"""Conversation Session Management

Manages conversation sessions for a single group, providing memory retrieval and LLM chat functionality.
"""

import json
import httpx
from typing import List, Dict, Any, Optional, Tuple
from datetime import timedelta
from pathlib import Path

from demo.config import ChatModeConfig, LLMConfig, ScenarioType
from demo.utils import query_memcells_by_group_and_time
from demo.ui import I18nTexts
from memory_layer.llm.llm_provider import LLMProvider
from common_utils.datetime_utils import get_now_with_timezone, to_iso_format


class ChatSession:
    """Conversation Session Manager"""

    def __init__(
        self,
        group_id: str,
        config: ChatModeConfig,
        llm_config: LLMConfig,
        scenario_type: ScenarioType,
        retrieval_mode: str,  # "rrf" / "embedding" / "bm25"
        data_source: str,  # "episode" / "event_log"
        texts: I18nTexts,
    ):
        """Initialize conversation session

        Args:
            group_id: Group ID
            config: Chat mode configuration
            llm_config: LLM configuration
            scenario_type: Scenario type
            retrieval_mode: Retrieval mode (rrf/embedding/bm25)
            data_source: Data source (episode/event_log)
            texts: I18nTexts object
        """
        self.group_id = group_id
        self.config = config
        self.llm_config = llm_config
        self.scenario_type = scenario_type
        self.retrieval_mode = retrieval_mode
        self.data_source = data_source
        self.texts = texts

        # Session State
        self.conversation_history: List[Tuple[str, str]] = []
        self.memcell_count: int = 0

        # Services
        self.llm_provider: Optional[LLMProvider] = None

        # API Configuration
        self.api_base_url = config.api_base_url
        self.retrieve_lightweight_url = (
            f"{self.api_base_url}/api/v3/agentic/retrieve_lightweight"
        )
        self.retrieve_agentic_url = (
            f"{self.api_base_url}/api/v3/agentic/retrieve_agentic"
        )

        # Last Retrieval Metadata
        self.last_retrieval_metadata: Optional[Dict[str, Any]] = None

    async def initialize(self) -> bool:
        """Initialize session

        Returns:
            Whether initialization was successful
        """
        try:
            display_name = (
                "group_chat"
                if self.group_id == "AI产品群"  # skip-i18n-check
                else self.group_id
            )
            print(
                f"\n[{self.texts.get('loading_label')}] {self.texts.get('loading_group_data', name=display_name)}"
            )

            # Check API Server Health
            await self._check_api_server()

            # Count MemCells
            now = get_now_with_timezone()
            start_date = now - timedelta(days=self.config.time_range_days)
            memcells = await query_memcells_by_group_and_time(
                self.group_id, start_date, now
            )
            self.memcell_count = len(memcells)
            print(
                f"[{self.texts.get('loading_label')}] {self.texts.get('loading_memories_success', count=self.memcell_count)} ✅"
            )

            # Load Conversation History
            loaded_history_count = await self.load_conversation_history()
            if loaded_history_count > 0:
                print(
                    f"[{self.texts.get('loading_label')}] {self.texts.get('loading_history_success', count=loaded_history_count)} ✅"
                )
            else:
                print(
                    f"[{self.texts.get('loading_label')}] {self.texts.get('loading_history_new')} ✅"
                )

            # Create LLM Provider
            self.llm_provider = LLMProvider(
                self.llm_config.provider,
                model=self.llm_config.model,
                api_key=self.llm_config.api_key,
                base_url=self.llm_config.base_url,
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens,
            )

            print(
                f"\n[{self.texts.get('hint_label')}] {self.texts.get('loading_help_hint')}\n"
            )
            return True

        except Exception as e:
            print(
                f"\n[{self.texts.get('error_label')}] {self.texts.get('session_init_error', error=str(e))}"
            )
            import traceback

            traceback.print_exc()
            return False

    async def _check_api_server(self) -> None:
        """Check if API server is running

        Raises:
            ConnectionError: If server is not running
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try accessing health check endpoint or any endpoint
                response = await client.get(f"{self.api_base_url}/docs")
                if response.status_code >= 500:
                    raise ConnectionError("API Server returned error")
        except (httpx.ConnectError, httpx.TimeoutException, ConnectionError) as e:
            error_msg = (
                f"\n❌ Cannot connect to API server: {self.api_base_url}\n\n"
                f"Please start V3 API server first:\n"
                f"  uv run python src/run.py --port 8001\n\n"
                f"Then run the chat application in another terminal.\n"
            )
            raise ConnectionError(error_msg) from e

    async def load_conversation_history(self) -> int:
        """Load conversation history from file

        Returns:
            Number of loaded conversation turns
        """
        try:
            display_name = (
                "group_chat"
                if self.group_id == "AI产品群"  # skip-i18n-check
                else self.group_id
            )
            history_files = sorted(
                self.config.chat_history_dir.glob(f"{display_name}_*.json"),
                reverse=True,
            )

            if not history_files:
                return 0

            latest_file = history_files[0]
            with latest_file.open("r", encoding="utf-8") as fp:
                data = json.load(fp)

            history = data.get("conversation_history", [])
            self.conversation_history = [
                (item["user_input"], item["assistant_response"])
                for item in history[-self.config.conversation_history_size :]
            ]

            return len(self.conversation_history)

        except Exception as e:
            print(
                f"[{self.texts.get('warning_label')}] {self.texts.get('loading_history_new')}: {e}"
            )
            return 0

    async def save_conversation_history(self) -> None:
        """Save conversation history to file"""
        try:
            display_name = (
                "group_chat"
                if self.group_id == "AI产品群"  # skip-i18n-check
                else self.group_id
            )
            timestamp = get_now_with_timezone().strftime("%Y-%m-%d_%H-%M")
            filename = f"{display_name}_{timestamp}.json"
            filepath = self.config.chat_history_dir / filename

            data = {
                "group_id": self.group_id,
                "last_updated": get_now_with_timezone().isoformat(),
                "conversation_history": [
                    {
                        "timestamp": get_now_with_timezone().isoformat(),
                        "user_input": user_q,
                        "assistant_response": assistant_a,
                    }
                    for user_q, assistant_a in self.conversation_history
                ],
            }

            with filepath.open("w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)

            print(f"[{self.texts.get('save_label')}] {filename} ✅")

        except Exception as e:
            print(f"[{self.texts.get('error_label')}] {e}")

    async def retrieve_memories(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve relevant memories - via HTTP API call

        Args:
            query: User query

        Returns:
            List of retrieved memories
        """
        # 🔥 Select HTTP API endpoint based on retrieval mode
        if self.retrieval_mode == "agentic":
            # Agentic Retrieval API
            result = await self._call_retrieve_agentic_api(query)
        else:
            # Lightweight Retrieval API
            result = await self._call_retrieve_lightweight_api(query)

        # Extract results and metadata
        memories = result.get("memories", [])
        metadata = result.get("metadata", {})

        # Save metadata (for UI display)
        self.last_retrieval_metadata = metadata

        return memories

    async def _call_retrieve_lightweight_api(self, query: str) -> Dict[str, Any]:
        """Call Lightweight Retrieval API (aligned with test_v3_retrieve_http.py)

        Args:
            query: User query

        Returns:
            Retrieval result dictionary
        """
        # 🔥 Critical: Decide whether to pass user_id based on scenario type
        # - Group chat scenario: Don't pass user_id, retrieve group-level memories
        # - Assistant scenario: Can pass user_id to retrieve specific user memories
        payload = {
            "query": query,
            "group_id": self.group_id,  # Pass group ID for filtering
            "top_k": self.config.top_k_memories,
            "data_source": self.data_source,  # episode / event_log
            "retrieval_mode": self.retrieval_mode,  # rrf / embedding / bm25
        }
        # Group chat scenario: Don't pass user_id, retrieve group-level shared memories
        # Assistant scenario: Can pass user_id for personal memories (currently not passing, using group memories)

        # Debug logs (shown only in dev environment)
        # print(f"\n[DEBUG] Lightweight Retrieval Request:")
        # print(f"  - API URL: {self.retrieve_lightweight_url}")
        # print(f"  - query: {query}")
        # print(f"  - user_id: user_001")
        # print(f"  - retrieval_mode: {self.retrieval_mode}")
        # print(f"  - data_source: {self.data_source}")
        # print(f"  - memory_scope: all")
        # print(f"  - top_k: {self.config.top_k_memories}")

        try:
            # 🔥 Consistent with test_v3_retrieve_http.py: verify=False, timeout=30.0
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(
                    self.retrieve_lightweight_url, json=payload
                )
                response.raise_for_status()
                api_response = response.json()

                # Check API response status
                if api_response.get("status") == "ok":
                    result = api_response.get(
                        "result", {"memories": [], "metadata": {}}
                    )
                    # memories_count = len(result.get("memories", []))
                    # print(f"  ✅ Retrieval success: {memories_count} memories")
                    return result
                else:
                    error_msg = api_response.get('message', 'Unknown error')
                    # print(f"  ❌ API Error: {error_msg}")
                    raise RuntimeError(f"API Error: {error_msg}")

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            raise RuntimeError(error_msg)
        except httpx.TimeoutException:
            error_msg = "Request timeout (over 30s)"
            raise RuntimeError(error_msg)
        except httpx.ConnectError as e:
            error_msg = f"Connection failed: Cannot connect to {self.api_base_url}\nPlease ensure V3 API service is started: uv run python src/bootstrap.py src/run.py --port 8001"
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Retrieval failed: {type(e).__name__}: {e}"
            raise RuntimeError(error_msg)

    async def _call_retrieve_agentic_api(self, query: str) -> Dict[str, Any]:
        """Call Agentic Retrieval API (aligned with test_v3_retrieve_http.py)

        Args:
            query: User query

        Returns:
            Retrieval result dictionary
        """
        # 🔥 Critical: Decide whether to pass user_id based on scenario type
        # - Group chat scenario: Don't pass user_id, retrieve group-level memories
        # - Assistant scenario: Can pass user_id to retrieve specific user memories
        payload = {
            "query": query,
            "group_id": self.group_id,  # Pass group ID for filtering
            "top_k": self.config.top_k_memories,
            "time_range_days": self.config.time_range_days,  # Use configured time range
        }
        # Group chat scenario: Don't pass user_id, retrieve group-level shared memories

        # Debug logs (shown only in dev environment)
        # print(f"\n[DEBUG] Agentic Retrieval Request:")
        # print(f"  - API URL: {self.retrieve_agentic_url}")
        # print(f"  - query: {query}")
        # print(f"  - user_id: user_001")
        # print(f"  - top_k: {self.config.top_k_memories}")
        # print(f"  - time_range_days: {self.config.time_range_days}")

        # Show friendly wait hint (Internationalized)
        print(f"\n⏳ {self.texts.get('agentic_retrieving')}")

        try:
            # 🔥 Agentic retrieval takes longer: increased to 180s (3 mins)
            # Because it involves LLM calls, sufficiency judgment, multi-round retrieval etc.
            async with httpx.AsyncClient(timeout=180.0, verify=False) as client:
                response = await client.post(self.retrieve_agentic_url, json=payload)
                response.raise_for_status()
                api_response = response.json()

                # Check API response status
                if api_response.get("status") == "ok":
                    result = api_response.get(
                        "result", {"memories": [], "metadata": {}}
                    )
                    # memories_count = len(result.get("memories", []))
                    # print(f"  ✅ Retrieval success: {memories_count} memories")
                    return result
                else:
                    error_msg = api_response.get('message', 'Unknown error')
                    # print(f"  ❌ API Error: {error_msg}")
                    raise RuntimeError(f"API Error: {error_msg}")

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            raise RuntimeError(error_msg)
        except httpx.TimeoutException:
            error_msg = "Request timeout (over 180s)\nHint: Agentic retrieval involves LLM calls and multi-round retrieval, taking longer\nSuggestion: Use RRF/Embedding/BM25 retrieval modes (faster)"
            raise RuntimeError(error_msg)
        except httpx.ConnectError as e:
            error_msg = f"Connection failed: Cannot connect to {self.api_base_url}\nPlease ensure V3 API service is started: uv run python src/bootstrap.py src/run.py --port 8001"
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Agentic retrieval failed: {type(e).__name__}: {e}"
            raise RuntimeError(error_msg)

    def build_prompt(
        self, user_query: str, memories: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Build Prompt

        Args:
            user_query: User query
            memories: Retrieved memory list

        Returns:
            List of Chat Messages
        """
        messages = []

        # System Message
        lang_key = "zh" if self.texts.language == "zh" else "en"
        system_content = self.texts.get(f"prompt_system_role_{lang_key}")
        messages.append({"role": "system", "content": system_content})

        # Retrieved Memories
        if memories:
            memory_lines = []
            for i, mem in enumerate(memories, start=1):
                # Use datetime_utils to uniformly handle time format
                raw_timestamp = mem.get("timestamp", "")
                iso_timestamp = to_iso_format(raw_timestamp)
                # Only take date part (first 10 characters, e.g., 2025-12-04)
                timestamp = iso_timestamp[:10] if iso_timestamp else ""
                subject = mem.get("subject", "")
                summary = mem.get("summary", "")
                episode = mem.get("episode", "")

                parts = [
                    f"[{i}] {self.texts.get('prompt_memory_date', date=timestamp)}"
                ]
                if subject:
                    parts.append(
                        self.texts.get("prompt_memory_subject", subject=subject)
                    )
                if summary:
                    parts.append(
                        self.texts.get("prompt_memory_content", content=summary)
                    )
                if episode:
                    parts.append(
                        self.texts.get("prompt_memory_episode", episode=episode)
                    )

                memory_lines.append(" | ".join(parts))

            memory_content = self.texts.get("prompt_memories_prefix") + "\n".join(
                memory_lines
            )
            messages.append({"role": "system", "content": memory_content})

        # Conversation History
        for user_q, assistant_a in self.conversation_history[
            -self.config.conversation_history_size :
        ]:
            messages.append({"role": "user", "content": user_q})
            messages.append({"role": "assistant", "content": assistant_a})

        # Current Question
        messages.append({"role": "user", "content": user_query})

        return messages

    async def chat(self, user_input: str) -> str:
        """Core Chat Logic

        Args:
            user_input: User input

        Returns:
            Assistant response
        """
        from .ui import ChatUI

        # Retrieve Memories
        memories = await self.retrieve_memories(user_input)

        # Show Retrieval Results
        if self.config.show_retrieved_memories and memories:
            ChatUI.print_retrieved_memories(
                memories[:5],
                texts=self.texts,
                retrieval_metadata=self.last_retrieval_metadata,
            )

        # Build Prompt
        messages = self.build_prompt(user_input, memories)

        # Show Generation Progress
        ChatUI.print_generating_indicator(self.texts)

        # Call LLM
        try:
            if hasattr(self.llm_provider, 'provider') and hasattr(
                self.llm_provider.provider, 'chat_with_messages'
            ):
                raw_response = await self.llm_provider.provider.chat_with_messages(
                    messages
                )
            else:
                prompt_parts = []
                for msg in messages:
                    role = msg["role"]
                    content = msg["content"]
                    if role == "system":
                        prompt_parts.append(f"System: {content}")
                    elif role == "user":
                        prompt_parts.append(f"User: {content}")
                    elif role == "assistant":
                        prompt_parts.append(f"Assistant: {content}")

                prompt = "\n\n".join(prompt_parts)
                raw_response = await self.llm_provider.generate(prompt)

            raw_response = raw_response.strip()

            # Clear Generation Progress
            ChatUI.print_generation_complete(self.texts)

            assistant_response = raw_response

        except Exception as e:
            ChatUI.clear_progress_indicator()
            error_msg = f"[{self.texts.get('error_label')}] {self.texts.get('chat_llm_error', error=str(e))}"
            print(f"\n{error_msg}")
            import traceback

            traceback.print_exc()
            return error_msg

        # Update Conversation History
        self.conversation_history.append((user_input, assistant_response))

        if len(self.conversation_history) > self.config.conversation_history_size:
            self.conversation_history = self.conversation_history[
                -self.config.conversation_history_size :
            ]

        return assistant_response

    def clear_history(self) -> None:
        """Clear conversation history"""
        from .ui import ChatUI

        count = len(self.conversation_history)
        self.conversation_history = []
        ChatUI.print_info(self.texts.get("cmd_clear_done", count=count), self.texts)

    async def reload_data(self) -> None:
        """Reload memory data"""
        from .ui import ChatUI
        from common_utils.cli_ui import CLIUI

        display_name = (
            "group_chat"
            if self.group_id == "AI产品群"  # skip-i18n-check
            else self.group_id
        )

        ui = CLIUI()
        print()
        ui.note(self.texts.get("cmd_reload_refreshing", name=display_name), icon="🔄")

        # Recount MemCells
        now = get_now_with_timezone()
        start_date = now - timedelta(days=self.config.time_range_days)
        memcells = await query_memcells_by_group_and_time(
            self.group_id, start_date, now
        )
        self.memcell_count = len(memcells)

        print()
        ui.success(
            f"✓ {self.texts.get('cmd_reload_complete', users=0, memories=self.memcell_count)}"
        )
        print()
