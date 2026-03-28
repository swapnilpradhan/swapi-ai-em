# 🚀 Quick Start Guide

Get the Multi-Agent EM Roadmap Platform running in 5 minutes!

## ✅ Prerequisites Check

```bash
# Check Python version (need 3.12+)
python --version

# Check if uv is installed
uv --version

# Check if you have OpenAI API key in .env
cat .env | grep OPENAI_API_KEY
```

## 🏃 Quick Start (3 Steps)

### Step 1: Install Dependencies
```bash
cd /Users/admin/Git/swapi-ai-em
uv sync
```

### Step 2: Activate Environment
```bash
source .venv/bin/activate
```

### Step 3: Start the Application
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 🎯 Access Points

Once running, visit:

- **Admin Dashboard**: http://localhost:8000/admin
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 🧪 Test the API

### Generate Content
```bash
curl -X POST "http://localhost:8000/generate-content" \
  -H "Content-Type: application/json" \
  -d '{"topic": "Machine Learning Fundamentals"}'
```

### Check System Health
```bash
curl "http://localhost:8000/health"
```

### View Metrics
```bash
curl "http://localhost:8000/metrics"
```

## 📊 Admin Dashboard Features

Visit http://localhost:8000/admin to see:

- 🤖 **Agent Status** - Real-time agent health and activity
- 📈 **System Metrics** - Performance and error rates
- 📝 **Activity Logs** - Live agent I/O streams
- 🔄 **Workflows** - Active and completed workflows

## 🔧 Optional: Start Redis (for Caching)

```bash
# Install Redis (if not already installed)
brew install redis

# Start Redis
brew services start redis
# or for manual start:
redis-server
```

**Note**: The app works without Redis, but caching improves performance.

## ⚡ Common Commands

```bash
# Stop the application
# Press Ctrl+C in the terminal

# Restart with fresh cache
curl -X DELETE "http://localhost:8000/cache/clear"

# View recent activities
curl "http://localhost:8000/activities?limit=10"

# Check agent status
curl "http://localhost:8000/agents/topic_breakdown_agent/status"
```

## 🐛 Troubleshooting

### App won't start?
```bash
# Make sure you're in the backend directory
cd backend
pwd  # Should show: /Users/admin/Git/swapi-ai-em/backend

# Check if port 8000 is already in use
lsof -i :8000
```

### Module import errors?
```bash
# Ensure backend/app/__init__.py exists
ls backend/app/__init__.py

# Reinstall dependencies
uv sync
```

### Redis connection errors?
```bash
# The app will work without Redis
# To use Redis, start it:
brew services start redis
```

## 📚 Next Steps

1. **Explore the Admin Dashboard** - http://localhost:8000/admin
2. **Try the API** - http://localhost:8000/docs
3. **Generate Content** - Use the `/generate-content` endpoint
4. **Read Full Documentation** - See README.md for complete details

## 🎓 Learning Path

This platform demonstrates:
- ✅ Multi-agent orchestration with CrewAI
- ✅ RAG implementation with ChromaDB
- ✅ MCP/A2A communication protocols
- ✅ OpenTelemetry observability
- ✅ Real-time monitoring with WebSockets
- ✅ Production-ready architecture

Start by generating content for a topic you're interested in, then watch the agents work together in the admin dashboard!

---

**Need Help?** Check the full README.md or the troubleshooting section above.
