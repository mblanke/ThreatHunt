"""IOC Enrichment Engine — VirusTotal, AbuseIPDB, Shodan integrations.

Provides automated IOC enrichment with caching and rate limiting.
Enriches IPs, hashes, domains with threat intelligence verdicts.
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import EnrichmentResult as EnrichmentDB

logger = logging.getLogger(__name__)


class IOCType(str, Enum):
    IP = "ip"
    DOMAIN = "domain"
    HASH_MD5 = "hash_md5"
    HASH_SHA1 = "hash_sha1"
    HASH_SHA256 = "hash_sha256"
    URL = "url"


class Verdict(str, Enum):
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass
class EnrichmentResultData:
    """Enrichment result from a provider."""
    ioc_value: str
    ioc_type: IOCType
    source: str
    verdict: Verdict
    score: float = 0.0                # 0-100 normalized threat score
    raw_data: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    country: str = ""
    asn: str = ""
    org: str = ""
    last_seen: str = ""
    error: str = ""
    latency_ms: int = 0


# ── Rate limiter ──────────────────────────────────────────────────────


class RateLimiter:
    """Simple token bucket rate limiter for API calls."""

    def __init__(self, calls_per_minute: int = 4):
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute
        self._last_call: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self._last_call = time.monotonic()


# ── Provider base ─────────────────────────────────────────────────────


class EnrichmentProvider:
    """Base class for enrichment providers."""

    name: str = "base"

    def __init__(self, api_key: str = "", rate_limit: int = 4):
        self.api_key = api_key
        self.rate_limiter = RateLimiter(rate_limit)
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10, read=30, write=10, pool=5),
            )
        return self._client

    async def cleanup(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def enrich(self, ioc_value: str, ioc_type: IOCType) -> EnrichmentResultData:
        raise NotImplementedError


# ── VirusTotal ────────────────────────────────────────────────────────


class VirusTotalProvider(EnrichmentProvider):
    """VirusTotal v3 API provider."""

    name = "virustotal"
    BASE_URL = "https://www.virustotal.com/api/v3"

    def __init__(self):
        super().__init__(api_key=settings.VIRUSTOTAL_API_KEY, rate_limit=4)

    def _headers(self) -> dict:
        return {"x-apikey": self.api_key}

    async def enrich(self, ioc_value: str, ioc_type: IOCType) -> EnrichmentResultData:
        if not self.is_configured:
            return EnrichmentResultData(
                ioc_value=ioc_value, ioc_type=ioc_type,
                source=self.name, verdict=Verdict.ERROR,
                error="VirusTotal API key not configured",
            )

        await self.rate_limiter.acquire()
        start = time.monotonic()

        try:
            endpoint = self._get_endpoint(ioc_value, ioc_type)
            if not endpoint:
                return EnrichmentResultData(
                    ioc_value=ioc_value, ioc_type=ioc_type,
                    source=self.name, verdict=Verdict.ERROR,
                    error=f"Unsupported IOC type: {ioc_type}",
                )

            client = self._get_client()
            resp = await client.get(endpoint, headers=self._headers())
            latency_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code == 404:
                return EnrichmentResultData(
                    ioc_value=ioc_value, ioc_type=ioc_type,
                    source=self.name, verdict=Verdict.UNKNOWN,
                    latency_ms=latency_ms,
                )

            resp.raise_for_status()
            data = resp.json()
            attrs = data.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})

            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            total = sum(stats.values()) if stats else 0

            # Determine verdict
            if malicious > 3:
                verdict = Verdict.MALICIOUS
            elif malicious > 0 or suspicious > 2:
                verdict = Verdict.SUSPICIOUS
            elif total > 0:
                verdict = Verdict.CLEAN
            else:
                verdict = Verdict.UNKNOWN

            score = (malicious / total * 100) if total > 0 else 0

            tags = attrs.get("tags", [])
            if attrs.get("type_description"):
                tags.append(attrs["type_description"])

            return EnrichmentResultData(
                ioc_value=ioc_value,
                ioc_type=ioc_type,
                source=self.name,
                verdict=verdict,
                score=round(score, 1),
                raw_data={
                    "stats": stats,
                    "reputation": attrs.get("reputation", 0),
                    "type_description": attrs.get("type_description", ""),
                    "names": attrs.get("names", [])[:5],
                },
                tags=tags[:10],
                country=attrs.get("country", ""),
                asn=str(attrs.get("asn", "")),
                org=attrs.get("as_owner", ""),
                last_seen=attrs.get("last_analysis_date", ""),
                latency_ms=latency_ms,
            )

        except httpx.HTTPStatusError as e:
            return EnrichmentResultData(
                ioc_value=ioc_value, ioc_type=ioc_type,
                source=self.name, verdict=Verdict.ERROR,
                error=f"HTTP {e.response.status_code}",
                latency_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            return EnrichmentResultData(
                ioc_value=ioc_value, ioc_type=ioc_type,
                source=self.name, verdict=Verdict.ERROR,
                error=str(e),
                latency_ms=int((time.monotonic() - start) * 1000),
            )

    def _get_endpoint(self, ioc_value: str, ioc_type: IOCType) -> str | None:
        if ioc_type == IOCType.IP:
            return f"{self.BASE_URL}/ip_addresses/{ioc_value}"
        elif ioc_type == IOCType.DOMAIN:
            return f"{self.BASE_URL}/domains/{ioc_value}"
        elif ioc_type in (IOCType.HASH_MD5, IOCType.HASH_SHA1, IOCType.HASH_SHA256):
            return f"{self.BASE_URL}/files/{ioc_value}"
        elif ioc_type == IOCType.URL:
            url_id = hashlib.sha256(ioc_value.encode()).hexdigest()
            return f"{self.BASE_URL}/urls/{url_id}"
        return None


# ── AbuseIPDB ─────────────────────────────────────────────────────────


class AbuseIPDBProvider(EnrichmentProvider):
    """AbuseIPDB API provider — IP reputation."""

    name = "abuseipdb"
    BASE_URL = "https://api.abuseipdb.com/api/v2"

    def __init__(self):
        super().__init__(api_key=settings.ABUSEIPDB_API_KEY, rate_limit=10)

    async def enrich(self, ioc_value: str, ioc_type: IOCType) -> EnrichmentResultData:
        if ioc_type != IOCType.IP:
            return EnrichmentResultData(
                ioc_value=ioc_value, ioc_type=ioc_type,
                source=self.name, verdict=Verdict.ERROR,
                error="AbuseIPDB only supports IP lookups",
            )

        if not self.is_configured:
            return EnrichmentResultData(
                ioc_value=ioc_value, ioc_type=ioc_type,
                source=self.name, verdict=Verdict.ERROR,
                error="AbuseIPDB API key not configured",
            )

        await self.rate_limiter.acquire()
        start = time.monotonic()

        try:
            client = self._get_client()
            resp = await client.get(
                f"{self.BASE_URL}/check",
                params={"ipAddress": ioc_value, "maxAgeInDays": 90, "verbose": "true"},
                headers={"Key": self.api_key, "Accept": "application/json"},
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            resp.raise_for_status()
            data = resp.json().get("data", {})

            abuse_score = data.get("abuseConfidenceScore", 0)
            total_reports = data.get("totalReports", 0)

            if abuse_score >= 75:
                verdict = Verdict.MALICIOUS
            elif abuse_score >= 25 or total_reports > 5:
                verdict = Verdict.SUSPICIOUS
            elif total_reports == 0:
                verdict = Verdict.UNKNOWN
            else:
                verdict = Verdict.CLEAN

            categories = data.get("reports", [])
            tags = []
            for report in categories[:10]:
                for cat_id in report.get("categories", []):
                    tag = self._category_name(cat_id)
                    if tag and tag not in tags:
                        tags.append(tag)

            return EnrichmentResultData(
                ioc_value=ioc_value,
                ioc_type=ioc_type,
                source=self.name,
                verdict=verdict,
                score=float(abuse_score),
                raw_data={
                    "abuse_confidence_score": abuse_score,
                    "total_reports": total_reports,
                    "is_whitelisted": data.get("isWhitelisted"),
                    "is_tor": data.get("isTor", False),
                    "usage_type": data.get("usageType", ""),
                    "isp": data.get("isp", ""),
                },
                tags=tags[:10],
                country=data.get("countryCode", ""),
                org=data.get("isp", ""),
                last_seen=data.get("lastReportedAt", ""),
                latency_ms=latency_ms,
            )

        except Exception as e:
            return EnrichmentResultData(
                ioc_value=ioc_value, ioc_type=ioc_type,
                source=self.name, verdict=Verdict.ERROR,
                error=str(e),
                latency_ms=int((time.monotonic() - start) * 1000),
            )

    @staticmethod
    def _category_name(cat_id: int) -> str:
        categories = {
            1: "DNS Compromise", 2: "DNS Poisoning", 3: "Fraud Orders",
            4: "DDoS Attack", 5: "FTP Brute-Force", 6: "Ping of Death",
            7: "Phishing", 8: "Fraud VoIP", 9: "Open Proxy",
            10: "Web Spam", 11: "Email Spam", 12: "Blog Spam",
            13: "VPN IP", 14: "Port Scan", 15: "Hacking",
            16: "SQL Injection", 17: "Spoofing", 18: "Brute-Force",
            19: "Bad Web Bot", 20: "Exploited Host", 21: "Web App Attack",
            22: "SSH", 23: "IoT Targeted",
        }
        return categories.get(cat_id, "")


# ── Shodan ────────────────────────────────────────────────────────────


class ShodanProvider(EnrichmentProvider):
    """Shodan API provider — infrastructure intelligence."""

    name = "shodan"
    BASE_URL = "https://api.shodan.io"

    def __init__(self):
        super().__init__(api_key=settings.SHODAN_API_KEY, rate_limit=1)

    async def enrich(self, ioc_value: str, ioc_type: IOCType) -> EnrichmentResultData:
        if ioc_type != IOCType.IP:
            return EnrichmentResultData(
                ioc_value=ioc_value, ioc_type=ioc_type,
                source=self.name, verdict=Verdict.ERROR,
                error="Shodan only supports IP lookups",
            )

        if not self.is_configured:
            return EnrichmentResultData(
                ioc_value=ioc_value, ioc_type=ioc_type,
                source=self.name, verdict=Verdict.ERROR,
                error="Shodan API key not configured",
            )

        await self.rate_limiter.acquire()
        start = time.monotonic()

        try:
            client = self._get_client()
            resp = await client.get(
                f"{self.BASE_URL}/shodan/host/{ioc_value}",
                params={"key": self.api_key, "minify": "true"},
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code == 404:
                return EnrichmentResultData(
                    ioc_value=ioc_value, ioc_type=ioc_type,
                    source=self.name, verdict=Verdict.UNKNOWN,
                    latency_ms=latency_ms,
                )

            resp.raise_for_status()
            data = resp.json()

            ports = data.get("ports", [])
            vulns = data.get("vulns", [])
            tags_raw = data.get("tags", [])

            # Determine verdict based on open ports and vulns
            if vulns:
                verdict = Verdict.SUSPICIOUS
                score = min(len(vulns) * 15, 100.0)
            elif len(ports) > 20:
                verdict = Verdict.SUSPICIOUS
                score = 40.0
            else:
                verdict = Verdict.CLEAN
                score = 0.0

            tags = tags_raw[:10]
            if vulns:
                tags.extend([f"CVE: {v}" for v in vulns[:5]])

            return EnrichmentResultData(
                ioc_value=ioc_value,
                ioc_type=ioc_type,
                source=self.name,
                verdict=verdict,
                score=score,
                raw_data={
                    "ports": ports[:20],
                    "vulns": vulns[:10],
                    "os": data.get("os"),
                    "hostnames": data.get("hostnames", [])[:5],
                    "domains": data.get("domains", [])[:5],
                    "last_update": data.get("last_update", ""),
                },
                tags=tags[:15],
                country=data.get("country_code", ""),
                asn=data.get("asn", ""),
                org=data.get("org", ""),
                last_seen=data.get("last_update", ""),
                latency_ms=latency_ms,
            )

        except Exception as e:
            return EnrichmentResultData(
                ioc_value=ioc_value, ioc_type=ioc_type,
                source=self.name, verdict=Verdict.ERROR,
                error=str(e),
                latency_ms=int((time.monotonic() - start) * 1000),
            )


# ── Enrichment Engine (orchestrator) ──────────────────────────────────


class EnrichmentEngine:
    """Orchestrates IOC enrichment across all providers with caching."""

    CACHE_TTL_HOURS = 24

    def __init__(self):
        self.providers: list[EnrichmentProvider] = [
            VirusTotalProvider(),
            AbuseIPDBProvider(),
            ShodanProvider(),
        ]

    @property
    def configured_providers(self) -> list[EnrichmentProvider]:
        return [p for p in self.providers if p.is_configured]

    async def enrich_ioc(
        self,
        ioc_value: str,
        ioc_type: IOCType,
        db: AsyncSession | None = None,
        skip_cache: bool = False,
    ) -> list[EnrichmentResultData]:
        """Enrich a single IOC across all configured providers.

        Uses cached results from DB when available.
        """
        results: list[EnrichmentResultData] = []

        # Check cache first
        if db and not skip_cache:
            cached = await self._get_cached(db, ioc_value, ioc_type)
            if cached:
                logger.info(f"Cache hit for {ioc_type.value}:{ioc_value} ({len(cached)} results)")
                return cached

        # Query all applicable providers in parallel
        tasks = []
        for provider in self.configured_providers:
            # Skip providers that don't support this IOC type
            if ioc_type in (IOCType.DOMAIN,) and provider.name in ("abuseipdb", "shodan"):
                continue
            if ioc_type == IOCType.IP and provider.name == "virustotal":
                tasks.append(provider.enrich(ioc_value, ioc_type))
            elif ioc_type == IOCType.IP:
                tasks.append(provider.enrich(ioc_value, ioc_type))
            elif ioc_type in (IOCType.HASH_MD5, IOCType.HASH_SHA1, IOCType.HASH_SHA256):
                if provider.name == "virustotal":
                    tasks.append(provider.enrich(ioc_value, ioc_type))
            elif ioc_type == IOCType.DOMAIN:
                if provider.name == "virustotal":
                    tasks.append(provider.enrich(ioc_value, ioc_type))
            elif ioc_type == IOCType.URL:
                if provider.name == "virustotal":
                    tasks.append(provider.enrich(ioc_value, ioc_type))

        if tasks:
            results = list(await asyncio.gather(*tasks, return_exceptions=False))

        # Cache results
        if db and results:
            await self._cache_results(db, results)

        return results

    async def enrich_batch(
        self,
        iocs: list[tuple[str, IOCType]],
        db: AsyncSession | None = None,
        concurrency: int = 3,
    ) -> dict[str, list[EnrichmentResultData]]:
        """Enrich a batch of IOCs with controlled concurrency."""
        sem = asyncio.Semaphore(concurrency)
        all_results: dict[str, list[EnrichmentResultData]] = {}

        async def _enrich_one(value: str, ioc_type: IOCType):
            async with sem:
                result = await self.enrich_ioc(value, ioc_type, db=db)
                all_results[value] = result

        tasks = [_enrich_one(v, t) for v, t in iocs]
        await asyncio.gather(*tasks, return_exceptions=True)
        return all_results

    async def enrich_dataset_iocs(
        self,
        rows: list[dict],
        ioc_columns: dict,
        db: AsyncSession | None = None,
        max_iocs: int = 50,
    ) -> dict[str, list[EnrichmentResultData]]:
        """Auto-enrich IOCs found in a dataset.

        Extracts unique IOC values from the identified columns and enriches them.
        """
        iocs_to_enrich: list[tuple[str, IOCType]] = []
        seen = set()

        for col_name, col_type in ioc_columns.items():
            ioc_type = self._map_column_type(col_type)
            if not ioc_type:
                continue

            for row in rows:
                value = row.get(col_name, "")
                if value and value not in seen:
                    seen.add(value)
                    iocs_to_enrich.append((str(value), ioc_type))

                if len(iocs_to_enrich) >= max_iocs:
                    break

            if len(iocs_to_enrich) >= max_iocs:
                break

        if iocs_to_enrich:
            return await self.enrich_batch(iocs_to_enrich, db=db)
        return {}

    async def _get_cached(
        self,
        db: AsyncSession,
        ioc_value: str,
        ioc_type: IOCType,
    ) -> list[EnrichmentResultData] | None:
        """Check for cached enrichment results."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.CACHE_TTL_HOURS)
        stmt = (
            select(EnrichmentDB)
            .where(
                EnrichmentDB.ioc_value == ioc_value,
                EnrichmentDB.ioc_type == ioc_type.value,
                EnrichmentDB.cached_at >= cutoff,
            )
        )
        result = await db.execute(stmt)
        cached = result.scalars().all()

        if not cached:
            return None

        return [
            EnrichmentResultData(
                ioc_value=c.ioc_value,
                ioc_type=IOCType(c.ioc_type),
                source=c.source,
                verdict=Verdict(c.verdict),
                score=c.score or 0.0,
                raw_data=c.raw_data or {},
                tags=c.tags or [],
                country=c.country or "",
                asn=c.asn or "",
                org=c.org or "",
            )
            for c in cached
        ]

    async def _cache_results(
        self,
        db: AsyncSession,
        results: list[EnrichmentResultData],
    ):
        """Cache enrichment results in the database."""
        for r in results:
            if r.verdict == Verdict.ERROR:
                continue  # Don't cache errors
            entry = EnrichmentDB(
                ioc_value=r.ioc_value,
                ioc_type=r.ioc_type.value,
                source=r.source,
                verdict=r.verdict.value,
                score=r.score,
                raw_data=r.raw_data,
                tags=r.tags,
                country=r.country,
                asn=r.asn,
                org=r.org,
            )
            db.add(entry)
        try:
            await db.flush()
        except Exception as e:
            logger.warning(f"Failed to cache enrichment: {e}")

    @staticmethod
    def _map_column_type(col_type: str) -> IOCType | None:
        """Map column type from normalizer to IOCType."""
        mapping = {
            "ip": IOCType.IP,
            "ip_address": IOCType.IP,
            "src_ip": IOCType.IP,
            "dst_ip": IOCType.IP,
            "domain": IOCType.DOMAIN,
            "hash_md5": IOCType.HASH_MD5,
            "hash_sha1": IOCType.HASH_SHA1,
            "hash_sha256": IOCType.HASH_SHA256,
            "url": IOCType.URL,
        }
        return mapping.get(col_type)

    async def cleanup(self):
        for provider in self.providers:
            await provider.cleanup()

    def status(self) -> dict:
        """Return enrichment engine status."""
        return {
            "providers": {
                p.name: {"configured": p.is_configured}
                for p in self.providers
            },
            "cache_ttl_hours": self.CACHE_TTL_HOURS,
        }


# Singleton
enrichment_engine = EnrichmentEngine()
