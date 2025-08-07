#!/usr/bin/env python3
"""
Hajimi King - 优化版主程序
使用并发验证、智能Token管理、安全日志等优化功能
"""

import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import signal

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import Config
from utils.file_manager import FileManager, Checkpoint
from utils.github_utils_enhanced import EnhancedGitHubUtils as GitHubUtils
from utils.concurrent_validator import concurrent_validator
from utils.secure_logger import secure_logger
from utils.token_manager import SmartTokenManager
from utils.stats_reporter import stats_reporter
from utils.session_manager import GitHubSessionManager


class HajimiKingOptimized:
    """优化版的Hajimi King主类"""
    
    def __init__(self):
        """初始化所有组件"""
        secure_logger.info("=" * 60)
        secure_logger.info("🚀 HAJIMI KING OPTIMIZED STARTING")
        secure_logger.info("=" * 60)
        
        # 初始化组件
        self.file_manager = FileManager(Config.DATA_PATH)
        self.token_manager = SmartTokenManager(Config.GITHUB_TOKENS)
        self.github_session = GitHubSessionManager(Config.GITHUB_TOKENS)
        self.github_utils = GitHubUtils.create_instance(Config.GITHUB_TOKENS)
        
        # 统计报告器
        stats_reporter.start_scan()
        
        # 信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.running = True
        secure_logger.info("✅ System initialized successfully")
    
    def _signal_handler(self, signum, frame):
        """处理终止信号"""
        secure_logger.info("\n⛔ Received termination signal, shutting down gracefully...")
        self.running = False
        self._cleanup()
        sys.exit(0)
    
    def _cleanup(self):
        """清理资源"""
        secure_logger.info("🧹 Cleaning up resources...")
        
        # 保存最终统计
        stats_reporter.end_scan()
        stats_reporter.print_summary()
        stats_reporter.generate_html_report()
        
        # 关闭验证器
        concurrent_validator.shutdown()
        
        # 显示Token状态
        token_summary = self.token_manager.get_status_summary()
        secure_logger.info(f"📊 Token usage summary: {token_summary['total_requests']} requests, "
                          f"{token_summary['success_rate']:.1%} success rate")
        
        secure_logger.info("✅ Cleanup completed")
    
    def check_system(self) -> bool:
        """系统检查"""
        secure_logger.info("🔍 Running system checks...")
        
        if not Config.check():
            secure_logger.error("❌ Configuration check failed")
            return False
        
        if not self.file_manager.check():
            secure_logger.error("❌ File manager check failed")
            return False
        
        secure_logger.info("✅ All system checks passed")
        return True
    
    def extract_keys_from_content(self, content: str) -> Dict[str, List[str]]:
        """从内容中提取密钥"""
        import re
        
        keys = {"gemini": [], "openrouter": []}
        api_key_type = Config.API_KEY_TYPE.lower()
        
        if api_key_type in ["gemini", "both"]:
            gemini_pattern = r'(AIzaSy[A-Za-z0-9\-_]{33})'
            keys["gemini"] = re.findall(gemini_pattern, content)
        
        if api_key_type in ["openrouter", "both"]:
            openrouter_pattern = r'(sk-or-[A-Za-z0-9\-_]{20,50})'
            keys["openrouter"] = re.findall(openrouter_pattern, content)
        
        return keys
    
    def filter_placeholder_keys(self, keys_by_type: Dict[str, List[str]], content: str) -> Dict[str, List[str]]:
        """过滤占位符密钥"""
        filtered = {}
        
        for key_type, key_list in keys_by_type.items():
            filtered_keys = []
            for key in key_list:
                context_index = content.find(key)
                if context_index != -1:
                    snippet = content[context_index:context_index + 45]
                    if "..." in snippet or "YOUR_" in snippet.upper() or "PLACEHOLDER" in snippet.upper():
                        continue
                filtered_keys.append(key)
            filtered[key_type] = list(set(filtered_keys))  # 去重
        
        return filtered
    
    def process_item(self, item: Dict[str, Any]) -> Tuple[int, int]:
        """
        处理单个搜索结果项
        
        Returns:
            (valid_count, rate_limited_count)
        """
        repo_name = item["repository"]["full_name"]
        file_path = item["path"]
        file_url = item["html_url"]
        
        # 更新统计
        stats_reporter.add_scanned_item()
        
        # 获取文件内容
        content = self.github_utils.get_file_content(item)
        if not content:
            secure_logger.warning(f"⚠️ Failed to fetch: {file_url}")
            stats_reporter.add_error("fetch_failed", f"Could not fetch {file_url}")
            return 0, 0
        
        # 提取密钥
        keys_by_type = self.extract_keys_from_content(content)
        filtered_keys = self.filter_placeholder_keys(keys_by_type, content)
        
        total_keys = sum(len(keys) for keys in filtered_keys.values())
        if total_keys == 0:
            return 0, 0
        
        secure_logger.info(f"🔑 Found {total_keys} potential keys in {repo_name}/{file_path}")
        
        # 并发验证密钥
        validation_results = concurrent_validator.validate_batch(filtered_keys)
        
        valid_keys = []
        rate_limited_keys = []
        
        for key_type, results in validation_results.items():
            for result in results:
                # 更新统计
                stats_reporter.add_found_key(key_type, f"{repo_name}/{file_path}", result.is_valid)
                
                if result.is_valid:
                    valid_keys.append(result.key)
                    secure_logger.log_key_validation(key_type, result.key, True, result.details)
                elif result.rate_limited:
                    rate_limited_keys.append(result.key)
                    stats_reporter.add_rate_limited_key(key_type)
                    secure_logger.log_key_validation(key_type, result.key, False, {"reason": "rate_limited"})
                else:
                    secure_logger.log_key_validation(key_type, result.key, False, {"error": result.error})
        
        # 保存结果
        if valid_keys:
            self.file_manager.save_valid_keys(repo_name, file_path, file_url, valid_keys)
            secure_logger.info(f"💾 Saved {len(valid_keys)} valid keys")
        
        if rate_limited_keys:
            self.file_manager.save_rate_limited_keys(repo_name, file_path, file_url, rate_limited_keys)
            secure_logger.info(f"💾 Saved {len(rate_limited_keys)} rate limited keys")
        
        return len(valid_keys), len(rate_limited_keys)
    
    def should_skip_item(self, item: Dict[str, Any], checkpoint: Checkpoint, force_full_scan: bool) -> Tuple[bool, str]:
        """检查是否应跳过此项"""
        # 检查SHA
        if not force_full_scan and item.get("sha") in checkpoint.scanned_shas:
            stats_reporter.add_skipped_item("sha_duplicate")
            return True, "sha_duplicate"
        
        # 检查仓库年龄
        repo_pushed_at = item["repository"].get("pushed_at")
        if repo_pushed_at:
            repo_pushed_dt = datetime.strptime(repo_pushed_at, "%Y-%m-%dT%H:%M:%SZ")
            if repo_pushed_dt < datetime.utcnow() - timedelta(days=Config.DATE_RANGE_DAYS):
                stats_reporter.add_skipped_item("age_filter")
                return True, "age_filter"
        
        # 检查文件路径黑名单
        lowercase_path = item["path"].lower()
        if any(token in lowercase_path for token in Config.FILE_PATH_BLACKLIST):
            stats_reporter.add_skipped_item("doc_filter")
            return True, "doc_filter"
        
        return False, ""
    
    def process_query(self, query: str, checkpoint: Checkpoint, force_full_scan: bool) -> Tuple[int, int]:
        """
        处理单个查询
        
        Returns:
            (valid_count, rate_limited_count)
        """
        secure_logger.info(f"🔍 Processing query: {query}")
        
        # 使用session管理器进行搜索
        result = self.github_utils.search_for_keys(query)
        
        if not result or "items" not in result:
            secure_logger.warning(f"❌ Query failed: {query}")
            stats_reporter.add_error("query_failed", f"Query failed: {query}")
            return 0, 0
        
        items = result["items"]
        if not items:
            secure_logger.info(f"📭 No items found for query: {query}")
            return 0, 0
        
        secure_logger.info(f"📦 Found {len(items)} items for query: {query}")
        
        valid_count = 0
        rate_limited_count = 0
        
        for i, item in enumerate(items, 1):
            if not self.running:
                break
            
            # 检查是否跳过
            should_skip, reason = self.should_skip_item(item, checkpoint, force_full_scan)
            if should_skip:
                secure_logger.debug(f"⏭️ Skipping item {i}/{len(items)}: {reason}")
                continue
            
            # 处理项
            item_valid, item_limited = self.process_item(item)
            valid_count += item_valid
            rate_limited_count += item_limited
            
            # 记录已扫描
            checkpoint.add_scanned_sha(item.get("sha"))
            
            # 定期保存进度
            if i % 10 == 0:
                self.file_manager.save_checkpoint(checkpoint)
                stats_reporter.save_report()
                secure_logger.info(f"📈 Progress: {i}/{len(items)} items processed")
        
        return valid_count, rate_limited_count
    
    def run(self):
        """主运行循环"""
        if not self.check_system():
            secure_logger.error("❌ System check failed, exiting...")
            return
        
        # 加载查询和检查点
        search_queries = self.file_manager.get_search_queries()
        checkpoint = self.file_manager.load_checkpoint()
        
        secure_logger.info(f"📋 Loaded {len(search_queries)} queries")
        stats_reporter.update_query_stats(len(search_queries), 0)
        
        # 检查是否全量扫描
        force_full_scan = checkpoint.should_force_full_scan()
        if force_full_scan:
            secure_logger.info("🔄 Full scan mode activated")
            checkpoint.reset_for_full_scan()
        
        loop_count = 0
        total_valid = 0
        total_limited = 0
        
        while self.running:
            loop_count += 1
            secure_logger.info(f"\n🔄 Starting loop #{loop_count}")
            
            processed_queries = 0
            
            for query in search_queries:
                if not self.running:
                    break
                
                # 检查是否已处理
                if query in checkpoint.processed_queries and not force_full_scan:
                    continue
                
                # 获取最佳Token
                token = self.token_manager.get_best_token()
                if not token:
                    secure_logger.error("❌ No available tokens, waiting...")
                    time.sleep(60)
                    continue
                
                # 处理查询
                valid, limited = self.process_query(query, checkpoint, force_full_scan)
                total_valid += valid
                total_limited += limited
                
                # 更新Token状态
                self.token_manager.update_token_status(token, success=valid > 0 or limited > 0)
                
                # 标记查询已处理
                checkpoint.add_processed_query(query)
                checkpoint.update_scan_time()
                self.file_manager.save_checkpoint(checkpoint)
                
                processed_queries += 1
                stats_reporter.update_query_stats(len(search_queries), processed_queries)
                
                # 定期显示统计
                if processed_queries % 5 == 0:
                    stats_reporter.print_summary()
                    token_summary = self.token_manager.get_status_summary()
                    secure_logger.info(f"🎯 Tokens: {token_summary['available_tokens']}/{token_summary['total_tokens']} available")
            
            if force_full_scan:
                checkpoint.update_full_scan_time()
                self.file_manager.save_checkpoint(checkpoint)
                secure_logger.info("✅ Full scan completed")
            
            secure_logger.info(f"🏁 Loop #{loop_count} complete - Valid: {total_valid}, Limited: {total_limited}")
            
            # 生成报告
            stats_reporter.save_report()
            stats_reporter.generate_html_report()
            
            # 休眠
            secure_logger.info("💤 Sleeping for 60 seconds...")
            time.sleep(60)
    
    def main(self):
        """主入口"""
        try:
            self.run()
        except KeyboardInterrupt:
            secure_logger.info("\n⛔ Interrupted by user")
        except Exception as e:
            secure_logger.error(f"💥 Fatal error: {e}")
            stats_reporter.add_error("fatal", str(e))
        finally:
            self._cleanup()


if __name__ == "__main__":
    app = HajimiKingOptimized()
    app.main()