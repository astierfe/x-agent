# Roadmap & Progress Tracker - x-agent
This document tracks the development progress, environment configuration, and future milestones for the **x-agent** project.

## Global Progress Status
-   [x] **Session 1: Environment Setup** (WSL2, Docker, VS Code, Cline & OpenRouter configuration)
-   [x] **Session 2: Specifications & Architecture** (Writing `specs.md` and designing the initial RSS module)
-   [x] **Session 3: Dockerization & First Run** (Container isolation, fixing the feedparser timeout bug, verifying network reachability, and local Git initialization)    
-   [x] **One-Off Action: GitHub Remote Link** (Successfully linked the local repository to GitHub via SSH)    
-   [x] **One-Off Action: Agent Guardrails (.clinerules)** (Set up rules for host safety, code standards, and mandatory English documentation)    
-   [x] **Session 4: SQLite Persistence** (Data modeling, database operations, and article deduplication)    
-   [x] **Session 5: Intelligence Engine (LLM)** (Smart filtering, content summarization, and draft creation for X)    
-   [x] **Session 6: Local Operator Interface (UI)** (Human-in-the-loop validation dashboard before publishing)  

## Accomplished Milestones (Sessions 1 to 5 + Transition Actions)
### 1. Environment & Tooling
-   **WSL2 (Ubuntu) & Docker Desktop** fully functional and synchronized.    
-   **VS Code** connected to WSL2 with Python, Docker, and Git extensions.    
-   **Remote GitHub Repository** linked via SSH (`git@github.com:astierfe/x-agent.git`) with the codebase pushed to the `main` branch.    
-   **`.clinerules` file created** to bound the agent's behavior: no execution on the host machine, mandatory Docker sandbox, strict Python typing, and strictly English comments/logs.   

### 2. Sourcing Engine (Module 1)
-   Created `src/sourcing/feed_config.py` with **22 curated tech RSS feeds** across target topics (Web3, Cross-chain, AI, Enterprise Legacy).    
-   Created `src/sourcing/rss_parser.py`: a robust feedparser wrapper that handles network timeouts, socket errors, and malformed XML gracefully.    

### 3. Database & Persistence Layer (Module 2)
-   Initialized SQLite database at `data/x_agent.db` (mapped via Docker volume).    
-   Designed a strictly typed database management module in `src/database/db_manager.py` using Python context managers (`with`) for safe transactions.    
-   Implemented WAL (Write-Ahead Logging) journal mode to allow concurrent read/write operations without locking issues.    
-   Integrated `INSERT OR IGNORE` logic on unique article URL constraints to deduplicate content automatically.    

### 4. Intelligence Engine & LLM Orchestration (Module 3)
-   **Unified API Client (`llm_client.py`)**: Designed a zero-dependency OpenRouter client utilizing Python's native `urllib.request`. Features built-in exponential backoff retry logic and dynamic model routing:    
    -   _Sandbox (Default)_: `google/gemma-4-31b-it:free` for costless testing.        
    -   _Production_: `deepseek/deepseek-chat` for cost-effective structured formatting.        
    -   _Social Tone_: `xai/grok-2` (or `grok-beta`) for platform-native generation.        
-   **Relevance Classifier (`filter.py`)**: Built a robust classification prompt yielding structured JSON. Supported by a bulletproof, brace-nesting parser that bypasses conversational noise and raw markdown fences to guarantee stable JSON loading.
    
-   **Post Generator (`post_generator.py`)**: Implemented a draft-writing module that crafts engaging X posts (< 280 characters), complete with clean truncation on word boundaries if limits are breached.
    
-   **Idempotent Storage Updates**: Expanded the SQLite schema with a separate `drafts` table (enforced via SQLite `PRAGMA foreign_keys = ON`). Programmed `main.py` to process only unseen articles using a `LEFT JOIN` on `drafts`. The engine logs all classification outcomes (including rejections), preventing redundant LLM calls on subsequent runs.
    
## Upcoming Development Milestones

### Next Milestone — Session 6: Local Operator Interface (UI)
The final stage of the MVP puts the human in control before anything goes live.

1.  **Streamlit/Gradio App**: Build a lightweight web interface running in a sidecar Docker container.    

2.  **Read-Only SQLite Access (`ro`)**: Mount the `./data` host directory to the UI container in read-only mode. This lets the user inspect data without database lockups or integrity risks.    

3.  **Draft Management Workflow**: Allow the operator to:    
    -   Browse filtered articles.        
    -   Inspect the LLM's classification reasoning and generated drafts.        
    -   Live-edit drafts and copy them to the clipboard in a single tap.        
    -   Manually request suggestions or replies by pasting comments.
        
## Budget Rules & Best Practices

-   **Cline Operating Mode**: Always use "Plan Mode" at the start of a session to review this roadmap and propose steps. Switch to "Act Mode" only after user validation.    
-   **The "New Chat" (`+`) Rule in Cline**: Clean the active chat history as soon as a session is validated to avoid exponential token caching costs.    
-   **Iterative Debugging Guardrails**: If Cline fails twice on the exact same error, stop the loop. Inspect the terminal logs manually and provide precise instructions.