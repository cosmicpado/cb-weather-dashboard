"""로컬에서 운영 데이터를 계속 받아 보기 — API 를 부르지 않고, 운영 서버가 5분마다 main 에 올리는 데이터를 가져온다.

    python tools/live_local.py              # 데이터 받기 + 웹서버 http://localhost:8765/지도.html
    python tools/live_local.py --port 8000  # 웹서버 포트 바꾸기
    python tools/live_local.py --no-serve   # 데이터만 받기(화면은 이미 띄운 다른 서버로 볼 때)

- 1분마다 git fetch 로 origin/main 의 data.js · data-cctv.js · images/*.png 를 작업 폴더에 덮어쓴다
  (지금 브랜치·커밋·스테이지는 건드리지 않는다. 바뀐 데이터 파일은 커밋하지 말 것).
- 같은 프로세스가 작업 폴더를 웹서버로 띄운다. 화면은 60초마다 data.js 를 다시 읽어 자동 갱신된다.
- 내 코드(지도.html 등)는 그대로라, 고치는 중인 화면을 실시간 운영 데이터로 볼 수 있다.
"""
import argparse
import functools
import http.server
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ['data.js', 'data-cctv.js']


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


def loop(every):
    while True:
        print(f'[{datetime.now():%H:%M:%S}] {sync()}', flush=True)
        time.sleep(every)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--every', type=int, default=60, help='가져오기 간격(초)')
    ap.add_argument('--no-serve', action='store_true', help='데이터만 받아 오고 웹서버는 띄우지 않는다(이미 다른 서버를 쓸 때)')
    a = ap.parse_args()
    if a.no_serve:
        try:
            loop(a.every)
        except KeyboardInterrupt:
            sys.exit(0)
    threading.Thread(target=loop, args=(a.every,), daemon=True).start()
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *x):                 # 요청 로그는 끈다(가져오기 기록만 보이게)
            pass
    handler = functools.partial(Quiet, directory=str(ROOT))
    class Server(http.server.ThreadingHTTPServer):
        allow_reuse_address = False                # Windows 는 켜 두면 이미 쓰는 포트에도 겹쳐 붙는다
    try:
        srv = Server(('127.0.0.1', a.port), handler)
    except OSError:
        # 이미 그 포트로 띄운 서버가 있으면(같은 폴더를 보고 있을 테니) 데이터만 받는다
        print(f'{a.port} 포트는 이미 사용 중 — 데이터만 받습니다. 화면은 쓰던 서버로 보세요. (끄기: Ctrl+C)', flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            sys.exit(0)
    print(f'열기: http://localhost:{a.port}/지도.html   (끄기: 이 창 닫기 또는 Ctrl+C)', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()
