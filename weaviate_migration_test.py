#!/usr/bin/env python3
"""
Weaviate 数据迁移脚本

功能:
1. 从源Weaviate实例迁移所有class数据到目标实例
2. 支持超过10000条数据的class(使用cursor分页)
3. 完整迁移metadata和vectors
4. 数据完整性验证
5. 增量迁移机制(时间戳优先，Hash备选)
6. 定时任务支持
7. 企业微信通知(可配置)
"""

import weaviate
from weaviate import Client, AuthApiKey
from typing import Any, Dict, List, Optional
import logging
from tqdm import tqdm
import time
import json
import os
import hashlib
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# ================================
# 配置区域 - 在这里修改配置
# ================================

# # 源Weaviate配置 -测试
# SOURCE_CONFIG = {
#     "endpoint": "http://weaviate-db.paas.paas.test",
#     "api_key": "WVF5YThaHlkYwhGUSmCRgsX3tD5ngdN8pkih"
# }
#
# # 目标Weaviate配置 - 测试
# TARGET_CONFIG = {
#     "endpoint": "http://weaviate-db-pre.aigc.paas.test",  # 修改为目标地址
#     "api_key": "WVF5YThaHlkYwhGUSmCRgsX3tD5ngdN8pkih"  # 修改为目标API Key
# }

# 源Weaviate配置 -生产
SOURCE_CONFIG = {
    "endpoint": "http://weaviate2201.8080-wm.db.idc:8080",
    "api_key": "sdhznq4wyyRqlQg9evy]"
}

# 目标Weaviate配置 - 生产
TARGET_CONFIG = {
    "endpoint": "http://weaviate2202.8081-wm.db.idc:8081",  # 修改为目标地址
    "api_key": "xbph0bs=mkjkGiy9yaiT"  # 修改为目标API Key
}

# 迁移配置
MIGRATION_CONFIG = {
    "batch_size": 100,  # 批量处理大小
    "state_file": "weaviate_migration_state.json",  # 状态文件路径
    "log_file": "weaviate_migration.log",  # 日志文件路径
    "schedule_timezone": "Asia/Shanghai",  # 定时任务时区
    "schedule_start_hour": 0,  # 每日允许执行开始时间（含）
    "schedule_end_hour": 6,  # 每日允许执行结束时间（不含）
    "large_class_full_sync_threshold": 5000,  # 大 class 直接切换为流式全量覆盖
    "streaming_verify_threshold": 5000,  # 大 class 使用流式校验阈值
}

# 企业微信通知配置(可选，不配置则不发送通知)
WECOM_CONFIG = {
    "webhook_url": "",  # 企业微信机器人webhook地址，例如: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx"
}

# ================================
# 配置日志
# ================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(MIGRATION_CONFIG['log_file']),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def configure_local_timezone():
    """为当前进程显式设置时区，保证日志和调度按北京时间运行"""
    timezone_name = MIGRATION_CONFIG.get("schedule_timezone", "Asia/Shanghai")
    os.environ["TZ"] = timezone_name
    if hasattr(time, "tzset"):
        time.tzset()


configure_local_timezone()


# ================================
# 企业微信通知器
# ================================

class WeComNotifier:
    """企业微信通知器"""

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url

    def is_configured(self) -> bool:
        """检查是否配置了企业微信"""
        return bool(self.webhook_url and len(self.webhook_url) > 0)

    def send(self, message: str, msg_type: str = "text") -> bool:
        """发送企业微信消息"""
        if not self.is_configured():
            # 无配置时只记录日志
            logger.info(f"[通知未配置] {message}")
            return False

        data = {
            "msgtype": msg_type,
            msg_type: {"content": message}
        }
        try:
            resp = requests.post(self.webhook_url, json=data, timeout=10)
            result = resp.json()
            if result.get('errcode') == 0:
                logger.info(f"通知发送成功: {message[:50]}...")
                return True
            else:
                logger.error(f"通知发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"发送告警失败: {e}")
            return False

    def notify_migration_start(self, class_name: str, mode: str):
        """通知迁移开始"""
        mode_desc = "全量" if mode == "full" else "增量"
        self.send(f"🚀 Weaviate迁移开始\nClass: {class_name}\n模式: {mode_desc}")

    def notify_migration_success(self, class_name: str, mode: str, count: int, details: str = ""):
        """通知迁移成功"""
        mode_desc = "全量" if mode == "full" else "增量"
        msg = f"✅ Weaviate迁移成功\nClass: {class_name}\n模式: {mode_desc}\n数量: {count}"
        if details:
            msg += f"\n{details}"
        self.send(msg)

    def notify_migration_failed(self, class_name: str, mode: str, error: str):
        """通知迁移失败"""
        mode_desc = "全量" if mode == "full" else "增量"
        self.send(f"❌ Weaviate迁移失败\nClass: {class_name}\n模式: {mode_desc}\n错误: {error}")

    def notify_incremental_details(
        self,
        class_name: str,
        added: int,
        updated: int,
        unchanged: int,
        deleted: int = 0
    ):
        """通知增量同步详情"""
        self.send(
            f"🔄 增量同步详情\n"
            f"Class: {class_name}\n"
            f"新增: {added}\n"
            f"更新: {updated}\n"
            f"删除: {deleted}\n"
            f"未变化: {unchanged}"
        )


# ================================
# 迁移状态管理
# ================================

class MigrationState:
    """迁移状态管理器"""

    def __init__(self, state_file: str):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """加载状态文件"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载状态文件失败: {e}, 创建新状态")
                return {}
        return {}

    def _save_state(self):
        """保存状态文件"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存状态文件失败: {e}")

    def get_class_state(self, class_name: str) -> Optional[Dict[str, Any]]:
        """获取class的迁移状态"""
        return self.state.get('classes', {}).get(class_name)

    def update_class_state(
        self,
        class_name: str,
        count: int,
        status: str,
        timestamp: Optional[str] = None,
        last_update_time: Optional[int] = None
    ):
        """更新class的迁移状态"""
        if 'classes' not in self.state:
            self.state['classes'] = {}

        self.state['classes'][class_name] = {
            'count': count,
            'status': status,  # 'completed', 'partial', 'failed'
            'last_migration': timestamp or datetime.now().isoformat(),
            'last_update_time': last_update_time,  # 记录源数据的最大更新时间
            'migrations': self.state['classes'].get(class_name, {}).get('migrations', 0) + 1
        }

        self._save_state()

    def needs_incremental_migration(self, class_name: str, current_count: int) -> bool:
        """
        判断是否需要增量迁移

        Args:
            class_name: class名称
            current_count: 当前源数据数量

        Returns:
            是否需要增量迁移
        """
        class_state = self.get_class_state(class_name)

        if not class_state:
            # 从未迁移过,需要全量迁移
            return True

        if class_state['status'] != 'completed':
            # 上次迁移未完成,需要重新迁移
            return True

        if class_state['count'] != current_count:
            # 数据量有变化,需要增量迁移
            logger.info(
                f"Class '{class_name}' 数据量变化: "
                f"{class_state['count']} -> {current_count}"
            )
            return True

        # 数据量相同,检查是否有数据更新(通过时间戳)
        # 如果有 last_update_time 且当前有更大的时间戳，则需要同步
        if class_state.get('last_update_time'):
            # 这里先返回True，让增量同步时做更精确的判断
            return True

        # 数据量相同,无需迁移
        return False

    def get_migration_summary(self) -> str:
        """获取迁移历史摘要"""
        if not self.state.get('classes'):
            return "暂无迁移历史"

        summary = ["\n迁移历史摘要:"]
        summary.append("-" * 60)

        for class_name, info in self.state['classes'].items():
            summary.append(
                f"{class_name}:\n"
                f"  - 数据量: {info['count']}\n"
                f"  - 状态: {info['status']}\n"
                f"  - 最后迁移: {info['last_migration']}\n"
                f"  - 迁移次数: {info['migrations']}"
            )

        return "\n".join(summary)


# ================================
# Weaviate 迁移器
# ================================

class WeaviateMigrator:
    """Weaviate数据迁移工具"""

    def __init__(
        self,
        source_endpoint: str,
        source_api_key: str,
        target_endpoint: str,
        target_api_key: str,
        batch_size: int = 100,
        state_file: str = "weaviate_migration_state.json",
        wecom_webhook: str = ""
    ):
        """
        初始化迁移器

        Args:
            source_endpoint: 源Weaviate端点
            source_api_key: 源API密钥
            target_endpoint: 目标Weaviate端点
            target_api_key: 目标API密钥
            batch_size: 批量处理大小
            state_file: 状态文件路径
            wecom_webhook: 企业微信webhook地址
        """
        self.source_client = self._init_client(source_endpoint, source_api_key, "源")
        self.target_client = self._init_client(target_endpoint, target_api_key, "目标")
        self.batch_size = batch_size
        self.state_manager = MigrationState(state_file)
        self.notifier = WeComNotifier(wecom_webhook)

    def _tqdm_kwargs(self) -> Dict[str, Any]:
        """统一进度条输出，避免和日志相互污染"""
        return {
            "file": sys.stdout,
            "dynamic_ncols": True,
            "leave": False,
            "mininterval": 0.5,
        }

    def _init_client(self, endpoint: str, api_key: str, name: str) -> Client:
        """初始化Weaviate客户端 (weaviate-client 3.24版本)"""
        auth_config = AuthApiKey(api_key=api_key)

        try:
            client = weaviate.Client(
                url=endpoint,
                auth_client_secret=auth_config,
                timeout_config=(5, 60),
                startup_period=None
            )
            logger.info(f"成功连接到{name}Weaviate: {endpoint}")
            return client
        except Exception as e:
            logger.error(f"连接{name}Weaviate失败 {endpoint}: {e}")
            raise

    def get_all_classes(self) -> List[str]:
        """获取所有class名称"""
        try:
            schema = self.source_client.schema.get()
            classes = [cls['class'] for cls in schema.get('classes', [])]
            logger.info(f"找到 {len(classes)} 个class: {classes}")
            return classes
        except Exception as e:
            logger.error(f"获取schema失败: {e}")
            raise

    def get_class_count_info(self, class_name: str, client_type: str = "source") -> Dict[str, Any]:
        """
        获取 class 数量信息，并区分 class 不存在 与 查询异常
        """
        client = self.source_client if client_type == "source" else self.target_client
        schema = client.schema.get()
        class_exists = any(cls.get('class') == class_name for cls in schema.get('classes', []))

        if not class_exists:
            return {
                "exists": False,
                "count": 0,
                "error": None
            }

        try:
            result = (
                client.query
                .aggregate(class_name)
                .with_meta_count()
                .do()
            )

            if "errors" in result:
                return {
                    "exists": True,
                    "count": None,
                    "error": result["errors"]
                }

            aggregate_data = result.get('data', {}).get('Aggregate', {}).get(class_name, [])
            if not aggregate_data:
                return {
                    "exists": True,
                    "count": None,
                    "error": f"聚合结果缺失: {result}"
                }

            count = aggregate_data[0]['meta']['count']
            return {
                "exists": True,
                "count": count,
                "error": None
            }
        except Exception as e:
            return {
                "exists": True,
                "count": None,
                "error": str(e)
            }

    def get_class_object_count(self, class_name: str, client_type: str = "source") -> int:
        """
        获取class中的对象总数

        Args:
            class_name: class名称
            client_type: 客户端类型 ('source' 或 'target')

        Returns:
            对象数量
        """
        try:
            count_info = self.get_class_count_info(class_name, client_type)
            if not count_info["exists"]:
                logger.info(f"Class '{class_name}' ({client_type}) 不存在，计数视为 0")
                return 0

            if count_info["error"] is not None:
                raise ValueError(count_info["error"])

            count = count_info["count"]
            logger.info(f"Class '{class_name}' ({client_type}) 总数: {count}")
            return count
        except Exception as e:
            logger.warning(f"无法获取class '{class_name}' ({client_type}) 的计数: {e}")
            return 0

    def get_class_replication_factor(self, class_name: str, client_type: str = "target") -> int:
        """
        获取class的复制因子

        Args:
            class_name: class名称
            client_type: 客户端类型 ('source' 或 'target')

        Returns:
            复制因子数量
        """
        try:
            client = self.source_client if client_type == "source" else self.target_client
            schema = client.schema.get()

            for cls in schema.get('classes', []):
                if cls['class'] == class_name:
                    replication_factor = cls.get('replicationConfig', {}).get('factor', 1)
                    logger.debug(f"Class '{class_name}' ({client_type}) 复制因子: {replication_factor}")
                    return replication_factor
            return 1
        except Exception as e:
            logger.warning(f"无法获取class '{class_name}' ({client_type}) 的复制因子: {e}")
            return 1

    def get_target_default_replication_factor(self) -> int:
        """
        从目标集群状态获取默认复制因子

        优先取目标集群 READY 节点数；
        如果拿不到，再回退到目标端已有 class 的复制因子；
        最后兜底为 1。
        """
        try:
            nodes = self.target_client.cluster.get_nodes_status()
            ready_nodes = [node for node in nodes if node.get("status") == "READY"]
            if ready_nodes:
                replication_factor = len(ready_nodes)
                logger.info(f"从目标集群 READY 节点数获取默认复制因子: {replication_factor}")
                return replication_factor

            if nodes:
                replication_factor = len(nodes)
                logger.info(f"目标集群无 READY 状态，使用节点总数作为默认复制因子: {replication_factor}")
                return replication_factor
        except Exception as e:
            logger.warning(f"无法从目标集群状态获取复制因子: {e}")

        try:
            target_schema = self.target_client.schema.get()
            if target_schema.get('classes'):
                factors = [
                    cls.get('replicationConfig', {}).get('factor', 1)
                    for cls in target_schema.get('classes', [])
                ]
                if factors:
                    replication_factor = max(factors)
                    logger.info(f"回退使用目标端已有class的最大复制因子: {replication_factor}")
                    return replication_factor
        except Exception as e:
            logger.warning(f"无法从目标schema回退获取复制因子: {e}")

        logger.warning("无法确定目标端默认复制因子，使用默认值 1")
        return 1

    def get_class_property_names(self, class_name: str, client=None) -> List[str]:
        """获取 class 的全部属性名，用于完整查询 properties"""
        if client is None:
            client = self.source_client

        schema = client.schema.get()
        for cls in schema.get('classes', []):
            if cls['class'] == class_name:
                return [prop['name'] for prop in cls.get('properties', [])]
        return []

    def get_max_update_time(self, class_name: str, client_type: str = "source") -> Optional[int]:
        """
        获取class中最大的更新时间戳(毫秒)

        Args:
            class_name: class名称
            client_type: 客户端类型

        Returns:
            最大更新时间戳,失败返回None
        """
        try:
            client = self.source_client if client_type == "source" else self.target_client

            result = (
                client.query
                .aggregate(class_name)
                .with_meta_count()
                .with_aggregates([
                    {"path": ["id"], "aggregates": [{"name": "max_time", "property": "*", "filters": {"operator": "Equal", "valueText": "x"}}]}
                ])
                .do()
            )
            # 注意: Weaviate 3.x 不支持直接获取 max UpdateTime，需要用其他方式
            # 这里简化处理，返回 None 表示不支持时间过滤
            return None
        except Exception as e:
            logger.warning(f"获取最大更新时间失败: {e}")
            return None

    def fetch_all_objects_with_cursor(
        self,
        class_name: str,
        client=None,
        include_vector: bool = True,
        include_metadata: bool = True,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        使用cursor分页获取class的所有对象

        这个方法可以处理超过10000条数据的class

        Args:
            class_name: class名称
            client: 使用的客户端，默认源客户端
            include_vector: 是否包含向量
            include_metadata: 是否包含系统metadata
            limit: 每页数量

        Returns:
            所有对象的列表
        """
        if client is None:
            client = self.source_client

        all_objects = []
        cursor = None
        property_names = self.get_class_property_names(class_name, client)

        logger.info(f"开始获取class '{class_name}' 的所有对象...")

        # 构建 additional 字段列表
        additional_fields = ["id"]
        if include_vector:
            additional_fields.append("vector")
        if include_metadata:
            additional_fields.extend(["creationTimeUnix", "lastUpdateTimeUnix"])

        with tqdm(desc=f"获取 {class_name}", unit="对象", **self._tqdm_kwargs()) as pbar:
            while True:
                try:
                    # 构建查询
                    query = (
                        client.query
                        .get(class_name, property_names)
                        .with_additional(additional_fields)
                        .with_limit(limit)
                    )

                    # 如果有cursor,添加到查询
                    if cursor:
                        query = query.with_after(cursor)

                    # 执行查询
                    result = query.do()

                    # 检查错误
                    if "errors" in result:
                        logger.error(f"查询错误: {result['errors']}")
                        break

                    # 获取数据
                    data = result.get('data', {}).get('Get', {}).get(class_name, [])

                    if not data:
                        logger.info("没有更多数据")
                        break

                    # 添加到结果列表
                    all_objects.extend(data)
                    pbar.update(len(data))

                    # 获取下一个cursor(最后一个对象的id)
                    cursor = data[-1]['_additional']['id']

                    # 如果返回的数据少于limit,说明已经到最后了
                    if len(data) < limit:
                        logger.info("已到达最后一页")
                        break

                except Exception as e:
                    logger.error(f"获取数据时出错: {e}")
                    break

        logger.info(f"总共获取了 {len(all_objects)} 个对象")
        return all_objects

    def iter_objects_with_cursor(
        self,
        class_name: str,
        client=None,
        include_vector: bool = True,
        include_metadata: bool = True,
        limit: int = 100
    ):
        """
        使用 cursor 分页迭代对象，避免一次性加载全部数据到内存
        """
        if client is None:
            client = self.source_client

        cursor = None
        property_names = self.get_class_property_names(class_name, client)

        additional_fields = ["id"]
        if include_vector:
            additional_fields.append("vector")
        if include_metadata:
            additional_fields.extend(["creationTimeUnix", "lastUpdateTimeUnix"])

        while True:
            query = (
                client.query
                .get(class_name, property_names)
                .with_additional(additional_fields)
                .with_limit(limit)
            )

            if cursor:
                query = query.with_after(cursor)

            result = query.do()
            if "errors" in result:
                raise Exception(result["errors"])

            objects = result.get('data', {}).get('Get', {}).get(class_name, [])
            if not objects:
                break

            yield objects

            cursor = objects[-1]['_additional']['id']
            if len(objects) < limit:
                break

    def fetch_first_objects(
        self,
        class_name: str,
        client=None,
        include_vector: bool = True,
        include_metadata: bool = True,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        只获取前 N 个对象，适合抽样验证
        """
        if client is None:
            client = self.source_client

        try:
            return next(
                self.iter_objects_with_cursor(
                    class_name,
                    client=client,
                    include_vector=include_vector,
                    include_metadata=include_metadata,
                    limit=limit
                )
            )
        except StopIteration:
            return []

    def compute_object_hash(self, obj: Dict[str, Any]) -> str:
        """
        计算对象的Hash值

        Args:
            obj: 对象数据

        Returns:
            Hash字符串
        """
        # 提取properties和vector用于计算hash
        properties = {k: v for k, v in obj.items() if k != '_additional'}
        vector = obj.get('_additional', {}).get('vector')

        data = {
            "properties": properties,
            "vector": vector
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

    def get_objects_with_hash(
        self,
        class_name: str,
        client=None,
        include_vector: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        获取所有对象及其Hash值

        Args:
            class_name: class名称
            client: 使用的客户端
            include_vector: 是否包含向量

        Returns:
            {object_id: {hash, data}}
        """
        if client is None:
            client = self.source_client

        objects = self.fetch_all_objects_with_cursor(
            class_name,
            client=client,
            include_vector=include_vector,
            include_metadata=True,
            limit=100
        )

        result = {}
        for obj in objects:
            obj_id = obj['_additional']['id']
            obj_hash = self.compute_object_hash(obj)
            result[obj_id] = {
                "hash": obj_hash,
                "data": obj
            }

        return result

    def get_object_ids(
        self,
        class_name: str,
        client=None,
        limit: int = 100
    ) -> List[str]:
        """
        获取 class 下所有对象 ID，适合删除或快速校验场景

        Args:
            class_name: class 名称
            client: 查询使用的 client，默认源端
            limit: 每页数量

        Returns:
            对象 ID 列表
        """
        if client is None:
            client = self.source_client

        all_ids = []
        cursor = None

        while True:
            query = (
                client.query
                .get(class_name)
                .with_additional(["id"])
                .with_limit(limit)
            )

            if cursor:
                query = query.with_after(cursor)

            result = query.do()
            if "errors" in result:
                raise Exception(result["errors"])

            objects = result.get('data', {}).get('Get', {}).get(class_name, [])
            if not objects:
                break

            all_ids.extend(obj['_additional']['id'] for obj in objects)
            cursor = objects[-1]['_additional']['id']

            if len(objects) < limit:
                break

        return all_ids

    def get_max_last_update_time_from_objects(
        self,
        objects: List[Dict[str, Any]]
    ) -> Optional[int]:
        """从对象列表中提取最大的 lastUpdateTimeUnix"""
        max_update_time = None

        for obj in objects:
            update_time = obj.get('_additional', {}).get('lastUpdateTimeUnix')
            if update_time is None:
                continue

            if max_update_time is None or update_time > max_update_time:
                max_update_time = update_time

        return max_update_time

    def time_based_incremental(
        self,
        class_name: str,
        last_update_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        基于时间戳的增量获取

        注意: Weaviate 3.x 原生不支持按 UpdateTime 过滤
        这个方法作为备选，实际使用时会尝试时间过滤，失败则返回空列表

        Args:
            class_name: class名称
            last_update_time: 上次同步的最大更新时间(毫秒)

        Returns:
            需要同步的对象列表
        """
        try:
            # Weaviate 3.x 使用 Filter 需要额外导入
            # 这里尝试使用 lastUpdateTimeUnix 过滤
            from weaviate.filters import Filter
            property_names = self.get_class_property_names(class_name, self.source_client)

            if last_update_time:
                # 尝试时间过滤
                result = (
                    self.source_client.query
                    .get(class_name, property_names)
                    .with_additional(["id", "vector", "creationTimeUnix", "lastUpdateTimeUnix"])
                    .with_where({
                        "path": ["_lastUpdateTimeUnix"],
                        "operator": "GreaterThan",
                        "valueInt": last_update_time
                    })
                    .with_limit(10000)
                    .do()
                )

                data = result.get('data', {}).get('Get', {}).get(class_name, [])
                logger.info(f"时间戳增量获取: {len(data)} 个对象")
                return data

        except Exception as e:
            logger.warning(f"时间戳增量获取失败: {e}, 将使用Hash差异同步")

        # 返回空列表表示需要使用Hash方式
        return []

    def hash_based_incremental(
        self,
        class_name: str
    ) -> Dict[str, Any]:
        """
        基于Hash的差异同步

        Args:
            class_name: class名称

        Returns:
            同步结果: {to_add, to_update, to_delete, unchanged}
        """
        logger.info(f"开始Hash差异对比: {class_name}")

        # 获取源端所有对象
        logger.info(f"获取源端 {class_name} 对象...")
        source_objects = self.get_objects_with_hash(class_name, self.source_client)
        logger.info(f"源端对象数: {len(source_objects)}")
        source_max_update_time = self.get_max_last_update_time_from_objects(
            [item["data"] for item in source_objects.values()]
        )

        # 获取目标端所有对象
        logger.info(f"获取目标端 {class_name} 对象...")
        try:
            target_objects = self.get_objects_with_hash(class_name, self.target_client)
            logger.info(f"目标端对象数: {len(target_objects)}")
        except Exception as e:
            logger.warning(f"获取目标端对象失败: {e}, 将执行全量同步")
            return {
                "to_add": [item["data"] for item in source_objects.values()],
                "to_update": [],
                "to_delete": [],
                "unchanged": 0,
                "full_sync": True,
                "source_count": len(source_objects),
                "target_count": 0,
                "source_max_update_time": source_max_update_time,
            }

        # 计算差异
        to_add = []      # 源有，目标没有
        to_update = []   # 源和目标都有但Hash不同
        to_delete = []   # 目标有，源没有
        unchanged = 0    # 未变化的数量

        source_ids = set(source_objects.keys())
        target_ids = set(target_objects.keys())

        # 新增的对象
        for obj_id in source_ids - target_ids:
            to_add.append(source_objects[obj_id]["data"])

        # 需要更新的对象
        for obj_id in source_ids & target_ids:
            if source_objects[obj_id]["hash"] != target_objects[obj_id]["hash"]:
                to_update.append(source_objects[obj_id]["data"])
            else:
                unchanged += 1

        # 需要删除的对象
        for obj_id in target_ids - source_ids:
            to_delete.append(obj_id)

        logger.info(f"Hash差异分析结果:")
        logger.info(f"  - 需要新增: {len(to_add)}")
        logger.info(f"  - 需要更新: {len(to_update)}")
        logger.info(f"  - 需要删除: {len(to_delete)}")
        logger.info(f"  - 未变化: {unchanged}")

        return {
            "to_add": to_add,
            "to_update": to_update,
            "to_delete": to_delete,
            "unchanged": unchanged,
            "full_sync": False,
            "source_count": len(source_objects),
            "target_count": len(target_objects),
            "source_max_update_time": source_max_update_time,
        }

    def target_has_data(self, class_name: str) -> bool:
        """检查目标class是否有数据"""
        count = self.get_class_object_count(class_name, "target")
        return count > 0

    def clear_target_class(self, class_name: str) -> bool:
        """
        清空目标class的所有数据

        Args:
            class_name: class名称

        Returns:
            是否成功
        """
        try:
            logger.info(f"开始清空目标class '{class_name}' 的数据...")
            target_ids = self.get_object_ids(class_name, client=self.target_client, limit=self.batch_size)

            if not target_ids:
                logger.info(f"目标class '{class_name}' 没有数据，无需清空")
                return True

            deleted = 0
            errors = []

            for obj_id in tqdm(target_ids, desc=f"清空 {class_name}", **self._tqdm_kwargs()):
                try:
                    self.target_client.data_object.delete(
                        uuid=obj_id,
                        class_name=class_name
                    )
                    deleted += 1
                except Exception as delete_error:
                    errors.append(f"{obj_id}: {delete_error}")
                    logger.error(f"删除对象失败 {obj_id}: {delete_error}")

            remaining = self.get_class_object_count(class_name, "target")
            if remaining != 0:
                logger.error(f"清空后目标class仍有 {remaining} 条数据")
                return False

            logger.info(f"清空完成，共删除 {deleted} 个对象")
            if errors:
                logger.error(f"清空过程中有 {len(errors)} 个对象删除失败")
                return False

            return True

        except Exception as e:
            logger.error(f"清空目标class失败: {e}")
            return False

    def migrate_class_schema(self, class_name: str) -> tuple:
        """
        迁移class的schema到目标实例

        复制因子完全按目标数据库配置：
        - 如果目标端class已存在 → 保留原配置
        - 如果目标端class不存在 → 从目标数据库读取复制因子创建

        Args:
            class_name: class名称

        Returns:
            (是否成功, 复制因子)
        """
        try:
            # 获取源schema
            schema = self.source_client.schema.get()
            class_schema = None

            for cls in schema.get('classes', []):
                if cls['class'] == class_name:
                    class_schema = cls
                    break

            if not class_schema:
                logger.error(f"找不到class '{class_name}' 的schema")
                return (False, 0)

            # 检查目标是否已存在
            target_schema = self.target_client.schema.get()
            for cls in target_schema.get('classes', []):
                if cls['class'] == class_name:
                    current_replication_factor = cls.get('replicationConfig', {}).get('factor', 1)
                    logger.info(f"Class '{class_name}' 已存在于目标实例，保留原配置")
                    logger.info(
                        f"目标端 class '{class_name}' 复制因子: {current_replication_factor} "
                        f"(已有class不做复制因子变更)"
                    )
                    return (True, current_replication_factor)

            # 目标端class不存在，从目标集群状态获取复制因子
            target_replication_factor = self.get_target_default_replication_factor()

            # 移除源端的复制因子配置，使用目标端的配置
            if 'replicationConfig' in class_schema:
                class_schema['replicationConfig']['factor'] = target_replication_factor
            else:
                class_schema['replicationConfig'] = {'factor': target_replication_factor}

            # 创建class
            self.target_client.schema.create_class(class_schema)
            logger.info(f"成功创建class '{class_name}'，复制因子: {target_replication_factor}")
            return (True, target_replication_factor)

        except Exception as e:
            logger.error(f"迁移schema失败: {e}")
            return (False, 0)

    def migrate_single_object(
        self,
        class_name: str,
        obj: Dict[str, Any],
        operation: str = "upsert"
    ) -> bool:
        """
        迁移单个对象

        Args:
            class_name: class名称
            obj: 对象数据

        Returns:
            是否成功
        """
        try:
            obj_id = obj['_additional']['id']
            vector = obj['_additional'].get('vector')
            properties = {k: v for k, v in obj.items() if k != '_additional'}
            if operation == "create":
                self.target_client.data_object.create(
                    data_object=properties,
                    class_name=class_name,
                    uuid=obj_id,
                    vector=vector
                )
            elif operation == "replace":
                self.target_client.data_object.replace(
                    data_object=properties,
                    class_name=class_name,
                    uuid=obj_id,
                    vector=vector
                )
            else:
                try:
                    self.target_client.data_object.replace(
                        data_object=properties,
                        class_name=class_name,
                        uuid=obj_id,
                        vector=vector
                    )
                except Exception:
                    self.target_client.data_object.create(
                        data_object=properties,
                        class_name=class_name,
                        uuid=obj_id,
                        vector=vector
                    )
            return True
        except Exception as e:
            logger.error(f"迁移对象失败: {e}")
            return False

    def delete_single_object(self, class_name: str, obj_id: str) -> bool:
        """删除目标端单个对象"""
        try:
            self.target_client.data_object.delete(
                uuid=obj_id,
                class_name=class_name
            )
            return True
        except Exception as e:
            logger.error(f"删除对象失败 {obj_id}: {e}")
            return False

    def sync_incremental_changes(
        self,
        class_name: str,
        to_add: List[Dict[str, Any]],
        to_update: List[Dict[str, Any]],
        to_delete: List[str]
    ) -> Dict[str, Any]:
        """
        按差异执行增量同步

        Returns:
            同步统计信息
        """
        stats = {
            'total': len(to_add) + len(to_update) + len(to_delete),
            'success': 0,
            'failed': 0,
            'errors': [],
            'created': 0,
            'updated': 0,
            'deleted': 0,
        }

        for obj in tqdm(to_add, desc=f"新增 {class_name}", **self._tqdm_kwargs()):
            if self.migrate_single_object(class_name, obj, operation="create"):
                stats['success'] += 1
                stats['created'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append(f"新增失败: {obj.get('_additional', {}).get('id', 'unknown')}")

        for obj in tqdm(to_update, desc=f"更新 {class_name}", **self._tqdm_kwargs()):
            if self.migrate_single_object(class_name, obj, operation="replace"):
                stats['success'] += 1
                stats['updated'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append(f"更新失败: {obj.get('_additional', {}).get('id', 'unknown')}")

        for obj_id in tqdm(to_delete, desc=f"删除 {class_name}", **self._tqdm_kwargs()):
            if self.delete_single_object(class_name, obj_id):
                stats['success'] += 1
                stats['deleted'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append(f"删除失败: {obj_id}")

        logger.info(
            f"增量同步执行完成: 新增 {stats['created']}，更新 {stats['updated']}，删除 {stats['deleted']}，失败 {stats['failed']}"
        )
        return stats

    def sync_objects_with_upsert(
        self,
        class_name: str,
        objects: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        对一批对象执行 upsert，同步目标端状态未知时使用
        """
        stats = {
            'total': len(objects),
            'success': 0,
            'failed': 0,
            'errors': []
        }

        for obj in tqdm(objects, desc=f"回补同步 {class_name}", **self._tqdm_kwargs()):
            if self.migrate_single_object(class_name, obj, operation="upsert"):
                stats['success'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append(f"回补失败: {obj.get('_additional', {}).get('id', 'unknown')}")

        logger.info(f"回补同步完成: 成功 {stats['success']}，失败 {stats['failed']}")
        return stats

    def migrate_objects(
        self,
        class_name: str,
        objects: List[Dict[str, Any]],
        mode: str = "full"
    ) -> Dict[str, Any]:
        """
        批量迁移对象到目标实例

        Args:
            class_name: class名称
            objects: 对象列表
            mode: 迁移模式 'full' 或 'incremental'

        Returns:
            迁移统计信息
        """
        stats = {
            'total': len(objects),
            'success': 0,
            'failed': 0,
            'errors': []
        }

        logger.info(f"开始迁移 {len(objects)} 个对象到class '{class_name}' (模式: {mode})...")

        if not objects:
            return stats

        # 配置批量处理
        self.target_client.batch.configure(
            batch_size=self.batch_size,
            dynamic=True,
            timeout_retries=3,
        )

        with self.target_client.batch as batch:
            for obj in tqdm(objects, desc=f"迁移 {class_name}", **self._tqdm_kwargs()):
                try:
                    # 提取数据
                    obj_id = obj['_additional']['id']
                    vector = obj['_additional'].get('vector')
                    properties = {k: v for k, v in obj.items() if k != '_additional'}

                    # 添加到批量处理
                    batch.add_data_object(
                        data_object=properties,
                        class_name=class_name,
                        uuid=obj_id,
                        vector=vector,
                    )

                    stats['success'] += 1

                except Exception as e:
                    stats['failed'] += 1
                    error_msg = f"对象 {obj.get('_additional', {}).get('id', 'unknown')}: {str(e)}"
                    stats['errors'].append(error_msg)
                    logger.error(error_msg)

        logger.info(f"迁移完成: 成功 {stats['success']}, 失败 {stats['failed']}")
        return stats

    def migrate_objects_streaming(
        self,
        class_name: str,
        total_count: int,
        mode: str = "full"
    ) -> Dict[str, Any]:
        """
        流式迁移对象，适合大 class，按分页拉取并即时写入
        """
        stats = {
            'total': total_count,
            'success': 0,
            'failed': 0,
            'errors': [],
            'max_update_time': None,
        }

        logger.info(f"开始流式迁移 class '{class_name}'，预计对象数 {total_count} (模式: {mode})...")

        with tqdm(total=total_count, desc=f"流式迁移 {class_name}", unit="对象", **self._tqdm_kwargs()) as pbar:
            for objects in self.iter_objects_with_cursor(
                class_name,
                client=self.source_client,
                include_vector=True,
                include_metadata=True,
                limit=self.batch_size
            ):
                batch_stats = self.migrate_objects(class_name, objects, mode=mode)
                stats['success'] += batch_stats['success']
                stats['failed'] += batch_stats['failed']
                stats['errors'].extend(batch_stats['errors'][:10])

                batch_max_update_time = self.get_max_last_update_time_from_objects(objects)
                if batch_max_update_time is not None:
                    if stats['max_update_time'] is None or batch_max_update_time > stats['max_update_time']:
                        stats['max_update_time'] = batch_max_update_time

                pbar.update(len(objects))

        logger.info(f"流式迁移完成: 成功 {stats['success']}, 失败 {stats['failed']}")
        return stats

    def verify_migration(
        self,
        class_name: str,
        expected_count: int
    ) -> Dict[str, Any]:
        """
        验证迁移的数据完整性

        Args:
            class_name: class名称
            expected_count: 预期的对象数量

        Returns:
            验证结果
        """
        logger.info(f"开始验证class '{class_name}' 的数据完整性...")

        verification = {
            'class_name': class_name,
            'expected_count': expected_count,
            'actual_count': 0,
            'match': False,
            'sample_check': False,
            'errors': []
        }

        try:
            # 1. 检查总数
            actual_count = self.get_class_object_count(class_name, "target")
            target_property_names = self.get_class_property_names(class_name, self.target_client)
            verification['actual_count'] = actual_count
            verification['match'] = (actual_count == expected_count)

            if not verification['match']:
                verification['errors'].append(
                    f"数量不匹配: 预期 {expected_count}, 实际 {actual_count}"
                )

            # 2. 抽样检查metadata完整性
            sample_objects_source = self.fetch_first_objects(
                class_name,
                client=self.source_client,
                limit=10
            )

            if sample_objects_source:
                # 检查这些对象在目标中是否存在且metadata一致
                for src_obj in sample_objects_source[:5]:  # 只检查前5个
                    obj_id = src_obj['_additional']['id']

                    # 在目标中查询
                    result = (
                        self.target_client.query
                        .get(class_name, target_property_names)
                        .with_additional(["id", "vector"])
                        .with_where({
                            "path": ["id"],
                            "operator": "Equal",
                            "valueText": obj_id
                        })
                        .with_limit(1)
                        .do()
                    )

                    target_objs = result.get('data', {}).get('Get', {}).get(class_name, [])

                    if not target_objs:
                        verification['errors'].append(f"对象 {obj_id} 在目标中不存在")
                        continue

                    tgt_obj = target_objs[0]

                    # 比较properties
                    src_props = {k: v for k, v in src_obj.items() if k != '_additional'}
                    tgt_props = {k: v for k, v in tgt_obj.items() if k != '_additional'}

                    if src_props != tgt_props:
                        verification['errors'].append(
                            f"对象 {obj_id} 的metadata不匹配"
                        )
                        continue

                verification['sample_check'] = len(verification['errors']) == 0

        except Exception as e:
            verification['errors'].append(f"验证过程出错: {str(e)}")

        # 输出验证结果
        if verification['match'] and verification['sample_check']:
            logger.info(f"✓ 验证通过: class '{class_name}' 数据完整")
        else:
            logger.warning(f"✗ 验证失败: {verification['errors']}")

        return verification

    def compute_metadata_hash(self, obj: Dict[str, Any]) -> str:
        """
        计算对象 metadata 的 hash（不含 vector），适合大数据量验证

        Args:
            obj: 对象数据

        Returns:
            hash 字符串
        """
        properties = {k: v for k, v in obj.items() if k != '_additional'}
        return hashlib.sha256(json.dumps(properties, sort_keys=True, default=str).encode()).hexdigest()

    def _fetch_batch_with_cursor(
        self,
        class_name: str,
        client,
        cursor: Optional[str] = None,
        limit: int = 100,
        include_vector: bool = False
    ) -> Dict[str, Any]:
        """
        分批获取对象及其 cursor

        Returns:
            {objects: [...], next_cursor: str or None}
        """
        additional_fields = ["id"]
        if include_vector:
            additional_fields.append("vector")
        additional_fields.extend(["creationTimeUnix", "lastUpdateTimeUnix"])
        property_names = self.get_class_property_names(class_name, client)

        query = (
            client.query
            .get(class_name, property_names)
            .with_additional(additional_fields)
            .with_limit(limit)
        )

        if cursor:
            query = query.with_after(cursor)

        result = query.do()
        objects = result.get('data', {}).get('Get', {}).get(class_name, [])

        next_cursor = None
        if objects and len(objects) == limit:
            next_cursor = objects[-1]['_additional']['id']

        return {'objects': objects, 'next_cursor': next_cursor}

    def verify_with_hash_streaming(
        self,
        class_name: str,
        batch_size: int = 100,
        include_vector: bool = False
    ) -> Dict[str, Any]:
        """
        流式 hash 验证 - 分批获取逐条比对，适合大数据量（10000+）

        Args:
            class_name: class名称
            batch_size: 每批大小
            include_vector: 是否验证 vector（默认否，大数据量时省内存）

        Returns:
            验证结果
        """
        logger.info(f"开始流式 hash 验证: {class_name}, 每批 {batch_size} 条, 包含vector: {include_vector}")

        verification = {
            'class_name': class_name,
            'total_verified': 0,
            'total_source': 0,
            'total_target': 0,
            'missing_ids': [],
            'mismatched_ids': [],
            'extra_ids': [],
            'passed': False,
            'errors': []
        }

        try:
            # 分批获取并比对
            source_cursor = None
            target_cursor = None

            with tqdm(desc=f"验证 {class_name}", unit="批", **self._tqdm_kwargs()) as pbar:
                while True:
                    # 分批获取源端
                    source_result = self._fetch_batch_with_cursor(
                        class_name, self.source_client, source_cursor, batch_size, include_vector
                    )
                    source_objs = source_result['objects']
                    source_cursor = source_result['next_cursor']

                    if not source_objs:
                        break

                    # 分批获取目标端
                    target_result = self._fetch_batch_with_cursor(
                        class_name, self.target_client, target_cursor, batch_size, include_vector
                    )
                    target_objs = target_result['objects']
                    target_cursor = target_result['next_cursor']

                    # 构建目标端的 id -> hash 映射
                    target_map = {}
                    for tgt_obj in target_objs:
                        obj_id = tgt_obj['_additional']['id']
                        target_map[obj_id] = self.compute_metadata_hash(tgt_obj)

                    # 逐条比对源端对象
                    for src_obj in source_objs:
                        obj_id = src_obj['_additional']['id']
                        src_hash = self.compute_metadata_hash(src_obj)

                        verification['total_source'] += 1

                        if obj_id not in target_map:
                            verification['missing_ids'].append(obj_id)
                        elif src_hash != target_map[obj_id]:
                            verification['mismatched_ids'].append(obj_id)
                        else:
                            verification['total_verified'] += 1

                    verification['total_target'] += len(target_objs)

                    pbar.update(1)

                    if not source_cursor:
                        break

            # 检查目标端多余的对象
            if verification['total_source'] < verification['total_target']:
                logger.warning(f"目标端数据多于源端，可能存在异常")

            # 判断是否通过
            verification['passed'] = (
                len(verification['missing_ids']) == 0 and
                len(verification['mismatched_ids']) == 0
            )

            # 输出结果
            if verification['passed']:
                logger.info(f"✓ 全量验证通过: 已验证 {verification['total_verified']} 条")
            else:
                logger.warning(f"✗ 验证失败:")
                if verification['missing_ids']:
                    logger.warning(f"  - 缺失: {len(verification['missing_ids'])} 条")
                if verification['mismatched_ids']:
                    logger.warning(f"  - 不匹配: {len(verification['mismatched_ids'])} 条")

        except Exception as e:
            verification['errors'].append(f"验证过程出错: {str(e)}")
            logger.error(f"流式验证出错: {e}")

        return verification

    def verify_class_consistency(self, class_name: str) -> Dict[str, Any]:
        """
        基于全量 hash 差异验证 class 是否与源端完全一致
        """
        logger.info(f"开始严格一致性校验: {class_name}")

        verification = {
            "class_name": class_name,
            "passed": False,
            "source_count": 0,
            "target_count": 0,
            "added_diff": 0,
            "updated_diff": 0,
            "deleted_diff": 0,
            "errors": []
        }

        try:
            source_count = self.get_class_object_count(class_name, "source")
            if source_count >= MIGRATION_CONFIG["streaming_verify_threshold"]:
                logger.info(
                    f"class '{class_name}' 数据量较大({source_count})，使用流式校验替代全量内存比对"
                )
                stream_verification = self.verify_with_hash_streaming(
                    class_name,
                    batch_size=self.batch_size,
                    include_vector=False
                )
                verification["source_count"] = stream_verification.get("total_source", 0)
                verification["target_count"] = stream_verification.get("total_target", 0)
                verification["added_diff"] = len(stream_verification.get("missing_ids", []))
                verification["updated_diff"] = len(stream_verification.get("mismatched_ids", []))
                verification["deleted_diff"] = max(
                    0,
                    stream_verification.get("total_target", 0) - stream_verification.get("total_source", 0)
                )
                verification["passed"] = stream_verification.get("passed", False)
                verification["errors"].extend(stream_verification.get("errors", []))
                if not verification["passed"] and not verification["errors"]:
                    verification["errors"].append(
                        f"流式校验存在差异: 缺失 {verification['added_diff']} / 不匹配 {verification['updated_diff']}"
                    )
                return verification

            diff = self.hash_based_incremental(class_name)
            verification["source_count"] = diff.get("source_count", 0)
            verification["target_count"] = diff.get("target_count", 0)
            verification["added_diff"] = len(diff.get("to_add", []))
            verification["updated_diff"] = len(diff.get("to_update", []))
            verification["deleted_diff"] = len(diff.get("to_delete", []))
            verification["passed"] = (
                not diff.get("full_sync") and
                verification["added_diff"] == 0 and
                verification["updated_diff"] == 0 and
                verification["deleted_diff"] == 0
            )

            if not verification["passed"]:
                verification["errors"].append(
                    f"仍存在差异: 新增 {verification['added_diff']} / 更新 {verification['updated_diff']} / 删除 {verification['deleted_diff']}"
                )
        except Exception as e:
            verification["errors"].append(f"严格一致性校验失败: {e}")

        if verification["passed"]:
            logger.info(f"✓ 严格一致性校验通过: {class_name}")
        else:
            logger.warning(f"✗ 严格一致性校验失败: {verification['errors']}")

        return verification

    def migrate_class(
        self,
        class_name: str,
        force: bool = False,
        mode: str = "auto"
    ) -> Dict[str, Any]:
        """
        迁移单个class的所有数据

        Args:
            class_name: class名称
            force: 是否强制迁移(忽略增量检查)
            mode: 迁移模式 'full'(全量), 'incremental'(增量), 'auto'(自动)

        Returns:
            迁移结果
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"开始迁移class: {class_name}, 模式: {mode}")
        logger.info(f"{'='*60}")

        result = {
            'class_name': class_name,
            'mode': mode,
            'success': False,
            'source_count': 0,
            'target_count': 0,
            'migrated_count': 0,
            'replication_factor': 0,
            'skipped': False,
            'incremental_details': {},
            'errors': []
        }

        # 确定迁移模式
        is_full_sync = force or mode == "full"

        try:
            # 1. 获取源数据总数
            source_count = self.get_class_object_count(class_name, "source")
            result['source_count'] = source_count

            if source_count == 0:
                logger.warning(f"Class '{class_name}' 没有数据,跳过")
                result['success'] = True
                result['skipped'] = True
                self.state_manager.update_class_state(class_name, 0, 'completed')
                return result

            # 2. 检查目标是否有数据
            target_count_info = self.get_class_count_info(class_name, "target")
            if target_count_info["error"] is not None:
                raise ValueError(f"目标class计数失败: {target_count_info['error']}")

            result['target_count'] = target_count_info["count"] or 0
            target_has_data = target_count_info["exists"] and result['target_count'] > 0

            # 3. 判断迁移策略
            if is_full_sync:
                # 全量同步: 清空目标 -> 全量复制
                sync_mode = "full"
                logger.info(f"全量同步模式: 清空目标后全量复制")
            else:
                # 增量同步
                if not target_count_info["exists"]:
                    sync_mode = "full"
                    logger.info(f"目标class不存在,执行全量同步")
                elif not target_has_data:
                    # 目标没数据 -> 全量同步
                    sync_mode = "full"
                    logger.info(f"目标class为空,执行全量同步")
                elif source_count >= MIGRATION_CONFIG["large_class_full_sync_threshold"]:
                    sync_mode = "full"
                    logger.info(
                        f"大class检测: source_count={source_count} >= "
                        f"{MIGRATION_CONFIG['large_class_full_sync_threshold']}，切换为流式全量覆盖"
                    )
                else:
                    # 目标有数据 -> 增量同步
                    sync_mode = "incremental"
                    logger.info(f"目标class已有数据,执行增量同步")

            # 发送开始通知
            if not force:  # force 模式下不发送通知
                self.notifier.notify_migration_start(class_name, sync_mode)

            # 4. 迁移schema
            schema_success, replication_factor = self.migrate_class_schema(class_name)
            result['replication_factor'] = replication_factor
            if not schema_success:
                result['errors'].append("Schema迁移失败")
                self.state_manager.update_class_state(class_name, source_count, 'failed')
                if not force:
                    self.notifier.notify_migration_failed(class_name, sync_mode, "Schema迁移失败")
                return result

            # 5. 根据模式执行迁移
            if sync_mode == "full":
                # 全量同步: 先清空目标
                if target_has_data:
                    logger.info("清空目标数据...")
                    if not self.clear_target_class(class_name):
                        result['errors'].append("清空目标数据失败")
                        self.state_manager.update_class_state(class_name, source_count, 'failed')
                        if not force:
                            self.notifier.notify_migration_failed(class_name, sync_mode, "清空目标数据失败")
                        return result

                # 流式迁移对象，避免大 class 一次性加载全部对象到内存
                migration_stats = self.migrate_objects_streaming(class_name, source_count, mode="full")
                source_max_update_time = migration_stats.get('max_update_time')
                result['migrated_count'] = migration_stats['success']

                if migration_stats['failed'] > 0:
                    result['errors'].extend(migration_stats['errors'][:10])  # 限制错误数量

                # 验证
                verification = self.verify_migration(class_name, source_count)
                strict_verification = self.verify_class_consistency(class_name)

                result['success'] = (
                    migration_stats['failed'] == 0 and
                    verification['match'] and
                    verification['sample_check'] and
                    strict_verification['passed']
                )

                if strict_verification['errors']:
                    result['errors'].extend(strict_verification['errors'])

                # 记录状态
                self.state_manager.update_class_state(
                    class_name, source_count,
                    'completed' if result['success'] else 'failed',
                    last_update_time=source_max_update_time
                )

                # 通知结果
                if not force:
                    if result['success']:
                        details = f"成功: {result['migrated_count']}, 失败: {migration_stats['failed']}"
                        self.notifier.notify_migration_success(class_name, sync_mode, result['migrated_count'], details)
                    else:
                        error_msg = result['errors'][0] if result['errors'] else "未知错误"
                        self.notifier.notify_migration_failed(class_name, sync_mode, error_msg)

            else:
                # 默认增量策略: 目标已有数据时，直接做基于 id + hash 的差异同步
                logger.info(f"执行增量同步: {class_name}")
                logger.info("默认策略: 基于Hash差异执行新增/更新/删除同步")
                hash_result = self.hash_based_incremental(class_name)

                if hash_result.get("full_sync"):
                    # 目标获取失败，退化为对源端对象做全量 upsert
                    logger.info("目标获取失败，执行回补式全量同步")
                    objects = hash_result["to_add"]
                    source_max_update_time = hash_result.get("source_max_update_time")
                    migration_stats = self.sync_objects_with_upsert(class_name, objects)
                    result['migrated_count'] = migration_stats['success']
                    result['incremental_details'] = {
                        "added": len(objects),
                        "updated": 0,
                        "deleted": 0,
                        "unchanged": 0
                    }
                    strict_verification = self.verify_class_consistency(class_name)
                    result['success'] = migration_stats['failed'] == 0 and strict_verification['passed']

                    if migration_stats['errors']:
                        result['errors'].extend(migration_stats['errors'][:10])
                    if strict_verification['errors']:
                        result['errors'].extend(strict_verification['errors'])

                    self.state_manager.update_class_state(
                        class_name, source_count,
                        'completed' if result['success'] else 'failed',
                        last_update_time=source_max_update_time
                    )
                else:
                    migration_stats = self.sync_incremental_changes(
                        class_name,
                        hash_result["to_add"],
                        hash_result["to_update"],
                        hash_result["to_delete"]
                    )

                    result['incremental_details'] = {
                        "added": len(hash_result["to_add"]),
                        "updated": len(hash_result["to_update"]),
                        "deleted": len(hash_result["to_delete"]),
                        "unchanged": hash_result["unchanged"]
                    }

                    if not force and (hash_result["to_add"] or hash_result["to_update"] or hash_result["to_delete"]):
                        self.notifier.notify_incremental_details(
                            class_name,
                            len(hash_result["to_add"]),
                            len(hash_result["to_update"]),
                            hash_result["unchanged"],
                            deleted=len(hash_result["to_delete"])
                        )

                    logger.info(f"增量同步完成:")
                    logger.info(f"  - 新增: {len(hash_result['to_add'])}")
                    logger.info(f"  - 更新: {len(hash_result['to_update'])}")
                    logger.info(f"  - 删除: {len(hash_result['to_delete'])}")
                    logger.info(f"  - 未变化: {hash_result['unchanged']}")

                    result['migrated_count'] = migration_stats['success']
                    strict_verification = self.verify_class_consistency(class_name)
                    result['success'] = migration_stats['failed'] == 0 and strict_verification['passed']

                    if strict_verification['errors']:
                        result['errors'].extend(strict_verification['errors'])

                    self.state_manager.update_class_state(
                        class_name, source_count,
                        'completed' if result['success'] else 'failed',
                        last_update_time=hash_result.get("source_max_update_time")
                    )

                    if not force:
                        if result['success']:
                            self.notifier.notify_migration_success(
                                class_name, sync_mode, result['migrated_count'],
                                f"新增:{len(hash_result['to_add'])}, 更新:{len(hash_result['to_update'])}, 删除:{len(hash_result['to_delete'])}, 未变化:{hash_result['unchanged']}"
                            )
                        else:
                            self.notifier.notify_migration_failed(class_name, sync_mode, "部分对象迁移失败")

        except Exception as e:
            result['errors'].append(f"迁移过程出错: {str(e)}")
            logger.error(f"迁移class '{class_name}' 失败: {e}")
            self.state_manager.update_class_state(class_name, result['source_count'], 'failed')
            if not force:
                self.notifier.notify_migration_failed(class_name, sync_mode if 'sync_mode' in dir() else "unknown", str(e))

        # 获取目标端最终复制因子
        if result['replication_factor'] == 0:
            result['replication_factor'] = self.get_class_replication_factor(class_name, "target")

        return result

    def migrate_all(
        self,
        class_filter: Optional[List[str]] = None,
        force: bool = False,
        mode: str = "auto"
    ) -> Dict[str, Any]:
        """
        迁移所有class

        Args:
            class_filter: 要迁移的class列表,None表示全部
            force: 是否强制迁移(忽略增量检查)
            mode: 迁移模式 'full'(全量), 'incremental'(增量), 'auto'(自动)

        Returns:
            迁移汇总结果
        """
        logger.info("\n" + "="*60)
        logger.info(f"开始迁移 (模式: {mode}, force: {force})")
        logger.info("="*60)

        summary = {
            'total_classes': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'total_objects': 0,
            'mode': mode,
            'results': []
        }

        try:
            # 获取所有class
            classes = class_filter if class_filter else self.get_all_classes()
            summary['total_classes'] = len(classes)

            # 迁移每个class
            for class_name in classes:
                result = self.migrate_class(class_name, force=force, mode=mode)
                summary['results'].append(result)

                if result['skipped']:
                    summary['skipped'] += 1
                elif result['success']:
                    summary['successful'] += 1
                    summary['total_objects'] += result['migrated_count']
                else:
                    summary['failed'] += 1

            # 输出汇总
            logger.info("\n" + "="*60)
            logger.info("迁移汇总")
            logger.info("="*60)
            logger.info(f"模式: {mode}")
            logger.info(f"总class数: {summary['total_classes']}")
            logger.info(f"成功: {summary['successful']}")
            logger.info(f"失败: {summary['failed']}")
            logger.info(f"跳过: {summary['skipped']}")
            logger.info(f"总迁移对象数: {summary['total_objects']}")

            for result in summary['results']:
                if result['skipped']:
                    status = "⊘"
                    msg = "跳过"
                elif result['success']:
                    status = "✓"
                    msg = "成功"
                else:
                    status = "✗"
                    msg = "失败"

                # 输出详细信息
                if result.get('incremental_details'):
                    details = result['incremental_details']
                    detail_str = (
                        f" [新增:{details.get('added', 0)}, 更新:{details.get('updated', 0)}, "
                        f"删除:{details.get('deleted', 0)}, 未变化:{details.get('unchanged', 0)}]"
                    )
                else:
                    detail_str = ""

                logger.info(
                    f"{status} {result['class_name']}: {msg} - "
                    f"{result['migrated_count']}/{result['source_count']} "
                    f"[副本:{result['replication_factor']}]{detail_str}"
                )
                if result['errors']:
                    for error in result['errors']:
                        logger.error(f"  - {error}")

        except Exception as e:
            logger.error(f"迁移失败: {e}")
            summary['error'] = str(e)

        return summary


# ================================
# 测试和菜单功能
# ================================

def test_data_integrity(migrator: WeaviateMigrator):
    """测试数据完整性"""
    print("\n" + "="*60)
    print("Weaviate 数据完整性测试")
    print("="*60)

    try:
        # 获取所有class
        classes = migrator.get_all_classes()

        if not classes:
            print("\n没有找到任何class")
            return

        print(f"\n找到 {len(classes)} 个class")

        # 测试每个class的数据完整性
        for class_name in classes:
            print(f"\n{'='*60}")
            print(f"测试class: {class_name}")
            print(f"{'='*60}")

            # 获取总数
            count = migrator.get_class_object_count(class_name, "source")
            print(f"对象总数: {count}")

            if count > 0:
                # 测试cursor分页是否能获取所有数据
                print("\n测试cursor分页获取所有数据...")
                objects = migrator.fetch_all_objects_with_cursor(
                    class_name,
                    limit=100
                )

                print(f"实际获取: {len(objects)} 个对象")

                if len(objects) == count:
                    print("✓ 数据完整性测试通过!")
                else:
                    print(f"✗ 数据完整性测试失败!")
                    print(f"  预期: {count}")
                    print(f"  实际: {len(objects)}")
                    print(f"  差异: {count - len(objects)}")

                # 检查metadata完整性
                print("\n检查metadata完整性...")
                if objects:
                    sample = objects[0]
                    print(f"样本对象ID: {sample['_additional']['id']}")
                    print(f"包含向量: {'vector' in sample['_additional']}")
                    print(f"包含创建时间: {'creationTimeUnix' in sample['_additional']}")
                    print(f"包含更新时间: {'lastUpdateTimeUnix' in sample['_additional']}")
                    print(f"Properties: {list(sample.keys())}")

                    # 显示所有properties
                    for key, value in sample.items():
                        if key != '_additional':
                            print(f"  - {key}: {type(value).__name__}")

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


def show_menu():
    """显示交互式菜单"""
    print("\n" + "="*60)
    print("Weaviate 数据迁移工具")
    print("="*60)
    print("\n请选择操作模式:")
    print("-" * 60)
    print("1. 测试数据完整性")
    print("2. 全量迁移(迁移所有class)")
    print("3. 增量迁移(只迁移有变化的class)")
    print("4. 指定class迁移(自动判断全量/增量)")
    print("5. 定时增量迁移(北京时间每天0点-6点连续执行)")
    print("6. 查看迁移历史")
    print("7. 退出")
    print("-" * 60)


def get_schedule_now() -> datetime:
    """获取调度时区下的当前时间"""
    return datetime.now(ZoneInfo(MIGRATION_CONFIG["schedule_timezone"]))


def is_in_schedule_window(now: datetime) -> bool:
    """判断当前时间是否在允许的定时窗口内"""
    start_hour = MIGRATION_CONFIG["schedule_start_hour"]
    end_hour = MIGRATION_CONFIG["schedule_end_hour"]
    return start_hour <= now.hour < end_hour


def scheduled_migration(migrator: WeaviateMigrator):
    """
    定时增量迁移

    Args:
        migrator: 迁移器实例
    """
    timezone_name = MIGRATION_CONFIG["schedule_timezone"]
    start_hour = MIGRATION_CONFIG["schedule_start_hour"]
    end_hour = MIGRATION_CONFIG["schedule_end_hour"]

    print(f"\n启动定时增量迁移")
    print(f"执行窗口: 每天 {start_hour:02d}:00 - {end_hour:02d}:00 ({timezone_name})")
    print("窗口内将按 class 顺序连续迁移，跑完一个接着跑下一个")
    print("按 Ctrl+C 停止定时任务\n")

    classes = migrator.get_all_classes()
    current_index = 0

    def migrate_next_class():
        nonlocal current_index

        if current_index >= len(classes):
            current_index = 0
            logger.info("\n所有class已迁移完成,重新开始循环")

        class_name = classes[current_index]
        logger.info(f"\n定时任务: 开始迁移 class '{class_name}'")

        try:
            result = migrator.migrate_class(class_name, force=False, mode="auto")

            if result['success']:
                logger.info(f"✓ Class '{class_name}' 迁移成功")
            else:
                error_msg = result['errors'][0] if result.get('errors') else "未知错误"
                logger.error(f"✗ Class '{class_name}' 迁移失败: {error_msg}")
                raise RuntimeError(f"定时迁移失败: class={class_name}, error={error_msg}")

        except Exception as e:
            logger.error(f"迁移 class '{class_name}' 时出错: {e}")
            raise

        current_index += 1

    try:
        while True:
            now = get_schedule_now()
            in_window = is_in_schedule_window(now)

            if in_window:
                logger.info(
                    f"定时窗口命中，当前时间: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                )
                migrate_next_class()
            else:
                time.sleep(30)
    except KeyboardInterrupt:
        print("\n\n定时任务已停止")
    except Exception as e:
        logger.error(f"定时任务因异常退出: {e}")
        raise


def interactive_mode():
    """交互式模式"""
    # 初始化迁移器
    try:
        migrator = WeaviateMigrator(
            source_endpoint=SOURCE_CONFIG['endpoint'],
            source_api_key=SOURCE_CONFIG['api_key'],
            target_endpoint=TARGET_CONFIG['endpoint'],
            target_api_key=TARGET_CONFIG['api_key'],
            batch_size=MIGRATION_CONFIG['batch_size'],
            state_file=MIGRATION_CONFIG['state_file'],
            wecom_webhook=WECOM_CONFIG.get('webhook_url', '')
        )
    except Exception as e:
        print(f"\n初始化迁移器失败: {e}")
        print("\n请检查配置:")
        print(f"  源端点: {SOURCE_CONFIG['endpoint']}")
        print(f"  目标端点: {TARGET_CONFIG['endpoint']}")
        return

    while True:
        show_menu()

        try:
            choice = input("\n请输入选项 (1-7): ").strip()

            if choice == '1':
                # 测试数据完整性
                test_data_integrity(migrator)

            elif choice == '2':
                # 全量迁移
                confirm = input("\n确认执行全量迁移? (y/n): ").strip().lower()
                if confirm == 'y':
                    migrator.migrate_all(force=True, mode="full")
                else:
                    print("已取消")

            elif choice == '3':
                # 增量迁移
                print("\n开始增量迁移...")
                migrator.migrate_all(force=False, mode="auto")

            elif choice == '4':
                # 指定class迁移
                classes_input = input("\n请输入要迁移的class名称(多个用空格分隔): ").strip()
                if classes_input:
                    class_list = classes_input.split()
                    print(f"\n将迁移以下class: {class_list}")
                    confirm = input("确认? (y/n): ").strip().lower()
                    if confirm == 'y':
                        migrator.migrate_all(class_filter=class_list, force=False, mode="auto")
                    else:
                        print("已取消")
                else:
                    print("未输入class名称")

            elif choice == '5':
                # 定时增量迁移
                print("\n将在北京时间每天 0:00-6:00 窗口内连续迁移class")
                confirm = input("确认启动定时任务? (y/n): ").strip().lower()

                if confirm == 'y':
                    scheduled_migration(migrator)
                else:
                    print("已取消")

            elif choice == '6':
                # 查看迁移历史
                print(migrator.state_manager.get_migration_summary())

            elif choice == '7':
                # 退出
                print("\n再见!")
                break

            else:
                print("\n无效选项,请重新选择")

            input("\n按回车键继续...")

        except KeyboardInterrupt:
            print("\n\n已取消操作")
            break
        except Exception as e:
            print(f"\n操作失败: {e}")
            import traceback
            traceback.print_exc()
            input("\n按回车键继续...")


# ================================
# 主函数
# ================================

def main():
    """主函数"""
    print("\n" + "="*60)
    print("Weaviate 数据迁移工具")
    print("="*60)
    print("\n当前配置:")
    print(f"  源端点: {SOURCE_CONFIG['endpoint']}")
    print(f"  目标端点: {TARGET_CONFIG['endpoint']}")
    print(f"  批量大小: {MIGRATION_CONFIG['batch_size']}")
    print(f"  状态文件: {MIGRATION_CONFIG['state_file']}")
    print(f"  企业微信: {'已配置' if WECOM_CONFIG.get('webhook_url') else '未配置'}")

    # 启动交互式模式
    interactive_mode()


if __name__ == '__main__':
    main()
