"""
Chat History Manager.

Orchestrates cache (Redis) and persistence (ADLS) with:
- Automatic fallback when cache unavailable
- Merge logic when persisting from cache
- Background persist scheduling
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass, field

import structlog

from src.memory.cache import RedisCache, InMemoryCache, CacheConfig
from src.memory.persistence import ADLSPersistence, PersistenceConfig

if TYPE_CHECKING:
    from agent_framework import ChatAgent

logger = structlog.get_logger(__name__)


@dataclass
class MemoryConfig:
    """Complete memory configuration."""
    cache: CacheConfig = field(default_factory=CacheConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)


@dataclass 
class ChatSession:
    """Represents an active chat session."""
    chat_id: str
    thread: Any  # Agent thread object
    created_at: datetime
    last_accessed: datetime
    message_count: int = 0
    persisted: bool = False
    

class ChatHistoryManager:
    """
    Orchestrates chat history across cache and persistence layers.
    
    Handles all edge cases:
    - chat_id provided, found in cache -> use cached
    - chat_id provided, not in cache, found in ADLS -> load to cache
    - chat_id provided, not found anywhere -> create new with that ID
    - chat_id not provided -> create new with generated UUID
    
    Merge logic for persistence:
    - When persisting, load existing ADLS data
    - Merge new messages from cache (dedupe by timestamp)
    - Save merged result back to ADLS
    """
    
    def __init__(
        self, 
        config: MemoryConfig,
        agent: Optional["ChatAgent"] = None
    ):
        """
        Initialize chat history manager.
        
        Args:
            config: MemoryConfig with cache and persistence settings
            agent: Optional ChatAgent for thread operations
        """
        self.config = config
        self._agent = agent
        
        # Initialize cache (Redis or fallback to in-memory)
        if config.cache.enabled:
            self._cache = RedisCache(config.cache)
        else:
            self._cache = InMemoryCache(ttl=config.cache.ttl)
        
        # Initialize persistence
        self._persistence = ADLSPersistence(config.persistence)
        
        # Track active sessions
        self._sessions: Dict[str, ChatSession] = {}
        
        # Background persist task
        self._persist_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(
            "ChatHistoryManager initialized",
            cache_enabled=config.cache.enabled,
            persistence_enabled=config.persistence.enabled
        )
    
    def set_agent(self, agent: "ChatAgent") -> None:
        """Set the agent for thread operations."""
        self._agent = agent
    
    async def get_or_create_thread(
        self, 
        chat_id: Optional[str] = None
    ) -> tuple[str, Any]:
        """
        Get existing thread or create new one.
        
        Args:
            chat_id: Optional chat session ID. If not provided, generates new UUID.
            
        Returns:
            Tuple of (chat_id, thread object)
            
        Edge cases handled:
        - chat_id=None -> new UUID, new thread
        - chat_id provided, in cache -> deserialize cached thread
        - chat_id provided, not in cache, in ADLS -> load from ADLS, cache it
        - chat_id provided, not found -> new thread with provided ID
        """
        if self._agent is None:
            raise RuntimeError("Agent not set. Call set_agent() first.")
        
        # Generate ID if not provided
        if not chat_id:
            chat_id = str(uuid.uuid4())
            logger.info("Generated new chat_id", chat_id=chat_id)
            return await self._create_new_session(chat_id)
        
        # Try cache first
        cached = await self._cache.get(chat_id)
        if cached:
            logger.info("Loading thread from cache", chat_id=chat_id)
            return await self._restore_session(chat_id, cached)
        
        # Try ADLS if persistence enabled
        if self.config.persistence.enabled:
            persisted = await self._persistence.get(chat_id)
            if persisted:
                logger.info("Loading thread from ADLS", chat_id=chat_id)
                # Cache the restored thread
                await self._cache.set(chat_id, persisted)
                return await self._restore_session(chat_id, persisted)
        
        # Not found anywhere - create new with provided ID
        logger.info("Creating new thread with provided chat_id", chat_id=chat_id)
        return await self._create_new_session(chat_id)
    
    async def _create_new_session(self, chat_id: str) -> tuple[str, Any]:
        """Create a new chat session."""
        thread = self._agent.get_new_thread()
        
        session = ChatSession(
            chat_id=chat_id,
            thread=thread,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc)
        )
        self._sessions[chat_id] = session
        
        return chat_id, thread
    
    async def _restore_session(
        self, 
        chat_id: str, 
        thread_data: Dict[str, Any]
    ) -> tuple[str, Any]:
        """Restore a session from serialized data."""
        try:
            # Make a copy and strip metadata fields before deserializing
            # The framework's deserialize_thread() doesn't expect our metadata fields
            clean_data = dict(thread_data)
            keys_to_strip = [k for k in clean_data.keys() if k.startswith('_')]
            for key in keys_to_strip:
                del clean_data[key]
            
            logger.debug("Deserializing thread", chat_id=chat_id, keys=list(clean_data.keys()))
            thread = await self._agent.deserialize_thread(clean_data)
            
            session = ChatSession(
                chat_id=chat_id,
                thread=thread,
                created_at=datetime.fromisoformat(
                    thread_data.get("_created_at", datetime.now(timezone.utc).isoformat())
                ),
                last_accessed=datetime.now(timezone.utc),
                message_count=thread_data.get("_message_count", 0),
                persisted=thread_data.get("_persisted", False)
            )
            self._sessions[chat_id] = session
            
            return chat_id, thread
            
        except Exception as e:
            logger.warning(
                "Failed to deserialize thread, creating new",
                chat_id=chat_id, 
                error=str(e)
            )
            return await self._create_new_session(chat_id)
    
    async def save_thread(
        self, 
        chat_id: str,
        thread: Any,
        force_persist: bool = False
    ) -> bool:
        """
        Save thread state to cache (and optionally ADLS).
        
        Args:
            chat_id: The chat session ID
            thread: The thread object to serialize
            force_persist: If True, immediately persist to ADLS
            
        Returns:
            True if saved successfully
        """
        try:
            # Serialize thread
            thread_data = await thread.serialize()
            
            # Add metadata
            session = self._sessions.get(chat_id)
            if session:
                session.last_accessed = datetime.now(timezone.utc)
                session.message_count += 1
                thread_data["_created_at"] = session.created_at.isoformat()
                thread_data["_message_count"] = session.message_count
            
            thread_data["_updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Save to cache
            cached = await self._cache.set(chat_id, thread_data)
            
            # Persist if forced or no cache available
            if force_persist or not cached:
                if self.config.persistence.enabled:
                    await self._persist_with_merge(chat_id, thread_data)
            
            return True
            
        except Exception as e:
            logger.error("Failed to save thread", chat_id=chat_id, error=str(e))
            return False
    
    async def _persist_with_merge(
        self, 
        chat_id: str, 
        new_data: Dict[str, Any]
    ) -> bool:
        """
        Persist to ADLS with merge logic.
        
        If data already exists in ADLS:
        1. Load existing data
        2. Merge messages (new data takes precedence for same timestamps)
        3. Save merged result
        """
        try:
            # Check for existing persisted data
            existing = await self._persistence.get(chat_id)
            
            if existing:
                # Merge: new data takes precedence
                merged = await self._merge_thread_data(existing, new_data)
                merged["_merge_count"] = existing.get("_merge_count", 0) + 1
            else:
                merged = new_data
            
            merged["_persisted"] = True
            merged["_persisted_at"] = datetime.now(timezone.utc).isoformat()
            
            success = await self._persistence.save(chat_id, merged)
            
            if success and chat_id in self._sessions:
                self._sessions[chat_id].persisted = True
            
            return success
            
        except Exception as e:
            logger.error("Persist with merge failed", chat_id=chat_id, error=str(e))
            return False
    
    async def _merge_thread_data(
        self, 
        existing: Dict[str, Any], 
        new: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge two thread data dictionaries.
        
        Strategy:
        - Messages: Combine and dedupe by content hash or timestamp
        - Metadata: New values override existing
        - Preserve oldest created_at, newest updated_at
        """
        merged = {**existing, **new}
        
        # Preserve original creation time
        if "_created_at" in existing:
            merged["_created_at"] = existing["_created_at"]
        
        # If both have messages lists, merge them
        if "messages" in existing and "messages" in new:
            existing_msgs = existing.get("messages", [])
            new_msgs = new.get("messages", [])
            
            # Simple merge: use new messages but don't lose any
            # The framework thread serialization should handle this internally
            # We just ensure we don't truncate
            if len(new_msgs) >= len(existing_msgs):
                merged["messages"] = new_msgs
            else:
                # This shouldn't happen, but preserve all messages
                seen = set()
                all_msgs = []
                for msg in existing_msgs + new_msgs:
                    # Dedupe by content if possible
                    key = str(msg.get("content", "")) + str(msg.get("timestamp", ""))
                    if key not in seen:
                        seen.add(key)
                        all_msgs.append(msg)
                merged["messages"] = all_msgs
        
        logger.debug(
            "Merged thread data",
            existing_msgs=len(existing.get("messages", [])),
            new_msgs=len(new.get("messages", [])),
            merged_msgs=len(merged.get("messages", []))
        )
        
        return merged
    
    async def delete_chat(self, chat_id: str) -> bool:
        """Delete chat from all storage layers."""
        success = True
        
        # Remove from cache
        await self._cache.delete(chat_id)
        
        # Remove from persistence
        if self.config.persistence.enabled:
            if not await self._persistence.delete(chat_id):
                success = False
        
        # Remove from active sessions
        self._sessions.pop(chat_id, None)
        
        return success
    
    async def list_chats(
        self, 
        source: str = "all",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List available chats.
        
        Args:
            source: "cache", "persistence", or "all"
            limit: Maximum number of results
            
        Returns:
            List of chat metadata dicts
        """
        results = []
        seen = set()
        
        # Active sessions
        for chat_id, session in self._sessions.items():
            if len(results) >= limit:
                break
            results.append({
                "chat_id": chat_id,
                "active": True,
                "created_at": session.created_at.isoformat(),
                "last_accessed": session.last_accessed.isoformat(),
                "message_count": session.message_count,
                "persisted": session.persisted
            })
            seen.add(chat_id)
        
        # Cache (if Redis)
        if source in ("cache", "all") and isinstance(self._cache, RedisCache):
            cached_ids = await self._cache.list_keys()
            for chat_id in cached_ids:
                if chat_id not in seen and len(results) < limit:
                    meta = await self._cache.get_metadata(chat_id)
                    if meta:
                        results.append(meta)
                        seen.add(chat_id)
        
        # Persistence
        if source in ("persistence", "all") and self.config.persistence.enabled:
            persisted = await self._persistence.list_chats(limit=limit)
            for item in persisted:
                if item["chat_id"] not in seen and len(results) < limit:
                    results.append(item)
                    seen.add(item["chat_id"])
        
        return results
    
    async def start_background_persist(self) -> None:
        """Start background task to persist chats before cache expiry."""
        if not self.config.persistence.enabled:
            return
        
        if self._running:
            return
        
        self._running = True
        self._persist_task = asyncio.create_task(self._background_persist_loop())
        logger.info("Started background persist task")
    
    async def _background_persist_loop(self) -> None:
        """Background loop to persist chats approaching TTL."""
        cache_ttl = self.config.cache.ttl
        persist_at = self._persistence.parse_schedule(cache_ttl)
        check_interval = min(60, persist_at // 4)  # Check frequently
        
        while self._running:
            try:
                await asyncio.sleep(check_interval)
                
                if not isinstance(self._cache, RedisCache):
                    continue
                
                # Check each cached chat's TTL
                chat_ids = await self._cache.list_keys()
                for chat_id in chat_ids:
                    ttl = await self._cache.get_ttl(chat_id)
                    if ttl is not None and ttl <= (cache_ttl - persist_at):
                        # Time to persist
                        logger.info("Auto-persisting before TTL expiry", chat_id=chat_id, ttl=ttl)
                        cached = await self._cache.get(chat_id)
                        if cached:
                            await self._persist_with_merge(chat_id, cached)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Background persist error", error=str(e))
    
    async def close(self) -> None:
        """Close all connections and stop background tasks."""
        # Stop background task
        self._running = False
        if self._persist_task:
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass
        
        # Persist all active sessions before closing
        if self.config.persistence.enabled:
            for chat_id, session in self._sessions.items():
                if not session.persisted:
                    try:
                        thread_data = await session.thread.serialize()
                        await self._persist_with_merge(chat_id, thread_data)
                    except Exception as e:
                        logger.warning("Failed to persist on close", chat_id=chat_id, error=str(e))
        
        # Close connections
        await self._cache.close()
        await self._persistence.close()
        
        self._sessions.clear()
        logger.info("ChatHistoryManager closed")


def parse_memory_config(config_dict: Dict[str, Any]) -> MemoryConfig:
    """
    Parse memory configuration from TOML config dict.
    
    Expected format:
    [agent.memory]
    enabled = true
    
    [agent.memory.cache]
    enabled = true
    host = "your-redis.redis.cache.windows.net"
    port = 6380
    ssl = true
    ttl = 3600
    prefix = "chat:"
    
    [agent.memory.persistence]
    enabled = true
    account_name = "yourstorageaccount"
    container = "chat-history"
    folder = "threads"
    schedule = "ttl+300"
    """
    memory_dict = config_dict.get("memory", {})
    
    # Cache config
    cache_dict = memory_dict.get("cache", {})
    cache_config = CacheConfig(
        enabled=cache_dict.get("enabled", False),
        host=cache_dict.get("host", ""),
        port=cache_dict.get("port", 6380),
        ssl=cache_dict.get("ssl", True),
        ttl=cache_dict.get("ttl", 3600),
        prefix=cache_dict.get("prefix", "chat:"),
        database=cache_dict.get("database", 0)
    )
    
    # Persistence config
    persist_dict = memory_dict.get("persistence", {})
    persist_config = PersistenceConfig(
        enabled=persist_dict.get("enabled", False),
        account_name=persist_dict.get("account_name", ""),
        container=persist_dict.get("container", "chat-history"),
        folder=persist_dict.get("folder", "threads"),
        schedule=persist_dict.get("schedule", "ttl+300")
    )
    
    return MemoryConfig(cache=cache_config, persistence=persist_config)
