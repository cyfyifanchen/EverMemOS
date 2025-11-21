# 导入保留用于类型注解和字段定义
from elasticsearch.dsl import field as e_field
from core.oxm.es.doc_base import AliasDoc
from core.oxm.es.analyzer import (
    completion_analyzer,
    lower_keyword_analyzer,
    edge_analyzer,
    whitespace_lowercase_trim_stop_analyzer,
)


class EpisodicMemoryDoc(AliasDoc("episodic-memory", number_of_shards=3)):
    """
    情景记忆Elasticsearch文档

    基于MongoDB EpisodicMemory模型，用于高效的BM25文本检索。
    主要检索字段为title和episode的拼接内容。

    字段说明：
    - event_id: 事件唯一标识（对应MongoDB的_id）
    - user_id: 用户ID（必需，用于过滤）
    - user_name: 用户名称
    - timestamp: 事件发生时间
    - title: 事件标题（对应MongoDB的subject字段）
    - episode: 情景描述（核心内容）
    - search_content: BM25搜索字段（支持多值存储，用于精确词匹配）
    - summary: 事件摘要
    - group_id: 群组ID（可选）
    - participants: 参与者列表
    - type: 事件类型（Conversation等）
    - keywords: 关键词列表
    - linked_entities: 关联实体ID列表
    - extend: 扩展字段（灵活存储）

    分词处理说明：
    - 应用层负责中文分词（推荐使用jieba）
    - title、episode、summary字段存储预分词结果（空格分隔）
    - search_content字段支持多值存储，每个值是一个搜索词
    - ES使用standard分析器处理search_content，original子字段用于精确匹配
    - 搜索时使用terms查询在search_content.original字段中匹配多个词

    附属字段说明：
    - original: 精确匹配，小写处理
    - ik: IK智能分词（需要ES安装IK插件）
    - edge_completion: 前缀匹配和自动补全
    """

    class CustomMeta:
        # 指定用于自动填充 meta.id 的字段名
        id_source_field = "event_id"

    # 基础标识字段
    event_id = e_field.Keyword(required=True)
    user_id = e_field.Keyword()  # 群组记忆时为 None
    user_name = e_field.Keyword()

    # 时间字段
    timestamp = e_field.Date(required=True)

    # 核心内容字段 - BM25检索的主要目标
    title = e_field.Text(
        required=False,
        analyzer=whitespace_lowercase_trim_stop_analyzer,
        search_analyzer=whitespace_lowercase_trim_stop_analyzer,
        fields={
            "keyword": e_field.Keyword(),  # 精确匹配
            # "completion": e_field.Completion(analyzer=completion_analyzer),  # 自动补全
        },
    )

    episode = e_field.Text(
        required=True,
        analyzer=whitespace_lowercase_trim_stop_analyzer,
        search_analyzer=whitespace_lowercase_trim_stop_analyzer,
        fields={"keyword": e_field.Keyword()},  # 精确匹配
    )

    # BM25检索核心字段 - 支持多值存储的搜索内容
    # 应用层可以存储多个相关的搜索词或短语
    search_content = e_field.Text(
        multi=True,
        required=True,
        # star
        analyzer="standard",
        fields={
            # 原始内容字段 - 用于精确匹配，小写处理
            "original": e_field.Text(
                analyzer=lower_keyword_analyzer, search_analyzer=lower_keyword_analyzer
            ),
            # # IK智能分词字段 - 需要安装IK插件
            # "ik": e_field.Text(
            #     analyzer="ik_smart",
            #     search_analyzer="ik_smart"
            # ),
            # 边缘N-gram字段 - 用于前缀匹配和自动补全
            # "edge_completion": e_field.Text(
            #     analyzer=edge_analyzer,
            #     search_analyzer=lower_keyword_analyzer
            # ),
        },
    )

    # 摘要字段
    summary = e_field.Text(
        analyzer=whitespace_lowercase_trim_stop_analyzer,
        search_analyzer=whitespace_lowercase_trim_stop_analyzer,
    )

    # 分类和标签字段
    group_id = e_field.Keyword()  # 群组ID
    participants = e_field.Keyword(multi=True)

    type = e_field.Keyword()  # Conversation/Email/Notion等
    keywords = e_field.Keyword(multi=True)  # 关键词列表
    linked_entities = e_field.Keyword(multi=True)  # 关联实体ID列表

    subject = e_field.Text()  # 事件标题
    memcell_event_id_list = e_field.Keyword(multi=True)  # 记忆单元事件ID列表

    # 扩展字段
    extend = e_field.Object(dynamic=True)  # 灵活的扩展字段

    # 审计字段
    created_at = e_field.Date()
    updated_at = e_field.Date()
