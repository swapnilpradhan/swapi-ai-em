"""
Agent-to-Agent (A2A) Communication System
Provides direct messaging, event-driven communication, and coordination between agents
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
import asyncio
import json
import logging
import uuid
from asyncio import Queue, Event

from opentelemetry import trace

from app.db.database import AsyncSessionLocal
from app.db.models import A2AMessageRecord


class MessageType(Enum):
    """Types of A2A messages"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    BROADCAST = "broadcast"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    STATUS_UPDATE = "status_update"


class MessagePriority(Enum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class A2AMessage:
    """A2A message structure"""
    message_id: str
    sender: str
    receiver: str
    message_type: MessageType
    priority: MessagePriority
    content: Dict[str, Any]
    timestamp: Optional[datetime] = None
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type.value,
            "priority": self.priority.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'A2AMessage':
        """Create from dictionary"""
        data = data.copy()
        data["message_type"] = MessageType(data["message_type"])
        data["priority"] = MessagePriority(data["priority"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data["expires_at"]:
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if message has expired"""
        return self.expires_at and datetime.now(timezone.utc) > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if message can be retried"""
        return self.retry_count < self.max_retries


class MessageBroker:
    """Central message broker for A2A communication"""
    
    def __init__(self):
        self.queues: Dict[str, Queue] = {}  # agent_id -> message queue
        self.subscriptions: Dict[str, List[str]] = {}  # topic -> [agent_ids]
        self.message_handlers: Dict[str, Callable] = {}  # message_type -> handler
        self.pending_responses: Dict[str, Event] = {}  # correlation_id -> Event
        self.response_data: Dict[str, Any] = {}  # correlation_id -> response
        self.tracer = trace.get_tracer(__name__)
        self.logger = logging.getLogger("a2a_broker")
        
        # Metrics
        self.metrics = {
            "messages_sent": 0,
            "messages_delivered": 0,
            "messages_failed": 0,
            "broadcasts_sent": 0
        }

    async def _persist_message_best_effort(self, message: A2AMessage) -> None:
        """Persist message to PostgreSQL (best effort; never raise)."""
        try:
            async with AsyncSessionLocal() as session:
                session.add(
                    A2AMessageRecord(
                        message_id=message.message_id,
                        sender=message.sender,
                        receiver=message.receiver,
                        message_type=message.message_type.value,
                        priority=message.priority.value if message.priority else None,
                        content=message.content,
                        correlation_id=message.correlation_id,
                        timestamp=message.timestamp,
                    )
                )
                await session.commit()
        except Exception:
            # Swallow all persistence errors — messaging must keep working
            return

    def _persist_message_fire_and_forget(self, message: A2AMessage) -> None:
        """Fire-and-forget wrapper to persist a message without blocking send path."""
        try:
            asyncio.create_task(self._persist_message_best_effort(message))
        except Exception:
            # No running event loop or task creation failed
            return
    
    def register_agent(self, agent_id: str) -> Queue:
        """Register an agent with the broker"""
        if agent_id not in self.queues:
            self.queues[agent_id] = Queue()
            self.logger.info(f"Registered agent: {agent_id}")
        return self.queues[agent_id]
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent"""
        if agent_id in self.queues:
            del self.queues[agent_id]
            self.logger.info(f"Unregistered agent: {agent_id}")
    
    async def send_message(self, message: A2AMessage) -> bool:
        """Send message to specific agent"""
        with self.tracer.start_as_current_span("a2a.send_message") as span:
            span.set_attributes({
                "message.id": message.message_id,
                "message.sender": message.sender,
                "message.receiver": message.receiver,
                "message.type": message.message_type.value
            })
            
            # Check if message is expired
            if message.is_expired():
                self.logger.warning(f"Message {message.message_id} expired")
                self.metrics["messages_failed"] += 1
                return False
            
            # Check if receiver exists
            if message.receiver not in self.queues:
                self.logger.warning(f"Receiver {message.receiver} not found")
                self.metrics["messages_failed"] += 1
                return False
            
            try:
                await self.queues[message.receiver].put(message)
                self.metrics["messages_sent"] += 1
                self._persist_message_fire_and_forget(message)
                self.logger.info(f"Message {message.message_id} sent to {message.receiver}")
                return True
            except Exception as e:
                self.logger.error(f"Failed to send message {message.message_id}: {str(e)}")
                self.metrics["messages_failed"] += 1
                return False
    
    async def broadcast(self, sender: str, message_type: MessageType, content: Dict[str, Any], 
                       priority: MessagePriority = MessagePriority.NORMAL) -> int:
        """Broadcast message to all agents except sender"""
        with self.tracer.start_as_current_span("a2a.broadcast") as span:
            span.set_attributes({
                "broadcast.sender": sender,
                "broadcast.type": message_type.value
            })
            
            message = A2AMessage(
                message_id=str(uuid.uuid4()),
                sender=sender,
                receiver="broadcast",
                message_type=message_type,
                priority=priority,
                content=content
            )
            
            sent_count = 0
            for agent_id, queue in self.queues.items():
                if agent_id != sender:
                    try:
                        await queue.put(message)
                        sent_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to broadcast to {agent_id}: {str(e)}")
            
            self.metrics["broadcasts_sent"] += 1
            self._persist_message_fire_and_forget(message)
            self.logger.info(f"Broadcast sent to {sent_count} agents")
            return sent_count
    
    async def receive_message(self, agent_id: str, timeout: Optional[float] = None) -> Optional[A2AMessage]:
        """Receive message for specific agent"""
        if agent_id not in self.queues:
            return None
        
        try:
            if timeout:
                message = await asyncio.wait_for(self.queues[agent_id].get(), timeout=timeout)
            else:
                message = await self.queues[agent_id].get()
            
            self.metrics["messages_delivered"] += 1
            return message
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            self.logger.error(f"Error receiving message for {agent_id}: {str(e)}")
            return None
    
    async def send_request(self, sender: str, receiver: str, content: Dict[str, Any], 
                          timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Send request and wait for response"""
        correlation_id = str(uuid.uuid4())
        response_event = Event()
        
        # Register response handler
        self.pending_responses[correlation_id] = response_event
        
        # Create request message
        message = A2AMessage(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            message_type=MessageType.REQUEST,
            priority=MessagePriority.NORMAL,
            content=content,
            correlation_id=correlation_id,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=timeout)
        )
        
        # Send message
        success = await self.send_message(message)
        if not success:
            del self.pending_responses[correlation_id]
            return None
        
        try:
            # Wait for response
            await asyncio.wait_for(response_event.wait(), timeout=timeout)
            return self.response_data.get(correlation_id)
        except asyncio.TimeoutError:
            self.logger.warning(f"Request {correlation_id} timed out")
            return None
        finally:
            # Cleanup
            del self.pending_responses[correlation_id]
            if correlation_id in self.response_data:
                del self.response_data[correlation_id]
    
    async def send_response(self, sender: str, receiver: str, correlation_id: str, 
                           content: Dict[str, Any]) -> bool:
        """Send response to a request"""
        message = A2AMessage(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            message_type=MessageType.RESPONSE,
            priority=MessagePriority.NORMAL,
            content=content,
            correlation_id=correlation_id
        )
        
        # Store response data
        self.response_data[correlation_id] = content
        
        # Notify waiting request
        if correlation_id in self.pending_responses:
            self.pending_responses[correlation_id].set()
        
        return await self.send_message(message)
    
    def subscribe_to_topic(self, topic: str, agent_id: str) -> None:
        """Subscribe agent to topic"""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        if agent_id not in self.subscriptions[topic]:
            self.subscriptions[topic].append(agent_id)
            self.logger.info(f"Agent {agent_id} subscribed to topic {topic}")
    
    def unsubscribe_from_topic(self, topic: str, agent_id: str) -> None:
        """Unsubscribe agent from topic"""
        if topic in self.subscriptions and agent_id in self.subscriptions[topic]:
            self.subscriptions[topic].remove(agent_id)
            self.logger.info(f"Agent {agent_id} unsubscribed from topic {topic}")
    
    async def publish_to_topic(self, sender: str, topic: str, content: Dict[str, Any]) -> int:
        """Publish message to topic subscribers"""
        if topic not in self.subscriptions:
            return 0
        
        message = A2AMessage(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver="topic_subscribers",
            message_type=MessageType.NOTIFICATION,
            priority=MessagePriority.NORMAL,
            content=content
        )
        
        sent_count = 0
        for agent_id in self.subscriptions[topic]:
            if agent_id != sender and agent_id in self.queues:
                try:
                    await self.queues[agent_id].put(message)
                    sent_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to publish to {agent_id}: {str(e)}")
        
        self.logger.info(f"Published to topic {topic}: {sent_count} subscribers")
        return sent_count
    
    async def send_heartbeat(self, sender: str, status: Dict[str, Any]) -> None:
        """Send heartbeat message"""
        await self.broadcast(sender, MessageType.HEARTBEAT, status, MessagePriority.LOW)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get broker metrics"""
        return {
            "registered_agents": len(self.queues),
            "active_subscriptions": sum(len(subs) for subs in self.subscriptions.values()),
            "pending_responses": len(self.pending_responses),
            **self.metrics
        }


# Global message broker instance
message_broker = MessageBroker()


class CommunicationManager:
    """High-level communication manager for agents"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.broker = message_broker
        self.tracer = trace.get_tracer(__name__)
        self.logger = logging.getLogger(f"comm.{agent_id}")
        
        # Register with broker
        self.message_queue = self.broker.register_agent(agent_id)
        
        # Message handlers
        self.handlers: Dict[MessageType, Callable] = {}
        
        # Processing task (started lazily to avoid event loop issues at init time)
        self.processing_task = None
    
    def _ensure_processing_task(self) -> None:
        """Start message processing task if not already running"""
        if self.processing_task is None or self.processing_task.done():
            try:
                self.processing_task = asyncio.create_task(self._process_messages())
            except RuntimeError:
                self.logger.warning("No running event loop — message processing deferred")
    
    async def _process_messages(self) -> None:
        """Process incoming messages"""
        while True:
            try:
                message = await self.broker.receive_message(self.agent_id, timeout=1.0)
                if message:
                    await self._handle_message(message)
            except Exception as e:
                self.logger.error(f"Error processing messages: {str(e)}")
                await asyncio.sleep(1.0)
    
    async def _handle_message(self, message: A2AMessage) -> None:
        """Handle incoming message"""
        with self.tracer.start_as_current_span("handle_message") as span:
            span.set_attributes({
                "message.id": message.message_id,
                "message.type": message.message_type.value
            })
            
            # Check for response (only RESPONSE message types)
            if message.message_type == MessageType.RESPONSE and message.correlation_id and message.correlation_id in self.broker.pending_responses:
                self.broker.response_data[message.correlation_id] = message.content
                self.broker.pending_responses[message.correlation_id].set()
                return
            
            # Handle by message type
            handler = self.handlers.get(message.message_type)
            if handler:
                try:
                    # Convert A2AMessage to AgentMessage for handler
                    from app.agents.base_agent import AgentMessage
                    agent_message = AgentMessage(
                        sender=message.sender,
                        receiver=message.receiver,
                        message_type=message.message_type.value,
                        content=message.content,
                        timestamp=message.timestamp or datetime.now(timezone.utc),
                        correlation_id=message.correlation_id,
                        message_id=message.message_id
                    )
                    await handler(agent_message)
                except Exception as e:
                    self.logger.error(f"Error handling message {message.message_id}: {str(e)}")
                    import traceback
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                self.logger.warning(f"No handler for message type {message.message_type}")
    
    def register_handler(self, message_type: MessageType, handler: Callable) -> None:
        """Register message handler"""
        self.handlers[message_type] = handler
    
    async def send_message(self, receiver: str, message_type: MessageType, content: Dict[str, Any],
                          priority: MessagePriority = MessagePriority.NORMAL) -> bool:
        """Send message to another agent"""
        self._ensure_processing_task()
        message = A2AMessage(
            message_id=str(uuid.uuid4()),
            sender=self.agent_id,
            receiver=receiver,
            message_type=message_type,
            priority=priority,
            content=content
        )
        return await self.broker.send_message(message)
    
    async def send_request(self, receiver: str, content: Dict[str, Any], timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Send request and wait for response"""
        self._ensure_processing_task()
        return await self.broker.send_request(self.agent_id, receiver, content, timeout)
    
    async def send_response(self, sender: str, receiver: str, correlation_id: str, content: Dict[str, Any]) -> bool:
        """Send response to a request"""
        return await self.broker.send_response(sender, receiver, correlation_id, content)
    
    async def broadcast(self, message_type: MessageType, content: Dict[str, Any],
                       priority: MessagePriority = MessagePriority.NORMAL) -> int:
        """Broadcast message to all agents"""
        return await self.broker.broadcast(self.agent_id, message_type, content, priority)
    
    def subscribe_to_topic(self, topic: str) -> None:
        """Subscribe to topic"""
        self.broker.subscribe_to_topic(topic, self.agent_id)
    
    def unsubscribe_from_topic(self, topic: str) -> None:
        """Unsubscribe from topic"""
        self.broker.unsubscribe_from_topic(topic, self.agent_id)
    
    async def publish_to_topic(self, topic: str, content: Dict[str, Any]) -> int:
        """Publish to topic"""
        return await self.broker.publish_to_topic(self.agent_id, topic, content)
    
    async def send_heartbeat(self, status: Dict[str, Any]) -> None:
        """Send heartbeat"""
        await self.broker.send_heartbeat(self.agent_id, status)
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        self.broker.unregister_agent(self.agent_id)
