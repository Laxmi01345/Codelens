# CodeLens

> Paste any GitHub URL. Get instant, AI-generated architecture docs — purpose, layout, tech stack, Mermaid diagrams, and interactive chat.

---

## Table of Contents

- [Overview](#overview)
- [Internal Flow](#internal-flow)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Repository Layout](#repository-layout)
- [Quick Start](#quickstart)
- [API Reference](#api-reference)
- [Key Design Decisions](#key-design-decisions)

---

## Overview

CodeLens is an AI-powered codebase analysis tool. It takes a GitHub repository URL and produces a comprehensive architecture document — similar to what a senior engineer would write after spending hours reading the code.

### What the User Sees

1. **Landing page** — dark theme, single URL input field
2. **Loading state** — "Analyzing repository..." with progress indication
3. **Wiki page** — full-screen architecture document with:
   - Collapsible folder tree (sidebar)
   - 5 analysis sections rendered as markdown
   - Zoomable Mermaid architecture diagram
   - Interactive chat panel at the bottom
4. **Chat** — ask follow-up questions about the codebase

### What the System Generates

| Section | Content | Format |
|---|---|---|
| Purpose & Scope | What the repo does, its goals | Plain text summary |
| Repository Layout | Directory structure + architectural pattern | Text tree (`├──` / `└──`) + pattern label |
| Tech Stack | Languages, frameworks, tools | Markdown table with evidence |
| Architecture | System design + component relationships | Mermaid diagram + description |
| RPC Protocol | API endpoints, communication protocols | Analysis of REST/GraphQL/gRPC usage |

---

## Internal Flow

This is exactly what happens from the moment a user pastes a URL to seeing the result.

### Step 1: User Enters URL

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
    ├──► Check PostgreSQL cache
    │    SELECT * FROM repo_analysis WHERE repo_url = '...'
    │
    ├──► Cache HIT? → Return cached result immediately (~50ms)
    │
    └──► Cache MISS? → Start full analysis pipeline (~15 sec)
```

### Step 3: Fetch Repository Data

```
repo_fetcher.py
    │
    ├──► validate_repo()                    ── GitHub API: GET /repos/{owner}/{repo}
    │    Returns: name, description, language, topics, default_branch
    │
    ├──► get_file_tree(max_depth=3)         ── GitHub API: GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1
    │    Returns: full directory structure as nested dict
    │
    ├──► fetch_key_files(file_tree)         ── GitHub API: GET /repos/{owner}/{repo}/contents/{path}
    │    Reads: README.md, package.json, requirements.txt, pyproject.toml,
    │           Cargo.toml, go.mod, pom.xml, Dockerfile, etc. (22 common names)
    │    Returns: dict of {filename: content}
    │
    └──► fetch_source_files(file_tree)      ── GitHub API: multiple GET calls
         Scans: src/, lib/, app/, internal/, pkg/ directories recursively
         Reads: .py, .js, .ts, .go, .rs, .java, .rb, .php files
         Truncates: each file to ~3000 chars
         Returns: dict of {filepath: content}

All of these run in parallel using asyncio.gather()
Total: ~5-8 seconds depending on repo size
```

### Step 4: Build LLM Prompt

```
hybrid_prompts.py
    │
    ├──► System prompt (anti-hallucination rules)
    │    "You are CodeLens, an expert software architect..."
    │    "Every statement MUST reference a specific file path..."
    │    "If information is not present, say 'Not found'..."
    │
    └──► User prompt (combined repo context)
         ┌─────────────────────────────────────────┐
         │ Repository: pallets/flask                │
         │ Description: The Python micro framework  │
         │ Language: Python                          │
         │ Topics: [web, python, wsgi]              │
         │                                          │
         │ File Tree:                               │
         │ ├── src/                                 │
         │ │   └── flask/                           │
         │ │       ├── __init__.py                  │
         │ │       ├── app.py                       │
         │ │       └── ...                          │
         │                                          │
         │ Config Files:                            │
         │ --- requirements.txt ---                 │
         │ Flask>=2.0                               │
         │ Werkzeug>=2.0                            │
         │ ...                                      │
         │                                          │
         │ Source Files:                            │
         │ --- src/flask/app.py ---                 │
         │ class Flask(__name__):                   │
         │     def __init__(self, ...):             │
         │         ...                              │
         └─────────────────────────────────────────┘
```

### Step 5: LLM Generates Analysis

```
Cerebras LLM (zai-glm-4.7)
    │
    ├── Receives combined prompt (~10,000-50,000 tokens)
    ├── Generates response (~2,000-4,000 tokens)
    ├── Takes ~10-15 seconds
    └── Returns structured output:

## Section 1: Purpose & Scope
Flask is a lightweight WSGI web application framework...

## Section 2: Repository Layout
```
flask/
├── src/flask/        # Core framework source
├── tests/            # Test suite
...
```
Pattern: modular layout

## Section 3: Source Layer (Tech Stack)
| Category | Technology | Evidence |
|----------|------------|----------|
| Language | Python | pyproject.toml |
| Framework | Flask | src/flask/__init__.py |
...

## Section 4: Architecture
```mermaid
flowchart TD
    A[Client Request] --> B[WSGI Server]
    B --> C[Flask App]
...
```

## Section 5: RPC Protocol
Flask uses WSGI protocol...
```

### Step 6: Parse Sections

```
hybrid_analyzer.py → parse_sections()
    │
    ├── Finds headers: ## Section N: Name, ## Name, # Name
    ├── Splits response by headers
    ├── Extracts content between consecutive headers
    ├── Strips header lines from content (wiki page renders them separately)
    └── Returns dict:
        {
            "purpose_scope": "Flask is a lightweight...",
            "repo_layout": "```\nflask/\n├── src/flask/...",
            "source_layer": "| Category | Technology |...",
            "tech_stack": "| Category | Technology |...",
            "architecture_text": "```mermaid\nflowchart TD\n..."
        }
```

### Step 7: Cache + Return

```
db_utils.py
    │
    ├──► store_repo_analysis()
    │    INSERT INTO repo_analysis (repo_url, purpose_scope, ...)
    │    ON CONFLICT (repo_url) DO UPDATE SET ...
    │
    └──► Return to frontend as JSON

Frontend receives response → stores in analysisCache Map
```

### Step 8: Render Wiki Page

```
WikiPage.jsx
    │
    ├──► WikiTreeView.jsx
    │    Parses repo_layout text tree
    │    Renders collapsible folder structure
    │    Click section → scroll to it
    │
    ├──► MarkdownRenderer.jsx
    │    Converts each section's markdown to HTML
    │    Handles: headers, bold, code blocks, tables, lists, links
    │    Preserves tree characters (├──, └──, │) in code blocks
    │
    ├──► MermaidDiagram.jsx
    │    Extracts ```mermaid blocks from architecture_text
    │    Renders with mermaid.js library
    │    Supports: zoom in/out, Ctrl+Scroll, drag to pan
    │    Click diagram → fullscreen modal with blurred background
    │
    └──► ChatPanel.jsx
         Floating bottom panel
         User types question → POST /api/chat
         Backend builds context from analysis + key files
         Single LLM call → returns answer
         Renders answer as markdown
```

### Chat Flow (Separate from Analysis)

```
User: "How does authentication work?"
    │
    ▼
ChatPanel → POST /api/chat { repo_url, question }
    │
    ▼
main.py → chat_with_repo()
    │
    ├──► Get cached analysis from DB
    │    purpose: "Flask is..."
    │    tech_stack: "| Language | Python |..."
    │    architecture: "```mermaid..."
    │
    ├──► Fetch key files (if not cached)
    │    src/flask/app.py (first 1500 chars)
    │    requirements.txt (full)
    │    ...
    │
    ├──► Build context string
    │    "Purpose: Flask is a...\nTech Stack:...\nArchitecture:...\n--- app.py ---\nclass Flask..."
    │
    ├──► Single LLM call
    │    System: "You are CodeLens, answer based on context..."
    │    User: "Repository: flask\n\nContext: ...\n\nQuestion: How does auth work?"
    │
    └──► Return answer
         "Based on the codebase, Flask uses a session-based..."
```

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
│                           MarkdownRenderer (content)    │
│                           MermaidDiagram (diagrams)     │
│                           ChatPanel (bottom)            │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  FASTAPI BACKEND                         │
│                    (Port 8000)                           │
│                                                         │
│  api.py (endpoints) ──► main.py (orchestrator)          │
│                              │                          │
│                    ┌─────────┼──────────┐               │
│                    ▼         ▼          ▼               │
│            repo_fetcher  hybrid_    db_utils            │
│            (GitHub API)  analyzer   (PostgreSQL)        │
│                          (Cerebras)                     │
└────────┬─────────────────┬──────────────┬──────────────┘
         │                 │              │
         ▼                 ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  GITHUB API  │  │  CEREBRAS    │  │  POSTGRESQL  │
│  (Rest API)  │  │  LLM         │  │  (Optional)  │
│              │  │  zai-glm-4.7 │  │              │
│  - Metadata  │  │              │  │  - Cache     │
│  - File tree │  │  - Analysis  │  │  - History   │
│  - Files     │  │  - Chat      │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

### MCP (Model Context Protocol) Layer

The backend uses MCP-compatible clients to interact with external services:

```
mcp_client/
├── github_mcp.py       ──► Wraps GitHub REST API
│   ├── validate_repo()     GET /repos/{owner}/{repo}
│   ├── get_file_content()  GET /repos/{owner}/{repo}/contents/{path}
│   ├── list_directory()    GET /repos/{owner}/{repo}/contents/{path}
│   ├── get_file_tree()     GET /repos/{owner}/{repo}/git/trees/{branch}
│   └── search_code()       GET /search/code?q=...+repo:...
│
├── tree_sitter_mcp.py  ──► AST parsing (with regex fallback)
│   ├── get_ast()           Parse code → AST JSON
│   ├── extract_symbols()   Find classes, functions, imports
│   ├── analyze_complexity() Line counts, metrics
│   └── find_references()   Symbol usage search
│
├── uml_mcp.py          ──► Diagram generation via Kroki.io
│   ├── generate_diagram()  Render any diagram type
│   ├── generate_mermaid()  Mermaid convenience method
│   └── build_*_diagram()   Programmatic diagram builders
│
└── client.py           ──► MCP client manager
    └── call_tool()         Unified interface for all servers
```

---

## Tech Stack

| Layer | Technology | Why This Choice |
|---|---|---|
| **Frontend** | React 19, Vite 5 | Fast dev server, mature ecosystem |
| **Language** | Plain JavaScript | Simple SPA, no type overhead needed |
| **Routing** | React Router v6 | SPA with nested routes |
| **Styling** | Tailwind CSS 4 + custom CSS | Dark theme, emerald accents |
| **Backend** | Python 3, FastAPI | Async support, auto-docs, Pydantic |
| **LLM** | Cerebras (`zai-glm-4.7`) | Free tier, fast inference |
| **Database** | PostgreSQL (psycopg2) | Optional caching, graceful fallback |
| **External API** | GitHub REST API | Direct file access, no cloning |
| **Diagrams** | Mermaid.js | Zoom/pan/fullscreen, dark theme |
| **Fonts** | Inter + JetBrains Mono | Clean developer aesthetic |
| **HTTP Client** | httpx (async) | Non-blocking GitHub API calls |

---

## Repository Layout

```
codelens/
├── backend/                        # Python analysis engine
│   ├── api.py                      # FastAPI app + endpoints
│   ├── main.py                     # Orchestrator (generate_repo_analysis, chat_with_repo)
│   ├── hybrid_analyzer.py          # Builds LLM prompt, calls Cerebras, parses sections
│   ├── hybrid_prompts.py           # System prompts with anti-hallucination rules
│   ├── repo_fetcher.py             # Parallel GitHub API fetching
│   ├── llm_utils.py                # Cerebras client wrapper
│   ├── db_utils.py                 # PostgreSQL operations (optional)
│   ├── agent/                      # Old agentic loop (kept for reference)
│   │   ├── agent_loop.py           #   Tool-use loop (8+ LLM calls)
│   │   ├── tools.py                #   Tool definitions
│   │   └── prompts.py              #   System prompts
│   ├── mcp_client/                 # MCP-compatible API wrappers
│   │   ├── github_mcp.py           #   GitHub REST API
│   │   ├── tree_sitter_mcp.py      #   AST parsing + regex fallback
│   │   ├── uml_mcp.py             #   Kroki diagram generation
│   │   └── client.py              #   MCP client manager
│   ├── .env                        # API keys (gitignored)
│   ├── requirements.txt
│   └── .venv/
│
├── frontend/                       # React 19 + Vite 5
│   ├── index.html                  # Entry HTML + Google Fonts
│   ├── vite.config.js
│   ├── package.json
│   ├── public/
│   │   └── favicon.svg             # Green book icon
│   └── src/
│       ├── main.jsx                # App entry (StrictMode removed)
│       ├── App.jsx                 # Router setup
│       ├── index.css               # Global dark theme styles
│       ├── api/
│       │   └── client.js           # API calls + in-memory analysisCache
│       ├── pages/
│       │   ├── HomePage.jsx        # Landing page (URL input)
│       │   └── WikiPage.jsx        # Full-screen wiki layout
│       └── components/
│           ├── Header.jsx          # Only shown on HomePage
│           ├── WikiTreeView.jsx    # Folder tree + section navigation
│           ├── MarkdownRenderer.jsx # Markdown → HTML
│           ├── MermaidDiagram.jsx  # Zoom/pan/fullscreen diagrams
│           └── ChatPanel.jsx       # Bottom floating chat
│
└── architecture.html               # Full architecture doc + 45 interview Q&As
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
cat > .env << EOF
CEREBRAS_API_KEY=your_cerebras_api_key
GITHUB_TOKEN=ghp_your_github_token
DATABASE_URL=postgresql://user:pass@localhost:5432/repo_analysis_db
EOF

# Start server
uvicorn api:app --reload --port 8000
# API docs available at http://localhost:8000/docs
```

### Frontend

```bash
cd codelens/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# Opens at http://localhost:5173

# Build for production
npm run build
```

### Environment Variables

```bash
# Required
CEREBRAS_API_KEY=your_cerebras_api_key

# Optional (increases GitHub rate limit from 60 to 5000 req/hr)
GITHUB_TOKEN=ghp_your_github_token

# Optional (enables analysis caching)
DATABASE_URL=postgresql://user:pass@localhost:5432/repo_analysis_db
```

---

## API Reference

### POST /api/analysis

Generate or retrieve cached repository analysis.

```json
// Request
{
  "repo_url": "https://github.com/pallets/flask",
  "force_refresh": false
}

// Response
{
  "repo_url": "https://github.com/pallets/flask",
  "purpose_scope": "Flask is a lightweight WSGI web application framework...",
  "repo_layout": "```\nflask/\n├── src/flask/\n│   ├── __init__.py\n...",
  "source_layer": "| Category | Technology | Evidence |\n|----------|------------|----------|...",
  "tech_stack": "| Category | Technology | Evidence |\n|----------|------------|----------|...",
  "architecture_text": "```mermaid\nflowchart TD\n    A[Client] --> B[WSGI]...\n```"
}
```

### POST /api/chat

Ask a question about a repository.

```json
// Request
{
  "repo_url": "https://github.com/pallets/flask",
  "question": "How does the routing system work?"
}

// Response
{
  "answer": "Flask's routing system works by using the @app.route() decorator..."
}
```

### GET /api/analysis/{repo_url}

Retrieve cached analysis (read-only, returns 404 if not cached).

---

## Key Design Decisions

### Why MCP Instead of Traditional RAG?

Traditional RAG chunks text → embeds → stores in vector DB → retrieves similar chunks. This project uses MCP-compatible clients for **direct, precise file retrieval** instead of semantic search.

| Aspect | MCP Approach | Traditional RAG |
|---|---|---|
| Retrieval | Exact file paths | Semantic similarity |
| Code structure | Preserved (whole files) | Broken (chunks) |
| Cost | Free (GitHub API) | Embedding API costs |
| Complexity | Simple (API calls) | Complex (vector DB) |
| Best for | Single repo analysis | Large doc collections |

### Why PostgreSQL is Optional

The system works without a database. If PostgreSQL is unavailable:
- Analysis regenerates on every request (~15 sec)
- Frontend `analysisCache` Map prevents duplicates within a session
- No configuration required for local development

### Why Recursive Source File Fetching

Initial version only read top-level files. Repos like Flask have source code in `src/flask/` subdirectories. `_fetch_code_files_recursive()` scans all source directories up to 3 levels deep.

### Why No README Fallback

Many repos have no README. The system falls back through:
GitHub description → topics → package.json → pyproject.toml → source docstrings

### Why StrictMode Was Removed

React StrictMode double-invokes effects in development, causing duplicate API calls. Removed because the performance cost of duplicate LLM calls outweighs StrictMode's benefits.

### Anti-Hallucination Rules

The LLM is given strict constraints:
1. Every statement must cite a specific file path
2. Use ONLY provided data — no guessing
3. Say "Not found in provided files" for missing info
4. Don't invent file names, function names, or code
5. Tech stack only from config files (package.json, requirements.txt, etc.)

---

## Interview Prep

See `architecture.html` for 45 interview questions and answers covering:
- System design & architecture
- Backend design
- LLM integration
- Frontend architecture
- API design
- Security
- Performance & optimization
- Testing & quality
- Key technical decisions
- Deployment & operations
