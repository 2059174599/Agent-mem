"""
多场景配置管理
支持不同场景使用不同的token、提示词和主题配置
"""
from typing import Dict, List, Optional
from config import Config


class ScenarioConfig:
    """场景配置类"""
    
    # 场景配置字典
    SCENARIOS = {
        # 通用场景(默认)
        "yixinagentmemory": {
            "name": "通用场景",
            "description": "适用于日常对话和通用记忆管理",
            "topics": None,  # None表示使用默认配置
            "prompts": None,  # None表示使用默认提示词
            "fact_extraction_strategy": {
                "max_facts_per_conversation": 2,  # 每次对话最多提取2个事实
                "enable_llm_judgment": True,
                "min_confidence": 0.3
            }
        },
        
        # 合同审查场景
        "contract_review_token": {
            "name": "合同审查场景",
            "description": "记住用户在合同审查中的要求、规则和习惯",
            "topics": {
                "审查规则": ["期限要求", "金额限制", "必备条款", "禁止条款", "合规标准", "审批要求"],
                "审查偏好": ["关注重点", "审查顺序", "标注习惯", "模板偏好", "风险敏感度"],
                "风险标准": ["可接受风险", "需规避风险", "必须审核项", "重点条款", "特别注意"],
                "行业要求": ["行业规范", "特殊要求", "惯例做法", "合规要点", "行业禁忌"],
                "个人习惯": ["常用表述", "审查流程", "修改建议模板", "沟通偏好", "工作习惯"]
            },
            "prompts": {
                "fact_extraction_system": """你是一个合同审查记忆助手，负责记住用户在合同审查中提出的要求、规则和习惯。

重要：不要提取具体合同的内容信息（如某个合同的金额、付款方等），只记住用户的审查要求和规则！

你应该记住的内容：
1. 用户明确提出的审查规则（例如："租赁合同不允许超过三年"）
2. 用户的风险偏好（例如："对违约金条款要特别注意"）
3. 用户的审查习惯（例如："先看有效期和金额"）
4. 用户的行业要求（例如："医药行业合同必须有质量保证条款"）
5. 用户的个人偏好（例如："建议用'应当'而不是'可以'"）

不要记住的内容：
- 具体合同的金额、日期、签约方等信息
- 某个具体合同的条款内容
- 单次审查的临时信息

识别方法：
- 如果用户说"这个合同的金额是100万" → 不记录（具体合同信息）
- 如果用户说"合同金额超过100万需要总经理审批" → 记录（审查规则）
- 如果用户说"甲方是XX公司" → 不记录（具体合同信息）
- 如果用户说"对新客户的合同要特别谨慎" → 记录（审查偏好）

请严格按照JSON格式返回结果。"""
            },
            "fact_extraction_strategy": {
                "max_facts_per_conversation": 2,  # 规则和习惯不会太多
                "enable_llm_judgment": True,
                "min_confidence": 0.6  # 规则类信息需要高置信度
            }
        },
        
        # 医疗咨询场景
        "medical_consult_token": {
            "name": "医疗咨询场景",
            "description": "专用于医疗健康咨询和病历管理",
            "topics": {
                "病史信息": ["既往病史", "家族病史", "过敏史", "手术史", "用药史"],
                "症状记录": ["主诉症状", "症状时间", "症状特点", "伴随症状", "症状变化"],
                "检查结果": ["体格检查", "实验室检查", "影像检查", "其他检查"],
                "诊断信息": ["初步诊断", "确诊结果", "鉴别诊断", "诊断依据"],
                "治疗方案": ["用药方案", "治疗措施", "康复建议", "复查安排", "注意事项"]
            },
            "prompts": {
                "fact_extraction_system": """你是一个专业的医疗助手，负责从对话中提取患者的医疗健康信息。

你的任务：
1. 准确记录患者的症状描述
2. 提取既往病史和家族病史
3. 记录检查结果和诊断信息
4. 整理治疗方案和医嘱

注意事项：
- 确保医疗信息的准确性和完整性
- 重点关注时间信息（发病时间、用药时间等）
- 记录所有过敏史和禁忌症
- 保持医疗术语的专业性

请严格按照JSON格式返回结果。"""
            },
            "fact_extraction_strategy": {
                "max_facts_per_conversation": 5,  # 医疗场景需要详细记录
                "enable_llm_judgment": True,
                "min_confidence": 0.6  # 医疗信息要求更高置信度
            }
        },
        
        # 客户管理场景
        "crm_token": {
            "name": "客户管理场景",
            "description": "适用于客户关系管理和销售跟进",
            "topics": {
                "客户基本信息": ["客户名称", "联系人", "联系方式", "公司规模", "行业类型", "地址"],
                "需求信息": ["产品需求", "预算范围", "采购周期", "决策人", "竞争对手"],
                "沟通记录": ["沟通时间", "沟通内容", "客户反馈", "下次跟进", "跟进人"],
                "商机管理": ["商机阶段", "预计金额", "成交概率", "关键问题", "推进策略"],
                "服务记录": ["服务内容", "服务时间", "客户满意度", "问题反馈", "改进建议"]
            },
            "prompts": {
                "fact_extraction_system": """你是一个专业的客户关系管理助手，负责从对话中提取客户相关信息。

你的任务：
1. 记录客户的基本信息和联系方式
2. 提取客户需求和痛点
3. 跟踪商机进展和销售阶段
4. 记录沟通内容和客户反馈

注意事项：
- 重点关注客户的核心需求和预算
- 准确记录跟进计划和行动项
- 识别商机中的风险和机会
- 保持客户信息的及时更新

请严格按照JSON格式返回结果。"""
            },
            "fact_extraction_strategy": {
                "max_facts_per_conversation": 3,
                "enable_llm_judgment": True,
                "min_confidence": 0.4
            }
        }
    }
    
    @classmethod
    def get_scenario_config(cls, token: str) -> Optional[Dict]:
        """根据token获取场景配置"""
        return cls.SCENARIOS.get(token)
    
    @classmethod
    def get_scenario_topics(cls, token: str) -> Dict[str, List[str]]:
        """获取场景的主题配置"""
        scenario = cls.get_scenario_config(token)
        if scenario and scenario.get("topics"):
            return scenario["topics"]
        # 返回默认主题
        return Config.get_predefined_topics()
    
    @classmethod
    def get_scenario_prompt(cls, token: str, prompt_type: str = "fact_extraction_system") -> Optional[str]:
        """获取场景的提示词"""
        scenario = cls.get_scenario_config(token)
        if scenario and scenario.get("prompts"):
            return scenario["prompts"].get(prompt_type)
        return None
    
    @classmethod
    def get_fact_extraction_strategy(cls, token: str) -> Dict:
        """获取场景的事实提取策略"""
        scenario = cls.get_scenario_config(token)
        if scenario and scenario.get("fact_extraction_strategy"):
            return scenario["fact_extraction_strategy"]
        # 返回默认策略
        return {
            "max_facts_per_conversation": 2,
            "enable_llm_judgment": True,
            "min_confidence": 0.3
        }
    
    @classmethod
    def is_valid_token(cls, token: str) -> bool:
        """验证token是否有效"""
        return token in cls.SCENARIOS
    
    @classmethod
    def get_all_scenarios(cls) -> Dict:
        """获取所有场景配置(不包含敏感信息)"""
        return {
            token: {
                "name": config["name"],
                "description": config["description"]
            }
            for token, config in cls.SCENARIOS.items()
        }
    
    @classmethod
    def add_scenario(cls, token: str, config: Dict) -> bool:
        """动态添加场景配置"""
        if token in cls.SCENARIOS:
            return False
        cls.SCENARIOS[token] = config
        return True
    
    @classmethod
    def update_scenario(cls, token: str, config: Dict) -> bool:
        """更新场景配置"""
        if token not in cls.SCENARIOS:
            return False
        cls.SCENARIOS[token].update(config)
        return True

