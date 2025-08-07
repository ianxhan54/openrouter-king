import random
import time
from typing import Dict, List, Optional, Any, Tuple
import base64
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from common.Logger import logger
from common.config import Config


class EnhancedGitHubUtils:
    """增强版GitHub工具类，改进错误处理和重试机制"""
    
    GITHUB_API_URL = "https://api.github.com/search/code"
    GITHUB_RAW_URL = "https://raw.githubusercontent.com"
    
    # HTTP状态码含义
    STATUS_MESSAGES = {
        400: "Bad Request - 请求格式错误",
        401: "Unauthorized - Token无效或过期",
        403: "Forbidden - 访问被拒绝或达到限流",
        404: "Not Found - 文件或仓库不存在",
        422: "Unprocessable Entity - 请求参数错误",
        429: "Too Many Requests - 达到API限流",
        500: "Internal Server Error - GitHub服务器错误",
        502: "Bad Gateway - GitHub服务暂时不可用",
        503: "Service Unavailable - GitHub服务维护中"
    }

    def __init__(self, tokens: List[str]):
        self.tokens = [token.strip() for token in tokens if token.strip()]
        self._token_ptr = 0
        self.session = self._create_session()
        self.failed_tokens = set()  # 记录失败的token
        self.token_stats = {token: {"success": 0, "failure": 0} for token in self.tokens}
        
    def _create_session(self) -> requests.Session:
        """创建配置好的Session"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def _next_token(self) -> Optional[str]:
        """获取下一个可用的Token"""
        if not self.tokens:
            return None
        
        # 跳过失败的token
        attempts = 0
        while attempts < len(self.tokens):
            token = self.tokens[self._token_ptr % len(self.tokens)]
            self._token_ptr += 1
            attempts += 1
            
            if token not in self.failed_tokens:
                return token.strip()
        
        # 如果所有token都失败了，重置失败列表再试一次
        if self.failed_tokens:
            logger.warning("⚠️ All tokens failed, resetting and retrying...")
            self.failed_tokens.clear()
            return self.tokens[0] if self.tokens else None
        
        return None

    def _handle_api_error(self, response: requests.Response, url: str) -> None:
        """处理API错误响应"""
        status = response.status_code
        error_msg = self.STATUS_MESSAGES.get(status, f"Unknown error {status}")
        
        # 尝试获取详细错误信息
        try:
            error_data = response.json()
            if "message" in error_data:
                error_msg = f"{error_msg} - {error_data['message']}"
            if "errors" in error_data:
                error_details = str(error_data["errors"])
                error_msg = f"{error_msg} - Details: {error_details}"
        except:
            pass
        
        # 检查特定错误类型
        if status == 404:
            # 404可能是正常的（文件被删除等），降级为warning
            logger.warning(f"⚠️ File not found (404): {url}")
        elif status == 403:
            # 检查是否是限流
            remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
            if remaining == '0':
                logger.error(f"🚫 Rate limit exceeded for current token")
                # 标记当前token为失败
                auth_header = response.request.headers.get('Authorization', '')
                if auth_header.startswith('token '):
                    failed_token = auth_header[6:]
                    self.failed_tokens.add(failed_token)
            else:
                logger.error(f"❌ Access forbidden (403): {error_msg}")
        else:
            logger.error(f"❌ API Error {status}: {error_msg} | URL: {url}")

    def search_for_keys(self, query: str, max_retries: int = 5) -> Dict[str, Any]:
        """搜索GitHub代码"""
        all_items = []
        total_count = 0
        expected_total = None
        pages_processed = 0

        for page in range(1, 11):
            page_result = None
            page_success = False

            for attempt in range(1, max_retries + 1):
                current_token = self._next_token()
                if not current_token:
                    logger.error("❌ No available tokens")
                    break

                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "Authorization": f"token {current_token}",
                    "User-Agent": "Mozilla/5.0"
                }

                params = {
                    "q": query,
                    "per_page": 100,
                    "page": page
                }

                try:
                    proxies = Config.get_requests_proxies()
                    response = self.session.get(
                        self.GITHUB_API_URL, 
                        headers=headers, 
                        params=params, 
                        timeout=30,
                        proxies=proxies
                    )
                    
                    if response.status_code == 200:
                        page_result = response.json()
                        page_success = True
                        self.token_stats[current_token]["success"] += 1
                        break
                    else:
                        self._handle_api_error(response, self.GITHUB_API_URL)
                        self.token_stats[current_token]["failure"] += 1
                        
                        if response.status_code in [403, 429]:
                            wait = min(2 ** attempt + random.uniform(0, 1), 60)
                            logger.info(f"⏳ Waiting {wait:.1f}s before retry...")
                            time.sleep(wait)
                        continue

                except requests.exceptions.RequestException as e:
                    logger.error(f"❌ Network error: {type(e).__name__} - {str(e)}")
                    time.sleep(2 ** attempt)
                    continue

            if not page_success or not page_result:
                if page == 1:
                    logger.error(f"❌ Failed to fetch first page for query: {query}")
                break

            pages_processed += 1
            
            if page == 1:
                total_count = page_result.get("total_count", 0)
                expected_total = min(total_count, 1000)

            items = page_result.get("items", [])
            if not items:
                break

            all_items.extend(items)

            if expected_total and len(all_items) >= expected_total:
                break

            time.sleep(random.uniform(0.5, 1.5))

        logger.info(f"🔍 Search complete: {len(all_items)}/{expected_total or '?'} items")
        
        return {
            "total_count": total_count,
            "incomplete_results": len(all_items) < (expected_total or 0),
            "items": all_items
        }

    def get_file_content(self, item: Dict[str, Any]) -> Optional[str]:
        """获取文件内容，使用多种策略"""
        repo_full_name = item["repository"]["full_name"]
        file_path = item["path"]
        
        # 策略1: 尝试通过API获取
        content = self._get_content_via_api(repo_full_name, file_path)
        if content:
            return content
        
        # 策略2: 尝试通过raw.githubusercontent.com获取
        content = self._get_content_via_raw(repo_full_name, file_path, item)
        if content:
            return content
        
        # 策略3: 如果文件名没有扩展名，可能是特殊文件
        if '.' not in file_path.split('/')[-1]:
            # 尝试常见的配置文件扩展名
            for ext in ['.env', '.txt', '.json', '.yml', '.yaml', '.conf', '.config']:
                test_path = file_path + ext
                content = self._get_content_via_api(repo_full_name, test_path)
                if content:
                    logger.info(f"✅ Found file with extension: {test_path}")
                    return content
        
        logger.warning(f"⚠️ Could not fetch content for: {repo_full_name}/{file_path}")
        return None

    def _get_content_via_api(self, repo: str, path: str) -> Optional[str]:
        """通过GitHub API获取文件内容"""
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        
        for attempt in range(3):
            token = self._next_token()
            if not token:
                break
            
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {token}"
            }
            
            try:
                proxies = Config.get_requests_proxies()
                response = self.session.get(url, headers=headers, timeout=30, proxies=proxies)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # 处理文件内容
                    if "content" in data:
                        # Base64解码
                        content = base64.b64decode(data["content"]).decode('utf-8', errors='ignore')
                        return content
                    elif "download_url" in data:
                        # 使用下载URL
                        return self._download_content(data["download_url"], token)
                    
                elif response.status_code == 404:
                    # 文件不存在，不需要重试
                    logger.debug(f"File not found: {url}")
                    break
                else:
                    self._handle_api_error(response, url)
                    if response.status_code in [403, 429]:
                        time.sleep(2 ** attempt)
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"API request failed: {type(e).__name__}")
                continue
        
        return None

    def _get_content_via_raw(self, repo: str, path: str, item: Dict) -> Optional[str]:
        """通过raw.githubusercontent.com获取文件内容"""
        # 获取默认分支
        default_branch = item.get("repository", {}).get("default_branch", "main")
        
        # 尝试多个可能的分支名
        for branch in [default_branch, "main", "master"]:
            url = f"{self.GITHUB_RAW_URL}/{repo}/{branch}/{path}"
            
            try:
                proxies = Config.get_requests_proxies()
                response = self.session.get(url, timeout=30, proxies=proxies)
                
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 404:
                    continue
                    
            except requests.exceptions.RequestException:
                continue
        
        return None

    def _download_content(self, url: str, token: str) -> Optional[str]:
        """下载文件内容"""
        headers = {"Authorization": f"token {token}"}
        
        try:
            proxies = Config.get_requests_proxies()
            response = self.session.get(url, headers=headers, timeout=30, proxies=proxies)
            
            if response.status_code == 200:
                return response.text
            else:
                logger.debug(f"Download failed: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"Download error: {type(e).__name__}")
        
        return None

    def get_token_statistics(self) -> Dict[str, Any]:
        """获取Token使用统计"""
        stats = []
        for token, stat in self.token_stats.items():
            total = stat["success"] + stat["failure"]
            success_rate = stat["success"] / total if total > 0 else 0
            stats.append({
                "token": token[:10] + "...",
                "success": stat["success"],
                "failure": stat["failure"],
                "success_rate": f"{success_rate:.1%}",
                "is_failed": token in self.failed_tokens
            })
        return {"tokens": stats, "failed_count": len(self.failed_tokens)}

    @staticmethod
    def create_instance(tokens: List[str]) -> 'EnhancedGitHubUtils':
        """创建实例"""
        return EnhancedGitHubUtils(tokens)