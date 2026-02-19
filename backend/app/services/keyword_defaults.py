"""Default AUP keyword themes and their seed keywords.

Called once on startup — only inserts themes that don't already exist,
so user edits are never overwritten.
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KeywordTheme, Keyword

logger = logging.getLogger(__name__)

# ── Default themes + keywords ─────────────────────────────────────────

DEFAULTS: dict[str, dict] = {
    "Gambling": {
        "color": "#f44336",
        "keywords": [
            "poker", "casino", "blackjack", "roulette", "sportsbook",
            "sports betting", "bet365", "draftkings", "fanduel", "bovada",
            "betonline", "mybookie", "slots", "slot machine", "parlay",
            "wager", "bookie", "betway", "888casino", "pokerstars",
            "william hill", "ladbrokes", "betfair", "unibet", "pinnacle",
        ],
    },
    "Gaming": {
        "color": "#9c27b0",
        "keywords": [
            "steam", "steamcommunity", "steampowered", "epic games",
            "epicgames", "origin.com", "battle.net", "blizzard",
            "roblox", "minecraft", "fortnite", "valorant", "league of legends",
            "twitch", "twitch.tv", "discord", "discord.gg", "xbox live",
            "playstation network", "gog.com", "itch.io", "gamepass",
            "riot games", "ubisoft", "ea.com",
        ],
    },
    "Streaming": {
        "color": "#ff9800",
        "keywords": [
            "netflix", "hulu", "disney+", "disneyplus", "hbomax",
            "amazon prime video", "peacock", "paramount+", "crunchyroll",
            "funimation", "spotify", "pandora", "soundcloud", "deezer",
            "tidal", "apple music", "youtube music", "pluto tv",
            "tubi", "vudu", "plex",
        ],
    },
    "Downloads / Piracy": {
        "color": "#ff5722",
        "keywords": [
            "torrent", "bittorrent", "utorrent", "qbittorrent", "piratebay",
            "thepiratebay", "1337x", "rarbg", "yts", "kickass",
            "limewire", "frostwire", "mega.nz", "rapidshare", "mediafire",
            "zippyshare", "uploadhaven", "fitgirl", "repack", "crack",
            "keygen", "warez", "nulled", "pirate", "magnet:",
        ],
    },
    "Adult Content": {
        "color": "#e91e63",
        "keywords": [
            "pornhub", "xvideos", "xhamster", "onlyfans", "chaturbate",
            "livejasmin", "brazzers", "redtube", "youporn", "xnxx",
            "porn", "xxx", "nsfw", "adult content", "cam site",
            "stripchat", "bongacams",
        ],
    },
    "Social Media": {
        "color": "#2196f3",
        "keywords": [
            "facebook", "instagram", "tiktok", "snapchat", "pinterest",
            "reddit", "tumblr", "myspace", "whatsapp web", "telegram web",
            "signal web", "wechat web", "twitter.com", "x.com",
            "threads.net", "mastodon", "bluesky",
        ],
    },
    "Job Search": {
        "color": "#4caf50",
        "keywords": [
            "indeed", "linkedin jobs", "glassdoor", "monster.com",
            "ziprecruiter", "careerbuilder", "dice.com", "hired.com",
            "angel.co", "wellfound", "levels.fyi", "salary.com",
            "payscale", "resume", "cover letter", "job application",
        ],
    },
    "Shopping": {
        "color": "#00bcd4",
        "keywords": [
            "amazon.com", "ebay", "etsy", "walmart.com", "target.com",
            "bestbuy", "aliexpress", "wish.com", "shein", "temu",
            "wayfair", "overstock", "newegg", "zappos", "coupon",
            "promo code", "add to cart",
        ],
    },
}


async def seed_defaults(db: AsyncSession) -> int:
    """Insert default themes + keywords for any theme name not already in DB.

    Returns the number of themes inserted (0 if all already exist).
    """
    # Rename legacy theme names
    _renames = [("Social Media (Personal)", "Social Media")]
    for old_name, new_name in _renames:
        old = await db.scalar(select(KeywordTheme.id).where(KeywordTheme.name == old_name))
        if old:
            await db.execute(
                KeywordTheme.__table__.update()
                .where(KeywordTheme.name == old_name)
                .values(name=new_name)
            )
            await db.commit()
            logger.info("Renamed AUP theme '%s' → '%s'", old_name, new_name)

    inserted = 0
    for theme_name, meta in DEFAULTS.items():
        exists = await db.scalar(
            select(KeywordTheme.id).where(KeywordTheme.name == theme_name)
        )
        if exists:
            continue

        theme = KeywordTheme(
            name=theme_name,
            color=meta["color"],
            enabled=True,
            is_builtin=True,
        )
        db.add(theme)
        await db.flush()  # get theme.id

        for kw in meta["keywords"]:
            db.add(Keyword(theme_id=theme.id, value=kw))

        inserted += 1
        logger.info("Seeded AUP theme '%s' with %d keywords", theme_name, len(meta["keywords"]))

    if inserted:
        await db.commit()
        logger.info("Seeded %d AUP keyword themes", inserted)
    else:
        logger.debug("All default AUP themes already present")

    return inserted
