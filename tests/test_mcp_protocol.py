"""Tests for MCP Protocol"""
import pytest
from datetime import datetime, timedelta
from backend.app.core.mcp_protocol import (
    MCPContext, MCPRegistry, ContextType
)


@pytest.mark.unit
class TestMCPContext:
    """Test MCP Context"""
    
    def test_context_creation(self):
        """Test creating MCP context"""
        context = MCPContext(
            context_id="test-1",
            agent_id="agent-1",
            context_type=ContextType.TOPIC_ANALYSIS,
            content={"data": "test"},
            metadata={"source": "test"}
        )
        
        assert context.context_id == "test-1"
        assert context.agent_id == "agent-1"
        assert context.version == 1
        assert context.access_count == 0
        assert context.created_at is not None
    
    def test_context_to_dict(self):
        """Test context serialization"""
        context = MCPContext(
            context_id="test-1",
            agent_id="agent-1",
            context_type=ContextType.TOPIC_ANALYSIS,
            content={"data": "test"},
            metadata={"source": "test"}
        )
        
        data = context.to_dict()
        
        assert data["context_id"] == "test-1"
        assert data["context_type"] == "topic_analysis"
        assert data["content"] == {"data": "test"}
        assert "created_at" in data
    
    def test_context_from_dict(self):
        """Test context deserialization"""
        data = {
            "context_id": "test-1",
            "agent_id": "agent-1",
            "context_type": "topic_analysis",
            "content": {"data": "test"},
            "metadata": {"source": "test"},
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": None,
            "access_count": 0
        }
        
        context = MCPContext.from_dict(data)
        
        assert context.context_id == "test-1"
        assert context.context_type == ContextType.TOPIC_ANALYSIS


@pytest.mark.unit
class TestMCPRegistry:
    """Test MCP Registry"""
    
    def test_register_context(self, sample_context):
        """Test registering context"""
        registry = MCPRegistry()
        
        result = registry.register_context(sample_context)
        
        assert result is True
        assert sample_context.context_id in registry.contexts
    
    def test_register_duplicate_context(self, sample_context):
        """Test registering duplicate context fails"""
        registry = MCPRegistry()
        
        registry.register_context(sample_context)
        result = registry.register_context(sample_context)
        
        assert result is False
    
    def test_get_context(self, sample_context):
        """Test getting context"""
        registry = MCPRegistry()
        registry.register_context(sample_context)
        
        retrieved = registry.get_context(sample_context.context_id, "test_agent")
        
        assert retrieved is not None
        assert retrieved.context_id == sample_context.context_id
        assert retrieved.access_count == 1
    
    def test_get_nonexistent_context(self):
        """Test getting nonexistent context"""
        registry = MCPRegistry()
        
        result = registry.get_context("nonexistent", "test_agent")
        
        assert result is None
    
    def test_get_expired_context(self):
        """Test getting expired context"""
        registry = MCPRegistry()
        
        context = MCPContext(
            context_id="expired",
            agent_id="agent-1",
            context_type=ContextType.TOPIC_ANALYSIS,
            content={},
            metadata={},
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        
        registry.register_context(context)
        result = registry.get_context("expired", "agent-1")
        
        assert result is None
    
    def test_update_context(self, sample_context):
        """Test updating context"""
        registry = MCPRegistry()
        registry.register_context(sample_context)
        
        result = registry.update_context(
            sample_context.context_id,
            {"new_data": "updated"},
            sample_context.agent_id
        )
        
        assert result is True
        updated = registry.get_context(sample_context.context_id, sample_context.agent_id)
        assert updated.version == 2
        assert "new_data" in updated.content
    
    def test_update_context_unauthorized(self, sample_context):
        """Test updating context by unauthorized agent"""
        registry = MCPRegistry()
        registry.register_context(sample_context)
        
        result = registry.update_context(
            sample_context.context_id,
            {"new_data": "updated"},
            "different_agent"
        )
        
        assert result is False
    
    def test_subscribe_to_context(self, sample_context):
        """Test subscribing to context"""
        registry = MCPRegistry()
        registry.register_context(sample_context)
        
        result = registry.subscribe_to_context(sample_context.context_id, "subscriber_agent")
        
        assert result is True
        assert "subscriber_agent" in registry.subscriptions[sample_context.context_id]
    
    def test_list_contexts(self, sample_context):
        """Test listing contexts"""
        registry = MCPRegistry()
        registry.register_context(sample_context)
        
        contexts = registry.list_contexts(sample_context.agent_id)
        
        assert len(contexts) == 1
        assert contexts[0].context_id == sample_context.context_id
    
    def test_delete_context(self, sample_context):
        """Test deleting context"""
        registry = MCPRegistry()
        registry.register_context(sample_context)
        
        result = registry.delete_context(sample_context.context_id, sample_context.agent_id)
        
        assert result is True
        assert sample_context.context_id not in registry.contexts
    
    def test_cleanup_expired_contexts(self):
        """Test cleaning up expired contexts"""
        registry = MCPRegistry()
        
        # Add expired context
        expired = MCPContext(
            context_id="expired",
            agent_id="agent-1",
            context_type=ContextType.TOPIC_ANALYSIS,
            content={},
            metadata={},
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        
        # Add active context
        active = MCPContext(
            context_id="active",
            agent_id="agent-1",
            context_type=ContextType.TOPIC_ANALYSIS,
            content={},
            metadata={}
        )
        
        registry.register_context(expired)
        registry.register_context(active)
        
        count = registry.cleanup_expired_contexts()
        
        assert count == 1
        assert "expired" not in registry.contexts
        assert "active" in registry.contexts
    
    def test_get_statistics(self, sample_context):
        """Test getting registry statistics"""
        registry = MCPRegistry()
        registry.register_context(sample_context)
        
        stats = registry.get_statistics()
        
        assert stats["total_contexts"] == 1
        assert stats["active_contexts"] == 1
        assert "context_type_counts" in stats
