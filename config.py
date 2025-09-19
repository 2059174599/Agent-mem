import os
from typing import List, Dict

class Config:
    """配置类 - 优先从环境变量获取，环境变量中没有则从配置文件获取"""
    
    @classmethod
    def get_env_or_default(cls, env_key: str, default_value: str) -> str:
        """从环境变量获取配置，如果没有则返回默认值"""
        return os.getenv(env_key, default_value)
    
    @classmethod
    def get_env_or_default_int(cls, env_key: str, default_value: int) -> int:
        """从环境变量获取整数配置，如果没有则返回默认值"""
        env_value = os.getenv(env_key)
        if env_value is not None:
            try:
                return int(env_value)
            except ValueError:
                print(f"警告: 环境变量 {env_key}={env_value} 不是有效的整数，使用默认值 {default_value}")
        return default_value
    
    @classmethod
    def get_env_or_default_bool(cls, env_key: str, default_value: bool) -> bool:
        """从环境变量获取布尔配置，如果没有则返回默认值"""
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value.lower() in ('true', '1', 'yes', 'on')
        return default_value
    
    @classmethod
    def get_env_or_default_float(cls, env_key: str, default_value: float) -> float:
        """从环境变量获取浮点数配置，如果没有则返回默认值"""
        env_value = os.getenv(env_key)
        if env_value is not None:
            try:
                return float(env_value)
            except ValueError:
                print(f"警告: 环境变量 {env_key}={env_value} 不是有效的浮点数，使用默认值 {default_value}")
        return default_value
    
    @classmethod
    def get_env_or_default_list(cls, env_key: str, default_value: List[str]) -> List[str]:
        """从环境变量获取列表配置，如果没有则返回默认值"""
        env_value = os.getenv(env_key)
        if env_value is not None:
            # 支持逗号分隔的字符串转换为列表
            return [item.strip() for item in env_value.split(',') if item.strip()]
        return default_value
    
    # ==================== 基础配置 ====================
    
    @classmethod
    def get_es_host(cls) -> str:
        return cls.get_env_or_default("ES_HOST", "http://localhost:9200")
    
    @classmethod
    def get_es_hosts(cls) -> list:
        """
        获取ES集群节点列表
        支持两种配置方式：
        1. ES_HOST: 单节点配置（向后兼容）
        2. ES_HOSTS: 多节点配置，逗号分隔，例如: "http://es1:9200,http://es2:9200,http://es3:9200"
        """
        hosts_str = cls.get_env_or_default("ES_HOSTS", "")
        if hosts_str:
            # 多节点配置
            return [host.strip() for host in hosts_str.split(",") if host.strip()]
        else:
            # 单节点配置（向后兼容）
            return [cls.get_es_host()]
    
    @classmethod
    def get_es_username(cls) -> str:
        return cls.get_env_or_default("ES_USERNAME", "elastic")
    
    @classmethod
    def get_es_password(cls) -> str:
        return cls.get_env_or_default("ES_PASSWORD", "difyai123456")
    
    @classmethod
    def get_es_chat_index(cls) -> str:
        return cls.get_env_or_default("ES_CHAT_INDEX", "aigc_user_dialogs")
    
    @classmethod
    def get_redis_host(cls) -> str:
        return cls.get_env_or_default("REDIS_HOST", "localhost")
    
    @classmethod
    def get_redis_port(cls) -> int:
        return cls.get_env_or_default_int("REDIS_PORT", 6379)
    
    @classmethod
    def get_redis_password(cls) -> str:
        return cls.get_env_or_default("REDIS_PASSWORD", "difyai123456")
    
    @classmethod
    def get_redis_db(cls) -> int:
        """获取Redis数据库编号 - 统一使用一个数据库"""
        return cls.get_env_or_default_int("REDIS_DB", 0)
    
    @classmethod
    def get_redis_cache_db(cls) -> int:
        """获取Redis缓存数据库编号 - 与主数据库相同"""
        return cls.get_redis_db()
    
    @classmethod
    def get_embedding_cache_ttl(cls) -> int:
        """获取embedding缓存TTL（秒）- 1-3个月，因为embedding不会变化"""
        return cls.get_env_or_default_int("EMBEDDING_CACHE_TTL", 2 * 30 * 24 * 3600)  # 默认2个月
    
    @classmethod
    def get_embedding_cache_ttl_min(cls) -> int:
        """获取embedding缓存最小TTL（秒）- 1个月"""
        return cls.get_env_or_default_int("EMBEDDING_CACHE_TTL_MIN", 1 * 30 * 24 * 3600)
    
    @classmethod
    def get_embedding_cache_ttl_max(cls) -> int:
        """获取embedding缓存最大TTL（秒）- 3个月"""
        return cls.get_env_or_default_int("EMBEDDING_CACHE_TTL_MAX", 3 * 30 * 24 * 3600)
    
    @classmethod
    def get_llm_base_url(cls) -> str:
        return cls.get_env_or_default("LLM_BASE_URL", "http://aigc-api.aigc.paas.corp/v1/chat/completions")
    
    @classmethod
    def get_llm_api_key(cls) -> str:
        return cls.get_env_or_default("LLM_API_KEY", "sk-ftmE4M3322c945i6A3TONZk8Oe2Op7nB1hChD3029EJGLX1A")
    
    @classmethod
    def get_llm_model(cls) -> str:
        return cls.get_env_or_default("LLM_MODEL", "gpt-4")

    @classmethod
    def get_llm_temperature(cls) -> float:
        return cls.get_env_or_default_float("LLM_TEMPERATURE", 0.1)
    
    @classmethod
    def get_llm_timeout(cls) -> int:
        return cls.get_env_or_default_int("LLM_TIMEOUT", 30)
    
    @classmethod
    def get_llm_retry_count(cls) -> int:
        return cls.get_env_or_default_int("LLM_RETRY_COUNT", 3)
    
    @classmethod
    def get_llm_retry_delay(cls) -> float:
        return cls.get_env_or_default_float("LLM_RETRY_DELAY", 1.0)
    
    @classmethod
    def get_embedding_base_url(cls) -> str:
        return cls.get_env_or_default("EMBEDDING_BASE_URL", "http://aigc-api.aigc.paas.test/v1/embeddings")
    
    @classmethod
    def get_embedding_api_key(cls) -> str:
        return cls.get_env_or_default("EMBEDDING_API_KEY", "sk-YC9Utxm3F4WBjQqFWCwuU9Tdk26i45zDa6637w7rTc3WyvYP")
    
    @classmethod
    def get_embedding_model(cls) -> str:
        return cls.get_env_or_default("EMBEDDING_MODEL", "bge-m3")
    
    @classmethod
    def get_embedding_timeout(cls) -> int:
        return cls.get_env_or_default_int("EMBEDDING_TIMEOUT", 30)
    
    @classmethod
    def get_embedding_retry_count(cls) -> int:
        return cls.get_env_or_default_int("EMBEDDING_RETRY_COUNT", 3)
    
    @classmethod
    def get_embedding_retry_delay(cls) -> float:
        return cls.get_env_or_default_float("EMBEDDING_RETRY_DELAY", 1.0)
    
    @classmethod
    def get_bge_m3_dims(cls) -> int:
        return cls.get_env_or_default_int("BGE_M3_DIMS", 1024)
    
    # ==================== 事实管理配置 ====================
    
    @classmethod
    def get_predefined_topics(cls) -> Dict[str, List[str]]:
        """获取预定义主题和子主题"""
        return {
            "兴趣爱好": cls.get_env_or_default_list("TOPIC_HOBBY", [
                "电影", "音乐", "阅读", "运动", "游戏", "旅行", "美食", "摄影", "画画", "唱歌", "跳舞", "收藏", "园艺", "手工",
                "书法", "编程", "写作", "设计", "建筑", "其他"
            ]),
            "个人信息": cls.get_env_or_default_list("TOPIC_PERSONAL", [
                "姓名", "年龄", "职业", "教育背景", "家庭状况", "联系方式", "地址", "生日", "星座", "血型", "身高体重", "外貌特征",
                "性格特点", "特长技能", "语言能力", "学历", "专业", "学校", "婚姻状况", "居住地", "其他"
            ]),
            "工作相关": cls.get_env_or_default_list("TOPIC_WORK", [
                "工作内容", "技能特长", "项目经验", "职业规划", "工作习惯", "公司信息", "职位级别", "薪资待遇", "同事关系", "工作环境",
                "工作地点", "工作压力", "工作成就", "工作目标", "工作效率", "工作态度", "团队合作", "沟通能力", "解决问题", "其他"
            ]),
            "生活习惯": cls.get_env_or_default_list("TOPIC_LIFESTYLE", [
                "作息时间", "饮食习惯", "运动习惯", "消费习惯", "学习习惯", "卫生习惯", "社交习惯", "娱乐习惯", "睡眠质量", "压力管理",
                "起床时间", "睡觉时间", "用餐时间", "食物偏好", "运动类型", "运动频率", "购物习惯", "消费观念", "学习时间", "其他"
            ]),
            "情感偏好": cls.get_env_or_default_list("TOPIC_EMOTION", [
                "性格特点", "价值观", "社交偏好", "情感状态", "人际关系", "沟通方式", "决策风格", "压力应对", "生活态度", "情绪管理",
                "情感表达", "情感需求", "乐观程度", "焦虑程度", "幸福感", "安全感", "归属感", "成就感", "社交需求", "其他"
            ]),
            "学习成长": cls.get_env_or_default_list("TOPIC_LEARNING", [
                "学习目标", "学习方法", "知识领域", "技能提升", "成长经历", "反思总结", "未来规划", "学习资源", "学习环境", "学习效果",
                "学习动机", "学习兴趣", "学习能力", "学习策略", "学习技巧", "学习计划", "学习成果", "学习习惯", "学习时间", "其他"
            ]),
            "人际关系": cls.get_env_or_default_list("TOPIC_RELATIONSHIP", [
                "朋友关系", "家庭关系", "同事关系", "恋人关系", "社交圈子", "沟通技巧", "冲突处理", "情感支持", "信任建立", "边界设定",
                "父母关系", "兄弟姐妹", "亲戚关系", "客户关系", "合作伙伴", "邻居关系", "网络关系", "亲密关系", "沟通频率", "其他"
            ]),
            "健康医疗": cls.get_env_or_default_list("TOPIC_HEALTH", [
                "身体状况", "疾病历史", "用药情况", "检查结果", "治疗方案", "康复进展", "预防措施", "健康习惯", "心理状态", "就医经历",
                "身高体重", "血压血糖", "心率呼吸", "视力听力", "遗传病史", "个人病史", "手术史", "过敏史", "慢性病", "其他"
            ]),
            "财务理财": cls.get_env_or_default_list("TOPIC_FINANCE", [
                "收入情况", "支出情况", "储蓄情况", "投资情况", "负债情况", "资产情况", "保险情况", "税务情况", "理财规划", "财务目标",
                "工资收入", "奖金收入", "投资收益", "生活支出", "住房支出", "交通支出", "银行存款", "基金投资", "股票投资", "其他"
            ]),
            "技术技能": cls.get_env_or_default_list("TOPIC_TECHNOLOGY", [
                "编程语言", "开发工具", "操作系统", "数据库", "网络技术", "云计算", "人工智能", "大数据", "区块链", "物联网",
                "前端开发", "后端开发", "移动开发", "算法设计", "数据结构", "软件工程", "项目管理", "测试技术", "安全技术", "其他"
            ]),
            "娱乐休闲": cls.get_env_or_default_list("TOPIC_ENTERTAINMENT", [
                "电影类型", "音乐类型", "游戏类型", "运动类型", "旅游类型", "美食类型", "购物类型", "社交类型", "学习类型", "创作类型",
                "观影习惯", "听歌习惯", "游戏习惯", "运动习惯", "旅游习惯", "美食习惯", "购物习惯", "社交习惯", "学习习惯", "其他"
            ])
        }
    
    @classmethod
    def get_topic_keywords(cls) -> Dict[str, List[str]]:
        """获取主题关键词映射"""
        return {
            "兴趣爱好": cls.get_env_or_default_list("KEYWORDS_HOBBY", [
                "喜欢", "爱好", "兴趣", "热爱", "享受", "沉迷", "擅长", "精通", "经常", "总是", "习惯"
            ]),
            "个人信息": cls.get_env_or_default_list("KEYWORDS_PERSONAL", [
                "姓名", "年龄", "职业", "教育", "家庭", "联系", "电话", "邮箱", "地址", "生日", "星座", "血型",
                "叫", "名字", "称呼", "身份", "角色", "自称"
            ]),
            "工作相关": cls.get_env_or_default_list("KEYWORDS_WORK", [
                "工作", "职业", "技能", "项目", "经验", "规划", "习惯", "公司", "职位", "薪资", "同事", "老板", "客户", "上班"
            ]),
            "生活习惯": cls.get_env_or_default_list("KEYWORDS_LIFESTYLE", [
                "作息", "饮食", "运动", "消费", "学习", "起床", "睡觉", "吃饭", "洗澡", "刷牙", "锻炼", "健身", "每天", "经常"
            ]),
            "情感偏好": cls.get_env_or_default_list("KEYWORDS_EMOTION", [
                "性格", "价值观", "社交", "情感", "心情", "感受", "想法", "态度", "观点", "信念", "原则", "觉得", "认为",
                "叫", "名字", "称呼", "自称", "助手", "AI", "机器人", "偏好", "喜欢", "希望", "想要", "希望"
            ]),
            "学习成长": cls.get_env_or_default_list("KEYWORDS_LEARNING", [
                "学习", "读书", "课程", "培训", "技能", "知识", "成长", "进步", "目标", "计划", "反思", "提升", "掌握"
            ]),
            "人际关系": cls.get_env_or_default_list("KEYWORDS_RELATIONSHIP", [
                "朋友", "家人", "同事", "恋人", "社交", "关系", "沟通", "相处", "理解", "支持", "帮助", "信任", "关心"
            ]),
            "健康医疗": cls.get_env_or_default_list("KEYWORDS_HEALTH", [
                "健康", "身体", "疾病", "症状", "医生", "医院", "药物", "治疗", "检查", "康复", "预防", "感觉", "不适"
            ]),
            "财务理财": cls.get_env_or_default_list("KEYWORDS_FINANCE", [
                "财务", "理财", "投资", "储蓄", "消费", "收入", "支出", "预算", "资金", "资产", "负债", "保险", "税务", "经济",
                "金钱", "费用", "成本", "收益", "利润", "亏损", "风险", "回报", "规划", "管理"
            ]),
            "技术技能": cls.get_env_or_default_list("KEYWORDS_TECHNOLOGY", [
                "技术", "技能", "编程", "开发", "软件", "硬件", "系统", "网络", "数据", "算法", "代码", "程序", "应用", "平台",
                "科技", "创新", "研发", "设计", "实现", "优化", "维护", "升级", "学习", "掌握"
            ]),
            "娱乐休闲": cls.get_env_or_default_list("KEYWORDS_ENTERTAINMENT", [
                "娱乐", "休闲", "放松", "享受", "乐趣", "快乐", "开心", "满足", "愉悦", "轻松", "自由", "时间", "活动", "方式",
                "消遣", "游戏", "电影", "音乐", "阅读", "运动", "旅游", "购物", "社交", "聚会"
            ])
        }
    
    @classmethod
    def get_synonyms_mapping(cls) -> Dict[str, List[str]]:
        """获取同义词映射"""
        return {
            # 兴趣爱好相关
            "电影": cls.get_env_or_default_list("SYNONYMS_MOVIE", ["片子", "影片", "影视", "cinema", "movie", "film", "看电影", "观影"]),
            "音乐": cls.get_env_or_default_list("SYNONYMS_MUSIC", ["歌曲", "歌", "曲子", "music", "song", "旋律", "听歌", "听音乐"]),
            "阅读": cls.get_env_or_default_list("SYNONYMS_READING", ["读书", "看书", "阅读", "读书", "阅读", "看书", "读书"]),
            "运动": cls.get_env_or_default_list("SYNONYMS_SPORT", ["锻炼", "健身", "跑步", "exercise", "sport", "活动", "运动", "健身"]),
            "游戏": cls.get_env_or_default_list("SYNONYMS_GAME", ["打游戏", "玩游戏", "游戏", "game", "娱乐", "消遣"]),
            "旅行": cls.get_env_or_default_list("SYNONYMS_TRAVEL", ["旅游", "旅行", "出去玩", "travel", "旅游", "旅行"]),
            "美食": cls.get_env_or_default_list("SYNONYMS_FOOD", ["吃", "美食", "食物", "food", "吃饭", "用餐", "饮食"]),
            
            # 工作相关
            "工作": cls.get_env_or_default_list("SYNONYMS_WORK", ["职业", "上班", "打工", "job", "work", "career", "职业", "做什么", "做什么工作", "从事什么", "职业是什么"]),
            "做什么": cls.get_env_or_default_list("SYNONYMS_WHAT_DO", ["工作", "职业", "从事", "做什么工作", "职业是什么", "干什么", "做什么的"]),
            "做什么工作": cls.get_env_or_default_list("SYNONYMS_WHAT_WORK", ["工作", "职业", "从事", "做什么", "职业是什么", "干什么", "做什么的"]),
            "职业": cls.get_env_or_default_list("SYNONYMS_CAREER", ["工作", "职业", "从事", "做什么", "职业是什么", "干什么", "做什么的"]),
            "程序员": cls.get_env_or_default_list("SYNONYMS_PROGRAMMER", ["编程", "开发", "码农", "programmer", "developer", "写代码", "编程"]),
            "编程": cls.get_env_or_default_list("SYNONYMS_PROGRAMMING", ["程序员", "开发", "码农", "programmer", "developer", "写代码", "编程"]),
            "开发": cls.get_env_or_default_list("SYNONYMS_DEVELOPMENT", ["程序员", "编程", "码农", "programmer", "developer", "写代码", "开发"]),
            "码农": cls.get_env_or_default_list("SYNONYMS_CODER", ["程序员", "编程", "开发", "programmer", "developer", "写代码", "码农"]),
            "写代码": cls.get_env_or_default_list("SYNONYMS_CODING", ["程序员", "编程", "开发", "码农", "programmer", "developer", "写代码"]),
            "设计师": cls.get_env_or_default_list("SYNONYMS_DESIGNER", ["设计", "美工", "designer", "设计", "美术", "创意"]),
            "销售": cls.get_env_or_default_list("SYNONYMS_SALES", ["卖东西", "销售", "sales", "推销", "销售", "卖货"]),
            "卖东西": cls.get_env_or_default_list("SYNONYMS_SELL", ["销售", "卖货", "sales", "推销", "销售", "卖东西"]),
            "老师": cls.get_env_or_default_list("SYNONYMS_TEACHER", ["教师", "老师", "teacher", "教学", "教育", "教书"]),
            "医生": cls.get_env_or_default_list("SYNONYMS_DOCTOR", ["大夫", "医生", "doctor", "医疗", "看病", "治疗"]),
            
            # 学习相关
            "学习": cls.get_env_or_default_list("SYNONYMS_STUDY", ["读书", "上课", "培训", "study", "learn", "教育", "学习", "读书", "上课"]),
            "读书": cls.get_env_or_default_list("SYNONYMS_READ", ["学习", "看书", "阅读", "study", "learn", "教育", "学习", "读书"]),
            "上课": cls.get_env_or_default_list("SYNONYMS_CLASS", ["学习", "读书", "培训", "study", "learn", "教育", "学习", "上课"]),
            "培训": cls.get_env_or_default_list("SYNONYMS_TRAINING", ["学习", "读书", "上课", "study", "learn", "教育", "学习", "培训"]),
            
            # 人际关系
            "朋友": cls.get_env_or_default_list("SYNONYMS_FRIEND", ["好友", "伙伴", "buddy", "friend", "同伴", "朋友", "好友"]),
            "家人": cls.get_env_or_default_list("SYNONYMS_FAMILY", ["亲人", "家庭成员", "family", "亲属", "家人", "亲人"]),
            "同事": cls.get_env_or_default_list("SYNONYMS_COLLEAGUE", ["同事", "同事", "colleague", "工作伙伴", "同事"]),
            "恋人": cls.get_env_or_default_list("SYNONYMS_LOVER", ["男朋友", "女朋友", "恋人", "lover", "对象", "伴侣"]),
            
            # 健康相关
            "健康": cls.get_env_or_default_list("SYNONYMS_HEALTH", ["身体", "体质", "health", "physical", "状况", "健康", "身体"]),
            "身体": cls.get_env_or_default_list("SYNONYMS_BODY", ["健康", "体质", "health", "physical", "状况", "身体", "健康"]),
            "生病": cls.get_env_or_default_list("SYNONYMS_SICK", ["不舒服", "生病", "sick", "ill", "患病", "生病", "身体不好", "身体不适"]),
            "不舒服": cls.get_env_or_default_list("SYNONYMS_UNCOMFORTABLE", ["生病", "不舒服", "sick", "ill", "患病", "不舒服", "身体不好", "身体不适"]),
            "身体不好": cls.get_env_or_default_list("SYNONYMS_UNWELL", ["生病", "不舒服", "sick", "ill", "患病", "身体不好", "身体不适"]),
            "身体不适": cls.get_env_or_default_list("SYNONYMS_UNCOMFORTABLE_ALT", ["生病", "不舒服", "sick", "ill", "患病", "身体不好", "身体不适"]),
            "医院": cls.get_env_or_default_list("SYNONYMS_HOSPITAL", ["医院", "hospital", "看病", "就医", "医院"]),
            "看病": cls.get_env_or_default_list("SYNONYMS_SEE_DOCTOR", ["医院", "hospital", "就医", "看病", "看病"]),
            
            # 性格情感
            "性格": cls.get_env_or_default_list("SYNONYMS_PERSONALITY", ["个性", "脾气", "personality", "character", "性情", "性格", "个性"]),
            "喜欢": cls.get_env_or_default_list("SYNONYMS_LIKE", ["爱好", "热爱", "享受", "沉迷", "擅长", "精通", "喜欢", "爱好"]),
            "讨厌": cls.get_env_or_default_list("SYNONYMS_DISLIKE", ["不喜欢", "讨厌", "dislike", "厌恶", "讨厌", "不喜欢"]),
            "开心": cls.get_env_or_default_list("SYNONYMS_HAPPY", ["高兴", "快乐", "happy", "开心", "高兴", "快乐", "愉快", "愉悦"]),
            "高兴": cls.get_env_or_default_list("SYNONYMS_GLAD", ["开心", "快乐", "happy", "高兴", "开心", "快乐", "愉快", "愉悦"]),
            "快乐": cls.get_env_or_default_list("SYNONYMS_JOY", ["开心", "高兴", "happy", "快乐", "开心", "高兴", "愉快", "愉悦"]),
            "愉快": cls.get_env_or_default_list("SYNONYMS_PLEASANT", ["开心", "高兴", "快乐", "happy", "愉快", "愉悦"]),
            "愉悦": cls.get_env_or_default_list("SYNONYMS_DELIGHTED", ["开心", "高兴", "快乐", "happy", "愉快", "愉悦"]),
            "难过": cls.get_env_or_default_list("SYNONYMS_SAD", ["伤心", "难过", "sad", "悲伤", "难过", "伤心"]),
            "伤心": cls.get_env_or_default_list("SYNONYMS_HEARTBROKEN", ["难过", "伤心", "sad", "悲伤", "伤心", "难过"]),
            
            # 生活习惯
            "习惯": cls.get_env_or_default_list("SYNONYMS_HABIT", ["习性", "惯例", "habit", "routine", "规律", "习惯", "习性"]),
            "经常": cls.get_env_or_default_list("SYNONYMS_OFTEN", ["总是", "习惯", "每天", "定期", "频繁", "经常", "总是"]),
            "每天": cls.get_env_or_default_list("SYNONYMS_DAILY", ["经常", "总是", "习惯", "定期", "频繁", "每天", "经常"]),
            "睡觉": cls.get_env_or_default_list("SYNONYMS_SLEEP", ["睡觉", "sleep", "休息", "睡觉", "休息"]),
            "吃饭": cls.get_env_or_default_list("SYNONYMS_EAT", ["吃饭", "eat", "用餐", "吃饭", "用餐"]),
            
            # 感觉认知
            "感觉": cls.get_env_or_default_list("SYNONYMS_FEEL", ["觉得", "认为", "感受", "体验", "察觉", "感觉", "觉得"]),
            "觉得": cls.get_env_or_default_list("SYNONYMS_THINK", ["感觉", "认为", "感受", "体验", "察觉", "觉得", "感觉"]),
            "认为": cls.get_env_or_default_list("SYNONYMS_BELIEVE", ["觉得", "感觉", "感受", "体验", "察觉", "认为", "觉得"]),
            
            # 关系连接
            "关系": cls.get_env_or_default_list("SYNONYMS_RELATION", ["联系", "关联", "连接", "纽带", "桥梁", "关系", "联系"]),
            "联系": cls.get_env_or_default_list("SYNONYMS_CONTACT", ["关系", "关联", "连接", "纽带", "桥梁", "联系", "关系"]),
            
            # 年龄相关（保持原有优化）
            "年龄": cls.get_env_or_default_list("SYNONYMS_AGE", ["多大了", "岁", "多大", "几岁", "年纪", "年岁", "你多大了", "几岁了"]),
            "多大": cls.get_env_or_default_list("SYNONYMS_SIZE", ["年龄", "岁", "几岁", "年纪", "年岁", "多大了", "你多大了"]),
            "几岁": cls.get_env_or_default_list("SYNONYMS_HOW_OLD", ["年龄", "岁", "多大", "年纪", "年岁", "多大了", "你多大了", "你几岁了"]),
            "多大了": cls.get_env_or_default_list("SYNONYMS_HOW_OLD_QUESTION", ["年龄", "岁", "多大", "几岁", "年纪", "年岁", "你几岁", "几岁了", "你多大了"]),
            "你多大了": cls.get_env_or_default_list("SYNONYMS_AGE_QUESTION", ["年龄", "岁", "多大", "几岁", "年纪", "年岁", "几岁了", "你几岁了"]),
            "你几岁了": cls.get_env_or_default_list("SYNONYMS_AGE_QUESTION_ALT", ["年龄", "岁", "多大", "几岁", "年纪", "年岁", "多大了", "你多大了"]),
            
            # 姓名相关
            "姓名": cls.get_env_or_default_list("SYNONYMS_NAME", ["名字", "姓名", "name", "叫什么", "叫什么名字", "姓名"]),
            "名字": cls.get_env_or_default_list("SYNONYMS_NAME_ALT", ["姓名", "名字", "name", "叫什么", "叫什么名字", "名字"]),
            "叫什么": cls.get_env_or_default_list("SYNONYMS_WHAT_NAME", ["姓名", "名字", "name", "叫什么名字", "姓名", "名字"]),
            "叫什么名字": cls.get_env_or_default_list("SYNONYMS_WHAT_NAME_FULL", ["姓名", "名字", "name", "叫什么", "姓名", "名字"]),
            "你是谁": cls.get_env_or_default_list("SYNONYMS_WHO_ARE_YOU", ["你是谁", "你是谁？", "你叫什么", "你叫什么名字", "你的名字", "你的姓名", "身份", "角色", "自称", "助手", "AI", "机器人"]),
            "你是谁？": cls.get_env_or_default_list("SYNONYMS_WHO_ARE_YOU_Q", ["你是谁", "你是谁？", "你叫什么", "你叫什么名字", "你的名字", "你的姓名", "身份", "角色", "自称", "助手", "AI", "机器人"]),
            
            # 时间相关
            "时间": cls.get_env_or_default_list("SYNONYMS_TIME", ["时候", "时间", "time", "什么时候", "时间", "时候"]),
            "什么时候": cls.get_env_or_default_list("SYNONYMS_WHEN", ["时间", "时候", "time", "什么时候", "时间", "时候"]),
            "今天": cls.get_env_or_default_list("SYNONYMS_TODAY", ["今天", "today", "今日", "今天", "今日"]),
            "明天": cls.get_env_or_default_list("SYNONYMS_TOMORROW", ["明天", "tomorrow", "明日", "明天", "明日"]),
            "昨天": cls.get_env_or_default_list("SYNONYMS_YESTERDAY", ["昨天", "yesterday", "昨日", "昨天", "昨日"])
        }
    
    @classmethod
    def get_semantic_patterns(cls) -> List[tuple]:
        """获取语义相关性模式"""
        return [
            ("电影", cls.get_env_or_default_list("SEMANTIC_MOVIE", ["科幻", "动作", "喜剧", "恐怖", "爱情", "剧情", "悬疑", "动画", "纪录片", "战争"])),
            ("音乐", cls.get_env_or_default_list("SEMANTIC_MUSIC", ["流行", "摇滚", "古典", "爵士", "民谣", "电子", "说唱", "蓝调", "乡村", "朋克"])),
            ("工作", cls.get_env_or_default_list("SEMANTIC_WORK", ["编程", "设计", "销售", "管理", "客服", "分析", "运营", "市场", "财务", "人事"])),
            ("学习", cls.get_env_or_default_list("SEMANTIC_STUDY", ["编程", "语言", "数学", "历史", "科学", "艺术", "哲学", "心理学", "经济学", "文学"])),
            ("运动", cls.get_env_or_default_list("SEMANTIC_SPORT", ["跑步", "游泳", "健身", "篮球", "足球", "瑜伽", "网球", "高尔夫", "滑雪", "骑行"])),
            ("性格", cls.get_env_or_default_list("SEMANTIC_PERSONALITY", ["内向", "外向", "乐观", "悲观", "冷静", "热情", "谨慎", "冒险", "理性", "感性"])),
            ("食物", cls.get_env_or_default_list("SEMANTIC_FOOD", ["中餐", "西餐", "日料", "韩料", "火锅", "烧烤", "甜点", "饮料", "水果", "零食"])),
            ("旅行", cls.get_env_or_default_list("SEMANTIC_TRAVEL", ["国内", "国外", "海边", "山区", "城市", "乡村", "古镇", "海岛", "沙漠", "森林"]))
        ]
    
    # ==================== 搜索策略配置 ====================
    
    @classmethod
    def get_search_thresholds(cls) -> Dict[str, float]:
        """获取搜索阈值配置（优化后降低阈值提高匹配敏感度）"""
        return {
            "keyword_similarity": float(cls.get_env_or_default("SEARCH_THRESHOLD_KEYWORD", "0.01")),
            "topic_relevance": float(cls.get_env_or_default("SEARCH_THRESHOLD_TOPIC", "0.1")),
            "content_overlap": float(cls.get_env_or_default("SEARCH_THRESHOLD_CONTENT", "0.05")),
            "semantic_similarity": float(cls.get_env_or_default("SEARCH_THRESHOLD_SEMANTIC", "0.15"))
        }
    
    @classmethod
    def get_search_weights(cls) -> Dict[str, float]:
        """获取搜索权重配置"""
        return {
            "topic_match": float(cls.get_env_or_default("SEARCH_WEIGHT_TOPIC", "0.4")),
            "keyword_overlap": float(cls.get_env_or_default("SEARCH_WEIGHT_KEYWORD", "0.3")),
            "content_match": float(cls.get_env_or_default("SEARCH_WEIGHT_CONTENT", "0.2")),
            "time_freshness_7d": float(cls.get_env_or_default("SEARCH_WEIGHT_TIME_7D", "0.1"))
        }
    
    @classmethod
    def get_search_strategies(cls) -> Dict[str, any]:
        """获取搜索策略配置（优化后默认关闭LLM和关键词匹配）"""
        return {
            # Redis事实搜索策略 - 默认关闭LLM和关键词匹配，直接返回全部事实
            "enable_llm_semantic_search": cls.get_env_or_default_bool("SEARCH_ENABLE_LLM_SEMANTIC", False),
            "enable_topic_search": cls.get_env_or_default_bool("SEARCH_ENABLE_TOPIC", False),
            "enable_keyword_search": cls.get_env_or_default_bool("SEARCH_ENABLE_KEYWORD", False),
            "enable_semantic_search": cls.get_env_or_default_bool("SEARCH_ENABLE_SEMANTIC", False),
            "enable_time_ranking": cls.get_env_or_default_bool("SEARCH_ENABLE_TIME_RANKING", False),
            "enable_fuzzy_match": cls.get_env_or_default_bool("SEARCH_ENABLE_FUZZY", False),
            
            # 搜索结果配置
            "max_search_results": cls.get_env_or_default_int("SEARCH_MAX_RESULTS", 50),
            "redis_return_all_facts": cls.get_env_or_default_bool("SEARCH_REDIS_RETURN_ALL_FACTS", False),
            "fact_count_threshold": cls.get_env_or_default_int("SEARCH_FACT_COUNT_THRESHOLD", 50),  # 事实数量阈值
            "recent_chats_limit": cls.get_env_or_default_int("SEARCH_RECENT_CHATS_LIMIT", 20),  # 最近对话轮数
            
            # LLM搜索配置（当启用时使用）
            "llm_search_timeout": cls.get_env_or_default_int("SEARCH_LLM_TIMEOUT", 30),
            "llm_search_temperature": cls.get_env_or_default_float("SEARCH_LLM_TEMPERATURE", 0.1),
            # ES搜索超时配置
            "es_search_timeout": cls.get_env_or_default_int("ES_SEARCH_TIMEOUT", 5)
        }
    
    @classmethod
    def get_quality_check_config(cls) -> Dict[str, any]:
        """获取答案质量检测配置"""
        return {
            "enabled": cls.get_env_or_default_bool("QUALITY_CHECK_ENABLED", True),  # 是否启用质量检测
            "min_answer_length": cls.get_env_or_default_int("QUALITY_CHECK_MIN_LENGTH", 10),  # 最小答案长度
            "max_repetition_ratio": cls.get_env_or_default_float("QUALITY_CHECK_MAX_REPETITION", 0.3),  # 最大重复比例
            "max_interjection_ratio": cls.get_env_or_default_float("QUALITY_CHECK_MAX_INTERJECTION", 0.7),  # 最大语气助词比例
            "min_relevance_score": cls.get_env_or_default_float("QUALITY_CHECK_MIN_RELEVANCE", 0.3),  # 最小相关性分数
            "min_llm_score": cls.get_env_or_default_float("QUALITY_CHECK_MIN_LLM_SCORE", 0.3),  # 最小LLM评分
        }
    
    # ==================== 事实管理策略配置 ====================
    
    @classmethod
    def get_fact_update_strategy(cls) -> Dict[str, any]:
        """获取事实更新策略（优化后默认禁用LLM判断以提高性能）"""
        return {
            "enable_llm_judgment": cls.get_env_or_default_bool("FACT_ENABLE_LLM_JUDGMENT", True),
            "default_similarity_threshold": float(cls.get_env_or_default("FACT_SIMILARITY_THRESHOLD", "0.1")),
            "enable_auto_merge": cls.get_env_or_default_bool("FACT_ENABLE_AUTO_MERGE", True),
            "merge_separator": cls.get_env_or_default("FACT_MERGE_SEPARATOR", "；"),
            "timestamp_format": cls.get_env_or_default("FACT_TIMESTAMP_FORMAT", "[提及于{timestamp}]")
        }
    
    @classmethod
    def get_fact_storage_strategy(cls) -> Dict[str, any]:
        """获取事实存储策略"""
        return {
            "enable_duplicate_check": cls.get_env_or_default_bool("FACT_ENABLE_DUPLICATE_CHECK", True),
            "max_fact_length": cls.get_env_or_default_int("FACT_MAX_LENGTH", 1000),
            "enable_compression": cls.get_env_or_default_bool("FACT_ENABLE_COMPRESSION", False),
            "backup_enabled": cls.get_env_or_default_bool("FACT_BACKUP_ENABLED", True)
        }
    
    # ==================== 系统配置 ====================
    
    @classmethod
    def get_es_chat_index(cls) -> str:
        return cls.get_env_or_default("ES_CHAT_INDEX", "aigc_user_dialogs")
    
    @classmethod
    def get_similarity_threshold(cls) -> float:
        return float(cls.get_env_or_default("SIMILARITY_THRESHOLD", "0.6"))
    
    @classmethod
    def get_max_search_results(cls) -> int:
        return cls.get_env_or_default_int("MAX_SEARCH_RESULTS", 10)
    
    # ==================== 应用配置 ====================
    
    @classmethod
    def get_app_port(cls) -> int:
        return cls.get_env_or_default_int("APP_PORT", 8000)
    
    @classmethod
    def get_app_host(cls) -> str:
        return cls.get_env_or_default("APP_HOST", "0.0.0.0")
    
    @classmethod
    def get_app_env(cls) -> str:
        return cls.get_env_or_default("APP_ENV", "production")
    
    @classmethod
    def get_debug(cls) -> bool:
        return cls.get_env_or_default_bool("DEBUG", False)
    
    # ==================== 日志配置 ====================
    
    @classmethod
    def get_log_level(cls) -> str:
        return cls.get_env_or_default("LOG_LEVEL", "INFO")
    
    @classmethod
    def get_log_format(cls) -> str:
        return cls.get_env_or_default("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    @classmethod
    def get_log_file(cls) -> str:
        return cls.get_env_or_default("LOG_FILE", "logs/app.log")
    
    # ==================== 性能配置 ====================
    
    @classmethod
    def get_request_timeout(cls) -> int:
        return cls.get_env_or_default_int("REQUEST_TIMEOUT", 30)
    
    @classmethod
    def get_max_retry_attempts(cls) -> int:
        return cls.get_env_or_default_int("MAX_RETRY_ATTEMPTS", 3)
    
    @classmethod
    def get_retry_delay(cls) -> int:
        return cls.get_env_or_default_int("RETRY_DELAY", 1)
    
    # ==================== 文本处理配置 ====================
    
    @classmethod
    def get_punctuation_pattern(cls) -> str:
        """获取标点符号正则表达式模式"""
        return cls.get_env_or_default("PUNCTUATION_PATTERN", r'[？?！!。，,、；;：:""''（）()【】\\[\\]《》<>]')
    
    @classmethod
    def get_text_cleaning_enabled(cls) -> bool:
        """是否启用文本清理（移除标点符号）"""
        return cls.get_env_or_default_bool("TEXT_CLEANING_ENABLED", True)
    
    @classmethod
    def clean_text(cls, text: str) -> str:
        """清理文本，移除标点符号"""
        if not cls.get_text_cleaning_enabled():
            return text
        
        import re
        pattern = cls.get_punctuation_pattern()
        return re.sub(pattern, '', text)
    
    # ==================== 工具方法 ====================
    
    @classmethod
    def get_topic_keywords_for_topic(cls, topic: str) -> List[str]:
        """获取指定主题的关键词列表"""
        return cls.get_topic_keywords().get(topic, [])
    
    @classmethod
    def get_all_topics(cls) -> List[str]:
        """获取所有主题列表"""
        return list(cls.get_predefined_topics().keys())
    
    @classmethod
    def get_sub_topics(cls, topic: str) -> List[str]:
        """获取指定主题的子主题列表"""
        return cls.get_predefined_topics().get(topic, [])
    
    @classmethod
    def get_synonyms(cls, word: str) -> List[str]:
        """获取指定词的同义词列表"""
        return cls.get_synonyms_mapping().get(word, [])
    
    @classmethod
    def get_search_threshold(cls, threshold_type: str) -> float:
        """获取指定类型的搜索阈值"""
        return cls.get_search_thresholds().get(threshold_type, 0.5)
    
    @classmethod
    def get_search_weight(cls, weight_type: str) -> float:
        """获取指定类型的搜索权重"""
        return cls.get_search_weights().get(weight_type, 0.5)
    
    @classmethod
    def get_search_strategy(cls, strategy_type: str) -> bool:
        """获取指定类型的搜索策略"""
        return cls.get_search_strategies().get(strategy_type, True)
    
    @classmethod
    def get_fact_update_setting(cls, setting_type: str) -> any:
        """获取指定类型的事实更新设置"""
        return cls.get_fact_update_strategy().get(setting_type, None)
    
    @classmethod
    def get_fact_storage_setting(cls, setting_type: str) -> any:
        """获取指定类型的事实存储设置"""
        return cls.get_fact_storage_strategy().get(setting_type, None)
    
    @classmethod
    def print_config_summary(cls):
        """打印配置摘要"""
        print("=== yaxin_memo 配置摘要 ===")
        print(f"ES主机: {cls.get_es_host()}")
        print(f"Redis主机: {cls.get_redis_host()}:{cls.get_redis_port()}")
        print(f"LLM模型: {cls.get_llm_model()}")
        print(f"Embedding模型: {cls.get_embedding_model()}")
        print(f"应用端口: {cls.get_app_port()}")
        print(f"调试模式: {cls.get_debug()}")
        print(f"日志级别: {cls.get_log_level()}")
        print("==========================")
