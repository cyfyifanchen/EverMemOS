"""
Memos Adapter - adapt Memos online API for evaluation framework.
Reference: https://www.memos.so/
"""
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import requests
from rich.console import Console

from evaluation.src.adapters.online_base import OnlineAPIAdapter
from evaluation.src.adapters.registry import register_adapter
from evaluation.src.core.data_models import Conversation, SearchResult


@register_adapter("memos")
class MemosAdapter(OnlineAPIAdapter):
    """
    Memos online API adapter.
    
    Supports:
    - Memory ingestion (supports conversation context)
    - Memory retrieval
    
    Official API supported parameters:
    - user_id (required) - Format: {conv_id}_{speaker}, already contains session info
    - query (required)
    - memory_limit_number (optional, default 6)
    
    Note: Does not use conversation_id parameter, as user_id already contains session info
    
    Config example:
    ```yaml
    adapter: "memos"
    api_url: "${MEMOS_URL}"
    api_key: "${MEMOS_KEY}"
    ```
    """
    
    def __init__(self, config: dict, output_dir: Path = None):
        super().__init__(config, output_dir)
        
        # Get API configuration
        self.api_url = config.get("api_url", "")
        if not self.api_url:
            raise ValueError("Memos API URL is required. Set 'api_url' in config.")
        
        api_key = config.get("api_key", "")
        if not api_key:
            raise ValueError("Memos API key is required. Set 'api_key' in config.")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": api_key
        }
        
        # Retrieval configuration (only keep batch_size and max_retries, other params not supported by official API)
        self.batch_size = config.get("batch_size", 9999)  # Memos supports large batches
        self.max_retries = config.get("max_retries", 5)
        
        self.console = Console()
        
        print(f"   API URL: {self.api_url}")
    
    async def add(
        self, 
        conversations: List[Conversation],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Ingest conversations into Memos.
        
        Memos API specifics:
        - Requires user_id and conversation_id
        - Supports large batch addition
        - Messages need to include chat_time
        """
        self.console.print(f"\n{'='*60}", style="bold cyan")
        self.console.print(f"Stage 1: Adding to Memos", style="bold cyan")
        self.console.print(f"{'='*60}", style="bold cyan")
        
        conversation_ids = []
        
        for conv in conversations:
            conv_id = conv.conversation_id
            conversation_ids.append(conv_id)
            
            # Detect if dual perspective handling is needed
            speaker_a = conv.metadata.get("speaker_a", "")
            speaker_b = conv.metadata.get("speaker_b", "")
            need_dual_perspective = self._need_dual_perspective(speaker_a, speaker_b)
            
            self.console.print(f"\n📥 Adding conversation: {conv_id}", style="cyan")
            
            if need_dual_perspective:
                # Dual perspective handling (LoCoMo style data)
                self.console.print(f"   Mode: Dual Perspective", style="dim")
                self._add_dual_perspective(conv, conv_id)
            else:
                # Single perspective handling (standard user/assistant data)
                self.console.print(f"   Mode: Single Perspective", style="dim")
                self._add_single_perspective(conv, conv_id)
            
            self.console.print(f"   ✅ Added successfully", style="green")
        
        self.console.print(f"\n✅ All conversations added to Memos", style="bold green")
        
        # Return metadata
        return {
            "type": "online_api",
            "system": "memos",
            "conversation_ids": conversation_ids,
        }
    
    def _need_dual_perspective(self, speaker_a: str, speaker_b: str) -> bool:
        """
        Determine if dual perspective handling is needed.
        
        Single perspective (no dual perspective needed):
        - Standard roles: "user"/"assistant"
        - Case variants: "User"/"Assistant"
        - With suffix: "user_123"/"assistant_456"
        
        Dual perspective (dual perspective needed):
        - Custom names: "Elena Rodriguez"/"Alex"
        """
        speaker_a_lower = speaker_a.lower()
        speaker_b_lower = speaker_b.lower()
        
        # Check if user/assistant related names (relaxed condition)
        def is_standard_role(speaker: str) -> bool:
            speaker = speaker.lower()
            # Exact match
            if speaker in ["user", "assistant"]:
                return True
            # Starts with user or assistant (handles user_123, assistant_456, etc.)
            if speaker.startswith("user") or speaker.startswith("assistant"):
                return True
            return False
        
        # Only need dual perspective when both speakers are not standard roles
        return not (is_standard_role(speaker_a) or is_standard_role(speaker_b))
    
    def _add_single_perspective(self, conv: Conversation, conv_id: str):
        """Single perspective addition (for standard user/assistant data)."""
        messages = self._conversation_to_messages(conv, format_type="memos")
        user_id = self._extract_user_id(conv, speaker="speaker_a")
        
        self.console.print(f"   User ID: {user_id}", style="dim")
        self.console.print(f"   Messages: {len(messages)}", style="dim")
        
        self._send_messages_to_api(messages, user_id, conv_id)
    
    def _add_dual_perspective(self, conv: Conversation, conv_id: str):
        """Dual perspective addition (for LoCoMo style data)."""
        # From speaker_a's perspective
        speaker_a_messages = self._conversation_to_messages(
            conv, 
            format_type="memos",
            perspective="speaker_a"
        )
        speaker_a_id = self._extract_user_id(conv, speaker="speaker_a")
        
        # From speaker_b's perspective
        speaker_b_messages = self._conversation_to_messages(
            conv,
            format_type="memos",
            perspective="speaker_b"
        )
        speaker_b_id = self._extract_user_id(conv, speaker="speaker_b")
        
        self.console.print(f"   Speaker A ID: {speaker_a_id}", style="dim")
        self.console.print(f"   Speaker A Messages: {len(speaker_a_messages)}", style="dim")
        self.console.print(f"   Speaker B ID: {speaker_b_id}", style="dim")
        self.console.print(f"   Speaker B Messages: {len(speaker_b_messages)}", style="dim")
        
        # Send separately
        self._send_messages_to_api(speaker_a_messages, speaker_a_id, conv_id)
        self._send_messages_to_api(speaker_b_messages, speaker_b_id, conv_id)
    
    def _send_messages_to_api(self, messages: List[Dict], user_id: str, conv_id: str):
        """Send messages to Memos API."""
        url = f"{self.api_url}/add/message"
        
        for i in range(0, len(messages), self.batch_size):
            batch_messages = messages[i : i + self.batch_size]
            
            payload = json.dumps(
                {
                    "messages": batch_messages,
                    "user_id": user_id,
                    "conversation_id": conv_id,
                },
                ensure_ascii=False
            )
            
            # Retry mechanism
            for attempt in range(self.max_retries):
                try:
                    response = requests.post(url, data=payload, headers=self.headers, timeout=60)
                    
                    if response.status_code != 200:
                        raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
                    result = response.json()
                    if result.get("message") != "ok":
                        raise Exception(f"API error: {result}")
                    
                    break
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        self.console.print(
                            f"   ⚠️  Retry {attempt + 1}/{self.max_retries}: {e}", 
                            style="yellow"
                        )
                        time.sleep(2 ** attempt)
                    else:
                        self.console.print(f"   ❌ Failed after {self.max_retries} retries: {e}", style="red")
                        raise e
    
    def _search_single_user(self, query: str, user_id: str, top_k: int) -> Dict[str, Any]:
        """
        Single user search (internal method).
        
        Args:
            query: Query text
            user_id: User ID (format: {conv_id}_{speaker}, already contains session info)
            top_k: Number of memories to return
        
        Returns:
            Search result dict:
            {
                "text_mem": [{"memories": [...]}],
                "pref_string": "Explicit Preference:\n1. ..."
            }
        
        Note:
            No need to pass conversation_id parameter, as user_id already contains session info.
            Example: user_id="locomo_0_Caroline" uniquely identifies the locomo_0 conversation.
        """
        url = f"{self.api_url}/search/memory"
        
        # Only use officially required parameters
        payload_dict = {
            "query": query,
            "user_id": user_id,
            "memory_limit_number": top_k,
        }
        
        payload = json.dumps(payload_dict, ensure_ascii=False)
        
        # Retry mechanism
        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, data=payload, headers=self.headers, timeout=60)
                
                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                
                result = response.json()
                if result.get("message") != "ok":
                    raise Exception(f"API error: {result}")
                
                data = result.get("data", {})
                text_mem_res = data.get("memory_detail_list", [])
                pref_mem_res = data.get("preference_detail_list", [])
                preference_note = data.get("preference_note", "")
                
                # Standardize field names: rename memory_value to memory
                for i in text_mem_res:
                    i.update({"memory": i.pop("memory_value", i.get("memory", ""))})
                
                # Format preference string
                explicit_prefs = [
                    p["preference"]
                    for p in pref_mem_res
                    if p.get("preference_type", "") == "explicit_preference"
                ]
                implicit_prefs = [
                    p["preference"]
                    for p in pref_mem_res
                    if p.get("preference_type", "") == "implicit_preference"
                ]
                
                pref_parts = []
                if explicit_prefs:
                    pref_parts.append(
                        "Explicit Preference:\n"
                        + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(explicit_prefs))
                    )
                if implicit_prefs:
                    pref_parts.append(
                        "Implicit Preference:\n"
                        + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(implicit_prefs))
                    )
                
                pref_string = "\n".join(pref_parts) + preference_note
                
                return {"text_mem": [{"memories": text_mem_res}], "pref_string": pref_string}
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise e
        
        return {"text_mem": [{"memories": []}], "pref_string": ""}
    
    async def search(
        self,
        query: str,
        conversation_id: str,
        index: Any,
        **kwargs
    ) -> SearchResult:
        """
        Retrieve relevant memories from Memos.
        
        Memos specifics:
        - Supports preference extraction (explicit/implicit preferences)
        - Supports multiple retrieval modes
        - Supports dual perspective search (LoCoMo style data)
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
            search_data = self._search_single_user(query, user_id, top_k)
        except Exception as e:
            self.console.print(f"❌ Memos search error: {e}", style="red")
            return SearchResult(
                query=query,
                conversation_id=conversation_id,
                results=[],
                retrieval_metadata={"error": str(e)}
            )
        
        # Convert to standard SearchResult format
        search_results = []
        for item in search_data["text_mem"][0]["memories"]:
            created_at = item.get("memory_time") or item.get("create_time", "")
            search_results.append({
                "content": item.get("memory", ""),
                "score": item.get("relativity", item.get("score", 0.0)),
                "user_id": user_id,
                "metadata": {
                    "memory_id": item.get("id", ""),
                    "created_at": str(created_at) if created_at else "",
                    "memory_type": item.get("memory_type", ""),
                    "confidence": item.get("confidence", 0.0),
                    "tags": item.get("tags", []),
                }
            })
        
        # Preference information already formatted
        pref_string = search_data.get("pref_string", "")
        
        return SearchResult(
            query=query,
            conversation_id=conversation_id,
            results=search_results,
            retrieval_metadata={
                "system": "memos",
                "preferences": {"pref_string": pref_string},
                "top_k": top_k,
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
        """
        Dual perspective search (for data with custom speaker names).
        
        Search memories for both speakers simultaneously and merge results.
        """
        
        try:
            # Search both user_ids separately
            search_a_results = self._search_single_user(query, speaker_a_user_id, top_k)
            search_b_results = self._search_single_user(query, speaker_b_user_id, top_k)
        except Exception as e:
            self.console.print(f"❌ Memos dual search error: {e}", style="red")
            return SearchResult(
                query=query,
                conversation_id=conversation_id,
                results=[],
                retrieval_metadata={
                    "error": str(e),
                    "user_ids": [speaker_a_user_id, speaker_b_user_id],
                    "dual_perspective": True,
                }
            )
        
        # Build detailed results list (add user_id to each memory)
        all_results = []
        
        # Speaker A's memories
        for memory in search_a_results["text_mem"][0]["memories"]:
            all_results.append({
                "content": memory.get("memory", ""),
                "score": memory.get("relativity", 0.0),
                "user_id": speaker_a_user_id,
                "metadata": {
                    "memory_id": memory.get("memory_id", ""),
                    "created_at": memory.get("created_at", ""),
                    "memory_type": memory.get("memory_type", ""),
                    "confidence": memory.get("confidence", 0.0),
                    "tags": memory.get("tags", []),
                }
            })
        
        # Speaker B's memories
        for memory in search_b_results["text_mem"][0]["memories"]:
            all_results.append({
                "content": memory.get("memory", ""),
                "score": memory.get("relativity", 0.0),
                "user_id": speaker_b_user_id,
                "metadata": {
                    "memory_id": memory.get("memory_id", ""),
                    "created_at": memory.get("created_at", ""),
                    "memory_type": memory.get("memory_type", ""),
                    "confidence": memory.get("confidence", 0.0),
                    "tags": memory.get("tags", []),
                }
            })
        
        # Merge memories and preferences from both speakers (for formatted_context)
        speaker_a_context = (
            "\n".join([i["memory"] for i in search_a_results["text_mem"][0]["memories"]])
            + f"\n{search_a_results.get('pref_string', '')}"
        )
        speaker_b_context = (
            "\n".join([i["memory"] for i in search_b_results["text_mem"][0]["memories"]])
            + f"\n{search_b_results.get('pref_string', '')}"
        )
        
        # Format using default template
        template = self._prompts["online_api"].get("templates", {}).get("default", "")
        formatted_context = template.format(
            speaker_1=speaker_a,
            speaker_1_memories=speaker_a_context,
            speaker_2=speaker_b,
            speaker_2_memories=speaker_b_context,
        )
        
        return SearchResult(
            query=query,
            conversation_id=conversation_id,
            results=all_results,
            retrieval_metadata={
                "system": "memos",
                "dual_perspective": True,
                "formatted_context": formatted_context,
                "top_k": top_k,
                "user_ids": [speaker_a_user_id, speaker_b_user_id],
                "preferences": {
                    "speaker_a_pref": search_a_results.get("pref_string", ""),
                    "speaker_b_pref": search_b_results.get("pref_string", ""),
                }
            }
        )
    def _get_answer_prompt(self) -> str:
        """
        Get answer prompt.
        
        Subclasses can override this method to return their own prompt.
        Defaults to generic default prompt.
        """
        return self._prompts["online_api"]["default"]["answer_prompt_memos"]

    def get_system_info(self) -> Dict[str, Any]:
        """Return system info."""
        return {
            "name": "Memos",
            "type": "online_api",
            "description": "Memos - Memory System with Preference Support",
            "adapter": "MemosAdapter",
        }


   