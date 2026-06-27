"""Celery Worker - Background job processing for repository analysis."""

import os
import sys
from celery import Celery

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Celery with Redis broker
celery_app = Celery(
    "codelens",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # 4 minutes soft limit
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
)


@celery_app.task(bind=True, name="tasks.analyze_repository")
def analyze_repository_task(self, repo_url: str, force_refresh: bool = False):
    """
    Background task for repository analysis.
    
    This runs in a separate worker process, freeing the API to handle
    other requests while analysis runs in the background.
    
    Interview point: "We use Celery for background job processing,
    allowing the API to remain responsive while heavy analysis runs."
    """
    import asyncio
    from main import generate_repo_analysis
    
    print(f"[Worker] Starting analysis for {repo_url}")
    print(f"[Worker] Task ID: {self.request.id}")
    
    try:
        # Update task state
        self.update_state(state="PROGRESS", meta={"status": "cloning"})
        
        # Run the async analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                generate_repo_analysis(repo_url, force_refresh)
            )
        finally:
            loop.close()
        
        print(f"[Worker] Analysis complete for {repo_url}")
        return {
            "status": "completed",
            "repo_url": repo_url,
            "sections": result,
        }
        
    except Exception as e:
        print(f"[Worker] Analysis failed for {repo_url}: {e}")
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@celery_app.task(bind=True, name="tasks.chat_with_repo")
def chat_task(self, repo_url: str, question: str, history: list = None):
    """
    Background task for chat (if needed for long-running queries).
    
    Usually chat is synchronous, but this allows async processing
    for complex queries that might take longer.
    """
    import asyncio
    from main import chat_with_repo
    
    print(f"[Worker] Processing chat for {repo_url}")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                chat_with_repo(repo_url, question, history)
            )
        finally:
            loop.close()
        
        return {
            "status": "completed",
            "answer": result,
        }
        
    except Exception as e:
        print(f"[Worker] Chat failed: {e}")
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


# Auto-discover tasks
celery_app.autodiscover_tasks(["backend"])
