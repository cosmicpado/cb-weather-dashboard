"""화면 사용자 의견 받기 — 서버.bat(tools/live_local.py)과 행정망 Rocky 서버(tools/server/feedback_server.py)가 같이 쓴다.

  POST /api/feedback   의견 한 건 저장 (화면의 💬 의견 보내기)
  GET  /api/feedback   저장된 의견 목록 (의견.html — 관리자만)

저장: <저장소>/.data/feedback.csv   — 엑셀로 바로 여는 원본(덧붙이기만 한다, UTF-8 BOM)
      <저장소>/.data/feedback.jsonl — 의견.html 이 읽는 같은 내용
  · 점(.)으로 시작하는 폴더라 nginx·서버.bat 이 밖으로 내주지 않는다.
  · 깃에 올리지 않는다(.gitignore). 소스 반영(update-code.sh 의 git reset)은 추적하지 않는 파일을 지우지 않는다.

목록 보기 권한(2026-11-10 사용자 결정: 키 입력 없이 '나만 아는 주소'로)
  · 서버 자신(127.0.0.1)에서 열면 바로 보인다 — 서버.bat 을 켠 PC 에서 http://localhost:8000/의견.html
  · 다른 PC 는 비밀 주소 http://<서버>/의견.html#k=<.env 의 FEEDBACK_ADMIN_KEY> 로 연다(# 뒤는 서버 기록에 안 남는다).
    키가 비어 있으면 서버 자신만 볼 수 있다. 주소가 새면 .env 의 키만 바꾸면 된다(서버 재시작 불필요).

안전장치(행정망 서버의 첫 '쓰기' 기능이라)
  · 본문 16KB · 의견 2,000자 · 부서/이름 40자까지
  · 같은 PC 는 20초에 한 번, 하루 30건까지
  · 다른 사이트가 몰래 보내지 못하게 X-Requested-With 머리글을 요구한다(일반 폼으로는 못 붙인다)
  · 저장만 하고 실행하지 않는다. 의견.html 은 글자를 그대로(textContent) 보여 준다.
"""
import csv
import hmac
import io
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / '.data' / 'feedback.jsonl'
STORE_CSV = ROOT / '.data' / 'feedback.csv'
KINDS = ('오류', '기능 제안', '새 사이트 제안', '기타')
# 이름을 비우면 익명 — 그래서 접속 주소(IP)는 저장하지 않는다(연속 전송 제한에만 잠깐 메모리에 둔다)
CSV_COLS = [('ts', '시각'), ('kind', '구분'), ('page', '화면'), ('station', '관서'), ('who', '부서·이름'), ('text', '내용')]
MAX_BODY = 16 * 1024
MAX_TEXT, MAX_SHORT = 2000, 40
GAP_SEC, DAY_MAX = 20, 30
_lock = threading.Lock()
_seen = {}          # ip -> [마지막 시각, 오늘 날짜, 오늘 건수]


def _env_key():
    """FEEDBACK_ADMIN_KEY — 환경변수가 먼저, 없으면 .env 에서 읽는다(서버를 다시 켜지 않아도 바뀐 키가 적용되게 매번 읽는다)."""
    v = os.environ.get('FEEDBACK_ADMIN_KEY')
    if v:
        return v.strip()
    try:
        for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
            if line.startswith('FEEDBACK_ADMIN_KEY='):
                return line.split('=', 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return ''


def _clean(v, n):
    s = str(v or '').replace('\r\n', '\n').replace('\r', '\n')
    s = ''.join(c for c in s if c == '\n' or c == '\t' or ord(c) >= 32)
    return s.strip()[:n]


def _is_local(ip):
    return ip in ('127.0.0.1', '::1', '::ffff:127.0.0.1')


def handle(method, ip, headers, body=b''):
    """(상태코드, 응답 dict) 를 돌려준다. headers 는 대소문자 무시 조회가 되는 객체(http.server 의 self.headers)."""
    if method == 'POST':
        return _post(ip, headers, body)
    if method == 'GET':
        return _get(ip, headers)
    return 405, {'ok': False, 'err': '지원하지 않는 방식'}


def _post(ip, headers, body):
    if (headers.get('X-Requested-With') or '') != 'cbweather':
        return 403, {'ok': False, 'err': '화면의 의견 보내기로만 보낼 수 있습니다'}
    if len(body) > MAX_BODY:
        return 413, {'ok': False, 'err': '너무 깁니다'}
    try:
        j = json.loads(body.decode('utf-8'))
        if not isinstance(j, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return 400, {'ok': False, 'err': '형식 오류'}
    text = _clean(j.get('text'), MAX_TEXT)
    if len(text) < 2:
        return 400, {'ok': False, 'err': '내용을 적어 주세요'}
    who = _clean(j.get('who'), MAX_SHORT)
    if _clean(j.get('kind'), 20) == '새 사이트 제안':
        # 구체적으로 받으려는 사용자 결정(2026-11-10) — 화면(feedback.js)과 같은 규칙
        if not who or who == '익명':
            return 400, {'ok': False, 'err': '새 사이트 제안은 부서·이름을 꼭 적어 주세요'}
        answer = ''.join(l for l in text.split('\n') if l.strip()[:1] not in ('①', '②', '③', '④'))
        if len(''.join(answer.split())) < 30:
            return 400, {'ok': False, 'err': '조금 더 구체적으로 적어 주세요 (항목별 답 30자 이상)'}
    now = time.time()
    today = datetime.now().strftime('%Y-%m-%d')
    with _lock:
        last, day, cnt = _seen.get(ip, [0, today, 0])
        if day != today:
            cnt = 0
        if now - last < GAP_SEC:
            return 429, {'ok': False, 'err': f'조금 전에 보내셨습니다. {int(GAP_SEC - (now - last)) + 1}초 뒤에 다시 보내 주세요'}
        if cnt >= DAY_MAX:
            return 429, {'ok': False, 'err': '오늘은 이 PC 에서 더 보낼 수 없습니다'}
        kind = _clean(j.get('kind'), 20)
        rec = {
            'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'kind': kind if kind in KINDS else '기타',
            'page': _clean(j.get('page'), 60),
            'station': _clean(j.get('station'), MAX_SHORT),
            'who': who or '익명',
            'text': text,
            'ua': _clean(headers.get('User-Agent'), 160),
        }
        STORE.parent.mkdir(parents=True, exist_ok=True)
        with open(STORE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        _append_csv(rec)
        _seen[ip] = [now, today, cnt + 1]
    return 200, {'ok': True}


def _csv_cell(v):
    v = str(v or '')
    return "'" + v if v[:1] in ('=', '+', '-', '@') else v      # 엑셀이 수식으로 실행하지 않게


def _append_csv(rec):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\r\n')
    new = not STORE_CSV.exists()
    if new:
        w.writerow([h for _, h in CSV_COLS])
    w.writerow([_csv_cell(rec.get(k)) for k, _ in CSV_COLS])
    with open(STORE_CSV, 'a', encoding='utf-8-sig' if new else 'utf-8', newline='') as f:
        f.write(buf.getvalue())


def _get(ip, headers):
    key = _env_key()
    given = (headers.get('X-Admin-Key') or '').strip()
    if not _is_local(ip) and not (key and given and hmac.compare_digest(key.encode(), given.encode())):
        return 403, {'ok': False, 'err': '볼 수 없는 주소입니다'}
    items = []
    try:
        with open(STORE, encoding='utf-8') as f:
            for line in f:
                try:
                    items.append(json.loads(line))
                except ValueError:
                    pass
    except FileNotFoundError:
        pass
    items.reverse()                         # 최신부터
    return 200, {'ok': True, 'n': len(items), 'items': items[:2000]}
