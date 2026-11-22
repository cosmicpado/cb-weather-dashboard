"""접속 기록(2026-11-18) — 화면을 열 때마다 한 줄씩 남기고, 관리자 화면 '접속 통계'에 모아 보여 준다.

저장: <저장소>/.data/access/YYYY-MM.csv  (시각, 화면, 기기, 방문자)
  · 화면 파일(종합·상황실·재해·도움말·관리자)을 열 때만 센다. 자료(data.js)를 1분마다 다시 읽는 것은 세지 않는다.
  · IP 주소는 저장하지 않는다 — 서버에만 있는 비밀 값(salt)과 IP·브라우저 정보를 섞어 되돌릴 수 없는 방문자 번호로만 남긴다.
    그래서 '몇 명이 봤는지'는 알 수 있지만 '누가(어느 주소가)'는 기록에 없다.
  · 방문자 번호는 처음 열 때 브라우저에 쿠키(cbv)로 맡겨 두고 다음부터 그 번호를 쓴다. 휴대폰은 통신사 주소가 수시로
    바뀌어 IP·브라우저만으로 세면 한 사람이 하루에 여러 명으로 잡혔다. 쿠키를 막은 브라우저는 예전처럼 IP·브라우저로 센다.
    (카톡 안 브라우저와 크롬처럼 브라우저가 다르면 쿠키도 따로라 여전히 두 명으로 잡힌다.)
  · 사람이 아닌 접속(카톡·메신저 링크 미리보기, 검색·검사 프로그램)은 세지 않는다.
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
PAGES = {'종합.html': '종합 현황', '상황실.html': '실시간 상황판', '재해.html': '재해별 집중 감시',
         '도움말.html': '도움말', '관리자.html': '관리자'}
OLD_NAMES = {'119종합상황실': '실시간 상황판'}   # 예전 기록의 화면 이름 → 지금 이름(통계에서 한 줄로 합친다)
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


COOKIE = 'cbv'
_BOT = re.compile(r'bot|crawl|spider|scrap|slurp|preview|facebookexternalhit|kakaotalk-scrap|Yeti|Daum|HeadlessChrome|'
                  r'python|curl|wget|Go-http|Java/|okhttp|axios|node-fetch|WhatsApp|TelegramBot', re.I)


def is_bot(ua):
    """사람이 아닌 접속 — 브라우저는 모두 'Mozilla/' 로 시작한다. 미리보기·검사 프로그램은 이름에 bot·scrap 등이 붙는다."""
    return not (ua or '').startswith('Mozilla/') or bool(_BOT.search(ua))


def visitor(ip, ua, cookie=''):
    """(방문자 번호, 쿠키를 새로 줘야 하나). 쿠키에 번호가 있으면 그것, 없으면 IP·브라우저로 만든 번호."""
    m = re.search(r'(?:^|;)\s*' + COOKIE + r'=([0-9a-f]{12})(?![0-9a-f])', cookie or '')
    if m:
        return m.group(1), False
    return hashlib.sha256((_salt() + '|' + (ip or '') + '|' + (ua or '')).encode('utf-8')).hexdigest()[:12], True


def cookie_header(vid):
    """Set-Cookie 값 — 400일(브라우저가 허락하는 최장). 화면 스크립트는 못 읽게 HttpOnly."""
    return f'{COOKIE}={vid}; Path=/; Max-Age=34560000; SameSite=Lax; HttpOnly'


def log(page_file, ip, ua, vid=None):
    """page_file = 실제 파일 이름(예 '종합.html'). 화면이 아니거나 사람이 아니면 아무것도 안 한다.
    vid = visitor() 로 구한 방문자 번호(없으면 IP·브라우저로). 실패해도 화면 제공에는 영향 없음."""
    page = PAGES.get(page_file)
    if not page or is_bot(ua):
        return
    try:
        vid = vid or visitor(ip, ua)[0]
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
    out, key, last = [], since.strftime('%Y-%m-%d %H:%M:%S'), None
    for p in sorted(DIR.glob('*.csv')):
        if p.stem < since.strftime('%Y-%m'):
            continue
        try:
            with open(p, encoding='utf-8', newline='') as f:
                for r in csv.reader(f):
                    if len(r) >= 4 and r[0] >= key and r[0][:1].isdigit():
                        r = [r[0], OLD_NAMES.get(r[1], r[1]), r[2], r[3]]
                        # 같은 방문자·같은 화면·같은 초에 두 줄 = 한 번 연 것(2026-11-20 이전 기록은 화면 틀의 자기 파일 받기까지 셌다)
                        if r == last:
                            continue
                        last = r
                        out.append(r)
        except OSError:
            pass
    return out


def stats(days=30):
    """관리자 화면용 요약 — 오늘·7일·30일 조회/방문자, 일별, 화면별, 시간대별(7일), 기기별(30일).
    by = 같은 요약을 기기별로({'PC': …, '휴대폰': …}) — 관리자 화면의 [전체 | PC | 휴대폰] 고르기."""
    now = datetime.now()
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = _rows(start)
    out = _summarize(rows, now, start, days)
    out['by'] = {d: _summarize([r for r in rows if r[2] == d], now, start, days) for d in ('PC', '휴대폰')}
    return out


def _summarize(rows, now, start, days):
    today = now.strftime('%Y-%m-%d')
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
