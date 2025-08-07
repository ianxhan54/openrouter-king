import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

from common.Logger import logger
from common.config import Config


@dataclass
class Checkpoint:
    last_scan_time: Optional[str] = None
    scanned_shas: Set[str] = field(default_factory=set)
    processed_queries: Set[str] = field(default_factory=set)
    last_full_scan_time: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，但不包含scanned_shas（单独存储）"""
        return {
            "last_scan_time": self.last_scan_time,
            "processed_queries": list(self.processed_queries),
            "last_full_scan_time": self.last_full_scan_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """从字典创建Checkpoint对象，scanned_shas需要单独加载"""
        return cls(
            last_scan_time=data.get("last_scan_time"),
            scanned_shas=set(),  # 将通过FileManager单独加载
            processed_queries=set(data.get("processed_queries", [])),
            last_full_scan_time=data.get("last_full_scan_time")
        )
    
    def add_scanned_sha(self, sha: str) -> None:
        if sha:
            self.scanned_shas.add(sha)
    
    def add_processed_query(self, query: str) -> None:
        if query:
            self.processed_queries.add(query)
    
    def update_scan_time(self) -> None:
        self.last_scan_time = datetime.utcnow().isoformat()
    
    def should_force_full_scan(self) -> bool:
        """检查是否应该强制进行全量扫描"""
        from common.config import Config
        
        # 检查配置强制全量扫描
        if Config.FORCE_FULL_SCAN:
            return True
        
        # 检查扫描模式
        if Config.SCAN_MODE == "full":
            return True
        
        # 检查智能扫描模式下的时间间隔
        if Config.SCAN_MODE == "smart" and self.last_full_scan_time:
            try:
                last_full_scan = datetime.fromisoformat(self.last_full_scan_time)
                hours_since_full_scan = (datetime.utcnow() - last_full_scan).total_seconds() / 3600
                if hours_since_full_scan >= Config.FULL_SCAN_INTERVAL_HOURS:
                    return True
            except Exception:
                return True  # 如果解析时间失败，进行全量扫描
        
        return False
    
    def reset_for_full_scan(self) -> None:
        """重置检查点以进行全量扫描"""
        self.processed_queries.clear()
        self.scanned_shas.clear()
        self.last_full_scan_time = datetime.utcnow().isoformat()
        logger.info("🔄 重置检查点以进行全量扫描")
    
    def update_full_scan_time(self) -> None:
        """更新最后全量扫描时间"""
        self.last_full_scan_time = datetime.utcnow().isoformat()


class FileManager:
    """文件管理器：负责所有文件相关操作"""
    
    def __init__(self, data_dir: str):
        """
        初始化FileManager并完成所有必要的设置
        
        Args:
            data_dir: 数据目录路径
        """
        logger.info("🔧 Initializing FileManager...")
        
        # 1. 基础路径设置
        self.data_dir = data_dir
        self.checkpoint_file = os.path.join(data_dir, "checkpoint.json")
        self.scanned_shas_file = os.path.join(data_dir, Config.SCANNED_SHAS_FILE)
        
        # 2. 动态文件名
        self._detail_log_filename: Optional[str] = None
        self._keys_valid_filename: Optional[str] = None
        self._rate_limited_filename: Optional[str] = None
        self._rate_limited_detail_filename: Optional[str] = None
        
        # 3. 创建数据目录
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            logger.info(f"Created data directory: {self.data_dir}")
        else:
            logger.info(f"Data directory exists: {self.data_dir}")
        
        # 4. 加载搜索查询
        try:
            self._search_queries = self.load_search_queries(Config.QUERIES_FILE)
            logger.info(f"✅ Loaded {len(self._search_queries)} search queries")
        except Exception as e:
            logger.error(f"❌ Failed to load search queries: {e}")
            self._search_queries = []
        
        # 5. 初始化文件名
        start_time = datetime.now()
        detail_prefix = Config.VALID_KEY_DETAIL_PREFIX.rstrip('_')
        self._detail_log_filename = os.path.join(
            self.data_dir, 
            f"{detail_prefix}_{start_time.strftime('%Y%m%d')}.log"
        )
        
        # 详细信息文件（包含余额和限额）
        self._keys_detail_info_filename = os.path.join(
            self.data_dir,
            f"keys_detail_info_{start_time.strftime('%Y%m%d')}.json"
        )
        
        self._keys_valid_filename = os.path.join(
            self.data_dir, 
            f"{Config.VALID_KEY_PREFIX}{start_time.strftime('%Y%m%d_%H')}.txt"
        )
        
        self._rate_limited_filename = os.path.join(
            self.data_dir, 
            f"{Config.RATE_LIMITED_KEY_PREFIX}{start_time.strftime('%Y%m%d_%H')}.txt"
        )
        
        self._rate_limited_detail_filename = os.path.join(
            self.data_dir, 
            f"{Config.RATE_LIMITED_KEY_DETAIL_PREFIX}{start_time.strftime('%Y%m%d')}.log"
        )
        
        # 创建文件（如果不存在），先确保父目录存在
        for filename in [self._detail_log_filename, self._keys_valid_filename, self._rate_limited_filename, self._rate_limited_detail_filename]:
            if not os.path.exists(filename):
                # 确保父目录存在（类似 mkdir -p）
                parent_dir = os.path.dirname(filename)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                
                with open(filename, 'a', encoding='utf-8') as f:
                    f.write("")
        
        # 创建详细信息JSON文件
        if not os.path.exists(self._keys_detail_info_filename):
            parent_dir = os.path.dirname(self._keys_detail_info_filename)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(self._keys_detail_info_filename, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        
        logger.info(f"Initialized detail log filename: {self._detail_log_filename}")
        logger.info(f"Initialized keys valid filename: {self._keys_valid_filename}")
        logger.info(f"Initialized rate limited filename: {self._rate_limited_filename}")
        logger.info(f"Initialized rate limited detail filename: {self._rate_limited_detail_filename}")
        
        logger.info("✅ FileManager initialization complete")
    
    def check(self) -> bool:
        """
        检查FileManager是否正确初始化，所有必要文件是否就绪
        
        Returns:
            bool: 检查是否通过
        """
        logger.info("🔍 Checking FileManager status...")
        
        errors = []
        
        # 检查数据目录
        if not os.path.exists(self.data_dir):
            errors.append(f"Data directory not found: {self.data_dir}")
            logger.error(f"❌ Data directory: {self.data_dir}")
        else:
            logger.info(f"✅ Data directory: {self.data_dir}")
        
        # 检查文件名是否初始化
        files_to_check = [
            (self._detail_log_filename, "Detail log file"),
            (self._keys_valid_filename, "Valid keys file"),
            (self._rate_limited_filename, "Rate limited file"),
            (self._rate_limited_detail_filename, "Rate limited detail file")
        ]
        
        for filename, description in files_to_check:
            if not filename:
                errors.append(f"{description} not initialized")
                logger.error(f"❌ {description}: Not initialized")
            elif not os.path.exists(filename):
                errors.append(f"{description} not found: {filename}")
                logger.error(f"❌ {description}: {filename}")
            else:
                logger.info(f"✅ {description}: {filename}")
        
        # 检查scanned_shas文件
        if os.path.exists(self.scanned_shas_file):
            logger.info(f"✅ Scanned SHAs file: {self.scanned_shas_file}")
        else:
            logger.info(f"📝 Scanned SHAs file will be created: {self.scanned_shas_file}")
        
        # 检查checkpoint文件
        if os.path.exists(self.checkpoint_file):
            logger.info(f"✅ Checkpoint file: {self.checkpoint_file}")
        else:
            logger.info(f"📝 Checkpoint file will be created: {self.checkpoint_file}")
        
        # 检查搜索查询
        if not hasattr(self, '_search_queries') or not self._search_queries:
            errors.append("Search queries not loaded or empty")
            logger.error("❌ Search queries: Not loaded or empty")
        else:
            logger.info(f"✅ Search queries: {len(self._search_queries)} loaded")
        
        if errors:
            logger.error("❌ FileManager check failed:")
            for error in errors:
                logger.error(f"   - {error}")
            return False
        
        logger.info("✅ FileManager status check passed")
        return True
    
    # ================================
    # 加载方法
    # ================================
    
    def load_checkpoint(self) -> Checkpoint:
        """加载checkpoint数据"""
        checkpoint = Checkpoint()
        
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    checkpoint = Checkpoint.from_dict(data)
            except Exception as e:
                logger.warning(f"Cannot read {self.checkpoint_file}: {e}. Will create new checkpoint.")
        else:
            logger.warning(f"{self.checkpoint_file} not found. Will create new checkpoint.")
            self.save_checkpoint(checkpoint)

        # 从单独文件加载scanned_shas
        checkpoint.scanned_shas = self.load_scanned_shas()
        
        return checkpoint
    
    def load_scanned_shas(self) -> Set[str]:
        """从文件中加载已扫描的SHA列表"""
        scanned_shas = set()
        
        if os.path.isfile(self.scanned_shas_file):
            try:
                with open(self.scanned_shas_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            scanned_shas.add(line)
                logger.info(f"Loaded {len(scanned_shas)} scanned SHAs from {self.scanned_shas_file}")
            except Exception as e:
                logger.error(f"Failed to read {self.scanned_shas_file}: {e}")
                logger.info("Using empty scanned SHAs set")
        else:
            logger.info(f"Scanned SHAs file not found: {self.scanned_shas_file}")
            logger.info("Starting with empty scanned SHAs set")
        
        return scanned_shas
    
    def load_search_queries(self, queries_file_path: str) -> List[str]:
        """从文件中加载搜索查询列表"""
        queries = []
        full_path = os.path.join(self.data_dir, queries_file_path)
        
        if not os.path.exists(full_path):
            self._create_default_queries_file(full_path)
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        queries.append(line)
            logger.info(f"Loaded {len(queries)} search queries from {full_path}")
        except Exception as e:
            logger.error(f"Failed to read {full_path}: {e}")
            logger.info("Using empty query list")
        
        return queries
    
    # ================================
    # 保存方法
    # ================================
    
    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """保存checkpoint数据"""
        # 1. 保存scanned_shas到单独文件
        self.save_scanned_shas(checkpoint.scanned_shas)
        
        # 2. 保存其他数据到checkpoint.json
        try:
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save {self.checkpoint_file}: {e}")
    
    def save_scanned_shas(self, scanned_shas: Set[str]) -> None:
        """保存已扫描的SHA列表到文件"""
        try:
            with open(self.scanned_shas_file, "w", encoding="utf-8") as f:
                f.write("# 已扫描的文件SHA列表\n")
                f.write("# 每行一个SHA，用于避免重复扫描\n")
                f.write(f"# 最后更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n")
                for sha in sorted(scanned_shas):
                    f.write(f"{sha}\n")
            logger.info(f"Saved {len(scanned_shas)} scanned SHAs to {self.scanned_shas_file}")
        except Exception as e:
            logger.error(f"Failed to save scanned SHAs to {self.scanned_shas_file}: {e}")
    
    def save_valid_keys(self, repo_name: str, file_path: str, file_url: str, valid_keys: List[str]) -> None:
        """保存有效的API密钥"""
        if not valid_keys or not self._detail_log_filename:
            return
        
        # 保存到详细日志文件
        with open(self._detail_log_filename, "a", encoding="utf-8") as f:
            f.write(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"URL: {file_url}\n")
            for key in valid_keys:
                f.write(f"KEY: {key}\n")
            f.write("-" * 80 + "\n")
        
        # 保存到keys_valid文件
        if self._keys_valid_filename:
            with open(self._keys_valid_filename, "a", encoding="utf-8") as f:
                for key in valid_keys:
                    f.write(f"{key}\n")

    def save_rate_limited_keys(self, repo_name: str, file_path: str, file_url: str, rate_limited_keys: List[str]) -> None:
        """保存被限流的API密钥"""
        if not rate_limited_keys:
            return
        
        # 保存详细信息到详细日志文件（新格式）
        if self._rate_limited_detail_filename:
            with open(self._rate_limited_detail_filename, "a", encoding="utf-8") as f:
                f.write(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"URL: {file_url}\n")
                for key in rate_limited_keys:
                    f.write(f"{key}\n")
                f.write("-" * 80 + "\n")
        
        # 保存纯密钥到原有文件（只保存key）
        if self._rate_limited_filename:
            with open(self._rate_limited_filename, "a", encoding="utf-8") as f:
                for key in rate_limited_keys:
                    f.write(f"{key}\n")
    
    def save_keys_with_details(self, repo_name: str, file_path: str, file_url: str, keys_with_info: List[Dict[str, Any]]) -> None:
        """保存带有详细信息的API密钥（包含余额和限额）"""
        if not keys_with_info:
            return
            
        try:
            # 读取现有数据
            existing_data = []
            if os.path.exists(self._keys_detail_info_filename):
                with open(self._keys_detail_info_filename, 'r', encoding='utf-8') as f:
                    try:
                        existing_data = json.load(f)
                    except json.JSONDecodeError:
                        existing_data = []
            
            # 添加新数据
            for key_info in keys_with_info:
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "repo_name": repo_name,
                    "file_path": file_path,
                    "file_url": file_url,
                    "key": key_info["key"],
                    "key_type": key_info["type"],
                    "details": key_info["info"]
                }
                existing_data.append(entry)
            
            # 保存更新后的数据
            with open(self._keys_detail_info_filename, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"💾 Saved {len(keys_with_info)} key(s) with detailed info to {self._keys_detail_info_filename}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save keys with details: {e}")
    
    def append_scanned_sha(self, sha: str) -> None:
        """追加单个SHA到文件中"""
        if not sha:
            return
            
        try:
            with open(self.scanned_shas_file, "a", encoding="utf-8") as f:
                f.write(f"{sha}\n")
        except Exception as e:
            logger.error(f"Failed to append SHA {sha} to {self.scanned_shas_file}: {e}")
    
    # ================================
    # 更新方法
    # ================================
    
    def update_dynamic_filenames(self) -> None:
        """更新时间相关的文件名（例如每小时更新）"""
        current_time = datetime.now()
        current_date_str = current_time.strftime('%Y%m%d')
        current_hour_str = current_time.strftime('%H')
        
        # 更新keys_valid文件名
        if self._keys_valid_filename:
            basename = os.path.basename(self._keys_valid_filename)
            if self._need_filename_update(basename, Config.VALID_KEY_PREFIX, current_date_str, current_hour_str):
                old_filename = self._keys_valid_filename
                self._keys_valid_filename = os.path.join(
                    self.data_dir, 
                    f"{Config.VALID_KEY_PREFIX}{current_time.strftime('%Y%m%d_%H')}.txt"
                )
                logger.info(f"Updated keys-valid filename: {old_filename} -> {self._keys_valid_filename}")
        
        # 更新rate_limited文件名
        if self._rate_limited_filename:
            basename = os.path.basename(self._rate_limited_filename)
            if self._need_filename_update(basename, Config.RATE_LIMITED_KEY_PREFIX, current_date_str, current_hour_str):
                old_filename = self._rate_limited_filename
                self._rate_limited_filename = os.path.join(
                    self.data_dir, 
                    f"{Config.RATE_LIMITED_KEY_PREFIX}{current_time.strftime('%Y%m%d_%H')}.txt"
                )
                logger.info(f"Updated rate-limited filename: {old_filename} -> {self._rate_limited_filename}")
        
        # 更新rate_limited_detail文件名（按日期分割）
        if self._rate_limited_detail_filename:
            basename = os.path.basename(self._rate_limited_detail_filename)
            if self._need_daily_filename_update(basename, Config.RATE_LIMITED_KEY_DETAIL_PREFIX, current_date_str):
                old_filename = self._rate_limited_detail_filename
                self._rate_limited_detail_filename = os.path.join(
                    self.data_dir, 
                    f"{Config.RATE_LIMITED_KEY_DETAIL_PREFIX}{current_date_str}.log"
                )
                logger.info(f"Updated rate-limited detail filename: {old_filename} -> {self._rate_limited_detail_filename}")
    
    # ================================
    # 属性访问器
    # ================================
    
    @property
    def detail_log_filename(self) -> Optional[str]:
        return self._detail_log_filename
    
    @property
    def keys_valid_filename(self) -> Optional[str]:
        return self._keys_valid_filename
    
    @property
    def rate_limited_filename(self) -> Optional[str]:
        return self._rate_limited_filename
    
    @property
    def rate_limited_detail_filename(self) -> Optional[str]:
        return self._rate_limited_detail_filename
    
    # 向后兼容的属性名
    @property
    def main_log_filename(self) -> Optional[str]:
        return self._detail_log_filename
    
    @property
    def keys_only_filename(self) -> Optional[str]:
        return self._keys_valid_filename
    
    def get_search_queries(self) -> List[str]:
        """获取搜索查询列表"""
        return getattr(self, '_search_queries', [])
    
    # ================================
    # 私有辅助方法
    # ================================
    
    def _create_default_queries_file(self, queries_file: str) -> None:
        """创建默认的查询文件"""
        try:
            os.makedirs(os.path.dirname(queries_file), exist_ok=True)
            with open(queries_file, "w", encoding="utf-8") as f:
                f.write("# GitHub搜索查询配置文件\n")
                f.write("# 每行一个查询语句，支持GitHub搜索语法\n")
                f.write("# 以#开头的行为注释，空行会被忽略\n")
                f.write("\n")
                f.write("# 基础API密钥搜索\n")
                f.write("AIzaSy in:file\n")
            logger.info(f"Created default queries file: {queries_file}")
        except Exception as e:
            logger.error(f"Failed to create default queries file {queries_file}: {e}")
    
    def _need_filename_update(self, basename: str, prefix: str, current_date: str, current_hour: str) -> bool:
        """检查是否需要更新文件名"""
        try:
            time_part = basename[len(prefix):].replace('.txt', '')
            if '_' in time_part:
                filename_date, filename_hour = time_part.split('_', 1)
                return filename_date != current_date or filename_hour != current_hour
        except (IndexError, ValueError):
            pass
        return True
    
    def _need_daily_filename_update(self, basename: str, prefix: str, current_date: str) -> bool:
        """检查是否需要更新按日期分割的文件名"""
        try:
            time_part = basename[len(prefix):].replace('.log', '')
            return time_part != current_date
        except (IndexError, ValueError):
            pass
        return True
