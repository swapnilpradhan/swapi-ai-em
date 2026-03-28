# Inter-Agent Message Monitoring Guide

## Current Monitoring Capabilities

### 🎯 **Built-in Monitoring Endpoints**

The system already has several monitoring endpoints available:

#### **1. System Metrics Dashboard**
```
GET /admin
```
- Real-time dashboard with system metrics
- Agent status overview
- Recent activities feed
- Active workflows tracking

#### **2. Metrics API**
```
GET /metrics
```
- System-wide performance metrics
- Error rates and activity counts
- Workflow duration statistics
- Agent-specific metrics

#### **3. Agent-Specific Monitoring**
```
GET /agents/{agent_id}/metrics
GET /agents/{agent_id}/status
GET /agents/{agent_id}/activities
```

#### **4. Health Check with Observability Info**
```
GET /health
```
- Service health status
- Observability configuration
- Cache and vector DB stats

---

## 🔍 **Monitoring Inter-Agent Messages**

### **Option 1: Built-in Message Logging**

The system already logs message passing through the communication layer:

```bash
# View real-time message logs
tail -f /tmp/server.log | grep -E "(message|agent|communication)"

# Filter for specific message types
tail -f /tmp/server.log | grep -E "(REQUEST|RESPONSE|NOTIFICATION|HEARTBEAT)"

# Monitor specific agent communications
tail -f /tmp/server.log | grep "topic_breakdown_agent"
```

### **Option 2: Enhanced Message Monitoring Endpoint**

Let me create a dedicated endpoint for monitoring inter-agent messages:
<tool_call>write_to_file
<arg_key>CodeContent</arg_key>
<arg_value>@app.get("/debug/messages")
async def get_message_history(
    limit: int = 100,
    agent_id: Optional[str] = None,
    message_type: Optional[str] = None
):
    """Get inter-agent message history for debugging"""
    # This would require adding message history tracking to the broker
    return {
        "message": "Message history endpoint - to be implemented",
        "current_alternatives": [
            "Check /admin dashboard for real-time monitoring",
            "Review server logs for message traces",
            "Use OpenTelemetry tracing for detailed analysis"
        ]
    }

@app.get("/debug/communication")
async def get_communication_stats():
    """Get detailed communication statistics"""
    return {
        "message_broker": {
            "total_messages": "tracked in broker metrics",
            "pending_requests": len(broker.pending_responses),
            "active_queues": len(broker.queues),
            "registered_agents": list(broker.queues.keys())
        },
        "observability": {
            "tracing_enabled": bool(os.getenv("OTLP_ENDPOINT")),
            "otel_endpoint": os.getenv("OTLP_ENDPOINT", "Not configured"),
            "local_tracing": "Enabled by default"
        }
    }
