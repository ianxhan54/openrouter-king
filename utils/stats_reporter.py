import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from common.Logger import logger


@dataclass
class ScanStatistics:
    """扫描统计数据"""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_queries: int = 0
    processed_queries: int = 0
    total_items_scanned: int = 0
    total_keys_found: int = 0
    valid_keys: int = 0
    invalid_keys: int = 0
    rate_limited_keys: int = 0
    skipped_items: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    keys_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    keys_by_source: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat() if self.start_time else None
        data['end_time'] = self.end_time.isoformat() if self.end_time else None
        data['duration'] = str(self.end_time - self.start_time) if self.end_time else None
        return data


class StatsReporter:
    """统计报告生成器"""
    
    def __init__(self, data_path: str = "data"):
        """
        初始化统计报告器
        
        Args:
            data_path: 数据存储路径
        """
        self.data_path = data_path
        self.stats_file = os.path.join(data_path, f"stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        self.current_stats = ScanStatistics()
        self.session_history: List[ScanStatistics] = []
        
        # 确保目录存在
        os.makedirs(data_path, exist_ok=True)
        
        logger.info(f"📊 StatsReporter initialized, output: {self.stats_file}")
    
    def start_scan(self):
        """开始新的扫描会话"""
        self.current_stats = ScanStatistics()
        logger.info("📊 Started new scan session")
    
    def end_scan(self):
        """结束当前扫描会话"""
        self.current_stats.end_time = datetime.now()
        self.session_history.append(self.current_stats)
        self.save_report()
        logger.info("📊 Scan session ended")
    
    def update_query_stats(self, total: int, processed: int):
        """更新查询统计"""
        self.current_stats.total_queries = total
        self.current_stats.processed_queries = processed
    
    def add_scanned_item(self):
        """增加扫描项计数"""
        self.current_stats.total_items_scanned += 1
    
    def add_found_key(self, key_type: str, source: str, is_valid: bool = None):
        """
        添加发现的密钥
        
        Args:
            key_type: 密钥类型
            source: 来源
            is_valid: 是否有效
        """
        self.current_stats.total_keys_found += 1
        self.current_stats.keys_by_type[key_type] += 1
        
        # 记录来源（不记录实际密钥值）
        source_key = f"{source[:50]}..." if len(source) > 50 else source
        if source_key not in self.current_stats.keys_by_source[key_type]:
            self.current_stats.keys_by_source[key_type].append(source_key)
        
        if is_valid is not None:
            if is_valid:
                self.current_stats.valid_keys += 1
            else:
                self.current_stats.invalid_keys += 1
    
    def add_rate_limited_key(self, key_type: str):
        """添加限流密钥统计"""
        self.current_stats.rate_limited_keys += 1
        self.current_stats.keys_by_type[f"{key_type}_rate_limited"] += 1
    
    def add_skipped_item(self, reason: str):
        """
        添加跳过的项
        
        Args:
            reason: 跳过原因
        """
        self.current_stats.skipped_items[reason] += 1
    
    def add_error(self, error_type: str, error_msg: str, context: Optional[Dict] = None):
        """
        添加错误记录
        
        Args:
            error_type: 错误类型
            error_msg: 错误消息
            context: 上下文信息
        """
        self.current_stats.errors.append({
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": error_msg,
            "context": context or {}
        })
    
    def get_current_summary(self) -> Dict:
        """
        获取当前统计摘要
        
        Returns:
            Dict: 统计摘要
        """
        duration = datetime.now() - self.current_stats.start_time
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        success_rate = 0
        if self.current_stats.total_keys_found > 0:
            success_rate = (self.current_stats.valid_keys / self.current_stats.total_keys_found) * 100
        
        return {
            "duration": f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}",
            "queries": f"{self.current_stats.processed_queries}/{self.current_stats.total_queries}",
            "items_scanned": self.current_stats.total_items_scanned,
            "keys_found": self.current_stats.total_keys_found,
            "valid_keys": self.current_stats.valid_keys,
            "invalid_keys": self.current_stats.invalid_keys,
            "rate_limited": self.current_stats.rate_limited_keys,
            "success_rate": f"{success_rate:.1f}%",
            "skipped_items": dict(self.current_stats.skipped_items),
            "keys_by_type": dict(self.current_stats.keys_by_type),
            "errors_count": len(self.current_stats.errors)
        }
    
    def print_summary(self):
        """打印统计摘要到日志"""
        summary = self.get_current_summary()
        
        logger.info("=" * 60)
        logger.info("📊 SCAN STATISTICS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"⏱️  Duration: {summary['duration']}")
        logger.info(f"🔍 Queries: {summary['queries']}")
        logger.info(f"📁 Items scanned: {summary['items_scanned']}")
        logger.info(f"🔑 Keys found: {summary['keys_found']}")
        logger.info(f"✅ Valid keys: {summary['valid_keys']}")
        logger.info(f"❌ Invalid keys: {summary['invalid_keys']}")
        logger.info(f"⚠️  Rate limited: {summary['rate_limited']}")
        logger.info(f"📈 Success rate: {summary['success_rate']}")
        
        if summary['skipped_items']:
            logger.info("🚫 Skipped items:")
            for reason, count in summary['skipped_items'].items():
                logger.info(f"   - {reason}: {count}")
        
        if summary['keys_by_type']:
            logger.info("🔐 Keys by type:")
            for key_type, count in summary['keys_by_type'].items():
                logger.info(f"   - {key_type}: {count}")
        
        if summary['errors_count'] > 0:
            logger.warning(f"⚠️  Errors encountered: {summary['errors_count']}")
        
        logger.info("=" * 60)
    
    def save_report(self, filename: Optional[str] = None):
        """
        保存统计报告到文件
        
        Args:
            filename: 可选的文件名
        """
        output_file = filename or self.stats_file
        
        try:
            report_data = {
                "generated_at": datetime.now().isoformat(),
                "current_session": self.current_stats.to_dict(),
                "summary": self.get_current_summary(),
                "session_history": [s.to_dict() for s in self.session_history[-10:]]  # 保留最近10次
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📊 Report saved to: {output_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save report: {e}")
    
    def generate_html_report(self) -> str:
        """
        生成HTML格式的报告
        
        Returns:
            str: HTML报告内容
        """
        summary = self.get_current_summary()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Hajimi King Scan Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }}
                h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                .stat-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #007bff; }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
                .stat-label {{ color: #666; margin-top: 5px; }}
                .success {{ border-left-color: #28a745; }}
                .success .stat-value {{ color: #28a745; }}
                .warning {{ border-left-color: #ffc107; }}
                .warning .stat-value {{ color: #ffc107; }}
                .danger {{ border-left-color: #dc3545; }}
                .danger .stat-value {{ color: #dc3545; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #007bff; color: white; }}
                tr:hover {{ background: #f5f5f5; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎪 Hajimi King Scan Report</h1>
                <p>Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{summary['duration']}</div>
                        <div class="stat-label">Duration</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{summary['items_scanned']}</div>
                        <div class="stat-label">Items Scanned</div>
                    </div>
                    <div class="stat-card success">
                        <div class="stat-value">{summary['valid_keys']}</div>
                        <div class="stat-label">Valid Keys</div>
                    </div>
                    <div class="stat-card danger">
                        <div class="stat-value">{summary['invalid_keys']}</div>
                        <div class="stat-label">Invalid Keys</div>
                    </div>
                    <div class="stat-card warning">
                        <div class="stat-value">{summary['rate_limited']}</div>
                        <div class="stat-label">Rate Limited</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{summary['success_rate']}</div>
                        <div class="stat-label">Success Rate</div>
                    </div>
                </div>
                
                <h2>Keys by Type</h2>
                <table>
                    <tr><th>Type</th><th>Count</th></tr>
                    {''.join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in summary['keys_by_type'].items())}
                </table>
                
                <h2>Skipped Items</h2>
                <table>
                    <tr><th>Reason</th><th>Count</th></tr>
                    {''.join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in summary['skipped_items'].items())}
                </table>
            </div>
        </body>
        </html>
        """
        
        # 保存HTML报告
        html_file = self.stats_file.replace('.json', '.html')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"📊 HTML report saved to: {html_file}")
        return html


# 创建全局实例
stats_reporter = StatsReporter()