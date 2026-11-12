"""행정망 Rocky 서버용 의견 받기 — 127.0.0.1:8081 에서만 듣고, nginx 가 /api/feedback 만 이리로 넘긴다.
(저장·권한·제한 규칙은 tools/feedback.py — 서버.bat 과 같은 코드)
systemd: cbweather-feedback.service (setup-rocky.sh 가 만든다)
"""
import http.server
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import feedback  # noqa: E402

PORT = 8081


class H(http.server.BaseHTTPRequestHandler):
    server_version = 'cbweather-feedback'
    sys_version = ''

    def log_message(self, *a):
        pass

    def _ip(self):
        # nginx 뒤에서만 돈다(127.0.0.1 에만 묶임) → nginx 가 넣어 준 실제 접속 주소를 믿는다
        return (self.headers.get('X-Real-IP') or self.client_address[0]).strip()

    def _go(self, method):
        if self.path.split('?', 1)[0] != '/api/feedback':
            return self._send(404, {'ok': False})
        body = b''
        if method == 'POST':
            try:
                n = int(self.headers.get('Content-Length') or 0)
            except ValueError:
                n = -1
            if n < 0 or n > feedback.MAX_BODY:
                return self._send(413, {'ok': False, 'err': '너무 깁니다'})
            body = self.rfile.read(n)
        code, out = feedback.handle(method, self._ip(), self.headers, body, self.path)
        self._send(code, out)

    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._go('GET')

    def do_POST(self):
        self._go('POST')


if __name__ == '__main__':
    http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
