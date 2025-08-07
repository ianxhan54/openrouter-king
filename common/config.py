import os
from typing import List, Dict, Optional

from dotenv import load_dotenv

from common.Logger import logger

# 只在环境变量不存在时才从.env加载值
load_dotenv(override=False)


class Config:
    GITHUB_TOKENS_STR = os.getenv("GITHUB_TOKENS", "")

    # 获取GitHub tokens列表
    GITHUB_TOKENS = [token.strip() for token in GITHUB_TOKENS_STR.split(',') if token.strip()]
    DATA_PATH = os.getenv('DATA_PATH', 'data')
    PROXY = os.getenv("PROXY", "")
    # 文件前缀配置
    VALID_KEY_DETAIL_PREFIX = os.getenv("VALID_KEY_DETAIL_PREFIX", "keys_valid_detail_")
    VALID_KEY_PREFIX = os.getenv("VALID_KEY_PREFIX", "keys_valid_")
    RATE_LIMITED_KEY_PREFIX = os.getenv("RATE_LIMITED_KEY_PREFIX", "gemini_key_429_")
    RATE_LIMITED_KEY_DETAIL_PREFIX = os.getenv("RATE_LIMITED_KEY_DETAIL_PREFIX", "gemini_key_429_detail_")
    # 日期范围过滤器配置 (单位：天)
    DATE_RANGE_DAYS = int(os.getenv("DATE_RANGE_DAYS", "730"))  # 默认730天 (约2年)

    # 查询文件路径配置
    QUERIES_FILE = os.getenv("QUERIES_FILE", "queries.txt")

    # 已扫描SHA文件配置
    SCANNED_SHAS_FILE = os.getenv("SCANNED_SHAS_FILE", "scanned_shas.txt")

    # Gemini模型配置
    HAJIMI_CHECK_MODEL = os.getenv("HAJIMI_CHECK_MODEL", "gemini-2.5-flash")

    # OpenRouter配置
    OPENROUTER_VALIDATION_ENDPOINT = os.getenv("OPENROUTER_VALIDATION_ENDPOINT", "https://openrouter.ai/api/v1/key")
    OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "10"))
    
    # API密钥类型配置
    API_KEY_TYPE = os.getenv("API_KEY_TYPE", "openrouter")  # gemini, openrouter, both
    
    # 扫描模式配置
    SCAN_MODE = os.getenv("SCAN_MODE", "incremental")  # incremental, full, smart
    FULL_SCAN_INTERVAL_HOURS = int(os.getenv("FULL_SCAN_INTERVAL_HOURS", "24"))
    FORCE_FULL_SCAN = os.getenv("FORCE_FULL_SCAN", "false").lower() == "true"

    # 文件路径黑名单配置
    FILE_PATH_BLACKLIST_STR = os.getenv("FILE_PATH_BLACKLIST", "readme,docs,doc/,.md,example,sample,tutorial")
    FILE_PATH_BLACKLIST = [token.strip().lower() for token in FILE_PATH_BLACKLIST_STR.split(',') if token.strip()]

    @classmethod
    def get_requests_proxies(cls) -> Optional[Dict[str, str]]:
        """
        获取requests包格式的proxy配置
        
        Returns:
            Optional[Dict[str, str]]: requests格式的proxies字典，如果未配置则返回None
        """
        if not cls.PROXY:
            return None
        
        # 支持多种格式的proxy配置
        proxy_url = cls.PROXY.strip()
        
        # 返回requests格式的proxies字典
        return {
            'http': proxy_url,
            'https': proxy_url
        }

    @classmethod
    def check(cls) -> bool:
        """
        检查必要的配置是否完整
        
        Returns:
            bool: 配置是否完整
        """
        logger.info("🔍 Checking required configurations...")
        
        errors = []
        
        # 检查GitHub tokens
        if not cls.GITHUB_TOKENS:
            errors.append("GitHub tokens not found. Please set GITHUB_TOKENS environment variable.")
            logger.error("❌ GitHub tokens: Missing")
        else:
            logger.info(f"✅ GitHub tokens: {len(cls.GITHUB_TOKENS)} configured")
        

        
        # 检查数据路径
        if not cls.DATA_PATH:
            errors.append("Data path not configured. Please set DATA_PATH.")
            logger.error("❌ Data path: Missing")
        else:
            logger.info(f"✅ Data path: {cls.DATA_PATH}")
        
        # 检查文件前缀配置
        required_prefixes = [
            (cls.VALID_KEY_DETAIL_PREFIX, "VALID_KEY_DETAIL_PREFIX"),
            (cls.VALID_KEY_PREFIX, "VALID_KEY_LOG_PREFIX"),
            (cls.RATE_LIMITED_KEY_PREFIX, "RATE_LIMITED_KEY_PREFIX"),
            (cls.RATE_LIMITED_KEY_DETAIL_PREFIX, "RATE_LIMITED_KEY_DETAIL_PREFIX")
        ]
        
        for prefix, name in required_prefixes:
            if not prefix:
                errors.append(f"{name} not configured.")
                logger.error(f"❌ {name}: Missing")
            else:
                logger.info(f"✅ {name}: {prefix}")
        
        # 检查Hajimi检验模型配置
        if not cls.HAJIMI_CHECK_MODEL:
            errors.append("HAJIMI_CHECK_MODEL not configured.")
            logger.error("❌ Hajimi check model: Missing")
        else:
            logger.info(f"✅ Hajimi check model: {cls.HAJIMI_CHECK_MODEL}")
        
        # 检查API密钥类型配置
        if cls.API_KEY_TYPE not in ["gemini", "openrouter", "both"]:
            errors.append(f"Invalid API_KEY_TYPE: {cls.API_KEY_TYPE}. Must be 'gemini', 'openrouter', or 'both'.")
            logger.error(f"❌ API key type: Invalid ({cls.API_KEY_TYPE})")
        else:
            logger.info(f"✅ API key type: {cls.API_KEY_TYPE}")
        
        # 检查扫描模式配置
        if cls.SCAN_MODE not in ["incremental", "full", "smart"]:
            errors.append(f"Invalid SCAN_MODE: {cls.SCAN_MODE}. Must be 'incremental', 'full', or 'smart'.")
            logger.error(f"❌ Scan mode: Invalid ({cls.SCAN_MODE})")
        else:
            logger.info(f"✅ Scan mode: {cls.SCAN_MODE}")
        
        # 检查OpenRouter配置
        if cls.API_KEY_TYPE in ["openrouter", "both"]:
            if not cls.OPENROUTER_VALIDATION_ENDPOINT:
                errors.append("OPENROUTER_VALIDATION_ENDPOINT not configured.")
                logger.error("❌ OpenRouter endpoint: Missing")
            else:
                logger.info(f"✅ OpenRouter endpoint: {cls.OPENROUTER_VALIDATION_ENDPOINT}")
            
            logger.info(f"✅ OpenRouter timeout: {cls.OPENROUTER_TIMEOUT}s")
        
        if errors:
            logger.error("❌ Configuration check failed:")
            for error in errors:
                logger.error(f"   - {error}")
            logger.info("Please check your .env file and configuration.")
            return False
        
        logger.info("✅ All required configurations are valid")
        return True


logger.info(f"*" * 30 + " CONFIG START" + "*" * 30)
logger.info(f"GITHUB_TOKENS: Found {len(Config.GITHUB_TOKENS)} tokens")
logger.info(f"API key type: {Config.API_KEY_TYPE}")
logger.info(f"Scan mode: {Config.SCAN_MODE}")
logger.info(f"Valid key detail prefix: {Config.VALID_KEY_DETAIL_PREFIX}")
logger.info(f"Valid key log prefix: {Config.VALID_KEY_PREFIX}")
logger.info(f"Rate limited key prefix: {Config.RATE_LIMITED_KEY_PREFIX}")
logger.info(f"Date range filter: {Config.DATE_RANGE_DAYS} days")
logger.info(f"Queries file: {Config.QUERIES_FILE}")
logger.info(f"Scanned SHAs file: {Config.SCANNED_SHAS_FILE}")
logger.info(f"File path blacklist: {len(Config.FILE_PATH_BLACKLIST)} items")
if Config.API_KEY_TYPE in ["openrouter", "both"]:
    logger.info(f"OpenRouter endpoint: {Config.OPENROUTER_VALIDATION_ENDPOINT}")
    logger.info(f"OpenRouter timeout: {Config.OPENROUTER_TIMEOUT}s")
logger.info(f"*" * 30 + " CONFIG END" + "*" * 30)

# 创建全局配置实例
config = Config()
