# Complete Inter-Agent Message Monitoring Guide

## 🔍 **Current Monitoring Options**

### **1. Built-in Dashboard (Recommended Start)**
```bash
# Access the admin dashboard
open http://localhost:8000/admin
```

**Features:**
- Real-time agent status
- System metrics
- Recent activities feed
- Active workflows tracking
- Error rate monitoring

### **2. Log-Based Message Tracing**
```bash
# Monitor all message traffic in real-time
tail -f /tmp/server.log | grep -E "(message|REQUEST|RESPONSE|NOTIFICATION)"

# Filter by specific agents
tail -f /tmp/server.log | grep "topic_breakdown_agent"
tail -f /tmp/server.log | grep "research_agent"
tail -f /tmp/server.log | grep "html_generation_agent"

# Monitor workflow steps
tail -f /tmp/server.log | grep -E "(Step [0-9]|workflow)"
```

### **3. API-Based Monitoring**
```bash
# System metrics
curl http://localhost:8000/metrics | jq

# Agent-specific metrics
curl http://localhost:8000/agents/topic_breakdown_agent/metrics | jq
curl http://localhost:8000/agents/research_agent/metrics | jq

# Recent activities
curl http://localhost:8000/agents/topic_breakdown_agent/activities | jq
```

---

## 🛠 **Setting Up OpenTelemetry Dashboard**

### **Option 1: Jaeger (Recommended for Development)**

#### **Install Jaeger**
```bash
# Using Docker (easiest)
docker run -d \
  --name jaeger \
  -p 16686:16686 \
  -p 14250:14250 \
  jaegertracing/all-in-one:latest

# Or using Homebrew (macOS)
brew install jaegertracing
jaeger-all-in-one --collector.grpc.host-port=:14250 --query.host-port=:16686
```

#### **Configure OpenTelemetry Exporter**
```bash
# Set environment variable
export OTLP_ENDPOINT=http://localhost:4317

# Or add to .env file
echo "OTLP_ENDPOINT=http://localhost:4317" >> .env
```

#### **Restart the Server**
```bash
pkill -f "uvicorn.*8000"
cd /Users/admin/Git/swapi-ai-em/backend && source ../.venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/server.log 2>&1 &
```

#### **Access Jaeger Dashboard**
```bash
open http://localhost:16686
```

### **Option 2: Grafana + Prometheus (Production Setup)**

#### **Install Prometheus**
```bash
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v ./prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

#### **Install Grafana**
```bash
docker run -d \
  --name grafana \
  -p 3000:3000 \
  grafana/grafana
```

#### **Configure OpenTelemetry for Prometheus**
```bash
export OTEL_EXPORTER_PROMETHEUS_ENDPOINT=http://localhost:9090
```

---

## 📊 **Message Flow Analysis**

### **Current Message Types**
1. **REQUEST**: Agent task requests
2. **RESPONSE**: Agent task responses
3. **NOTIFICATION**: Workflow events
4. **HEARTBEAT**: Agent health checks

### **Message Flow Patterns**
```
Coordinator → MessageBroker → Agent → MessageBroker → Coordinator
     ↓              ↓           ↓              ↓           ↓
   Workflow    Message      Task         Response    Result
   Start      Routing    Processing     Collection   Aggregation
```

### **Monitoring Key Metrics**
- **Message Latency**: Time between request and response
- **Agent Availability**: Heartbeat and health status
- **Workflow Duration**: End-to-end workflow time
- **Error Rates**: Failed messages and timeouts
- **Queue Depth**: Pending messages per agent

---

## 🚀 **Advanced Monitoring Setup**

### **1. Enable Detailed Logging**
```python
# Add to main.py or environment
import logging
logging.getLogger('a2a_broker').setLevel(logging.DEBUG)
logging.getLogger('comm.*').setLevel(logging.DEBUG)
```

### **2. Add Custom Message Tracing**
```python
# In a2a_communication.py
async def send_request(self, sender: str, receiver: str, content: Dict[str, Any], timeout: float = 30.0):
    with self.tracer.start_as_current_span("agent_request") as span:
        span.set_attributes({
            "sender": sender,
            "receiver": receiver,
            "correlation_id": correlation_id,
            "content_size": len(str(content))
        })
        
        # Existing send_request logic...
```

### **3. Real-time Message Monitoring**
```bash
# Watch message flow in real-time
watch -n 1 'curl -s http://localhost:8000/metrics | jq ".recent_activities | length"'

# Monitor specific workflow
curl -s "http://localhost:8000/activities?workflow_type=standard_content_generation" | jq
```

---

## 📱 **Dashboard Access Points**

### **Primary Dashboard**
- **URL**: `http://localhost:8000/admin`
- **Features**: Real-time metrics, agent status, activities
- **Refresh**: Auto-refreshes every 5 seconds

### **OpenTelemetry Tracing**
- **Jaeger**: `http://localhost:16686` (if configured)
- **Service Name**: `multi-agent-em-platform`
- **Trace Operations**: `handle_message`, `process_task`, `execute_workflow_step`

### **Health Check**
- **URL**: `http://localhost:8000/health`
- **Includes**: Service status, observability config, database stats

---

## 🔧 **Troubleshooting Message Issues**

### **Common Problems & Solutions**

#### **1. Messages Not Being Delivered**
```bash
# Check agent registration
curl http://localhost:8000/health | jq ".agents"

# Check message broker status
tail -f /tmp/server.log | grep "a2a_broker"
```

#### **2. Agent Timeouts**
```bash
# Check agent health
curl http://localhost:8000/agents/research_agent/status | jq

# Monitor heartbeat messages
tail -f /tmp/server.log | grep "HEARTBEAT"
```

#### **3. Workflow Failures**
```bash
# Check recent errors
curl http://localhost:8000/metrics | jq ".system_metrics.error_rate"

# Review workflow logs
tail -f /tmp/server.log | grep -E "(workflow|Step.*failed)"
```

---

## 🎯 **Recommended Monitoring Setup**

### **For Development**
1. **Built-in Dashboard** (`/admin`) - Quick overview
2. **Log Monitoring** - Detailed message tracing
3. **Jaeger** - Request tracing (optional)

### **For Production**
1. **Grafana + Prometheus** - Comprehensive metrics
2. **Jaeger** - Distributed tracing
3. **Alert Manager** - Automated notifications
4. **Log Aggregation** - Centralized logging

---

## 📝 **Quick Start Commands**

```bash
# 1. Start monitoring (in separate terminals)
# Terminal 1: Server logs
tail -f /tmp/server.log | grep -E "(message|workflow|Step)"

# Terminal 2: Dashboard
open http://localhost:8000/admin

# Terminal 3: Health checks
watch -n 5 'curl -s http://localhost:8000/health | jq ".status"'

# 2. Test with a request
curl "http://localhost:8000/learn?topic=Machine%20Learning"

# 3. Monitor the flow
# Watch the logs and dashboard for message flow
```

This setup gives you complete visibility into inter-agent communications, workflow execution, and system performance.
