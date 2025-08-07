import asyncio
import random
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from common.config import Config
from utils.token_manager import SmartTokenManager
from utils.secure_logger import secure_logger
from utils.stats_reporter import stats_reporter


class AsyncGitHubScanner:
    """异步GitHub扫描器，提升并发性能"""
    
    GITHUB_API_URL = "https://api.github.com/search/code"
    
    def __init__(self, tokens: List[str], max_concurrency: int = 10):
        """
        初始化异步扫描器
        
        Args:
            tokens: GitHub Token列表
            max_concurrency: 最大并发数
        """
        self.token_manager = SmartTokenManager(tokens)
        self.semaphore = asyncio.Semaphore(max_concurrency)
        
        # 创建异步HTTP客户端
        proxies = Config.get_requests_proxies()
        self.client = httpx.AsyncClient(
            proxies=proxies,
            timeout=30,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
        )
        
        secure_logger.info(f"🚀 AsyncGitHubScanner initialized with {max_concurrency} concurrent tasks")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_page(self, query: str, page: int) -> Optional[Dict[str, Any]]:
        """
        异步获取单个页面的搜索结果
        
        Args:
            query: 搜索查询
            page: 页码
        
        Returns:
            Optional[Dict[str, Any]]: 搜索结果
        """
        token = self.token_manager.get_best_token()
        if not token:
            secure_logger.error("❌ No available tokens for async fetch")
            await asyncio.sleep(60)
            return None
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token}",
            "User-Agent": "Mozilla/5.0"
        }
        
        params = {
            "q": query,
            "per_page": 100,
            "page": page
        }
        
        async with self.semaphore:
            try:
                response = await self.client.get(self.GITHUB_API_URL, headers=headers, params=params)
                
                # 更新token状态
                self.token_manager.update_token_status(token, response.headers, response.status_code == 200)
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                secure_logger.warning(f"⚠️ HTTP Error {e.response.status_code} for page {page}")
                if e.response.status_code in [403, 429]:
                    # 标记token限流
                    self.token_manager.mark_token_limited(token)
                raise  # 让tenacity处理重试
                
            except httpx.RequestError as e:
                secure_logger.error(f"❌ Network error: {type(e).__name__}")
                raise
    
    async def search_for_keys(self, query: str) -> List[Dict[str, Any]]:
        """
        异步搜索所有页面的密钥
        
        Args:
            query: 搜索查询
            
        Returns:
            List[Dict[str, Any]]: 所有搜索结果项
        """
        all_items = []
        
        # 先获取第一页，确定总页数
        first_page_result = await self._fetch_page(query, 1)
        
        if not first_page_result or not first_page_result.get("items"):
            secure_logger.info(f"📭 No results found for query: {query}")
            return []
        
        all_items.extend(first_page_result["items"])
        
        total_count = first_page_result.get("total_count", 0)
        max_pages = min((total_count // 100) + 1, 10)  # GitHub API最多返回10页
        
        secure_logger.info(f"📦 Found {total_count} items, fetching up to {max_pages} pages...")
        
        # 并发获取剩余页面
        if max_pages > 1:
            tasks = [self._fetch_page(query, page) for page in range(2, max_pages + 1)]
            
            for future in asyncio.as_completed(tasks):
                try:
                    page_result = await future
                    if page_result and page_result.get("items"):
                        all_items.extend(page_result["items"])
                except Exception as e:
                    secure_logger.error(f"❌ Failed to fetch page: {e}")
        
        secure_logger.info(f"✅ Query '{query}' complete, found {len(all_items)} items total")
        return all_items
    
    async def get_file_content(self, item: Dict[str, Any]) -> Optional[str]:
        """异步获取文件内容"""
        url = item.get("html_url", "").replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except (httpx.RequestError, httpx.HTTPStatusError):
            # 失败后尝试API获取
            api_url = item.get("url")
            if not api_url:
                return None
            
            token = self.token_manager.get_best_token()
            if not token:
                return None
            
            headers = {"Authorization": f"token {token}"}
            
            try:
                response = await self.client.get(api_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if "content" in data:
                    import base64
                    return base64.b64decode(data["content"]).decode('utf-8', errors='ignore')
            except Exception:
                return None
        
        return None
    
    async def process_item(self, item: Dict[str, Any]) -> Tuple[int, int]:
        """异步处理单个项"""
        content = await self.get_file_content(item)
        
        if not content:
            stats_reporter.add_skipped_item("fetch_failed")
            return 0, 0
        
        # 提取和验证
        # (这里可以复用之前的逻辑，但为了演示，简化了)
        from app.hajimi_king_optimized import HajimiKingOptimized
        
        extractor = HajimiKingOptimized()
        keys_by_type = extractor.extract_keys_from_content(content)
        filtered_keys = extractor.filter_placeholder_keys(keys_by_type, content)
        
        total_keys = sum(len(v) for v in filtered_keys.values())
        if total_keys == 0:
            return 0, 0
        
        from utils.concurrent_validator import concurrent_validator
        
        results = concurrent_validator.validate_batch(filtered_keys)
        valid_count = sum(1 for res_list in results.values() for res in res_list if res.is_valid)
        limited_count = sum(1 for res_list in results.values() for res in res_list if res.rate_limited)
        
        return valid_count, limited_count
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
        
async def run_async_scanner():
    """运行异步扫描器示例"""
    async with AsyncGitHubScanner(Config.GITHUB_TOKENS) as scanner:
        queries = ["AIzaSy", "sk-or-"]
        
        for query in queries:
            items = await scanner.search_for_keys(query)
            
            tasks = [scanner.process_item(item) for item in items]
            
            results = await asyncio.gather(*tasks)
            
            total_valid = sum(r[0] for r in results)
            total_limited = sum(r[1] for r in results)
            
            secure_logger.info(f"📊 Query '{query}': {total_valid} valid, {total_limited} rate limited")
            
            
if __name__ == "__main__":
    # 运行异步扫描
    asyncio.run(run_async_scanner())
