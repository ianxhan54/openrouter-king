import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入原始的 Flask app
from app import app

# Vercel 的处理函数
def handler(request, response):
    # 这是 Vercel 的 WSGI 适配器
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    from werkzeug.wrappers import Response
    
    # 创建一个简单的根应用
    def application(environ, start_response):
        response = Response('API is running!')
        return response(environ, start_response)
    
    # 返回 Flask app
    return app

# 导出 app 给 Vercel
app = app
