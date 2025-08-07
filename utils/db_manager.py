import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import asdict

from common.config import Config
from utils.secure_logger import secure_logger


class DatabaseManager:
    """数据库管理器，用于存储和管理扫描数据"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        if db_path is None:
            db_path = os.path.join(Config.DATA_PATH, "hajimi_king.db")
        
        self.db_path = db_path
        self.conn = None
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._create_tables()
            secure_logger.info(f"💾 Database connected: {db_path}")
        except sqlite3.Error as e:
            secure_logger.error(f"❌ Database error: {e}")
    
    def _create_tables(self):
        """创建数据库表"""
        if not self.conn:
            return
        
        cursor = self.conn.cursor()
        
        # 密钥表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_value TEXT NOT NULL UNIQUE,
            key_type TEXT NOT NULL,
            is_valid BOOLEAN,
            rate_limited BOOLEAN,
            details TEXT,
            source_repo TEXT,
            source_path TEXT,
            source_url TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP
        )
        """)
        
        # 已扫描文件表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scanned_files (
            sha TEXT PRIMARY KEY,
            repo_name TEXT,
            file_path TEXT,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 扫描会话表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            total_queries INTEGER,
            processed_items INTEGER,
            valid_keys_found INTEGER,
            summary TEXT
        )
        """)
        
        self.conn.commit()
    
    def add_or_update_key(self, key_data: Dict[str, Any]):
        """
        添加或更新密钥信息
        
        Args:
            key_data: 包含密钥信息的字典
        """
        if not self.conn:
            return
        
        cursor = self.conn.cursor()
        
        query = """
        INSERT INTO keys (key_value, key_type, is_valid, rate_limited, details, source_repo, source_path, source_url, last_seen)
        VALUES (:key_value, :key_type, :is_valid, :rate_limited, :details, :source_repo, :source_path, :source_url, :last_seen)
        ON CONFLICT(key_value) DO UPDATE SET
            is_valid = excluded.is_valid,
            rate_limited = excluded.rate_limited,
            details = excluded.details,
            last_seen = excluded.last_seen
        """
        
        try:
            cursor.execute(query, {
                "key_value": key_data["key"],
                "key_type": key_data["key_type"],
                "is_valid": key_data.get("is_valid", False),
                "rate_limited": key_data.get("rate_limited", False),
                "details": json.dumps(key_data.get("details")),
                "source_repo": key_data.get("source_repo"),
                "source_path": key_data.get("source_path"),
                "source_url": key_data.get("source_url"),
                "last_seen": datetime.now()
            })
            self.conn.commit()
        except sqlite3.Error as e:
            secure_logger.error(f"❌ Failed to add/update key: {e}")
    
    def add_scanned_sha(self, sha: str, repo_name: str, file_path: str):
        """添加已扫描的文件SHA"""
        if not self.conn:
            return
        
        query = "INSERT OR IGNORE INTO scanned_files (sha, repo_name, file_path) VALUES (?, ?, ?)"
        
        try:
            self.conn.execute(query, (sha, repo_name, file_path))
            self.conn.commit()
        except sqlite3.Error as e:
            secure_logger.warning(f"⚠️ Failed to add scanned SHA: {e}")
    
    def is_sha_scanned(self, sha: str) -> bool:
        """检查SHA是否已扫描"""
        if not self.conn:
            return False
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM scanned_files WHERE sha = ?", (sha,))
        return cursor.fetchone() is not None
    
    def start_session(self) -> int:
        """开始新的扫描会话"""
        if not self.conn:
            return -1
        
        query = "INSERT INTO scan_sessions (start_time) VALUES (?)"
        cursor = self.conn.cursor()
        cursor.execute(query, (datetime.now(),))
        self.conn.commit()
        return cursor.lastrowid
    
    def end_session(self, session_id: int, stats: 'ScanStatistics'):
        """结束扫描会话"""
        if not self.conn:
            return
        
        query = """
        UPDATE scan_sessions 
        SET end_time = ?, total_queries = ?, processed_items = ?, valid_keys_found = ?, summary = ?
        WHERE id = ?
        """
        
        try:
            self.conn.execute(query, (
                datetime.now(),
                stats.total_queries,
                stats.total_items_scanned,
                stats.valid_keys,
                json.dumps(stats.to_dict()),
                session_id
            ))
            self.conn.commit()
        except sqlite3.Error as e:
            secure_logger.error(f"❌ Failed to end session: {e}")
    
    def get_valid_keys(self) -> List[Dict]:
        """获取所有有效的密钥"""
        if not self.conn:
            return []
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM keys WHERE is_valid = 1")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_stats_summary(self) -> Dict:
        """获取数据库统计摘要"""
        if not self.conn:
            return {}
        
        cursor = self.conn.cursor()
        
        try:
            total_keys = cursor.execute("SELECT COUNT(*) FROM keys").fetchone()[0]
            valid_keys = cursor.execute("SELECT COUNT(*) FROM keys WHERE is_valid = 1").fetchone()[0]
            rate_limited_keys = cursor.execute("SELECT COUNT(*) FROM keys WHERE rate_limited = 1").fetchone()[0]
            scanned_files = cursor.execute("SELECT COUNT(*) FROM scanned_files").fetchone()[0]
            
            return {
                "total_keys": total_keys,
                "valid_keys": valid_keys,
                "rate_limited_keys": rate_limited_keys,
                "scanned_files": scanned_files
            }
        except sqlite3.Error:
            return {}
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            secure_logger.info("💾 Database connection closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# 创建全局实例
db_manager = DatabaseManager()