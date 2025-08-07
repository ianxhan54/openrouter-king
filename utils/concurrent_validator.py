import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Union, Optional
from dataclasses import dataclass

from common.Logger import logger
from common.config import Config
from utils.openrouter_validator import openrouter_validator

try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


@dataclass
class ValidationResult:
    """密钥验证结果"""
    key: str
    key_type: str
    is_valid: bool
    rate_limited: bool = False
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ConcurrentValidator:
    """并发密钥验证器"""
    
    def __init__(self, max_workers: int = 5, delay_range: tuple = (0.5, 2.0)):
        """
        初始化并发验证器
        
        Args:
            max_workers: 最大并发工作线程数
            delay_range: 验证延迟范围（秒）
        """
        self.max_workers = max_workers
        self.delay_range = delay_range
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    def validate_gemini_key(self, api_key: str) -> ValidationResult:
        """验证Gemini密钥"""
        if not GEMINI_AVAILABLE:
            return ValidationResult(
                key=api_key,
                key_type="gemini",
                is_valid=False,
                error="Gemini library not installed"
            )
        
        try:
            time.sleep(random.uniform(*self.delay_range))
            
            genai.configure(
                api_key=api_key,
                transport="rest",
                client_options={"api_endpoint": "generativelanguage.googleapis.com"},
            )
            
            model = genai.GenerativeModel(Config.HAJIMI_CHECK_MODEL)
            response = model.generate_content("hi")
            
            return ValidationResult(
                key=api_key,
                key_type="gemini",
                is_valid=True
            )
            
        except (google_exceptions.PermissionDenied, google_exceptions.Unauthenticated):
            return ValidationResult(
                key=api_key,
                key_type="gemini",
                is_valid=False,
                error="Invalid key"
            )
            
        except google_exceptions.TooManyRequests:
            return ValidationResult(
                key=api_key,
                key_type="gemini",
                is_valid=False,
                rate_limited=True,
                error="Rate limited"
            )
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate limit" in error_str.lower():
                return ValidationResult(
                    key=api_key,
                    key_type="gemini",
                    is_valid=False,
                    rate_limited=True,
                    error="Rate limited"
                )
            elif "403" in error_str or "SERVICE_DISABLED" in error_str:
                return ValidationResult(
                    key=api_key,
                    key_type="gemini",
                    is_valid=False,
                    error="Service disabled"
                )
            else:
                return ValidationResult(
                    key=api_key,
                    key_type="gemini",
                    is_valid=False,
                    error=f"Unknown error: {e}"
                )
    
    def validate_openrouter_key(self, api_key: str) -> ValidationResult:
        """验证OpenRouter密钥"""
        result = openrouter_validator.validate_key(api_key)
        
        if isinstance(result, dict) and result.get("valid"):
            return ValidationResult(
                key=api_key,
                key_type="openrouter",
                is_valid=True,
                details=result
            )
        elif result == "rate_limited":
            return ValidationResult(
                key=api_key,
                key_type="openrouter",
                is_valid=False,
                rate_limited=True,
                error="Rate limited"
            )
        elif result is False:
            return ValidationResult(
                key=api_key,
                key_type="openrouter",
                is_valid=False,
                error="Invalid key"
            )
        else:
            return ValidationResult(
                key=api_key,
                key_type="openrouter",
                is_valid=False,
                error="Validation error"
            )
    
    def validate_key(self, api_key: str, key_type: str = "auto") -> ValidationResult:
        """
        验证单个密钥
        
        Args:
            api_key: API密钥
            key_type: 密钥类型（auto, gemini, openrouter）
        
        Returns:
            ValidationResult: 验证结果
        """
        if key_type == "auto":
            if api_key.startswith("AIzaSy"):
                key_type = "gemini"
            elif api_key.startswith("sk-or-"):
                key_type = "openrouter"
            else:
                return ValidationResult(
                    key=api_key,
                    key_type="unknown",
                    is_valid=False,
                    error="Unknown key type"
                )
        
        if key_type == "gemini":
            return self.validate_gemini_key(api_key)
        elif key_type == "openrouter":
            return self.validate_openrouter_key(api_key)
        else:
            return ValidationResult(
                key=api_key,
                key_type=key_type,
                is_valid=False,
                error=f"Unsupported key type: {key_type}"
            )
    
    def validate_batch(self, keys_by_type: Dict[str, List[str]]) -> Dict[str, List[ValidationResult]]:
        """
        批量并发验证密钥
        
        Args:
            keys_by_type: 按类型分组的密钥字典
        
        Returns:
            Dict[str, List[ValidationResult]]: 按类型分组的验证结果
        """
        all_tasks = []
        results_by_type = {key_type: [] for key_type in keys_by_type}
        
        # 提交所有验证任务
        for key_type, keys in keys_by_type.items():
            for key in keys:
                future = self.executor.submit(self.validate_key, key, key_type)
                all_tasks.append((future, key_type))
        
        # 收集结果
        completed = 0
        total = len(all_tasks)
        
        for future, key_type in all_tasks:
            try:
                result = future.result(timeout=30)
                results_by_type[key_type].append(result)
                completed += 1
                
                # 进度日志
                if completed % 10 == 0 or completed == total:
                    logger.info(f"🔄 Validation progress: {completed}/{total}")
                    
            except Exception as e:
                logger.error(f"❌ Validation failed: {e}")
                # 创建失败结果
                results_by_type[key_type].append(
                    ValidationResult(
                        key="unknown",
                        key_type=key_type,
                        is_valid=False,
                        error=str(e)
                    )
                )
        
        return results_by_type
    
    def shutdown(self):
        """关闭执行器"""
        self.executor.shutdown(wait=True)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


# 创建全局实例
concurrent_validator = ConcurrentValidator(max_workers=5)