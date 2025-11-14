"""
Online API Adapter base class.

Provides common functionality for all online memory system APIs (Mem0, Memos, Memu, etc.).
All online API adapters can inherit from this class.

Design principles:
- Provide default answer() implementation (using generic prompt)
- Subclasses can override answer() to use their own specific prompts
- Provide helper methods for data format conversion
"""
from abc import abstractmethod
from pathlib import Path
from typing import Any, List, Dict, Optional

from evaluation.src.adapters.base import BaseAdapter
from evaluation.src.core.data_models import Conversation, SearchResult
from evaluation.src.utils.config import load_yaml

# Import Memory Layer components
from memory_layer.llm.llm_provider import LLMProvider


class OnlineAPIAdapter(BaseAdapter):
    """
    Online API Adapter base class.
    
    Provides common functionality:
    1. LLM Provider initialization
    2. Answer generation (reuses EverMemOS implementation)
    3. Standard format conversion helper methods
    
    Subclasses only need to implement:
    - add(): Call online API to ingest data
    - search(): Call online API for retrieval
    """
    
    def __init__(self, config: dict, output_dir: Path = None):
        super().__init__(config)
        self.output_dir = Path(output_dir) if output_dir else Path(".")
        
        # Initialize LLM Provider (for answer generation)
        llm_config = config.get("llm", {})
        
        self.llm_provider = LLMProvider(
            provider_type=llm_config.get("provider", "openai"),
            model=llm_config.get("model", "gpt-4o-mini"),
            api_key=llm_config.get("api_key", ""),
            base_url=llm_config.get("base_url", "https://api.openai.com/v1"),
            temperature=llm_config.get("temperature", 0.3),
            max_tokens=llm_config.get("max_tokens", 32768),
        )
        
        # Load prompts (from YAML file)
        evaluation_root = Path(__file__).parent.parent.parent
        prompts_path = evaluation_root / "config" / "prompts.yaml"
        self._prompts = load_yaml(str(prompts_path))
        
        print(f"✅ {self.__class__.__name__} initialized")
        print(f"   LLM Model: {llm_config.get('model')}")
        print(f"   Output Dir: {self.output_dir}")
    
    @abstractmethod
    async def add(
        self, 
        conversations: List[Conversation],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Ingest conversation data (call online API).
        
        Subclasses must implement this method.
        """
        pass
    
    @abstractmethod
    async def search(
        self, 
        query: str,
        conversation_id: str,
        index: Any,
        **kwargs
    ) -> SearchResult:
        """
        Retrieve relevant memories (call online API).
        
        Subclasses must implement this method.
        """
        pass
    
    async def answer(self, query: str, context: str, **kwargs) -> str:
        """
        Generate answer (using generic MEMOS prompt).
        
        Subclasses can override this method to use their own specific prompt.
        Defaults to ANSWER_PROMPT_MEMOS (suitable for most systems).
        """
        # Get answer prompt (subclasses can override _get_answer_prompt)
        prompt = self._get_answer_prompt().format(context=context, question=query)
        
        # Get retry count
        max_retries = self.config.get("answer", {}).get("max_retries", 3)
        
        # Generate answer
        for i in range(max_retries):
            try:
                result = await self.llm_provider.generate(
                    prompt=prompt,
                    temperature=0,
                    max_tokens=32768,
                )
                
                # Clean result (remove possible "FINAL ANSWER:" prefix)
                if "FINAL ANSWER:" in result:
                    parts = result.split("FINAL ANSWER:")
                    if len(parts) > 1:
                        result = parts[1].strip()
                    else:
                        result = result.strip()
                else:
                    result = result.strip()
                
                if result == "":
                    continue
                
                return result
            except Exception as e:
                print(f"⚠️  Answer generation error (attempt {i+1}/{max_retries}): {e}")
                if i == max_retries - 1:
                    raise
                continue
        
        return ""
    
    def _get_answer_prompt(self) -> str:
        """
        Get answer prompt.
        
        Subclasses can override this method to return their own prompt.
        Defaults to generic default prompt.
        """
        return self._prompts["online_api"]["default"]["answer_prompt_memos"]
    
    # ===== Helper methods: format conversion =====
    
    def _conversation_to_messages(
        self, 
        conversation: Conversation,
        format_type: str = "basic",
        perspective: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert standard Conversation to message list.
        
        Args:
            conversation: Standard conversation object
            format_type: Format type (basic, mem0, memos, memu)
            perspective: Perspective (speaker_a or speaker_b), used for dual-perspective systems like Memos
        
        Returns:
            Message list
        """
        messages = []
        speaker_a = conversation.metadata.get("speaker_a", "")
        speaker_b = conversation.metadata.get("speaker_b", "")
        
        for msg in conversation.messages:
            # Intelligently determine role and content
            role, content = self._determine_role_and_content(
                msg.speaker_name, 
                msg.content,
                speaker_a,
                speaker_b,
                perspective
            )
            
            # Base message
            message = {
                "role": role,
                "content": content,
            }
            
            # Add extra fields based on different system requirements
            if format_type == "mem0":
                # Mem0 format: needs timestamp
                if msg.timestamp:
                    from common_utils.datetime_utils import to_iso_format
                    message["timestamp"] = to_iso_format(msg.timestamp)
            
            elif format_type == "memos":
                # Memos format: needs chat_time
                if msg.timestamp:
                    from common_utils.datetime_utils import to_iso_format
                    message["chat_time"] = to_iso_format(msg.timestamp)
            
            elif format_type == "memu":
                # Memu format: needs created_at
                if msg.timestamp:
                    from common_utils.datetime_utils import to_iso_format
                    message["created_at"] = to_iso_format(msg.timestamp)
            
            messages.append(message)
        
        return messages
    
    def _determine_role_and_content(
        self,
        speaker_name: str,
        content: str,
        speaker_a: str,
        speaker_b: str,
        perspective: Optional[str] = None
    ) -> tuple:
        """
        Intelligently determine message role and content.
        
        For systems that only support user/assistant (e.g., Memos), special handling is needed:
        1. If speaker is standard role (user/assistant and variants), use directly
        2. If custom name, convert based on perspective:
           - From speaker_a perspective: speaker_a messages are "user", speaker_b are "assistant"
           - From speaker_b perspective: speaker_b messages are "user", speaker_a are "assistant"
        3. Content for custom speakers needs "speaker: " prefix
        
        Args:
            speaker_name: Speaker name
            content: Message content
            speaker_a: speaker_a in conversation
            speaker_b: speaker_b in conversation
            perspective: Perspective (for dual-perspective systems)
        
        Returns:
            (role, content) tuple
        """
        # Case 1: Standard roles (user/assistant and variants)
        speaker_lower = speaker_name.lower()
        
        # Check if standard role or variant
        if speaker_lower in ["user", "assistant"]:
            # Exact match: "user", "User", "assistant", "Assistant"
            return speaker_lower, content
        elif speaker_lower.startswith("user"):
            # Variants: "user_123", "User_456", etc.
            return "user", content
        elif speaker_lower.startswith("assistant"):
            # Variants: "assistant_123", "Assistant_456", etc.
            return "assistant", content
        
        # Case 2: Custom speaker, needs conversion
        # Default behavior: speaker_a is user, speaker_b is assistant
        if perspective == "speaker_b":
            # From speaker_b's perspective
            if speaker_name == speaker_b:
                role = "user"
            elif speaker_name == speaker_a:
                role = "assistant"
            else:
                # Unknown speaker, default to assistant
                role = "assistant"
        else:
            # From speaker_a's perspective (default)
            if speaker_name == speaker_a:
                role = "user"
            elif speaker_name == speaker_b:
                role = "assistant"
            else:
                # Unknown speaker, default to user
                role = "user"
        
        # For custom speakers, content needs prefix
        formatted_content = f"{speaker_name}: {content}"
        
        return role, formatted_content
    
    def _extract_user_id(self, conversation: Conversation, speaker: str = "speaker_a") -> str:
        """
        Extract user_id from Conversation (for online API).
        
        Logic: Combine conversation_id and speaker name to ensure conversation isolation.
        
        Args:
            conversation: Standard conversation object
            speaker: Speaker identifier (speaker_a or speaker_b)
        
        Returns:
            user_id string, format: {conv_id}_{speaker_name}
        
        Examples:
            - LoCoMo: speaker_a="Caroline" → user_id="locomo_0_Caroline"
            - PersonaMem: speaker_a="Kanoa Manu" → user_id="personamem_0_Kanoa_Manu"
            - No speaker: → user_id="locomo_0_speaker_a"
        
        Design rationale:
            - Include conv_id: Ensure memory isolation between conversations (evaluation accuracy)
            - Include speaker name: More intuitive for backend viewing (e.g., Caroline vs speaker_a)
            - Replace spaces with underscores: Avoid spaces in user_id
        """
        conv_id = conversation.conversation_id
        speaker_name = conversation.metadata.get(speaker)
        
        if speaker_name:
            # Has speaker name: replace spaces with underscores
            speaker_name_normalized = speaker_name.replace(" ", "_")
            user_id = f"{conv_id}_{speaker_name_normalized}"
        else:
            # No speaker name: locomo_0_speaker_a
            user_id = f"{conv_id}_{speaker}"
        
        return user_id
    
    def _get_user_id_from_conversation_id(self, conversation_id: str) -> str:
        """
        Derive user_id from conversation_id (simplified version).
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            user_id string
        """
        # Simplified implementation: directly use conversation_id
        # May need more complex mapping logic in actual use
        return conversation_id
    
    def get_system_info(self) -> Dict[str, Any]:
        """Return system info."""
        return {
            "name": self.__class__.__name__,
            "type": "online_api",
            "description": f"{self.__class__.__name__} adapter for online memory API",
        }

