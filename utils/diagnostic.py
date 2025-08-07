#!/usr/bin/env python3
"""
系统诊断工具
用于检查Hajimi King运行环境和配置状态
"""
import os
import sys
import requests
import importlib.util
from datetime import datetime
from typing import Dict, List, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.Logger import logger
from common.config import Config


class SystemDiagnostic:
    """系统诊断类"""
    
    def __init__(self):
        self.results = []
        
    def add_result(self, category: str, item: str, status: str, details: str = ""):
        """添加诊断结果"""
        self.results.append({
            "category": category,
            "item": item,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        
        # 实时输出结果
        status_symbol = "✅" if status == "OK" else "❌" if status == "ERROR" else "⚠️"
        logger.info(f"{status_symbol} {category} - {item}: {status}")
        if details:
            logger.debug(f"   详细信息: {details}")
    
    def check_python_environment(self):
        """检查Python环境"""
        logger.info("🐍 检查Python环境...")
        
        # Python版本
        python_version = sys.version
        self.add_result("Python环境", "Python版本", "OK", python_version)
        
        # 必要的模块检查
        required_modules = [
            "requests", "google.generativeai", "dotenv", "json", "os", "sys", "time", "datetime"
        ]
        
        for module_name in required_modules:
            try:
                if module_name == "google.generativeai":
                    import google.generativeai as genai
                    self.add_result("Python环境", f"模块 {module_name}", "OK", "已安装")
                else:
                    importlib.import_module(module_name)
                    self.add_result("Python环境", f"模块 {module_name}", "OK", "已安装")
            except ImportError as e:
                self.add_result("Python环境", f"模块 {module_name}", "ERROR", f"未安装: {str(e)}")
    
    def check_file_system(self):
        """检查文件系统"""
        logger.info("📁 检查文件系统...")
        
        # 检查关键目录
        required_dirs = ["data", "data/keys", "data/logs", "common", "utils", "app"]
        for dir_path in required_dirs:
            if os.path.exists(dir_path):
                self.add_result("文件系统", f"目录 {dir_path}", "OK", "存在")
            else:
                self.add_result("文件系统", f"目录 {dir_path}", "ERROR", "不存在")
        
        # 检查关键文件
        required_files = [
            "data/queries.txt", "common/config.py", "common/Logger.py", 
            "app/hajimi_king.py", "run.py"
        ]
        for file_path in required_files:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                self.add_result("文件系统", f"文件 {file_path}", "OK", f"大小: {file_size} bytes")
            else:
                self.add_result("文件系统", f"文件 {file_path}", "ERROR", "不存在")
        
        # 检查写入权限
        test_file = "data/diagnostic_test.tmp"
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            self.add_result("文件系统", "写入权限", "OK", "可以写入data目录")
        except Exception as e:
            self.add_result("文件系统", "写入权限", "ERROR", f"无法写入data目录: {str(e)}")
    
    def check_configuration(self):
        """检查配置"""
        logger.info("⚙️ 检查配置...")
        
        # GitHub tokens
        if Config.GITHUB_TOKENS:
            self.add_result("配置", "GitHub Tokens", "OK", f"配置了 {len(Config.GITHUB_TOKENS)} 个token")
        else:
            self.add_result("配置", "GitHub Tokens", "ERROR", "未配置GitHub tokens")
        
        # API密钥类型
        if Config.API_KEY_TYPE in ["gemini", "openrouter", "both"]:
            self.add_result("配置", "API密钥类型", "OK", Config.API_KEY_TYPE)
        else:
            self.add_result("配置", "API密钥类型", "ERROR", f"无效的API密钥类型: {Config.API_KEY_TYPE}")
        
        # 数据路径
        if os.path.exists(Config.DATA_PATH):
            self.add_result("配置", "数据路径", "OK", Config.DATA_PATH)
        else:
            self.add_result("配置", "数据路径", "ERROR", f"数据路径不存在: {Config.DATA_PATH}")
        
        # 查询文件
        if os.path.exists(Config.QUERIES_FILE):
            with open(Config.QUERIES_FILE, 'r', encoding='utf-8') as f:
                queries = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            self.add_result("配置", "查询文件", "OK", f"包含 {len(queries)} 个查询")
        else:
            self.add_result("配置", "查询文件", "ERROR", f"查询文件不存在: {Config.QUERIES_FILE}")
    
    def check_network_connectivity(self):
        """检查网络连接"""
        logger.info("🌐 检查网络连接...")
        
        # 测试基本网络连接
        test_urls = [
            ("GitHub API", "https://api.github.com"),
            ("Google", "https://www.google.com"),
        ]
        
        # 如果配置了OpenRouter，也测试OpenRouter
        if Config.API_KEY_TYPE in ["openrouter", "both"]:
            test_urls.append(("OpenRouter API", Config.OPENROUTER_VALIDATION_ENDPOINT))
        
        for name, url in test_urls:
            try:
                proxies = Config.get_requests_proxies()
                response = requests.get(url, timeout=10, proxies=proxies)
                if response.status_code == 200:
                    self.add_result("网络连接", name, "OK", f"状态码: {response.status_code}")
                else:
                    self.add_result("网络连接", name, "WARNING", f"状态码: {response.status_code}")
            except Exception as e:
                self.add_result("网络连接", name, "ERROR", f"连接失败: {str(e)}")
        
        # 测试代理设置
        if Config.PROXY:
            self.add_result("网络连接", "代理配置", "OK", Config.PROXY)
        else:
            self.add_result("网络连接", "代理配置", "OK", "未配置代理")
    
    def check_github_api_access(self):
        """检查GitHub API访问"""
        logger.info("🔑 检查GitHub API访问...")
        
        if not Config.GITHUB_TOKENS:
            self.add_result("GitHub API", "Token访问", "ERROR", "未配置GitHub tokens")
            return
        
        # 测试第一个token
        test_token = Config.GITHUB_TOKENS[0]
        headers = {
            "Authorization": f"token {test_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            proxies = Config.get_requests_proxies()
            response = requests.get("https://api.github.com/user", headers=headers, timeout=10, proxies=proxies)
            
            if response.status_code == 200:
                user_info = response.json()
                self.add_result("GitHub API", "Token验证", "OK", f"用户: {user_info.get('login', 'Unknown')}")
                
                # 检查剩余API调用次数
                rate_limit_remaining = response.headers.get('X-RateLimit-Remaining', 'Unknown')
                rate_limit_limit = response.headers.get('X-RateLimit-Limit', 'Unknown')
                self.add_result("GitHub API", "API限额", "OK", f"剩余: {rate_limit_remaining}/{rate_limit_limit}")
                
            elif response.status_code == 401:
                self.add_result("GitHub API", "Token验证", "ERROR", "Token无效或已过期")
            elif response.status_code == 403:
                self.add_result("GitHub API", "Token验证", "ERROR", "Token权限不足或API限额耗尽")
            else:
                self.add_result("GitHub API", "Token验证", "WARNING", f"意外状态码: {response.status_code}")
                
        except Exception as e:
            self.add_result("GitHub API", "Token验证", "ERROR", f"请求失败: {str(e)}")
    
    def run_full_diagnostic(self):
        """运行完整诊断"""
        logger.info("🔍 开始系统诊断...")
        logger.info("=" * 60)
        
        self.check_python_environment()
        self.check_file_system()
        self.check_configuration()
        self.check_network_connectivity()
        self.check_github_api_access()
        
        logger.info("=" * 60)
        logger.info("📊 诊断完成")
        
        # 统计结果
        total = len(self.results)
        ok_count = len([r for r in self.results if r["status"] == "OK"])
        error_count = len([r for r in self.results if r["status"] == "ERROR"])
        warning_count = len([r for r in self.results if r["status"] == "WARNING"])
        
        logger.info(f"📈 诊断结果统计:")
        logger.info(f"   ✅ 正常: {ok_count}")
        logger.info(f"   ⚠️ 警告: {warning_count}")
        logger.info(f"   ❌ 错误: {error_count}")
        logger.info(f"   📊 总计: {total}")
        
        if error_count > 0:
            logger.error("⚠️ 发现系统问题，请检查上述错误项")
            return False
        elif warning_count > 0:
            logger.warning("⚠️ 系统基本正常，但有一些警告项")
            return True
        else:
            logger.info("✅ 系统状态良好")
            return True


def main():
    """主函数"""
    diagnostic = SystemDiagnostic()
    return diagnostic.run_full_diagnostic()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
