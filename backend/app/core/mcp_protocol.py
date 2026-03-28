"""
Model Context Protocol (MCP) Implementation
Provides standardized context sharing between agents
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import json
import logging
from enum import Enum

from opentelemetry import trace


class ContextType(Enum):
    """Types of MCP contexts"""
    TOPIC_ANALYSIS = "topic_analysis"
    RESEARCH_PLAN = "research_plan"
    HTML_STRUCTURE = "html_structure"
    AGENT_STATE = "agent_state"
    SHARED_KNOWLEDGE = "shared_knowledge"


@dataclass
class MCPContext:
    """MCP Context structure"""
    context_id: str
    agent_id: str
    context_type: ContextType
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    version: int = 1
    created_at: datetime = None
    expires_at: Optional[datetime] = None
    access_count: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "context_id": self.context_id,
            "agent_id": self.agent_id,
            "context_type": self.context_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPContext':
        """Create from dictionary"""
        data = data.copy()
        data["context_type"] = ContextType(data["context_type"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data["expires_at"]:
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        return cls(**data)


class MCPRegistry:
    """Registry for managing MCP contexts"""
    
    def __init__(self):
        self.contexts: Dict[str, MCPContext] = {}
        self.subscriptions: Dict[str, List[str]] = {}  # context_id -> [agent_ids]
        self.tracer = trace.get_tracer(__name__)
        self.logger = logging.getLogger("mcp_registry")
    
    def register_context(self, context: MCPContext) -> bool:
        """Register a new context"""
        with self.tracer.start_as_current_span("mcp.register_context") as span:
            span.set_attributes({
                "context.id": context.context_id,
                "context.type": context.context_type.value,
                "agent.id": context.agent_id
            })
            
            if context.context_id in self.contexts:
                self.logger.warning(f"Context {context.context_id} already exists")
                return False
            
            self.contexts[context.context_id] = context
            self.logger.info(f"Registered context {context.context_id}")
            return True
    
    def get_context(self, context_id: str, requesting_agent: str) -> Optional[MCPContext]:
        """Get context with access tracking"""
        with self.tracer.start_as_current_span("mcp.get_context") as span:
            span.set_attributes({
                "context.id": context_id,
                "requesting.agent": requesting_agent
            })
            
            context = self.contexts.get(context_id)
            if not context:
                self.logger.warning(f"Context {context_id} not found")
                return None
            
            # Check if expired
            if context.expires_at and datetime.now(timezone.utc) > context.expires_at:
                self.logger.warning(f"Context {context_id} expired")
                return None
            
            # Update access count
            context.access_count += 1
            
            return context
    
    def update_context(self, context_id: str, content: Dict[str, Any], agent_id: str) -> bool:
        """Update context content"""
        with self.tracer.start_as_current_span("mcp.update_context") as span:
            span.set_attributes({
                "context.id": context_id,
                "agent.id": agent_id
            })
            
            context = self.contexts.get(context_id)
            if not context:
                self.logger.warning(f"Context {context_id} not found for update")
                return False
            
            # Only allow original agent to update
            if context.agent_id != agent_id:
                self.logger.warning(f"Agent {agent_id} not authorized to update context {context_id}")
                return False
            
            context.content.update(content)
            context.version += 1
            
            # Notify subscribers
            self._notify_subscribers(context_id, "context_updated")
            
            self.logger.info(f"Updated context {context_id} to version {context.version}")
            return True
    
    def subscribe_to_context(self, context_id: str, agent_id: str) -> bool:
        """Subscribe agent to context updates"""
        if context_id not in self.contexts:
            return False
        
        if context_id not in self.subscriptions:
            self.subscriptions[context_id] = []
        
        if agent_id not in self.subscriptions[context_id]:
            self.subscriptions[context_id].append(agent_id)
            self.logger.info(f"Agent {agent_id} subscribed to context {context_id}")
        
        return True
    
    def _notify_subscribers(self, context_id: str, event_type: str) -> None:
        """Notify subscribers of context events"""
        subscribers = self.subscriptions.get(context_id, [])
        if subscribers:
            self.logger.info(f"Notifying {len(subscribers)} subscribers of {event_type} for context {context_id}")
    
    def list_contexts(self, agent_id: str, context_type: Optional[ContextType] = None) -> List[MCPContext]:
        """List contexts accessible to agent"""
        accessible_contexts = []
        
        for context in self.contexts.values():
            # Filter by type if specified
            if context_type and context.context_type != context_type:
                continue
            
            # Check if expired
            if context.expires_at and datetime.now(timezone.utc) > context.expires_at:
                continue
            
            # Agent can access their own contexts and subscribed contexts
            if (context.agent_id == agent_id or 
                agent_id in self.subscriptions.get(context.context_id, [])):
                accessible_contexts.append(context)
        
        return accessible_contexts
    
    def delete_context(self, context_id: str, agent_id: str) -> bool:
        """Delete context"""
        context = self.contexts.get(context_id)
        if not context:
            return False
        
        # Only allow original agent to delete
        if context.agent_id != agent_id:
            return False
        
        del self.contexts[context_id]
        if context_id in self.subscriptions:
            del self.subscriptions[context_id]
        
        self.logger.info(f"Deleted context {context_id}")
        return True
    
    def cleanup_expired_contexts(self) -> int:
        """Clean up expired contexts"""
        expired_count = 0
        now = datetime.now(timezone.utc)
        
        expired_contexts = [
            cid for cid, ctx in self.contexts.items()
            if ctx.expires_at and now > ctx.expires_at
        ]
        
        for context_id in expired_contexts:
            del self.contexts[context_id]
            if context_id in self.subscriptions:
                del self.subscriptions[context_id]
            expired_count += 1
        
        if expired_count > 0:
            self.logger.info(f"Cleaned up {expired_count} expired contexts")
        
        return expired_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get MCP registry statistics"""
        now = datetime.now(timezone.utc)
        active_contexts = sum(
            1 for ctx in self.contexts.values()
            if not ctx.expires_at or ctx.expires_at > now
        )
        
        context_type_counts = {}
        for context in self.contexts.values():
            context_type_counts[context.context_type.value] = context_type_counts.get(context.context_type.value, 0) + 1
        
        return {
            "total_contexts": len(self.contexts),
            "active_contexts": active_contexts,
            "expired_contexts": len(self.contexts) - active_contexts,
            "context_type_counts": context_type_counts,
            "total_subscriptions": sum(len(subs) for subs in self.subscriptions.values())
        }


# Global MCP registry instance
mcp_registry = MCPRegistry()


def create_topic_analysis_context(
    context_id: str,
    agent_id: str,
    topic: str,
    subtopics: List[str],
    research_queries: List[str]
) -> MCPContext:
    """Create a topic analysis context"""
    return MCPContext(
        context_id=context_id,
        agent_id=agent_id,
        context_type=ContextType.TOPIC_ANALYSIS,
        content={
            "topic": topic,
            "subtopics": subtopics,
            "research_queries": research_queries,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat()
        },
        metadata={
            "purpose": "topic_breakdown_analysis",
            "complexity": len(subtopics),
            "query_count": len(research_queries)
        },
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)  # Expire after 24 hours
    )


def create_research_plan_context(
    context_id: str,
    agent_id: str,
    research_plan: Dict[str, Any],
    sources: List[str]
) -> MCPContext:
    """Create a research plan context"""
    return MCPContext(
        context_id=context_id,
        agent_id=agent_id,
        context_type=ContextType.RESEARCH_PLAN,
        content={
            "research_plan": research_plan,
            "sources": sources,
            "plan_timestamp": datetime.now(timezone.utc).isoformat()
        },
        metadata={
            "purpose": "research_planning",
            "source_count": len(sources),
            "plan_complexity": len(research_plan.get("sections", []))
        },
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12)  # Expire after 12 hours
    )


def create_html_structure_context(
    context_id: str,
    agent_id: str,
    html_structure: Dict[str, Any],
    style_guide: Dict[str, Any]
) -> MCPContext:
    """Create an HTML structure context"""
    return MCPContext(
        context_id=context_id,
        agent_id=agent_id,
        context_type=ContextType.HTML_STRUCTURE,
        content={
            "html_structure": html_structure,
            "style_guide": style_guide,
            "structure_timestamp": datetime.now(timezone.utc).isoformat()
        },
        metadata={
            "purpose": "html_generation_planning",
            "section_count": len(html_structure.get("sections", [])),
            "style_complexity": len(style_guide)
        },
        expires_at=datetime.now(timezone.utc) + timedelta(hours=6)  # Expire after 6 hours
    )
