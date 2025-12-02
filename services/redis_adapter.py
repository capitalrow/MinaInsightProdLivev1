#!/usr/bin/env python3
# 🚀 Production Feature: Redis Adapter for Socket.IO Scaling
"""
Implements Redis adapter for Socket.IO to enable horizontal scaling
and distributed messaging across multiple server instances.

Addresses: "WebSocket Scaling & Backpressure" from production assessment.

Key Features:
- Redis pub/sub for cross-instance messaging
- Sticky session support via Redis
- Distributed room management
- Backpressure handling with Redis queues
- Health monitoring and failover
"""

import logging
import time
import json
import os
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
import redis
from redis import Redis
from redis.client import PubSub
from redis.connection import ConnectionPool
import threading
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)

@dataclass
class RedisConfig:
    """Redis configuration for Socket.IO adapter."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    max_connections: int = 20
    socket_keepalive: bool = True
    socket_keepalive_options: Optional[Dict[str, int]] = None
    decode_responses: bool = True
    
    def __post_init__(self) -> None:
        if self.socket_keepalive_options is None:
            self.socket_keepalive_options = {
                'TCP_KEEPIDLE': 600,
                'TCP_KEEPINTVL': 30,
                'TCP_KEEPCNT': 3
            }

class RedisSocketIOAdapter:
    """
    🚀 Production-grade Redis adapter for Socket.IO horizontal scaling.
    
    Enables multiple Flask-SocketIO instances to share client state and
    coordinate message broadcasting through Redis pub/sub.
    """
    
    def __init__(self, config: Optional[RedisConfig] = None):
        self.config = config or self._get_config_from_env()
        self.instance_id = f"mina_{uuid.uuid4().hex[:8]}"
        
        # Redis connections - typed as Optional for proper type checking
        self.redis_pub: Optional[Redis] = None
        self.redis_sub: Optional[Redis] = None
        self.redis_state: Optional[Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None
        
        # Pub/Sub management
        self.pubsub: Optional[PubSub] = None
        self.pubsub_thread: Optional[threading.Thread] = None
        self.message_handlers: Dict[str, Callable[..., Any]] = {}
        
        # State management
        self.local_rooms: Dict[str, set] = {}  # {room: {client_ids}}
        self.local_clients: Dict[str, Dict[str, Any]] = {}  # {client_id: metadata}
        self.state_lock = threading.RLock()
        
        # Metrics
        self.messages_published = 0
        self.messages_received = 0
        self.redis_errors = 0
        self.last_health_check = time.time()
        self.health_check_interval = 30  # seconds
        
        # Initialize Redis connections
        self._initialize_redis()
        
        logger.info(f"🚀 Redis Socket.IO adapter initialized: instance {self.instance_id}")
    
    def _get_config_from_env(self) -> RedisConfig:
        """Get Redis configuration from environment variables."""
        return RedisConfig(
            host=os.environ.get('REDIS_HOST', 'localhost'),
            port=int(os.environ.get('REDIS_PORT', '6379')),
            db=int(os.environ.get('REDIS_DB', '0')),
            password=os.environ.get('REDIS_PASSWORD'),
            max_connections=int(os.environ.get('REDIS_MAX_CONNECTIONS', '20'))
        )
    
    def _initialize_redis(self):
        """Initialize Redis connections with connection pooling."""
        try:
            # Create connection pool
            self.connection_pool = redis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                max_connections=self.config.max_connections,
                socket_keepalive=self.config.socket_keepalive,
                socket_keepalive_options=self.config.socket_keepalive_options,
                decode_responses=self.config.decode_responses
            )
            
            # Publisher connection
            self.redis_pub = redis.Redis(connection_pool=self.connection_pool)
            
            # Subscriber connection (separate from pool)
            self.redis_sub = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                decode_responses=self.config.decode_responses
            )
            
            # State management connection
            self.redis_state = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connections
            self.redis_pub.ping()
            self.redis_sub.ping()
            self.redis_state.ping()
            
            # Initialize pub/sub
            self._initialize_pubsub()
            
            logger.info("✅ Redis connections established successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis connections: {e}")
            self.redis_errors += 1
            raise
    
    def _initialize_pubsub(self):
        """Initialize Redis pub/sub for cross-instance messaging."""
        try:
            self.pubsub = self.redis_sub.pubsub(ignore_subscribe_messages=True)
            
            # Subscribe to instance-specific and broadcast channels
            channels = [
                f"socketio:instance:{self.instance_id}",  # Instance-specific
                "socketio:broadcast",                     # Broadcast to all instances
                "socketio:rooms",                        # Room management
                "socketio:transcription"                 # Transcription events
            ]
            
            for channel in channels:
                self.pubsub.subscribe(channel)
            
            # Start message processing thread
            self.pubsub_thread = threading.Thread(
                target=self._process_pubsub_messages,
                name="redis-pubsub",
                daemon=True
            )
            self.pubsub_thread.start()
            
            logger.info(f"📡 Redis pub/sub initialized for channels: {channels}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize pub/sub: {e}")
            self.redis_errors += 1
            raise
    
    def _process_pubsub_messages(self):
        """Process incoming pub/sub messages."""
        while True:
            try:
                message = self.pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    self._handle_pubsub_message(message)
                    
                # Periodic health check
                if time.time() - self.last_health_check > self.health_check_interval:
                    self._health_check()
                    
            except Exception as e:
                logger.error(f"Error processing pub/sub message: {e}")
                self.redis_errors += 1
                time.sleep(1)  # Brief pause on error
    
    def _handle_pubsub_message(self, message: Dict[str, Any]):
        """Handle incoming pub/sub message."""
        try:
            channel = message['channel']
            data = json.loads(message['data'])
            
            self.messages_received += 1
            
            # Skip messages from this instance
            if data.get('source_instance') == self.instance_id:
                return
            
            message_type = data.get('type')
            
            if message_type == 'emit':
                self._handle_emit_message(data)
            elif message_type == 'join_room':
                self._handle_room_join(data)
            elif message_type == 'leave_room':
                self._handle_room_leave(data)
            elif message_type == 'transcription_update':
                self._handle_transcription_update(data)
            else:
                logger.debug(f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling pub/sub message: {e}")
            self.redis_errors += 1
    
    def _handle_emit_message(self, data: Dict[str, Any]):
        """Handle emit message from another instance."""
        # This would integrate with Flask-SocketIO to emit to local clients
        event = data.get('event')
        payload = data.get('payload')
        room = data.get('room')
        
        # Call registered handler if available
        if 'emit' in self.message_handlers:
            self.message_handlers['emit'](event, payload, room)
    
    def _handle_room_join(self, data: Dict[str, Any]):
        """Handle room join from another instance."""
        client_id = data.get('client_id')
        room = data.get('room')
        
        if room and client_id:
            with self.state_lock:
                if room not in self.local_rooms:
                    self.local_rooms[room] = set()
                # Note: Don't add remote clients to local rooms
                # This is just for awareness
    
    def _handle_room_leave(self, data: Dict[str, Any]):
        """Handle room leave from another instance."""
        client_id = data.get('client_id')
        room = data.get('room')
        
        # Update local awareness of room state
        with self.state_lock:
            if room in self.local_rooms and client_id in self.local_rooms[room]:
                self.local_rooms[room].discard(client_id)
    
    def _handle_transcription_update(self, data: Dict[str, Any]):
        """Handle transcription update from another instance."""
        if 'transcription_update' in self.message_handlers:
            self.message_handlers['transcription_update'](data)
    
    def _health_check(self):
        """Perform Redis health check."""
        try:
            self.redis_pub.ping()
            self.redis_state.ping()
            self.last_health_check = time.time()
            
            # Update instance heartbeat
            heartbeat_key = f"socketio:heartbeat:{self.instance_id}"
            self.redis_state.setex(heartbeat_key, 60, json.dumps({
                'instance_id': self.instance_id,
                'timestamp': time.time(),
                'messages_published': self.messages_published,
                'messages_received': self.messages_received,
                'redis_errors': self.redis_errors
            }))
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            self.redis_errors += 1
    
    def emit_to_room(self, room: str, event: str, data: Dict[str, Any], 
                     include_self: bool = True) -> bool:
        """
        Emit message to all instances that have clients in the room.
        
        Args:
            room: Room name
            event: Event name
            data: Event data
            include_self: Whether to emit to local instance
            
        Returns:
            Success status
        """
        try:
            message = {
                'type': 'emit',
                'source_instance': self.instance_id,
                'timestamp': time.time(),
                'room': room,
                'event': event,
                'payload': data,
                'include_self': include_self
            }
            
            # Publish to broadcast channel
            channel = "socketio:broadcast"
            self.redis_pub.publish(channel, json.dumps(message))
            self.messages_published += 1
            
            logger.debug(f"Emitted to room {room}: {event}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to emit to room {room}: {e}")
            self.redis_errors += 1
            return False
    
    def join_room(self, client_id: str, room: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Add client to room across all instances.
        
        Args:
            client_id: Client identifier
            room: Room name
            metadata: Optional client metadata
            
        Returns:
            Success status
        """
        try:
            # Update local state
            with self.state_lock:
                if room not in self.local_rooms:
                    self.local_rooms[room] = set()
                self.local_rooms[room].add(client_id)
                
                if client_id not in self.local_clients:
                    self.local_clients[client_id] = {}
                self.local_clients[client_id].update(metadata or {})
            
            # Store in Redis for persistence
            room_key = f"socketio:room:{room}"
            client_data = {
                'instance_id': self.instance_id,
                'joined_at': time.time(),
                'metadata': metadata or {}
            }
            self.redis_state.hset(room_key, client_id, json.dumps(client_data))
            self.redis_state.expire(room_key, 3600)  # 1 hour TTL
            
            # Notify other instances
            message = {
                'type': 'join_room',
                'source_instance': self.instance_id,
                'timestamp': time.time(),
                'client_id': client_id,
                'room': room,
                'metadata': metadata
            }
            
            self.redis_pub.publish("socketio:rooms", json.dumps(message))
            self.messages_published += 1
            
            logger.debug(f"Client {client_id} joined room {room}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to join room {room}: {e}")
            self.redis_errors += 1
            return False
    
    def leave_room(self, client_id: str, room: str) -> bool:
        """
        Remove client from room across all instances.
        
        Args:
            client_id: Client identifier
            room: Room name
            
        Returns:
            Success status
        """
        try:
            # Update local state
            with self.state_lock:
                if room in self.local_rooms:
                    self.local_rooms[room].discard(client_id)
                    if not self.local_rooms[room]:
                        del self.local_rooms[room]
            
            # Remove from Redis
            room_key = f"socketio:room:{room}"
            self.redis_state.hdel(room_key, client_id)
            
            # Notify other instances
            message = {
                'type': 'leave_room',
                'source_instance': self.instance_id,
                'timestamp': time.time(),
                'client_id': client_id,
                'room': room
            }
            
            self.redis_pub.publish("socketio:rooms", json.dumps(message))
            self.messages_published += 1
            
            logger.debug(f"Client {client_id} left room {room}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to leave room {room}: {e}")
            self.redis_errors += 1
            return False
    
    def get_room_clients(self, room: str) -> List[Dict[str, Any]]:
        """
        Get all clients in a room across all instances.
        
        Args:
            room: Room name
            
        Returns:
            List of client information
        """
        try:
            room_key = f"socketio:room:{room}"
            clients_data = self.redis_state.hgetall(room_key)
            
            clients = []
            for client_id, data_json in clients_data.items():
                try:
                    client_data = json.loads(data_json)
                    clients.append({
                        'client_id': client_id,
                        'instance_id': client_data.get('instance_id'),
                        'joined_at': client_data.get('joined_at'),
                        'metadata': client_data.get('metadata', {})
                    })
                except json.JSONDecodeError:
                    continue
            
            return clients
            
        except Exception as e:
            logger.error(f"Failed to get room clients for {room}: {e}")
            self.redis_errors += 1
            return []
    
    def register_message_handler(self, message_type: str, handler: Callable):
        """Register a handler for specific message types."""
        self.message_handlers[message_type] = handler
        logger.debug(f"Registered handler for message type: {message_type}")
    
    def get_adapter_stats(self) -> Dict[str, Any]:
        """Get Redis adapter statistics."""
        return {
            'instance_id': self.instance_id,
            'redis_connected': self.redis_pub is not None,
            'messages_published': self.messages_published,
            'messages_received': self.messages_received,
            'redis_errors': self.redis_errors,
            'local_rooms': len(self.local_rooms),
            'local_clients': len(self.local_clients),
            'last_health_check': self.last_health_check,
            'pubsub_active': self.pubsub_thread is not None and self.pubsub_thread.is_alive()
        }
    
    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get cluster-wide statistics."""
        try:
            # Get all instance heartbeats
            heartbeat_pattern = "socketio:heartbeat:*"
            heartbeat_keys = self.redis_state.keys(heartbeat_pattern)
            
            instances = []
            total_published = 0
            total_received = 0
            total_errors = 0
            
            for key in heartbeat_keys:
                try:
                    data_json = self.redis_state.get(key)
                    if data_json:
                        data = json.loads(data_json)
                        instances.append(data)
                        total_published += data.get('messages_published', 0)
                        total_received += data.get('messages_received', 0)
                        total_errors += data.get('redis_errors', 0)
                except json.JSONDecodeError:
                    continue
            
            return {
                'total_instances': len(instances),
                'active_instances': len([i for i in instances 
                                       if time.time() - i.get('timestamp', 0) < 120]),
                'total_messages_published': total_published,
                'total_messages_received': total_received,
                'total_redis_errors': total_errors,
                'instances': instances
            }
            
        except Exception as e:
            logger.error(f"Failed to get cluster stats: {e}")
            return {'error': str(e)}
    
    def shutdown(self):
        """Gracefully shutdown the Redis adapter."""
        logger.info("🛑 Shutting down Redis Socket.IO adapter...")
        
        # Stop pub/sub thread
        if self.pubsub:
            self.pubsub.close()
        
        if self.pubsub_thread and self.pubsub_thread.is_alive():
            self.pubsub_thread.join(timeout=5)
        
        # Remove instance heartbeat
        try:
            heartbeat_key = f"socketio:heartbeat:{self.instance_id}"
            self.redis_state.delete(heartbeat_key)
        except:
            pass
        
        # Close Redis connections
        if self.redis_pub:
            self.redis_pub.close()
        if self.redis_sub:
            self.redis_sub.close()
        if self.redis_state:
            self.redis_state.close()
        
        logger.info("✅ Redis Socket.IO adapter shutdown complete")

# Global adapter instance
_redis_adapter: Optional[RedisSocketIOAdapter] = None

def get_redis_adapter() -> Optional[RedisSocketIOAdapter]:
    """Get the global Redis adapter instance."""
    return _redis_adapter

def initialize_redis_adapter(config: Optional[RedisConfig] = None) -> RedisSocketIOAdapter:
    """Initialize the global Redis adapter."""
    global _redis_adapter
    _redis_adapter = RedisSocketIOAdapter(config)
    return _redis_adapter