"""
HTML Generation Agent (Agent 3)
Creates Head First/Byte Byte Go style HTML content from research plans
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json
from pathlib import Path

from app.agents.base_agent import BaseAgent, AgentMessage
from app.core.mcp_protocol import mcp_registry, create_html_structure_context, ContextType
from app.core.a2a_communication import CommunicationManager, MessageType, MessagePriority
from app.core.observability import observability_service, TracingContext


class HTMLGenerationAgent(BaseAgent):
    """Agent responsible for generating Head First/Byte Byte Go style HTML content"""
    
    def __init__(self):
        super().__init__("html_generation_agent", "HTML Generation Specialist")
        self.communication = CommunicationManager(self.agent_id)
        self.capabilities = ["html_generation", "content_styling", "interactive_elements", "educational_design"]
        
        # Register message handlers
        self.communication.register_handler(MessageType.REQUEST, self._handle_request)
        self.communication.register_handler(MessageType.NOTIFICATION, self._handle_notification)
        
        # OpenAI client for LLM operations
        import openai
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Register with observability
        observability_service.register_agent(self.agent_id, "html_generation")
        
        # Subscribe to relevant topics
        self.communication.subscribe_to_topic("html_generation")
        self.communication.subscribe_to_topic("context_updates")
        
        # Output directory for generated HTML
        self.output_dir = Path("./generated_content")
        self.output_dir.mkdir(exist_ok=True)
        
        self.logger.info("HTML Generation Agent initialized")
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process HTML generation task"""
        with TracingContext("html_generation", self.agent_id, task_type="html_creation") as span:
            try:
                # Check if this is a continuation from research
                context_id = task.get("context_id")
                if context_id:
                    return await self._process_context_based_generation(context_id)
                
                # Otherwise, process direct generation request
                content_structure = task.get("content_structure", {})
                style_guide = task.get("style_guide", {})
                topic = task.get("topic", "")
                
                if not topic or not content_structure:
                    raise ValueError("Topic and content structure are required")
                
                self.logger.info(f"Generating HTML for: {topic}")
                
                # Step 1: Generate HTML content
                html_content = await self._generate_html_content(topic, content_structure, style_guide)
                
                # Step 2: Save HTML file
                file_path = await self._save_html_file(topic, html_content)
                
                # Step 3: Create MCP context for the generated content
                context_id = f"html_content_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                context = create_html_structure_context(
                    context_id=context_id,
                    agent_id=self.agent_id,
                    html_structure=content_structure,
                    style_guide=style_guide
                )
                
                # Update context with generation results
                context.content.update({
                    "generated_html": html_content,
                    "file_path": str(file_path),
                    "generated_at": datetime.now(timezone.utc).isoformat()
                })
                
                # Register context
                mcp_registry.register_context(context)
                
                result = {
                    "status": "success",
                    "topic": topic,
                    "context_id": context_id,
                    "file_path": str(file_path),
                    "content_structure": content_structure,
                    "style_guide": style_guide,
                    "html_preview": html_content[:500] + "..." if len(html_content) > 500 else html_content,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                self.logger.info(f"Successfully generated HTML for: {topic}")
                return result
                
            except Exception as e:
                self.logger.error(f"Error generating HTML: {str(e)}")
                raise
    
    async def _process_context_based_generation(self, context_id: str) -> Dict[str, Any]:
        """Process HTML generation based on existing context from research"""
        with TracingContext("context_based_generation", self.agent_id) as span:
            span.set_attribute("context_id", context_id)
            
            # Get the context from MCP registry
            context = mcp_registry.get_context(context_id, self.agent_id)
            if not context:
                raise ValueError(f"Context {context_id} not found")
            
            research_plan = context.content
            content_structure = research_plan.get("research_plan", {})
            style_guide = research_plan.get("style_guide", {})
            sources = research_plan.get("sources", [])
            
            topic = content_structure.get("title", "Generated Content")
            
            self.logger.info(f"Processing context-based HTML generation for: {topic}")
            
            # Generate HTML content
            html_content = await self._generate_html_content(topic, content_structure, style_guide)
            
            # Save HTML file
            file_path = await self._save_html_file(topic, html_content)
            
            # Update the original context with generation results
            context.content.update({
                "generated_html": html_content,
                "file_path": str(file_path),
                "generated_at": datetime.now(timezone.utc).isoformat()
            })
            
            result = {
                "status": "success",
                "topic": topic,
                "context_id": context_id,
                "file_path": str(file_path),
                "content_structure": content_structure,
                "style_guide": style_guide,
                "sources": sources,
                "html_preview": html_content[:500] + "..." if len(html_content) > 500 else html_content,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Broadcast completion
            await self.communication.broadcast(
                MessageType.NOTIFICATION,
                content={
                    "type": "html_generation_completed",
                    "context_id": context_id,
                    "topic": topic,
                    "file_path": str(file_path),
                    "status": "success"
                }
            )
            
            return result
    
    async def _generate_html_content(self, topic: str, content_structure: Dict[str, Any], 
                                    style_guide: Dict[str, Any]) -> str:
        """Generate complete HTML content"""
        with TracingContext("generate_html_content", self.agent_id) as span:
            sections = content_structure.get("sections", [])
            visual_style = style_guide.get("visual_style", "head_first_byte_byte_go")
            color_scheme = style_guide.get("color_scheme", {})
            
            # Generate HTML structure
            html_parts = []
            
            # HTML header with styles
            html_parts.append(self._generate_html_header(topic, style_guide))
            
            # Body content
            html_parts.append('<body>')
            
            # Generate sidebar navigation (before main content)
            style_guide_with_topic = {**style_guide, "topic": topic}
            html_parts.append(self._generate_sidebar_navigation(sections, style_guide_with_topic))
            
            # Generate hero section (opens <main>)
            html_parts.append(self._generate_hero_section(topic, content_structure, style_guide))
            
            # Generate main content sections with dividers
            for i, section in enumerate(sections):
                section_html = await self._generate_section(section, style_guide, section_index=i)
                html_parts.append(section_html)
                # Add divider between sections (not after the last one)
                if i < len(sections) - 1:
                    html_parts.append('  <div class="divider"></div>\n')
            
            # Generate quiz section (closes </main> and adds <script>)
            html_parts.append(await self._generate_quiz_section(topic, sections, style_guide))
            
            # Close body and html
            html_parts.append('</body>')
            html_parts.append('</html>')
            
            complete_html = "\n".join(html_parts)
            
            span.set_attributes({
                "sections_generated": len(sections),
                "html_length": len(complete_html)
            })
            
            return complete_html
    
    def _generate_html_header(self, topic: str, style_guide: Dict[str, Any]) -> str:
        """Generate HTML header with light-theme track/course styles"""
        header_fonts = "Syne"
        body_font = "DM Sans"
        code_font = "DM Mono"
        
        header = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{topic} — Visual Explainer</title>
<link href="https://fonts.googleapis.com/css2?family={header_fonts}:wght@700;800&family={body_font}:wght@400;500;700&family={code_font}:wght@500&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg:       #FFF9EE;
  --surface:  #FFFFFF;
  --card:     #F8F6F1;
  --border:   #E2DDD5;
  --text:     #1E1F2E;
  --muted:    #6B7280;
  --yellow:   #FFD23F;
  --orange:   #FF7043;
  --teal:     #00C9A7;
  --blue:     #4F8EF7;
  --pink:     #F06292;
  --green:    #66BB6A;
  --purple:   #AB7DF6;
  --red:      #EF5350;
  --font-head: '{header_fonts}', sans-serif;
  --font-body: '{body_font}', sans-serif;
  --font-mono: '{code_font}', monospace;
}}
html {{ scroll-behavior: smooth; }}
body {{ font-family: var(--font-body); background: var(--bg); color: var(--text); line-height: 1.6; }}

/* ── SIDEBAR NAV ── */
.sidebar {{
  position: fixed; left: 0; top: 0; bottom: 0; width: 220px;
  background: var(--surface); border-right: 1px solid var(--border);
  padding: 1.5rem 1rem; z-index: 100; overflow-y: auto;
  display: flex; flex-direction: column; gap: .3rem;
}}
.sidebar-logo {{
  font-family: var(--font-head); font-size: 1rem; font-weight: 800;
  color: var(--text); letter-spacing: 1px; margin-bottom: 1.2rem;
  padding-bottom: 1rem; border-bottom: 1px solid var(--border);
  line-height: 1.3;
}}
.sidebar-logo span {{ color: var(--muted); font-size: .75rem; font-weight: 400; display: block; font-family: var(--font-body); letter-spacing: 0; margin-top: .2rem; }}
.nav-item {{
  display: flex; align-items: center; gap: .6rem;
  padding: .55rem .8rem; border-radius: 8px;
  font-size: .8rem; font-weight: 500; color: var(--muted);
  cursor: pointer; transition: all .2s; text-decoration: none;
  border: 1px solid transparent;
}}
.nav-item:hover, .nav-item.active {{
  background: var(--card); color: var(--text); border-color: var(--border);
}}
.nav-item .nav-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
.nav-item .nav-num {{ font-family: var(--font-mono); font-size: .7rem; color: var(--muted); margin-left: auto; }}

/* ── MAIN ── */
.main {{ margin-left: 220px; padding: 3rem 3rem 6rem; max-width: 1000px; }}

/* ── PAGE HERO ── */
.hero {{
  border: 1px solid var(--border); border-radius: 20px;
  background: linear-gradient(135deg, #FFF5E1 0%, #FFF9EE 100%);
  padding: 3rem; margin-bottom: 3rem; position: relative; overflow: hidden;
}}
.hero::before {{
  content: ''; position: absolute; right: -20px; top: -30px;
  font-family: var(--font-head); font-size: 9rem; font-weight: 800;
  color: rgba(0,0,0,.03); pointer-events: none; line-height: 1;
}}
.track-badge {{
  display: inline-flex; align-items: center; gap: .5rem;
  background: rgba(255,112,67,.1); border: 1px solid rgba(255,112,67,.25);
  color: var(--orange); font-family: var(--font-mono); font-size: .75rem;
  padding: .35rem .9rem; border-radius: 20px; margin-bottom: 1.2rem;
}}
.hero h1 {{
  font-family: var(--font-head); font-size: clamp(2rem, 4vw, 3rem);
  font-weight: 800; line-height: 1.1; margin-bottom: .8rem;
}}
.hero h1 em {{ color: var(--orange); font-style: normal; }}
.hero p {{ color: var(--muted); font-size: 1rem; max-width: 560px; line-height: 1.7; }}
.topic-pills {{ display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1.5rem; }}
.pill {{
  padding: .35rem .9rem; border-radius: 20px; font-size: .75rem; font-weight: 700;
  border: 1px solid; cursor: pointer; transition: all .2s; text-decoration: none;
}}

/* ── SECTION ── */
.section {{ margin-bottom: 4rem; scroll-margin-top: 2rem; }}
.section-header {{
  display: flex; align-items: center; gap: 1rem;
  margin-bottom: 1.5rem; padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}}
.section-num {{
  width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center;
  font-family: var(--font-mono); font-size: .85rem; font-weight: 500; flex-shrink: 0;
}}
.section-header h2 {{ font-family: var(--font-head); font-size: 1.5rem; font-weight: 800; }}
.section-header .em-tag {{
  margin-left: auto; background: rgba(255,112,67,.1); border: 1px solid rgba(255,112,67,.25);
  color: var(--orange); font-size: .7rem; font-weight: 700; padding: .25rem .7rem;
  border-radius: 20px; white-space: nowrap; font-family: var(--font-mono);
}}

/* ── CARDS ── */
.card {{
  background: var(--card); border: 1px solid var(--border); border-radius: 14px;
  padding: 1.4rem 1.5rem; margin-bottom: 1rem;
}}
.card-grid {{ display: grid; gap: 1rem; }}
.card-grid.cols2 {{ grid-template-columns: 1fr 1fr; }}
.card-grid.cols3 {{ grid-template-columns: repeat(3, 1fr); }}
.card h3 {{
  font-family: var(--font-head); font-size: 1rem; font-weight: 700; margin-bottom: .5rem;
  display: flex; align-items: center; gap: .5rem;
}}
.card p, .card li {{ font-size: .88rem; color: var(--muted); line-height: 1.65; }}
.card ul {{ padding-left: 1.2rem; }}
.card li {{ margin-bottom: .25rem; }}

/* ── HIGHLIGHT ── */
.highlight {{
  background: rgba(255,210,63,.12); border: 1px solid rgba(255,210,63,.3);
  border-left: 3px solid var(--yellow); border-radius: 10px;
  padding: 1rem 1.2rem; margin-bottom: 1rem;
}}
.highlight .hl-label {{
  font-family: var(--font-mono); font-size: .7rem; color: var(--orange);
  letter-spacing: 1px; margin-bottom: .4rem; display: block;
}}
.highlight p {{ font-size: .88rem; color: var(--text); line-height: 1.65; }}

/* ── EM INSIGHT ── */
.em-insight {{
  background: rgba(255,112,67,.06); border: 1px solid rgba(255,112,67,.18);
  border-left: 3px solid var(--orange); border-radius: 10px;
  padding: 1rem 1.2rem; margin-top: 1rem;
}}
.em-insight .ei-label {{
  font-family: var(--font-mono); font-size: .7rem; color: var(--orange);
  letter-spacing: 1px; margin-bottom: .4rem; display: flex; align-items: center; gap: .4rem;
}}
.em-insight p, .em-insight li {{ font-size: .85rem; color: var(--text); line-height: 1.65; }}
.em-insight ul {{ padding-left: 1.1rem; margin-top: .3rem; }}

/* ── DIAGRAMS ── */
.diagram {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 1.5rem; margin-bottom: 1rem; overflow-x: auto;
}}
.diagram-title {{
  font-family: var(--font-mono); font-size: .72rem; color: var(--muted);
  letter-spacing: 1.5px; margin-bottom: 1.2rem; text-transform: uppercase;
}}

/* ── CONCEPT CARDS (visual grid) ── */
.concept-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; min-width: 400px; }}
.concept-card {{
  border-radius: 12px; padding: 1.2rem; border: 1px solid var(--border); position: relative;
}}
.concept-card .cc-icon {{ font-size: 2rem; margin-bottom: .6rem; display: block; }}
.concept-card .cc-name {{ font-family: var(--font-head); font-size: 1rem; font-weight: 700; margin-bottom: .4rem; }}
.concept-card .cc-def  {{ font-size: .8rem; color: var(--muted); line-height: 1.5; margin-bottom: .7rem; }}
.concept-card .cc-example {{
  font-family: var(--font-mono); font-size: .72rem;
  background: rgba(0,0,0,.03); padding: .5rem .7rem; border-radius: 6px; line-height: 1.6;
}}

/* ── FLOW DIAGRAM ── */
.flow-row {{ display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; min-width: 400px; }}
.flow-block {{
  border-radius: 10px; padding: .7rem 1rem; text-align: center;
  font-size: .78rem; font-weight: 700; line-height: 1.4; border: 1px solid var(--border);
  min-width: 100px;
}}
.flow-arrow {{ color: var(--muted); font-size: 1.2rem; flex-shrink: 0; }}

/* ── QUIZ SECTION ── */
.quiz-section {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 20px; padding: 2rem; margin-top: 3rem;
}}
.quiz-header {{
  display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem;
  padding-bottom: 1rem; border-bottom: 1px solid var(--border);
}}
.quiz-header h2 {{ font-family: var(--font-head); font-size: 1.5rem; font-weight: 800; }}
.quiz-score {{
  margin-left: auto; font-family: var(--font-mono); font-size: .85rem;
  color: var(--orange); background: rgba(255,112,67,.08);
  padding: .4rem 1rem; border-radius: 20px; border: 1px solid rgba(255,112,67,.2);
}}
.quiz-q {{ margin-bottom: 1.5rem; }}
.quiz-q .q-text {{ font-size: .95rem; font-weight: 700; margin-bottom: .8rem; line-height: 1.5; }}
.quiz-q .q-context {{
  font-size: .8rem; color: var(--muted); margin-bottom: .8rem; line-height: 1.5;
  font-style: italic;
}}
.quiz-options {{ display: flex; flex-direction: column; gap: .5rem; }}
.quiz-opt {{
  display: flex; align-items: flex-start; gap: .8rem; cursor: pointer;
  background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: .8rem 1rem; transition: all .2s; font-size: .88rem; line-height: 1.5;
}}
.quiz-opt:hover {{ border-color: var(--blue); background: rgba(79,142,247,.05); }}
.quiz-opt.correct {{ border-color: var(--green); background: rgba(102,187,106,.08); }}
.quiz-opt.wrong   {{ border-color: var(--red);   background: rgba(239,83,80,.08); }}
.quiz-opt.reveal  {{ border-color: var(--green); background: rgba(102,187,106,.05); }}
.opt-letter {{
  width: 24px; height: 24px; border-radius: 6px; border: 1px solid var(--border);
  display: grid; place-items: center; font-family: var(--font-mono); font-size: .75rem;
  flex-shrink: 0; font-weight: 500;
}}
.quiz-opt.correct .opt-letter {{ background: var(--green); border-color: var(--green); color: #fff; }}
.quiz-opt.wrong   .opt-letter {{ background: var(--red);   border-color: var(--red);   color: #fff; }}
.quiz-opt.reveal  .opt-letter {{ background: var(--green); border-color: var(--green); color: #fff; }}
.q-explanation {{
  display: none; margin-top: .8rem; padding: .8rem 1rem;
  background: rgba(79,142,247,.06); border: 1px solid rgba(79,142,247,.15);
  border-radius: 8px; font-size: .82rem; color: var(--text); line-height: 1.6;
}}
.q-explanation.show {{ display: block; }}
.q-explanation strong {{ color: var(--blue); }}
.quiz-submit {{
  width: 100%; padding: .9rem; border-radius: 10px; border: none;
  background: var(--orange); color: #fff; font-family: var(--font-head);
  font-size: 1rem; font-weight: 700; cursor: pointer; letter-spacing: 1px;
  margin-top: 1.5rem; transition: opacity .2s;
}}
.quiz-submit:hover {{ opacity: .9; }}
.quiz-submit:disabled {{ opacity: .5; cursor: not-allowed; }}
.quiz-result {{
  display: none; text-align: center; padding: 2rem;
  border: 1px solid var(--border); border-radius: 14px; margin-top: 1.5rem;
  background: var(--card);
}}
.quiz-result.show {{ display: block; }}
.quiz-result .qr-score {{ font-family: var(--font-head); font-size: 3rem; font-weight: 800; color: var(--orange); }}
.quiz-result .qr-label {{ font-size: 1rem; color: var(--muted); margin-top: .3rem; }}
.quiz-result .qr-msg   {{ font-size: .9rem; margin-top: 1rem; color: var(--text); line-height: 1.6; max-width: 480px; margin-inline: auto; }}
.quiz-reset {{
  padding: .7rem 2rem; border-radius: 10px; border: 1px solid var(--border);
  background: var(--card); color: var(--text); font-family: var(--font-body);
  font-size: .9rem; font-weight: 700; cursor: pointer; margin-top: 1rem; transition: all .2s;
}}
.quiz-reset:hover {{ border-color: var(--orange); color: var(--orange); }}

/* ── DIVIDER ── */
.divider {{
  height: 1px; background: linear-gradient(to right, transparent, var(--border), transparent);
  margin: 3rem 0;
}}

/* ── RESPONSIVE ── */
@media (max-width: 820px) {{
  .sidebar {{ display: none; }}
  .main {{ margin-left: 0; padding: 1.5rem 1rem 5rem; }}
  .card-grid.cols2, .card-grid.cols3 {{ grid-template-columns: 1fr; }}
  .concept-grid {{ grid-template-columns: 1fr; }}
}}

/* ── ANIMATIONS ── */
@keyframes fadeUp {{ from {{ opacity:0; transform: translateY(16px); }} to {{ opacity:1; transform: translateY(0); }} }}
.section {{ animation: fadeUp .5s ease both; }}
.section:nth-child(1) {{ animation-delay: .05s; }}
.section:nth-child(2) {{ animation-delay: .1s; }}
.section:nth-child(3) {{ animation-delay: .15s; }}
</style>
</head>'''
        
        return header
    
    # Color palette for section rotation
    SECTION_COLORS = [
        ("blue", "#4F8EF7", "rgba(79,142,247,"),
        ("orange", "#FF7043", "rgba(255,112,67,"),
        ("pink", "#F06292", "rgba(240,98,146,"),
        ("purple", "#AB7DF6", "rgba(171,125,246,"),
        ("yellow", "#FFD23F", "rgba(255,210,63,"),
        ("teal", "#00C9A7", "rgba(0,229,195,"),
        ("green", "#66BB6A", "rgba(102,187,106,"),
    ]

    def _get_section_color(self, index: int):
        """Get color tuple for a section by index"""
        return self.SECTION_COLORS[index % len(self.SECTION_COLORS)]

    def _generate_hero_section(self, topic: str, content_structure: Dict[str, Any], style_guide: Dict[str, Any]) -> str:
        """Generate hero section with track badge and topic pills"""
        theme = content_structure.get("theme", "")
        sections = content_structure.get("sections", [])
        total = content_structure.get("total_sections", len(sections))
        
        hero = f'''
<!-- Main Content -->
<main class="main">

<!-- Hero Section -->
<div class="hero">
  <div class="track-badge">⚡ LEARNING GUIDE · {total} SECTIONS</div>
  <h1><em>{topic}</em></h1>
  <p>{theme}</p>
  <div class="topic-pills">'''

        for i, section in enumerate(sections):
            if section.get("type") == "summary":
                continue
            sid = section.get("id", f"section_{i}")
            title = section.get("title", f"Section {i+1}")
            _, color_var, rgba_prefix = self._get_section_color(i)
            hero += f'''
    <a href="#{sid}" class="pill" style="color:{color_var};border-color:{rgba_prefix}.4);background:{rgba_prefix}.06)">{title}</a>'''

        hero += '''
  </div>
</div>'''
        
        return hero
    
    def _generate_sidebar_navigation(self, sections: List[Dict[str, Any]], style_guide: Dict[str, Any]) -> str:
        """Generate sidebar navigation with color-coded dots"""
        topic = style_guide.get("topic", "Learning Guide")
        total = len(sections)
        
        nav = f'''
<!-- Sidebar Navigation -->
<nav class="sidebar">
  <div class="sidebar-logo">{topic} <span>{total} sections</span></div>'''
        
        for i, section in enumerate(sections):
            section_id = section.get("id", f"section_{i+1}")
            section_title = section.get("title", f"Section {i+1}")
            section_num = f"{i+1:02d}"
            color_name, _, _ = self._get_section_color(i)
            
            nav += f'''
  <a class="nav-item" href="#{section_id}"><span class="nav-dot" style="background:var(--{color_name})"></span>{section_title}<span class="nav-num">{section_num}</span></a>'''
        
        nav += '''
  <a class="nav-item" href="#quiz"><span class="nav-dot" style="background:var(--orange)"></span>Self-Quiz 🎯<span class="nav-num">Q</span></a>
</nav>'''
        
        return nav
    
    async def _generate_section(self, section: Dict[str, Any], style_guide: Dict[str, Any], section_index: int = 0) -> str:
        """Generate individual section content using structured JSON from LLM"""
        section_id = section.get("id", "section")
        section_title = section.get("title", "Section")
        section_type = section.get("type", "content")
        
        # Section numbering
        if section_id.startswith("section_"):
            try:
                section_num = int(section_id.split("_")[1])
            except (ValueError, IndexError):
                section_num = section_index + 1
        elif section_id == "introduction":
            section_num = 0
        elif section_id == "summary":
            section_num = section_index
        else:
            section_num = section_index + 1
        
        color_name, color_var, rgba_prefix = self._get_section_color(section_index)
        num_str = f"{section_num:02d}" if section_num < 100 else "✓"
        
        section_html = f'''
<!-- Section: {section_title} -->
<section id="{section_id}" class="section">
  <div class="section-header">
    <div class="section-num" style="background:{rgba_prefix}.12);color:var(--{color_name});">{num_str}</div>
    <h2>{section_title}</h2>
    <span class="em-tag">🎯 EM Relevance: HIGH</span>
  </div>'''
        
        # Generate content based on section type
        if section_type == "intro":
            section_html += await self._generate_intro_content(section, style_guide)
        elif section_type == "content":
            section_html += await self._generate_main_content(section, style_guide, section_index)
        elif section_type == "summary":
            section_html += await self._generate_summary_content(section, style_guide)
        else:
            section_html += await self._generate_main_content(section, style_guide, section_index)
        
        section_html += '\n</section>\n'
        
        return section_html
    
    async def _generate_intro_content(self, section: Dict[str, Any], style_guide: Dict[str, Any]) -> str:
        """Generate introduction section content using structured JSON from LLM"""
        section_title = section.get("title", "Introduction")
        
        prompt = f"""Generate an engaging introduction for the topic: "{section_title}"

Write in Head First / Byte Byte Go style: conversational, bold, problem-first.
Target audience: Engineering Managers who need credible technical fluency.

Return ONLY valid JSON (no markdown fences) with these keys:
{{
  "core_question": "A bold opening question or statement that hooks the reader (1-2 sentences)",
  "welcome_text": "A short, punchy paragraph (2-3 sentences) explaining what they will learn and why it matters for EMs",
  "learning_objectives": ["objective 1", "objective 2", "objective 3"],
  "em_insight": "Why this topic is especially important for engineering managers (1-2 sentences)"
}}"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert educational content designer. Always respond with valid JSON only, no markdown."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            data = json.loads(response.choices[0].message.content.strip())
            observability_service.record_token_usage(self.agent_id, "gpt-4", response.usage.total_tokens)
        except Exception as e:
            self.logger.error(f"Error generating intro content: {str(e)}")
            data = {
                "core_question": f"What is {section_title} and why should every EM understand it?",
                "welcome_text": f"This guide covers the essential concepts of {section_title} with practical examples and insights designed specifically for engineering managers.",
                "learning_objectives": ["Understand core concepts", "Apply practical knowledge", "Make better technical decisions"],
                "em_insight": "Understanding this topic helps you lead technical discussions with credibility and make informed architectural decisions."
            }
        
        html = f'''
  <div class="highlight">
    <span class="hl-label">THE CORE QUESTION</span>
    <p><strong>{data.get("core_question", "")}</strong></p>
  </div>

  <div class="card">
    <h3>🎯 What You'll Learn</h3>
    <p>{data.get("welcome_text", "")}</p>
    <ul>'''
        for obj in data.get("learning_objectives", []):
            html += f'\n      <li><strong>{obj}</strong></li>'
        html += '''
    </ul>
  </div>

  <div class="em-insight">
    <div class="ei-label">🎯 EM INSIGHT — Why this matters for you</div>
    <p>''' + data.get("em_insight", "") + '''</p>
  </div>'''
        return html
    
    async def _generate_main_content(self, section: Dict[str, Any], style_guide: Dict[str, Any], section_index: int = 0) -> str:
        """Generate main content section using structured JSON from LLM"""
        section_title = section.get("title", "Content Section")
        color_name, color_var, rgba_prefix = self._get_section_color(section_index)
        
        prompt = f"""Generate educational content for the topic: "{section_title}"

Write in Head First / Byte Byte Go style: problem-first, use real-world analogies, conversational and bold.
Target audience: Engineering Managers who need credible technical fluency.

Return ONLY valid JSON (no markdown fences) with these keys:
{{
  "core_question_label": "A short uppercase label like THE BIG IDEA or THE CORE TENSION or WHY THIS MATTERS (max 5 words)",
  "core_question": "A bold 1-2 sentence statement framing the central problem or idea of this topic",
  "concepts": [
    {{
      "emoji": "an emoji that represents this concept",
      "name": "Concept Name",
      "definition": "Clear 1-2 sentence definition in plain language",
      "example": "A concrete real-world example (1-2 lines)",
      "when_to_use": ["bullet 1", "bullet 2", "bullet 3"]
    }}
  ],
  "analogy": {{
    "title": "A relatable analogy title",
    "explanation": "The analogy explained in 2-3 sentences, connecting the technical concept to something familiar"
  }},
  "em_insight_title": "EM INSIGHT — A specific actionable subtitle",
  "em_insights": ["Actionable insight 1 with bold key phrase", "Actionable insight 2", "Actionable insight 3"]
}}

Generate 2-3 concepts. Make insights specific and actionable, not generic."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert technical educator specializing in making complex topics accessible to engineering managers. Always respond with valid JSON only, no markdown."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=1200
            )
            data = json.loads(response.choices[0].message.content.strip())
            observability_service.record_token_usage(self.agent_id, "gpt-4", response.usage.total_tokens)
        except Exception as e:
            self.logger.error(f"Error generating main content: {str(e)}")
            data = {
                "core_question_label": "THE BIG IDEA",
                "core_question": f"Understanding {section_title} is essential for making informed technical decisions as an engineering manager.",
                "concepts": [
                    {"emoji": "📚", "name": "Key Concept", "definition": f"Core principle of {section_title}.", "example": "Applied in real-world engineering teams.", "when_to_use": ["When making architectural decisions", "During technical planning", "In team discussions"]}
                ],
                "analogy": {"title": "Think of it like building a house", "explanation": f"Just as a house needs a solid foundation, {section_title} provides the groundwork for sound engineering decisions."},
                "em_insight_title": "EM INSIGHT — What this means for your team",
                "em_insights": [f"Understanding {section_title} helps you ask the right questions in design reviews.", "This knowledge enables you to make better build vs. buy decisions.", "Use this to set the right technical direction for your team."]
            }
        
        return self._render_main_content_html(data, color_name, rgba_prefix)
    
    def _render_main_content_html(self, data: Dict[str, Any], color_name: str, rgba_prefix: str) -> str:
        """Render structured content data into HTML"""
        concepts = data.get("concepts", [])
        analogy = data.get("analogy", {})
        
        # Highlight box
        html = f'''
  <div class="highlight">
    <span class="hl-label">{data.get("core_question_label", "THE BIG IDEA")}</span>
    <p><strong>{data.get("core_question", "")}</strong></p>
  </div>'''
        
        # Concept cards as visual grid diagram
        if len(concepts) >= 2:
            cols = "cols3" if len(concepts) >= 3 else "cols2"
            html += f'''

  <div class="diagram">
    <div class="diagram-title">KEY CONCEPTS — SIDE BY SIDE</div>
    <div class="card-grid {cols}">'''
            
            concept_colors = [
                ("blue", "rgba(79,142,247,"),
                ("teal", "rgba(0,229,195,"),
                ("purple", "rgba(171,125,246,"),
                ("orange", "rgba(255,112,67,"),
                ("pink", "rgba(240,98,146,"),
            ]
            
            for ci, concept in enumerate(concepts):
                cc_name, cc_rgba = concept_colors[ci % len(concept_colors)]
                html += f'''
      <div class="concept-card" style="background:{cc_rgba}.06);border-color:{cc_rgba}.2)">
        <span class="cc-icon">{concept.get("emoji", "📌")}</span>
        <div class="cc-name" style="color:var(--{cc_name})">{concept.get("name", "")}</div>
        <div class="cc-def">{concept.get("definition", "")}</div>
        <div class="cc-example">{concept.get("example", "")}</div>
      </div>'''
            
            html += '''
    </div>
  </div>'''
        elif concepts:
            concept = concepts[0]
            html += f'''
  <div class="card">
    <h3 style="color:var(--{color_name})">{concept.get("emoji", "📌")} {concept.get("name", "")}</h3>
    <p>{concept.get("definition", "")}</p>
    <p style="margin-top:.5rem"><strong>Example:</strong> {concept.get("example", "")}</p>
  </div>'''
        
        # When-to-use cards
        if concepts and any(c.get("when_to_use") for c in concepts):
            cols = "cols3" if len(concepts) >= 3 else "cols2"
            html += f'''

  <div class="card-grid {cols}">'''
            for ci, concept in enumerate(concepts):
                cc_name = ["blue", "teal", "purple", "orange", "pink"][ci % 5]
                html += f'''
    <div class="card">
      <h3 style="color:var(--{cc_name})">{concept.get("emoji", "📌")} {concept.get("name", "")} — When to use</h3>
      <ul>'''
                for item in concept.get("when_to_use", []):
                    html += f'\n        <li>{item}</li>'
                html += '''
      </ul>
    </div>'''
            html += '''
  </div>'''
        
        # Analogy card
        if analogy.get("title"):
            html += f'''

  <div class="card">
    <h3 style="color:var(--{color_name})">💡 Analogy: {analogy.get("title", "")}</h3>
    <p>{analogy.get("explanation", "")}</p>
  </div>'''
        
        # EM Insight
        html += f'''

  <div class="em-insight">
    <div class="ei-label">🎯 {data.get("em_insight_title", "EM INSIGHT")}</div>
    <ul>'''
        for insight in data.get("em_insights", []):
            html += f'\n      <li><strong>{insight.split(".")[0]}.</strong>{".".join(insight.split(".")[1:]) if "." in insight else ""}</li>'
        html += '''
    </ul>
  </div>'''
        
        return html
    
    async def _generate_summary_content(self, section: Dict[str, Any], style_guide: Dict[str, Any]) -> str:
        """Generate summary section content"""
        return '''
  <div class="highlight">
    <span class="hl-label">CONGRATULATIONS</span>
    <p><strong>You've completed this learning guide!</strong> You now have the foundational fluency to lead technical discussions with confidence and make informed decisions.</p>
  </div>

  <div class="card-grid cols2">
    <div class="card">
      <h3 style="color:var(--green)">✅ Key Takeaways</h3>
      <ul>
        <li>You understand the core concepts and how they connect</li>
        <li>You can ask the right questions in design reviews</li>
        <li>You know the tradeoffs your team faces</li>
        <li>You have the vocabulary for credible technical conversations</li>
      </ul>
    </div>
    <div class="card">
      <h3 style="color:var(--blue)">� Next Steps</h3>
      <ul>
        <li>Apply these concepts in your next 1:1 or design review</li>
        <li>Share this guide with your team for alignment</li>
        <li>Dive deeper into the areas most relevant to your current projects</li>
        <li>Take the quiz below to test your understanding</li>
      </ul>
    </div>
  </div>

  <div class="em-insight">
    <div class="ei-label">🎯 EM INSIGHT — The ongoing journey</div>
    <p>Technical fluency is a muscle, not a destination. The best EMs stay curious, keep learning, and create environments where their teams can teach them. Use this foundation as a springboard.</p>
  </div>'''
    
    async def _generate_quiz_section(self, topic: str, sections: List[Dict[str, Any]], style_guide: Dict[str, Any]) -> str:
        """Generate interactive quiz section with up to 5 questions per topic"""
        # Collect section titles for quiz generation (skip intro/summary)
        content_sections = [s for s in sections if s.get("type") == "content"]
        section_titles = [s.get("title", "") for s in content_sections]
        
        prompt = f"""Generate quiz questions for: "{topic}"

Sections covered: {json.dumps(section_titles)}

Generate UP TO 5 questions PER SECTION for comprehensive coverage.
Each question should test EM decision-making, not just definitions.
Use scenario-based questions where possible.

Return ONLY a valid JSON array (no markdown fences):
[
  {{
    "q": "The question text — scenario-based, from an EM perspective",
    "context": "Optional 1-sentence context/scenario setup (or empty string)",
    "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
    "answer": 0,
    "explanation": "<strong>Correct.</strong> Explanation of why this answer is right and others are wrong (use <strong> for emphasis)"
  }}
]

Rules:
- answer is a 0-indexed integer (0=A, 1=B, 2=C, 3=D)
- Generate {min(len(content_sections) * 5, 25)} questions total
- Cover ALL sections proportionally
- Make wrong options plausible — avoid obvious throwaway answers
- Explanations should teach, not just confirm"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert educational assessor for engineering managers. Generate challenging, scenario-based quiz questions. Always respond with valid JSON array only, no markdown."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=4000
            )
            raw = response.choices[0].message.content.strip()
            # Handle potential markdown fences
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            quiz_data = json.loads(raw)
            observability_service.record_token_usage(self.agent_id, "gpt-4", response.usage.total_tokens)
        except Exception as e:
            self.logger.error(f"Error generating quiz: {str(e)}")
            quiz_data = [
                {
                    "q": f"What is the most important consideration for an EM working with {topic}?",
                    "context": "",
                    "options": ["Deep technical implementation details", "Strategic alignment with business goals", "Both technical understanding and strategic alignment", "Delegating entirely to the team"],
                    "answer": 2,
                    "explanation": "<strong>Correct.</strong> EMs need both technical credibility and strategic thinking. Pure delegation without understanding leads to poor decisions, while getting lost in implementation details misses the bigger picture."
                },
                {
                    "q": f"Your team proposes a new approach to {topic}. What's your first question?",
                    "context": "The team is excited about a new technology they want to adopt.",
                    "options": ["How does this compare to our current approach in measurable terms?", "Which blog post did you read about this?", "Let's just try it and see what happens", "I'll need to research this myself before deciding"],
                    "answer": 0,
                    "explanation": "<strong>Correct.</strong> Asking for measurable comparison against the baseline is the EM's most powerful question. It forces rigorous thinking, prevents hype-driven decisions, and ensures any change is justified by evidence."
                },
                {
                    "q": f"When should an EM push back on a team's technical decision about {topic}?",
                    "context": "",
                    "options": ["Never — trust the team completely", "Always — maintain control over all decisions", "When the decision has significant cost, risk, or strategic implications that the team may not fully see", "Only when you personally disagree with the approach"],
                    "answer": 2,
                    "explanation": "<strong>Correct.</strong> EMs should push back when they see risks or strategic misalignment the team might miss — not to micromanage, but to ensure decisions account for the full picture including cost, timeline, and organizational context."
                }
            ]
        
        total_q = len(quiz_data)
        quiz_json = json.dumps(quiz_data, ensure_ascii=False)
        
        quiz_html = f'''
<!-- Quiz Section -->
<section class="quiz-section" id="quiz">
  <div class="quiz-header">
    <div style="font-size:1.5rem">🎯</div>
    <h2>Self-Quiz — {topic}</h2>
    <div class="quiz-score" id="scoreDisplay">0 / {total_q} answered</div>
  </div>
  <p style="font-size:.88rem;color:var(--muted);margin-bottom:1.5rem">Answer as an Engineering Manager would. Focus on the <em>decision-making</em> angle, not just textbook definitions. Click your answer, then submit to see explanations.</p>

  <div id="quizContainer"></div>

  <button class="quiz-submit" id="submitBtn" onclick="submitQuiz()">Submit &amp; See My Score</button>
  <div class="quiz-result" id="quizResult">
    <div class="qr-score" id="finalScore"></div>
    <div class="qr-label">out of {total_q} correct</div>
    <div class="qr-msg" id="finalMsg"></div>
    <button class="quiz-reset" onclick="resetQuiz()">↩ Retake Quiz</button>
  </div>
</section>

</main>

<script>
const questions = {quiz_json};

let selected = new Array(questions.length).fill(null);
let submitted = false;

function buildQuiz() {{
  const container = document.getElementById('quizContainer');
  container.innerHTML = '';
  questions.forEach((q, qi) => {{
    const div = document.createElement('div');
    div.className = 'quiz-q';
    div.innerHTML = `
      <div class="q-text">${{qi+1}}. ${{q.q}}</div>
      ${{q.context ? `<div class="q-context">📋 Context: ${{q.context}}</div>` : ''}}
      <div class="quiz-options" id="opts-${{qi}}">
        ${{q.options.map((o,oi) => `
          <div class="quiz-opt" id="opt-${{qi}}-${{oi}}" onclick="selectOpt(${{qi}},${{oi}})">
            <div class="opt-letter">${{String.fromCharCode(65+oi)}}</div>
            <div>${{o}}</div>
          </div>
        `).join('')}}
      </div>
      <div class="q-explanation" id="exp-${{qi}}">${{q.explanation}}</div>
    `;
    container.appendChild(div);
  }});
  updateScore();
}}

function selectOpt(qi, oi) {{
  if (submitted) return;
  selected[qi] = oi;
  document.querySelectorAll(`#opts-${{qi}} .quiz-opt`).forEach(el => {{
    el.classList.remove('correct','wrong','reveal');
    el.style.borderColor = '';
    el.style.background = '';
  }});
  document.getElementById(`opt-${{qi}}-${{oi}}`).style.borderColor = 'var(--blue)';
  document.getElementById(`opt-${{qi}}-${{oi}}`).style.background = 'rgba(79,142,247,.07)';
  updateScore();
}}

function updateScore() {{
  const answered = selected.filter(s => s !== null).length;
  document.getElementById('scoreDisplay').textContent = `${{answered}} / ${{questions.length}} answered`;
}}

function submitQuiz() {{
  if (submitted) return;
  submitted = true;
  document.getElementById('submitBtn').disabled = true;
  let correct = 0;
  questions.forEach((q, qi) => {{
    const opts = document.querySelectorAll(`#opts-${{qi}} .quiz-opt`);
    opts.forEach((el, oi) => {{
      el.style.borderColor = '';
      el.style.background = '';
      if (oi === q.answer) el.classList.add('reveal');
    }});
    if (selected[qi] !== null) {{
      const chosenEl = document.getElementById(`opt-${{qi}}-${{selected[qi]}}`);
      chosenEl.classList.remove('reveal');
      if (selected[qi] === q.answer) {{
        chosenEl.classList.add('correct'); correct++;
      }} else {{
        chosenEl.classList.add('wrong');
        document.getElementById(`opt-${{qi}}-${{q.answer}}`).classList.add('reveal');
      }}
    }}
    document.getElementById(`exp-${{qi}}`).classList.add('show');
  }});
  const pct = correct / questions.length;
  document.getElementById('finalScore').textContent = correct;
  const msgs = [
    [0.3, "Keep going! Re-read the sections and try again. These concepts take a few passes to stick."],
    [0.5, "Good start! Review the EM Insight boxes — they have the decision-making angle you need."],
    [0.7, "Solid foundation! A few tricky spots. Focus on the sections you missed."],
    [0.9, "Strong work! You're thinking like an EM. One more pass and you'll have full fluency."],
    [1.1, "Perfect score! 🎉 You're ready for credible technical conversations with your team."]
  ];
  const msg = msgs.find(([t]) => pct < t) || msgs[msgs.length-1];
  document.getElementById('finalMsg').textContent = msg[1];
  document.getElementById('quizResult').classList.add('show');
  document.getElementById('quizResult').scrollIntoView({{behavior:'smooth',block:'center'}});
}}

function resetQuiz() {{
  selected = new Array(questions.length).fill(null);
  submitted = false;
  document.getElementById('submitBtn').disabled = false;
  document.getElementById('quizResult').classList.remove('show');
  buildQuiz();
}}

// Nav highlight on scroll
const sectionEls = document.querySelectorAll('section[id]');
const navItems = document.querySelectorAll('.nav-item');
const observer = new IntersectionObserver(entries => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      navItems.forEach(n => n.classList.remove('active'));
      const match = document.querySelector(`.nav-item[href="#${{e.target.id}}"]`);
      if (match) match.classList.add('active');
    }}
  }});
}}, {{ threshold: 0.3 }});
sectionEls.forEach(s => observer.observe(s));

buildQuiz();
</script>'''
        
        return quiz_html
    
    async def _save_html_file(self, topic: str, html_content: str) -> Path:
        """Save HTML content to file"""
        # Generate filename
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_topic.lower().replace(' ', '_')}_explainer.html"
        file_path = self.output_dir / filename
        
        # Save file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.logger.info(f"Saved HTML file: {file_path}")
        
        return file_path
    
    async def _handle_request(self, message: AgentMessage) -> None:
        """Handle incoming request messages"""
        with TracingContext("handle_request", self.agent_id, message_id=message.message_id) as span:
            try:
                task_data = message.content
                result = await self.process_task(task_data)
                
                # Send response
                await self.communication.send_response(
                    sender=self.agent_id,
                    receiver=message.sender,
                    correlation_id=message.correlation_id,
                    content=result
                )
                
            except Exception as e:
                self.logger.error(f"Error handling request: {str(e)}")
                
                # Send error response
                await self.communication.send_response(
                    sender=self.agent_id,
                    receiver=message.sender,
                    correlation_id=message.correlation_id,
                    content={
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                )
    
    async def _handle_notification(self, message: AgentMessage) -> None:
        """Handle notification messages"""
        notification_type = message.content.get("type", "")
        self.logger.info(f"Received notification: {notification_type}")
        
        # Handle different notification types
        if notification_type == "context_available":
            await self._handle_context_available(message)
        elif notification_type == "context_update":
            await self._handle_context_update(message)
    
    async def _handle_context_available(self, message: AgentMessage) -> None:
        """Handle context available notifications"""
        context_id = message.content.get("context_id")
        context_type = message.content.get("context_type")
        sender = message.content.get("sender")
        
        self.logger.info(f"Context available: {context_id} ({context_type}) from {sender}")
        
        # If this is a research plan context, process it
        if context_type == "research_plan" and sender == "research_agent":
            try:
                result = await self._process_context_based_generation(context_id)
                
                # Send notification about completion
                await self.communication.send_message(
                    receiver=sender,
                    message_type=MessageType.NOTIFICATION,
                    content={
                        "type": "html_generation_completed",
                        "context_id": context_id,
                        "topic": result.get("topic"),
                        "file_path": result.get("file_path"),
                        "status": result.get("status")
                    }
                )
                
            except Exception as e:
                self.logger.error(f"Error processing context-based generation: {str(e)}")
    
    async def _handle_context_update(self, message: AgentMessage) -> None:
        """Handle context update notifications"""
        context_id = message.content.get("context_id")
        if context_id:
            context = mcp_registry.get_context(context_id, self.agent_id)
            if context:
                self.logger.info(f"Received context update for {context_id}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        base_status = await self.health_check()
        
        # Add agent-specific status
        base_status.update({
            "capabilities": self.capabilities,
            "active_contexts": len(self.contexts),
            "communication_metrics": self.communication.broker.get_metrics(),
            "generated_files": len(list(self.output_dir.glob("*.html"))) if self.output_dir.exists() else 0
        })
        
        return base_status
    
    async def cleanup(self) -> None:
        """Cleanup agent resources"""
        await self.communication.cleanup()
        
        # Unregister from observability
        observability_service.unregister_agent(self.agent_id)
        
        self.logger.info("HTML Generation Agent cleaned up")
