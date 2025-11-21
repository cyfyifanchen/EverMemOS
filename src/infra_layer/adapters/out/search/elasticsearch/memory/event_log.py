# 导入保留用于类型注解和字段定义
from elasticsearch.dsl import field as e_field
from core.oxm.es.doc_base import AliasDoc
from core.oxm.es.analyzer import (
    completion_analyzer,
    lower_keyword_analyzer,
    edge_analyzer,
    whitespace_lowercase_trim_stop_analyzer,
)


class EventLogDoc(AliasDoc("event-log", number_of_shards=3)):
    """
    事件日志 Elasticsearch 文档
    
    使用独立的 event-log 索引。
    """
    class CustomMeta:
        # 指定用于自动填充 meta.id 的字段名
        id_source_field = "id"
    
    # 基础标识字段
    # id 字段通过 CustomMeta.id_source_field 自动从 kwargs 提取并设置为 meta.id
    user_id = e_field.Keyword()  
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
        },
    )

    episode = e_field.Text(
        required=True,
        analyzer=whitespace_lowercase_trim_stop_analyzer,
        search_analyzer=whitespace_lowercase_trim_stop_analyzer,
        fields={"keyword": e_field.Keyword()},  # 精确匹配
    )

    atomic_fact = e_field.Text(
        required=True,
        analyzer=whitespace_lowercase_trim_stop_analyzer,
        search_analyzer=whitespace_lowercase_trim_stop_analyzer,
        fields={"keyword": e_field.Keyword()},
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
        },
    )

    # 摘要字段
    summary = e_field.Text(
        analyzer=whitespace_lowercase_trim_stop_analyzer,
        search_analyzer=whitespace_lowercase_trim_stop_analyzer,
    )

    # 分类和标签字段
    group_id = e_field.Keyword()  # 群组ID
    group_name = e_field.Keyword()  # 群组名称
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

