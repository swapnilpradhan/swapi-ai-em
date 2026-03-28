#!/usr/bin/env python3
"""Quick test script to debug topic breakdown agent"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

load_dotenv()

async def test_topic_breakdown():
    """Test the topic breakdown agent directly"""
    from backend.app.agents.topic_breakdown_agent import TopicBreakdownAgent
    
    print("Initializing Topic Breakdown Agent...")
    agent = TopicBreakdownAgent()
    
    print("Processing task...")
    task = {"topic": "Deep Learning"}
    
    try:
        result = await agent.process_task(task)
        print("\n✅ SUCCESS!")
        print(f"Status: {result.get('status')}")
        print(f"Context ID: {result.get('context_id')}")
        print(f"Subtopics: {len(result.get('subtopics', []))}")
        return result
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}")
        print(f"Message: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_topic_breakdown())
    sys.exit(0 if result else 1)
