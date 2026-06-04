# x-agent

An autonomous, human-in-the-loop Python agent designed to monitor tech ecosystems, filter insights via LLMs, and draft curated content for X (Twitter).

## Core Objective
`x-agent` continuously tracks specific technology sectors, synthesizes complex updates into high-value posts or threads, and prepares context-aware replies. To guarantee quality and brand safety, **no content is ever published without mandatory human validation** through a local operator interface.

## Target Topics
- **Web3 & Blockchain Engineering**
- **Cross-chain Interoperability Protocols**
- **AI & Agentic Frameworks**
- **Enterprise Legacy Architectures** (SOA, ESB, Enterprise Integration)

## System Architecture
The application is structured into three decoupled modules:
1. **Sourcing Engine:** A robust and rate-limit-free RSS feed parser that normalizes and deduplicates incoming tech articles.
2. **Intelligence Engine:** An LLM-powered processing pipeline that filters out noise, summarizes content, and generates platform-optimized drafts.
3. **Local Operator Interface:** A minimalist UI (Streamlit/Gradio) allowing the operator to review, edit, approve, or reject pending drafts.

## Tech Stack & Constraints
- **Language:** Python 3.11+ (Strict typing)
- **Containerization:** 100% Docker-isolated environment running under WSL2 (Ubuntu)
- **Storage:** SQLite (Single-file persistent storage via Docker volume)