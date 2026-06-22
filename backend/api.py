"""FastAPI Endpoints - API layer for CodeLens backend."""

import asyncio
import os
import sys
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import generate_repo_analysis, chat_with_repo
from db_utils import get_repo_analysis
from github_client.github import GitHubAccessError, GitHubClient

app = FastAPI(
    title="CodeLens API",
    description="Hybrid Analysis Engine for GitHub Repository Analysis",
    version="2.0.0",
)

# CORS - allow all origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class AnalysisRequest(BaseModel):
    repo_url: str
    force_refresh: bool = False


class ChatRequest(BaseModel):
    repo_url: str
    question: str


class AnalysisResponse(BaseModel):
    repo_url: str
    purpose_scope: str
    repo_layout: str
    source_layer: str
    tech_stack: str
    architecture_text: str


class ChatResponse(BaseModel):
    answer: str


# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "codelens-api", "version": "2.0.0"}


# Analysis endpoint
@app.post("/api/analysis", response_model=AnalysisResponse)
async def analyze_repository(request: AnalysisRequest):
    """Generate or retrieve repository analysis."""
    try:
        result = await generate_repo_analysis(
            request.repo_url, force_refresh=request.force_refresh
        )
        return AnalysisResponse(
            repo_url=request.repo_url,
            purpose_scope=result.get("purpose_scope", ""),
            repo_layout=result.get("repo_layout", ""),
            source_layer=result.get("source_layer", ""),
            tech_stack=result.get("tech_stack", ""),
            architecture_text=result.get("architecture_text", ""),
        )
    except GitHubAccessError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# Get cached analysis
@app.get("/api/analysis/{repo_url:path}")
async def get_analysis(repo_url: str):
    """Retrieve cached analysis for a repository."""
    result = get_repo_analysis(repo_url)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


# Chat endpoint
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat about a repository."""
    try:
        answer = await chat_with_repo(request.repo_url, request.question)
        return ChatResponse(answer=answer)
    except GitHubAccessError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


# Issues endpoint
@app.get("/api/issues/{repo_url:path}")
async def get_issues(repo_url: str, state: str = "open", limit: int = 20):
    """Fetch issues from a GitHub repository."""
    try:
        github = GitHubClient()
        issues = await github.get_issues(repo_url, state=state, limit=limit)
        return {"repo_url": repo_url, "state": state, "issues": issues, "count": len(issues)}
    except GitHubAccessError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch issues: {str(e)}")


# WebSocket for streaming chat
@app.websocket("/api/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for streaming chat."""
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            repo_url = data.get("repo_url")
            question = data.get("question")

            if not repo_url or not question:
                await websocket.send_json({"error": "Missing repo_url or question"})
                continue

            await websocket.send_json({"status": "processing"})

            try:
                answer = await chat_with_repo(repo_url, question)
                await websocket.send_json({"answer": answer})
            except GitHubAccessError as e:
                await websocket.send_json({"error": str(e)})
            except Exception as e:
                await websocket.send_json({"error": str(e)})

    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
