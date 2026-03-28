"""
Observability Service with OpenTelemetry
Provides distributed tracing, metrics, and monitoring for the multi-agent system
"""

import os
import logging
import time
import asyncio
import functools
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
import json

from opentelemetry import trace, metrics, baggage
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes


@dataclass
class AgentMetrics:
    """Agent performance metrics"""
    agent_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    average_task_duration: float = 0.0
    total_task_duration: float = 0.0
    last_activity: Optional[datetime] = None
    error_rate: float = 0.0
    tokens_used: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    
    def update_task_completion(self, duration: float, success: bool = True) -> None:
        """Update task completion metrics"""
        self.last_activity = datetime.now(timezone.utc)
        
        if success:
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1
        
        self.total_task_duration += duration
        self.average_task_duration = self.total_task_duration / (self.tasks_completed + self.tasks_failed)
        
        # Update error rate
        total_tasks = self.tasks_completed + self.tasks_failed
        self.error_rate = self.tasks_failed / total_tasks if total_tasks > 0 else 0.0
    
    def update_cache_metrics(self, hit: bool) -> None:
        """Update cache metrics"""
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def update_token_usage(self, tokens: int) -> None:
        """Update token usage metrics"""
        self.tokens_used += tokens
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        if self.last_activity:
            result["last_activity"] = self.last_activity.isoformat()
        return result


class ObservabilityService:
    """Central observability service for the multi-agent system"""
    
    def __init__(self, service_name: str = "multi-agent-em"):
        self.service_name = service_name
        self.logger = logging.getLogger("observability")
        
        # Initialize OpenTelemetry
        self._setup_tracing()
        self._setup_metrics()
        
        # Agent metrics storage
        self.agent_metrics: Dict[str, AgentMetrics] = {}
        
        # System metrics
        self.system_metrics = {
            "total_requests": 0,
            "total_errors": 0,
            "active_agents": 0,
            "vector_db_queries": 0,
            "cache_operations": 0
        }
        
        # Performance tracking
        self.performance_history: List[Dict[str, Any]] = []
        
        self.logger.info("Observability service initialized")
    
    def _setup_tracing(self) -> None:
        """Setup distributed tracing"""
        # Create resource
        resource = Resource(attributes={
            ResourceAttributes.SERVICE_NAME: self.service_name,
            ResourceAttributes.SERVICE_VERSION: "1.0.0",
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.getenv("ENVIRONMENT", "development")
        })
        
        # Setup tracer provider
        tracer_provider = TracerProvider(resource=resource)
        
        # Setup OTLP exporter (only if configured)
        otlp_endpoint = os.getenv("OTLP_ENDPOINT")
        if otlp_endpoint:
            try:
                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
                span_processor = BatchSpanProcessor(otlp_exporter)
                tracer_provider.add_span_processor(span_processor)
                self.logger.info(f"OTLP trace exporter configured for {otlp_endpoint}")
            except Exception as e:
                self.logger.warning(f"Failed to setup OTLP trace exporter: {e}")
        else:
            self.logger.info("OTLP trace exporter not configured - tracing will be local only")
        
        # Set as global tracer provider
        trace.set_tracer_provider(tracer_provider)
        
        # Get tracer
        self.tracer = trace.get_tracer(__name__)
    
    def _setup_metrics(self) -> None:
        """Setup metrics collection"""
        # Setup meter provider
        otlp_endpoint = os.getenv("OTLP_ENDPOINT")
        
        if otlp_endpoint:
            try:
                metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
                metric_reader = PeriodicExportingMetricReader(
                    export_interval_millis=30000,  # 30 seconds
                    exporter=metric_exporter
                )
                self.logger.info(f"OTLP metric exporter configured for {otlp_endpoint}")
            except Exception as e:
                self.logger.warning(f"Failed to setup OTLP metric exporter: {e}")
                metric_reader = None
        else:
            self.logger.info("OTLP metric exporter not configured - metrics will be local only")
            metric_reader = None
        
        # Create meter provider with or without exporter
        if metric_reader:
            meter_provider = MeterProvider(metric_readers=[metric_reader])
        else:
            meter_provider = MeterProvider()
        
        metrics.set_meter_provider(meter_provider)
        
        # Get meter
        self.meter = metrics.get_meter(__name__)
        
        # Create instruments
        self.request_counter = self.meter.create_counter(
            "requests_total",
            description="Total number of requests"
        )
        
        self.error_counter = self.meter.create_counter(
            "errors_total",
            description="Total number of errors"
        )
        
        self.task_duration_histogram = self.meter.create_histogram(
            "task_duration_seconds",
            description="Task duration in seconds"
        )
        
        self.active_agents_gauge = self.meter.create_up_down_counter(
            "active_agents",
            description="Number of active agents"
        )
    
    def create_agent_tracer(self, agent_id: str) -> trace.Tracer:
        """Create tracer for specific agent"""
        return trace.get_tracer(f"agent.{agent_id}")
    
    def register_agent(self, agent_id: str, agent_type: str) -> None:
        """Register agent for monitoring"""
        if agent_id not in self.agent_metrics:
            self.agent_metrics[agent_id] = AgentMetrics(agent_id=agent_id)
            self.active_agents_gauge.add(1)
            self.system_metrics["active_agents"] += 1
            
            self.logger.info(f"Registered agent {agent_id} ({agent_type}) for monitoring")
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister agent from monitoring"""
        if agent_id in self.agent_metrics:
            del self.agent_metrics[agent_id]
            self.active_agents_gauge.add(-1)
            self.system_metrics["active_agents"] -= 1
            
            self.logger.info(f"Unregistered agent {agent_id} from monitoring")
    
    def record_task_start(self, agent_id: str, task_type: str, task_data: Dict[str, Any]) -> trace.Span:
        """Record task start with tracing"""
        span = self.tracer.start_span(f"task.{task_type}")
        span.set_attributes({
            "agent.id": agent_id,
            "task.type": task_type,
            "task.data_size": len(str(task_data))
        })
        
        # Update system metrics
        self.request_counter.add(1, {"agent_id": agent_id, "task_type": task_type})
        self.system_metrics["total_requests"] += 1
        
        return span
    
    def record_task_completion(self, span: trace.Span, agent_id: str, duration: float, 
                             success: bool = True, error: Optional[Exception] = None) -> None:
        """Record task completion"""
        span.set_attributes({
            "task.duration": duration,
            "task.success": success
        })
        
        if success:
            span.set_status(trace.Status(trace.StatusCode.OK))
        else:
            span.set_status(trace.Status(trace.StatusCode.ERROR, description=str(error)))
            if error:
                span.record_exception(error)
            
            # Update error metrics
            self.error_counter.add(1, {"agent_id": agent_id})
            self.system_metrics["total_errors"] += 1
        
        # Record duration histogram
        self.task_duration_histogram.record(duration, {"agent_id": agent_id})
        
        # Update agent metrics
        if agent_id in self.agent_metrics:
            self.agent_metrics[agent_id].update_task_completion(duration, success)
        
        span.end()
    
    def record_vector_db_query(self, query: str, results_count: int, duration: float) -> None:
        """Record vector database query metrics"""
        with self.tracer.start_as_current_span("vector_db.query") as span:
            span.set_attributes({
                "vector_db.query_length": len(query),
                "vector_db.results_count": results_count,
                "vector_db.duration": duration
            })
            
            self.system_metrics["vector_db_queries"] += 1
    
    def record_cache_operation(self, operation: str, hit: bool, key: str) -> None:
        """Record cache operation metrics"""
        with self.tracer.start_as_current_span("cache.operation") as span:
            span.set_attributes({
                "cache.operation": operation,
                "cache.hit": hit,
                "cache.key": key
            })
            
            self.system_metrics["cache_operations"] += 1
    
    def record_token_usage(self, agent_id: str, model: str, tokens: int, cost: float = 0.0) -> None:
        """Record token usage metrics"""
        with self.tracer.start_as_current_span("token.usage") as span:
            span.set_attributes({
                "agent.id": agent_id,
                "llm.model": model,
                "llm.tokens": tokens,
                "llm.cost": cost
            })
            
            if agent_id in self.agent_metrics:
                self.agent_metrics[agent_id].update_token_usage(tokens)
    
    def get_agent_metrics(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for specific agent"""
        if agent_id in self.agent_metrics:
            return self.agent_metrics[agent_id].to_dict()
        return None
    
    def get_all_agent_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all agents"""
        return {agent_id: metrics.to_dict() for agent_id, metrics in self.agent_metrics.items()}
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-level metrics"""
        # Calculate overall error rate
        total_requests = self.system_metrics["total_requests"]
        error_rate = (self.system_metrics["total_errors"] / total_requests 
                     if total_requests > 0 else 0.0)
        
        # Calculate cache hit rate
        cache_operations = self.system_metrics["cache_operations"]
        cache_hits = sum(metrics.cache_hits for metrics in self.agent_metrics.values())
        cache_misses = sum(metrics.cache_misses for metrics in self.agent_metrics.values())
        cache_hit_rate = (cache_hits / (cache_hits + cache_misses) 
                         if (cache_hits + cache_misses) > 0 else 0.0)
        
        return {
            **self.system_metrics,
            "error_rate": error_rate,
            "cache_hit_rate": cache_hit_rate,
            "total_tokens_used": sum(metrics.tokens_used for metrics in self.agent_metrics.values()),
            "average_task_duration": (
                sum(metrics.average_task_duration for metrics in self.agent_metrics.values()) /
                len(self.agent_metrics) if self.agent_metrics else 0.0
            )
        }
    
    def get_performance_history(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """Get performance history for the last N minutes"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        # Filter performance history
        recent_history = [
            entry for entry in self.performance_history
            if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
        ]
        
        return recent_history
    
    def record_performance_snapshot(self) -> None:
        """Record a performance snapshot"""
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_metrics": self.get_system_metrics(),
            "agent_count": len(self.agent_metrics),
            "active_agents": len([
                metrics for metrics in self.agent_metrics.values()
                if metrics.last_activity and 
                (datetime.now(timezone.utc) - metrics.last_activity).total_seconds() < 300  # Active in last 5 minutes
            ])
        }
        
        self.performance_history.append(snapshot)
        
        # Keep only last 24 hours of history
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        self.performance_history = [
            entry for entry in self.performance_history
            if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
        ]
    
    def create_health_check_span(self) -> trace.Span:
        """Create span for health check"""
        span = self.tracer.start_span("health.check")
        span.set_attributes({
            "service.name": self.service_name,
            "check.timestamp": datetime.now(timezone.utc).isoformat()
        })
        return span
    
    def get_tracing_config(self) -> Dict[str, Any]:
        """Get tracing configuration"""
        return {
            "service_name": self.service_name,
            "otel_enabled": bool(os.getenv("OTLP_ENDPOINT")),
            "otel_endpoint": os.getenv("OTLP_ENDPOINT", "not configured"),
            "registered_agents": list(self.agent_metrics.keys())
        }


# Global observability service instance
observability_service = ObservabilityService()


class TracingContext:
    """Context manager for automatic tracing"""
    
    def __init__(self, operation_name: str, agent_id: Optional[str] = None, **attributes):
        self.operation_name = operation_name
        self.agent_id = agent_id
        self.attributes = attributes
        self.span = None
        self.start_time = None
    
    def __enter__(self):
        self.span = observability_service.tracer.start_span(self.operation_name)
        self.start_time = time.time()
        
        # Set attributes
        if self.agent_id:
            self.span.set_attribute("agent.id", self.agent_id)
        
        for key, value in self.attributes.items():
            self.span.set_attribute(key, value)
        
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            duration = time.time() - self.start_time
            
            if exc_type:
                self.span.set_status(trace.Status(trace.StatusCode.ERROR, description=str(exc_val)))
                self.span.record_exception(exc_val)
            else:
                self.span.set_status(trace.Status(trace.StatusCode.OK))
            
            self.span.set_attribute("duration", duration)
            self.span.end()


def trace_operation(operation_name: str, agent_id: Optional[str] = None, **attributes):
    """Decorator for tracing operations (supports both sync and async functions)"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with TracingContext(operation_name, agent_id, **attributes):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with TracingContext(operation_name, agent_id, **attributes):
                    return func(*args, **kwargs)
            return wrapper
    return decorator
