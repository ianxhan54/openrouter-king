import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as application

# 移除 app.run() 相关代码，因为 Vercel 会自动处理
if __name__ != "__main__":
    # 在 Vercel 环境中运行
    app = application
