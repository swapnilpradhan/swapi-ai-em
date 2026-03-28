#!/usr/bin/env python3
"""
Simple OpenTelemetry Collector
Receives and displays traces when Jaeger/Docker aren't available
"""

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys

class SimpleCollectorHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.traces = []
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests - display collected traces"""
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = self._generate_dashboard_html()
            self.wfile.write(html.encode())
        elif self.path == '/traces':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            traces_data = {
                'traces': self.traces,
                'count': len(self.traces),
                'timestamp': time.time()
            }
            self.wfile.write(json.dumps(traces_data, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Handle POST requests - receive OpenTelemetry data"""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            # Parse the received data
            if self.path.startswith('/v1/traces'):
                self._handle_traces(post_data)
            elif self.path.startswith('/v1/metrics'):
                self._handle_metrics(post_data)
            else:
                print(f"Unknown endpoint: {self.path}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            
        except Exception as e:
            print(f"Error handling POST request: {e}")
            self.send_response(500)
            self.end_headers()
    
    def _handle_traces(self, data):
        """Handle incoming trace data"""
        try:
            # Simple trace parsing
            trace_data = {
                'timestamp': time.time(),
                'size': len(data),
                'preview': data[:200].decode('utf-8', errors='ignore') + '...' if len(data) > 200 else data.decode('utf-8', errors='ignore')
            }
            
            self.traces.append(trace_data)
            
            # Keep only last 100 traces
            if len(self.traces) > 100:
                self.traces = self.traces[-100:]
            
            print(f"📊 Received trace data ({len(data)} bytes)")
            
        except Exception as e:
            print(f"Error parsing traces: {e}")
    
    def _handle_metrics(self, data):
        """Handle incoming metrics data"""
        print(f"📈 Received metrics data ({len(data)} bytes)")
    
    def _generate_dashboard_html(self):
        """Generate a simple HTML dashboard"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Simple OpenTelemetry Collector</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ background: #e8f4fd; padding: 15px; border-radius: 5px; flex: 1; }}
        .traces {{ margin-top: 20px; }}
        .trace {{ background: #f9f9f9; padding: 10px; margin: 5px 0; border-left: 4px solid #007acc; }}
        .refresh {{ background: #007acc; color: white; padding: 10px 20px; border: none; border-radius: 3px; cursor: pointer; }}
        .refresh:hover {{ background: #005a9e; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Simple OpenTelemetry Collector</h1>
        <p>Receiving traces from Multi-Agent EM Platform</p>
        <button class="refresh" onclick="location.reload()">🔄 Refresh</button>
    </div>
    
    <div class="stats">
        <div class="stat">
            <h3>📊 Total Traces</h3>
            <h2>{len(self.traces)}</h2>
        </div>
        <div class="stat">
            <h3>🕐 Last Update</h3>
            <h2>{time.strftime('%H:%M:%S')}</h2>
        </div>
        <div class="stat">
            <h3>🔗 Status</h3>
            <h2>🟢 Active</h2>
        </div>
    </div>
    
    <div class="traces">
        <h2>📋 Recent Traces</h2>
        {self._generate_traces_html()}
    </div>
    
    <script>
        // Auto-refresh every 5 seconds
        setTimeout(() => location.reload(), 5000);
    </script>
</body>
</html>
"""
    
    def _generate_traces_html(self):
        """Generate HTML for recent traces"""
        if not self.traces:
            return "<p>No traces received yet. Make sure your application is sending traces.</p>"
        
        traces_html = ""
        for i, trace in enumerate(reversed(self.traces[-10:])):  # Show last 10
            timestamp = time.strftime('%H:%M:%S', time.localtime(trace['timestamp']))
            traces_html += f"""
            <div class="trace">
                <strong>Trace #{len(self.traces) - i}</strong> - {timestamp}<br>
                <small>Size: {trace['size']} bytes</small><br>
                <code>{trace['preview']}</code>
            </div>
            """
        
        return traces_html
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

def start_collector(port=16686):
    """Start the simple collector"""
    try:
        server = HTTPServer(('localhost', port), SimpleCollectorHandler)
        print(f"🚀 Simple OpenTelemetry Collector started!")
        print(f"📊 Dashboard: http://localhost:{port}")
        print(f"🔗 Receiving traces from Multi-Agent EM Platform")
        print(f"⏹️  Press Ctrl+C to stop")
        print("-" * 50)
        
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Collector stopped")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"❌ Port {port} is already in use")
            print(f"💡 Try: lsof -ti:{port} | xargs kill -9")
        else:
            print(f"❌ Error starting collector: {e}")
        sys.exit(1)

if __name__ == "__main__":
    port = 16686
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    start_collector(port)
