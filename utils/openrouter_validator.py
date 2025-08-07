import random
import time
from typing import Union, Dict, Any
import requests

from common.Logger import logger
from common.config import Config


class OpenRouterValidator:
    """OpenRouter API密钥验证器"""
    
    VALIDATION_ENDPOINT = "https://openrouter.ai/api/v1/key"
    
    def __init__(self, timeout: int = 10):
        """
        初始化OpenRouter验证器
        
        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
    
    def validate_key(self, api_key: str) -> Union[bool, str]:
        """
        验证OpenRouter API密钥
        
        Args:
            api_key: 要验证的API密钥
            
        Returns:
            Union[bool, str]: 验证结果
            - True: 密钥有效
            - False: 密钥无效  
            - "rate_limited": 达到速率限制
            - "error": 其他错误
        """
        try:
            # 添加随机延迟避免过快请求
            time.sleep(random.uniform(0.5, 1.5))
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # 获取代理配置
            proxies = Config.get_requests_proxies()
            
            # 发送验证请求
            if proxies:
                response = requests.get(
                    self.VALIDATION_ENDPOINT, 
                    headers=headers, 
                    timeout=self.timeout,
                    proxies=proxies
                )
            else:
                response = requests.get(
                    self.VALIDATION_ENDPOINT, 
                    headers=headers, 
                    timeout=self.timeout
                )
            
            # 处理响应状态码
            if response.status_code == 200:
                # 验证成功，检查响应数据
                try:
                    data = response.json()
                    if "data" in data:
                        key_info = data['data']
                        usage = key_info.get('usage', 0)
                        limit = key_info.get('limit', 'unlimited')
                        is_free_tier = key_info.get('is_free_tier', False)
                        
                        logger.info(f"✅ OpenRouter密钥验证成功")
                        logger.info(f"   💰 使用量: {usage}")
                        logger.info(f"   📊 限额: {limit}")
                        logger.info(f"   🆓 免费层: {'是' if is_free_tier else '否'}")
                        
                        return {
                            "valid": True,
                            "usage": usage,
                            "limit": limit,
                            "is_free_tier": is_free_tier,
                            "remaining": limit - usage if isinstance(limit, (int, float)) and limit > 0 else "unlimited"
                        }
                    else:
                        logger.warning(f"⚠️ OpenRouter API返回异常格式: {data}")
                        return "error"
                except Exception as e:
                    logger.warning(f"⚠️ 解析OpenRouter API响应失败: {e}")
                    return "error"
                    
            elif response.status_code == 401:
                # 无效密钥
                return False
                
            elif response.status_code == 402:
                # 余额不足，但密钥本身是有效的
                logger.info("💰 OpenRouter密钥有效但余额不足")
                return {
                    "valid": True,
                    "usage": "unknown",
                    "limit": "unknown", 
                    "is_free_tier": False,
                    "remaining": 0,
                    "status": "insufficient_balance"
                }
                
            elif response.status_code == 429:
                # 速率限制
                return "rate_limited"
                
            else:
                # 其他错误
                logger.warning(f"⚠️ OpenRouter API返回未知状态码: {response.status_code}")
                return "error"
                
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ OpenRouter API请求超时")
            return "error"
            
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️ 无法连接到OpenRouter API")
            return "error"
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ OpenRouter API请求异常: {e}")
            return "error"
            
        except Exception as e:
            logger.error(f"❌ OpenRouter密钥验证意外错误: {e}")
            return "error"
    
    def get_key_info(self, api_key: str) -> Dict[str, Any]:
        """
        获取密钥详细信息
        
        Args:
            api_key: API密钥
            
        Returns:
            Dict[str, Any]: 密钥信息，包含usage、limit等
        """
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            proxies = Config.get_requests_proxies()
            
            if proxies:
                response = requests.get(
                    self.VALIDATION_ENDPOINT, 
                    headers=headers, 
                    timeout=self.timeout,
                    proxies=proxies
                )
            else:
                response = requests.get(
                    self.VALIDATION_ENDPOINT, 
                    headers=headers, 
                    timeout=self.timeout
                )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {})
            else:
                return {}
                
        except Exception as e:
            logger.warning(f"⚠️ 获取OpenRouter密钥信息失败: {e}")
            return {}


# 创建全局实例
openrouter_validator = OpenRouterValidator()