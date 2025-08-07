import re
from typing import Any, Optional
import hashlib

from common.Logger import logger as base_logger


class SecureLogger:
    """安全日志记录器，自动脱敏处理敏感信息"""
    
    # 敏感信息模式
    PATTERNS = {
        'github_token': r'(ghp_[A-Za-z0-9]{36})',
        'gemini_key': r'(AIzaSy[A-Za-z0-9\-_]{33})',
        'openrouter_key': r'(sk-or-[A-Za-z0-9\-_]{20,50})',
        'generic_api_key': r'([a-zA-Z0-9]{32,})',
        'email': r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        'ip_address': r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
        'url_with_creds': r'(https?://[^:]+:[^@]+@[^\s]+)'
    }
    
    def __init__(self, mask_char: str = "*", show_prefix_length: int = 6):
        """
        初始化安全日志记录器
        
        Args:
            mask_char: 掩码字符
            show_prefix_length: 显示的前缀长度
        """
        self.mask_char = mask_char
        self.show_prefix_length = show_prefix_length
        self.sensitive_hashes = {}  # 存储敏感信息的哈希值
    
    def mask_sensitive_data(self, text: str) -> str:
        """
        掩码敏感数据
        
        Args:
            text: 要处理的文本
        
        Returns:
            str: 脱敏后的文本
        """
        if not isinstance(text, str):
            text = str(text)
        
        masked_text = text
        
        for pattern_name, pattern in self.PATTERNS.items():
            matches = re.finditer(pattern, masked_text)
            
            for match in matches:
                sensitive_data = match.group(1)
                
                # 记录敏感数据的哈希（用于审计）
                data_hash = hashlib.sha256(sensitive_data.encode()).hexdigest()[:8]
                self.sensitive_hashes[data_hash] = pattern_name
                
                # 创建掩码
                if len(sensitive_data) > self.show_prefix_length:
                    masked = (
                        sensitive_data[:self.show_prefix_length] +
                        self.mask_char * (len(sensitive_data) - self.show_prefix_length - 3) +
                        sensitive_data[-3:]
                    )
                else:
                    masked = self.mask_char * len(sensitive_data)
                
                masked_text = masked_text.replace(sensitive_data, masked)
        
        return masked_text
    
    def format_key_for_log(self, key: str, key_type: str = "api") -> str:
        """
        格式化密钥用于日志记录
        
        Args:
            key: 密钥
            key_type: 密钥类型
        
        Returns:
            str: 格式化后的密钥
        """
        if not key:
            return "N/A"
        
        # 生成密钥指纹
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:8]
        
        # 显示部分密钥信息
        if len(key) > 10:
            masked_key = f"{key[:6]}...{key[-4:]}"
        else:
            masked_key = "*" * len(key)
        
        return f"{key_type}[{masked_key}|{key_hash}]"
    
    def info(self, message: str, *args, **kwargs):
        """安全的info日志"""
        safe_message = self.mask_sensitive_data(message)
        base_logger.info(safe_message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        """安全的debug日志"""
        safe_message = self.mask_sensitive_data(message)
        base_logger.debug(safe_message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """安全的warning日志"""
        safe_message = self.mask_sensitive_data(message)
        base_logger.warning(safe_message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """安全的error日志"""
        safe_message = self.mask_sensitive_data(message)
        base_logger.error(safe_message, *args, **kwargs)
    
    def log_key_found(self, key_type: str, key: str, source: str):
        """
        记录发现的密钥（安全方式）
        
        Args:
            key_type: 密钥类型
            key: 密钥值
            source: 来源
        """
        formatted_key = self.format_key_for_log(key, key_type)
        self.info(f"🔑 Found {key_type} key: {formatted_key} from {source}")
    
    def log_key_validation(self, key_type: str, key: str, is_valid: bool, details: Optional[dict] = None):
        """
        记录密钥验证结果（安全方式）
        
        Args:
            key_type: 密钥类型
            key: 密钥值
            is_valid: 是否有效
            details: 额外详情
        """
        formatted_key = self.format_key_for_log(key, key_type)
        status = "✅ VALID" if is_valid else "❌ INVALID"
        
        message = f"{status} {key_type}: {formatted_key}"
        if details:
            # 过滤敏感详情
            safe_details = {k: v for k, v in details.items() if k not in ['key', 'secret', 'token']}
            message += f" | Details: {safe_details}"
        
        self.info(message)
    
    def get_audit_summary(self) -> dict:
        """
        获取审计摘要
        
        Returns:
            dict: 包含脱敏操作的摘要信息
        """
        return {
            "masked_count": len(self.sensitive_hashes),
            "pattern_types": list(set(self.sensitive_hashes.values())),
            "hash_prefixes": list(self.sensitive_hashes.keys())
        }


# 创建全局安全日志实例
secure_logger = SecureLogger()