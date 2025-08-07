import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading

from common.Logger import logger


@dataclass
class TokenStatus:
    """Token状态信息"""
    token: str
    remaining_requests: int = 1000  # 默认剩余请求数
    reset_time: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=1))
    is_limited: bool = False
    consecutive_failures: int = 0
    last_used: datetime = field(default_factory=datetime.now)
    total_requests: int = 0
    successful_requests: int = 0


class SmartTokenManager:
    """智能Token管理器，自动处理限流和轮换"""
    
    def __init__(self, tokens: List[str], rate_limit_threshold: int = 10):
        """
        初始化Token管理器
        
        Args:
            tokens: GitHub Token列表
            rate_limit_threshold: 触发限流的剩余请求阈值
        """
        self.tokens = tokens
        self.rate_limit_threshold = rate_limit_threshold
        self.token_status: Dict[str, TokenStatus] = {}
        self._lock = threading.Lock()
        self.current_index = 0
        
        # 初始化所有token状态
        for token in tokens:
            self.token_status[token] = TokenStatus(token=token)
        
        logger.info(f"🎯 Initialized SmartTokenManager with {len(tokens)} tokens")
    
    def get_best_token(self) -> Optional[str]:
        """
        获取最佳可用Token
        
        Returns:
            Optional[str]: 最佳Token，如果没有可用则返回None
        """
        with self._lock:
            now = datetime.now()
            available_tokens = []
            
            # 收集所有可用的token
            for token, status in self.token_status.items():
                # 检查是否已解除限流
                if status.is_limited and now >= status.reset_time:
                    status.is_limited = False
                    status.remaining_requests = 1000
                    status.consecutive_failures = 0
                    logger.info(f"🔓 Token unlocked: {self._mask_token(token)}")
                
                # 只选择未限流且有剩余请求的token
                if not status.is_limited and status.remaining_requests > self.rate_limit_threshold:
                    available_tokens.append((token, status))
            
            if not available_tokens:
                # 如果没有可用token，尝试找最快恢复的
                return self._get_next_available_token()
            
            # 按照以下优先级排序：
            # 1. 剩余请求数最多
            # 2. 连续失败次数最少
            # 3. 最久未使用
            available_tokens.sort(key=lambda x: (
                -x[1].remaining_requests,
                x[1].consecutive_failures,
                x[1].last_used
            ))
            
            best_token = available_tokens[0][0]
            self.token_status[best_token].last_used = now
            self.token_status[best_token].total_requests += 1
            
            return best_token
    
    def _get_next_available_token(self) -> Optional[str]:
        """获取下一个可用的Token（等待恢复）"""
        now = datetime.now()
        next_available = None
        min_wait_time = timedelta(hours=24)  # 最大等待时间
        
        for token, status in self.token_status.items():
            if status.is_limited:
                wait_time = status.reset_time - now
                if wait_time < min_wait_time:
                    min_wait_time = wait_time
                    next_available = token
        
        if next_available and min_wait_time.total_seconds() < 60:
            # 如果等待时间小于1分钟，直接等待
            logger.warning(f"⏳ All tokens limited, waiting {min_wait_time.total_seconds():.0f}s...")
            time.sleep(min_wait_time.total_seconds())
            self.token_status[next_available].is_limited = False
            return next_available
        
        logger.error("❌ No tokens available and wait time too long")
        return None
    
    def update_token_status(self, 
                          token: str, 
                          response_headers: Optional[Dict] = None,
                          success: bool = True):
        """
        更新Token状态
        
        Args:
            token: Token字符串
            response_headers: 响应头（包含限流信息）
            success: 请求是否成功
        """
        with self._lock:
            if token not in self.token_status:
                return
            
            status = self.token_status[token]
            
            if success:
                status.consecutive_failures = 0
                status.successful_requests += 1
            else:
                status.consecutive_failures += 1
                
                # 连续失败太多次，暂时禁用
                if status.consecutive_failures >= 3:
                    status.is_limited = True
                    status.reset_time = datetime.now() + timedelta(minutes=5)
                    logger.warning(f"🔒 Token temporarily disabled due to failures: {self._mask_token(token)}")
            
            # 更新限流信息
            if response_headers:
                if 'X-RateLimit-Remaining' in response_headers:
                    status.remaining_requests = int(response_headers['X-RateLimit-Remaining'])
                    
                    # 检查是否接近限流
                    if status.remaining_requests <= self.rate_limit_threshold:
                        logger.warning(f"⚠️ Token near rate limit: {self._mask_token(token)} - {status.remaining_requests} remaining")
                
                if 'X-RateLimit-Reset' in response_headers:
                    reset_timestamp = int(response_headers['X-RateLimit-Reset'])
                    status.reset_time = datetime.fromtimestamp(reset_timestamp)
                
                # 检查是否触发限流
                if 'X-RateLimit-Remaining' in response_headers and int(response_headers['X-RateLimit-Remaining']) == 0:
                    status.is_limited = True
                    logger.error(f"🚫 Token rate limited: {self._mask_token(token)}")
    
    def mark_token_limited(self, token: str, duration_minutes: int = 60):
        """
        手动标记Token为限流状态
        
        Args:
            token: Token字符串
            duration_minutes: 限流持续时间（分钟）
        """
        with self._lock:
            if token in self.token_status:
                status = self.token_status[token]
                status.is_limited = True
                status.reset_time = datetime.now() + timedelta(minutes=duration_minutes)
                status.remaining_requests = 0
                logger.warning(f"🔒 Token marked as limited for {duration_minutes}min: {self._mask_token(token)}")
    
    def get_status_summary(self) -> Dict:
        """
        获取Token状态摘要
        
        Returns:
            Dict: 状态摘要信息
        """
        with self._lock:
            total_tokens = len(self.tokens)
            available_tokens = sum(1 for s in self.token_status.values() if not s.is_limited)
            total_requests = sum(s.total_requests for s in self.token_status.values())
            successful_requests = sum(s.successful_requests for s in self.token_status.values())
            
            return {
                "total_tokens": total_tokens,
                "available_tokens": available_tokens,
                "limited_tokens": total_tokens - available_tokens,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
                "tokens_detail": [
                    {
                        "token": self._mask_token(status.token),
                        "is_limited": status.is_limited,
                        "remaining_requests": status.remaining_requests,
                        "consecutive_failures": status.consecutive_failures,
                        "reset_time": status.reset_time.isoformat() if status.is_limited else None
                    }
                    for status in self.token_status.values()
                ]
            }
    
    def _mask_token(self, token: str) -> str:
        """掩码Token用于日志"""
        if len(token) > 10:
            return f"{token[:7]}...{token[-3:]}"
        return "*" * len(token)
    
    def rotate_token(self) -> Optional[str]:
        """
        简单的轮换策略（用于向后兼容）
        
        Returns:
            Optional[str]: 下一个Token
        """
        return self.get_best_token()


# 示例使用
if __name__ == "__main__":
    tokens = ["ghp_token1", "ghp_token2", "ghp_token3"]
    manager = SmartTokenManager(tokens)
    
    # 获取最佳token
    best_token = manager.get_best_token()
    print(f"Best token: {best_token}")
    
    # 模拟请求和更新状态
    headers = {"X-RateLimit-Remaining": "500", "X-RateLimit-Reset": str(int(time.time()) + 3600)}
    manager.update_token_status(best_token, headers, success=True)
    
    # 获取状态摘要
    summary = manager.get_status_summary()
    print(f"Status summary: {summary}")