import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any
import threading

from common.Logger import logger
from common.config import Config


class SessionManager:
    """HTTP Session管理器，使用连接池和重试策略"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.sessions = {}
            self.initialized = True
    
    def get_session(self, 
                    service: str = "default",
                    max_retries: int = 3,
                    backoff_factor: float = 0.3,
                    pool_connections: int = 10,
                    pool_maxsize: int = 20) -> requests.Session:
        """
        获取或创建一个Session实例
        
        Args:
            service: 服务标识符
            max_retries: 最大重试次数
            backoff_factor: 重试退避因子
            pool_connections: 连接池连接数
            pool_maxsize: 连接池最大大小
        
        Returns:
            requests.Session: 配置好的Session实例
        """
        if service not in self.sessions:
            session = requests.Session()
            
            # 配置重试策略
            retry_strategy = Retry(
                total=max_retries,
                backoff_factor=backoff_factor,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
            )
            
            # 配置适配器
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=pool_connections,
                pool_maxsize=pool_maxsize
            )
            
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            # 设置默认headers
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
            })
            
            # 配置代理
            proxies = Config.get_requests_proxies()
            if proxies:
                session.proxies.update(proxies)
            
            self.sessions[service] = session
            logger.debug(f"✅ Created new session for service: {service}")
        
        return self.sessions[service]
    
    def close_session(self, service: str = "default"):
        """关闭指定服务的Session"""
        if service in self.sessions:
            self.sessions[service].close()
            del self.sessions[service]
            logger.debug(f"🔒 Closed session for service: {service}")
    
    def close_all(self):
        """关闭所有Session"""
        for service in list(self.sessions.keys()):
            self.close_session(service)
        logger.info("🔒 All sessions closed")


class GitHubSessionManager:
    """GitHub API专用Session管理器"""
    
    def __init__(self, tokens: list):
        self.tokens = tokens
        self.session_manager = SessionManager()
        self.current_token_index = 0
        self._lock = threading.Lock()
    
    def get_session_with_token(self) -> tuple[requests.Session, str]:
        """
        获取配置了Token的Session
        
        Returns:
            tuple: (session, token)
        """
        with self._lock:
            token = self.tokens[self.current_token_index]
            self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
        
        session = self.session_manager.get_session("github")
        session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        })
        
        return session, token
    
    def mark_token_limited(self, token: str):
        """标记Token为限流状态"""
        logger.warning(f"⚠️ Token marked as rate limited: {token[:10]}...")
    
    def request_with_retry(self, 
                          method: str,
                          url: str,
                          max_attempts: int = 3,
                          **kwargs) -> Optional[requests.Response]:
        """
        使用自动Token轮换的请求方法
        
        Args:
            method: HTTP方法
            url: 请求URL
            max_attempts: 最大尝试次数
            **kwargs: 其他请求参数
        
        Returns:
            Optional[requests.Response]: 响应对象
        """
        last_error = None
        
        for attempt in range(max_attempts):
            session, token = self.get_session_with_token()
            
            try:
                response = session.request(method, url, **kwargs)
                
                # 检查限流
                if response.status_code in [403, 429]:
                    self.mark_token_limited(token)
                    continue
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.debug(f"Request failed (attempt {attempt + 1}/{max_attempts}): {e}")
                continue
        
        logger.error(f"❌ All attempts failed for {url}: {last_error}")
        return None


# 创建全局实例
session_manager = SessionManager()