"""
内容压缩服务 - 针对过长的记忆内容进行智能压缩
特别优化编程、数据库等技术类记忆
"""
import re
from typing import Dict, Optional
from services.llm_service import llm_service
from services.async_logging_service import log_info, log_error
from logging_config import get_logger

logger = get_logger(__name__)


class ContentCompressionService:
    """内容压缩服务 - 智能压缩过长的记忆内容"""
    
    # 内容长度阈值配置
    COMPRESSION_THRESHOLDS = {
        "技术技能": 200,      # 技术类内容超过200字符压缩
        "工作相关": 200,      # 工作类内容超过200字符压缩
        "学习成长": 200,      # 学习类内容超过200字符压缩
        "default": 300        # 其他主题超过300字符压缩
    }
    
    # 技术关键词(用于识别技术类内容)
    TECH_KEYWORDS = [
        "编程", "开发", "代码", "函数", "类", "方法", "算法", "数据结构",
        "数据库", "SQL", "API", "接口", "框架", "库", "包", "模块",
        "Python", "Java", "JavaScript", "Go", "C++", "C#", "Ruby",
        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
        "Django", "Flask", "FastAPI", "Spring", "React", "Vue", "Angular",
        "Docker", "Kubernetes", "Linux", "命令", "配置", "部署", "运维"
    ]
    
    @classmethod
    def should_compress(cls, topic: str, content: str) -> bool:
        """判断内容是否需要压缩"""
        threshold = cls.COMPRESSION_THRESHOLDS.get(topic, cls.COMPRESSION_THRESHOLDS["default"])
        return len(content) > threshold
    
    @classmethod
    def is_technical_content(cls, content: str) -> bool:
        """判断是否为技术类内容"""
        content_lower = content.lower()
        return any(keyword.lower() in content_lower for keyword in cls.TECH_KEYWORDS)
    
    @classmethod
    async def compress_content(cls, topic: str, sub_topic: str, content: str) -> Dict[str, str]:
        """
        压缩内容
        
        返回:
            {
                "compressed": "压缩后的内容",
                "original_length": 原始长度,
                "compressed_length": 压缩后长度,
                "compression_ratio": 压缩比例
            }
        """
        try:
            # 检查是否需要压缩
            if not cls.should_compress(topic, content):
                await log_info("compression", f"内容无需压缩: topic={topic}, length={len(content)}")
                return {
                    "compressed": content,
                    "original_length": len(content),
                    "compressed_length": len(content),
                    "compression_ratio": 1.0
                }
            
            # 判断是否为技术类内容
            is_tech = cls.is_technical_content(content)
            
            # 根据内容类型选择压缩策略
            if is_tech:
                compressed = await cls._compress_technical_content(topic, sub_topic, content)
            else:
                compressed = await cls._compress_general_content(topic, sub_topic, content)
            
            original_length = len(content)
            compressed_length = len(compressed)
            compression_ratio = compressed_length / original_length if original_length > 0 else 1.0
            
            await log_info("compression", 
                f"内容压缩完成: topic={topic}, 原始长度={original_length}, "
                f"压缩后长度={compressed_length}, 压缩比={compression_ratio:.2%}")
            
            return {
                "compressed": compressed,
                "original_length": original_length,
                "compressed_length": compressed_length,
                "compression_ratio": compression_ratio
            }
            
        except Exception as e:
            await log_error("compression", f"内容压缩失败: {e}")
            # 失败时返回原内容
            return {
                "compressed": content,
                "original_length": len(content),
                "compressed_length": len(content),
                "compression_ratio": 1.0,
                "error": str(e)
            }
    
    @classmethod
    async def _compress_technical_content(cls, topic: str, sub_topic: str, content: str) -> str:
        """压缩技术类内容 - 提取核心技术要点"""
        
        prompt = f"""请将以下技术类记忆内容压缩为简洁的要点形式,保留核心技术信息。

主题: {topic}
子主题: {sub_topic}
原始内容:
{content}

压缩要求:
1. 保留关键技术术语和概念
2. 删除冗余的解释和示例代码(如果很长)
3. 使用简洁的表达方式
4. 保留核心步骤和要点
5. 如果有代码示例,只保留关键部分或用简短描述代替
6. 最终长度控制在100-150字符内

请直接返回压缩后的内容,不要添加任何解释。"""
        
        try:
            compressed = await llm_service.call_llm_async(
                system_prompt="你是一个专业的技术内容编辑助手,擅长将复杂的技术内容提炼为简洁的要点。",
                user_prompt=prompt
            )
            
            # 清理可能的多余空白
            compressed = cls._clean_content(compressed)
            
            # 如果压缩后仍然过长,进行二次压缩
            if len(compressed) > 200:
                compressed = await cls._secondary_compression(compressed, target_length=150)
            
            return compressed
            
        except Exception as e:
            await log_error("compression", f"技术内容压缩失败: {e}")
            # 失败时使用简单压缩
            return cls._simple_compress(content, 150)
    
    @classmethod
    async def _compress_general_content(cls, topic: str, sub_topic: str, content: str) -> str:
        """压缩通用类内容 - 保留核心信息"""
        
        prompt = f"""请将以下记忆内容压缩为简洁的核心信息。

主题: {topic}
子主题: {sub_topic}
原始内容:
{content}

压缩要求:
1. 保留最核心的信息和关键点
2. 删除冗余的描述和细节
3. 使用精炼的表达
4. 保留时间、地点、人物等关键要素
5. 最终长度控制在150-200字符内

请直接返回压缩后的内容,不要添加任何解释。"""
        
        try:
            compressed = await llm_service.call_llm_async(
                system_prompt="你是一个专业的内容编辑助手,擅长提炼文本的核心信息。",
                user_prompt=prompt
            )
            
            # 清理可能的多余空白
            compressed = cls._clean_content(compressed)
            
            # 如果压缩后仍然过长,进行二次压缩
            if len(compressed) > 250:
                compressed = await cls._secondary_compression(compressed, target_length=200)
            
            return compressed
            
        except Exception as e:
            await log_error("compression", f"通用内容压缩失败: {e}")
            # 失败时使用简单压缩
            return cls._simple_compress(content, 200)
    
    @classmethod
    async def _secondary_compression(cls, content: str, target_length: int = 150) -> str:
        """二次压缩 - 针对首次压缩后仍然过长的内容"""
        
        prompt = f"""以下内容仍然过长,请进一步压缩到{target_length}字符以内,只保留最核心的信息。

内容:
{content}

要求:
1. 只保留绝对核心的信息
2. 使用最精炼的表达
3. 严格控制在{target_length}字符以内

请直接返回压缩后的内容。"""
        
        try:
            compressed = await llm_service.call_llm_async(
                system_prompt="你是一个专业的内容精炼助手。",
                user_prompt=prompt
            )
            
            return cls._clean_content(compressed)
            
        except Exception as e:
            await log_error("compression", f"二次压缩失败: {e}")
            # 失败时使用简单截断
            return content[:target_length] + "..."
    
    @classmethod
    def _simple_compress(cls, content: str, max_length: int = 200) -> str:
        """简单压缩 - 作为LLM压缩失败时的后备方案"""
        if len(content) <= max_length:
            return content
        
        # 尝试按句子截断
        sentences = re.split(r'[。！？.!?]', content)
        compressed = ""
        
        for sentence in sentences:
            if len(compressed) + len(sentence) <= max_length - 3:
                compressed += sentence + "。"
            else:
                break
        
        if not compressed:
            # 如果第一句就太长,直接截断
            compressed = content[:max_length - 3] + "..."
        
        return compressed
    
    @classmethod
    def _clean_content(cls, content: str) -> str:
        """清理内容中的多余空白和格式"""
        # 移除多余的空行
        content = re.sub(r'\n\s*\n', '\n', content)
        # 移除行首行尾空白
        content = '\n'.join(line.strip() for line in content.split('\n'))
        # 移除多余空格
        content = re.sub(r'\s+', ' ', content)
        return content.strip()
    
    @classmethod
    async def batch_compress_facts(cls, facts: list) -> list:
        """批量压缩事实列表"""
        compressed_facts = []
        
        for fact in facts:
            topic = fact.get("topic", "")
            sub_topic = fact.get("sub_topic", "")
            memo = fact.get("memo", "")
            
            # 压缩内容
            result = await cls.compress_content(topic, sub_topic, memo)
            
            # 创建压缩后的事实
            compressed_fact = fact.copy()
            compressed_fact["memo"] = result["compressed"]
            compressed_fact["original_memo"] = memo  # 保存原始内容
            compressed_fact["compression_info"] = {
                "original_length": result["original_length"],
                "compressed_length": result["compressed_length"],
                "compression_ratio": result["compression_ratio"]
            }
            
            compressed_facts.append(compressed_fact)
        
        return compressed_facts


# 创建全局单例
content_compression_service = ContentCompressionService()

