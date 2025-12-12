#!/usr/bin/env python3
"""
Backfill Task Types Script

Re-classifies existing tasks using AI based on their spoken context (provenance quote).
This script analyzes the extraction_context of each task to determine the appropriate
task_type (decision, action_item, follow_up, research).
"""

import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Task
from services.openai_client_manager import get_openai_client


def classify_task_type_simple(task):
    """Simple keyword-based classification for tasks without AI."""
    text = ""
    
    if task.extraction_context:
        if isinstance(task.extraction_context, dict):
            text = task.extraction_context.get("quote", "") or ""
            text += " " + (task.extraction_context.get("spoken_quote", "") or "")
        elif isinstance(task.extraction_context, str):
            text = task.extraction_context
    
    text += " " + (task.title or "") + " " + (task.description or "")
    text_lower = text.lower()
    
    decision_keywords = [
        "decided", "agreed", "confirmed", "approved", "finalized",
        "conclusion", "let's go with", "we'll use", "the plan is",
        "we're going to", "settled on"
    ]
    
    followup_keywords = [
        "follow up", "circle back", "revisit", "next meeting",
        "touch base", "check in", "follow-up", "get back to", "reconnect"
    ]
    
    research_keywords = [
        "research", "investigate", "find out", "look into",
        "explore", "analyze", "study", "discover", "learn about",
        "figure out", "understand", "evaluate", "assess"
    ]
    
    if any(kw in text_lower for kw in decision_keywords):
        return "decision"
    elif any(kw in text_lower for kw in followup_keywords):
        return "follow_up"
    elif any(kw in text_lower for kw in research_keywords):
        return "research"
    else:
        return "action_item"


async def classify_tasks_with_ai(tasks, client):
    """Use AI to classify a batch of tasks."""
    from services.ai_model_manager import AIModelManager
    
    task_descriptions = []
    for i, task in enumerate(tasks):
        quote = ""
        if task.extraction_context:
            if isinstance(task.extraction_context, dict):
                quote = task.extraction_context.get("quote", "") or task.extraction_context.get("spoken_quote", "")
        
        task_descriptions.append({
            "id": i,
            "title": task.title,
            "description": task.description or "",
            "quote": quote
        })
    
    system_prompt = """You are an AI assistant that classifies meeting tasks by type.

For each task, classify it as one of:
- "decision": Final conclusions or choices made ("We decided to...", "Let's go with...")
- "action_item": Specific tasks assigned to someone ("You need to...", "Can you...")
- "follow_up": Items to revisit or continue later ("Let's circle back...", "We'll revisit...")
- "research": Questions to investigate ("We need to find out...", "Look into...")

Return a JSON array with the id and task_type for each task:
{"classifications": [{"id": 0, "task_type": "action_item"}, {"id": 1, "task_type": "decision"}]}"""

    user_prompt = f"""Classify these tasks:

{json.dumps(task_descriptions, indent=2)}"""

    try:
        def make_api_call(model: str):
            return client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )
        
        result_obj = AIModelManager.call_with_fallback(
            make_api_call,
            operation_name="task type classification"
        )
        
        if not result_obj.success:
            return None
        
        content = result_obj.response.choices[0].message.content
        result = json.loads(content)
        return result.get("classifications", [])
        
    except Exception as e:
        print(f"AI classification failed: {e}")
        return None


def backfill_task_types(use_ai=False, dry_run=True, batch_size=10):
    """Backfill task_type for all tasks that have default 'action_item' type."""
    with app.app_context():
        tasks = db.session.query(Task).filter(
            Task.deleted_at.is_(None)
        ).all()
        
        print(f"Found {len(tasks)} total tasks to analyze")
        
        client = get_openai_client() if use_ai else None
        
        updated = 0
        type_counts = {"decision": 0, "action_item": 0, "follow_up": 0, "research": 0}
        
        if use_ai and client:
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i + batch_size]
                print(f"Processing batch {i // batch_size + 1}...")
                
                classifications = asyncio.run(classify_tasks_with_ai(batch, client))
                
                if classifications:
                    for cls in classifications:
                        task = batch[cls["id"]]
                        new_type = cls.get("task_type", "action_item")
                        if new_type in type_counts:
                            if task.task_type != new_type:
                                if not dry_run:
                                    task.task_type = new_type
                                updated += 1
                            type_counts[new_type] += 1
                else:
                    for task in batch:
                        new_type = classify_task_type_simple(task)
                        if task.task_type != new_type:
                            if not dry_run:
                                task.task_type = new_type
                            updated += 1
                        type_counts[new_type] += 1
        else:
            for task in tasks:
                new_type = classify_task_type_simple(task)
                if task.task_type != new_type:
                    if not dry_run:
                        task.task_type = new_type
                    updated += 1
                type_counts[new_type] += 1
        
        if not dry_run:
            db.session.commit()
        
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Results:")
        print(f"  Tasks that would change: {updated}")
        print(f"  Final type distribution:")
        for task_type, count in type_counts.items():
            print(f"    {task_type}: {count}")
        
        return updated, type_counts


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill task types for existing tasks")
    parser.add_argument("--ai", action="store_true", help="Use AI for classification (more accurate)")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry run)")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for AI classification")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Task Type Backfill Script")
    print("=" * 60)
    print(f"Mode: {'AI-powered' if args.ai else 'Keyword-based'}")
    print(f"Dry run: {not args.apply}")
    print()
    
    backfill_task_types(
        use_ai=args.ai,
        dry_run=not args.apply,
        batch_size=args.batch_size
    )
