# Roadmap & Progress Tracker - x-agent
This document tracks the development progress, environment configuration, and future milestones for the x-agent project.

Global Progress Status :
[x] Session 1: Environment Setup (WSL2, Docker, VS Code, Cline & OpenRouter configuration)
[x] Session 2: Specifications & Architecture (Writing specs.md and designing the initial RSS module)
[x] Session 3: Dockerization & First Run (Container isolation, fixing the feedparser timeout bug, verifying network reachability, and local Git initialization)
[x] One-Off Action: GitHub Remote Link (Successfully linked the local repository to GitHub via SSH)
[x] One-Off Action: Agent Guardrails (.clinerules) (Set up rules for host safety, code standards, and mandatory English documentation)
[ ] Session 4: SQLite Persistence (Data modeling, database operations, and article deduplication)
[ ] Session 5: Intelligence Engine (LLM) (Smart filtering, content summarization, and draft creation for X)
[ ] Session 6: Local Operator Interface (UI) (Human-in-the-loop validation dashboard before publishing)

Accomplished Milestones (Sessions 1 to 3 + Transition Actions) :
1. Environment & Tooling
- WSL2 (Ubuntu) & Docker Desktop fully functional and synchronized.
- VS Code connected to WSL2 with Python, Docker, and Git extensions.
- Remote GitHub Repository linked via SSH (git@github.com:astierfe/x-agent.git) with the initial codebase pushed to the main branch.
- .clinerules file created to bound the agent's behavior: no execution on the host machine, mandatory Docker sandbox, strict Python typing, and strictly English comments/logs.

2. Sourcing Engine (Module 1)
- Created src/sourcing/feed_config.py with 22 curated tech RSS feeds across target topics (Web3, Cross-chain, AI, Enterprise Legacy).
- Created src/sourcing/rss_parser.py: a robust feedparser wrapper that:
    - Normalizes feed items into structured Python dataclasses (FeedEntry, FeedResult, FetchOutcome).
    - Gracefully handles network timeouts and socket errors using Python's native socket library.
    - Mitigates malformed XML errors through feedparser's bozo flags.

3. Isolation & Verification
- Created requirements.txt containing feedparser>=6.0.10.
- Implemented a lean Dockerfile based on python:3.11-slim.
- Created a temporary main.py entrypoint to run batch operations.
- Test Result: Successfully retrieved and parsed 1,826 live tech articles directly through the Docker container network.    

Upcoming Development Milestones :

Next Milestone — Session 4: SQLite Persistence :
Prevent processing duplicate articles and manage local storage.
1. Schema Initialization: Create an articles table in a local SQLite file inside the allowed host directory (data/x_agent.db).
2. Deduplication at Source: Enforce unique constraints on article URLs to store only unseen content.
3. Docker Persistence: Mount the container data directory /app/data to the host WSL2 filesystem (./data) ensuring the database survives container restarts.

Session 5: Intelligence Engine (LLM)
1. Set up an API client within the Python environment to connect to a high-quality analysis model (e.g., DeepSeek or Claude via OpenRouter).
2. Create an agentic relevance filter: Evaluate fetched articles and discard out-of-scope noise.
3. Post Generator: Write concise 280-character drafts, Threads, or context-aware replies.

Session 6: Local Operator Interface (UI)
1. Build a minimalist web UI using a lightweight framework like Streamlit or Gradio running in a sidecar Docker container.
2. Architecture: Mount the `./data` host directory to the UI container in read-only mode (`ro`) to allow data visualization without risking SQLite concurrent write locks.
3. Allow the human operator to view pending drafts, edit them, approve them for publication, or reject them.

Budget Rules & Best Practices
- Cline Operating Mode: Always use "Plan Mode" at the start of a session to review this roadmap and propose steps. Switch to "Act Mode" only after user validation.
- The "New Chat" (+) Rule in Cline: Clean the active chat history as soon as a session is validated. This resets the context window and avoids exponential token caching costs.
- Iterative Debugging Guardrails: If Cline fails twice on the exact same error, stop the loop. Inspect the terminal logs manually and provide precise instructions rather than letting the agent guess.