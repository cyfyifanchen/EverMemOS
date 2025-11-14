"""
Mem0 Adapter - adapt Mem0 online API for evaluation framework.
Reference: https://mem0.ai/

Key features:
- Dual-perspective handling: separate storage and retrieval for speaker_a and speaker_b
- Supports custom instructions
"""
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console

from evaluation.src.adapters.online_base import OnlineAPIAdapter
from evaluation.src.adapters.registry import register_adapter
from evaluation.src.core.data_models import Conversation, SearchResult


@register_adapter("mem0")
class Mem0Adapter(OnlineAPIAdapter):
    """
    Mem0 online API adapter.
    
    Supports:
    - Standard memory storage and retrieval
    
    Config example:
    ```yaml
    adapter: "mem0"
    api_key: "${MEM0_API_KEY}"
    batch_size: 2
    display_timezone_offset: 8  # Optional: convert timestamps to UTC+8 for display
    ```
    """
    
    def __init__(self, config: dict, output_dir: Path = None):
        super().__init__(config, output_dir)
        
        # Import Mem0 client
        try:
            from mem0 import MemoryClient
        except ImportError:
            raise ImportError(
                "Mem0 client not installed. "
                "Please install: pip install mem0ai"
            )
        
        # Initialize Mem0 client
        api_key = config.get("api_key", "")
        if not api_key:
            raise ValueError("Mem0 API key is required. Set 'api_key' in config.")
        
        self.client = MemoryClient(api_key=api_key)
        self.batch_size = config.get("batch_size", 2)
        self.max_retries = config.get("max_retries", 5)
        self.max_content_length = config.get("max_content_length", 8000)
        self.console = Console()
        
        # Set custom instructions (loaded from prompts.yaml)
        # Prioritize config settings (backward compatible), otherwise load from prompts
        custom_instructions = config.get("custom_instructions", None)
        if not custom_instructions:
            # Load from prompts.yaml
            custom_instructions = self._prompts.get("add_stage", {}).get("mem0", {}).get("custom_instructions", None)
            print(f"   ✅ Custom instructions set (from prompts.yaml)")
        
        if custom_instructions:
            try:
                self.client.update_project(custom_instructions=custom_instructions)
                print(f"   ✅ Custom instructions set (from prompts.yaml)")
            except Exception as e:
                print(f"   ⚠️  Failed to set custom instructions: {e}")
        
        print(f"   Batch Size: {self.batch_size}")
        print(f"   Max Content Length: {self.max_content_length}")
    
    def _convert_timestamp_to_display_timezone(self, timestamp_str: str) -> str:
        """
        Convert mem0's timestamp to display timezone.
        
        Default behavior (if display_timezone_offset not set):
        - Convert to system local timezone (symmetric with add stage where naive datetime 
          is treated as local timezone by Python's .timestamp() method)
        
        Optional behavior (if display_timezone_offset is set):
        - Convert to specified timezone (e.g., UTC for explicit UTC handling)
        
        Args:
            timestamp_str: ISO format timestamp string with timezone (e.g., "2023-05-07T22:56:00-07:00")
        
        Returns:
            Formatted timestamp string in display timezone or original if conversion fails
        """
        if not timestamp_str:
            return timestamp_str
        
        try:
            # Parse ISO format timestamp (with timezone)
            dt = datetime.fromisoformat(timestamp_str)
            
            dt_display = dt.astimezone(None)
            
            # Format as readable string (YYYY-MM-DD HH:MM:SS)
            return dt_display.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            # If conversion fails, return original string
            self.console.print(f"⚠️  Failed to convert timestamp '{timestamp_str}': {e}", style="yellow")
            return timestamp_str
    
    async def prepare(self, conversations: List[Conversation], **kwargs) -> None:
        """
        Preparation stage: update project configuration and clean existing data.
        
        Args:
            conversations: Standard format conversation list
            **kwargs: Extra parameters
        """
        # Check if need to clean existing data
        clean_before_add = self.config.get("clean_before_add", False)
        
        if not clean_before_add:
            self.console.print("   ⏭️  Skipping data cleanup (clean_before_add=false)", style="dim")
            return
        
        self.console.print(f"\n{'='*60}", style="bold yellow")
        self.console.print(f"Preparation: Cleaning existing data", style="bold yellow")
        self.console.print(f"{'='*60}", style="bold yellow")
        
        # Collect all user_ids to clean
        user_ids_to_clean = set()
        
        for conv in conversations:
            # Get user_id for speaker_a and speaker_b
            speaker_a = conv.metadata.get("speaker_a", "")
            speaker_b = conv.metadata.get("speaker_b", "")
            
            need_dual = self._need_dual_perspective(speaker_a, speaker_b)
            
            user_ids_to_clean.add(self._extract_user_id(conv, speaker="speaker_a"))
            
            if need_dual:
                user_ids_to_clean.add(self._extract_user_id(conv, speaker="speaker_b"))
        
        # Clean all user data
        self.console.print(f"\n🗑️  Cleaning data for {len(user_ids_to_clean)} user(s)...", style="yellow")
        
        cleaned_count = 0
        failed_count = 0
        
        for user_id in user_ids_to_clean:
            try:
                self.client.delete_all(user_id=user_id)
                cleaned_count += 1
                self.console.print(f"   ✅ Cleaned: {user_id}", style="green")
            except Exception as e:
                failed_count += 1
                self.console.print(f"   ⚠️  Failed to clean {user_id}: {e}", style="yellow")
        
        self.console.print(
            f"\n✅ Cleanup completed: {cleaned_count} succeeded, {failed_count} failed",
            style="bold green"
        )
    
    def _need_dual_perspective(self, speaker_a: str, speaker_b: str) -> bool:
        """
        Determine if dual-perspective handling is needed.
        
        Single perspective (no dual-perspective needed):
        - Standard roles: "user"/"assistant"
        - Case variants: "User"/"Assistant"
        - With suffix: "user_123"/"assistant_456"
        
        Dual perspective (dual-perspective needed):
        - Custom names: "Elena Rodriguez"/"Alex"
        """
        def is_standard_role(speaker: str) -> bool:
            speaker = speaker.lower()
            # Exact match
            if speaker in ["user", "assistant"]:
                return True
            # Starts with user or assistant
            if speaker.startswith("user") or speaker.startswith("assistant"):
                return True
            return False
        
        # Only need dual perspective when both speakers are not standard roles
        return not (is_standard_role(speaker_a) or is_standard_role(speaker_b))
    
    async def add(
        self, 
        conversations: List[Conversation],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Ingest conversations into Mem0.
        
        Key features:
        - Supports single and dual perspective handling
        - Single perspective: standard user/assistant data
        - Dual perspective: custom speaker names, stores memories separately for each speaker
        
        Mem0 API specifics:
        - Requires user_id to distinguish different users
        - Supports batch addition (recommended batch_size=2)
        - Supports graph memory (optional)
        - Requires timestamp (Unix timestamp)
        """
        self.console.print(f"\n{'='*60}", style="bold cyan")
        self.console.print(f"Stage 1: Adding to Mem0 (Dual Perspective)", style="bold cyan")
        self.console.print(f"{'='*60}", style="bold cyan")
        
        conversation_ids = []
        
        for conv in conversations:
            conv_id = conv.conversation_id
            conversation_ids.append(conv_id)
            
            # Get speaker information
            speaker_a = conv.metadata.get("speaker_a", "")
            speaker_b = conv.metadata.get("speaker_b", "")
            
            # Get user_id (extracted from metadata, already set during data loading)
            speaker_a_user_id = self._extract_user_id(conv, speaker="speaker_a")
            speaker_b_user_id = self._extract_user_id(conv, speaker="speaker_b")
            
            # Detect if dual perspective handling is needed
            need_dual_perspective = self._need_dual_perspective(speaker_a, speaker_b)
            
            # Get timestamp (using first message's time)
            timestamp = None
            is_fake_timestamp = False
            if conv.messages and conv.messages[0].timestamp:
                timestamp = int(conv.messages[0].timestamp.timestamp()) 
                is_fake_timestamp = conv.messages[0].metadata.get("is_fake_timestamp", False)
            
            self.console.print(f"\n📥 Adding conversation: {conv_id}", style="cyan")
            if is_fake_timestamp:
                self.console.print(f"   ⚠️  Using fake timestamp (original data has no timestamp)", style="yellow")
            
            if need_dual_perspective:
                # Dual perspective handling (LoCoMo style data)
                self.console.print(f"   Mode: Dual Perspective", style="dim")
                await self._add_dual_perspective(conv, speaker_a, speaker_b, speaker_a_user_id, speaker_b_user_id, timestamp)
            else:
                # Single perspective handling (standard user/assistant data)
                self.console.print(f"   Mode: Single Perspective", style="dim")
                await self._add_single_perspective(conv, speaker_a_user_id, timestamp)
            
            self.console.print(f"   ✅ Added successfully", style="green")
        
        self.console.print(f"\n✅ All conversations added to Mem0", style="bold green")
        
        # Return metadata (online API doesn't need local index)
        return {
            "type": "online_api",
            "system": "mem0",
            "conversation_ids": conversation_ids,
        }
    
    async def _add_single_perspective(self, conv: Conversation, user_id: str, timestamp: int):
        """Single perspective addition (for standard user/assistant data)."""
        messages = []
        truncated_count = 0
        
        for msg in conv.messages:
            # Standard format: directly use speaker_name: content
            content = f"{msg.speaker_name}: {msg.content}"
            
            # Truncate overly long content (Mem0 API limit)
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length]
                truncated_count += 1
            
            # Determine role (user or assistant)
            role = "user" if msg.speaker_name.lower().startswith("user") else "assistant"
            messages.append({"role": role, "content": content})
        
        self.console.print(f"   User ID: {user_id}", style="dim")
        self.console.print(f"   Messages: {len(messages)}", style="dim")
        if truncated_count > 0:
            self.console.print(f"   ⚠️  Truncated {truncated_count} messages (>{self.max_content_length} chars)", style="yellow")
        
        await self._add_messages_for_user(messages, user_id, timestamp, "Single User")
    
    async def _add_dual_perspective(
        self, 
        conv: Conversation, 
        speaker_a: str, 
        speaker_b: str,
        speaker_a_user_id: str,
        speaker_b_user_id: str,
        timestamp: int
    ):
        """Dual perspective addition (for data with custom speaker names)."""
        # Construct message lists for both perspectives separately
        speaker_a_messages = []
        speaker_b_messages = []
        truncated_count = 0
        
        for msg in conv.messages:
            # Format: speaker_name: content
            content = f"{msg.speaker_name}: {msg.content}"
            
            # Truncate overly long content (Mem0 API limit)
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length]
                truncated_count += 1
            
            if msg.speaker_name == speaker_a:
                # What speaker_a said
                speaker_a_messages.append({"role": "user", "content": content})
                speaker_b_messages.append({"role": "assistant", "content": content})
            elif msg.speaker_name == speaker_b:
                # What speaker_b said
                speaker_a_messages.append({"role": "assistant", "content": content})
                speaker_b_messages.append({"role": "user", "content": content})
        
        self.console.print(f"   Speaker A: {speaker_a} (user_id: {speaker_a_user_id})", style="dim")
        self.console.print(f"   Speaker A Messages: {len(speaker_a_messages)}", style="dim")
        self.console.print(f"   Speaker B: {speaker_b} (user_id: {speaker_b_user_id})", style="dim")
        self.console.print(f"   Speaker B Messages: {len(speaker_b_messages)}", style="dim")
        if truncated_count > 0:
            self.console.print(f"   ⚠️  Truncated {truncated_count} messages (>{self.max_content_length} chars)", style="yellow")
        
        # Add messages for both user_ids separately
        await self._add_messages_for_user(
            speaker_a_messages, 
            speaker_a_user_id, 
            timestamp, 
            f"Speaker A ({speaker_a})"
        )
        await self._add_messages_for_user(
            speaker_b_messages, 
            speaker_b_user_id, 
            timestamp, 
            f"Speaker B ({speaker_b})"
        )
    
    async def _add_messages_for_user(
        self, 
        messages: List[Dict], 
        user_id: str, 
        timestamp: int,
        description: str
    ):
        """
        Add messages for a single user (with batching and retry).
        
        Args:
            messages: Message list
            user_id: User ID
            timestamp: Unix timestamp
            description: Description (for logging)
        """
        for i in range(0, len(messages), self.batch_size):
            batch_messages = messages[i : i + self.batch_size]
            
            # Retry mechanism
            for attempt in range(self.max_retries):
                try:
                    self.client.add(
                        messages=batch_messages,
                        timestamp=timestamp,
                        user_id=user_id,
                    )
                    break
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        self.console.print(
                        f"   ⚠️  [{description}] Retry {attempt + 1}/{self.max_retries}: {e}", 
                            style="yellow"
                        )
                        time.sleep(2 ** attempt)
                    else:
                        self.console.print(
                            f"   ❌ [{description}] Failed after {self.max_retries} retries: {e}", 
                            style="red"
                        )
                        raise e
    
    async def search(
        self, 
        query: str,
        conversation_id: str,
        index: Any,
        **kwargs
    ) -> SearchResult:
        """
        Retrieve relevant memories from Mem0.
        
        Key features:
        - Intelligently determine if dual perspective search is needed
        - Single perspective: search one user_id
        - Dual perspective: search both speaker_a and speaker_b simultaneously, merge results
        
        Args:
            query: Query text
            conversation_id: Conversation ID
            index: Index metadata (contains conversation_ids)
            **kwargs: Optional parameters, such as top_k, conversation (for rebuilding cache)
        
        Returns:
            Standard format search result
        """
        top_k = kwargs.get("top_k", 10)
        
        # Get conversation info directly from kwargs (don't use cache)
        conversation = kwargs.get("conversation")
        if conversation:
            speaker_a = conversation.metadata.get("speaker_a", "")
            speaker_b = conversation.metadata.get("speaker_b", "")
            speaker_a_user_id = self._extract_user_id(conversation, speaker="speaker_a")
            speaker_b_user_id = self._extract_user_id(conversation, speaker="speaker_b")
            need_dual_perspective = self._need_dual_perspective(speaker_a, speaker_b)
        else:
            # Fallback: use default user_id
            speaker_a_user_id = f"{conversation_id}_speaker_a"
            speaker_b_user_id = f"{conversation_id}_speaker_b"
            speaker_a = "speaker_a"
            speaker_b = "speaker_b"
            need_dual_perspective = False
        
        if need_dual_perspective:
            # Dual perspective search: search from both speakers' perspectives separately
            return await self._search_dual_perspective(
                query, conversation_id, speaker_a, speaker_b, 
                speaker_a_user_id, speaker_b_user_id, top_k
            )
        else:
            # Single perspective search (standard user/assistant data)
            return await self._search_single_perspective(
                query, conversation_id, speaker_a_user_id, top_k
            )
    
    async def _search_single_perspective(
        self, query: str, conversation_id: str, user_id: str, top_k: int
    ) -> SearchResult:
        """Single perspective search (for standard user/assistant data)."""
        
        try:
            results = self.client.search(
                query=query,
                top_k=top_k,
                user_id=user_id,
                filters={"AND": [{"user_id": f"{user_id}"}]},
            )
            
            # Debug: print raw search results
            self.console.print(f"\n[DEBUG] Mem0 Search Results (Single):", style="yellow")
            self.console.print(f"  Query: {query}", style="dim")
            self.console.print(f"  User ID: {user_id}", style="dim")
            self.console.print(f"  Results: {json.dumps(results, indent=2, ensure_ascii=False)}", style="dim")
            
        except Exception as e:
            self.console.print(f"❌ Mem0 search error: {e}", style="red")
            return SearchResult(
                query=query,
                conversation_id=conversation_id,
                results=[],
                retrieval_metadata={"error": str(e)}
            )
        
        # Build detailed results list (add user_id to each memory)
        memory_results = []
        for memory in results.get("results", []):
            # Convert timestamp to display timezone if configured
            created_at_original = memory.get("created_at", "")
            created_at_display = self._convert_timestamp_to_display_timezone(created_at_original)
            
            memory_results.append({
                "content": f"{created_at_display}: {memory['memory']}",
                "score": memory.get("score", 0.0),
                "user_id": user_id,
                "metadata": {
                    "id": memory.get("id", ""),
                    "created_at": created_at_original,  # Keep original for reference
                    "created_at_display": created_at_display,  # Add display version
                    "memory": memory.get("memory", ""),
                    "user_id": memory.get("user_id", ""),
                }
            })
        
        return SearchResult(
            query=query,
            conversation_id=conversation_id,
            results=memory_results,
            retrieval_metadata={
                "system": "mem0",
                "top_k": top_k,
                "dual_perspective": False,
                "user_ids": [user_id],
            }
        )
    
    async def _search_dual_perspective(
        self, 
        query: str, 
        conversation_id: str,
        speaker_a: str,
        speaker_b: str,
        speaker_a_user_id: str,
        speaker_b_user_id: str,
        top_k: int
    ) -> SearchResult:
        """Dual perspective search (for data with custom speaker names)."""
        
        # Dual perspective search: search both user_ids separately
        try:
            search_speaker_a_results = self.client.search(
                query=query,
                top_k=top_k,
                user_id=speaker_a_user_id,
                filters={"AND": [{"user_id": f"{speaker_a_user_id}"}]},
            )
            search_speaker_b_results = self.client.search(
                query=query,
                top_k=top_k,
                user_id=speaker_b_user_id,
                filters={"AND": [{"user_id": f"{speaker_b_user_id}"}]},
            )
            
            # Debug: print raw search results
            self.console.print(f"\n[DEBUG] Mem0 Search Results (Dual):", style="yellow")
            self.console.print(f"  Query: {query}", style="dim")
            self.console.print(f"  Speaker A ({speaker_a}, user_id={speaker_a_user_id}):", style="dim")
            self.console.print(f"    {json.dumps(search_speaker_a_results, indent=2, ensure_ascii=False)}", style="dim")
            self.console.print(f"  Speaker B ({speaker_b}, user_id={speaker_b_user_id}):", style="dim")
            self.console.print(f"    {json.dumps(search_speaker_b_results, indent=2, ensure_ascii=False)}", style="dim")
            
        except Exception as e:
            self.console.print(f"❌ Mem0 dual search error: {e}", style="red")
            return SearchResult(
                query=query,
                conversation_id=conversation_id,
                results=[],
                retrieval_metadata={"error": str(e)}
            )
        
        # Build detailed results list (add user_id to each memory)
        all_results = []
        
        # Speaker A's memories
        for memory in search_speaker_a_results.get("results", []):
            created_at_original = memory.get("created_at", "")
            created_at_display = self._convert_timestamp_to_display_timezone(created_at_original)
            
            all_results.append({
                "content": f"{created_at_display}: {memory['memory']}",
                "score": memory.get("score", 0.0),
                "user_id": speaker_a_user_id,
                "metadata": {
                    "id": memory.get("id", ""),
                    "created_at": created_at_original,
                    "created_at_display": created_at_display,
                    "memory": memory.get("memory", ""),
                    "user_id": memory.get("user_id", ""),
                }
            })
        
        # Speaker B's memories
        for memory in search_speaker_b_results.get("results", []):
            created_at_original = memory.get("created_at", "")
            created_at_display = self._convert_timestamp_to_display_timezone(created_at_original)
            
            all_results.append({
                "content": f"{created_at_display}: {memory['memory']}",
                "score": memory.get("score", 0.0),
                "user_id": speaker_b_user_id,
                "metadata": {
                    "id": memory.get("id", ""),
                    "created_at": created_at_original,
                    "created_at_display": created_at_display,
                    "memory": memory.get("memory", ""),
                    "user_id": memory.get("user_id", ""),
                }
            })
        
        # Format memories (for formatted_context)
        speaker_a_memories = [
            f"{self._convert_timestamp_to_display_timezone(memory['created_at'])}: {memory['memory']}"
            for memory in search_speaker_a_results.get("results", [])
        ]
        speaker_b_memories = [
            f"{self._convert_timestamp_to_display_timezone(memory['created_at'])}: {memory['memory']}"
            for memory in search_speaker_b_results.get("results", [])
        ]
        
        # Format memories as readable text (not JSON array)
        speaker_a_memories_text = "\n".join(speaker_a_memories) if speaker_a_memories else "(No memories found)"
        speaker_b_memories_text = "\n".join(speaker_b_memories) if speaker_b_memories else "(No memories found)"
        
        # Use standard default template
        template = self._prompts["online_api"].get("templates", {}).get("default", "")
        context = template.format(
            speaker_1=speaker_a,
            speaker_1_memories=speaker_a_memories_text,
            speaker_2=speaker_b,
            speaker_2_memories=speaker_b_memories_text,
        )
        
        # Return results
        return SearchResult(
            query=query,
            conversation_id=conversation_id,
            results=all_results,
            retrieval_metadata={
                "system": "mem0",
                "top_k": top_k,
                "dual_perspective": True,
                "user_ids": [speaker_a_user_id, speaker_b_user_id],
                "formatted_context": context,
                "speaker_a_memories_count": len(speaker_a_memories),
                "speaker_b_memories_count": len(speaker_b_memories),
            }
        )
    
    def _get_answer_prompt(self) -> str:
        """
        Return answer prompt.
        
        Uses generic default prompt (loaded from YAML).
        """
        return self._prompts["online_api"]["default"]["answer_prompt_mem0"]
    
    def get_system_info(self) -> Dict[str, Any]:
        """Return system info."""
        return {
            "name": "Mem0",
            "type": "online_api",
            "description": "Mem0 - Personalized AI Memory Layer",
            "adapter": "Mem0Adapter",
        }

