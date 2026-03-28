# Multi-Agent EM Roadmap Platform

A comprehensive educational multi-agent system that demonstrates advanced AI/ML engineering concepts while generating Head First/Byte Byte Go style educational content.

## 🚀 Overview

This platform implements a sophisticated multi-agent architecture using CrewAI orchestration, ChromaDB vector storage, MCP/A2A protocols, OpenTelemetry observability, and real-time monitoring. The system breaks down user topics, researches them using RAG, and generates beautiful educational HTML content.

## 🏗️ Architecture

### Multi-Agent System

1. **Topic Breakdown Agent** - Analyzes topics and breaks them into subtopics
2. **Research Agent** - Uses RAG to research subtopics and create content plans
3. **HTML Generation Agent** - Creates Head First/Byte Byte Go style HTML content
4. **Coordinator Agent** - Orchestrates workflows and manages agent coordination

### Core Technologies

- **CrewAI**: Multi-agent orchestration and coordination
- **ChromaDB**: Vector database for RAG capabilities
- **OpenTelemetry**: Distributed tracing and observability
- **Redis**: Caching and session management
- **FastAPI**: High-performance API framework
- **WebSocket**: Real-time monitoring and communication

### Communication Protocols

- **MCP (Model Context Protocol)**: Context sharing between agents
- **A2A (Agent-to-Agent)**: Direct messaging and coordination
- **RAG (Retrieval-Augmented Generation)**: Knowledge retrieval from EM Roadmap

## 🛠️ Installation

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Redis (if not using Docker)
- OpenAI API Key

### Local Development

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd swapi-ai-em
   ```

2. **Install Dependencies**
   ```bash
   # Install uv if you haven't already
   # curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Sync dependencies
   uv sync
   ```

3. **Environment Setup**
   ```bash
   # Your .env file should already have your OpenAI API key
   # If not, add it:
   # OPENAI_API_KEY=your_key_here
   ```

4. **Start Redis (Optional but Recommended)**
   ```bash
   # Install Redis if not already installed
   brew install redis  # macOS
   # or: apt-get install redis  # Linux
   
   # Start Redis
   brew services start redis
   # or: redis-server
   ```

5. **Start the Application**
   ```bash
   # Activate virtual environment
   source .venv/bin/activate
   
   # Start the application
   cd backend
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Access the Application**
   - Main API: http://localhost:8000
   - Admin Dashboard: http://localhost:8000/admin
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

### Docker Deployment

1. **Build and Run**
   ```bash
   docker-compose up -d
   ```

2. **Access Services**
   - Main Application: http://localhost:8000
   - Admin Dashboard: http://localhost:8000/admin
   - Jaeger Tracing: http://localhost:16686
   - Grafana: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090

## 📖 Usage

### API Endpoints

#### Generate Content
```bash
curl -X POST "http://localhost:8000/generate-content" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Machine Learning Fundamentals",
    "workflow_type": "standard_content_generation"
  }'
```

#### Legacy Learn Endpoint
```bash
curl "http://localhost:8000/learn?topic=Deep%20Learning"
```

#### Search Vector Database
```bash
curl -X POST "http://localhost:8000/vector-db/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "neural networks",
    "n_results": 5
  }'
```

#### System Metrics
```bash
curl "http://localhost:8000/metrics"
```

### Admin Dashboard

Visit `http://localhost:8000/admin` for real-time monitoring:
- 🤖 Agent status and performance
- 📊 System metrics and error rates
- 📝 Real-time activity logs
- 🔄 Active workflow monitoring
- 📈 Performance analytics

## 🔧 Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=your_openai_api_key

# Optional
REDIS_URL=redis://localhost:6379
OTLP_ENDPOINT=http://localhost:4317
ENVIRONMENT=development
```

### Workflow Templates

The system supports predefined workflow templates:

1. **Standard Content Generation**
   - Topic breakdown → Research → HTML generation
   - Estimated time: 4.5 minutes

2. **Parallel Research Workflow**
   - Topic breakdown → Parallel research → Batch HTML generation
   - Estimated time: 7 minutes

## 📊 Monitoring & Observability

### OpenTelemetry Integration

- **Distributed Tracing**: Complete request flow across agents
- **Metrics Collection**: Performance, token usage, error rates
- **Custom Dashboards**: Grafana visualization

### Key Metrics

- Agent performance and task completion rates
- Workflow execution times and success rates
- Vector database query performance
- Cache hit rates and response times
- System resource utilization

### Real-time Monitoring

The admin dashboard provides:
- Live agent activity streams
- Workflow progress tracking
- Error monitoring and alerting
- Performance analytics

## 🧪 Testing

### Health Check
```bash
curl "http://localhost:8000/health"
```

### Agent Status
```bash
curl "http://localhost:8000/agents/topic_breakdown_agent/status"
```

### Cache Statistics
```bash
curl "http://localhost:8000/cache/stats"
```

## 🔧 Troubleshooting

### Common Issues

**Issue 1: `onnxruntime` Platform Error**
```
Error: Distribution `onnxruntime==1.24.4` can't be installed
```
**Solution**: This is a known issue with ChromaDB dependencies on macOS x86_64. The simplified `pyproject.toml` avoids this by using minimal dependencies.

**Issue 2: Package Build Error**
```
ValueError: Unable to determine which files to ship inside the wheel
```
**Solution**: Ensure the `backend/app/__init__.py` file exists and `pyproject.toml` has the package configuration:
```toml
[tool.hatch.build.targets.wheel]
packages = ["backend"]
```

**Issue 3: Module Import Errors**
```
ModuleNotFoundError: No module named 'app'
```
**Solution**: Make sure you're running from the `backend` directory:
```bash
cd backend
uvicorn main:app --reload
```

**Issue 4: Redis Connection Error**
```
Error connecting to Redis
```
**Solution**: The app will work without Redis (just slower). To use Redis:
```bash
brew services start redis  # macOS
# or
redis-server  # Manual start
```

**Issue 5: OpenAI API Key Error**
```
AuthenticationError: Invalid API key
```
**Solution**: Check your `.env` file has the correct API key:
```bash
cat .env
# Should show: OPENAI_API_KEY=sk-...
```

### Quick Start (Minimal Setup)

If you just want to test the application quickly without all dependencies:

```bash
# 1. Install minimal dependencies
uv sync

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Start the app (from backend directory)
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 4. Visit http://localhost:8000/admin
```

**Note**: Some features (ChromaDB, OpenTelemetry, Redis caching) may not work without their respective services running, but the core application will function.

## 🎯 Educational Features

### Head First/Byte Byte Go Style

Generated content includes:
- 🎨 Visual design with modern styling
- 📱 Responsive layout and navigation
- 🧪 Interactive quizzes and exercises
- 💡 EM insights and practical examples
- 📊 Diagrams and visual explanations

### Content Structure

1. **Hero Section**: Welcome and learning objectives
2. **Main Content**: Detailed explanations with examples
3. **EM Insights**: Engineering manager perspectives
4. **Interactive Quiz**: Knowledge testing
5. **Summary**: Key takeaways and next steps

## 🔍 Advanced Concepts Demonstrated

### Multi-Agent Orchestration
- CrewAI workflow coordination
- Parallel and sequential execution
- Agent communication protocols
- Error handling and recovery

### RAG Implementation
- ChromaDB vector indexing
- Semantic search capabilities
- Context-aware content generation
- Knowledge synthesis

### MCP/A2A Protocols
- Model Context Protocol for context sharing
- Agent-to-agent messaging
- Event-driven communication
- State management

### Production Patterns
- Caching strategies with Redis
- Distributed tracing with OpenTelemetry
- Real-time monitoring with WebSockets
- Containerized deployment

## 🚀 Performance Optimization

### Caching Strategy

- **Response Caching**: API responses cached for 1 hour
- **Agent Results**: Computation results cached for 30 minutes
- **Vector Search**: Search results cached for 2 hours
- **Session Management**: User sessions cached for 24 hours

### Scalability Features

- Async/await throughout the stack
- Connection pooling for Redis
- Efficient vector database operations
- Background task processing

## 🛡️ Security Considerations

- Input validation and sanitization
- API rate limiting (implement as needed)
- Secure WebSocket connections
- Environment variable management
- Container security best practices

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests and documentation
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- **CrewAI**: Multi-agent orchestration framework
- **ChromaDB**: Vector database for semantic search
- **OpenTelemetry**: Observability framework
- **FastAPI**: Modern web framework
- **Head First**: Educational content style inspiration

## 📞 Support

For questions and support:
- Create an issue in the repository
- Check the admin dashboard for system status
- Review the logs for troubleshooting

---

**Built with ❤️ for AI/ML education and multi-agent system demonstration**