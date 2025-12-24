"""
持久化服务 - 使用ARQ任务队列进行定时持久化
将Redis记忆持久化到ES或本地文件
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio

from services.async_logging_service import log_info, log_error, log_warning
from logging_config import get_logger
from config import Config

logger = get_logger(__name__)


class BasePersistenceBackend:
    """持久化后端基类"""
    
    async def save_facts(self, user_id: str, agent_id: Optional[str], facts: List[Dict]) -> bool:
        raise NotImplementedError
    
    async def load_facts(self, user_id: str, agent_id: Optional[str]) -> List[Dict]:
        raise NotImplementedError
    
    async def delete_facts(self, user_id: str, agent_id: Optional[str]) -> bool:
        raise NotImplementedError
    
    async def backup_all_facts(self) -> Dict[str, Any]:
        raise NotImplementedError
    
    async def restore_facts(self, backup_data: Dict[str, Any]) -> bool:
        raise NotImplementedError


class FilePersistenceBackend(BasePersistenceBackend):
    """文件持久化后端 - 使用JSON文件存储"""
    
    def __init__(self, data_dir: str = "data/persistence"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"初始化文件持久化后端: {self.data_dir}")
    
    def _get_file_path(self, user_id: str, agent_id: Optional[str] = None) -> Path:
        """获取用户事实文件路径"""
        if agent_id:
            filename = f"{user_id}_{agent_id}_facts.json"
        else:
            filename = f"{user_id}_facts.json"
        return self.data_dir / filename
    
    async def save_facts(self, user_id: str, agent_id: Optional[str], facts: List[Dict]) -> bool:
        """保存事实到JSON文件"""
        try:
            file_path = self._get_file_path(user_id, agent_id)
            
            # 准备保存数据
            save_data = {
                "user_id": user_id,
                "agent_id": agent_id,
                "facts": facts,
                "saved_at": datetime.now().isoformat(),
                "total_facts": len(facts)
            }
            
            # 异步写入文件
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._write_json_file,
                file_path,
                save_data
            )
            
            await log_info("persistence", 
                f"✅ 事实已持久化到文件: user={user_id}, agent={agent_id}, "
                f"facts={len(facts)}, file={file_path}")
            
            return True
            
        except Exception as e:
            await log_error("persistence", f"❌ 保存事实到文件失败: {e}")
            return False
    
    def _write_json_file(self, file_path: Path, data: Dict):
        """同步写入JSON文件(在executor中执行)"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    async def load_facts(self, user_id: str, agent_id: Optional[str] = None) -> List[Dict]:
        """从JSON文件加载事实"""
        try:
            file_path = self._get_file_path(user_id, agent_id)
            
            if not file_path.exists():
                await log_warning("persistence", f"⚠️ 事实文件不存在: {file_path}")
                return []
            
            # 异步读取文件
            data = await asyncio.get_event_loop().run_in_executor(
                None,
                self._read_json_file,
                file_path
            )
            
            facts = data.get("facts", [])
            await log_info("persistence", 
                f"✅ 从文件加载事实: user={user_id}, agent={agent_id}, "
                f"facts={len(facts)}, file={file_path}")
            
            return facts
            
        except Exception as e:
            await log_error("persistence", f"❌ 从文件加载事实失败: {e}")
            return []
    
    def _read_json_file(self, file_path: Path) -> Dict:
        """同步读取JSON文件(在executor中执行)"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    async def delete_facts(self, user_id: str, agent_id: Optional[str] = None) -> bool:
        """删除事实文件"""
        try:
            file_path = self._get_file_path(user_id, agent_id)
            
            if file_path.exists():
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    file_path.unlink
                )
                await log_info("persistence", f"✅ 已删除事实文件: {file_path}")
                return True
            else:
                await log_warning("persistence", f"⚠️ 事实文件不存在: {file_path}")
                return False
                
        except Exception as e:
            await log_error("persistence", f"❌ 删除事实文件失败: {e}")
            return False
    
    async def backup_all_facts(self) -> Dict[str, Any]:
        """备份所有事实文件"""
        try:
            backup_data = {
                "backup_time": datetime.now().isoformat(),
                "users": []
            }
            
            # 遍历所有事实文件
            for file_path in self.data_dir.glob("*_facts.json"):
                try:
                    data = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self._read_json_file,
                        file_path
                    )
                    backup_data["users"].append(data)
                except Exception as e:
                    await log_error("persistence", f"❌ 备份文件失败: {file_path}, {e}")
            
            await log_info("persistence", 
                f"✅ 备份完成: {len(backup_data['users'])}个用户的事实")
            
            return backup_data
            
        except Exception as e:
            await log_error("persistence", f"❌ 备份失败: {e}")
            return {"error": str(e)}
    
    async def restore_facts(self, backup_data: Dict[str, Any]) -> bool:
        """恢复事实数据"""
        try:
            users_data = backup_data.get("users", [])
            restored_count = 0
            
            for user_data in users_data:
                user_id = user_data.get("user_id")
                agent_id = user_data.get("agent_id")
                facts = user_data.get("facts", [])
                
                if await self.save_facts(user_id, agent_id, facts):
                    restored_count += 1
            
            await log_info("persistence", 
                f"✅ 恢复完成: {restored_count}/{len(users_data)}个用户的事实")
            
            return restored_count == len(users_data)
            
        except Exception as e:
            await log_error("persistence", f"❌ 恢复失败: {e}")
            return False


class ESPersistenceBackend(BasePersistenceBackend):
    """Elasticsearch持久化后端"""
    
    def __init__(self):
        from models.es_models import ESService
        self.es_service = ESService()
        self.index_name = Config.get_persistence_es_index()
        logger.info(f"初始化ES持久化后端: index={self.index_name}")
        
        # 确保索引存在
        self._ensure_index()
    
    def _ensure_index(self):
        """确保ES索引存在"""
        try:
            if not self.es_service.es.indices.exists(index=self.index_name):
                # 创建索引
                mapping = {
                    "mappings": {
                        "properties": {
                            "user_id": {"type": "keyword"},
                            "agent_id": {"type": "keyword"},
                            "facts": {"type": "object", "enabled": False},  # 存储为JSON
                            "saved_at": {"type": "date"},
                            "total_facts": {"type": "integer"}
                        }
                    }
                }
                self.es_service.es.indices.create(index=self.index_name, body=mapping)
                logger.info(f"✅ 创建ES持久化索引: {self.index_name}")
        except Exception as e:
            logger.error(f"创建ES索引失败: {e}")
    
    async def save_facts(self, user_id: str, agent_id: Optional[str], facts: List[Dict]) -> bool:
        """保存事实到ES"""
        try:
            # 文档ID: user_id 或 user_id_agent_id
            doc_id = f"{user_id}_{agent_id}" if agent_id else user_id
            
            # 准备文档
            doc = {
                "user_id": user_id,
                "agent_id": agent_id,
                "facts": facts,
                "saved_at": datetime.now().isoformat(),
                "total_facts": len(facts)
            }
            
            # 保存到ES (使用upsert)
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.es_service.es.index(
                    index=self.index_name,
                    id=doc_id,
                    body=doc
                )
            )
            
            await log_info("persistence", 
                f"✅ 事实已持久化到ES: user={user_id}, agent={agent_id}, facts={len(facts)}")
            
            return True
            
        except Exception as e:
            await log_error("persistence", f"❌ 保存事实到ES失败: {e}")
            return False
    
    async def load_facts(self, user_id: str, agent_id: Optional[str] = None) -> List[Dict]:
        """从ES加载事实"""
        try:
            doc_id = f"{user_id}_{agent_id}" if agent_id else user_id
            
            # 从ES获取
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.es_service.es.get(
                    index=self.index_name,
                    id=doc_id,
                    ignore=[404]
                )
            )
            
            if result and result.get("found"):
                facts = result["_source"].get("facts", [])
                await log_info("persistence", 
                    f"✅ 从ES加载事实: user={user_id}, agent={agent_id}, facts={len(facts)}")
                return facts
            else:
                await log_warning("persistence", f"⚠️ ES中未找到数据: {doc_id}")
                return []
            
        except Exception as e:
            await log_error("persistence", f"❌ 从ES加载事实失败: {e}")
            return []
    
    async def delete_facts(self, user_id: str, agent_id: Optional[str] = None) -> bool:
        """从ES删除事实"""
        try:
            doc_id = f"{user_id}_{agent_id}" if agent_id else user_id
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.es_service.es.delete(
                    index=self.index_name,
                    id=doc_id,
                    ignore=[404]
                )
            )
            
            await log_info("persistence", f"✅ 已从ES删除事实: {doc_id}")
            return True
            
        except Exception as e:
            await log_error("persistence", f"❌ 从ES删除事实失败: {e}")
            return False
    
    async def backup_all_facts(self) -> Dict[str, Any]:
        """备份ES中的所有事实"""
        try:
            # 查询所有文档
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.es_service.es.search(
                    index=self.index_name,
                    body={"query": {"match_all": {}}, "size": 10000}
                )
            )
            
            backup_data = {
                "backup_time": datetime.now().isoformat(),
                "backend": "elasticsearch",
                "users": []
            }
            
            for hit in result["hits"]["hits"]:
                backup_data["users"].append(hit["_source"])
            
            await log_info("persistence", 
                f"✅ ES备份完成: {len(backup_data['users'])}个用户")
            
            return backup_data
            
        except Exception as e:
            await log_error("persistence", f"❌ ES备份失败: {e}")
            return {"error": str(e)}
    
    async def restore_facts(self, backup_data: Dict[str, Any]) -> bool:
        """恢复事实到ES"""
        try:
            users_data = backup_data.get("users", [])
            restored_count = 0
            
            for user_data in users_data:
                user_id = user_data.get("user_id")
                agent_id = user_data.get("agent_id")
                facts = user_data.get("facts", [])
                
                if await self.save_facts(user_id, agent_id, facts):
                    restored_count += 1
            
            await log_info("persistence", 
                f"✅ ES恢复完成: {restored_count}/{len(users_data)}个用户")
            
            return restored_count == len(users_data)
            
        except Exception as e:
            await log_error("persistence", f"❌ ES恢复失败: {e}")
            return False


# 获取持久化后端实例的工厂函数
def get_persistence_backend():
    """获取持久化后端实例"""
    backend_type = Config.get_persistence_backend()
    if backend_type == "es":
        return ESPersistenceBackend()
    else:
        return FilePersistenceBackend()

