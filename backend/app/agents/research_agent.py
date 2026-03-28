"""
Research Agent (Agent 2)
Uses RAG to research subtopics and create content plans
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json

from app.agents.base_agent import BaseAgent, AgentMessage
from app.core.mcp_protocol import mcp_registry, create_research_plan_context, ContextType
from app.core.a2a_communication import CommunicationManager, MessageType, MessagePriority
from app.core.vector_db import vector_db_service
from app.core.observability import observability_service, TracingContext


class ResearchAgent(BaseAgent):
    """Agent responsible for researching subtopics and creating content plans"""
    
    def __init__(self):
        super().__init__("research_agent", "Research & Planning Specialist")
        self.communication = CommunicationManager(self.agent_id)
        self.capabilities = ["rag_research", "content_planning", "source_analysis", "knowledge_synthesis"]
        
        # Register message handlers
        self.communication.register_handler(MessageType.REQUEST, self._handle_request)
        self.communication.register_handler(MessageType.NOTIFICATION, self._handle_notification)
        
        # OpenAI client for LLM operations
        import openai
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Register with observability
        observability_service.register_agent(self.agent_id, "research")
        
        # Subscribe to relevant topics
        self.communication.subscribe_to_topic("research_planning")
        self.communication.subscribe_to_topic("context_updates")
        
        self.logger.info("Research Agent initialized")
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process research task"""
        with TracingContext("research_task", self.agent_id, task_type="research_planning") as span:
            try:
                # Check if this is a continuation from topic breakdown
                context_id = task.get("context_id")
                if context_id:
                    return await self._process_context_based_research(context_id)
                
                # Otherwise, process direct research request
                topic = task.get("topic", "")
                subtopics = task.get("subtopics", [])
                research_queries = task.get("research_queries", [])
                
                if not topic:
                    raise ValueError("Topic is required")
                
                self.logger.info(f"Processing research for: {topic}")
                
                # Step 1: Research each subtopic using RAG
                research_results = await self._research_subtopics(subtopics)
                
                # Step 2: Synthesize findings
                synthesized_content = await self._synthesize_findings(topic, research_results)
                
                # Step 3: Create content structure
                content_structure = await self._create_content_structure(topic, subtopics, synthesized_content)
                
                # Step 4: Generate style guide
                style_guide = await self._generate_style_guide(topic, synthesized_content)
                
                # Step 5: Create MCP context
                context_id = f"research_plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                context = create_research_plan_context(
                    context_id=context_id,
                    agent_id=self.agent_id,
                    research_plan=content_structure,
                    sources=[result["sources"] for result in research_results]
                )
                
                # Register context
                mcp_registry.register_context(context)
                
                # Step 6: Share context with HTML generation agent
                await self._share_context_with_html_agent(context)
                
                result = {
                    "status": "success",
                    "topic": topic,
                    "context_id": context_id,
                    "research_results": research_results,
                    "synthesized_content": synthesized_content,
                    "content_structure": content_structure,
                    "style_guide": style_guide,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                self.logger.info(f"Successfully completed research for: {topic}")
                return result
                
            except Exception as e:
                self.logger.error(f"Error processing research task: {str(e)}")
                raise
    
    async def _process_context_based_research(self, context_id: str) -> Dict[str, Any]:
        """Process research based on existing context from topic breakdown"""
        with TracingContext("context_based_research", self.agent_id) as span:
            span.set_attribute("context_id", context_id)
            
            # Get the context from MCP registry
            context = mcp_registry.get_context(context_id, self.agent_id)
            if not context:
                raise ValueError(f"Context {context_id} not found")
            
            topic_data = context.content
            topic = topic_data["topic"]
            subtopics = topic_data["subtopics"]
            research_queries = topic_data["research_queries"]
            
            self.logger.info(f"Processing context-based research for: {topic}")
            
            # Research each subtopic
            research_results = await self._research_subtopics(subtopics)
            
            # Synthesize findings
            synthesized_content = await self._synthesize_findings(topic, research_results)
            
            # Create content structure
            content_structure = await self._create_content_structure(topic, subtopics, synthesized_content)
            
            # Generate style guide
            style_guide = await self._generate_style_guide(topic, synthesized_content)
            
            # Update the original context with research results
            context.content.update({
                "research_results": research_results,
                "synthesized_content": synthesized_content,
                "content_structure": content_structure,
                "style_guide": style_guide,
                "research_completed_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Create new context for HTML generation
            html_context_id = f"html_structure_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            html_context = create_research_plan_context(
                context_id=html_context_id,
                agent_id=self.agent_id,
                research_plan=content_structure,
                sources=[result["sources"] for result in research_results]
            )
            
            mcp_registry.register_context(html_context)
            
            # Share with HTML agent
            await self._share_context_with_html_agent(html_context)
            
            return {
                "status": "success",
                "topic": topic,
                "original_context_id": context_id,
                "new_context_id": html_context_id,
                "research_results": research_results,
                "synthesized_content": synthesized_content,
                "content_structure": content_structure,
                "style_guide": style_guide,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _research_subtopics(self, subtopics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Research each subtopic using RAG"""
        with TracingContext("research_subtopics", self.agent_id) as span:
            span.set_attribute("subtopics_count", len(subtopics))
            
            research_results = []
            
            for subtopic in subtopics:
                subtopic_id = subtopic.get("id", "unknown")
                subtopic_title = subtopic.get("title", "")
                
                with TracingContext("research_single_subtopic", self.agent_id, subtopic_id=subtopic_id) as subtopic_span:
                    try:
                        # Search for relevant content
                        search_results = await vector_db_service.search_similar_content(
                            query=subtopic_title,
                            n_results=5,
                            content_type="topic"
                        )
                        
                        # Record vector DB query
                        observability_service.record_vector_db_query(subtopic_title, len(search_results), 0.2)
                        
                        # Analyze and synthesize search results
                        synthesized_research = await self._synthesize_search_results(subtopic, search_results)
                        
                        research_result = {
                            "subtopic_id": subtopic_id,
                            "subtopic_title": subtopic_title,
                            "search_results": search_results,
                            "synthesized_research": synthesized_research,
                            "sources": [result["metadata"] for result in search_results],
                            "confidence_score": self._calculate_confidence_score(search_results, synthesized_research)
                        }
                        
                        research_results.append(research_result)
                        
                        subtopic_span.set_attributes({
                            "search_results_count": len(search_results),
                            "confidence_score": research_result["confidence_score"]
                        })
                        
                    except Exception as e:
                        self.logger.error(f"Error researching subtopic {subtopic_title}: {str(e)}")
                        
                        # Add placeholder result
                        research_results.append({
                            "subtopic_id": subtopic_id,
                            "subtopic_title": subtopic_title,
                            "search_results": [],
                            "synthesized_research": f"Research data for {subtopic_title} will be generated during HTML creation.",
                            "sources": [],
                            "confidence_score": 0.0
                        })
            
            span.set_attribute("research_completed", len(research_results))
            return research_results
    
    async def _synthesize_search_results(self, subtopic: Dict[str, Any], search_results: List[Dict[str, Any]]) -> str:
        """Synthesize search results into coherent research"""
        subtopic_title = subtopic.get("title", "")
        subtopic_description = subtopic.get("description", "")
        
        # Combine search results
        combined_content = "\n\n".join([
            result["content"] for result in search_results[:3]  # Limit to top 3 results
        ])
        
        if not combined_content.strip():
            return f"Research for {subtopic_title}: Based on the topic '{subtopic_description}', this section will cover key concepts and practical applications."
        
        prompt = f"""
        Synthesize the following research content for the subtopic: "{subtopic_title}"
        
        Subtopic Description: {subtopic_description}
        
        Research Content:
        {combined_content}
        
        Create a synthesized research summary that:
        1. Extracts key concepts and insights
        2. Identifies main themes and patterns
        3. Highlights important relationships
        4. Maintains educational clarity
        5. Is suitable for Head First/Byte Byte Go style content
        
        Keep it concise but comprehensive (200-300 words).
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert educational researcher. Create clear, engaging syntheses of technical content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            synthesized = response.choices[0].message.content.strip()
            
            # Record token usage
            usage = response.usage
            observability_service.record_token_usage(
                self.agent_id, "gpt-4", usage.total_tokens
            )
            
            return synthesized
            
        except Exception as e:
            self.logger.error(f"Error synthesizing search results: {str(e)}")
            return f"Research synthesis for {subtopic_title}: Key concepts and insights will be developed based on available educational content."
    
    async def _synthesize_findings(self, topic: str, research_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesize all research findings"""
        with TracingContext("synthesize_findings", self.agent_id) as span:
            span.set_attribute("research_results_count", len(research_results))
            
            # Extract key themes across all subtopics
            all_synthesized = [result["synthesized_research"] for result in research_results]
            combined_research = "\n\n".join(all_synthesized)
            
            prompt = f"""
            Synthesize research findings for the topic: "{topic}"
            
            Research Content:
            {combined_research}
            
            Create a comprehensive synthesis that includes:
            1. Overall theme and narrative
            2. Key learning objectives
            3. Main concepts and their relationships
            4. Practical applications and examples
            5. Target audience considerations
            
            Format as JSON with keys: theme, objectives, concepts, applications, audience
            """
            
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert curriculum designer. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                
                synthesis_text = response.choices[0].message.content.strip()
                synthesis = json.loads(synthesis_text)
                
                # Record token usage
                usage = response.usage
                observability_service.record_token_usage(
                    self.agent_id, "gpt-4", usage.total_tokens
                )
                
                return synthesis
                
            except Exception as e:
                self.logger.error(f"Error synthesizing findings: {str(e)}")
                return {
                    "theme": f"Comprehensive exploration of {topic}",
                    "objectives": ["Understand core concepts", "Apply practical knowledge", "Develop expertise"],
                    "concepts": ["Key concepts will be identified during content creation"],
                    "applications": ["Practical applications will be developed"],
                    "audience": "Intermediate learners"
                }
    
    async def _create_content_structure(self, topic: str, subtopics: List[Dict[str, Any]], 
                                       synthesized_content: Dict[str, Any]) -> Dict[str, Any]:
        """Create structured content outline"""
        with TracingContext("create_content_structure", self.agent_id) as span:
            sections = []
            
            # Introduction section
            sections.append({
                "id": "introduction",
                "title": f"Introduction to {topic}",
                "type": "intro",
                "content_type": "hero",
                "estimated_content": f"Welcome to learning about {topic}. This comprehensive guide covers essential concepts and practical applications.",
                "visual_elements": ["hero_banner", "topic_overview"],
                "interactions": ["learning_objectives"]
            })
            
            # Main content sections for each subtopic
            for i, subtopic in enumerate(subtopics):
                section_id = f"section_{i+1}"
                section = {
                    "id": section_id,
                    "title": subtopic.get("title", f"Section {i+1}"),
                    "type": "content",
                    "content_type": "main_content",
                    "estimated_content": f"Detailed exploration of {subtopic.get('title', 'this topic')} with practical examples and insights.",
                    "visual_elements": ["diagrams", "examples", "code_snippets"],
                    "interactions": ["quizzes", "exercises"],
                    "subtopic_id": subtopic.get("id"),
                    "research_reference": f"research_result_{i}"
                }
                sections.append(section)
            
            # Summary section
            sections.append({
                "id": "summary",
                "title": "Summary and Next Steps",
                "type": "summary",
                "content_type": "conclusion",
                "estimated_content": "Recap of key concepts and guidance for continued learning.",
                "visual_elements": ["key_takeaways", "resource_links"],
                "interactions": ["final_quiz", "certificate"]
            })
            
            content_structure = {
                "title": topic,
                "theme": synthesized_content.get("theme", ""),
                "learning_objectives": synthesized_content.get("objectives", []),
                "sections": sections,
                "total_sections": len(sections),
                "estimated_reading_time": len(subtopics) * 15,  # 15 minutes per subtopic
                "difficulty_level": "intermediate"
            }
            
            span.set_attributes({
                "sections_created": len(sections),
                "estimated_reading_time": content_structure["estimated_reading_time"]
            })
            
            return content_structure
    
    async def _generate_style_guide(self, topic: str, synthesized_content: Dict[str, Any]) -> Dict[str, Any]:
        """Generate style guide for HTML content"""
        with TracingContext("generate_style_guide", self.agent_id) as span:
            # Determine style based on content type
            audience = synthesized_content.get("audience", "intermediate")
            
            style_guide = {
                "visual_style": "head_first_byte_byte_go",
                "color_scheme": {
                    "primary": "#4F8EF7",  # Blue
                    "secondary": "#FF7043",  # Orange
                    "accent": "#FFD23F",  # Yellow
                    "background": "#FFF9EE",  # Warm paper (light theme)
                    "surface": "#FFFFFF",  # White surface
                    "card": "#F8F6F1",  # Warm card bg
                    "border": "#E2DDD5",  # Soft border
                    "text": "#1E1F2E",  # Dark ink text
                    "muted": "#6B7280"  # Muted text
                },
                "typography": {
                    "headings": "Syne",
                    "body": "DM Sans",
                    "code": "DM Mono"
                },
                "layout": {
                    "sidebar_navigation": True,
                    "sticky_headers": True,
                    "visual_diagrams": True,
                    "interactive_elements": True,
                    "responsive_design": True
                },
                "content_elements": {
                    "hero_section": True,
                    "progress_tracking": True,
                    "interactive_quizzes": True,
                    "code_examples": True,
                    "visual_explanations": True,
                    "em_insights": True
                },
                "tone": "engaging_educational",
                "complexity": "intermediate",
                "interactivity_level": "high"
            }
            
            span.set_attributes({
                "visual_style": style_guide["visual_style"],
                "interactivity_level": style_guide["interactivity_level"]
            })
            
            return style_guide
    
    def _calculate_confidence_score(self, search_results: List[Dict[str, Any]], synthesized_research: str) -> float:
        """Calculate confidence score for research quality"""
        if not search_results:
            return 0.0
        
        # Base score from number of results
        base_score = min(len(search_results) / 3.0, 1.0)  # Max score for 3+ results
        
        # Adjust based on content quality (simplified)
        content_length = len(synthesized_research)
        length_score = min(content_length / 200.0, 1.0)  # Prefer 200+ characters
        
        # Average distance (relevance) from search results
        if search_results and "distance" in search_results[0]:
            avg_distance = sum(r.get("distance", 0.5) for r in search_results) / len(search_results)
            relevance_score = 1.0 - avg_distance
        else:
            relevance_score = 0.5
        
        # Combined score
        confidence_score = (base_score * 0.4 + length_score * 0.3 + relevance_score * 0.3)
        
        return round(confidence_score, 2)
    
    async def _share_context_with_html_agent(self, context) -> None:
        """Share context with HTML generation agent via MCP"""
        try:
            # Subscribe HTML agent to this context
            mcp_registry.subscribe_to_context(context.context_id, "html_generation_agent")
            
            # Send notification to HTML agent
            await self.communication.send_message(
                receiver="html_generation_agent",
                message_type=MessageType.NOTIFICATION,
                content={
                    "type": "context_available",
                    "context_id": context.context_id,
                    "context_type": context.context_type.value,
                    "sender": self.agent_id
                },
                priority=MessagePriority.NORMAL
            )
            
            self.logger.info(f"Shared context {context.context_id} with HTML generation agent")
            
        except Exception as e:
            self.logger.error(f"Error sharing context with HTML agent: {str(e)}")
    
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
        
        # If this is a topic analysis context, process it
        if context_type == "topic_analysis" and sender == "topic_breakdown_agent":
            try:
                result = await self._process_context_based_research(context_id)
                
                # Send notification about completion
                await self.communication.send_message(
                    receiver=sender,
                    message_type=MessageType.NOTIFICATION,
                    content={
                        "type": "research_completed",
                        "original_context_id": context_id,
                        "new_context_id": result.get("new_context_id"),
                        "status": result.get("status")
                    }
                )
                
            except Exception as e:
                self.logger.error(f"Error processing context-based research: {str(e)}")
    
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
            "research_cache_size": 0
        })
        
        return base_status
    
    async def cleanup(self) -> None:
        """Cleanup agent resources"""
        await self.communication.cleanup()
        
        # Unregister from observability
        observability_service.unregister_agent(self.agent_id)
        
        self.logger.info("Research Agent cleaned up")
