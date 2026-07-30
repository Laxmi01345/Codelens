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
    history: list[dict] = None  # Conversation history for memory


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
@app.post("/api/analysis")
async def analyze_repository(request: AnalysisRequest):
    """Generate or retrieve repository analysis."""
    try:
        result = await generate_repo_analysis(
            request.repo_url, force_refresh=request.force_refresh
        )
        # Return full result including _relevant_files and _commit_hash
        return {
            "repo_url": request.repo_url,
            "purpose_scope": result.get("purpose_scope", ""),
            "repo_layout": result.get("repo_layout", ""),
            "source_layer": result.get("source_layer", ""),
            "tech_stack": result.get("tech_stack", ""),
            "architecture_text": result.get("architecture_text", ""),
            "_relevant_files": result.get("_relevant_files", []),
            "_commit_hash": result.get("_commit_hash", ""),
        }
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


# Chat endpoint (non-streaming)
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat about a repository."""
    try:
        answer = await chat_with_repo(
            request.repo_url, 
            request.question,
            history=request.history,
        )
        return ChatResponse(answer=answer)
    except GitHubAccessError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


# Chat endpoint with streaming (SSE)
@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response using Server-Sent Events."""
    from fastapi.responses import StreamingResponse
    
    async def event_generator():
        try:
            response_generator = await chat_with_repo(
                request.repo_url,
                request.question,
                history=request.history,
                stream=True,
            )
            for chunk in response_generator:
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


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
    """WebSocket endpoint for streaming chat with conversation memory."""
    await websocket.accept()
    
    # Store conversation history per connection
    conversation_history = []
    max_history = 4  # Keep last 4 messages for memory

    try:
        while True:
            data = await websocket.receive_json()
            repo_url = data.get("repo_url")
            question = data.get("question")
            use_streaming = data.get("stream", True)  # Default to streaming

            if not repo_url or not question:
                await websocket.send_json({"error": "Missing repo_url or question"})
                continue

            await websocket.send_json({"status": "processing"})

            try:
                if use_streaming:
                    # Streaming mode - send chunks as they arrive
                    await websocket.send_json({"type": "stream_start"})
                    
                    response_generator = await chat_with_repo(
                        repo_url, question,
                        history=conversation_history,
                        stream=True,
                    )
                    
                    full_response = ""
                    for chunk in response_generator:
                        full_response += chunk
                        await websocket.send_json({"type": "chunk", "content": chunk})
                    
                    # Add to conversation history
                    conversation_history.append({"role": "user", "content": question})
                    conversation_history.append({"role": "assistant", "content": full_response})
                    
                    # Trim history to keep only last N messages
                    if len(conversation_history) > max_history * 2:
                        conversation_history = conversation_history[-(max_history * 2):]
                    
                    await websocket.send_json({"type": "stream_end", "answer": full_response})
                else:
                    # Non-streaming mode
                    answer = await chat_with_repo(
                        repo_url, question,
                        history=conversation_history,
                    )
                    
                    # Add to conversation history
                    conversation_history.append({"role": "user", "content": question})
                    conversation_history.append({"role": "assistant", "content": answer})
                    
                    # Trim history
                    if len(conversation_history) > max_history * 2:
                        conversation_history = conversation_history[-(max_history * 2):]
                    
                    await websocket.send_json({"type": "answer", "answer": answer})
                    
            except GitHubAccessError as e:
                await websocket.send_json({"type": "error", "error": str(e)})
            except Exception as e:
                await websocket.send_json({"type": "error", "error": str(e)})

    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
