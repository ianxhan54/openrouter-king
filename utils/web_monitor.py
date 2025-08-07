from flask import Flask, jsonify, render_template, request
from threading import Thread
import webbrowser
import os

from utils.db_manager import db_manager
from utils.stats_reporter import stats_reporter
from utils.token_manager import SmartTokenManager
from common.config import Config


class WebMonitor:
    """Web监控界面"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 5001):
        self.app = Flask(__name__, template_folder='templates')
        self.host = host
        self.port = port
        
        # 确保templates目录存在
        if not os.path.exists('templates'):
            os.makedirs('templates')
        
        self._setup_routes()
        self._create_templates()

    def _setup_routes(self):
        """设置路由"""
        self.app.route('/')(self.index)
        self.app.route('/api/stats')(self.api_stats)
        self.app.route('/api/valid_keys')(self.api_valid_keys)
        self.app.route('/api/token_status')(self.api_token_status)
    
    def _create_templates(self):
        """创建HTML模板文件"""
        index_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Hajimi King Monitor</title>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body>
            <div class="container-fluid mt-4">
                <h1 class="text-center">👑 Hajimi King Monitor</h1>
                
                <div class="row mt-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">Scan Statistics</div>
                            <div class="card-body">
                                <canvas id="statsChart"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">Token Status</div>
                            <div class="card-body">
                                <canvas id="tokenChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card mt-4">
                    <div class="card-header">Valid Keys</div>
                    <div class="card-body">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Key</th>
                                    <th>Type</th>
                                    <th>Source Repo</th>
                                    <th>Last Seen</th>
                                </tr>
                            </thead>
                            <tbody id="validKeysTable">
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <script>
                function updateCharts() {
                    // Stats Chart
                    fetch('/api/stats')
                        .then(response => response.json())
                        .then(data => {
                            const statsCtx = document.getElementById('statsChart').getContext('2d');
                            new Chart(statsCtx, {
                                type: 'bar',
                                data: {
                                    labels: ['Valid Keys', 'Invalid Keys', 'Rate Limited'],
                                    datasets: [{
                                        label: 'Count',
                                        data: [data.valid_keys, data.invalid_keys, data.rate_limited],
                                        backgroundColor: ['#28a745', '#dc3545', '#ffc107']
                                    }]
                                }
                            });
                        });
                        
                    // Token Chart
                    fetch('/api/token_status')
                        .then(response => response.json())
                        .then(data => {
                            const tokenCtx = document.getElementById('tokenChart').getContext('2d');
                            new Chart(tokenCtx, {
                                type: 'doughnut',
                                data: {
                                    labels: ['Available', 'Limited'],
                                    datasets: [{
                                        data: [data.available_tokens, data.limited_tokens],
                                        backgroundColor: ['#007bff', '#6c757d']
                                    }]
                                }
                            });
                        });
                }
                
                function updateValidKeys() {
                    fetch('/api/valid_keys')
                        .then(response => response.json())
                        .then(data => {
                            const tableBody = document.getElementById('validKeysTable');
                            tableBody.innerHTML = '';
                            data.forEach(key => {
                                tableBody.innerHTML += `
                                    <tr>
                                        <td>${key.key_value.substring(0,10)}...</td>
                                        <td>${key.key_type}</td>
                                        <td>${key.source_repo}</td>
                                        <td>${new Date(key.last_seen).toLocaleString()}</td>
                                    </tr>
                                `;
                            });
                        });
                }
                
                setInterval(() => {
                    updateCharts();
                    updateValidKeys();
                }, 5000);
                
                window.onload = () => {
                    updateCharts();
                    updateValidKeys();
                };
            </script>
        </body>
        </html>
        """
        with open("templates/index.html", "w") as f:
            f.write(index_html)

    def index(self):
        """主页"""
        return render_template('index.html')
        
    def api_stats(self):
        """获取统计数据API"""
        summary = stats_reporter.get_current_summary()
        return jsonify(summary)
        
    def api_valid_keys(self):
        """获取有效密钥API"""
        valid_keys = db_manager.get_valid_keys()
        return jsonify(valid_keys)
        
    def api_token_status(self):
        """获取Token状态API"""
        token_manager = SmartTokenManager(Config.GITHUB_TOKENS)
        status = token_manager.get_status_summary()
        return jsonify(status)

    def run_in_thread(self):
        """在线程中运行Web服务器"""
        def run_app():
            try:
                self.app.run(host=self.host, port=self.port, debug=False)
            except OSError:
                print(f"Port {self.port} is already in use. Please choose another port.")

        thread = Thread(target=run_app, daemon=True)
        thread.start()
        print(f"📈 Web Monitor running at http://{self.host}:{self.port}")
        
        # 自动打开浏览器
        webbrowser.open_new(f"http://{self.host}:{self.port}")


def start_web_monitor():
    """启动Web监控"""
    monitor = WebMonitor()
    monitor.run_in_thread()

# 示例使用
if __name__ == '__main__':
    start_web_monitor()
    
    # 保持主线程运行
    while True:
        try:
            # 这里可以放主程序的循环
            pass
        except KeyboardInterrupt:
            print("Shutting down...")
            break
