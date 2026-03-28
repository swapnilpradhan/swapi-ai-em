"""Pytest configuration and fixtures"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime
import os

# Set test environment
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["REDIS_URL"] = "redis://localhost:6379"


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    client = Mock()
    client.chat = Mock()
    client.chat.completions = Mock()
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = '{"test": "response"}'
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 100
    
    client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    return client


@pytest.fixture
def mock_redis_client():
    """Mock Redis client"""
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.setex = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=False)
    client.close = AsyncMock()
    
    return client


@pytest.fixture
def sample_task_data():
    """Sample task data for testing"""
    return {
        "topic": "Machine Learning",
        "workflow_type": "standard_content_generation",
        "context_id": "test-context-123"
    }


@pytest.fixture
def sample_context():
    """Sample MCP context"""
    from backend.app.core.mcp_protocol import MCPContext, ContextType
    
    return MCPContext(
        context_id="test-context-123",
        agent_id="test_agent",
        context_type=ContextType.TOPIC_ANALYSIS,
        content={"topic": "Machine Learning", "analysis": "test"},
        metadata={"source": "test"}
    )


@pytest.fixture
def sample_a2a_message():
    """Sample A2A message"""
    from backend.app.core.a2a_communication import A2AMessage, MessageType, MessagePriority
    
    return A2AMessage(
        message_id="msg-123",
        sender="agent_1",
        receiver="agent_2",
        message_type=MessageType.REQUEST,
        priority=MessagePriority.NORMAL,
        content={"task": "test"},
        timestamp=datetime.utcnow()
    )


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
