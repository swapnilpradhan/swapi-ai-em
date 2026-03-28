"""
Cache Service with Redis
Provides caching for responses, sessions, and agent results
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta, timezone
from dataclasses import asdict

import redis.asyncio as redis
from opentelemetry import trace


class CacheService:
    """Redis-based caching service for the multi-agent system"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.tracer = trace.get_tracer(__name__)
        self.logger = logging.getLogger("cache_service")
        self.redis_client = None
        
        # Cache configuration
        self.default_ttl = 3600  # 1 hour
        self.session_ttl = 86400  # 24 hours
        self.agent_result_ttl = 1800  # 30 minutes
        
        # Cache key prefixes
        self.prefixes = {
            "response": "resp:",
            "session": "sess:",
            "agent_result": "agent:",
            "context": "ctx:",
            "vector_cache": "vec:",
            "user_data": "user:"
        }
        
        # Metrics
        self.metrics = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
    
    async def connect(self) -> bool:
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=False)
            
            # Test connection
            await self.redis_client.ping()
            
            self.logger.info(f"Connected to Redis at {self.redis_url}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {str(e)}")
            self.metrics["errors"] += 1
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("Disconnected from Redis")
    
    def _make_key(self, prefix: str, key: str) -> str:
        """Create cache key with prefix"""
        return f"{self.prefixes.get(prefix, prefix)}{key}"
    
    async def get(self, prefix: str, key: str, default: Any = None) -> Optional[Any]:
        """Get value from cache"""
        with self.tracer.start_as_current_span("cache.get") as span:
            span.set_attributes({
                "cache.prefix": prefix,
                "cache.key": key
            })
            
            if not self.redis_client:
                await self.connect()
            
            try:
                cache_key = self._make_key(prefix, key)
                value = await self.redis_client.get(cache_key)
                
                if value is not None:
                    # Deserialize value (JSON only — no pickle for security)
                    try:
                        if isinstance(value, bytes):
                            value = value.decode('utf-8')
                        deserialized_value = json.loads(value)
                        
                        self.metrics["hits"] += 1
                        span.set_attribute("cache.hit", True)
                        
                        return deserialized_value
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Return raw value if deserialization fails
                        self.metrics["hits"] += 1
                        span.set_attribute("cache.hit", True)
                        return value
                else:
                    self.metrics["misses"] += 1
                    span.set_attribute("cache.hit", False)
                    return default
                    
            except Exception as e:
                self.logger.error(f"Error getting from cache: {str(e)}")
                self.metrics["errors"] += 1
                span.record_exception(e)
                return default
    
    async def set(self, prefix: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        with self.tracer.start_as_current_span("cache.set") as span:
            span.set_attributes({
                "cache.prefix": prefix,
                "cache.key": key,
                "cache.ttl": ttl or self.default_ttl
            })
            
            if not self.redis_client:
                await self.connect()
            
            try:
                cache_key = self._make_key(prefix, key)
                
                # Serialize value (JSON only — no pickle for security)
                serialized_value = json.dumps(value, default=str).encode('utf-8')
                
                # Set with TTL
                cache_ttl = ttl or self._get_default_ttl(prefix)
                result = await self.redis_client.setex(cache_key, cache_ttl, serialized_value)
                
                self.metrics["sets"] += 1
                span.set_attribute("cache.success", bool(result))
                
                return bool(result)
                
            except Exception as e:
                self.logger.error(f"Error setting cache: {str(e)}")
                self.metrics["errors"] += 1
                span.record_exception(e)
                return False
    
    async def delete(self, prefix: str, key: str) -> bool:
        """Delete value from cache"""
        with self.tracer.start_as_current_span("cache.delete") as span:
            span.set_attributes({
                "cache.prefix": prefix,
                "cache.key": key
            })
            
            if not self.redis_client:
                await self.connect()
            
            try:
                cache_key = self._make_key(prefix, key)
                result = await self.redis_client.delete(cache_key)
                
                self.metrics["deletes"] += 1
                span.set_attribute("cache.deleted", result > 0)
                
                return result > 0
                
            except Exception as e:
                self.logger.error(f"Error deleting from cache: {str(e)}")
                self.metrics["errors"] += 1
                span.record_exception(e)
                return False
    
    async def exists(self, prefix: str, key: str) -> bool:
        """Check if key exists in cache"""
        with self.tracer.start_as_current_span("cache.exists") as span:
            span.set_attributes({
                "cache.prefix": prefix,
                "cache.key": key
            })
            
            if not self.redis_client:
                await self.connect()
            
            try:
                cache_key = self._make_key(prefix, key)
                result = await self.redis_client.exists(cache_key)
                
                span.set_attribute("cache.exists", bool(result))
                return bool(result)
                
            except Exception as e:
                self.logger.error(f"Error checking cache existence: {str(e)}")
                self.metrics["errors"] += 1
                span.record_exception(e)
                return False
    
    def _get_default_ttl(self, prefix: str) -> int:
        """Get default TTL for prefix"""
        ttl_mapping = {
            "response": self.default_ttl,
            "session": self.session_ttl,
            "agent_result": self.agent_result_ttl,
            "context": self.session_ttl,
            "vector_cache": self.default_ttl * 2,  # Longer for vector cache
            "user_data": self.session_ttl
        }
        return ttl_mapping.get(prefix, self.default_ttl)
    
    # Response caching
    async def cache_response(self, request_key: str, response: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache API response"""
        return await self.set("response", request_key, response, ttl)
    
    async def get_cached_response(self, request_key: str) -> Optional[Dict[str, Any]]:
        """Get cached API response"""
        return await self.get("response", request_key)
    
    # Session management
    async def create_session(self, session_id: str, user_data: Dict[str, Any]) -> bool:
        """Create new session"""
        session_data = {
            "session_id": session_id,
            "user_data": user_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat()
        }
        return await self.set("session", session_id, session_data)
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return await self.get("session", session_id)
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data"""
        session = await self.get_session(session_id)
        if session:
            session.update(updates)
            session["last_activity"] = datetime.now(timezone.utc).isoformat()
            return await self.set("session", session_id, session)
        return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        return await self.delete("session", session_id)
    
    # Agent result caching
    async def cache_agent_result(self, agent_id: str, task_hash: str, result: Dict[str, Any]) -> bool:
        """Cache agent computation result"""
        cache_key = f"{agent_id}:{task_hash}"
        return await self.set("agent_result", cache_key, result)
    
    async def get_cached_agent_result(self, agent_id: str, task_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached agent result"""
        cache_key = f"{agent_id}:{task_hash}"
        return await self.get("agent_result", cache_key)
    
    # Context caching
    async def cache_context(self, context_id: str, context_data: Dict[str, Any]) -> bool:
        """Cache MCP context"""
        return await self.set("context", context_id, context_data)
    
    async def get_cached_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        """Get cached MCP context"""
        return await self.get("context", context_id)
    
    # Vector search caching
    async def cache_vector_search(self, query_hash: str, search_results: List[Dict[str, Any]]) -> bool:
        """Cache vector search results"""
        return await self.set("vector_cache", query_hash, search_results)
    
    async def get_cached_vector_search(self, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached vector search results"""
        return await self.get("vector_cache", query_hash)
    
    # User data caching
    async def cache_user_data(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Cache user-specific data"""
        return await self.set("user_data", user_id, data)
    
    async def get_cached_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user data"""
        return await self.get("user_data", user_id)
    
    # Batch operations
    async def mget(self, prefix: str, keys: List[str]) -> List[Optional[Any]]:
        """Get multiple values"""
        if not self.redis_client:
            await self.connect()
        
        try:
            cache_keys = [self._make_key(prefix, key) for key in keys]
            values = await self.redis_client.mget(cache_keys)
            
            results = []
            for value in values:
                if value is not None:
                    try:
                        if isinstance(value, bytes):
                            value = value.decode('utf-8')
                        deserialized_value = json.loads(value)
                        results.append(deserialized_value)
                        self.metrics["hits"] += 1
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        results.append(value)
                        self.metrics["hits"] += 1
                else:
                    results.append(None)
                    self.metrics["misses"] += 1
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in mget: {str(e)}")
            self.metrics["errors"] += 1
            return [None] * len(keys)
    
    async def mset(self, prefix: str, key_value_pairs: List[tuple], ttl: Optional[int] = None) -> bool:
        """Set multiple values"""
        if not self.redis_client:
            await self.connect()
        
        try:
            cache_ttl = ttl or self._get_default_ttl(prefix)
            
            # Use pipeline for atomic operation
            pipe = self.redis_client.pipeline()
            
            for key, value in key_value_pairs:
                cache_key = self._make_key(prefix, key)
                
                # Serialize value (JSON only — no pickle for security)
                serialized_value = json.dumps(value, default=str).encode('utf-8')
                
                pipe.setex(cache_key, cache_ttl, serialized_value)
            
            await pipe.execute()
            
            self.metrics["sets"] += len(key_value_pairs)
            return True
            
        except Exception as e:
            self.logger.error(f"Error in mset: {str(e)}")
            self.metrics["errors"] += 1
            return False
    
    # Cache statistics and management
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get Redis cache information"""
        if not self.redis_client:
            await self.connect()
        
        try:
            info = await self.redis_client.info()
            
            return {
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "our_metrics": self.metrics.copy()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cache info: {str(e)}")
            return {"error": str(e), "our_metrics": self.metrics.copy()}
    
    async def clear_cache_by_prefix(self, prefix: str) -> int:
        """Clear all cache entries with specific prefix"""
        if not self.redis_client:
            await self.connect()
        
        try:
            prefix_pattern = self.prefixes.get(prefix, prefix) + "*"
            
            # Get all keys with prefix
            keys = await self.redis_client.keys(prefix_pattern)
            
            if keys:
                deleted = await self.redis_client.delete(*keys)
                self.logger.info(f"Cleared {deleted} cache entries with prefix {prefix}")
                return deleted
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Error clearing cache by prefix: {str(e)}")
            self.metrics["errors"] += 1
            return 0
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        if not self.redis_client:
            await self.connect()
        
        try:
            # Get all session keys
            session_pattern = self.prefixes["session"] + "*"
            session_keys = await self.redis_client.keys(session_pattern)
            
            expired_count = 0
            current_time = datetime.now(timezone.utc)
            
            for key in session_keys:
                try:
                    session_data = await self.redis_client.get(key)
                    if session_data:
                        # Deserialize and check last activity
                        if isinstance(session_data, bytes):
                            session_data = session_data.decode('utf-8')
                        session = json.loads(session_data)
                        
                        last_activity = session.get("last_activity")
                        if last_activity:
                            last_activity_time = datetime.fromisoformat(last_activity)
                            if (current_time - last_activity_time) > timedelta(hours=24):
                                # Expired session, delete it
                                await self.redis_client.delete(key)
                                expired_count += 1
                except Exception as e:
                    self.logger.error(f"Error checking session {key}: {str(e)}")
            
            if expired_count > 0:
                self.logger.info(f"Cleaned up {expired_count} expired sessions")
            
            return expired_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up expired sessions: {str(e)}")
            self.metrics["errors"] += 1
            return 0
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get cache service metrics"""
        total_requests = self.metrics["hits"] + self.metrics["misses"]
        hit_rate = (self.metrics["hits"] / total_requests) if total_requests > 0 else 0.0
        
        return {
            "hits": self.metrics["hits"],
            "misses": self.metrics["misses"],
            "sets": self.metrics["sets"],
            "deletes": self.metrics["deletes"],
            "errors": self.metrics["errors"],
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }


# Global cache service instance
cache_service = CacheService()
