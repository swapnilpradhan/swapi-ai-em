"""
Topic Breakdown Agent (Agent 1)
Analyzes user topics and breaks them down into subtopics for research
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json

from app.agents.base_agent import BaseAgent, AgentMessage
from app.core.mcp_protocol import mcp_registry, create_topic_analysis_context, ContextType
from app.core.a2a_communication import CommunicationManager, MessageType, MessagePriority
from app.core.vector_db import vector_db_service
from app.core.observability import observability_service, TracingContext


class TopicBreakdownAgent(BaseAgent):
    """Agent responsible for breaking down topics into subtopics"""
    
    def __init__(self):
        super().__init__("topic_breakdown_agent", "Topic Breakdown Specialist")
        self.communication = CommunicationManager(self.agent_id)
        self.capabilities = ["topic_analysis", "subtopic_generation", "research_planning", "rag_querying"]
        
        # Register message handlers
        self.communication.register_handler(MessageType.REQUEST, self._handle_request)
        self.communication.register_handler(MessageType.NOTIFICATION, self._handle_notification)
        
        # OpenAI client for LLM operations
        import openai
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Register with observability
        observability_service.register_agent(self.agent_id, "topic_breakdown")
        
        self.logger.info("Topic Breakdown Agent initialized")
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process topic breakdown task"""
        with TracingContext("topic_breakdown", self.agent_id, task_type="topic_analysis") as span:
            try:
                topic = task.get("topic", "")
                if not topic:
                    raise ValueError("Topic is required")
                
                self.logger.info(f"Processing topic breakdown for: {topic}")
                
                # Step 1: Analyze topic complexity and scope
                topic_analysis = await self._analyze_topic(topic)
                
                # Step 2: Generate subtopics
                subtopics = await self._generate_subtopics(topic, topic_analysis)
                
                # Step 3: Use RAG to find related content
                related_content = await self._find_related_content(topic, subtopics)
                
                # Step 4: Generate research queries
                research_queries = await self._generate_research_queries(topic, subtopics, related_content)
                
                # Step 5: Create MCP context
                context_id = f"topic_analysis_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                context = create_topic_analysis_context(
                    context_id=context_id,
                    agent_id=self.agent_id,
                    topic=topic,
                    subtopics=subtopics,
                    research_queries=research_queries
                )
                
                # Register context
                mcp_registry.register_context(context)
                
                # Step 6: Share context with research agent
                await self._share_context_with_research_agent(context)
                
                result = {
                    "status": "success",
                    "topic": topic,
                    "context_id": context_id,
                    "analysis": topic_analysis,
                    "subtopics": subtopics,
                    "related_content": related_content,
                    "research_queries": research_queries,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                self.logger.info(f"Successfully processed topic: {topic}")
                return result
                
            except Exception as e:
                self.logger.error(f"Error processing topic breakdown: {str(e)}")
                raise
    
    async def _analyze_topic(self, topic: str) -> Dict[str, Any]:
        """Analyze topic complexity and scope"""
        with TracingContext("analyze_topic", self.agent_id) as span:
            span.set_attribute("topic", topic)
            
            prompt = f"""
            Analyze the following topic for complexity and scope: "{topic}"
            
            Provide analysis in JSON format with:
            - complexity_level (simple/medium/complex)
            - domain_area (e.g., "AI/ML", "Software Engineering", "Product Management")
            - estimated_subtopics (number of subtopics needed)
            - key_concepts (main concepts involved)
            - research_depth (shallow/moderate/deep)
            - target_audience (beginner/intermediate/advanced)
            """
            
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert educational content analyst. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                
                analysis_text = response.choices[0].message.content
                analysis = json.loads(analysis_text)
                
                # Record token usage
                usage = response.usage
                observability_service.record_token_usage(
                    self.agent_id, "gpt-4", usage.total_tokens
                )
                
                span.set_attributes({
                    "complexity_level": analysis.get("complexity_level"),
                    "domain_area": analysis.get("domain_area"),
                    "estimated_subtopics": analysis.get("estimated_subtopics")
                })
                
                return analysis
                
            except Exception as e:
                self.logger.error(f"Error analyzing topic: {str(e)}")
                # Return default analysis
                return {
                    "complexity_level": "medium",
                    "domain_area": "General",
                    "estimated_subtopics": 3,
                    "key_concepts": [topic],
                    "research_depth": "moderate",
                    "target_audience": "intermediate"
                }
    
    async def _generate_subtopics(self, topic: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate subtopics based on analysis"""
        with TracingContext("generate_subtopics", self.agent_id) as span:
            complexity = analysis.get("complexity_level", "medium")
            estimated_count = analysis.get("estimated_subtopics", 3)
            domain = analysis.get("domain_area", "General")
            
            prompt = f"""
            Generate {estimated_count} subtopics for the topic: "{topic}"
            
            Context:
            - Complexity: {complexity}
            - Domain: {domain}
            - Target Audience: {analysis.get('target_audience', 'intermediate')}
            
            For each subtopic, provide:
            - title (clear and descriptive)
            - description (1-2 sentences)
            - priority (high/medium/low)
            - estimated_research_time (minutes)
            
            Respond with valid JSON array of subtopic objects.
            """
            
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert curriculum designer. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.4
                )
                
                subtopics_text = response.choices[0].message.content
                subtopics = json.loads(subtopics_text)
                
                # Ensure it's a list
                if isinstance(subtopics, dict):
                    subtopics = [subtopics]
                
                # Add IDs and validate structure
                for i, subtopic in enumerate(subtopics):
                    subtopic["id"] = f"subtopic_{i+1}"
                    subtopic.setdefault("priority", "medium")
                    subtopic.setdefault("estimated_research_time", 15)
                
                # Record token usage
                usage = response.usage
                observability_service.record_token_usage(
                    self.agent_id, "gpt-4", usage.total_tokens
                )
                
                span.set_attribute("subtopics_generated", len(subtopics))
                
                return subtopics
                
            except Exception as e:
                self.logger.error(f"Error generating subtopics: {str(e)}")
                # Return default subtopics
                return [
                    {
                        "id": "subtopic_1",
                        "title": f"Introduction to {topic}",
                        "description": f"Basic concepts and overview of {topic}",
                        "priority": "high",
                        "estimated_research_time": 15
                    },
                    {
                        "id": "subtopic_2",
                        "title": f"Advanced {topic} Concepts",
                        "description": f"Deeper exploration of {topic}",
                        "priority": "medium",
                        "estimated_research_time": 20
                    }
                ]
    
    async def _find_related_content(self, topic: str, subtopics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find related content using RAG"""
        with TracingContext("find_related_content", self.agent_id) as span:
            # Build search queries from topic and subtopics
            search_queries = [topic] + [subtopic["title"] for subtopic in subtopics]
            
            related_content = []
            
            for query in search_queries[:3]:  # Limit to prevent too many queries
                try:
                    results = await vector_db_service.search_similar_content(query, n_results=2)
                    
                    for result in results:
                        content_item = {
                            "query": query,
                            "content": result["content"],
                            "metadata": result["metadata"],
                            "relevance_score": 1.0 - result.get("distance", 0.0)
                        }
                        related_content.append(content_item)
                    
                    # Record vector DB query
                    observability_service.record_vector_db_query(query, len(results), 0.1)
                    
                except Exception as e:
                    self.logger.error(f"Error searching for related content: {str(e)}")
            
            span.set_attribute("related_content_found", len(related_content))
            return related_content
    
    async def _generate_research_queries(self, topic: str, subtopics: List[Dict[str, Any]], 
                                       related_content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate research queries for each subtopic"""
        with TracingContext("generate_research_queries", self.agent_id) as span:
            queries = []
            
            for subtopic in subtopics:
                # Create research query based on subtopic
                query = {
                    "subtopic_id": subtopic["id"],
                    "subtopic_title": subtopic["title"],
                    "research_query": f"{subtopic['title']}: {subtopic.get('description', '')}",
                    "priority": subtopic.get("priority", "medium"),
                    "estimated_time": subtopic.get("estimated_research_time", 15),
                    "related_sources": [
                        content["metadata"] for content in related_content
                        if subtopic["title"].lower() in content["content"].lower()
                    ][:2]  # Limit related sources
                }
                
                queries.append(query)
            
            span.set_attribute("research_queries_generated", len(queries))
            return queries
    
    async def _share_context_with_research_agent(self, context) -> None:
        """Share context with research agent via MCP"""
        try:
            # Subscribe research agent to this context
            mcp_registry.subscribe_to_context(context.context_id, "research_agent")
            
            # Send notification to research agent
            await self.communication.send_message(
                receiver="research_agent",
                message_type=MessageType.NOTIFICATION,
                content={
                    "type": "context_available",
                    "context_id": context.context_id,
                    "context_type": context.context_type.value,
                    "sender": self.agent_id
                },
                priority=MessagePriority.NORMAL
            )
            
            self.logger.info(f"Shared context {context.context_id} with research agent")
            
        except Exception as e:
            self.logger.error(f"Error sharing context with research agent: {str(e)}")
    
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
        if notification_type == "context_update":
            await self._handle_context_update(message)
    
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
            "communication_metrics": self.communication.broker.get_metrics()
        })
        
        return base_status
    
    async def cleanup(self) -> None:
        """Cleanup agent resources"""
        await self.communication.cleanup()
        
        # Unregister from observability
        observability_service.unregister_agent(self.agent_id)
        
        self.logger.info("Topic Breakdown Agent cleaned up")
