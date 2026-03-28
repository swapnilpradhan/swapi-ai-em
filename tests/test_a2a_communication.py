"""Tests for A2A Communication"""
import pytest
import asyncio
from datetime import datetime, timedelta
from backend.app.core.a2a_communication import (
    A2AMessage, MessageType, MessagePriority, MessageBroker, CommunicationManager
)


@pytest.mark.unit
class TestA2AMessage:
    """Test A2A Message"""
    
    def test_message_creation(self):
        """Test creating A2A message"""
        message = A2AMessage(
            message_id="msg-1",
            sender="agent-1",
            receiver="agent-2",
            message_type=MessageType.REQUEST,
            priority=MessagePriority.NORMAL,
            content={"task": "test"}
        )
        
        assert message.message_id == "msg-1"
        assert message.sender == "agent-1"
        assert message.timestamp is not None
        assert message.retry_count == 0
    
    def test_message_to_dict(self):
        """Test message serialization"""
        message = A2AMessage(
            message_id="msg-1",
            sender="agent-1",
            receiver="agent-2",
            message_type=MessageType.REQUEST,
            priority=MessagePriority.NORMAL,
            content={"task": "test"}
        )
        
        data = message.to_dict()
        
        assert data["message_id"] == "msg-1"
        assert data["message_type"] == "request"
        assert data["priority"] == 2
    
    def test_message_from_dict(self):
        """Test message deserialization"""
        data = {
            "message_id": "msg-1",
            "sender": "agent-1",
            "receiver": "agent-2",
            "message_type": "request",
            "priority": 2,
            "content": {"task": "test"},
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": None,
            "reply_to": None,
            "expires_at": None,
            "retry_count": 0,
            "max_retries": 3
        }
        
        message = A2AMessage.from_dict(data)
        
        assert message.message_id == "msg-1"
        assert message.message_type == MessageType.REQUEST
    
    def test_message_expiration(self):
        """Test message expiration check"""
        message = A2AMessage(
            message_id="msg-1",
            sender="agent-1",
            receiver="agent-2",
            message_type=MessageType.REQUEST,
            priority=MessagePriority.NORMAL,
            content={},
            expires_at=datetime.utcnow() - timedelta(seconds=1)
        )
        
        assert message.is_expired() is True
    
    def test_message_retry(self):
        """Test message retry capability"""
        message = A2AMessage(
            message_id="msg-1",
            sender="agent-1",
            receiver="agent-2",
            message_type=MessageType.REQUEST,
            priority=MessagePriority.NORMAL,
            content={},
            retry_count=2,
            max_retries=3
        )
        
        assert message.can_retry() is True
        
        message.retry_count = 3
        assert message.can_retry() is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessageBroker:
    """Test Message Broker"""
    
    async def test_register_agent(self):
        """Test registering agent"""
        broker = MessageBroker()
        
        queue = broker.register_agent("agent-1")
        
        assert "agent-1" in broker.queues
        assert queue is not None
    
    async def test_unregister_agent(self):
        """Test unregistering agent"""
        broker = MessageBroker()
        broker.register_agent("agent-1")
        
        broker.unregister_agent("agent-1")
        
        assert "agent-1" not in broker.queues
    
    async def test_send_message(self, sample_a2a_message):
        """Test sending message"""
        broker = MessageBroker()
        broker.register_agent("agent_2")
        
        result = await broker.send_message(sample_a2a_message)
        
        assert result is True
        assert broker.metrics["messages_sent"] == 1
    
    async def test_send_message_to_nonexistent_agent(self, sample_a2a_message):
        """Test sending message to nonexistent agent"""
        broker = MessageBroker()
        
        result = await broker.send_message(sample_a2a_message)
        
        assert result is False
        assert broker.metrics["messages_failed"] == 1
    
    async def test_send_expired_message(self):
        """Test sending expired message"""
        broker = MessageBroker()
        broker.register_agent("agent-2")
        
        message = A2AMessage(
            message_id="msg-1",
            sender="agent-1",
            receiver="agent-2",
            message_type=MessageType.REQUEST,
            priority=MessagePriority.NORMAL,
            content={},
            expires_at=datetime.utcnow() - timedelta(seconds=1)
        )
        
        result = await broker.send_message(message)
        
        assert result is False
        assert broker.metrics["messages_failed"] == 1
    
    async def test_broadcast(self):
        """Test broadcasting message"""
        broker = MessageBroker()
        broker.register_agent("agent-1")
        broker.register_agent("agent-2")
        broker.register_agent("agent-3")
        
        count = await broker.broadcast(
            "agent-1",
            MessageType.NOTIFICATION,
            {"event": "test"}
        )
        
        assert count == 2  # Sent to agent-2 and agent-3, not sender
        assert broker.metrics["broadcasts_sent"] == 1
    
    async def test_receive_message(self, sample_a2a_message):
        """Test receiving message"""
        broker = MessageBroker()
        broker.register_agent("agent_2")
        
        await broker.send_message(sample_a2a_message)
        received = await broker.receive_message("agent_2", timeout=1.0)
        
        assert received is not None
        assert received.message_id == sample_a2a_message.message_id
        assert broker.metrics["messages_delivered"] == 1
    
    async def test_receive_message_timeout(self):
        """Test receiving message with timeout"""
        broker = MessageBroker()
        broker.register_agent("agent-1")
        
        received = await broker.receive_message("agent-1", timeout=0.1)
        
        assert received is None
    
    async def test_send_request_and_response(self):
        """Test request-response pattern"""
        broker = MessageBroker()
        broker.register_agent("agent-1")
        broker.register_agent("agent-2")
        
        # Simulate agent-2 responding
        async def responder():
            await asyncio.sleep(0.1)
            message = await broker.receive_message("agent-2", timeout=1.0)
            if message:
                await broker.send_response(
                    "agent-2",
                    "agent-1",
                    message.correlation_id,
                    {"result": "success"}
                )
        
        # Start responder task
        responder_task = asyncio.create_task(responder())
        
        # Send request
        response = await broker.send_request(
            "agent-1",
            "agent-2",
            {"task": "test"},
            timeout=2.0
        )
        
        await responder_task
        
        assert response is not None
        assert response["result"] == "success"
    
    async def test_subscribe_to_topic(self):
        """Test subscribing to topic"""
        broker = MessageBroker()
        
        broker.subscribe_to_topic("test_topic", "agent-1")
        
        assert "test_topic" in broker.subscriptions
        assert "agent-1" in broker.subscriptions["test_topic"]
    
    async def test_publish_to_topic(self):
        """Test publishing to topic"""
        broker = MessageBroker()
        broker.register_agent("agent-1")
        broker.register_agent("agent-2")
        broker.subscribe_to_topic("test_topic", "agent-1")
        broker.subscribe_to_topic("test_topic", "agent-2")
        
        count = await broker.publish_to_topic(
            "publisher",
            "test_topic",
            {"event": "test"}
        )
        
        assert count == 2
    
    async def test_get_metrics(self):
        """Test getting broker metrics"""
        broker = MessageBroker()
        broker.register_agent("agent-1")
        
        metrics = broker.get_metrics()
        
        assert "registered_agents" in metrics
        assert metrics["registered_agents"] == 1
        assert "messages_sent" in metrics


@pytest.mark.unit
@pytest.mark.asyncio
class TestCommunicationManager:
    """Test Communication Manager"""
    
    async def test_manager_creation(self):
        """Test creating communication manager"""
        manager = CommunicationManager("test-agent")
        
        assert manager.agent_id == "test-agent"
        assert "test-agent" in manager.broker.queues
        
        await manager.cleanup()
    
    async def test_register_handler(self):
        """Test registering message handler"""
        manager = CommunicationManager("test-agent")
        
        async def test_handler(message):
            pass
        
        manager.register_handler(MessageType.REQUEST, test_handler)
        
        assert MessageType.REQUEST in manager.handlers
        
        await manager.cleanup()
    
    async def test_send_message(self):
        """Test sending message via manager"""
        manager1 = CommunicationManager("agent-1")
        manager2 = CommunicationManager("agent-2")
        
        result = await manager1.send_message(
            "agent-2",
            MessageType.NOTIFICATION,
            {"event": "test"}
        )
        
        assert result is True
        
        await manager1.cleanup()
        await manager2.cleanup()
    
    async def test_broadcast(self):
        """Test broadcasting via manager"""
        manager1 = CommunicationManager("agent-1")
        manager2 = CommunicationManager("agent-2")
        
        count = await manager1.broadcast(
            MessageType.NOTIFICATION,
            {"event": "test"}
        )
        
        assert count >= 1
        
        await manager1.cleanup()
        await manager2.cleanup()
