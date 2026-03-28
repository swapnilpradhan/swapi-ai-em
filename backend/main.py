import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from datetime import datetime, timezone
import json
import uuid

load_dotenv()

# Import services and agents
from app.agents.topic_breakdown_agent import TopicBreakdownAgent
from app.agents.research_agent import ResearchAgent
from app.agents.html_generation_agent import HTMLGenerationAgent
from app.agents.coordinator_agent import CoordinatorAgent
from app.core.vector_db import vector_db_service
from app.services.cache_service import cache_service
from app.services.monitoring_service import monitoring_service
from app.core.observability import observability_service
from app.db.database import init_db
from app.api.generations import router as generations_router
from app.api.admin import router as admin_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Multi-Agent EM Roadmap Platform",
    description="Educational multi-agent system for generating AI/ML content",
    version="3.0.0"
)

# Register API routers
app.include_router(generations_router)
app.include_router(admin_router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request models
class GenerateContentRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500, description="Topic to generate content for")
    workflow_type: str = Field(default="standard_content_generation", description="Workflow type to use")


class VectorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    n_results: int = Field(default=5, ge=1, le=50, description="Number of results")
    content_type: str = Field(default=None, description="Optional content type filter")


# Global agent instances
agents = {}
coordinator = None


@app.on_event("startup")
async def startup_event():
    """Initialize services and agents"""
    global coordinator, agents
    
    logger.info("Starting Multi-Agent EM Platform...")
    
    # Initialize PostgreSQL tables
    try:
        await init_db()
        logger.info("PostgreSQL database initialized")
    except Exception as e:
        logger.warning(f"PostgreSQL not available, DB features disabled: {e}")
    
    # Initialize cache service
    cache_connected = await cache_service.connect()
    logger.info(f"Cache service connected: {cache_connected}")
    
    # Initialize vector database and index content
    try:
        content_dir = os.getenv("EM_ROADMAP_CONTENT_DIR", "/Users/admin/Git/em-roadmap/output")
        indexed_count = await vector_db_service.index_em_roadmap_content(content_dir)
        logger.info(f"Indexed {indexed_count} EM Roadmap files")
    except Exception as e:
        logger.error(f"Error indexing content: {str(e)}")
    
    # Initialize coordinator first
    coordinator = CoordinatorAgent()
    
    # Initialize agents
    agents["topic_breakdown_agent"] = TopicBreakdownAgent()
    agents["research_agent"] = ResearchAgent()
    agents["html_generation_agent"] = HTMLGenerationAgent()
    
    logger.info("All agents initialized")
    
    # Register agents as immediately available in coordinator
    # This bypasses the heartbeat requirement for initial availability
    for agent_id in ["topic_breakdown_agent", "research_agent", "html_generation_agent"]:
        if agent_id in coordinator.agent_registry:
            coordinator.agent_registry[agent_id]["status"] = "active"
            coordinator.agent_registry[agent_id]["last_heartbeat"] = datetime.now(timezone.utc)
            logger.info(f"Registered {agent_id} as active")
    
    # Start monitoring background tasks
    monitoring_service.start()
    
    logger.info("Multi-Agent EM Platform started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services and agents"""
    logger.info("Shutting down Multi-Agent EM Platform...")
    
    # Cleanup agents
    for agent in agents.values():
        try:
            await agent.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up agent: {str(e)}")
    
    # Cleanup coordinator
    if coordinator:
        try:
            await coordinator.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up coordinator: {str(e)}")
    
    # Cleanup services
    try:
        await cache_service.disconnect()
        await monitoring_service.cleanup()
    except Exception as e:
        logger.error(f"Error cleaning up services: {str(e)}")
    
    logger.info("Multi-Agent EM Platform shutdown complete")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    vector_db_info = None
    vector_db_error = None
    try:
        vector_db_info = vector_db_service.get_collection_stats()
    except Exception as e:
        vector_db_error = str(e)

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "cache": await cache_service.get_cache_info(),
            "vector_db": vector_db_info,
            "vector_db_error": vector_db_error,
            "monitoring": await monitoring_service.get_system_metrics(),
            "observability": observability_service.get_tracing_config()
        },
        "agents": {
            agent_id: await agent.get_status()
            for agent_id, agent in agents.items()
        },
        "coordinator": await coordinator.get_system_status() if coordinator else None
    }


@app.get("/learn")
async def learn_topic(topic: str):
    """Legacy endpoint for backward compatibility"""
    if not topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
    
    # Try to get from cache first
    cache_key = f"learn_topic:{topic}"
    cached_result = await cache_service.get_cached_response(cache_key)
    
    if cached_result:
        logger.info(f"Cache hit for topic: {topic}")
        return cached_result
    
    # Use coordinator for new workflow
    try:
        result = await coordinator.process_task({
            "workflow_type": "standard_content_generation",
            "topic": topic
        })
        
        # Cache the result
        await cache_service.cache_response(cache_key, result, ttl=3600)
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing topic: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-content")
async def generate_content(request: GenerateContentRequest):
    """Generate educational content using multi-agent workflow"""
    topic = request.topic
    workflow_type = request.workflow_type
    
    # Check cache first
    cache_key = f"generate_content:{workflow_type}:{topic}"
    cached_result = await cache_service.get_cached_response(cache_key)
    
    if cached_result:
        logger.info(f"Cache hit for content generation: {topic}")
        return cached_result
    
    try:
        result = await coordinator.process_task({
            "workflow_type": workflow_type,
            "topic": topic
        })
        
        # Cache the result
        await cache_service.cache_response(cache_key, result, ttl=3600)
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflows")
async def get_workflows():
    """Get all workflow executions"""
    return await monitoring_service.get_workflow_history()


@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get specific workflow details"""
    workflow = monitoring_service.workflows.get(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return monitoring_service._workflow_to_dict(workflow)


@app.get("/activities")
async def get_activities(agent_id: str = None, activity_type: str = None, limit: int = 50):
    """Get recent agent activities"""
    return await monitoring_service.get_recent_activities(agent_id, activity_type, limit)


@app.get("/metrics")
async def get_metrics():
    """Get system and agent metrics"""
    return await monitoring_service.get_dashboard_data()


@app.get("/agents/{agent_id}/metrics")
async def get_agent_metrics(agent_id: str):
    """Get metrics for specific agent"""
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return await monitoring_service.get_agent_metrics(agent_id)


@app.get("/agents/{agent_id}/status")
async def get_agent_status(agent_id: str):
    """Get agent status"""
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return await agents[agent_id].get_status()


@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    return await cache_service.get_cache_info()


@app.delete("/cache/clear")
async def clear_cache(prefix: str = None, admin_key: str = None):
    """Clear cache by prefix (requires ADMIN_API_KEY)"""
    expected_key = os.getenv("ADMIN_API_KEY")
    if not expected_key or admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Forbidden: valid admin_key required")
    
    if prefix:
        deleted = await cache_service.clear_cache_by_prefix(prefix)
        return {"deleted": deleted, "prefix": prefix}
    else:
        await cache_service.clear_cache_by_prefix("response")
        await cache_service.clear_cache_by_prefix("session")
        await cache_service.clear_cache_by_prefix("agent_result")
        await cache_service.clear_cache_by_prefix("context")
        return {"message": "Cache cleared for common prefixes"}


@app.get("/vector-db/stats")
async def get_vector_db_stats():
    """Get vector database statistics"""
    return vector_db_service.get_collection_stats()


@app.post("/vector-db/search")
async def search_vector_db(request: VectorSearchRequest):
    """Search vector database"""
    query = request.query
    n_results = request.n_results
    content_type = request.content_type
    
    try:
        results = await vector_db_service.search_similar_content(query, n_results, content_type)
        return {"query": query, "results": results}
    except Exception as e:
        logger.error(f"Error searching vector DB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin")
async def admin_dashboard():
    """Admin dashboard HTML page"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Agent Admin Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; }
        .header { background: #1e293b; padding: 1rem 2rem; border-bottom: 1px solid #334155; }
        .header h1 { font-size: 1.5rem; font-weight: 600; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.5rem; }
        .card h2 { font-size: 1.2rem; margin-bottom: 1rem; color: #60a5fa; }
        .metric { display: flex; justify-content: space-between; margin-bottom: 0.5rem; }
        .metric-value { font-weight: 600; }
        .activity-log { max-height: 300px; overflow-y: auto; }
        .activity-item { padding: 0.5rem 0; border-bottom: 1px solid #334155; font-size: 0.9rem; }
        .workflow-item { padding: 0.5rem 0; border-bottom: 1px solid #334155; }
        .workflow-running { color: #fbbf24; }
        .workflow-completed { color: #34d399; }
        .workflow-failed { color: #f87171; }
        .status-indicator { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.5rem; }
        .status-active { background: #34d399; }
        .status-inactive { background: #6b7280; }
        .refresh-btn { background: #3b82f6; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; margin-bottom: 1rem; }
        .refresh-btn:hover { background: #2563eb; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Multi-Agent Admin Dashboard</h1>
    </div>
    
    <div class="container">
        <button class="refresh-btn" onclick="refreshData()">🔄 Refresh</button>
        
        <div class="grid">
            <!-- System Metrics -->
            <div class="card">
                <h2>📊 System Metrics</h2>
                <div id="system-metrics">
                    <div class="metric">
                        <span>Active Workflows:</span>
                        <span class="metric-value" id="active-workflows">-</span>
                    </div>
                    <div class="metric">
                        <span>Total Activities:</span>
                        <span class="metric-value" id="total-activities">-</span>
                    </div>
                    <div class="metric">
                        <span>Error Rate:</span>
                        <span class="metric-value" id="error-rate">-</span>
                    </div>
                    <div class="metric">
                        <span>Active Connections:</span>
                        <span class="metric-value" id="active-connections">-</span>
                    </div>
                </div>
            </div>
            
            <!-- Agent Status -->
            <div class="card">
                <h2>🤖 Agent Status</h2>
                <div id="agent-status">
                    <!-- Agent status will be populated here -->
                </div>
            </div>
            
            <!-- Recent Activities -->
            <div class="card">
                <h2>📝 Recent Activities</h2>
                <div class="activity-log" id="activities-log">
                    <!-- Activities will be populated here -->
                </div>
            </div>
            
            <!-- Active Workflows -->
            <div class="card">
                <h2>🔄 Active Workflows</h2>
                <div id="workflows-log">
                    <!-- Workflows will be populated here -->
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let ws;
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
            
            ws.onclose = function() {
                setTimeout(connectWebSocket, 5000);
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
        }
        
        function handleWebSocketMessage(data) {
            if (data.type === 'initial_data') {
                updateDashboard(data.data);
            } else if (data.type === 'agent_activity') {
                addActivity(data.data);
            } else if (data.type.startsWith('workflow_')) {
                updateWorkflows();
            }
        }
        
        function updateDashboard(data) {
            // Update system metrics
            const metrics = data.system_metrics;
            document.getElementById('active-workflows').textContent = metrics.active_workflows;
            document.getElementById('total-activities').textContent = metrics.total_activities;
            document.getElementById('error-rate').textContent = (metrics.error_rate * 100).toFixed(1) + '%';
            document.getElementById('active-connections').textContent = metrics.active_connections;
            
            // Update agent status
            updateAgentStatus(data.agent_metrics);
            
            // Update activities
            updateActivities(data.recent_activities);
            
            // Update workflows
            updateWorkflowsList(data.active_workflows);
        }
        
        function updateAgentStatus(agentMetrics) {
            const container = document.getElementById('agent-status');
            container.innerHTML = '';
            
            for (const [agentId, metrics] of Object.entries(agentMetrics)) {
                const status = metrics.status === 'active' ? 'status-active' : 'status-inactive';
                const div = document.createElement('div');
                div.className = 'metric';
                div.innerHTML = `
                    <span><span class="status-indicator ${status}"></span>${agentId}:</span>
                    <span class="metric-value">${metrics.status}</span>
                `;
                container.appendChild(div);
            }
        }
        
        function updateActivities(activities) {
            const container = document.getElementById('activities-log');
            container.innerHTML = '';
            
            activities.forEach(activity => {
                const div = document.createElement('div');
                div.className = 'activity-item';
                div.innerHTML = `
                    <strong>${activity.agent_id}</strong> - ${activity.activity_type}
                    <br><small>${new Date(activity.timestamp).toLocaleTimeString()}</small>
                `;
                container.appendChild(div);
            });
        }
        
        function updateWorkflowsList(workflows) {
            const container = document.getElementById('workflows-log');
            container.innerHTML = '';
            
            if (workflows.length === 0) {
                container.innerHTML = '<div class="workflow-item">No active workflows</div>';
                return;
            }
            
            workflows.forEach(workflow => {
                const div = document.createElement('div');
                div.className = 'workflow-item';
                div.innerHTML = `
                    <span class="workflow-${workflow.status}">${workflow.status}</span>
                    <strong>${workflow.workflow_id}</strong>
                    <br><small>${workflow.workflow_type} - Step ${workflow.current_step}/${workflow.total_steps}</small>
                `;
                container.appendChild(div);
            });
        }
        
        function addActivity(activity) {
            const container = document.getElementById('activities-log');
            const div = document.createElement('div');
            div.className = 'activity-item';
            div.innerHTML = `
                <strong>${activity.agent_id}</strong> - ${activity.activity_type}
                <br><small>${new Date(activity.timestamp).toLocaleTimeString()}</small>
            `;
            
            // Add to top
            if (container.firstChild) {
                container.insertBefore(div, container.firstChild);
            } else {
                container.appendChild(div);
            }
            
            // Keep only last 20 activities
            while (container.children.length > 20) {
                container.removeChild(container.lastChild);
            }
        }
        
        function updateWorkflows() {
            fetch('/workflows')
                .then(response => response.json())
                .then(data => {
                    const activeWorkflows = data.filter(w => w.status === 'running');
                    updateWorkflowsList(activeWorkflows);
                })
                .catch(error => console.error('Error fetching workflows:', error));
        }
        
        function refreshData() {
            fetch('/metrics')
                .then(response => response.json())
                .then(data => updateDashboard(data))
                .catch(error => console.error('Error refreshing data:', error));
        }
        
        // Initialize
        connectWebSocket();
        refreshData();
        
        // Auto-refresh every 30 seconds
        setInterval(refreshData, 30000);
    </script>
</body>
</html>
    """)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time monitoring"""
    await websocket.accept()
    connection_id = str(uuid.uuid4())
    
    try:
        # Register connection
        await monitoring_service.register_connection(connection_id, websocket)
        
        # Keep connection alive
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                # Handle WebSocket messages (if needed)
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        # Unregister connection
        await monitoring_service.unregister_connection(connection_id)
