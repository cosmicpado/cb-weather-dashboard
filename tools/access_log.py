"""접속 기록(2026-11-18) — 화면을 열 때마다 한 줄씩 남기고, 관리자 화면 '접속 통계'에 모아 보여 준다.

저장: <저장소>/.data/access/YYYY-MM.csv  (시각, 화면, 기기, 방문자)
  · 화면 파일(종합·상황실·재해·도움말·관리자)을 열 때만 센다. 자료(data.js)를 1분마다 다시 읽는 것은 세지 않는다.
  · IP 주소는 저장하지 않는다 — 서버에만 있는 비밀 값(salt)과 IP·브라우저 정보를 섞어 되돌릴 수 없는 방문자 번호로만 남긴다.
    그래서 '몇 명이 봤는지'는 알 수 있지만 '누가(어느 주소가)'는 기록에 없다.
  · 13개월 지난 파일은 지운다.
"""
import csv
import hashlib
import re
import secrets
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / '.data' / 'access'
PAGES = {'종합.html': '종합 현황', '상황실.html': '119종합상황실', '재해.html': '재해별 집중 감시',
         '도움말.html': '도움말', '관리자.html': '관리자'}
KEEP_MONTHS = 13
_lock = threading.Lock()
_salt_cache = None


def _salt():
    global _salt_cache
    if _salt_cache:
        return _salt_cache
    DIR.mkdir(parents=True, exist_ok=True)
    p = DIR / 'salt'
    try:
        s = p.read_text(encoding='utf-8').strip()
    except OSError:
        s = ''
    if len(s) < 32:
        s = secrets.token_hex(32)
        p.write_text(s, encoding='utf-8')
    _salt_cache = s
    return s


def _device(ua):
    return '휴대폰' if re.search(r'Mobi|Android|iPhone|iPad', ua or '') else 'PC'


def log(page_file, ip, ua):
    """page_file = 실제 파일 이름(예 '종합.html'). 화면이 아니면 아무것도 안 한다. 실패해도 화면 제공에는 영향 없음."""
    page = PAGES.get(page_file)
    if not page:
        return
    try:
        vid = hashlib.sha256((_salt() + '|' + (ip or '') + '|' + (ua or '')).encode('utf-8')).hexdigest()[:12]
        now = datetime.now()
        path = DIR / f'{now:%Y-%m}.csv'
        with _lock:
            new = not path.exists()
            with open(path, 'a', encoding='utf-8', newline='') as f:
                w = csv.writer(f)
                if new:
                    w.writerow(['시각', '화면', '기기', '방문자'])
                w.writerow([now.strftime('%Y-%m-%d %H:%M:%S'), page, _device(ua), vid])
            if new:
                _prune(now)
    except Exception:
        pass


def _prune(now):
    cut = (now.replace(day=1) - timedelta(days=31 * KEEP_MONTHS)).strftime('%Y-%m')
    for p in DIR.glob('*.csv'):
        if p.stem < cut:
            try:
                p.unlink()
            except OSError:
                pass


def _rows(since):
    """since(datetime) 이후 줄 [(시각, 화면, 기기, 방문자)]."""
    out, key = [], since.strftime('%Y-%m-%d %H:%M:%S')
    for p in sorted(DIR.glob('*.csv')):
        if p.stem < since.strftime('%Y-%m'):
            continue
        try:
            with open(p, encoding='utf-8', newline='') as f:
                for r in csv.reader(f):
                    if len(r) >= 4 and r[0] >= key and r[0][:1].isdigit():
                        out.append(r[:4])
        except OSError:
            pass
    return out


def stats(days=30):
    """관리자 화면용 요약 — 오늘·7일·30일 조회/방문자, 일별, 화면별, 시간대별(7일), 기기별(30일)."""
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = _rows(start)
    d7 = (now - timedelta(days=6)).strftime('%Y-%m-%d')

    def summary(rs):
        return {'views': len(rs), 'visitors': len({r[3] for r in rs})}

    by_day = defaultdict(list)
    for r in rows:
        by_day[r[0][:10]].append(r)
    daily = []
    for i in range(days):
        d = (start + timedelta(days=i)).strftime('%Y-%m-%d')
        daily.append({'date': d, **summary(by_day.get(d, []))})
    pages = []
    for name in PAGES.values():
        rs = [r for r in rows if r[1] == name]
        if not rs:
            continue
        pages.append({'page': name, 'today': summary([r for r in rs if r[0][:10] == today]),
                      'd7': summary([r for r in rs if r[0][:10] >= d7]), 'd30': summary(rs)})
    hours = Counter(int(r[0][11:13]) for r in rows if r[0][:10] >= d7)
    dev = Counter(r[2] for r in rows)
    return {'ok': True, 'at': now.strftime('%Y-%m-%d %H:%M'), 'days': days,
            'today': summary([r for r in rows if r[0][:10] == today]),
            'd7': summary([r for r in rows if r[0][:10] >= d7]), 'd30': summary(rows),
            'daily': daily, 'pages': pages, 'hours': [hours.get(h, 0) for h in range(24)],
            'device': {'PC': dev.get('PC', 0), '휴대폰': dev.get('휴대폰', 0)}}
