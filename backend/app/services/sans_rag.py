"""SANS RAG service — queries the 300GB SANS courseware indexed in Open WebUI.

Provides contextual SANS references for threat hunting guidance.
Uses two approaches:
1. Open WebUI RAG pipeline (if configured with a knowledge collection)
2. Embedding-based semantic search against locally indexed SANS content
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from app.config import settings
from app.agents.providers_v2 import _get_client
from app.agents.registry import Node

logger = logging.getLogger(__name__)


# ── SANS course catalog for reference matching ────────────────────────

SANS_COURSES = {
    "SEC401": "Security Essentials",
    "SEC504": "Hacker Tools, Techniques, and Incident Handling",
    "SEC503": "Network Monitoring and Threat Detection In-Depth",
    "SEC505": "Securing Windows and PowerShell Automation",
    "SEC506": "Securing Linux/Unix",
    "SEC510": "Public Cloud Security: AWS, Azure, and GCP",
    "SEC511": "Continuous Monitoring and Security Operations",
    "SEC530": "Defensible Security Architecture and Engineering",
    "SEC540": "Cloud Security and DevSecOps Automation",
    "SEC555": "SIEM with Tactical Analytics",
    "SEC560": "Enterprise Penetration Testing",
    "SEC565": "Red Team Operations and Adversary Emulation",
    "SEC573": "Automating Information Security with Python",
    "SEC575": "Mobile Device Security and Ethical Hacking",
    "SEC588": "Cloud Penetration Testing",
    "SEC599": "Defeating Advanced Adversaries - Purple Team Tactics",
    "FOR408": "Windows Forensic Analysis",
    "FOR498": "Digital Acquisition and Rapid Triage",
    "FOR500": "Windows Forensic Analysis",
    "FOR508": "Advanced Incident Response, Threat Hunting, and Digital Forensics",
    "FOR509": "Enterprise Cloud Forensics and Incident Response",
    "FOR518": "Mac and iOS Forensic Analysis and Incident Response",
    "FOR572": "Advanced Network Forensics: Threat Hunting, Analysis, and Incident Response",
    "FOR578": "Cyber Threat Intelligence",
    "FOR585": "Smartphone Forensic Analysis In-Depth",
    "FOR610": "Reverse-Engineering Malware: Malware Analysis Tools and Techniques",
    "FOR710": "Reverse-Engineering Malware: Advanced Code Analysis",
    "ICS410": "ICS/SCADA Security Essentials",
    "ICS515": "ICS Visibility, Detection, and Response",
}

# Topic-to-course mapping for fallback recommendations
TOPIC_COURSE_MAP = {
    "malware": ["FOR610", "FOR710", "SEC504"],
    "reverse engineer": ["FOR610", "FOR710"],
    "incident response": ["FOR508", "SEC504"],
    "forensic": ["FOR508", "FOR500", "FOR408"],
    "windows forensic": ["FOR500", "FOR408"],
    "network forensic": ["FOR572"],
    "threat hunting": ["FOR508", "SEC504", "FOR578"],
    "threat intelligence": ["FOR578"],
    "powershell": ["SEC505", "FOR508"],
    "lateral movement": ["SEC504", "FOR508"],
    "persistence": ["FOR508", "SEC504"],
    "privilege escalation": ["SEC504", "SEC560"],
    "credential": ["SEC504", "SEC560"],
    "memory forensic": ["FOR508"],
    "disk forensic": ["FOR500", "FOR408"],
    "registry": ["FOR500", "FOR408"],
    "event log": ["FOR508", "SEC555"],
    "siem": ["SEC555"],
    "log analysis": ["SEC555", "SEC503"],
    "network monitor": ["SEC503"],
    "pcap": ["SEC503", "FOR572"],
    "cloud": ["SEC510", "SEC540", "FOR509"],
    "aws": ["SEC510", "SEC540", "FOR509"],
    "azure": ["SEC510", "FOR509"],
    "linux": ["SEC506"],
    "mobile": ["SEC575", "FOR585"],
    "penetration test": ["SEC560", "SEC565"],
    "red team": ["SEC565", "SEC599"],
    "purple team": ["SEC599"],
    "python": ["SEC573"],
    "automation": ["SEC573", "SEC540"],
    "deobfusc": ["FOR610", "SEC504"],
    "base64": ["FOR610", "SEC504"],
    "shellcode": ["FOR610", "FOR710"],
    "ransomware": ["FOR508", "FOR610"],
    "phishing": ["SEC504", "FOR578"],
    "c2": ["FOR508", "SEC504", "FOR572"],
    "command and control": ["FOR508", "SEC504"],
    "exfiltration": ["FOR508", "FOR572", "SEC503"],
    "dns": ["FOR572", "SEC503"],
    "ioc": ["FOR508", "FOR578"],
    "mitre": ["FOR508", "SEC504", "SEC599"],
    "att&ck": ["FOR508", "SEC504"],
    "velociraptor": ["FOR508"],
    "volatility": ["FOR508"],
    "scheduled task": ["FOR508", "SEC504"],
    "service": ["FOR508", "SEC504"],
    "wmi": ["FOR508", "SEC504"],
    "process": ["FOR508"],
    "dll": ["FOR610", "FOR508"],
}


@dataclass
class RAGResult:
    """Result from a RAG query."""
    query: str
    context: str  # Retrieved relevant text
    sources: list[str] = field(default_factory=list)  # Source document names
    course_references: list[str] = field(default_factory=list)  # SANS course IDs
    confidence: float = 0.0
    latency_ms: int = 0


class SANSRAGService:
    """Service for querying SANS courseware via Open WebUI RAG pipeline."""

    def __init__(self):
        self.openwebui_url = settings.OPENWEBUI_URL.rstrip("/")
        self.api_key = settings.OPENWEBUI_API_KEY
        self.rag_model = settings.DEFAULT_FAST_MODEL
        self._available: bool | None = None

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def query(
        self,
        question: str,
        context: str = "",
        max_tokens: int = 1024,
    ) -> RAGResult:
        """Query SANS courseware for relevant context.

        Uses Open WebUI's RAG-enabled chat to retrieve from indexed SANS content.
        Falls back to topic-based course recommendations if RAG is unavailable.
        """
        start = time.monotonic()

        # Try Open WebUI RAG pipeline first
        try:
            result = await self._query_openwebui_rag(question, context, max_tokens)
            result.latency_ms = int((time.monotonic() - start) * 1000)

            # Enrich with course references if not already present
            if not result.course_references:
                result.course_references = self._match_courses(question)

            return result

        except Exception as e:
            logger.warning(f"RAG query failed, using fallback: {e}")
            # Fallback to topic-based matching
            courses = self._match_courses(question)
            return RAGResult(
                query=question,
                context="",
                sources=[],
                course_references=courses,
                confidence=0.3 if courses else 0.0,
                latency_ms=int((time.monotonic() - start) * 1000),
            )

    async def _query_openwebui_rag(
        self,
        question: str,
        context: str,
        max_tokens: int,
    ) -> RAGResult:
        """Query Open WebUI with RAG context retrieval.

        Open WebUI automatically retrieves from its indexed knowledge base
        when the model is configured with a knowledge collection.
        """
        client = _get_client()

        system_msg = (
            "You are a SANS cybersecurity knowledge assistant. "
            "Use your indexed SANS courseware to answer the question. "
            "Always cite the specific SANS course (e.g., FOR508, SEC504) "
            "and relevant section when referencing material. "
            "If the question relates to threat hunting procedures, "
            "reference the specific SANS methodology or framework."
        )

        messages = [
            {"role": "system", "content": system_msg},
        ]

        if context:
            messages.append({
                "role": "user",
                "content": f"Investigation context:\n{context}\n\nQuestion: {question}",
            })
        else:
            messages.append({"role": "user", "content": question})

        payload = {
            "model": self.rag_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "stream": False,
        }

        resp = await client.post(
            f"{self.openwebui_url}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()

        content = ""
        if data.get("choices"):
            content = data["choices"][0].get("message", {}).get("content", "")

        # Extract course references from response
        course_refs = self._extract_course_refs(content)
        sources = self._extract_sources(data)

        return RAGResult(
            query=question,
            context=content,
            sources=sources,
            course_references=course_refs,
            confidence=0.8 if content else 0.0,
        )

    def _extract_course_refs(self, text: str) -> list[str]:
        """Extract SANS course references from response text."""
        refs = set()
        # Match patterns like SEC504, FOR508, ICS410
        pattern = r'\b(SEC|FOR|ICS|MGT|AUD|DEV|LEG)\d{3}\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        # Need to get the full match
        full_pattern = r'\b(?:SEC|FOR|ICS|MGT|AUD|DEV|LEG)\d{3}\b'
        full_matches = re.findall(full_pattern, text, re.IGNORECASE)
        for m in full_matches:
            course_id = m.upper()
            if course_id in SANS_COURSES:
                refs.add(f"{course_id}: {SANS_COURSES[course_id]}")
            else:
                refs.add(course_id)
        return sorted(refs)

    def _extract_sources(self, api_response: dict) -> list[str]:
        """Extract source document references from Open WebUI response metadata."""
        sources = []
        # Open WebUI may include source metadata in various formats
        if "sources" in api_response:
            for src in api_response["sources"]:
                if isinstance(src, dict):
                    sources.append(src.get("name", src.get("title", str(src))))
                else:
                    sources.append(str(src))
        # Check in metadata
        for choice in api_response.get("choices", []):
            meta = choice.get("metadata", {})
            if "sources" in meta:
                for src in meta["sources"]:
                    if isinstance(src, dict):
                        sources.append(src.get("name", str(src)))
                    else:
                        sources.append(str(src))
        return sources[:10]  # Limit

    def _match_courses(self, query: str) -> list[str]:
        """Match query keywords to SANS courses using topic map."""
        q = query.lower()
        matched = set()
        for topic, courses in TOPIC_COURSE_MAP.items():
            if topic in q:
                for course_id in courses:
                    if course_id in SANS_COURSES:
                        matched.add(f"{course_id}: {SANS_COURSES[course_id]}")
        return sorted(matched)[:5]

    async def get_course_context(self, course_id: str) -> str:
        """Get a brief course description for context injection."""
        course_id = course_id.upper().split(":")[0].strip()
        if course_id in SANS_COURSES:
            return f"{course_id}: {SANS_COURSES[course_id]}"
        return ""

    async def enrich_prompt(
        self,
        query: str,
        investigation_context: str = "",
    ) -> str:
        """Generate SANS-enriched context to inject into agent prompts.

        Returns a context string with relevant SANS references.
        """
        result = await self.query(query, context=investigation_context, max_tokens=512)

        parts = []
        if result.context:
            parts.append(f"SANS Reference Context:\n{result.context}")
        if result.course_references:
            parts.append(f"Relevant SANS Courses: {', '.join(result.course_references)}")
        if result.sources:
            parts.append(f"Sources: {', '.join(result.sources[:5])}")

        return "\n".join(parts) if parts else ""

    async def health_check(self) -> dict:
        """Check RAG service availability."""
        try:
            client = _get_client()
            resp = await client.get(
                f"{self.openwebui_url}/v1/models",
                headers=self._headers(),
                timeout=5,
            )
            available = resp.status_code == 200
            self._available = available
            return {
                "available": available,
                "url": self.openwebui_url,
                "model": self.rag_model,
            }
        except Exception as e:
            self._available = False
            return {
                "available": False,
                "url": self.openwebui_url,
                "error": str(e),
            }


# Singleton
sans_rag = SANSRAGService()
