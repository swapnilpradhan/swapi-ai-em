"""
Base Agent class for multi-agent system
Provides common functionality for all agents including MCP/A2A communication
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import asyncio
import logging
from datetime import datetime, timezone

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from app.core.mcp_protocol import MCPContext


@dataclass
class AgentMessage:
    """Message structure for A2A communication"""
    sender: str
    receiver: str
    message_type: str
    content: Dict[str, Any]
    timestamp: datetime
    correlation_id: Optional[str] = None
    message_id: Optional[str] = None


class BaseAgent(ABC):
    """Base class for all agents in the multi-agent system"""
    
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.tracer = trace.get_tracer(__name__)
        self.logger = logging.getLogger(f"agent.{agent_id}")
        
        # MCP Context storage
        self.contexts: Dict[str, MCPContext] = {}
        
        # A2A message queue
        self.message_queue: asyncio.Queue = asyncio.Queue()
        
        # Agent capabilities
        self.capabilities: List[str] = []
        
        # Performance metrics
        self.metrics = {
            "tasks_completed": 0,
            "total_processing_time": 0.0,
            "errors": 0
        }
    
    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Abstract method for processing tasks"""
        pass
    
    async def send_message(self, receiver: str, message_type: str, content: Dict[str, Any]) -> None:
        """Send message to another agent (A2A communication)"""
        with self.tracer.start_as_current_span("send_message") as span:
            span.set_attributes({
                "agent.sender": self.agent_id,
                "agent.receiver": receiver,
                "message.type": message_type
            })
            
            message = AgentMessage(
                sender=self.agent_id,
                receiver=receiver,
                message_type=message_type,
                content=content,
                timestamp=datetime.now(timezone.utc),
                correlation_id=span.get_span_context().trace_id
            )
            
            # In a real implementation, this would send to a message broker
            # For now, we'll simulate direct agent communication
            self.logger.info(f"Sending message to {receiver}: {message_type}")
            
            # Store in message queue for processing
            await self.message_queue.put(message)
    
    async def receive_message(self, message: AgentMessage) -> None:
        """Receive message from another agent"""
        with self.tracer.start_as_current_span("receive_message") as span:
            span.set_attributes({
                "agent.sender": message.sender,
                "agent.receiver": self.agent_id,
                "message.type": message.message_type
            })
            
            self.logger.info(f"Received message from {message.sender}: {message.message_type}")
            
            # Process the message
            await self.handle_message(message)
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages"""
        # Default implementation - can be overridden by subclasses
        self.logger.info(f"Handling message: {message.message_type}")
    
    def create_context(self, context_id: str, content: Dict[str, Any], metadata: Dict[str, Any] = None) -> MCPContext:
        """Create MCP context"""
        context = MCPContext(
            context_id=context_id,
            agent_id=self.agent_id,
            content=content,
            metadata=metadata or {}
        )
        
        self.contexts[context_id] = context
        self.logger.info(f"Created context {context_id}")
        
        return context
    
    def get_context(self, context_id: str) -> Optional[MCPContext]:
        """Get MCP context"""
        return self.contexts.get(context_id)
    
    def update_context(self, context_id: str, content: Dict[str, Any]) -> bool:
        """Update MCP context"""
        if context_id not in self.contexts:
            return False
        
        context = self.contexts[context_id]
        context.content.update(content)
        context.version += 1
        
        self.logger.info(f"Updated context {context_id} to version {context.version}")
        return True
    
    async def share_context(self, context_id: str, target_agent: str) -> bool:
        """Share context with another agent via MCP"""
        if context_id not in self.contexts:
            return False
        
        context = self.contexts[context_id]
        
        # Send context sharing message (awaited to catch errors)
        await self.send_message(
            receiver=target_agent,
            message_type="mcp_context_share",
            content={
                "context_id": context_id,
                "context": {
                    "context_id": context.context_id,
                    "agent_id": context.agent_id,
                    "content": context.content,
                    "metadata": context.metadata,
                    "version": context.version,
                }
            }
        )
        
        return True
    
    async def execute_with_tracing(self, task_name: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with OpenTelemetry tracing"""
        with self.tracer.start_as_current_span(f"agent.{task_name}") as span:
            span.set_attributes({
                "agent.id": self.agent_id,
                "agent.name": self.name,
                "task.name": task_name
            })
            
            start_time = datetime.now(timezone.utc)
            
            try:
                result = await self.process_task(task_data)
                
                # Update metrics
                self.metrics["tasks_completed"] += 1
                processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                self.metrics["total_processing_time"] += processing_time
                
                span.set_status(Status(StatusCode.OK))
                span.set_attribute("task.duration", processing_time)
                
                return result
                
            except Exception as e:
                self.metrics["errors"] += 1
                self.logger.error(f"Error executing task {task_name}: {str(e)}")
                
                span.set_status(Status(StatusCode.ERROR, description=str(e)))
                span.record_exception(e)
                
                raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics"""
        avg_processing_time = (
            self.metrics["total_processing_time"] / self.metrics["tasks_completed"]
            if self.metrics["tasks_completed"] > 0 else 0
        )
        
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "tasks_completed": self.metrics["tasks_completed"],
            "average_processing_time": avg_processing_time,
            "errors": self.metrics["errors"],
            "capabilities": self.capabilities,
            "active_contexts": len(self.contexts)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the agent"""
        return {
            "status": "healthy",
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": self.capabilities,
            "metrics": self.get_metrics()
        }
