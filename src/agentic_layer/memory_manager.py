from __future__ import annotations

from typing import Any, List, Optional, Tuple
import logging
import asyncio

from datetime import datetime, timedelta
import jieba
import numpy as np
import time
from typing import Dict, Any
from dataclasses import dataclass

from api_specs.memory_types import BaseMemory, EpisodeMemory, EventLog, Foresight, RawDataType
from biz_layer.mem_memorize import memorize
from api_specs.dtos.memory_command import MemorizeRequest
from .fetch_mem_service import get_fetch_memory_service
from api_specs.dtos.memory_query import (
    FetchMemRequest,
    FetchMemResponse,
    RetrieveMemRequest,
    RetrieveMemResponse,
    Metadata,
)
from core.di import get_bean_by_type
from infra_layer.adapters.out.search.repository.episodic_memory_es_repository import (
    EpisodicMemoryEsRepository,
)
from infra_layer.adapters.out.search.repository.foresight_es_repository import (
    ForesightEsRepository,
)
from infra_layer.adapters.out.search.repository.event_log_es_repository import (
    EventLogEsRepository,
)
from core.observation.tracing.decorators import trace_logger
from core.nlp.stopwords_utils import filter_stopwords
from common_utils.datetime_utils import from_iso_format, get_now_with_timezone
from infra_layer.adapters.out.persistence.repository.memcell_raw_repository import (
    MemCellRawRepository,
)
from infra_layer.adapters.out.persistence.repository.group_user_profile_memory_raw_repository import (
    GroupUserProfileMemoryRawRepository,
)
from infra_layer.adapters.out.persistence.document.memory.memcell import DataTypeEnum
from infra_layer.adapters.out.persistence.document.memory.user_profile import (
    UserProfile,
)
from infra_layer.adapters.out.search.repository.episodic_memory_milvus_repository import (
    EpisodicMemoryMilvusRepository,
)
from infra_layer.adapters.out.search.repository.foresight_milvus_repository import (
    ForesightMilvusRepository,
)
from infra_layer.adapters.out.search.repository.event_log_milvus_repository import (
    EventLogMilvusRepository,
)
from .vectorize_service import get_vectorize_service
from .rerank_service import get_rerank_service
from api_specs.memory_models import MemoryType, RetrieveMethod

logger = logging.getLogger(__name__)


@dataclass
class EventLogCandidate:
    """Event Log candidate object (used for retrieval from atomic_fact)"""

    event_id: str
    user_id: str
    group_id: str
    timestamp: datetime
    episode: str  # atomic_fact content
    summary: str
    subject: str
    extend: dict  # contains embedding


class MemoryManager:
    """Unified memory interface.

    Provides the following main functions:
    - memorize: Accept raw data and persistently store
    - fetch_mem: Retrieve memory fields by key, supports multiple memory types
    - retrieve_mem: Memory reading based on prompt-based retrieval methods
    """

    def __init__(self) -> None:
        # Get memory service instance
        self._fetch_service = get_fetch_memory_service()

        logger.info(
            "MemoryManager initialized with fetch_mem_service and retrieve_mem_service"
        )

    # --------- Write path (raw data -> memorize) ---------
    @trace_logger(operation_name="agentic_layer memory storage")
    async def memorize(self, memorize_request: MemorizeRequest) -> int:
        """Memorize a heterogeneous list of raw items.

        Accepts list[Any], where each item can be one of the typed raw dataclasses
        (ChatRawData / EmailRawData / MemoRawData / LincDocRawData) or any dict-like
        object. Each item is stored as a MemoryCell with a synthetic key.
        
        Returns:
            int: Number of memories extracted (0 if no boundary detected)
        """
        count = await memorize(memorize_request)
        return count

    # --------- Read path (query -> fetch_mem) ---------
    # Memory reading based on key-value, including static and dynamic memory
    @trace_logger(operation_name="agentic_layer memory reading")
    async def fetch_mem(self, request: FetchMemRequest) -> FetchMemResponse:
        """Retrieve memory data, supports multiple memory types

        Args:
            request: FetchMemRequest containing query parameters

        Returns:
            FetchMemResponse containing query results
        """
        logger.debug(
            f"fetch_mem called with request: user_id={request.user_id}, memory_type={request.memory_type}"
        )

        # repository supports MemoryType.MULTIPLE type, default is corememory
        response = await self._fetch_service.find_by_user_id(
            user_id=request.user_id,
            memory_type=request.memory_type,
            version_range=request.version_range,
            limit=request.limit,
        )

        # Note: response.metadata already contains complete employee information via _get_employee_metadata
        # including source, user_id, memory_type, limit, email, phone, full_name
        # No need to update again here, as fetch_mem_service already provides correct information

        logger.debug(
            f"fetch_mem returned {len(response.memories)} memories for user {request.user_id}"
        )
        return response

    # Memory reading based on retrieve_method, including static and dynamic memory
    @trace_logger(operation_name="agentic_layer memory retrieval")
    async def retrieve_mem(
        self, retrieve_mem_request: 'RetrieveMemRequest'
    ) -> RetrieveMemResponse:
        """Retrieve memory data, dispatching to different retrieval methods based on retrieve_method

        Args:
            retrieve_mem_request: RetrieveMemRequest containing retrieval parameters

        Returns:
            RetrieveMemResponse containing retrieval results
        """
        try:
            # Validate request parameters
            if not retrieve_mem_request:
                raise ValueError("retrieve_mem_request is required for retrieve_mem")

            # Dispatch based on retrieve_method
            from api_specs.memory_models import RetrieveMethod

            retrieve_method = retrieve_mem_request.retrieve_method

            logger.info(
                f"retrieve_mem dispatching request: user_id={retrieve_mem_request.user_id}, "
                f"retrieve_method={retrieve_method}, query={retrieve_mem_request.query}"
            )

            # Dispatch based on retrieval method
            if retrieve_method == RetrieveMethod.KEYWORD:
                # Keyword retrieval
                return await self.retrieve_mem_keyword(retrieve_mem_request)
            elif retrieve_method == RetrieveMethod.VECTOR:
                # Vector retrieval
                return await self.retrieve_mem_vector(retrieve_mem_request)
            elif retrieve_method == RetrieveMethod.HYBRID:
                # Hybrid retrieval
                return await self.retrieve_mem_hybrid(retrieve_mem_request)
            else:
                raise ValueError(f"Unsupported retrieval method: {retrieve_method}")

        except Exception as e:
            logger.error(f"Error in retrieve_mem: {e}", exc_info=True)
            return RetrieveMemResponse(
                memories=[],
                original_data=[],
                scores=[],
                importance_scores=[],
                total_count=0,
                has_more=False,
                query_metadata=Metadata(
                    source="retrieve_mem_service",
                    user_id=(
                        retrieve_mem_request.user_id if retrieve_mem_request else ""
                    ),
                    memory_type="retrieve",
                ),
                metadata=Metadata(
                    source="retrieve_mem_service",
                    user_id=(
                        retrieve_mem_request.user_id if retrieve_mem_request else ""
                    ),
                    memory_type="retrieve",
                ),
            )

    # Keyword retrieval method (original retrieve_mem logic)
    @trace_logger(operation_name="agentic_layer keyword memory retrieval")
    async def retrieve_mem_keyword(
        self, retrieve_mem_request: 'RetrieveMemRequest'
    ) -> RetrieveMemResponse:
        """Keyword-based memory retrieval (original retrieve_mem implementation)

        Args:
            retrieve_mem_request: RetrieveMemRequest containing retrieval parameters

        Returns:
            RetrieveMemResponse containing retrieval results
        """
        try:
            # Get parameters from Request
            if not retrieve_mem_request:
                raise ValueError(
                    "retrieve_mem_request is required for retrieve_mem_keyword"
                )

            search_results = await self.get_keyword_search_results(retrieve_mem_request)

            if not search_results:
                logger.warning(
                    f"No results found in keyword search: user_id={retrieve_mem_request.user_id}, query={retrieve_mem_request.query}"
                )
                return RetrieveMemResponse(
                    memories=[],
                    original_data=[],
                    scores=[],
                    importance_scores=[],
                    total_count=0,
                    has_more=False,
                    query_metadata=Metadata(
                        source="episodic_memory_es_repository",
                        user_id=retrieve_mem_request.user_id,
                        memory_type="retrieve_keyword",
                    ),
                    metadata=Metadata(
                        source="episodic_memory_es_repository",
                        user_id=retrieve_mem_request.user_id,
                        memory_type="retrieve_keyword",
                    ),
                )

            # Use generic grouping processing strategy
            memories, scores, importance_scores, original_data, total_count = (
                await self.group_by_groupid_stratagy(search_results, source_type=RetrieveMethod.KEYWORD.value)
            )

            logger.debug(
                f"EpisodicMemoryEsRepository multi_search returned {len(memories)} groups for query: {retrieve_mem_request.query}"
            )

            return RetrieveMemResponse(
                memories=memories,
                scores=scores,
                importance_scores=importance_scores,
                original_data=original_data,
                total_count=total_count,
                has_more=False,
                query_metadata=Metadata(
                    source="episodic_memory_es_repository",
                    user_id=retrieve_mem_request.user_id,
                    memory_type="retrieve_keyword",
                ),
                metadata=Metadata(
                    source="episodic_memory_es_repository",
                    user_id=retrieve_mem_request.user_id,
                    memory_type="retrieve_keyword",
                ),
            )

        except Exception as e:
            logger.error(f"Error in retrieve_mem_keyword: {e}", exc_info=True)
            return RetrieveMemResponse(
                memories=[],
                original_data=[],
                scores=[],
                importance_scores=[],
                total_count=0,
                has_more=False,
                query_metadata=Metadata(
                    source="retrieve_mem_keyword_service",
                    user_id=(
                        retrieve_mem_request.user_id if retrieve_mem_request else ""
                    ),
                    memory_type="retrieve_keyword",
                ),
                metadata=Metadata(
                    source="retrieve_mem_keyword_service",
                    user_id=(
                        retrieve_mem_request.user_id if retrieve_mem_request else ""
                    ),
                    memory_type="retrieve_keyword",
                ),
            )

    async def get_keyword_search_results(
        self, retrieve_mem_request: 'RetrieveMemRequest'
    ) -> Dict[str, Any]:
        try:
            # Get parameters from Request
            if not retrieve_mem_request:
                raise ValueError("retrieve_mem_request is required for retrieve_mem")

            top_k = retrieve_mem_request.top_k
            query = retrieve_mem_request.query
            user_id = retrieve_mem_request.user_id
            group_id = retrieve_mem_request.group_id
            start_time = retrieve_mem_request.start_time
            end_time = retrieve_mem_request.end_time
            memory_types = retrieve_mem_request.memory_types

            # MemoryType -> ES Repository mapping
            ES_REPO_MAP = {
                MemoryType.FORESIGHT: ForesightEsRepository,
                MemoryType.EVENT_LOG: EventLogEsRepository,
                MemoryType.EPISODIC_MEMORY: EpisodicMemoryEsRepository,
            }

            # Convert query string to search word list
            # Use jieba for search mode word segmentation, then filter stopwords
            if query:
                raw_words = list(jieba.cut_for_search(query))
                query_words = filter_stopwords(raw_words, min_length=2)
            else:
                query_words = []

            logger.debug(f"query_words: {query_words}")

            # Build time range filter conditions, handle None values
            date_range = {}
            if start_time is not None:
                date_range["gte"] = start_time
            if end_time is not None:
                date_range["lte"] = end_time

            # Take the first memory_type, default episodic_memory
            mem_type = memory_types[0] if memory_types else MemoryType.EPISODIC_MEMORY
            
            repo_class = ES_REPO_MAP.get(mem_type)
            if not repo_class:
                logger.warning(f"Unsupported memory_type: {mem_type}")
                return []
            
            es_repo = get_bean_by_type(repo_class)
            logger.debug(f"Using {repo_class.__name__} for {mem_type}")
            
            results = await es_repo.multi_search(
                query=query_words,
                user_id=user_id,
                group_id=group_id,
                size=top_k,
                from_=0,
                date_range=date_range,
            )
            
            # Mark memory_type, search_source, and unified score
            if results:
                for r in results:
                    r['memory_type'] = mem_type.value
                    r['_search_source'] = RetrieveMethod.KEYWORD.value
                    r['id'] = r.get('_id', '')  # Unify ES '_id' to 'id'
                    r['score'] = r.get('_score', 0.0)  # Unified score field
            
            return results or []
        except Exception as e:
            logger.error(f"Error in get_keyword_search_results: {e}")
            return []

    # Vector-based memory retrieval
    @trace_logger(operation_name="agentic_layer vector memory retrieval")
    async def retrieve_mem_vector(
        self, retrieve_mem_request: 'RetrieveMemRequest'
    ) -> RetrieveMemResponse:
        """Memory retrieval based on vector similarity

        Args:
            request: Request containing retrieval parameters, including query and retrieve_mem_request

        Returns:
            RetrieveMemResponse containing retrieval results
        """
        try:
            # Get parameters from Request
            logger.debug(
                f"retrieve_mem_vector called with retrieve_mem_request: {retrieve_mem_request}"
            )
            if not retrieve_mem_request:
                raise ValueError(
                    "retrieve_mem_request is required for retrieve_mem_vector"
                )

            query = retrieve_mem_request.query
            if not query:
                raise ValueError("query is required for retrieve_mem_vector")

            user_id = retrieve_mem_request.user_id
            group_id = retrieve_mem_request.group_id
            top_k = retrieve_mem_request.top_k
            start_time = retrieve_mem_request.start_time
            end_time = retrieve_mem_request.end_time

            logger.debug(
                f"retrieve_mem_vector called with query: {query}, user_id: {user_id}, group_id: {group_id}, top_k: {top_k}"
            )

            # Get vectorization service
            vectorize_service = get_vectorize_service()

            # Convert query text to vector
            logger.debug(f"Starting to vectorize query text: {query}")
            query_vector = await vectorize_service.get_embedding(query)
            query_vector_list = query_vector.tolist()  # Convert to list format
            logger.debug(
                f"Query text vectorization completed, vector dimension: {len(query_vector_list)}"
            )

            # Select Milvus repository based on memory type
            mem_type = retrieve_mem_request.memory_types[0] if retrieve_mem_request.memory_types else MemoryType.EPISODIC_MEMORY
            match mem_type:
                case MemoryType.FORESIGHT:
                    milvus_repo = get_bean_by_type(ForesightMilvusRepository)
                case MemoryType.EVENT_LOG:
                    milvus_repo = get_bean_by_type(EventLogMilvusRepository)
                case MemoryType.EPISODIC_MEMORY:
                    milvus_repo = get_bean_by_type(EpisodicMemoryMilvusRepository)
                case _:
                    raise ValueError(f"Unsupported memory type: {mem_type}")
            # Handle time range filter conditions
            start_time_dt = None
            end_time_dt = None
            foresight_start_dt = None
            foresight_end_dt = None
            current_time_dt = None

            if start_time is not None:
                start_time_dt = from_iso_format(start_time) if isinstance(start_time, str) else start_time

            if end_time is not None:
                if isinstance(end_time, str):
                    end_time_dt = from_iso_format(end_time)
                    # If date only format, set to end of day
                    if len(end_time) == 10:
                        end_time_dt = end_time_dt.replace(hour=23, minute=59, second=59)
                else:
                    end_time_dt = end_time

            # Handle foresight time range (only valid for foresight)
            if mem_type == MemoryType.FORESIGHT:
                if retrieve_mem_request.start_time:
                    foresight_start_dt = from_iso_format(retrieve_mem_request.start_time)
                if retrieve_mem_request.end_time:
                    foresight_end_dt = from_iso_format(retrieve_mem_request.end_time)
                if retrieve_mem_request.current_time:
                    current_time_dt = datetime.strptime(
                        retrieve_mem_request.current_time, "%Y-%m-%d"
                    )

            # Call Milvus vector search (pass different parameters based on memory type)
            if mem_type == MemoryType.FORESIGHT:
                # Foresight: supports time range and validity filtering, supports radius parameter
                search_results = await milvus_repo.vector_search(
                    query_vector=query_vector_list,
                    user_id=user_id,
                    group_id=group_id,
                    start_time=foresight_start_dt,
                    end_time=foresight_end_dt,
                    current_time=current_time_dt,
                    limit=top_k,
                    score_threshold=0.0,
                    radius=retrieve_mem_request.radius,  # Get similarity threshold parameter from request object
                )
            else:
                # Episodic memory and event log: use timestamp filtering, supports radius parameter
                search_results = await milvus_repo.vector_search(
                    query_vector=query_vector_list,
                    user_id=user_id,
                    group_id=group_id,
                    start_time=start_time_dt,
                    end_time=end_time_dt,
                    limit=top_k,
                    score_threshold=0.0,
                    radius=retrieve_mem_request.radius,  # Get similarity threshold parameter from request object
                )

            logger.debug(f"Milvus vector search returned {len(search_results)} results")

            # Add memory_type, search_source to results (Milvus already has 'score')
            mem_type_value = retrieve_mem_request.memory_types[0].value if retrieve_mem_request.memory_types else 'episodic_memory'
            for r in search_results:
                r['memory_type'] = mem_type_value
                r['_search_source'] = RetrieveMethod.VECTOR.value
                r['id'] = r.get('id', '')  # Ensure id field exists
                r['score'] = r.get('score')  # Unified score field
                # Milvus already uses 'score', no need to rename

            # Use generic grouping processing strategy
            memories, scores, importance_scores, original_data, total_count = (
                await self.group_by_groupid_stratagy(
                    search_results, source_type=RetrieveMethod.VECTOR.value
                )
            )

            logger.debug(
                f"EpisodicMemoryMilvusRepository vector_search returned {len(memories)} groups for query: {query}"
            )

            return RetrieveMemResponse(
                memories=memories,
                scores=scores,
                importance_scores=importance_scores,
                original_data=original_data,
                total_count=total_count,
                has_more=False,
                query_metadata=Metadata(
                    source="episodic_memory_milvus_repository",
                    user_id=user_id,
                    memory_type="retrieve_vector",
                ),
                metadata=Metadata(
                    source="episodic_memory_milvus_repository",
                    user_id=user_id,
                    memory_type="retrieve_vector",
                ),
            )

        except Exception as e:
            logger.error(f"Error in retrieve_mem_vector: {e}")
            return RetrieveMemResponse(
                memories=[],
                original_data=[],
                scores=[],
                importance_scores=[],
                total_count=0,
                has_more=False,
                query_metadata=Metadata(
                    source="retrieve_mem_vector_service",
                    user_id=user_id if 'user_id' in locals() else "",
                    memory_type="retrieve_vector",
                ),
                metadata=Metadata(
                    source="retrieve_mem_vector_service",
                    user_id=user_id if 'user_id' in locals() else "",
                    memory_type="retrieve_vector",
                ),
            )

    async def get_vector_search_results(
        self, retrieve_mem_request: 'RetrieveMemRequest'
    ) -> Dict[str, Any]:
        try:
            # Get parameters from Request
            logger.debug(
                f"get_vector_search_results called with retrieve_mem_request: {retrieve_mem_request}"
            )
            if not retrieve_mem_request:
                raise ValueError(
                    "retrieve_mem_request is required for get_vector_search_results"
                )
            query = retrieve_mem_request.query
            if not query:
                raise ValueError("query is required for retrieve_mem_vector")

            user_id = retrieve_mem_request.user_id
            group_id = retrieve_mem_request.group_id
            top_k = retrieve_mem_request.top_k
            start_time = retrieve_mem_request.start_time
            end_time = retrieve_mem_request.end_time

            logger.debug(
                f"retrieve_mem_vector called with query: {query}, user_id: {user_id}, group_id: {group_id}, top_k: {top_k}"
            )

            # Get vectorization service
            vectorize_service = get_vectorize_service()

            # Convert query text to vector
            logger.debug(f"Starting to vectorize query text: {query}")
            query_vector = await vectorize_service.get_embedding(query)
            query_vector_list = query_vector.tolist()  # Convert to list format
            logger.debug(
                f"Query text vectorization completed, vector dimension: {len(query_vector_list)}"
            )

            # Select Milvus repository based on memory type
            mem_type = retrieve_mem_request.memory_types[0]
            match mem_type:
                case MemoryType.FORESIGHT:
                    milvus_repo = get_bean_by_type(ForesightMilvusRepository)
                case MemoryType.EVENT_LOG:
                    milvus_repo = get_bean_by_type(EventLogMilvusRepository)
                case MemoryType.EPISODIC_MEMORY:
                    milvus_repo = get_bean_by_type(EpisodicMemoryMilvusRepository)
                case _:
                    raise ValueError(f"Unsupported memory type: {mem_type}")

            # Handle time range filter conditions
            start_time_dt = None
            end_time_dt = None
            current_time_dt = None

            if start_time is not None:
                start_time_dt = from_iso_format(start_time) if isinstance(start_time, str) else start_time

            if end_time is not None:
                if isinstance(end_time, str):
                    end_time_dt = from_iso_format(end_time)
                    # If date only format, set to end of day
                    if len(end_time) == 10:
                        end_time_dt = end_time_dt.replace(hour=23, minute=59, second=59)
                else:
                    end_time_dt = end_time

            # Handle foresight time range (only valid for foresight)
            if mem_type == MemoryType.FORESIGHT:
                if retrieve_mem_request.start_time:
                    start_time_dt = from_iso_format(retrieve_mem_request.start_time)
                if retrieve_mem_request.end_time:
                    end_time_dt = from_iso_format(retrieve_mem_request.end_time)
                if retrieve_mem_request.current_time:
                    current_time_dt = from_iso_format(retrieve_mem_request.current_time)

            # Call Milvus vector search (pass different parameters based on memory type)
            if mem_type == MemoryType.FORESIGHT:
                # Foresight: supports time range and validity filtering, supports radius parameter
                search_results = await milvus_repo.vector_search(
                    query_vector=query_vector_list,
                    user_id=user_id,
                    group_id=group_id,
                    start_time=start_time_dt,
                    end_time=end_time_dt,
                    current_time=current_time_dt,
                    limit=top_k,
                    score_threshold=0.0,
                    radius=retrieve_mem_request.radius,
                )
            else:
                # Episodic memory and event log: use timestamp filtering, supports radius parameter
                search_results = await milvus_repo.vector_search(
                    query_vector=query_vector_list,
                    user_id=user_id,
                    group_id=group_id,
                    start_time=start_time_dt,
                    end_time=end_time_dt,
                    limit=top_k,
                    score_threshold=0.0,
                    radius=retrieve_mem_request.radius,
                )
            
            # Add memory_type, _search_source markers (Milvus already has 'score')
            mem_type_value = retrieve_mem_request.memory_types[0].value if retrieve_mem_request.memory_types else 'episodic_memory'
            for r in search_results:
                r['memory_type'] = mem_type_value
                r['_search_source'] = RetrieveMethod.VECTOR.value
                # Milvus already uses 'score', no need to rename
            
            return search_results
        except Exception as e:
            logger.error(f"Error in get_vector_search_results: {e}")
            return []

    # Hybrid memory retrieval
    @trace_logger(operation_name="agentic_layer hybrid memory retrieval")
    async def retrieve_mem_hybrid(
        self, retrieve_mem_request: 'RetrieveMemRequest'
    ) -> RetrieveMemResponse:
        """Hybrid memory retrieval based on keywords and vectors

        Args:
            retrieve_mem_request: RetrieveMemRequest containing retrieval parameters

        Returns:
            RetrieveMemResponse containing hybrid retrieval results
        """
        try:
            logger.debug(
                f"retrieve_mem_hybrid called with retrieve_mem_request: {retrieve_mem_request}"
            )
            if not retrieve_mem_request:
                raise ValueError(
                    "retrieve_mem_request is required for retrieve_mem_hybrid"
                )

            query = retrieve_mem_request.query
            if not query:
                raise ValueError("query is required for retrieve_mem_hybrid")

            user_id = retrieve_mem_request.user_id
            top_k = retrieve_mem_request.top_k
            start_time = retrieve_mem_request.start_time
            end_time = retrieve_mem_request.end_time

            logger.debug(
                f"retrieve_mem_hybrid called with query: {query}, user_id: {user_id}, top_k: {top_k}"
            )

            # Create keyword retrieval request
            keyword_request = RetrieveMemRequest(
                user_id=user_id,
                memory_types=retrieve_mem_request.memory_types,
                top_k=top_k,
                filters=retrieve_mem_request.filters,
                include_metadata=retrieve_mem_request.include_metadata,
                start_time=start_time,
                end_time=end_time,
                query=query,
            )

            # Create vector retrieval request
            vector_request = RetrieveMemRequest(
                user_id=user_id,
                memory_types=retrieve_mem_request.memory_types,
                top_k=top_k,
                filters=retrieve_mem_request.filters,
                include_metadata=retrieve_mem_request.include_metadata,
                start_time=start_time,
                end_time=end_time,
                query=query,
            )

            # Execute both retrievals in parallel, get raw search results
            keyword_search_results = await self.get_keyword_search_results(
                keyword_request
            )
            vector_search_results = await self.get_vector_search_results(vector_request)

            logger.debug(
                f"Keyword retrieval returned {len(keyword_search_results)} raw results"
            )
            logger.debug(
                f"Vector retrieval returned {len(vector_search_results)} raw results"
            )

            # Merge raw search results and rerank
            hybrid_result = await self._merge_and_rerank_search_results(
                keyword_search_results, vector_search_results, top_k, user_id, query
            )

            logger.debug(
                f"Hybrid retrieval finally returned {len(hybrid_result.memories)} groups"
            )

            return hybrid_result

        except Exception as e:
            logger.error(f"Error in retrieve_mem_hybrid: {e}")
            return RetrieveMemResponse(
                memories=[],
                original_data=[],
                scores=[],
                importance_scores=[],
                total_count=0,
                has_more=False,
                query_metadata=Metadata(
                    source="retrieve_mem_hybrid_service",
                    user_id=user_id if 'user_id' in locals() else "",
                    memory_type="retrieve_hybrid",
                ),
                metadata=Metadata(
                    source="retrieve_mem_hybrid_service",
                    user_id=user_id if 'user_id' in locals() else "",
                    memory_type="retrieve_hybrid",
                ),
            )


    async def _merge_and_rerank_search_results(
        self,
        keyword_search_results: List[Dict[str, Any]],
        vector_search_results: List[Dict[str, Any]],
        top_k: int,
        user_id: str,
        query: str,
    ) -> RetrieveMemResponse:
        """Merge raw search results from keyword and vector retrieval, and rerank

        Args:
            keyword_search_results: Raw search results from keyword retrieval
            vector_search_results: Raw search results from vector retrieval
            top_k: Maximum number of groups to return
            user_id: User ID
            query: Query text

        Returns:
            RetrieveMemResponse: Merged and reranked results
        """
        # Extract search results
        keyword_hits = keyword_search_results
        vector_hits = vector_search_results

        logger.debug(f"Raw keyword retrieval results: {len(keyword_hits)} items")
        logger.debug(f"Raw vector retrieval results: {len(vector_hits)} items")

        # Merge all search results and mark source
        all_hits = []

        # Add keyword retrieval results, mark source
        for hit in keyword_hits:
            hit_copy = hit.copy()
            hit_copy['_search_source'] = 'keyword'
            all_hits.append(hit_copy)

        # Add vector retrieval results, mark source
        for hit in vector_hits:
            hit_copy = hit.copy()
            hit_copy['_search_source'] = 'vector'
            all_hits.append(hit_copy)

        logger.debug(f"Total results after merging: {len(all_hits)} items")

        # Use rerank service for reordering
        try:
            rerank_service = get_rerank_service()
            reranked_hits = await rerank_service._rerank_all_hits(
                query, all_hits, top_k
            )

            logger.debug(
                f"Number of results after rerank service: {len(reranked_hits)} items"
            )

        except Exception as e:
            logger.error(f"Rerank service failed, falling back to simple sorting: {e}")
            # If rerank fails, fall back to simple score sorting
            reranked_hits = sorted(
                all_hits, key=lambda x: x.get('score', 0), reverse=True
            )[:top_k]

        # Group process reranked results
        memories, scores, importance_scores, original_data, total_count = (
            await self.group_by_groupid_stratagy(reranked_hits, source_type=RetrieveMethod.HYBRID.value)
        )

        # Build final result
        return RetrieveMemResponse(
            memories=memories,
            scores=scores,
            importance_scores=importance_scores,
            original_data=original_data,
            total_count=total_count,
            has_more=False,
            query_metadata=Metadata(
                source="hybrid_retrieval",
                user_id=user_id,
                memory_type="retrieve_hybrid",
            ),
            metadata=Metadata(
                source="hybrid_retrieval",
                user_id=user_id,
                memory_type="retrieve_hybrid",
            ),
        )

    def _calculate_importance_score(
        self, importance_evidence: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate group importance score

        Calculate score based on group importance evidence, mainly considering:
        - speak_count: User's speaking count in this group
        - refer_count: Number of times user was mentioned
        - conversation_count: Total conversation count in this group

        Importance score = (total speaking count + total mention count) / total conversation count

        Args:
            importance_evidence: Group importance evidence dictionary

        Returns:
            float: Importance score, range [0, +∞), larger value means more important group
        """
        if not importance_evidence or not isinstance(importance_evidence, dict):
            return 0.0

        evidence_list = importance_evidence.get('evidence_list', [])
        if not evidence_list:
            return 0.0

        total_speak_count = 0
        total_refer_count = 0
        total_conversation_count = 0

        # Accumulate statistics from all evidence
        for evidence in evidence_list:
            if isinstance(evidence, dict):
                total_speak_count += evidence.get('speak_count', 0)
                total_refer_count += evidence.get('refer_count', 0)
                total_conversation_count += evidence.get('conversation_count', 0)

        # Avoid division by zero
        if total_conversation_count == 0:
            return 0.0

        # Calculate importance score
        return (total_speak_count + total_refer_count) / total_conversation_count

    async def _batch_get_memcells(
        self, event_ids: List[str], batch_size: int = 100
    ) -> Dict[str, Any]:
        """Batch get MemCells, supports batch queries to control single query size

        Args:
            event_ids: List of event_id to get
            batch_size: Number of items per batch, default 100

        Returns:
            Dict[event_id, MemCell]: Mapping dictionary from event_id to MemCell
        """
        if not event_ids:
            return {}

        # Deduplicate event_ids
        unique_event_ids = list(set(event_ids))
        logger.debug(
            f"Batch get MemCells: Total {len(unique_event_ids)} (before deduplication: {len(event_ids)})"
        )

        memcell_repo = get_bean_by_type(MemCellRawRepository)
        all_memcells = {}

        # Batch get
        for i in range(0, len(unique_event_ids), batch_size):
            batch_event_ids = unique_event_ids[i : i + batch_size]
            logger.debug(
                f"Getting batch {i // batch_size + 1} MemCells: {len(batch_event_ids)} items"
            )

            batch_memcells = await memcell_repo.get_by_event_ids(batch_event_ids)
            all_memcells.update(batch_memcells)

        logger.debug(
            f"Batch get MemCells completed: Successfully retrieved {len(all_memcells)} items"
        )
        return all_memcells

    async def _batch_get_group_profiles(
        self, user_group_pairs: List[Tuple[str, str]]
    ) -> Dict[Tuple[str, str], Any]:
        """Batch get group user profiles, supports efficient querying

        Args:
            user_group_pairs: List of (user_id, group_id) tuples

        Returns:
            Dict[(user_id, group_id), GroupUserProfileMemory]: Mapping dictionary
        """
        if not user_group_pairs:
            return {}

        # Deduplicate
        unique_pairs = list(set(user_group_pairs))
        logger.debug(
            f"Batch get group user profiles: Total {len(unique_pairs)} (before deduplication: {len(user_group_pairs)})"
        )

        group_user_profile_repo = get_bean_by_type(GroupUserProfileMemoryRawRepository)
        profiles = await group_user_profile_repo.batch_get_by_user_groups(unique_pairs)

        logger.debug(
            f"Batch get group user profiles completed: Successfully retrieved {len([v for v in profiles.values() if v is not None])} items"
        )
        return profiles

    def _get_type_str(self, val) -> str:
        """Extract string value of type field"""
        if isinstance(val, RawDataType):
            return val.value
        return str(val) if val else ''

    def _extract_hit_fields_from_es(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        """Extract fields from ES search result"""
        source = hit.get('_source', {})
        return {
            'hit_id': source.get('event_id', ''),
            'user_id': source.get('user_id', ''),
            'group_id': source.get('group_id', ''),
            'timestamp_raw': source.get('timestamp', ''),
            'episode': source.get('episode', ''),
            'memcell_event_id_list': source.get('memcell_event_id_list', []),
            'subject': source.get('subject', ''),
            'summary': source.get('summary', ''),
            'participants': source.get('participants', []),
            'event_type': source.get('type', ''),
            'atomic_fact': source.get('atomic_fact', ''),
            'foresight': source.get('foresight', ''),
            'evidence': source.get('evidence', ''),
            'extend_data': source.get('extend', {}) or {},
            'search_source': 'keyword',
        }

    def _extract_hit_fields_from_milvus(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        """Extract fields from Milvus search result"""
        metadata = hit.get('metadata', {})
        timestamp_val = hit.get('timestamp') or hit.get('start_time')
        return {
            'hit_id': hit.get('id', ''),
            'user_id': hit.get('user_id', ''),
            'group_id': hit.get('group_id', ''),
            'timestamp_raw': timestamp_val,
            'episode': hit.get('episode', ''),
            'memcell_event_id_list': metadata.get('memcell_event_id_list', []),
            'subject': metadata.get('subject', ''),
            'summary': metadata.get('summary', ''),
            'participants': metadata.get('participants', []),
            'event_type': self._get_type_str(hit.get('type') or hit.get('event_type')),
            'atomic_fact': hit.get('atomic_fact', ''),
            'foresight': hit.get('content', ''),  # Milvus foresight uses 'content' field
            'evidence': hit.get('evidence', ''),
            'extend_data': metadata.get('extend', {}) or {},
            'search_source': 'vector',
        }

    def _extract_hit_fields(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        """Extract fields from search result based on _search_source"""
        search_source = hit.get('_search_source')
        match search_source:
            case RetrieveMethod.KEYWORD.value:
                return self._extract_hit_fields_from_es(hit)
            case RetrieveMethod.VECTOR.value:
                return self._extract_hit_fields_from_milvus(hit)
            case _:
                raise ValueError(f"Unknown _search_source: {search_source}")
    async def group_by_groupid_stratagy(
        self, search_results: List[Dict[str, Any]], source_type: str = RetrieveMethod.VECTOR.value
    ) -> tuple:
        """Generic search result grouping processing strategy

        Args:
            search_results: List of search results
            source_type: Retrieval method (keyword/vector/hybrid)

        Returns:
            tuple: (memories, scores, importance_scores, original_data, total_count)
        """
        # Step 1: Collect all data needed for queries
        all_memcell_event_ids = []
        all_user_group_pairs = []

        for hit in search_results:
            fields = self._extract_hit_fields(hit)
            memcell_event_id_list = fields['memcell_event_id_list']
            user_id = fields['user_id']
            group_id = fields['group_id']

            if memcell_event_id_list:
                all_memcell_event_ids.extend(memcell_event_id_list)

            # Collect user_id and group_id pairs
            if user_id and group_id:
                all_user_group_pairs.append((user_id, group_id))

        # Step 2: Execute two batch query tasks concurrently
        memcells_task = asyncio.create_task(
            self._batch_get_memcells(all_memcell_event_ids)
        )
        profiles_task = asyncio.create_task(
            self._batch_get_group_profiles(all_user_group_pairs)
        )

        # Wait for all tasks to complete
        memcells_cache, profiles_cache = await asyncio.gather(
            memcells_task, profiles_task
        )

        # Step 3: Process search results
        memories_by_group = {}  # {group_id: {'memories': [Memory], 'scores': [float], 'importance_evidence': dict}}
        original_data_by_group = {}

        for hit in search_results:
            # Extract fields
            fields = self._extract_hit_fields(hit)
            # Get score (each retrieval method uses its own score field)
            score = hit.get('score', 0.0)
            
            hit_id = fields['hit_id']
            user_id = fields['user_id']
            group_id = fields['group_id']
            timestamp_raw = fields['timestamp_raw']
            memcell_event_id_list = fields['memcell_event_id_list']
            episode = fields['episode']
            subject = fields['subject']
            summary = fields['summary']
            participants = fields['participants']
            event_type = fields['event_type']
            atomic_fact = fields['atomic_fact']
            foresight = fields['foresight']
            evidence = fields['evidence']
            extend_data = fields['extend_data']
            search_source = fields['search_source']
            # Process timestamp
            timestamp = from_iso_format(timestamp_raw)

            # Get memcell data from cache (foresight doesn't need this)
            memory_type_value = hit.get('memory_type', 'episodic_memory')
            memcells = []
            if memcell_event_id_list:
                # Get memcells from cache in original order
                for event_id in memcell_event_id_list:
                    memcell = memcells_cache.get(event_id)
                    if memcell:
                        memcells.append(memcell)
                    else:
                        logger.debug(f"Memcell not found: event_id={event_id}")
                        continue

            # Add raw data for each memcell
            for memcell in memcells:
                if group_id not in original_data_by_group:
                    original_data_by_group[group_id] = []
                original_data_by_group[group_id].append(memcell.original_data)

            # Create object based on memory type
            base_kwargs = dict(
                memory_type=memory_type_value,
                user_id=user_id,
                timestamp=timestamp,
                ori_event_id_list=[hit_id],
                group_id=group_id,
                participants=participants,
                memcell_event_id_list=memcell_event_id_list,
                type=RawDataType.from_string(event_type),
                extend={
                    '_search_source': search_source,
                    'parent_episode_id': extend_data.get('parent_episode_id'),
                },
            )
            
            match memory_type_value:
                case MemoryType.EVENT_LOG.value:
                    memory = EventLog(**base_kwargs, atomic_fact=atomic_fact)
                case MemoryType.FORESIGHT.value:
                    memory = Foresight(**base_kwargs, foresight=foresight, evidence=evidence)
                case MemoryType.EPISODIC_MEMORY.value:
                    # EpisodeMemory has additional fields: subject, summary, episode
                    memory = EpisodeMemory(**base_kwargs, subject=subject, summary=summary, episode=episode)
                case _:
                    raise ValueError(f"Unsupported memory type: {memory_type_value}")

            # Get group_importance_evidence from cache
            group_importance_evidence = None
            if user_id and group_id:
                group_user_profile = profiles_cache.get((user_id, group_id))
                if (
                    group_user_profile
                    and hasattr(group_user_profile, 'group_importance_evidence')
                    and group_user_profile.group_importance_evidence
                ):
                    group_importance_evidence = (
                        group_user_profile.group_importance_evidence
                    )
                    # Add group_importance_evidence to memory's extend field
                    if not hasattr(memory, 'extend') or memory.extend is None:
                        memory.extend = {}
                    memory.extend['group_importance_evidence'] = (
                        group_importance_evidence
                    )
                    logger.debug(
                        f"Added group_importance_evidence to memory: user_id={user_id}, group_id={group_id}"
                    )

            # Group by group_id
            if group_id not in memories_by_group:
                memories_by_group[group_id] = {
                    'memories': [],
                    'scores': [],
                    'importance_evidence': group_importance_evidence,
                }

            memories_by_group[group_id]['memories'].append(memory)
            memories_by_group[group_id]['scores'].append(score)  # Save original score

            # Update group_importance_evidence (if current memory has updated evidence)
            if group_importance_evidence:
                memories_by_group[group_id][
                    'importance_evidence'
                ] = group_importance_evidence

        # Sort memories within each group by timestamp, and calculate importance score
        group_scores = []
        for group_id, group_data in memories_by_group.items():
            # Sort memories by timestamp
            group_data['memories'].sort(
                key=lambda m: m.timestamp if m.timestamp else ''
            )

            # Calculate importance score
            importance_score = self._calculate_importance_score(
                group_data['importance_evidence']
            )
            group_scores.append((group_id, importance_score))

        # Sort groups by importance score
        group_scores.sort(key=lambda x: x[1], reverse=True)

        # Build final results
        memories = []
        scores = []
        importance_scores = []
        original_data = []
        for group_id, importance_score in group_scores:
            group_data = memories_by_group[group_id]
            group_memories = group_data['memories']
            group_scores_list = group_data['scores']
            group_original_data = original_data_by_group.get(group_id, [])
            memories.append({group_id: group_memories})
            # scores structure consistent with memories: List[Dict[str, List[float]]]
            scores.append({group_id: group_scores_list})
            # original_data structure consistent with memories: List[Dict[str, List[Dict[str, Any]]]]
            original_data.append({group_id: group_original_data})
            importance_scores.append(importance_score)

        total_count = sum(
            len(group_data['memories']) for group_data in memories_by_group.values()
        )
        return memories, scores, importance_scores, original_data, total_count

    # --------- Lightweight retrieval (Embedding + BM25 + RRF)---------
    @trace_logger(operation_name="agentic_layer lightweight retrieval")
    async def retrieve_lightweight(
        self,
        query: str,
        user_id: str = None,
        group_id: str = None,
        time_range_days: int = 365,
        top_k: int = 20,
        retrieval_mode: str = "rrf",  # "embedding" | "bm25" | "rrf"
        data_source: str = "episode",  # "episode" | "event_log" | "foresight" | "profile"
        current_time: Optional[
            datetime
        ] = None,  # Current time, used to filter foresight within validity period
        radius: Optional[float] = None,  # COSINE similarity threshold
    ) -> Dict[str, Any]:
        """
        Lightweight memory retrieval (unified use of Milvus/ES retrieval)

        Args:
            query: User query
            user_id: User ID (for filtering)
            group_id: Group ID (for filtering; required for profile data source)
            time_range_days: Time range in days
            top_k: Number of results to return
            retrieval_mode: Retrieval mode
                - "embedding": Pure vector retrieval (via Milvus)
                - "bm25": Pure keyword retrieval (via ES)
                - "rrf": RRF fusion (default, Milvus + ES)
            data_source: Data source
                - "episode": Retrieve from episode (default)
                - "event_log": Retrieve from event_log
                - "foresight": Retrieve from foresight
                - "profile": Directly retrieve profile by user_id + group_id
            current_time: Current time, used to filter foresight within validity period (only valid when data_source=foresight)

        Returns:
            Dict containing memories, metadata
        """
        start_time = time.time()

        # Compatible with old parameter names
        if data_source == "memcell":
            data_source = "episode"

        if data_source == "profile":
            if not user_id or not group_id:
                raise ValueError(
                    "user_id and group_id must be provided when retrieving profile"
                )
            return await self._retrieve_profile_memories(
                user_id=user_id, group_id=group_id, top_k=top_k, start_time=start_time
            )

        return await self._retrieve_from_vector_stores(
            query=query,
            user_id=user_id,  # Pass directly, no modification
            group_id=group_id,  # Pass directly, no modification
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            data_source=data_source,
            start_time=start_time,
            current_time=current_time,
            radius=radius,
        )

    async def _retrieve_from_vector_stores(
        self,
        query: str,
        user_id: str = None,
        group_id: str = None,
        top_k: int = 20,
        retrieval_mode: str = "rrf",
        data_source: str = "memcell",
        start_time: float = None,
        current_time: Optional[datetime] = None,
        radius: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Unified vector store retrieval method (supports embedding, bm25, rrf three modes)

        Args:
            query: Query text
            user_id: User ID filter
            group_id: Group ID filter
            top_k: Number of results to return
            retrieval_mode: Retrieval mode (embedding/bm25/rrf)
            data_source: Data source (memcell/event_log/foresight)
            start_time: Start time (for calculating latency)
            current_time: Current time, used to filter foresight within validity period (only valid when data_source=foresight)
            radius: COSINE similarity threshold (only valid for non-foresight)

        Returns:
            Dict containing memories, metadata
        """
        if start_time is None:
            start_time = time.time()

        try:
            # 1. Embedding retrieval (via Milvus, select different Repository based on data_source)
            embedding_results = []
            embedding_count = 0

            if retrieval_mode in ["embedding", "rrf"]:
                # Select Milvus repository based on data_source
                match data_source:
                    case MemoryType.FORESIGHT.value:
                        milvus_repo = get_bean_by_type(ForesightMilvusRepository)
                    case MemoryType.EVENT_LOG.value:
                        milvus_repo = get_bean_by_type(EventLogMilvusRepository)
                    case MemoryType.EPISODIC_MEMORY.value:
                        milvus_repo = get_bean_by_type(EpisodicMemoryMilvusRepository)
                    case _:
                        raise ValueError(f"Unsupported memory type: {data_source}")

                vectorize_service = get_vectorize_service()

                # Generate query vector
                query_vec = await vectorize_service.get_embedding(query)

                # Vector retrieval
                # Note: To ensure enough candidates are retrieved, increase limit
                # Milvus limit: topk maximum is 16384
                # To solve the issue of EventLog/Foresight returning only 1 result, significantly increase limit
                retrieval_limit = min(
                    max(top_k * 200, 1000), 16384
                )  # At least 1000, maximum 16384

                # Call vector_search with different parameters based on data_source
                milvus_kwargs = dict(
                    query_vector=query_vec,
                    user_id=user_id,
                    group_id=group_id,
                    limit=retrieval_limit,
                    radius=radius,
                )
                if data_source == "foresight":
                    milvus_kwargs["current_time"] = current_time

                logger.info(
                    f"Calling Milvus retrieval: data_source={data_source}, "
                    f"limit={retrieval_limit}, radius={radius}, "
                    f"user_id={user_id}, group_id={group_id}"
                )
                milvus_results = await milvus_repo.vector_search(**milvus_kwargs)

                # Process Milvus retrieval results
                # Determine metric type based on data_source:
                # - foresight and episode use COSINE, score is similarity (range -1 to 1)
                # - event_log uses L2, score is distance (range 0 to +∞), needs conversion to similarity
                for result in milvus_results:
                    score = result.get('score', 0)
                    # All data sources use COSINE uniformly, similarity is score
                    similarity = score
                    embedding_results.append((result, similarity))
                    if result.get('content'):
                        result['foresight'] = result['content']

                # Sort by similarity
                embedding_results.sort(key=lambda x: x[1], reverse=True)
                logger.info(
                    f"Milvus retrieval completed: data_source={data_source}, "
                    f"result count={len(embedding_results)}, "
                    f"query={query[:30]}, "
                    f"user_id={user_id}, group_id={group_id}"
                )
                embedding_count = len(embedding_results)

            # 2. BM25 retrieval (via Elasticsearch)
            bm25_results = []
            bm25_count = 0

            if retrieval_mode in ["bm25", "rrf"]:
                # Select ES repository based on data_source
                match data_source:
                    case MemoryType.FORESIGHT.value:
                        es_repo = get_bean_by_type(ForesightEsRepository)
                    case MemoryType.EVENT_LOG.value:
                        es_repo = get_bean_by_type(EventLogEsRepository)
                    case MemoryType.EPISODIC_MEMORY.value:
                        es_repo = get_bean_by_type(EpisodicMemoryEsRepository)
                    case _:
                        raise ValueError(f"Unsupported memory type: {data_source}")

                raw_query_words = list(jieba.cut(query))
                query_words = filter_stopwords(raw_query_words, min_length=2)

                logger.debug(
                    f"BM25 retrieval: data_source={data_source}, query={query}, "
                    f"raw_query_words={raw_query_words}, query_words={query_words}"
                )

                # Call ES retrieval
                # Note: To ensure enough candidates are retrieved, increase size
                retrieval_size = max(top_k * 10, 100)  # At least 100 candidates

                es_kwargs = dict(
                    query=query_words,
                    user_id=user_id,
                    group_id=group_id,
                    size=retrieval_size,
                )
                if data_source == "foresight" and current_time is not None:
                    es_kwargs["current_time"] = current_time
                hits = await es_repo.multi_search(**es_kwargs)

                # Process ES retrieval results (no longer secondary filtering based on whether user_id is empty)
                for hit in hits:
                    source = hit.get('_source', {})
                    bm25_score = hit.get('_score', 0)
                    metadata = source.get('extend', {})
                    result = {
                        'score': bm25_score,
                        'id': hit.get('_id', ''),
                        'user_id': source.get('user_id', ''),
                        'group_id': source.get('group_id', ''),
                        'timestamp': source.get('timestamp', ''),
                        'episode': source.get('episode', ''),
                        'foresight': source.get('foresight', ''),
                        'evidence': source.get('evidence', ''),
                        'atomic_fact': source.get('atomic_fact', ''),
                        'search_content': source.get('search_content', []),
                        'metadata': metadata,
                    }
                    if isinstance(metadata, dict):
                        result['start_time'] = metadata.get('start_time')
                        result['end_time'] = metadata.get('end_time')
                    else:
                        result['start_time'] = None
                        result['end_time'] = None
                    bm25_results.append((result, bm25_score))
                logger.debug(
                    f"ES retrieval completed: data_source={data_source}, result count={len(bm25_results)}"
                )
                bm25_count = len(bm25_results)

            # 3. Return results based on mode
            if retrieval_mode == "embedding":
                # Pure vector retrieval
                final_results = embedding_results[:top_k]
                memories = [
                    {
                        'score': score,
                        'id': result.get('id', ''),
                        'user_id': result.get('user_id', ''),
                        'group_id': result.get('group_id', ''),
                        'timestamp': result.get('timestamp', ''),
                        'subject': result.get('metadata', {}).get('title', ''),
                        'episode': (
                            result.get('episode', '')
                            if data_source == "episode"
                            else (
                                result.get('content', '')
                                if data_source == "foresight"
                                else result.get('atomic_fact', '')
                            )
                        ),
                        'summary': result.get('metadata', {}).get('summary', ''),
                        'evidence': (
                            result.get('evidence', '')
                            if data_source == "foresight"
                            else ''
                        ),
                        'atomic_fact': result.get('atomic_fact', ''),
                        'metadata': result.get('metadata', {}),
                    }
                    for result, score in final_results
                ]

                metadata = {
                    "retrieval_mode": "embedding",
                    "data_source": data_source,
                    "embedding_candidates": embedding_count,
                    "total_latency_ms": (time.time() - start_time) * 1000,
                }
                memories = self._filter_foresight_memories_by_time(
                    memories, data_source, current_time
                )
                metadata["final_count"] = len(memories)

            elif retrieval_mode == "bm25":
                # Pure BM25 retrieval
                final_results = bm25_results[:top_k]
                memories = [result for result, score in final_results]

                metadata = {
                    "retrieval_mode": "bm25",
                    "data_source": data_source,
                    "bm25_candidates": bm25_count,
                    "total_latency_ms": (time.time() - start_time) * 1000,
                }
                memories = self._filter_foresight_memories_by_time(
                    memories, data_source, current_time
                )
                metadata["final_count"] = len(memories)

            else:  # rrf
                # RRF fusion
                from agentic_layer.retrieval_utils import reciprocal_rank_fusion

                fused_results = reciprocal_rank_fusion(
                    embedding_results, bm25_results, k=60
                )

                final_results = fused_results[:top_k]

                # Unified format
                memories = []
                for doc, rrf_score in final_results:
                    # doc may come from Milvus or ES, need unified format
                    # Differentiation method: Milvus has 'id' field, ES has 'event_id' field
                    if 'event_id' in doc and 'id' not in doc:
                        # Result from ES (already in standard format)
                        memory = {
                            'score': rrf_score,
                            'event_id': doc.get('event_id', ''),
                            'user_id': doc.get('user_id', ''),
                            'group_id': doc.get('group_id', ''),
                            'timestamp': doc.get('timestamp', ''),
                            'subject': '',
                            'episode': doc.get('episode', ''),
                            'summary': '',
                            'evidence': doc.get('evidence', ''),
                            'atomic_fact': doc.get('atomic_fact', ''),
                            'metadata': doc.get('metadata', {}),
                            'start_time': doc.get('start_time'),
                            'end_time': doc.get('end_time'),
                        }
                    else:
                        # Result from Milvus (need to convert field names)
                        # Get correct content field based on data_source
                        content_field = 'episode'  # default
                        evidence_field = ''
                        if data_source == "foresight":
                            content_field = 'content'
                            evidence_field = doc.get('evidence', '')
                        elif data_source == "event_log":
                            content_field = 'atomic_fact'

                        start_val = doc.get('start_time')
                        end_val = doc.get('end_time')
                        memory = {
                            'score': rrf_score,
                            'event_id': doc.get('id', ''),  # Milvus uses 'id'
                            'user_id': doc.get('user_id', ''),
                            'group_id': doc.get('group_id', ''),
                            'timestamp': doc.get('timestamp', ''),
                            'subject': (
                                doc.get('metadata', {}).get('title', '')
                                if isinstance(doc.get('metadata'), dict)
                                else ''
                            ),
                            'episode': doc.get(content_field, ''),
                            'summary': (
                                doc.get('metadata', {}).get('summary', '')
                                if isinstance(doc.get('metadata'), dict)
                                else ''
                            ),
                            'evidence': evidence_field,
                            'atomic_fact': doc.get('atomic_fact', ''),
                            'metadata': (
                                doc.get('metadata', {})
                                if isinstance(doc.get('metadata'), dict)
                                else {}
                            ),
                            'start_time': self._format_datetime_field(start_val),
                            'end_time': self._format_datetime_field(end_val),
                        }
                    memories.append(memory)

                metadata = {
                    "retrieval_mode": "rrf",
                    "data_source": data_source,
                    "embedding_candidates": embedding_count,
                    "bm25_candidates": bm25_count,
                    "total_latency_ms": (time.time() - start_time) * 1000,
                }
                memories = self._filter_foresight_memories_by_time(
                    memories, data_source, current_time
                )
                metadata["final_count"] = len(memories)

            return {"memories": memories, "count": len(memories), "metadata": metadata}

        except Exception as e:
            logger.error(f"Vector store retrieval failed: {e}", exc_info=True)
            return {
                "memories": [],
                "count": 0,
                "metadata": {
                    "retrieval_mode": retrieval_mode,
                    "data_source": data_source,
                    "error": str(e),
                    "total_latency_ms": (time.time() - start_time) * 1000,
                },
            }

    async def _retrieve_profile_memories(
        self, user_id: str, group_id: str, top_k: int, start_time: float
    ) -> Dict[str, Any]:
        """Directly read user profile from user_profiles collection"""
        doc = await UserProfile.find_one(
            UserProfile.user_id == user_id,
            UserProfile.group_id == group_id,
            sort=[("version", -1)],
        )

        memories: List[Dict[str, Any]] = []
        if doc:
            memories.append(
                {
                    "user_id": doc.user_id,
                    "group_id": doc.group_id,
                    "profile": doc.profile_data,
                    "scenario": doc.scenario,
                    "confidence": doc.confidence,
                    "version": doc.version,
                    "cluster_ids": doc.cluster_ids,
                    "memcell_count": doc.memcell_count,
                    "last_updated_cluster": doc.last_updated_cluster,
                    "updated_at": (
                        doc.updated_at.isoformat() if doc.updated_at else None
                    ),
                }
            )

        metadata = {
            "retrieval_mode": "direct",
            "data_source": "profile",
            "profile_count": len(memories),
            "total_latency_ms": (time.time() - start_time) * 1000,
        }

        return {
            "memories": memories[:top_k],
            "count": len(memories[:top_k]),
            "metadata": metadata,
        }

    @staticmethod
    def _format_datetime_field(value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def _parse_datetime_value(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    return None
        return None

    def _filter_foresight_memories_by_time(
        self,
        memories: List[Dict[str, Any]],
        data_source: str,
        current_time: Optional[datetime],
    ) -> List[Dict[str, Any]]:
        if data_source != "foresight" or not current_time:
            return memories
        current_dt = (
            current_time
            if isinstance(current_time, datetime)
            else self._parse_datetime_value(current_time)
        )
        if current_dt is None:
            return memories

        filtered = []
        for memory in memories:
            start_dt = self._parse_datetime_value(memory.get("start_time"))
            end_dt = self._parse_datetime_value(memory.get("end_time"))

            if start_dt and start_dt > current_dt:
                continue
            if end_dt and end_dt < current_dt:
                continue
            filtered.append(memory)
        return filtered

    # --------- Agentic retrieval (LLM-guided multi-round retrieval)---------
    @trace_logger(operation_name="agentic_layer Agentic retrieval")
    async def retrieve_agentic(
        self,
        query: str,
        user_id: str = None,
        group_id: str = None,
        time_range_days: int = 365,
        top_k: int = 20,
        llm_provider=None,
        agentic_config=None,
    ) -> Dict[str, Any]:
        """Agentic retrieval: LLM-guided multi-round intelligent retrieval

        Process: Round 1 (RRF retrieval) → Rerank → LLM judgment → Round 2 (multi-query) → Fusion → Rerank
        """
        # Validate parameters
        if llm_provider is None:
            raise ValueError("llm_provider is required for agentic retrieval")

        # Import dependencies
        from .agentic_utils import (
            AgenticConfig,
            check_sufficiency,
            generate_multi_queries,
            format_documents_for_llm,
        )
        from .rerank_service import get_rerank_service

        # Use default configuration
        if agentic_config is None:
            agentic_config = AgenticConfig()
        config = agentic_config

        start_time = time.time()
        metadata = {
            "retrieval_mode": "agentic",
            "is_multi_round": False,
            "round1_count": 0,
            "round1_reranked_count": 0,
            "is_sufficient": None,
            "reasoning": None,
            "missing_info": None,
            "refined_queries": None,
            "round2_count": 0,
            "final_count": 0,
            "total_latency_ms": 0.0,
        }

        logger.info(f"{'='*60}")
        logger.info(f"Agentic Retrieval: {query[:60]}...")
        logger.info(f"{'='*60}")

        try:
            # ========== Round 1: RRF hybrid retrieval ==========
            logger.info("Round 1: RRF retrieval...")

            round1_result = await self.retrieve_lightweight(
                query=query,
                user_id=user_id,
                group_id=group_id,
                time_range_days=time_range_days,
                top_k=config.round1_top_n,  # 20
                retrieval_mode="rrf",
                data_source="episode",
            )

            round1_memories = round1_result.get("memories", [])
            metadata["round1_count"] = len(round1_memories)
            metadata["round1_latency_ms"] = round1_result.get("metadata", {}).get(
                "total_latency_ms", 0
            )

            logger.info(f"Round 1: Retrieved {len(round1_memories)} memories")

            if not round1_memories:
                logger.warning("Round 1 returned no results")
                metadata["total_latency_ms"] = (time.time() - start_time) * 1000
                return {"memories": [], "count": 0, "metadata": metadata}

            # ========== Rerank Round 1 results → Top 5 ==========
            if config.use_reranker:
                logger.info("Reranking Top 20 to Top 5 for sufficiency check...")
                rerank_service = get_rerank_service()

                # Convert format for rerank
                candidates_for_rerank = [
                    {
                        "index": i,
                        "episode": mem.get("episode", ""),
                        "summary": mem.get("summary", ""),
                        "subject": mem.get("subject", ""),
                        "score": mem.get("score", 0),
                    }
                    for i, mem in enumerate(round1_memories)
                ]

                reranked_hits = await rerank_service._rerank_all_hits(
                    query, candidates_for_rerank, top_k=config.round1_rerank_top_n
                )

                # Extract Top 5 for LLM judgment
                top5_for_llm = []
                for hit in reranked_hits[: config.round1_rerank_top_n]:
                    idx = hit.get("index", 0)
                    if 0 <= idx < len(round1_memories):
                        mem = round1_memories[idx]
                        # Convert to (candidate, score) format for LLM use
                        top5_for_llm.append((mem, hit.get("score", 0)))

                metadata["round1_reranked_count"] = len(top5_for_llm)
                logger.info(
                    f"Rerank: Got Top {len(top5_for_llm)} for sufficiency check"
                )
            else:
                # No reranker, directly take top 5
                top5_for_llm = [
                    (mem, mem.get("score", 0))
                    for mem in round1_memories[: config.round1_rerank_top_n]
                ]
                metadata["round1_reranked_count"] = len(top5_for_llm)
                logger.info("No Rerank: Using original Top 5")

            if not top5_for_llm:
                logger.warning("No results for sufficiency check")
                metadata["total_latency_ms"] = (time.time() - start_time) * 1000
                return round1_result

            # ========== LLM check sufficiency ==========
            logger.info("LLM: Checking sufficiency on Top 5...")

            is_sufficient, reasoning, missing_info = await check_sufficiency(
                query=query,
                results=top5_for_llm,
                llm_provider=llm_provider,
                max_docs=config.round1_rerank_top_n,
            )

            metadata["is_sufficient"] = is_sufficient
            metadata["reasoning"] = reasoning
            metadata["missing_info"] = missing_info

            logger.info(
                f"LLM Result: {'✅ Sufficient' if is_sufficient else '❌ Insufficient'}"
            )
            logger.info(f"LLM Reasoning: {reasoning}")

            # ========== If sufficient: directly return Round 1 results ==========
            if is_sufficient:
                logger.info("Decision: Sufficient! Using Round 1 results")
                metadata["final_count"] = len(round1_memories)
                metadata["total_latency_ms"] = (time.time() - start_time) * 1000

                round1_result["metadata"] = metadata
                logger.info(f"Complete: Latency {metadata['total_latency_ms']:.0f}ms")
                return round1_result

            # ========== Round 2: LLM generate multiple refined queries ==========
            metadata["is_multi_round"] = True
            logger.info("Decision: Insufficient, entering Round 2")

            if missing_info:
                logger.info(f"Missing: {', '.join(missing_info)}")

            if config.enable_multi_query:
                logger.info("LLM: Generating multiple refined queries...")

                refined_queries, query_strategy = await generate_multi_queries(
                    original_query=query,
                    results=top5_for_llm,
                    missing_info=missing_info,
                    llm_provider=llm_provider,
                    max_docs=config.round1_rerank_top_n,
                    num_queries=config.num_queries,
                )

                metadata["refined_queries"] = refined_queries
                metadata["query_strategy"] = query_strategy
                metadata["num_queries"] = len(refined_queries)

                logger.info(f"Generated {len(refined_queries)} queries")
                for i, q in enumerate(refined_queries, 1):
                    logger.debug(f"  Query {i}: {q[:80]}...")
            else:
                # Single query mode
                refined_queries = [query]
                metadata["refined_queries"] = refined_queries
                metadata["num_queries"] = 1

            # ========== Round 2: Parallel execute multi-query retrieval ==========
            logger.info(
                f"Round 2: Executing {len(refined_queries)} queries in parallel..."
            )

            # Parallel call retrieve_lightweight
            round2_tasks = [
                self.retrieve_lightweight(
                    query=q,
                    user_id=user_id,
                    group_id=group_id,
                    time_range_days=time_range_days,
                    top_k=config.round2_per_query_top_n,  # 50 per query
                    retrieval_mode="rrf",
                    data_source="episode",
                )
                for q in refined_queries
            ]

            round2_results_list = await asyncio.gather(
                *round2_tasks, return_exceptions=True
            )

            # Collect results from all queries
            all_round2_memories = []
            for i, result in enumerate(round2_results_list, 1):
                if isinstance(result, Exception):
                    logger.error(f"Query {i} failed: {result}")
                    continue

                memories = result.get("memories", [])
                if memories:
                    all_round2_memories.extend(memories)
                    logger.debug(f"Query {i}: Retrieved {len(memories)} memories")

            logger.info(
                f"Round 2: Total retrieved {len(all_round2_memories)} memories before dedup"
            )

            # ========== Deduplicate and merge ==========
            logger.info("Merge: Deduplicating and combining Round 1 + Round 2...")

            # Deduplicate: use event_id
            round1_event_ids = {mem.get("event_id") for mem in round1_memories}
            round2_unique = [
                mem
                for mem in all_round2_memories
                if mem.get("event_id") not in round1_event_ids
            ]

            # Merge: Round 1 (20) + Round 2 deduplicated results (take up to total 40)
            combined_memories = round1_memories.copy()
            needed_from_round2 = config.combined_total - len(combined_memories)
            combined_memories.extend(round2_unique[:needed_from_round2])

            metadata["round2_count"] = len(round2_unique[:needed_from_round2])
            logger.info(
                f"Merge: Round1={len(round1_memories)}, Round2_unique={len(round2_unique[:needed_from_round2])}, Total={len(combined_memories)}"
            )

            # ========== Final Rerank ==========
            if config.use_reranker and len(combined_memories) > 0:
                logger.info(f"Rerank: Reranking {len(combined_memories)} memories...")

                rerank_service = get_rerank_service()

                # Convert format
                candidates_for_rerank = [
                    {
                        "index": i,
                        "episode": mem.get("episode", ""),
                        "summary": mem.get("summary", ""),
                        "subject": mem.get("subject", ""),
                        "score": mem.get("score", 0),
                    }
                    for i, mem in enumerate(combined_memories)
                ]

                reranked_hits = await rerank_service._rerank_all_hits(
                    query,  # Use original query
                    candidates_for_rerank,
                    top_k=config.final_top_n,
                )

                # Extract final Top 20
                final_memories = []
                for hit in reranked_hits[: config.final_top_n]:
                    idx = hit.get("index", 0)
                    if 0 <= idx < len(combined_memories):
                        mem = combined_memories[idx].copy()
                        mem["score"] = hit.get("score", mem.get("score", 0))
                        final_memories.append(mem)

                logger.info(f"Rerank: Final Top {len(final_memories)} selected")
            else:
                # No Reranker, directly return Top N
                final_memories = combined_memories[: config.final_top_n]
                logger.info(f"No Rerank: Returning Top {len(final_memories)}")

            metadata["final_count"] = len(final_memories)
            metadata["total_latency_ms"] = (time.time() - start_time) * 1000

            logger.info(
                f"Complete: Final {len(final_memories)} memories | Latency {metadata['total_latency_ms']:.0f}ms"
            )
            logger.info(f"{'='*60}\n")

            return {
                "memories": final_memories,
                "count": len(final_memories),
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"Agentic retrieval failed: {e}", exc_info=True)

            # Fallback to lightweight
            logger.warning("Falling back to lightweight retrieval")

            fallback_result = await self.retrieve_lightweight(
                query=query,
                user_id=user_id,
                group_id=group_id,
                time_range_days=time_range_days,
                top_k=top_k,
                retrieval_mode="rrf",
                data_source="episode",
            )

            fallback_result["metadata"]["retrieval_mode"] = "agentic_fallback"
            fallback_result["metadata"]["fallback_reason"] = str(e)

            return fallback_result
