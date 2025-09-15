from datetime import datetime
from typing import Optional, List, Dict, Any
from elasticsearch import Elasticsearch
from config import Config
from logging_config import get_logger

logger = get_logger(__name__)

class ChatDocument:
    """聊天记录文档模型 - 适配新的索引结构"""
    
    def __init__(self, user_id: str, agent_id: Optional[str], 
                 question: str, answer: str, timestamp: datetime = None):
        self.user_id = user_id
        self.agent_id = agent_id
        self.question = question
        self.answer = answer
        self.timestamp = timestamp or datetime.now()
        self.embedding = None  # 使用单个embedding字段
        self.topics = []  # 添加topics字段
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "question": self.question,
            "answer": self.answer,
            "timestamp": self.timestamp.isoformat(),
            "embedding": self.embedding,  # 使用单个embedding字段
            "topics": self.topics  # 添加topics字段
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatDocument':
        doc = cls(
            user_id=data["user_id"],
            agent_id=data.get("agent_id"),
            question=data["question"],
            answer=data["answer"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )
        doc.embedding = data.get("embedding")
        doc.topics = data.get("topics", [])
        return doc

class ESService:
    """ES服务类 - 只负责对话存储和搜索"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ESService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.es = None
            self.index_created = False
            self._init_es_connection()
            ESService._initialized = True
    
    def _init_es_connection(self):
        """初始化ES连接 - 支持集群配置"""
        try:
            es_hosts = Config.get_es_hosts()
            logger.info(f"初始化ES连接，节点: {es_hosts}")
            
            self.es = Elasticsearch(
                es_hosts,
                basic_auth=(Config.get_es_username(), Config.get_es_password()),
                verify_certs=False,
                request_timeout=30,
                retry_on_timeout=True,
                max_retries=3
            )
            
            # 测试连接 - 使用更可靠的方法
            try:
                # 尝试获取集群信息来测试连接
                info = self.es.info()
                if len(es_hosts) == 1:
                    logger.info(f"ES连接初始化成功: {es_hosts[0]}")
                else:
                    logger.info(f"ES集群连接初始化成功，节点数: {len(es_hosts)}")
                logger.info(f"ES集群信息: {info.get('cluster_name', 'unknown')} - {info.get('version', {}).get('number', 'unknown')}")
            except Exception as e:
                logger.error(f"ES连接测试失败: {e}")
                self.es = None
                
        except Exception as e:
            logger.error(f"ES连接初始化失败: {e}")
            self.es = None
    
    def _ensure_chat_index_exists(self):
        """确保聊天索引存在，如果不存在则创建"""
        if not self.es:
            logger.error("ES连接未建立，无法检查索引")
            return False
        
        if self.index_created:
            return True
        
        try:
            # 检查索引是否存在
            if self.es.indices.exists(index=Config.get_es_chat_index()):
                logger.info(f"ES索引已存在: {Config.get_es_chat_index()}")
                self.index_created = True
                return True
            else:
                # 创建索引
                return self._create_chat_index()
        except Exception as e:
            logger.error(f"检查ES索引失败: {e}")
            return False
    
    def _create_chat_index(self):
        """创建聊天记录索引"""
        try:
            # 使用指定的mapping配置
            mapping = {
                "settings": {
                    "analysis": {
                        "analyzer": {
                            "ik_smart": {
                                "type": "custom",
                                "tokenizer": "ik_smart"
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "user_id": {"type": "keyword"},
                        "agent_id": {
                            "type": "keyword",
                            "null_value": "N/A"  # 可为空，提供默认值
                        },
                        "question": {
                            "type": "text",
                            "analyzer": "ik_smart",
                            "search_analyzer": "ik_smart",  # 关键：确保搜索时使用相同分词器
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "answer": {
                            "type": "text",
                            "analyzer": "ik_smart",
                            "search_analyzer": "ik_smart"  # 关键：确保搜索时使用相同分词器
                        },
                        "timestamp": {
                            "type": "date", 
                            "format": "yyyy-MM-dd HH:mm:ss.SSS||strict_date_optional_time||epoch_millis"  # 支持您需要的格式
                        },
                        "topics": {
                            "type": "keyword",
                            "null_value": []  # 可为空数组
                        },
                        "embedding": {
                            "type": "dense_vector",
                            "dims": 1024  # BGE-M3模型的固定维度
                        }
                    }
                }
            }
            
            # 先删除可能存在的索引
            try:
                if self.es.indices.exists(index=Config.get_es_chat_index()):
                    self.es.indices.delete(index=Config.get_es_chat_index())
                    logger.info(f"删除旧索引: {Config.get_es_chat_index()}")
            except Exception as e:
                logger.warning(f"删除旧索引失败: {e}")
            
            # 创建新索引
            self.es.indices.create(index=Config.get_es_chat_index(), body=mapping)
            logger.info(f"成功创建ES索引: {Config.get_es_chat_index()}")
            self.index_created = True
            return True
            
        except Exception as e:
            logger.error(f"创建ES索引失败: {e}")
            return False
    
    def add_chat(self, chat: ChatDocument) -> str:
        """添加聊天记录"""
        if not self._ensure_chat_index_exists():
            raise Exception("无法创建或访问ES索引")
        
        doc = chat.to_dict()
        try:
            result = self.es.index(index=Config.get_es_chat_index(), body=doc)
            return result["_id"]
        except Exception as e:
            logger.error(f"添加聊天记录到ES失败: {e}")
            raise
    
    def search_similar_chats(self, user_id: str, query: str, 
                           embedding: List[float], agent_id: Optional[str] = None, limit: int = 10, min_similarity: float = 0.5) -> List[Dict]:
        """搜索相似的聊天记录 - 优先返回最新数据"""
        if not self._ensure_chat_index_exists():
            logger.error("无法创建或访问ES索引")
            return []
        
        # 混合搜索：关键词 + 向量相似度 + 时间排序
        # 注意：存储的embedding只基于问题，搜索时也只使用问题的embedding
        must_conditions = [
            {"term": {"user_id": user_id}}
        ]
        
        # 优化搜索策略：专注于问题匹配，使用IK分词器
        should_conditions = [
            # 问题精确短语匹配（最高权重）
            {
                "multi_match": {
                    "query": query,
                    "fields": ["question^10"],
                    "type": "phrase",  # 精确短语匹配
                    "boost": 10.0
                }
            },
            # 问题最佳字段匹配（高权重）
            {
                "multi_match": {
                    "query": query,
                    "fields": ["question^8"],
                    "type": "best_fields",
                    "fuzziness": "0",
                    "minimum_should_match": "80%"  # 提高匹配要求，减少不相关结果
                }
            },
            # 问题跨字段匹配（中等权重）
            {
                "multi_match": {
                    "query": query,
                    "fields": ["question^6"],
                    "type": "cross_fields",
                    "minimum_should_match": "70%"
                }
            },
            # 问题前缀匹配（较低权重）
            {
                "multi_match": {
                    "query": query,
                    "fields": ["question^4"],
                    "type": "phrase_prefix",
                    "boost": 4.0
                }
            }
        ]
        
        # 如果提供了agent_id，添加过滤条件
        if agent_id is not None:
            must_conditions.append({"term": {"agent_id": agent_id}})
        
        # 混合搜索：关键词 + 向量搜索，但设置更高的向量相似度阈值
        search_body = {
            "knn": {
                "field": "embedding",
                "query_vector": embedding,
                "k": limit * 2,  # 获取更多候选结果
                "num_candidates": limit * 10,
                "filter": {
                    "bool": {
                        "must": must_conditions
                    }
                }
            },
            "query": {
                "bool": {
                    "must": must_conditions,
                    "should": should_conditions,
                    "minimum_should_match": 1  # 至少匹配一个should条件
                }
            },
            "size": limit,
            "min_score": 0.1,  # 降低阈值，确保相关结果能被返回
            "sort": [
                {"_score": {"order": "desc"}},      # 首先按相关性排序
                {"timestamp": {"order": "desc"}}    # 然后按时间倒序（最新优先）
            ]
        }
        
        try:
            result = self.es.search(index=Config.get_es_chat_index(), **search_body)
            
            # 过滤结果：只返回相似度高于阈值的
            filtered_results = []
            for hit in result["hits"]["hits"]:
                score = hit.get("_score", 0.0)
                
                # 对于混合搜索，我们需要更严格的过滤
                # 1. 检查是否有关键词匹配（分数通常很高，如100+）
                # 2. 检查是否有向量相似度匹配（分数通常在0-2之间）
                # 3. 设置更高的向量相似度阈值来过滤不相关结果
                
                # 如果分数很高（>50），说明是关键词匹配，直接通过
                if score > 50:
                    filtered_results.append({
                        **hit["_source"],
                        "_score": score
                    })
                # 如果分数较低，检查是否达到向量相似度阈值
                elif score >= min_similarity:
                    # 对于向量搜索，我们设置更高的阈值（0.8）来过滤不相关结果
                    vector_threshold = 0.8
                    if score >= vector_threshold:
                        filtered_results.append({
                            **hit["_source"],
                            "_score": score
                        })
            
            # 按相似度排序并限制数量
            filtered_results.sort(key=lambda x: x["_score"], reverse=True)
            return filtered_results[:limit]
            
        except Exception as e:
            logger.error(f"ES搜索失败: {e}")
            return []
    
    def search_similar_chats_by_question_only(self, user_id: str, query: str, 
                                            limit: int = 10) -> List[Dict]:
        """仅根据问题进行搜索（不使用embedding）- 用于纯关键词搜索"""
        if not self._ensure_chat_index_exists():
            logger.error("无法创建或访问ES索引")
            return []
        
        # 纯关键词搜索，不依赖embedding
        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"user_id": user_id}}
                    ],
                    "should": [
                        # 问题精确短语匹配（最高权重）
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["question^10"],
                                "type": "phrase",  # 精确短语匹配
                                "boost": 10.0
                            }
                        },
                        # 问题最佳字段匹配（高权重）
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["question^8"],
                                "type": "best_fields",
                                "fuzziness": "0",
                                "minimum_should_match": "80%"  # 提高匹配要求，减少不相关结果
                            }
                        },
                        # 问题跨字段匹配（中等权重）
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["question^6"],
                                "type": "cross_fields",
                                "minimum_should_match": "70%"
                            }
                        },
                        # 问题前缀匹配（较低权重）
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["question^4"],
                                "type": "phrase_prefix",
                                "boost": 4.0
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": limit,
            "min_score": 0.1,  # 降低阈值，确保相关结果能被返回
            "sort": [
                {"_score": {"order": "desc"}},      # 按相关性排序
                {"timestamp": {"order": "desc"}}    # 然后按时间倒序
            ]
        }
        
        try:
            result = self.es.search(index=Config.get_es_chat_index(), **search_body)
            # 返回包含_score的结果
            return [{
                **hit["_source"],
                "_score": hit.get("_score", 0.0)
            } for hit in result["hits"]["hits"]]
        except Exception as e:
            logger.error(f"ES关键词搜索失败: {e}")
            return []
    
    def search_similar_chats_by_embedding_only(self, user_id: str, 
                                             embedding: List[float], 
                                             agent_id: Optional[str] = None,
                                             limit: int = 10,
                                             min_similarity: float = 0.6) -> List[Dict]:
        """仅根据embedding进行搜索（纯向量搜索）"""
        if not self._ensure_chat_index_exists():
            logger.error("无法创建或访问ES索引")
            return []
        
        # 使用knn方法进行向量搜索，并添加相似度阈值
        search_body = {
            "knn": {
                "field": "embedding",
                "query_vector": embedding,
                "k": limit * 2,  # 获取更多候选结果
                "num_candidates": limit * 10,
                "filter": {
                    "bool": {
                        "must": [
                            {"term": {"user_id": user_id}}
                        ]
                    }
                }
            },
            "query": {
                "bool": {
                    "must": [
                        {"term": {"user_id": user_id}}
                    ]
                }
            },
            "size": limit,
            "sort": [
                {"_score": {"order": "desc"}},      # 按相似度排序
                {"timestamp": {"order": "desc"}}    # 然后按时间倒序
            ]
        }
        
        # 如果提供了agent_id，添加过滤条件
        if agent_id is not None:
            search_body["knn"]["filter"]["bool"]["must"].append({"term": {"agent_id": agent_id}})
            search_body["query"]["bool"]["must"].append({"term": {"agent_id": agent_id}})
        
        try:
            result = self.es.search(index=Config.get_es_chat_index(), **search_body)
            
            # 过滤结果：只返回相似度高于阈值的
            filtered_results = []
            for hit in result["hits"]["hits"]:
                score = hit.get("_score", 0.0)
                # ES的knn搜索返回的分数范围是0-1，需要转换为余弦相似度
                # 对于knn搜索，分数通常已经接近余弦相似度
                if score >= min_similarity:
                    filtered_results.append({
                        **hit["_source"],
                        "_score": score
                    })
            
            # 按相似度排序并限制数量
            filtered_results.sort(key=lambda x: x["_score"], reverse=True)
            return filtered_results[:limit]
            
        except Exception as e:
            logger.error(f"ES向量搜索失败: {e}")
            return []
    
    def get_recent_chats(self, user_id: str, agent_id: Optional[str] = None, 
                        limit: int = 20) -> List[Dict]:
        """获取用户最近的对话记录"""
        try:
            logger.info(f"获取最近对话: user_id={user_id}, agent_id={agent_id}, limit={limit}")
            
            # 构建查询条件
            must_conditions = [{"term": {"user_id": user_id}}]
            
            if agent_id is not None:
                must_conditions.append({"term": {"agent_id": agent_id}})
            
            search_body = {
                "query": {
                    "bool": {
                        "must": must_conditions
                    }
                },
                "size": limit,
                "sort": [
                    {"timestamp": {"order": "desc"}}  # 按时间倒序
                ],
                "_source": ["question", "answer", "timestamp", "topics"]
            }
            
            response = self.es.search(
                index=Config.get_es_chat_index(),
                body=search_body
            )
            
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                results.append({
                    "question": source.get("question", ""),
                    "answer": source.get("answer", ""),
                    "timestamp": source.get("timestamp", ""),
                    "chat_id": hit["_id"],  # 使用ES文档的_id作为chat_id
                    # "topics": source.get("topics", [])
                })
            
            logger.info(f"获取到{len(results)}个最近对话")
            return results
            
        except Exception as e:
            logger.error(f"获取最近对话失败: {e}")
            return []
    
    def get_all_chats(self) -> List[Dict]:
        """获取所有对话记录（用于数据清理）"""
        try:
            logger.info("获取所有对话记录")
            
            search_body = {
                "query": {"match_all": {}},
                "size": 10000,  # 获取大量数据
                "_source": ["question", "answer", "chat_id", "user_id", "agent_id", "timestamp"]
            }
            
            response = self.es.search(
                index=Config.get_es_chat_index(),
                body=search_body,
                scroll="5m"  # 使用scroll API处理大量数据
            )
            
            results = []
            scroll_id = response.get("_scroll_id")
            
            while True:
                for hit in response["hits"]["hits"]:
                    source = hit["_source"]
                    results.append({
                        "question": source.get("question", ""),
                        "answer": source.get("answer", ""),
                        "chat_id": hit["_id"],  # 使用ES的_id作为chat_id
                        "user_id": source.get("user_id", ""),
                        "agent_id": source.get("agent_id", ""),
                        "timestamp": source.get("timestamp", "")
                    })
                
                if not scroll_id or len(response["hits"]["hits"]) == 0:
                    break
                    
                response = self.es.scroll(
                    scroll_id=scroll_id,
                    scroll="5m"
                )
            
            logger.info(f"获取到{len(results)}条对话记录")
            return results
            
        except Exception as e:
            logger.error(f"获取所有对话记录失败: {e}")
            return []
    
    def delete_chat(self, chat_id: str) -> bool:
        """删除指定的对话记录"""
        try:
            # 检查chat_id是否为空
            if not chat_id or chat_id.strip() == "":
                logger.warning(f"删除对话记录失败: chat_id为空")
                return False
                
            logger.info(f"删除对话记录: chat_id={chat_id}")
            
            # 使用chat_id作为文档ID进行删除
            response = self.es.delete(
                index=Config.get_es_chat_index(),
                id=chat_id
            )
            
            if response.get("result") == "deleted":
                logger.info(f"成功删除对话记录: chat_id={chat_id}")
                return True
            else:
                logger.warning(f"删除对话记录失败: chat_id={chat_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除对话记录异常: {e}")
            return False
