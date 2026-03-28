"""
Coordinator Agent
Orchestrates the multi-agent workflow and manages overall system coordination
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import json

from app.agents.base_agent import BaseAgent, AgentMessage
from app.core.mcp_protocol import mcp_registry, ContextType
from app.core.a2a_communication import CommunicationManager, MessageType, MessagePriority
from app.core.observability import observability_service, TracingContext


class CoordinatorAgent(BaseAgent):
    """Coordinator agent for orchestrating multi-agent workflows"""
    
    def __init__(self):
        super().__init__("coordinator_agent", "Workflow Coordinator")
        self.communication = CommunicationManager(self.agent_id)
        self.capabilities = ["workflow_orchestration", "agent_coordination", "task_management", "monitoring"]
        
        # Register message handlers
        self.communication.register_handler(MessageType.REQUEST, self._handle_request)
        self.communication.register_handler(MessageType.NOTIFICATION, self._handle_notification)
        self.communication.register_handler(MessageType.STATUS_UPDATE, self._handle_status_update)
        self.communication.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
        
        # Register with observability
        observability_service.register_agent(self.agent_id, "coordinator")
        
        # Workflow state management
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        self.workflow_templates: Dict[str, Dict[str, Any]] = {}
        
        # Agent registry
        self.agent_registry: Dict[str, Dict[str, Any]] = {
            "topic_breakdown_agent": {
                "name": "Topic Breakdown Specialist",
                "status": "inactive",
                "capabilities": ["topic_analysis", "subtopic_generation"],
                "last_heartbeat": None
            },
            "research_agent": {
                "name": "Research & Planning Specialist", 
                "status": "inactive",
                "capabilities": ["rag_research", "content_planning"],
                "last_heartbeat": None
            },
            "html_generation_agent": {
                "name": "HTML Generation Specialist",
                "status": "inactive",
                "capabilities": ["html_generation", "content_styling"],
                "last_heartbeat": None
            }
        }
        
        # Initialize workflow templates
        self._initialize_workflow_templates()
        
        # Subscribe to system-wide topics
        self.communication.subscribe_to_topic("workflow_events")
        self.communication.subscribe_to_topic("agent_status")
        self.communication.subscribe_to_topic("system_monitoring")
        
        # Start background tasks
        self.monitoring_task = asyncio.create_task(self._monitor_system())
        self.heartbeat_task = asyncio.create_task(self._send_heartbeat())
        
        self.logger.info("Coordinator Agent initialized")
    
    def _initialize_workflow_templates(self) -> None:
        """Initialize predefined workflow templates"""
        self.workflow_templates = {
            "standard_content_generation": {
                "name": "Standard Content Generation",
                "description": "Complete workflow from topic to HTML content",
                "steps": [
                    {
                        "agent": "topic_breakdown_agent",
                        "task_type": "topic_analysis",
                        "required_inputs": ["topic"],
                        "parallel": False,
                        "timeout": 60
                    },
                    {
                        "agent": "research_agent", 
                        "task_type": "research_planning",
                        "required_inputs": ["context_id"],
                        "parallel": False,
                        "timeout": 120
                    },
                    {
                        "agent": "html_generation_agent",
                        "task_type": "html_creation",
                        "required_inputs": ["context_id"],
                        "parallel": False,
                        "timeout": 90
                    }
                ],
                "total_estimated_time": 270  # 4.5 minutes
            },
            "parallel_research": {
                "name": "Parallel Research Workflow",
                "description": "Research multiple topics in parallel",
                "steps": [
                    {
                        "agent": "topic_breakdown_agent",
                        "task_type": "topic_analysis",
                        "required_inputs": ["topics"],
                        "parallel": False,
                        "timeout": 90
                    },
                    {
                        "agent": "research_agent",
                        "task_type": "parallel_research",
                        "required_inputs": ["context_id"],
                        "parallel": True,
                        "timeout": 180
                    },
                    {
                        "agent": "html_generation_agent",
                        "task_type": "batch_html_creation",
                        "required_inputs": ["context_ids"],
                        "parallel": False,
                        "timeout": 150
                    }
                ],
                "total_estimated_time": 420  # 7 minutes
            }
        }
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process coordination task"""
        with TracingContext("coordinate_workflow", self.agent_id, task_type="coordination") as span:
            try:
                workflow_type = task.get("workflow_type", "standard_content_generation")
                topic = task.get("topic", "")
                
                if not topic:
                    raise ValueError("Topic is required for workflow execution")
                
                self.logger.info(f"Starting {workflow_type} workflow for: {topic}")
                
                # Execute workflow
                result = await self._execute_workflow(workflow_type, task)
                
                self.logger.info(f"Completed {workflow_type} workflow for: {topic}")
                return result
                
            except Exception as e:
                self.logger.error(f"Error processing coordination task: {str(e)}")
                raise
    
    async def _execute_workflow(self, workflow_type: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a predefined workflow"""
        with TracingContext("execute_workflow", self.agent_id, workflow_type=workflow_type) as span:
            workflow_template = self.workflow_templates.get(workflow_type)
            if not workflow_template:
                raise ValueError(f"Unknown workflow type: {workflow_type}")
            
            # Create workflow instance
            workflow_id = f"workflow_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            workflow = {
                "id": workflow_id,
                "type": workflow_type,
                "template": workflow_template,
                "status": "running",
                "started_at": datetime.now(timezone.utc),
                "current_step": 0,
                "completed_steps": [],
                "failed_steps": [],
                "context_chain": [],
                "results": {},
                "task_data": task_data
            }
            
            self.active_workflows[workflow_id] = workflow
            
            try:
                # Execute workflow steps
                for i, step in enumerate(workflow_template["steps"]):
                    workflow["current_step"] = i
                    
                    step_result = await self._execute_workflow_step(workflow_id, step)
                    
                    if step_result["status"] == "success":
                        workflow["completed_steps"].append(i)
                        workflow["results"][f"step_{i}"] = step_result
                        
                        # Add context to chain if provided
                        if "context_id" in step_result:
                            workflow["context_chain"].append(step_result["context_id"])
                    else:
                        workflow["failed_steps"].append(i)
                        raise Exception(f"Step {i} failed: {step_result.get('error', 'Unknown error')}")
                
                # Mark workflow as completed
                workflow["status"] = "completed"
                workflow["completed_at"] = datetime.now(timezone.utc)
                
                # Broadcast completion
                await self.communication.broadcast(
                    MessageType.NOTIFICATION,
                    content={
                        "type": "workflow_completed",
                        "workflow_id": workflow_id,
                        "workflow_type": workflow_type,
                        "status": "success"
                    }
                )
                
                return {
                    "status": "success",
                    "workflow_id": workflow_id,
                    "workflow_type": workflow_type,
                    "results": workflow["results"],
                    "context_chain": workflow["context_chain"],
                    "completed_at": workflow["completed_at"].isoformat()
                }
                
            except Exception as e:
                workflow["status"] = "failed"
                workflow["failed_at"] = datetime.now(timezone.utc)
                workflow["error"] = str(e)
                
                # Broadcast failure
                await self.communication.broadcast(
                    MessageType.NOTIFICATION,
                    content={
                        "type": "workflow_failed",
                        "workflow_id": workflow_id,
                        "workflow_type": workflow_type,
                        "error": str(e)
                    }
                )
                
                raise
            
            finally:
                # Clean up old workflows (keep last 24 hours)
                await self._cleanup_old_workflows()
    
    async def _execute_workflow_step(self, workflow_id: str, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single workflow step"""
        with TracingContext("execute_workflow_step", self.agent_id, workflow_id=workflow_id) as span:
            agent_id = step["agent"]
            task_type = step["task_type"]
            required_inputs = step.get("required_inputs", [])
            timeout = step.get("timeout", 60)
            
            span.set_attributes({
                "step_agent": agent_id,
                "step_task_type": task_type,
                "step_timeout": timeout
            })
            
            # Check if agent is available
            if not await self._is_agent_available(agent_id):
                raise Exception(f"Agent {agent_id} is not available")
            
            # Prepare task data
            workflow = self.active_workflows[workflow_id]
            task_data = self._prepare_step_task_data(workflow, step, required_inputs)
            
            # Send request to agent
            try:
                result = await self.communication.send_request(
                    receiver=agent_id,
                    content=task_data,
                    timeout=timeout
                )
                
                if result and result.get("status") == "success":
                    span.set_attribute("step_status", "success")
                    return result
                else:
                    span.set_attribute("step_status", "failed")
                    error_msg = result.get("error", "Unknown error") if result else "No response"
                    self.logger.error(f"Step failed for agent {agent_id}: {error_msg}")
                    self.logger.error(f"Full result: {result}")
                    return {
                        "status": "failed",
                        "error": error_msg
                    }
                    
            except asyncio.TimeoutError:
                span.set_attribute("step_status", "timeout")
                return {
                    "status": "failed",
                    "error": f"Step timed out after {timeout} seconds"
                }
            except Exception as e:
                span.set_attribute("step_status", "error")
                return {
                    "status": "failed",
                    "error": str(e)
                }
    
    async def _is_agent_available(self, agent_id: str) -> bool:
        """Check if an agent is available"""
        agent_info = self.agent_registry.get(agent_id)
        if not agent_info:
            return False
        
        # For now, just check if agent is registered and marked as active
        # TODO: Re-enable heartbeat checking once agents implement heartbeat handlers
        return agent_info["status"] == "active"
    
    def _prepare_step_task_data(self, workflow: Dict[str, Any], step: Dict[str, Any], 
                               required_inputs: List[str]) -> Dict[str, Any]:
        """Prepare task data for a workflow step"""
        task_data = workflow["task_data"].copy()
        
        # Add context from previous steps if required
        if "context_id" in required_inputs and workflow["context_chain"]:
            task_data["context_id"] = workflow["context_chain"][-1]
        
        # Add results from previous steps
        for input_req in required_inputs:
            if input_req.startswith("step_"):
                step_num = int(input_req.split("_")[1])
                if step_num in workflow["completed_steps"]:
                    task_data[input_req] = workflow["results"].get(input_req, {})
        
        return task_data
    
    async def _monitor_system(self) -> None:
        """Background task to monitor system health"""
        while True:
            try:
                # Check agent heartbeats
                await self._check_agent_heartbeats()
                
                # Update system metrics
                await self._update_system_metrics()
                
                # Record performance snapshot
                observability_service.record_performance_snapshot()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in system monitoring: {str(e)}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _check_agent_heartbeats(self) -> None:
        """Check for recent agent heartbeats"""
        current_time = datetime.now(timezone.utc)
        
        for agent_id, agent_info in self.agent_registry.items():
            if agent_info["last_heartbeat"]:
                time_since_heartbeat = current_time - agent_info["last_heartbeat"]
                
                if time_since_heartbeat > timedelta(minutes=2):
                    if agent_info["status"] == "active":
                        agent_info["status"] = "inactive"
                        self.logger.warning(f"Agent {agent_id} marked as inactive (no heartbeat)")
                        
                        # Broadcast status change
                        await self.communication.broadcast(
                            MessageType.STATUS_UPDATE,
                            content={
                                "type": "agent_status_change",
                                "agent_id": agent_id,
                                "old_status": "active",
                                "new_status": "inactive"
                            }
                        )
    
    async def _update_system_metrics(self) -> None:
        """Update system-wide metrics"""
        # Count active workflows
        active_workflows = len([
            w for w in self.active_workflows.values()
            if w["status"] == "running"
        ])
        
        # Count active agents
        active_agents = len([
            a for a in self.agent_registry.values()
            if a["status"] == "active"
        ])
        
        # Update observability metrics
        observability_service.system_metrics.update({
            "active_workflows": active_workflows,
            "active_agents": active_agents
        })
    
    async def _send_heartbeat(self) -> None:
        """Background task to send coordinator heartbeat"""
        while True:
            try:
                status = {
                    "agent_id": self.agent_id,
                    "status": "active",
                    "active_workflows": len(self.active_workflows),
                    "registered_agents": len(self.agent_registry),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                await self.communication.send_heartbeat(status)
                await asyncio.sleep(60)  # Send heartbeat every minute
                
            except Exception as e:
                self.logger.error(f"Error sending heartbeat: {str(e)}")
                await asyncio.sleep(120)  # Wait longer on error
    
    async def _cleanup_old_workflows(self) -> None:
        """Clean up workflows older than 24 hours"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        old_workflows = [
            workflow_id for workflow_id, workflow in self.active_workflows.items()
            if workflow.get("started_at", datetime.now(timezone.utc)) < cutoff_time
        ]
        
        for workflow_id in old_workflows:
            del self.active_workflows[workflow_id]
            self.logger.info(f"Cleaned up old workflow: {workflow_id}")
    
    async def _handle_request(self, message: AgentMessage) -> None:
        """Handle incoming request messages"""
        with TracingContext("handle_request", self.agent_id, message_id=message.message_id) as span:
            try:
                task_data = message.content
                result = await self.process_task(task_data)
                
                # Send response
                await self.communication.send_response(
                    sender=self.agent_id,
                    receiver=message.sender,
                    correlation_id=message.correlation_id,
                    content=result
                )
                
            except Exception as e:
                self.logger.error(f"Error handling request: {str(e)}")
                
                # Send error response
                await self.communication.send_response(
                    sender=self.agent_id,
                    receiver=message.sender,
                    correlation_id=message.correlation_id,
                    content={
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                )
    
    async def _handle_notification(self, message: AgentMessage) -> None:
        """Handle notification messages"""
        notification_type = message.content.get("type", "")
        self.logger.info(f"Received notification: {notification_type}")
        
        # Handle different notification types
        if notification_type == "agent_heartbeat":
            await self._handle_agent_heartbeat(message)
        elif notification_type == "workflow_completed":
            await self._handle_workflow_completed(message)
        elif notification_type == "workflow_failed":
            await self._handle_workflow_failed(message)
    
    async def _handle_heartbeat(self, message: AgentMessage) -> None:
        """Handle HEARTBEAT message type"""
        sender = message.sender
        status_data = message.content
        
        if sender in self.agent_registry:
            self.agent_registry[sender]["last_heartbeat"] = datetime.now(timezone.utc)
            self.agent_registry[sender]["status"] = status_data.get("status", "active")
            
            # Update agent capabilities if provided
            if "capabilities" in status_data:
                self.agent_registry[sender]["capabilities"] = status_data["capabilities"]
            
            self.logger.debug(f"Heartbeat received from {sender}, status: {status_data.get('status', 'active')}")
    
    async def _handle_agent_heartbeat(self, message: AgentMessage) -> None:
        """Handle agent heartbeat messages (legacy notification type)"""
        sender = message.sender
        status_data = message.content
        
        if sender in self.agent_registry:
            self.agent_registry[sender]["last_heartbeat"] = datetime.now(timezone.utc)
            self.agent_registry[sender]["status"] = status_data.get("status", "unknown")
            
            # Update agent capabilities if provided
            if "capabilities" in status_data:
                self.agent_registry[sender]["capabilities"] = status_data["capabilities"]
    
    async def _handle_workflow_completed(self, message: AgentMessage) -> None:
        """Handle workflow completion notifications"""
        workflow_id = message.content.get("workflow_id")
        if workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            workflow["status"] = "completed"
            workflow["completed_at"] = datetime.now(timezone.utc)
            
            self.logger.info(f"Workflow {workflow_id} completed successfully")
    
    async def _handle_workflow_failed(self, message: AgentMessage) -> None:
        """Handle workflow failure notifications"""
        workflow_id = message.content.get("workflow_id")
        error = message.content.get("error", "Unknown error")
        
        if workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            workflow["status"] = "failed"
            workflow["failed_at"] = datetime.now(timezone.utc)
            workflow["error"] = error
            
            self.logger.error(f"Workflow {workflow_id} failed: {error}")
    
    async def _handle_status_update(self, message: AgentMessage) -> None:
        """Handle status update messages"""
        update_type = message.content.get("type", "")
        
        if update_type == "agent_status_change":
            agent_id = message.content.get("agent_id")
            new_status = message.content.get("new_status")
            
            if agent_id in self.agent_registry:
                old_status = self.agent_registry[agent_id]["status"]
                self.agent_registry[agent_id]["status"] = new_status
                
                self.logger.info(f"Agent {agent_id} status changed: {old_status} -> {new_status}")
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific workflow"""
        return self.active_workflows.get(workflow_id)
    
    async def get_all_workflows(self) -> Dict[str, Dict[str, Any]]:
        """Get all active workflows"""
        return self.active_workflows.copy()
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        base_status = await self.health_check()
        
        # Add coordinator-specific status
        base_status.update({
            "capabilities": self.capabilities,
            "active_workflows": len(self.active_workflows),
            "registered_agents": len(self.agent_registry),
            "workflow_templates": list(self.workflow_templates.keys()),
            "agent_registry": self.agent_registry,
            "communication_metrics": self.communication.broker.get_metrics()
        })
        
        return base_status
    
    async def cleanup(self) -> None:
        """Cleanup coordinator resources"""
        # Cancel background tasks
        if self.monitoring_task:
            self.monitoring_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        # Wait for tasks to complete
        try:
            await asyncio.gather(self.monitoring_task, self.heartbeat_task, return_exceptions=True)
        except Exception:
            pass  # Ignore cancellation errors
        
        await self.communication.cleanup()
        
        # Unregister from observability
        observability_service.unregister_agent(self.agent_id)
        
        self.logger.info("Coordinator Agent cleaned up")
