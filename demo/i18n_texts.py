"""国际化文本定义 - 支持中英文双语

本模块定义了对话系统所有界面文本的中英文版本。

使用方法：
    from i18n_texts import I18nTexts
    texts = I18nTexts("zh")  # 或 "en"
    print(texts.get("banner_title"))
"""

from typing import Dict, Any


class I18nTexts:
    """国际化文本管理器"""

    # 所有文本的中英文映射
    TEXTS: Dict[str, Dict[str, str]] = {
        # ==================== 语言选择 ====================
        "language_selection_title": {
            "zh": "🌏  语言选择 / Language Selection",
            "en": "🌏  Language Selection / 语言选择",
        },
        "language_prompt": {
            "zh": "请选择语言 (Select Language) [1-2]",
            "en": "Please select language [1-2]",
        },
        "language_chinese": {"zh": "中文", "en": "Chinese (中文)"},
        "language_english": {"zh": "英文 (English)", "en": "English"},
        "language_selected": {"zh": "已选择语言", "en": "Language selected"},
        "invalid_input_number": {
            "zh": "请输入有效的数字",
            "en": "Please enter a valid number",
        },
        # ==================== 场景模式选择 ====================
        "scenario_selection_title": {
            "zh": "🎯  场景模式选择",
            "en": "🎯  Scenario Mode Selection",
        },
        "scenario_prompt": {
            "zh": "请选择场景模式 [1-2]",
            "en": "Please select scenario mode [1-2]",
        },
        "scenario_assistant": {"zh": "助手模式", "en": "Assistant Mode"},
        "scenario_assistant_desc": {
            "zh": "单人对话，基于个人记忆的智能助手",
            "en": "One-on-one conversation with personal memory-based AI assistant",
        },
        "scenario_group_chat": {"zh": "群聊模式", "en": "Group Chat Mode"},
        "scenario_group_chat_desc": {
            "zh": "多人群聊，基于群组记忆的对话分析",
            "en": "Multi-person chat with group memory-based conversation analysis",
        },
        "scenario_selected": {"zh": "已选择场景模式", "en": "Scenario mode selected"},
        # ==================== 检索模式选择 ====================
        "retrieval_mode_selection_title": {
            "zh": "🔍  检索模式选择",
            "en": "🔍  Retrieval Mode Selection",
        },
        "retrieval_mode_prompt": {
            "zh": "请选择检索模式 [1-2]",
            "en": "Please select retrieval mode [1-2]",
        },
        "retrieval_mode_lightweight": {"zh": "轻量级检索", "en": "Lightweight Retrieval"},
        "retrieval_mode_lightweight_desc": {
            "zh": "快速检索，适合 demo 数据或小批量数据",
            "en": "Fast retrieval, suitable for demo or small-scale data",
        },
        "retrieval_mode_agentic": {"zh": "Agentic 检索", "en": "Agentic Retrieval"},
        "retrieval_mode_agentic_desc": {
            "zh": "智能多轮检索，提升检索效果，适合大规模数据",
            "en": "Multi-round intelligent retrieval, improves quality, suitable for large-scale data",
        },
        "retrieval_mode_selected": {"zh": "已选择检索模式", "en": "Retrieval mode selected"},
        "retrieval_mode_lightweight_note": {
            "zh": "💡 轻量级检索：速度快，成本低，适合 demo 演示和快速测试",
            "en": "💡 Lightweight: Fast and cost-effective, ideal for demos and quick tests",
        },
        "retrieval_mode_agentic_note": {
            "zh": "💡 Agentic 检索：质量高，包含多轮检索和 LLM 引导，适合生产环境和大规模数据",
            "en": "💡 Agentic: High quality with multi-round retrieval and LLM guidance, ideal for production and large datasets",
        },
        # ==================== 横幅和欢迎 ====================
        "banner_title": {
            "zh": "🧠  EverMem 记忆对话助手",
            "en": "🧠  EverMem Memory-Enhanced Chat Assistant",
        },
        "banner_subtitle": {
            "zh": "🤖 v1.0.0  ·  Memory-Enhanced Chat",
            "en": "🤖 v1.0.0  ·  Memory-Enhanced Chat",
        },
        "readline_available": {
            "zh": "支持方向键移动光标、删除字符，按 ↑↓ 浏览历史输入",
            "en": "Arrow keys supported for cursor movement, ↑↓ to browse input history",
        },
        "readline_unavailable": {
            "zh": "安装 readline 模块以支持更好的输入体验",
            "en": "Install readline module for better input experience",
        },
        # ==================== 群组选择 ====================
        "groups_available_title": {
            "zh": "📊  可用的群组对话",
            "en": "📊  Available Group Conversations",
        },
        "groups_not_found": {
            "zh": "未找到任何群组对话",
            "en": "No group conversations found",
        },
        "groups_extract_hint": {
            "zh": "提示：请先运行 extract_memory.py 提取记忆",
            "en": "Hint: Please run extract_memory.py to extract memories first",
        },
        "groups_select_prompt": {
            "zh": "请选择群组编号",
            "en": "Please select group number",
        },
        "groups_select_range_error": {
            "zh": "请输入 {min} 到 {max} 之间的数字",
            "en": "Please enter a number between {min} and {max}",
        },
        "groups_selection_cancelled": {
            "zh": "已取消群组选择",
            "en": "Group selection cancelled",
        },
        "groups_not_selected_exit": {
            "zh": "未选择群组，退出程序",
            "en": "No group selected, exiting program",
        },
        # ==================== 会话初始化 ====================
        "loading_group_data": {
            "zh": "正在加载群组 {name} 的数据...",
            "en": "Loading data for group {name}...",
        },
        "loading_profiles_warning": {
            "zh": "未找到用户 Profile 文件",
            "en": "User profile files not found",
        },
        "loading_profiles_hint": {
            "zh": "将继续使用记忆，但没有个人画像信息",
            "en": "Will continue with memories but without profile information",
        },
        "loading_profiles_success": {
            "zh": "个人画像: {count} 个用户 ({names})",
            "en": "Profiles: {count} users ({names})",
        },
        "loading_memories_success": {
            "zh": "群组记忆: {count} 条",
            "en": "Group memories: {count} items",
        },
        "loading_history_success": {
            "zh": "对话历史: {count} 轮（上次会话）",
            "en": "Conversation history: {count} rounds (last session)",
        },
        "loading_history_new": {
            "zh": "对话历史: 0 轮（新会话）",
            "en": "Conversation history: 0 rounds (new session)",
        },
        "loading_help_hint": {
            "zh": "输入 'help' 查看命令列表",
            "en": "Type 'help' to see command list",
        },
        "session_init_failed": {
            "zh": "会话初始化失败",
            "en": "Session initialization failed",
        },
        "session_init_error": {
            "zh": "会话初始化失败: {error}",
            "en": "Session initialization failed: {error}",
        },
        # ==================== 对话交互 ====================
        "chat_start_note": {
            "zh": "开始对话  |  输入 'help' 查看命令  |  输入 'exit' 退出",
            "en": "Start chatting  |  Type 'help' for commands  |  Type 'exit' to quit",
        },
        "chat_input_prompt": {"zh": "  💬 You: ", "en": "  💬 You: "},
        "chat_generating": {
            "zh": "正在思考并生成回答...",
            "en": "Thinking and generating response...",
        },
        "chat_generation_complete": {"zh": "生成完成", "en": "Generation complete"},
        "chat_llm_error": {
            "zh": "LLM 调用失败: {error}",
            "en": "LLM call failed: {error}",
        },
        "chat_error": {
            "zh": "对话处理失败: {error}",
            "en": "Chat processing failed: {error}",
        },
        # ==================== 检索结果 ====================
        "retrieval_title": {
            "zh": "检索到 {total} 条记忆",
            "en": "Retrieved {total} memories",
        },
        "retrieval_showing": {
            "zh": "（显示前 {shown} 条）",
            "en": "(showing first {shown} items)",
        },
        "retrieval_complete": {"zh": "检索完成", "en": "Retrieval Complete"},
        "retrieval_semantic": {
            "zh": "使用语义相似度进行检索",
            "en": "Using semantic similarity for retrieval",
        },
        "retrieval_latency": {
            "zh": "检索耗时: {latency}ms",
            "en": "Retrieval latency: {latency}ms",
        },
        "retrieval_multi_round": {
            "zh": "多轮检索（Round 1 → Round 2）",
            "en": "Multi-round retrieval (Round 1 → Round 2)",
        },
        "retrieval_single_round": {
            "zh": "单轮检索",
            "en": "Single-round retrieval",
        },
        "prompt_memory_episode": {"zh": "详情：{episode}", "en": "Details: {episode}"},
        # ==================== 命令处理 ====================
        "cmd_help_title": {"zh": "📖  可用命令", "en": "📖  Available Commands"},
        "cmd_exit": {
            "zh": "exit       退出对话（自动保存历史记录）",
            "en": "exit       Exit chat (auto-save history)",
        },
        "cmd_clear": {
            "zh": "clear      清空当前对话历史",
            "en": "clear      Clear current conversation history",
        },
        "cmd_reload": {
            "zh": "reload     重新加载记忆和画像数据",
            "en": "reload     Reload memories and profiles",
        },
        "cmd_reasoning": {
            "zh": "reasoning  查看上一次回答的完整推理过程",
            "en": "reasoning  View full reasoning of last response",
        },
        "cmd_help": {
            "zh": "help       显示此帮助信息",
            "en": "help       Show this help message",
        },
        "cmd_exit_saving": {
            "zh": "正在保存对话历史...",
            "en": "Saving conversation history...",
        },
        "cmd_exit_complete": {
            "zh": "保存完成，再见！",
            "en": "Save complete, goodbye!",
        },
        "cmd_clear_done": {
            "zh": "已清空 {count} 轮对话历史",
            "en": "Cleared {count} rounds of conversation history",
        },
        "cmd_reload_refreshing": {
            "zh": "正在刷新 {name} 的数据...",
            "en": "Refreshing data for {name}...",
        },
        "cmd_reload_complete": {
            "zh": "数据刷新完成：{users} 个用户，{memories} 条记忆",
            "en": "Data refresh complete: {users} users, {memories} memories",
        },
        "cmd_reasoning_no_data": {
            "zh": "暂无推理记录，请先提问",
            "en": "No reasoning record, please ask a question first",
        },
        "cmd_interrupt_saving": {
            "zh": "检测到中断信号，正在保存对话历史...",
            "en": "Interrupt detected, saving conversation history...",
        },
        # ==================== 结构化响应 ====================
        "response_reasoning_title": {
            "zh": "🧠  完整推理过程",
            "en": "🧠  Full Reasoning Process",
        },
        "response_answer_label": {"zh": "📝 回答内容", "en": "📝 Answer"},
        "response_reasoning_label": {"zh": "🔍 推理过程", "en": "🔍 Reasoning"},
        "response_metadata_label": {"zh": "📊 元数据", "en": "📊 Metadata"},
        "response_notes_label": {"zh": "💡 补充说明", "en": "💡 Additional Notes"},
        "response_confidence": {"zh": "置信度", "en": "Confidence"},
        "response_references": {"zh": "引用", "en": "References"},
        "response_no_references": {"zh": "无", "en": "None"},
        "response_assistant_title": {"zh": "🤖 Assistant", "en": "🤖 Assistant"},
        # ==================== 配置和连接 ====================
        "config_api_key_missing": {
            "zh": "LLM_API_KEY / OPENROUTER_API_KEY / OPENAI_API_KEY 未设置",
            "en": "LLM_API_KEY / OPENROUTER_API_KEY / OPENAI_API_KEY not set",
        },
        "config_api_key_hint": {
            "zh": "提示：请配置 API 密钥后重试",
            "en": "Hint: Please configure API key and retry",
        },
        "mongodb_connecting": {
            "zh": "连接 MongoDB...",
            "en": "Connecting to MongoDB...",
        },
        "mongodb_init_failed": {
            "zh": "MongoDB 初始化失败: {error}",
            "en": "MongoDB initialization failed: {error}",
        },
        # ==================== 表格标题 ====================
        "table_header_index": {"zh": "#", "en": "#"},
        "table_header_group": {"zh": "Group", "en": "Group"},
        "table_header_name": {"zh": "Name", "en": "Name"},
        "table_header_count": {"zh": "Count", "en": "Count"},
        # ==================== LLM Prompt (系统消息) ====================
        "prompt_system_role_zh": {
            "zh": """你是记忆增强 AI 助手，可访问用户画像与历史对话。请用温和、合作、尊重的中文回答。

目标：
- 基于记忆进行专业分析与推理，给出简洁可用的结论与建议。

工作原则：
- 严格区分「事实/推断/假设」，引用具体记忆编号；信息不足坦诚说明。
- 近期与用户显式更正优先于过往；避免无关或敏感外推。

推理流程（精简，必须遵循）：
1) 解析问题：识别意图、范围、限制与期望输出。
2) 检索记忆：从画像与历史中提取候选；按 相关性/时效性/一致性 评估；记录候选编号+要点。
   - 选择优先：显式陈述 > 近期 > 高频一致 > 权威；若冲突，指出并建议澄清。
3) 生成答案：在 answer 中先给 1–3 句结论（友好语气）；必要时附 1 条可执行建议。
   - 信息不足：说明缺口，并在答案末尾给至多 2 个简短澄清问题（括号内）。
   - 禁止在 answer 中出现编号、推理或内部术语。
4) 引用与信心：在 reasoning 中用 [n] 标注依据；references 列使用到的编号（去重、按出现顺序）。
   - confidence：high（≥2 条一致证据或强画像、无冲突）/ medium（单条或轻微冲突）/ low（证据不足或冲突明显）。

输出与格式（严格）：
- 仅输出有效 JSON；不得有任何额外文字或 Markdown。
- 所有字符串用双引号；换行写为 \\n。
- 必填：answer、reasoning、references、confidence；additional_notes 可选；无引用则 []。

Schema：
{
  "answer": "用户可见的直接结论，简洁专业",
  "reasoning": "任务解析→候选记忆→证据评估→推理链条→置信度判断；明确 事实/推断/假设，并用 [n] 标注依据",
  "references": ["[1]", "[3]"],
  "confidence": "high|medium|low",
  "additional_notes": "补充说明或建议（可选）"
}""",
            "en": """You are a memory-augmented AI assistant with access to user profiles and conversation history. Use a gentle, cooperative, respectful assistant tone to answer in English.

Goal:
- Provide concise, actionable conclusions and suggestions based on memory-driven professional analysis and reasoning.

Working Principles:
- Strictly distinguish \"Fact/Inference/Assumption\", cite specific memory numbers; be honest when information is insufficient.
- Prioritize recent explicit corrections by the user over older content; avoid irrelevant or sensitive extrapolations.

Reasoning Flow (concise, must follow):
1) Parse the task: identify intent, scope, constraints, and expected output.
2) Retrieve memories: extract candidates from profiles and history; evaluate by Relevance/Recency/Consistency; record candidate numbers + key points.
   - Selection priority: explicit statements > recent > high-frequency consistent > authoritative; if conflicts exist, point them out and suggest clarification.
3) Generate the answer: In the answer field, give a 1–3 sentence conclusion (friendly tone); add 1 actionable suggestion if necessary.
   - If information is insufficient: state the gap and append up to 2 short clarification questions at the end of the answer (in parentheses).
   - The answer must not include numbering, reasoning, or internal terminology.
4) Citations & confidence: In reasoning, mark evidence with [n]; in references, list the used numbers (deduplicated, ordered by first appearance).
   - confidence: high (≥2 consistent pieces of evidence or strong profile, no conflict) / medium (single piece or minor conflict) / low (insufficient evidence or clear conflict).

Output & Format (strict):
- Output valid JSON only; no extra text or Markdown.
- Use double quotes for all strings; write line breaks as \\n.
- Required: answer, reasoning, references, confidence; additional_notes optional; [] if no references.

Schema:
{
  "answer": "Direct conclusion for the user, concise and professional",
  "reasoning": "Task parsing → candidate memories → evidence evaluation → reasoning chain → confidence judgment; explicitly mark Fact/Inference/Assumption and use [n] for evidence",
  "references": ["[1]", "[3]"],
  "confidence": "high|medium|low",
  "additional_notes": "Optional supplementary notes or suggestions"
}""",
        },
        "prompt_system_role_en": {
            "zh": """你是记忆增强 AI 助手，可访问用户画像与历史对话。请用温和、合作、尊重的助理语气。你必须始终用英文回答。

目标：
- 基于记忆进行专业分析与推理，给出简洁可用的结论与建议。

工作原则：
- 严格区分「事实/推断/假设」，引用具体记忆编号；信息不足坦诚说明。
- 近期与用户显式更正优先于过往；避免无关或敏感外推。

推理流程（精简，必须遵循）：
1) 解析问题：识别意图、范围、限制与期望输出。
2) 检索记忆：从画像与历史中提取候选；按 相关性/时效性/一致性 评估；记录候选编号+要点。
   - 选择优先：显式陈述 > 近期 > 高频一致 > 权威；若冲突，指出并建议澄清。
3) 生成答案：在 answer 中先给 1–3 句结论（友好语气）；必要时附 1 条可执行建议。
   - 信息不足：说明缺口，并在答案末尾给至多 2 个简短澄清问题（括号内）。
   - 禁止在 answer 中出现编号、推理或内部术语。
4) 引用与信心：在 reasoning 中用 [n] 标注依据；references 列使用到的编号（去重、按出现顺序）。
   - confidence：high（≥2 条一致证据或强画像、无冲突）/ medium（单条或轻微冲突）/ low（证据不足或冲突明显）。

输出与格式（严格）：
- 仅输出有效 JSON；不得有任何额外文字或 Markdown。
- 所有字符串用双引号；换行写为 \\n。
- 必填：answer、reasoning、references、confidence；additional_notes 可选；无引用则 []。

Schema：
{
  "answer": "用户可见的直接结论，简洁专业",
  "reasoning": "任务解析→候选记忆→证据评估→推理链条→置信度判断；明确 事实/推断/假设，并用 [n] 标注依据",
  "references": ["[1]", "[3]"],
  "confidence": "high|medium|low",
  "additional_notes": "补充说明或建议（可选）"
}""",
            "en": """You are a memory-augmented AI assistant with access to user profiles and conversation history. Use a gentle, cooperative, respectful assistant tone to answer in English.

Goal:
- Provide concise, actionable conclusions and suggestions based on memory-driven professional analysis and reasoning.

Working Principles:
- Strictly distinguish \"Fact/Inference/Assumption\", cite specific memory numbers; be honest when information is insufficient.
- Prioritize recent explicit corrections by the user over older content; avoid irrelevant or sensitive extrapolations.

Reasoning Flow (concise, must follow):
1) Parse the task: identify intent, scope, constraints, and expected output.
2) Retrieve memories: extract candidates from profiles and history; evaluate by Relevance/Recency/Consistency; record candidate numbers + key points.
   - Selection priority: explicit statements > recent > high-frequency consistent > authoritative; if conflicts exist, point them out and suggest clarification.
3) Generate the answer: In the answer field, give a 1–3 sentence conclusion (friendly tone); add 1 actionable suggestion if necessary.
   - If information is insufficient: state the gap and append up to 2 short clarification questions at the end of the answer (in parentheses).
   - The answer must not include numbering, reasoning, or internal terminology.
4) Citations & confidence: In reasoning, mark evidence with [n]; in references, list the used numbers (deduplicated, ordered by first appearance).
   - confidence: high (≥2 consistent pieces of evidence or strong profile, no conflict) / medium (single piece or minor conflict) / low (insufficient evidence or clear conflict).

Output & Format (strict):
- Output valid JSON only; no extra text or Markdown.
- Use double quotes for all strings; write line breaks as \\n.
- Required: answer, reasoning, references, confidence; additional_notes optional; [] if no references.

Schema:
{
  "answer": "Direct conclusion for the user, concise and professional",
  "reasoning": "Task parsing → candidate memories → evidence evaluation → reasoning chain → confidence judgment; explicitly mark Fact/Inference/Assumption and use [n] for evidence",
  "references": ["[1]", "[3]"],
  "confidence": "high|medium|low",
  "additional_notes": "Optional supplementary notes or suggestions"
}""",
        },
        "prompt_profile_prefix_zh": {
            "zh": "用户的个人画像是：\n\n",
            "en": "User's personal profile is:\n\n",
        },
        "prompt_profile_prefix_en": {
            "zh": "个人画像（用于理解用户背景和推断岗位职责）：\n",
            "en": "Personal Profiles (for understanding user background and inferring job responsibilities):\n",
        },
        "prompt_memories_prefix": {
            "zh": "相关记忆（按相关度排序）：\n",
            "en": "Relevant Memories (sorted by relevance):\n",
        },
        "prompt_memory_date": {"zh": "{date}", "en": "{date}"},
        "prompt_memory_subject": {"zh": "主题：{subject}", "en": "Topic: {subject}"},
        "prompt_memory_content": {"zh": "内容：{content}", "en": "Content: {content}"},
        # ==================== 其他 ====================
        "loading_label": {"zh": "加载", "en": "Loading"},
        "warning_label": {"zh": "警告", "en": "Warning"},
        "hint_label": {"zh": "提示", "en": "Hint"},
        "error_label": {"zh": "错误", "en": "Error"},
        "save_label": {"zh": "保存", "en": "Save"},
        "success_label": {"zh": "成功", "en": "Success"},
    }

    def __init__(self, language: str = "zh"):
        """初始化国际化文本管理器

        Args:
            language: 语言代码，"zh" 或 "en"
        """
        self.language = language if language in ["zh", "en"] else "zh"

    def get(self, key: str, **kwargs) -> str:
        """获取指定键的文本

        Args:
            key: 文本键
            **kwargs: 格式化参数

        Returns:
            格式化后的文本
        """
        text_dict = self.TEXTS.get(key, {})
        text = text_dict.get(self.language, text_dict.get("zh", key))

        # 如果有格式化参数，进行格式化
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                # 如果格式化失败，返回原文本
                pass

        return text

    def set_language(self, language: str) -> None:
        """设置语言

        Args:
            language: 语言代码，"zh" 或 "en"
        """
        if language in ["zh", "en"]:
            self.language = language
