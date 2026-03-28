#!/usr/bin/env python3
"""
Direct pipeline execution — bypasses A2A messaging.
Usage: python generate_track.py "Chunking and Embedding"
"""
import asyncio
import sys
import os
import json
import time

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


async def main(topic: str):
    # Lazy imports after path/env setup
    from app.agents.topic_breakdown_agent import TopicBreakdownAgent
    from app.agents.research_agent import ResearchAgent
    from app.agents.html_generation_agent import HTMLGenerationAgent

    print(f"\n{'='*60}")
    print(f"  Generating track: {topic}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # ── Step 1: Topic Breakdown ──
    print("[1/3] Topic Breakdown Agent — analyzing topic...")
    tba = TopicBreakdownAgent()
    tb_result = await tba.process_task({"topic": topic})
    context_id = tb_result["context_id"]
    subtopics = tb_result.get("subtopics", [])
    print(f"  ✓ Created {len(subtopics)} subtopics  (context: {context_id})")
    for st in subtopics:
        print(f"    • {st.get('title', st.get('name', '?'))}")

    # ── Step 2: Research Agent ──
    print(f"\n[2/3] Research Agent — synthesising content...")
    ra = ResearchAgent()
    ra_result = await ra.process_task({"context_id": context_id})
    content_structure = ra_result["content_structure"]
    style_guide = ra_result["style_guide"]
    sections = content_structure.get("sections", [])
    print(f"  ✓ Built {len(sections)} sections + style guide")

    # ── Step 3: HTML Generation Agent ──
    print(f"\n[3/3] HTML Generation Agent — rendering HTML...")
    hga = HTMLGenerationAgent()
    hga_result = await hga.process_task({
        "topic": topic,
        "content_structure": content_structure,
        "style_guide": style_guide,
    })
    file_path = hga_result["file_path"]
    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"  ✅ Done in {elapsed:.1f}s")
    print(f"  📄 Output: {file_path}")
    print(f"{'='*60}\n")

    return file_path


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Chunking and Embedding"
    asyncio.run(main(topic))
