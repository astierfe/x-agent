"""
RSS feed configuration for x-agent sourcing module.

Contains curated lists of target tech RSS feeds organized by topic,
matching the scope defined in specs.md:
  - Web3 & Blockchain Engineering
  - Cross-chain Interoperability Protocols
  - AI & Agentic Frameworks
  - Enterprise Legacy Architectures (SOA, ESB, Enterprise Integration)

Each feed entry is a dict with 'name' and 'url' keys.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Per-topic feed lists
# ---------------------------------------------------------------------------

WEB3_BLOCKCHAIN_FEEDS: list[dict[str, str]] = [
    {
        "name": "CoinDesk - Blockchain",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss",
    },
    {
        "name": "The Block",
        "url": "https://www.theblock.co/rss",
    },
    {
        "name": "Bankless",
        "url": "https://feeds.simplecast.com/CVfZqC0q",
    },
    {
        "name": "Ethereum Foundation Blog",
        "url": "https://blog.ethereum.org/feed.xml",
    },
    {
        "name": "Paradigm Blog",
        "url": "https://www.paradigm.xyz/rss",
    },
]

CROSSCHAIN_FEEDS: list[dict[str, str]] = [
    {
        "name": "Cosmos Blog",
        "url": "https://blog.cosmos.network/feed",
    },
    {
        "name": "Polkadot Blog",
        "url": "https://polkadot.network/blog/feed",
    },
    {
        "name": "Chainlink Blog",
        "url": "https://blog.chain.link/feed",
    },
    {
        "name": "LayerZero Blog",
        "url": "https://medium.com/feed/layerzero-official",
    },
    {
        "name": "Wormhole Blog",
        "url": "https://wormhole.com/blog/rss",
    },
]

AI_AGENTIC_FEEDS: list[dict[str, str]] = [
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
    },
    {
        "name": "Anthropic Blog",
        "url": "https://www.anthropic.com/blog/rss.xml",
    },
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
    },
    {
        "name": "LangChain Blog",
        "url": "https://blog.langchain.dev/rss",
    },
    {
        "name": "Towards Data Science - AI",
        "url": "https://towardsdatascience.com/feed",
    },
    {
        "name": "Simon Willison's Weblog",
        "url": "https://simonwillison.net/atom/everything/",
    },
]

ENTERPRISE_LEGACY_FEEDS: list[dict[str, str]] = [
    {
        "name": "AWS Architecture Blog",
        "url": "https://aws.amazon.com/blogs/architecture/feed",
    },
    {
        "name": "Google Cloud Blog",
        "url": "https://cloudblog.withgoogle.com/rss",
    },
    {
        "name": "IBM Developer Blog",
        "url": "https://developer.ibm.com/blogs/feed",
    },
    {
        "name": "InfoQ - Architecture & Design",
        "url": "https://feed.infoq.com/architecture-design",
    },
    {
        "name": "Martin Fowler",
        "url": "https://martinfowler.com/feed.atom",
    },
    {
        "name": "The New Stack",
        "url": "https://thenewstack.io/feed",
    },
]

# ---------------------------------------------------------------------------
# Master feed list -- flat union of all topic feeds
# ---------------------------------------------------------------------------

ALL_FEEDS: list[dict[str, str]] = (
    WEB3_BLOCKCHAIN_FEEDS
    + CROSSCHAIN_FEEDS
    + AI_AGENTIC_FEEDS
    + ENTERPRISE_LEGACY_FEEDS
)

# ---------------------------------------------------------------------------
# Convenience lookup keyed by topic slug
# ---------------------------------------------------------------------------

TOPIC_FEEDS: dict[str, list[dict[str, str]]] = {
    "web3_blockchain": WEB3_BLOCKCHAIN_FEEDS,
    "crosschain": CROSSCHAIN_FEEDS,
    "ai_agentic": AI_AGENTIC_FEEDS,
    "enterprise_legacy": ENTERPRISE_LEGACY_FEEDS,
}