"""
LLM服务 - 处理LLM调用和事实提取
"""

import asyncio
import aiohttp
import json
import random
from typing import Dict, List
from config import Config
from services.async_logging_service import log_info, log_error, log_warning
from services.unified_cache_service import unified_cache_service

class LLMService:
    """LLM服务类"""
    
    def __init__(self):
        self.session = None
        self.cache_service = unified_cache_service
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    def _get_cache_key(self, text: str, cache_type: str = "llm") -> str:
        """生成缓存键"""
        return self.cache_service.generate_cache_key(cache_type, text)
    
    def _get_llm_cache_ttl(self) -> int:
        """获取LLM缓存的随机TTL（1-3天）"""
        min_ttl = 24 * 3600  # 1天
        max_ttl = 3 * 24 * 3600  # 3天
        return random.randint(min_ttl, max_ttl)
    
    async def extract_facts(self, question: str) -> Dict:
        """提取事实 - 带缓存"""
        try:
            # 检查缓存
            cache_key = self._get_cache_key(question, "llm")
            cached_result = await self.cache_service.get("llm", cache_key)
            
            if cached_result:
                await log_info("llm", f"缓存命中: {question[:30]}...")
                return cached_result
            
            # 调用LLM
            result = await self._call_llm_with_retry(question, Config.get_llm_retry_count())
            
            if result:
                # 缓存结果
                ttl = self._get_llm_cache_ttl()
                await self.cache_service.set("llm", cache_key, result, ttl)
                await log_info("llm", f"LLM结果已缓存: TTL={ttl}秒")
            
            return result
            
        except Exception as e:
            await log_error("llm", f"事实提取失败: {e}")
            return {"contains_facts": False, "facts": []}
    
    async def _call_llm_with_retry(self, question: str, retry_count: int) -> Dict:
        """带重试机制的LLM调用"""
        # 获取提示词
        from prompts.fact_extraction import FACT_EXTRACTION_SYSTEM_PROMPT, FACT_EXTRACTION_USER_PROMPT
        
        # 构建主题字符串
        topics_dict = Config.get_predefined_topics()
        topics_str = "\n".join([f"{topic}: {', '.join(sub_topics)}" for topic, sub_topics in topics_dict.items()])

        for attempt in range(retry_count + 1):
            try:
                if not self.session:
                    self.session = aiohttp.ClientSession()
                
                # 构建用户提示词
                user_prompt = FACT_EXTRACTION_USER_PROMPT.format(
                    question=question,
                    topics=topics_str
                )
                
                payload = {
                    "model": Config.get_llm_model(),
                    "messages": [
                        {"role": "system", "content": FACT_EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": Config.get_llm_temperature()
                }
                
                async with self.session.post(
                    Config.get_llm_base_url(),
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {Config.get_llm_api_key()}",
                        "Content-Type": "application/json"
                    },
                    timeout=aiohttp.ClientTimeout(total=Config.get_llm_timeout())
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        
                        try:
                            # 处理markdown格式的JSON
                            if content.strip().startswith('```json'):
                                # 提取markdown代码块中的JSON
                                lines = content.strip().split('\n')
                                json_lines = []
                                in_json = False
                                for line in lines:
                                    if line.strip() == '```json':
                                        in_json = True
                                        continue
                                    elif line.strip() == '```':
                                        in_json = False
                                        break
                                    elif in_json:
                                        json_lines.append(line)
                                content = '\n'.join(json_lines)
                            elif content.strip().startswith('```'):
                                # 处理其他格式的代码块
                                lines = content.strip().split('\n')
                                json_lines = []
                                in_json = False
                                for line in lines:
                                    if line.strip().startswith('```'):
                                        if not in_json:
                                            in_json = True
                                        else:
                                            in_json = False
                                            break
                                    elif in_json:
                                        json_lines.append(line)
                                content = '\n'.join(json_lines)
                            
                            parsed_result = json.loads(content)
                            if attempt > 0:
                                await log_info("llm", f"LLM调用成功 (重试第{attempt}次): {question[:30]}...")
                            return parsed_result
                        except json.JSONDecodeError as e:
                            await log_error("llm", f"LLM返回格式错误: {e}, 内容: {content[:200]}...")
                            return {"contains_facts": False, "facts": []}
                    else:
                        if attempt < retry_count:
                            await log_warning("llm", f"LLM调用失败，状态码: {response.status}，准备重试 (第{attempt + 1}次)")
                            await asyncio.sleep(Config.get_llm_retry_delay() * (attempt + 1))  # 指数退避
                            continue
                        else:
                            await log_error("llm", f"LLM调用失败，状态码: {response.status}，已重试{retry_count}次")
                            return {"contains_facts": False, "facts": []}
                        
            except asyncio.TimeoutError:
                if attempt < retry_count:
                    await log_warning("llm", f"LLM调用超时，准备重试 (第{attempt + 1}次)")
                    await asyncio.sleep(Config.get_llm_retry_delay() * (attempt + 1))
                    continue
                else:
                    await log_error("llm", f"LLM调用超时，已重试{retry_count}次")
                    return {"contains_facts": False, "facts": []}
                    
            except Exception as e:
                if attempt < retry_count:
                    await log_warning("llm", f"LLM调用异常: {e}，准备重试 (第{attempt + 1}次)")
                    await asyncio.sleep(Config.get_llm_retry_delay() * (attempt + 1))
                    continue
                else:
                    await log_error("llm", f"LLM调用异常: {e}，已重试{retry_count}次")
                    return {"contains_facts": False, "facts": []}
        
        return {"contains_facts": False, "facts": []}
    
    async def call_llm_async(self, system_prompt: str, user_prompt: str) -> str:
        """通用LLM调用方法 - 用于智能过滤等场景"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            payload = {
                "model": Config.get_llm_model(),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": Config.get_llm_temperature()
            }
            
            async with self.session.post(
                Config.get_llm_base_url(),
                json=payload,
                headers={
                    "Authorization": f"Bearer {Config.get_llm_api_key()}",
                    "Content-Type": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=Config.get_llm_timeout())
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    # 处理markdown格式的JSON
                    if content.strip().startswith('```json'):
                        # 提取markdown代码块中的JSON
                        lines = content.strip().split('\n')
                        json_lines = []
                        in_json = False
                        for line in lines:
                            if line.strip() == '```json':
                                in_json = True
                                continue
                            elif line.strip() == '```':
                                in_json = False
                                break
                            elif in_json:
                                json_lines.append(line)
                        content = '\n'.join(json_lines)
                    elif content.strip().startswith('```'):
                        # 处理其他格式的代码块
                        lines = content.strip().split('\n')
                        json_lines = []
                        in_json = False
                        for line in lines:
                            if line.strip().startswith('```'):
                                if not in_json:
                                    in_json = True
                                else:
                                    in_json = False
                                    break
                            elif in_json:
                                json_lines.append(line)
                        content = '\n'.join(json_lines)
                    
                    return content
                else:
                    await log_error("llm", f"LLM调用失败，状态码: {response.status}")
                    return ""
                    
        except Exception as e:
            await log_error("llm", f"LLM调用异常: {e}")
            return ""

# 全局实例
llm_service = LLMService()
