#!/usr/bin/env python3
"""
Hajimi King 启动脚本
从项目根目录运行主程序
"""
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入并运行主程序
if __name__ == "__main__":
    from app.hajimi_king import main
    main()