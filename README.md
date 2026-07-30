# CodeLens

> Paste any GitHub URL. Get instant, AI-generated architecture docs — purpose, layout, tech stack, Mermaid diagrams, and interactive chat.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Internal Flow](#internal-flow)
- [4-Layer Hierarchical RAG](#4-layer-hierarchical-rag)
- [Per-Section Relevant Files](#per-section-relevant-files)
- [Streaming & Conversation Memory](#streaming--conversation-memory)
- [Tech Stack](#tech-stack)
- [Repository Layout](#repository-layout)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Key Design Decisions](#key-design-decisions)

---

## Overview

CodeLens is an AI-powered codebase analysis tool. It takes a GitHub repository URL and produces a comprehensive architecture document — similar to what a senior engineer would write after spending hours reading the code.

### What the User Sees

1. **Landing page** — dark theme, URL input, recently analyzed repos (localStorage), popular repos grid
2. **Loading state** — "Analyzing repository..." with progress indication
3. **Wiki page** — full-screen architecture document with:
   - Collapsible folder tree (sidebar)
   - File structure viewer (real git clone data)
   - Per-section relevant source files (topic-based assignment)
   - 5 analysis sections rendered as markdown
   - Interactive chat panel at the bottom (with streaming)
4. **Chat** — ask follow-up questions about the codebase (with conversation memory)

### What the System Generates

| Section | Content | Relevant Files |
|---|---|---|
| Purpose & Scope | What the repo does, its goals | README, package.json, setup.py |
| Repository Layout | Directory structure + pattern | None (uses file tree viewer) |
| Source Layer | Key files and their purposes | Source files (.py, .js, .ts, etc.) |
| Tech Stack | Languages, frameworks, tools | Config files (requirements.txt, Dockerfile, etc.) |
| Architecture | System design + relationships | Main source files (main.py, api.py, etc.) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      DEVELOPER                          │
│                   (Enters GitHub URL)                    │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  REACT + VITE FRONTEND                   │
│                    (Port 5173)                           │
│                                                         │
│  HomePage ──► WikiPage ──► WikiTreeView (sidebar)       │
│  (recent      (FileTreeView (file structure)            │
│   repos via   MarkdownRenderer (content)                │
│   localStorage ChatPanel (streaming)                    │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  FASTAPI BACKEND                         │
│                    (Port 8000)                           │
│                                                         │
│  api.py (SSE + WebSocket) ──► main.py (orchestrator)    │
│       │                           │                     │
│       │              ┌────────────┼────────────┐        │
│       │              ▼            ▼            ▼        │
│       │    repo_cloner.py  hybrid_analyzer  db_utils   │
│       │    (git clone)     (Cerebras)      (PG + JSON) │
│       │              │                                 │
│       │              ▼                                 │
│       │    4-Layer Index (Embeddings)                   │
│       │    sentence-transformers                        │
└─────────────────────────────────────────────────────────┘
```

---

## Internal Flow

### Step 1: User Enters GitHub URL

```
User pastes: https://github.com/pallets/flask
                    │
                    ▼
        Frontend (HomePage.jsx)
        Sends POST /api/analysis
        { repo_url: "...", force_refresh: false }
```

### Step 2: Backend Receives Request

```
FastAPI (api.py)
    │
    ├──► Check PostgreSQL/JSON cache
    │    SELECT * FROM repo_analysis WHERE repo_url = '...'
    │
    ├──► Cache HIT? → Return cached result immediately (~50ms)
    │
    └──► Cache MISS? → Start full analysis pipeline (~15 sec)
```

### Step 3: Clone Repository & Read Files

```
repo_cloner.py
    │
    ├──► clone_repo()                    ── git clone --depth 1
    │    Shallow clone to temp directory (~3-5 sec)
    │
    ├──► read_all_files()                ── Local filesystem (os.walk)
    │    Reads all source files (.py, .js, .ts, etc.)
    │    Reads all config files (.gitignore, package.json, etc.)
    │    Builds complete file tree (every file, no limits)
    │
    └──► cleanup_repo()                  ── shutil.rmtree
         Remove temp directory

Total: ~4-6 seconds. No API rate limits.
```

### Step 4: Build 4-Layer Index

```
main.py → _get_or_build_index()
    │
    ├──► Layer 1: File Metadata (path, language, size, lines)
    ├──► Layer 2: AST Structure (functions, classes, imports)
    ├──► Layer 3: Dependency Graph (import relationships)
    └──► Layer 4: Code Chunks (function/class-level pieces)

Embeddings: sentence-transformers (all-MiniLM-L6-v2)
Index: SQLite (in-memory) + numpy vectors
```

### Step 5: LLM Generates Analysis

```
Cerebras LLM (zai-glm-4.7)
    │
    ├── Receives 4-layer context (~3-8K tokens)
    ├── Generates all 5 sections in one response
    ├── Takes ~10-15 seconds
    └── Returns structured output with headers
```

### Step 6: Post-Process & Cache

```
hybrid_analyzer.py
    │
    ├──► Parse sections (regex split by headers)
    ├──► Add inline source citations (file → GitHub link)
    ├──► Extract per-section relevant files (topic-based)
    │
    ▼
db_utils.py
    │
    ├──► PostgreSQL: UPSERT with metadata JSONB column
    │    (stores per-section files, commit hash, file tree)
    └──► JSON fallback: ~/.codelens/cache/{hash}.json

Frontend stores in analysisCache Map + localStorage
```

### Chat Flow (4-Layer RAG)

```
User: "How does authentication work?"
    │
    ▼
ChatPanel → POST /api/chat { repo_url, question, history }
    │
    ▼
main.py → chat_with_repo()
    │
    ├──► Detect query type (summary vs specific)
    ├──► Build 4-layer context (3K-8K tokens)
    ├──► Single Cerebras LLM call
    └──► Return streamed answer with citations
```

---

## 4-Layer Hierarchical RAG

| Layer | Content | When Sent | Token Cost | Implementation |
|---|---|---|---|---|
| **Layer 1** | File metadata (path, language, size, lines) | Always | ~1K tokens | `code_index.py` |
| **Layer 2** | AST structure (functions, classes, imports) | Always | ~2K tokens | `code_index.py` |
| **Layer 3** | Dependency graph (importers, imports) | Specific queries only | ~1-3K tokens | `query_builder.py` |
| **Layer 4** | Code chunks (function/class bodies) via embeddings | Specific queries only | ~2-5K tokens | `chunker.py` + `code_index.py` |

### Smart Query Detection

| Query Type | Examples | Layers Used | Token Cost |
|---|---|---|---|
| **Summary** | "What does this project do?", "Overview" | Layers 1-2 only | ~3K tokens |
| **Specific** | "Show me auth.py", "Who imports api.py?" | All 4 layers | ~8K tokens |

---

## Per-Section Relevant Files

Each wiki section shows only the files relevant to that topic:

| Section | Files Shown | Logic |
|---|---|---|
| Purpose & Scope | README.md, package.json, setup.py | Project entry points |
| Repository Layout | None | Uses file tree viewer instead |
| Source Layer | .py, .js, .ts, .tsx files + content mentions | Source code files |
| Tech Stack | requirements.txt, Dockerfile, tsconfig.json, etc. | Config/build files |
| Architecture | main.py, api.py, App.jsx, etc. | Core entry points |

Files are assigned by topic, not by scanning content. Max 15 files per section.

---

## Streaming & Conversation Memory

- **SSE** via `POST /api/chat/stream` — token-by-token streaming
- **WebSocket** via `WS /api/ws/chat` — bidirectional with JSON messages
- **Conversation Memory** — last 4 exchanges per connection for follow-up context

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Frontend** | React 19, Vite 5 | Fast dev, mature ecosystem |
| **Language** | Plain JavaScript (JSX) | Simple SPA, no type overhead |
| **Backend** | Python 3, FastAPI | Async, auto-docs, Pydantic |
| **LLM** | Cerebras (`zai-glm-4.7`) | Free tier, fast inference |
| **Embeddings** | sentence-transformers (`all-MiniLM-L6-v2`) | Semantic search, runs locally |
| **Database** | PostgreSQL + JSON file fallback | Caching with graceful degradation |
| **API** | Git Clone | Complete file access, no limits |
| **Storage** | localStorage (frontend) | Recent repos persistence |

---

## Repository Layout

```
codelens/
├── backend/
│   ├── api.py                      # FastAPI + SSE + WebSocket
│   ├── main.py                     # Orchestrator (4-layer RAG)
│   ├── hybrid_analyzer.py          # LLM call + section parsing + source citations
│   ├── hybrid_prompts.py           # Anti-hallucination prompts
│   ├── repo_cloner.py              # Shallow git clone + local reads + commit hash
│   ├── repo_fetcher.py             # Clone orchestrator + AST parsing
│   ├── db_utils.py                 # PostgreSQL + JSON file fallback
│   ├── analysis/
│   │   ├── pipeline.py             # Static analysis orchestrator
│   │   ├── ast_parser.py           # Regex AST parser (6 languages)
│   │   ├── graph_builder.py        # Dependency graph builder
│   │   ├── file_cache.py           # SHA-256 file cache
│   │   ├── chunker.py              # AST-aware code chunking
│   │   ├── code_index.py           # Embeddings semantic search
│   │   └── query_builder.py        # 4-layer context builder
│   └── github_client/
│       └── github.py               # GitHub API (validate, issues)
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── api/client.js           # API client + localStorage persistence
│   │   ├── pages/
│   │   │   ├── HomePage.jsx        # Landing page + recent repos + popular repos
│   │   │   └── WikiPage.jsx        # Analysis viewer + file tree + relevant files
│   │   └── components/
│   │       ├── Header.jsx
│   │       ├── WikiTreeView.jsx    # Section navigation sidebar
│   │       ├── FileTreeView.jsx    # Collapsible file tree viewer
│   │       ├── MarkdownRenderer.jsx
│   │       └── ChatPanel.jsx       # Streaming chat with memory
│   ├── package.json
│   └── vite.config.js
│
└── architecture.html               # Architecture doc + interview Q&As
```

---

## Quick Start

### Backend

```bash
cd codelens/backend

# Create virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure .env
# CEREBRAS_API_KEY=your_cerebras_api_key

# Start server (use python -m, NOT bare uvicorn)
python -m uvicorn api:app --reload --port 8000
# API docs at http://localhost:8000/docs
```

### Frontend

```bash
cd codelens/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# Opens at http://localhost:5173
```

### Environment Variables

```bash
# Required
CEREBRAS_API_KEY=your_cerebras_api_key

# Optional
GITHUB_TOKEN=ghp_your_github_token    # increases rate limit
DATABASE_URL=postgresql://...         # enables PostgreSQL caching
```

---

## API Reference

### POST /api/analysis

Generate or retrieve cached repository analysis.

```json
// Request
{ "repo_url": "https://github.com/pallets/flask", "force_refresh": false }

// Response
{
  "repo_url": "...",
  "purpose_scope": "...",
  "repo_layout": "...",
  "source_layer": "...",
  "tech_stack": "...",
  "architecture_text": "...",
  "_relevant_files": [...],
  "_relevant_files_purpose_scope": [...],
  "_relevant_files_repo_layout": [],
  "_relevant_files_source_layer": [...],
  "_relevant_files_tech_stack": [...],
  "_relevant_files_architecture_text": [...],
  "_commit_hash": "abc12345",
  "_file_tree": { "backend/": {...}, "frontend/": {...} }
}
```

### POST /api/chat

Ask a question (supports streaming via `history`).

```json
// Request
{ "repo_url": "...", "question": "How does routing work?", "history": [] }

// Response
{ "answer": "Flask's routing uses @app.route() decorator..." }
```

### POST /api/chat/stream

SSE streaming endpoint. Returns `text/event-stream`.

### WS /api/ws/chat

WebSocket with conversation memory (last 4 exchanges).

### GET /api/analysis/{repo_url}

Retrieve cached analysis (read-only, 404 if not cached).

### GET /api/issues/{repo_url}

Fetch GitHub issues for a repository.

---

## Key Design Decisions

### Why Git Clone Instead of GitHub API?

| Aspect | Git Clone (Current) | GitHub API (Previous) |
|---|---|---|
| File access | All files, no limits | Depth 3, 15 files/dir |
| Content | Full, no truncation | Truncated to 2000 chars |
| Rate limits | None (local reads) | 5000 req/hr |
| Speed | ~3-5 seconds | ~5-8 seconds (serial) |

### Why 4-Layer RAG?

- **Token savings:** Summary queries use ~3K tokens (94% savings), specific queries use ~8K tokens (84% savings)
- **Full awareness:** Layers 1-2 always sent, giving complete codebase structure
- **Relevant details:** Layers 3-4 retrieved via embeddings, not dump-everything

### Why Topic-Based File Assignment?

Instead of scanning LLM output for file paths (unreliable), files are assigned to sections by topic:
- Config files → Tech Stack
- Source files → Source Layer
- Entry points → Architecture
This is predictable and doesn't depend on the LLM mentioning specific paths.

### Why PostgreSQL + JSON Fallback?

PostgreSQL provides robust caching when available. When it's not (local dev, no DB setup), the JSON file cache at `~/.codelens/cache/` provides the same persistence with zero configuration.

### Why python -m uvicorn?

The `uvicorn.exe` shim can point to the wrong Python environment. Using `python -m uvicorn` ensures the correct venv Python is used.

---

## Interview Prep

See `architecture.html` for interview questions and answers covering:
- System design & architecture
- Backend design
- LLM integration
- Frontend architecture
- API design
- Key technical decisions
