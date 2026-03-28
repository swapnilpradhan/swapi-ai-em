"""Tests for Base Agent"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from backend.app.agents.base_agent import BaseAgent, AgentMessage, MCPContext


class TestAgent(BaseAgent):
    """Test implementation of BaseAgent"""
    
    async def process_task(self, task):
        """Test task processing"""
        return {"status": "success", "result": "test"}


@pytest.mark.unit
class TestBaseAgent:
    """Test Base Agent functionality"""
    
    def test_agent_creation(self):
        """Test creating agent"""
        agent = TestAgent("test-agent", "Test Agent")
        
        assert agent.agent_id == "test-agent"
        assert agent.name == "Test Agent"
        assert agent.capabilities == []
        assert len(agent.contexts) == 0
    
    def test_create_context(self):
        """Test creating MCP context"""
        agent = TestAgent("test-agent", "Test Agent")
        
        context = agent.create_context(
            "ctx-1",
            {"data": "test"},
            {"source": "test"}
        )
        
        assert context.context_id == "ctx-1"
        assert context.agent_id == "test-agent"
        assert "ctx-1" in agent.contexts
    
    def test_get_context(self):
        """Test getting context"""
        agent = TestAgent("test-agent", "Test Agent")
        agent.create_context("ctx-1", {"data": "test"})
        
        context = agent.get_context("ctx-1")
        
        assert context is not None
        assert context.context_id == "ctx-1"
    
    def test_update_context(self):
        """Test updating context"""
        agent = TestAgent("test-agent", "Test Agent")
        agent.create_context("ctx-1", {"data": "test"})
        
        result = agent.update_context("ctx-1", {"new_data": "updated"})
        
        assert result is True
        context = agent.get_context("ctx-1")
        assert context.version == 2
        assert "new_data" in context.content
    
    def test_get_metrics(self):
        """Test getting agent metrics"""
        agent = TestAgent("test-agent", "Test Agent")
        agent.metrics["tasks_completed"] = 5
        agent.metrics["total_processing_time"] = 10.0
        
        metrics = agent.get_metrics()
        
        assert metrics["agent_id"] == "test-agent"
        assert metrics["tasks_completed"] == 5
        assert metrics["average_processing_time"] == 2.0
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test agent health check"""
        agent = TestAgent("test-agent", "Test Agent")
        
        health = await agent.health_check()
        
        assert health["status"] == "healthy"
        assert health["agent_id"] == "test-agent"
        assert "metrics" in health
    
    @pytest.mark.asyncio
    async def test_execute_with_tracing(self):
        """Test task execution with tracing"""
        agent = TestAgent("test-agent", "Test Agent")
        
        result = await agent.execute_with_tracing(
            "test_task",
            {"input": "test"}
        )
        
        assert result["status"] == "success"
        assert agent.metrics["tasks_completed"] == 1
    
    @pytest.mark.asyncio
    async def test_execute_with_tracing_error(self):
        """Test task execution error handling"""
        agent = TestAgent("test-agent", "Test Agent")
        
        # Override process_task to raise error
        async def failing_task(task):
            raise ValueError("Test error")
        
        agent.process_task = failing_task
        
        with pytest.raises(ValueError):
            await agent.execute_with_tracing("test_task", {})
        
        assert agent.metrics["errors"] == 1


@pytest.mark.unit
class TestAgentMessage:
    """Test Agent Message"""
    
    def test_message_creation(self):
        """Test creating agent message"""
        message = AgentMessage(
            sender="agent-1",
            receiver="agent-2",
            message_type="request",
            content={"task": "test"},
            timestamp=datetime.utcnow()
        )
        
        assert message.sender == "agent-1"
        assert message.receiver == "agent-2"
        assert message.message_type == "request"
    
    def test_message_with_correlation_id(self):
        """Test message with correlation ID"""
        message = AgentMessage(
            sender="agent-1",
            receiver="agent-2",
            message_type="response",
            content={"result": "success"},
            timestamp=datetime.utcnow(),
            correlation_id="corr-123"
        )
        
        assert message.correlation_id == "corr-123"
    
    def test_message_with_message_id(self):
        """Test message with message ID"""
        message = AgentMessage(
            sender="agent-1",
            receiver="agent-2",
            message_type="request",
            content={},
            timestamp=datetime.utcnow(),
            message_id="msg-456"
        )
        
        assert message.message_id == "msg-456"
