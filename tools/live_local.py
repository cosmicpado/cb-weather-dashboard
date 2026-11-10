"""로컬에서 운영 데이터를 계속 받아 보기 — API 를 부르지 않고, 운영 서버가 5분마다 main 에 올리는 데이터를 가져온다.

    python tools/live_local.py              # 데이터 받기 + 웹서버 http://localhost:8765/지도.html
    python tools/live_local.py --port 8000  # 웹서버 포트 바꾸기
    python tools/live_local.py --no-serve   # 데이터만 받기(화면은 이미 띄운 다른 서버로 볼 때)
    python tools/live_local.py --lan        # 다른 PC 에서도 접속(내부망 배포) — http://<이 PC IP>:8000/
    python tools/live_local.py --collect    # 운영 서버를 거치지 않고 이 PC 가 직접 API 로 수집(5분마다)

- 1분마다 git fetch 로 origin/main 의 data.js · data-cctv.js · images/*.png 를 작업 폴더에 덮어쓴다
  (지금 브랜치·커밋·스테이지는 건드리지 않는다. 바뀐 데이터 파일은 커밋하지 말 것).
- --collect 면 대신 update_data.py --no-push 를 돌린다(.env 의 API 키 필요, GitHub 에는 올리지 않는다).
- 같은 프로세스가 작업 폴더를 웹서버로 띄운다. 화면은 60초마다 data.js 를 다시 읽어 자동 갱신된다.
- 내 코드(지도.html 등)는 그대로라, 고치는 중인 화면을 실시간 운영 데이터로 볼 수 있다.
"""
import argparse
import functools
import http.server
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import feedback  # noqa: E402  — 의견 받기(/api/feedback)
FILES = ['data.js', 'data-cctv.js']
SERVE_EXT = {'.html', '.js', '.css', '.json', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.woff', '.woff2'}
# Cloudflare _headers 와 같게 둔다. CSP 를 스크립트 출처까지 조이지 않는 이유는 _headers 주석 참고.
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'SAMEORIGIN',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Content-Security-Policy': "frame-ancestors 'self'; object-src 'none'; base-uri 'self'",
}


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True)


def sync():
    if git('fetch', '-q', 'origin', 'main').returncode != 0:
        return '가져오기 실패(네트워크?) — 다음 회차에 다시'
    names = FILES + [n for n in git('ls-tree', '--name-only', 'origin/main', 'images/').stdout.decode().split() if n.endswith('.png')]
    changed = []
    for name in names:
        blob = git('show', f'origin/main:{name}')
        if blob.returncode != 0:
            continue
        path = ROOT / name
        if not path.exists() or path.read_bytes() != blob.stdout:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob.stdout)
            changed.append(name)
    stamp = git('log', '-1', '--format=%s', 'origin/main').stdout.decode('utf-8', 'replace').strip()
    return (f'갱신 {len(changed)}개' if changed else '변화 없음') + f' · 서버 최신 커밋: {stamp}'


def collect():
    t0 = time.time()
    r = subprocess.run([sys.executable, str(ROOT / 'tools' / 'update_data.py'), '--no-push'], cwd=ROOT,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
        return '수집 실패 — ' + ' / '.join(tail)
    return f'직접 수집 완료 ({time.time() - t0:.0f}초)'


def radar():
    r = subprocess.run([sys.executable, str(ROOT / 'tools' / 'update_data.py'), '--radar-only'], cwd=ROOT,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = (r.stdout or r.stderr).strip().splitlines()
    return (out[-1] if out else '레이더 결과 없음') if r.returncode == 0 else '레이더 실패 — ' + ' / '.join(out[-2:])


def loop(every, job=sync):
    while True:
        print(f'[{datetime.now():%H:%M:%S}] {job()}', flush=True)
        time.sleep(every)


def allowed_path(raw):
    """화면에 필요한 파일만 내준다 — 운영 nginx(tools/server/setup-*.sh)와 같은 규칙.
    ⚠ 작업 폴더에는 .env(API 키)·.git·tools 가 함께 있다. --lan 이면 내부망 어디서나 받아 갈 수 있으므로
      빼면 안 된다(2026-11-06 점검에서 /.env 가 그대로 내려받아지는 것을 발견).
    Windows 는 '.env.'·'tools '·'.env::$DATA' 처럼 끝 글자가 달라도 같은 파일로 열어서 그런 모양도 막는다."""
    path = unquote(raw.split('?', 1)[0].split('#', 1)[0])      # 표준 처리기(translate_path)와 같은 방식으로 자른다
    if path == '/':
        return True                                            # → index.html → 지도.html
    if path.endswith('/') or any(c in path for c in '\\:\0'):
        return False                                           # 폴더 목록 · 역슬래시 경로 · 대체 스트림
    parts = [p for p in path.split('/') if p]
    if not parts or parts[-1] != parts[-1].rstrip(' .'):
        return False
    for p in parts:
        if p.startswith('.') or p.rstrip(' .').lower() == 'tools':
            return False
    return os.path.splitext(parts[-1])[1].lower() in SERVE_EXT


class Quiet(http.server.SimpleHTTPRequestHandler):
    # Windows 는 레지스트리 때문에 .js 종류가 text/plain 으로 잡힐 수 있다. nosniff 면 그런 스크립트는 막히므로 못 박는다.
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
                      '.json': 'application/json', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.woff': 'font/woff', '.woff2': 'font/woff2'}

    def log_message(self, *x):                 # 요청 로그는 끈다(가져오기 기록만 보이게)
        pass

    def _feedback(self, method):
        """화면의 💬 의견 보내기 · 의견.html — 규칙은 tools/feedback.py(Rocky 서버와 같은 코드)."""
        body = b''
        if method == 'POST':
            try:
                n = int(self.headers.get('Content-Length') or 0)
            except ValueError:
                n = -1
            if n < 0 or n > feedback.MAX_BODY:
                code, out = 413, {'ok': False, 'err': '너무 깁니다'}
            else:
                body = self.rfile.read(n)
                code, out = feedback.handle(method, self.client_address[0], self.headers, body)
        else:
            code, out = feedback.handle(method, self.client_address[0], self.headers)
        b = json.dumps(out, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.split('?', 1)[0] == '/api/feedback':
            return self._feedback('GET')
        return super().do_GET()

    def do_POST(self):
        if self.path.split('?', 1)[0] == '/api/feedback':
            return self._feedback('POST')
        self.send_error(405)

    def send_head(self):                       # GET·HEAD 가 모두 여기를 지난다
        if not allowed_path(self.path):
            self.send_error(404)
            return None
        return super().send_head()

    def end_headers(self):                     # 운영(nginx·Cloudflare)과 같게 — 브라우저가 옛 data.js 를 다시 쓰지 않게
        self.send_header('Cache-Control', 'no-cache')
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        super().end_headers()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--every', type=int, help='가져오기 간격(초, 기본 60 · --collect 면 300)')
    ap.add_argument('--collect', action='store_true', help='운영 서버 데이터 대신 이 PC 가 직접 API 로 수집한다')
    ap.add_argument('--no-serve', action='store_true', help='데이터만 받아 오고 웹서버는 띄우지 않는다(이미 다른 서버를 쓸 때)')
    ap.add_argument('--lan', action='store_true', help='다른 PC 에서도 접속하게 연다(기본은 이 PC 만)')
    a = ap.parse_args()
    job = collect if a.collect else sync
    every = a.every or (300 if a.collect else 60)
    if a.collect:
        print('직접 수집 모드 — 5분마다 API 를 부릅니다(한 회차 1~2분). GitHub 에는 올리지 않습니다.', flush=True)
    if a.no_serve:
        try:
            loop(every, job)
        except KeyboardInterrupt:
            sys.exit(0)
    threading.Thread(target=loop, args=(every, job), daemon=True).start()
    if a.collect:
        # 레이더만 1분마다 따로 — 5분 전체 수집을 기다리면 화면이 10분 넘게 늦는다(상황실 레이더 칸이 frames.json 을 1분마다 읽는다)
        threading.Thread(target=loop, args=(60, radar), daemon=True).start()
    handler = functools.partial(Quiet, directory=str(ROOT))
    class Server(http.server.ThreadingHTTPServer):
        allow_reuse_address = False                # Windows 는 켜 두면 이미 쓰는 포트에도 겹쳐 붙는다
    try:
        srv = Server(('0.0.0.0' if a.lan else '127.0.0.1', a.port), handler)
    except OSError:
        if a.lan:
            # 내부망 서버는 다른 PC 접속이 목적이라, 다른 프로그램이 포트를 잡고 있으면 조용히 물러나면 안 된다
            print(f'\n  ✗ {a.port} 포트를 다른 프로그램이 이미 쓰고 있어 내부망 서버를 열 수 없습니다.', flush=True)
            print('    예전에 켜 둔 서버 창(서버시작.bat 등)이나 다른 서버.bat 창을 닫고 다시 실행하세요.', flush=True)
            print(f'    무엇이 쓰는지 보기: netstat -ano | findstr :{a.port}\n', flush=True)
            sys.exit(1)
        # 이미 그 포트로 띄운 서버가 있으면(같은 폴더를 보고 있을 테니) 데이터만 받는다
        print(f'{a.port} 포트는 이미 사용 중 — 데이터만 받습니다. 화면은 쓰던 서버로 보세요. (끄기: Ctrl+C)', flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            sys.exit(0)
    print(f'열기: http://localhost:{a.port}/지도.html   (끄기: 이 창 닫기 또는 Ctrl+C)', flush=True)
    if a.lan:
        import socket
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            ip = '<이 PC IP>'
        print(f'다른 PC 에서: http://{ip}:{a.port}/지도.html', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()
