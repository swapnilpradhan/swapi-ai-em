"""
Monitoring Service for Real-time Agent Observation
Provides n8n-style dashboard for monitoring agent I/O, errors, and performance
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from collections import deque
import uuid

from opentelemetry import trace
from app.core.observability import observability_service


@dataclass
class AgentActivity:
    """Agent activity record"""
    timestamp: datetime
    agent_id: str
    activity_type: str  # "input", "output", "error", "status_change"
    content: Dict[str, Any]
    correlation_id: Optional[str] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class WorkflowExecution:
    """Workflow execution record"""
    workflow_id: str
    workflow_type: str
    status: str  # "running", "completed", "failed", "cancelled"
    started_at: datetime
    completed_at: Optional[datetime] = None
    current_step: int = 0
    total_steps: int = 0
    agent_sequence: List[str] = None
    results: Dict[str, Any] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.agent_sequence is None:
            self.agent_sequence = []
        if self.results is None:
            self.results = {}


class MonitoringService:
    """Real-time monitoring service for agent activities"""
    
    def __init__(self, max_activities: int = 1000, max_workflows: int = 100):
        self.max_activities = max_activities
        self.max_workflows = max_workflows
        self.tracer = trace.get_tracer(__name__)
        self.logger = logging.getLogger("monitoring")
        
        # Activity storage (rolling buffer)
        self.activities: deque = deque(maxlen=max_activities)
        self.workflows: Dict[str, WorkflowExecution] = {}
        
        # Real-time connections (WebSocket clients)
        self.active_connections: Dict[str, Any] = {}
        
        # Metrics
        self.metrics = {
            "total_activities": 0,
            "total_workflows": 0,
            "active_connections": 0,
            "errors_count": 0,
            "avg_workflow_duration": 0.0
        }
        
        # Background task (started lazily to avoid event loop issues at import time)
        self.cleanup_task = None
        
        self.logger.info("Monitoring Service initialized")
    
    def start(self) -> None:
        """Start background tasks — call from within a running event loop"""
        if self.cleanup_task is None or self.cleanup_task.done():
            try:
                self.cleanup_task = asyncio.create_task(self._cleanup_old_data())
            except RuntimeError:
                self.logger.warning("No running event loop — cleanup task deferred")
    
    async def record_agent_activity(self, agent_id: str, activity_type: str, 
                                   content: Dict[str, Any], correlation_id: str = None,
                                   duration_ms: float = None, error: str = None) -> None:
        """Record agent activity"""
        with self.tracer.start_as_current_span("monitoring.record_activity") as span:
            span.set_attributes({
                "agent.id": agent_id,
                "activity.type": activity_type,
                "activity.correlation_id": correlation_id or ""
            })
            
            activity = AgentActivity(
                timestamp=datetime.now(timezone.utc),
                agent_id=agent_id,
                activity_type=activity_type,
                content=content,
                correlation_id=correlation_id,
                duration_ms=duration_ms,
                error=error
            )
            
            # Add to activities
            self.activities.append(activity)
            self.metrics["total_activities"] += 1
            
            # Track errors
            if activity_type == "error" or error:
                self.metrics["errors_count"] += 1
            
            # Broadcast to connected clients
            await self._broadcast_activity(activity)
            
            # Update workflow if this is part of a workflow
            if correlation_id:
                await self._update_workflow_activity(correlation_id, activity)
            
            self.logger.debug(f"Recorded activity: {agent_id} - {activity_type}")
    
    async def start_workflow_monitoring(self, workflow_id: str, workflow_type: str,
                                        agent_sequence: List[str], total_steps: int) -> None:
        """Start monitoring a workflow execution"""
        with self.tracer.start_as_current_span("monitoring.start_workflow") as span:
            span.set_attributes({
                "workflow.id": workflow_id,
                "workflow.type": workflow_type,
                "workflow.steps": total_steps
            })
            
            workflow = WorkflowExecution(
                workflow_id=workflow_id,
                workflow_type=workflow_type,
                status="running",
                started_at=datetime.now(timezone.utc),
                current_step=0,
                total_steps=total_steps,
                agent_sequence=agent_sequence.copy()
            )
            
            self.workflows[workflow_id] = workflow
            self.metrics["total_workflows"] += 1
            
            # Broadcast workflow start
            await self._broadcast_workflow_event("workflow_started", workflow)
            
            self.logger.info(f"Started monitoring workflow: {workflow_id}")
    
    async def update_workflow_step(self, workflow_id: str, step_number: int, 
                                  agent_id: str, status: str = "running") -> None:
        """Update workflow step progress"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return
        
        workflow.current_step = step_number
        
        # Broadcast step update
        await self._broadcast_workflow_event("workflow_step_updated", workflow)
        
        self.logger.debug(f"Updated workflow {workflow_id} to step {step_number}")
    
    async def complete_workflow(self, workflow_id: str, results: Dict[str, Any], 
                               error: str = None) -> None:
        """Mark workflow as completed or failed"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return
        
        workflow.completed_at = datetime.now(timezone.utc)
        workflow.results = results
        workflow.error = error
        workflow.status = "failed" if error else "completed"
        
        # Update metrics
        if workflow.status == "completed":
            duration = (workflow.completed_at - workflow.started_at).total_seconds()
            self._update_average_duration(duration)
        
        # Broadcast completion
        event_type = "workflow_failed" if error else "workflow_completed"
        await self._broadcast_workflow_event(event_type, workflow)
        
        self.logger.info(f"Workflow {workflow_id} {workflow.status}")
    
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow"""
        workflow = self.workflows.get(workflow_id)
        if not workflow or workflow.status != "running":
            return False
        
        workflow.status = "cancelled"
        workflow.completed_at = datetime.now(timezone.utc)
        
        # Broadcast cancellation
        await self._broadcast_workflow_event("workflow_cancelled", workflow)
        
        self.logger.info(f"Cancelled workflow: {workflow_id}")
        return True
    
    async def get_recent_activities(self, agent_id: str = None, activity_type: str = None,
                                   limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent activities with optional filtering"""
        activities = list(self.activities)
        
        # Apply filters
        if agent_id:
            activities = [a for a in activities if a.agent_id == agent_id]
        
        if activity_type:
            activities = [a for a in activities if a.activity_type == activity_type]
        
        # Sort by timestamp (newest first) and limit
        activities.sort(key=lambda x: x.timestamp, reverse=True)
        activities = activities[:limit]
        
        # Convert to dict
        return [self._activity_to_dict(a) for a in activities]
    
    async def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get currently running workflows"""
        active_workflows = [
            workflow for workflow in self.workflows.values()
            if workflow.status == "running"
        ]
        
        return [self._workflow_to_dict(w) for w in active_workflows]
    
    async def get_workflow_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent workflow executions"""
        workflows = list(self.workflows.values())
        
        # Sort by start time (newest first) and limit
        workflows.sort(key=lambda x: x.started_at, reverse=True)
        workflows = workflows[:limit]
        
        return [self._workflow_to_dict(w) for w in workflows]
    
    async def get_agent_metrics(self, agent_id: str) -> Dict[str, Any]:
        """Get metrics for specific agent"""
        recent_activities = [
            a for a in self.activities
            if a.agent_id == agent_id and 
            a.timestamp > datetime.now(timezone.utc) - timedelta(hours=1)
        ]
        
        # Calculate metrics
        total_activities = len(recent_activities)
        error_count = len([a for a in recent_activities if a.activity_type == "error" or a.error])
        avg_duration = 0.0
        
        durations = [a.duration_ms for a in recent_activities if a.duration_ms is not None]
        if durations:
            avg_duration = sum(durations) / len(durations)
        
        # Activity breakdown
        activity_breakdown = {}
        for activity in recent_activities:
            activity_breakdown[activity.activity_type] = activity_breakdown.get(activity.activity_type, 0) + 1
        
        return {
            "agent_id": agent_id,
            "recent_activities": total_activities,
            "error_count": error_count,
            "error_rate": error_count / total_activities if total_activities > 0 else 0.0,
            "avg_duration_ms": avg_duration,
            "activity_breakdown": activity_breakdown,
            "last_activity": recent_activities[-1].timestamp.isoformat() if recent_activities else None
        }
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-wide monitoring metrics"""
        # Calculate error rate
        error_rate = (self.metrics["errors_count"] / self.metrics["total_activities"]) if self.metrics["total_activities"] > 0 else 0.0
        
        # Active workflows count
        active_workflows_count = len([
            w for w in self.workflows.values() if w.status == "running"
        ])
        
        # Recent activity rate (last hour)
        recent_activities = [
            a for a in self.activities
            if a.timestamp > datetime.now(timezone.utc) - timedelta(hours=1)
        ]
        
        return {
            "total_activities": self.metrics["total_activities"],
            "total_workflows": self.metrics["total_workflows"],
            "active_connections": self.metrics["active_connections"],
            "errors_count": self.metrics["errors_count"],
            "error_rate": error_rate,
            "avg_workflow_duration": self.metrics["avg_workflow_duration"],
            "active_workflows": active_workflows_count,
            "activities_per_hour": len(recent_activities),
            "monitoring_uptime": datetime.now(timezone.utc).isoformat()
        }
    
    async def register_connection(self, connection_id: str, websocket) -> None:
        """Register a WebSocket connection for real-time updates"""
        self.active_connections[connection_id] = websocket
        self.metrics["active_connections"] += 1
        
        self.logger.info(f"Registered connection: {connection_id}")
        
        # Send initial data
        await self._send_initial_data(connection_id, websocket)
    
    async def unregister_connection(self, connection_id: str) -> None:
        """Unregister a WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            self.metrics["active_connections"] = max(0, self.metrics["active_connections"] - 1)
            
            self.logger.info(f"Unregistered connection: {connection_id}")
    
    async def _broadcast_activity(self, activity: AgentActivity) -> None:
        """Broadcast activity to all connected clients"""
        if not self.active_connections:
            return
        
        message = {
            "type": "agent_activity",
            "data": self._activity_to_dict(activity)
        }
        
        await self._broadcast_to_all(message)
    
    async def _broadcast_workflow_event(self, event_type: str, workflow: WorkflowExecution) -> None:
        """Broadcast workflow event to all connected clients"""
        if not self.active_connections:
            return
        
        message = {
            "type": event_type,
            "data": self._workflow_to_dict(workflow)
        }
        
        await self._broadcast_to_all(message)
    
    async def _broadcast_to_all(self, message: Dict[str, Any]) -> None:
        """Broadcast message to all connected clients"""
        message_str = json.dumps(message)
        disconnected = []
        
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message_str)
            except Exception as e:
                self.logger.error(f"Error broadcasting to {connection_id}: {str(e)}")
                disconnected.append(connection_id)
        
        # Clean up disconnected clients
        for connection_id in disconnected:
            await self.unregister_connection(connection_id)
    
    async def _send_initial_data(self, connection_id: str, websocket) -> None:
        """Send initial data to newly connected client"""
        try:
            # Send recent activities
            recent_activities = await self.get_recent_activities(limit=20)
            
            # Send active workflows
            active_workflows = await self.get_active_workflows()
            
            # Send system metrics
            system_metrics = await self.get_system_metrics()
            
            initial_data = {
                "type": "initial_data",
                "data": {
                    "recent_activities": recent_activities,
                    "active_workflows": active_workflows,
                    "system_metrics": system_metrics
                }
            }
            
            await websocket.send_text(json.dumps(initial_data))
            
        except Exception as e:
            self.logger.error(f"Error sending initial data to {connection_id}: {str(e)}")
    
    async def _update_workflow_activity(self, correlation_id: str, activity: AgentActivity) -> None:
        """Update workflow based on agent activity"""
        # Find workflow that matches correlation ID
        for workflow in self.workflows.values():
            if workflow.status == "running":
                # Check if this activity matches the current agent in sequence
                if workflow.current_step < len(workflow.agent_sequence):
                    current_agent = workflow.agent_sequence[workflow.current_step]
                    if activity.agent_id == current_agent:
                        # Update workflow step progress
                        await self.update_workflow_step(
                            workflow.workflow_id,
                            workflow.current_step + (1 if activity.activity_type in ["output", "error"] else 0),
                            activity.agent_id,
                            "completed" if activity.activity_type == "output" else "running"
                        )
                        
                        # If error, mark workflow as failed
                        if activity.activity_type == "error" or activity.error:
                            await self.complete_workflow(
                                workflow.workflow_id,
                                {"error": activity.error or "Unknown error"},
                                activity.error
                            )
                        
                        break
    
    def _update_average_duration(self, duration: float) -> None:
        """Update average workflow duration"""
        if self.metrics["avg_workflow_duration"] == 0:
            self.metrics["avg_workflow_duration"] = duration
        else:
            # Simple moving average
            self.metrics["avg_workflow_duration"] = (
                self.metrics["avg_workflow_duration"] * 0.9 + duration * 0.1
            )
    
    def _activity_to_dict(self, activity: AgentActivity) -> Dict[str, Any]:
        """Convert activity to dictionary"""
        return {
            "timestamp": activity.timestamp.isoformat(),
            "agent_id": activity.agent_id,
            "activity_type": activity.activity_type,
            "content": activity.content,
            "correlation_id": activity.correlation_id,
            "duration_ms": activity.duration_ms,
            "error": activity.error
        }
    
    def _workflow_to_dict(self, workflow: WorkflowExecution) -> Dict[str, Any]:
        """Convert workflow to dictionary"""
        return {
            "workflow_id": workflow.workflow_id,
            "workflow_type": workflow.workflow_type,
            "status": workflow.status,
            "started_at": workflow.started_at.isoformat(),
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
            "current_step": workflow.current_step,
            "total_steps": workflow.total_steps,
            "agent_sequence": workflow.agent_sequence,
            "results": workflow.results,
            "error": workflow.error,
            "progress_percent": (workflow.current_step / workflow.total_steps * 100) if workflow.total_steps > 0 else 0
        }
    
    async def _cleanup_old_data(self) -> None:
        """Background task to clean up old monitoring data"""
        while True:
            try:
                # Clean up old activities (older than 24 hours)
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                
                # Remove old activities from deque
                while self.activities and self.activities[0].timestamp < cutoff_time:
                    self.activities.popleft()
                
                # Clean up completed workflows (older than 24 hours)
                old_workflows = [
                    workflow_id for workflow_id, workflow in self.workflows.items()
                    if workflow.completed_at and workflow.completed_at < cutoff_time
                ]
                
                for workflow_id in old_workflows:
                    del self.workflows[workflow_id]
                
                if old_workflows:
                    self.logger.info(f"Cleaned up {len(old_workflows)} old workflows")
                
                await asyncio.sleep(3600)  # Clean up every hour
                
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {str(e)}")
                await asyncio.sleep(3600)  # Wait longer on error
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data"""
        return {
            "system_metrics": await self.get_system_metrics(),
            "recent_activities": await self.get_recent_activities(limit=50),
            "active_workflows": await self.get_active_workflows(),
            "workflow_history": await self.get_workflow_history(limit=10),
            "agent_metrics": {
                agent_id: await self.get_agent_metrics(agent_id)
                for agent_id in ["topic_breakdown_agent", "research_agent", "html_generation_agent", "coordinator_agent"]
            }
        }
    
    async def cleanup(self) -> None:
        """Cleanup monitoring service"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for connection_id in list(self.active_connections.keys()):
            await self.unregister_connection(connection_id)
        
        self.logger.info("Monitoring Service cleaned up")


# Global monitoring service instance
monitoring_service = MonitoringService()
