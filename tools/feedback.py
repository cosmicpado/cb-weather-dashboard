"""화면 사용자 의견 받기 — 서버.bat(tools/live_local.py)과 행정망 Rocky 서버(tools/server/feedback_server.py)가 같이 쓴다.

  POST /api/feedback   의견 한 건 저장 (화면의 💬 의견 보내기)
       {"action":"status", "id", "status", "note"}  처리 상태·처리 내용 저장 (관리자.html — 관리자만)
       {"action":"delete", "id"}                     의견 지우기 (관리자만, 2026-11-16) — 시험 의견 등.
         └ feedback.jsonl · feedback.csv 에서 그 줄을 실제로 빼고 처리 상태도 지운다. 되살릴 수 없다.
  GET  /api/feedback   저장된 의견 목록 + 처리 상태 (관리자.html — 관리자만)
  GET  /api/feedback?notices=1   공지사항 고친 것·지운 것·새로 쓴 것 (누구나 — 모든 화면의 notices.js 가 읽는다)
  POST {"action":"notice_save", "item":{id,date,kind,title,body,from}}  공지 쓰기·고치기 (관리자만)
       {"action":"notice_delete", "id"}                                   공지 지우기 (관리자만)
  GET  /api/feedback?duty=1      비상근무 기준표 (누구나 — 상황실 '비상근무' 칸 duty.js 가 읽는다, 2026-11-16)
  POST {"action":"duty_save", "rows":[{who,s1,s2,s3,s4,snow}] | null}   기준표 저장 · null 이면 기본값으로 (관리자만)
       └ .data/duty.json. 기본값은 duty.js 안에 있다.
  GET  /api/feedback?stage=1     충북 재대본 비상단계 직접 지정값 (누구나 — stage.js 가 1분마다 읽는다, 2026-11-16)
  POST {"action":"stage_set", "rank":0~4 | null, "pin":"1234"}   직접 지정(0 평상 ~ 4 3단계) · null 이면 자동(특보 기준)으로
       └ 상황실 벽면 화면에서 누른다. 지정 번호(PIN)가 맞아야 한다 — 서버 PC(관리자)는 번호 없이(2026-11-16 번호 추가:
         번호 없이 두니 내부망 누구나 모든 화면의 단계를 바꿀 수 있어 곤란). 5번 틀리면 그 주소는 10분 막는다.
         번호를 아직 안 정했으면 관리자만 바꿀 수 있다. 24시간 지나면 저절로 자동으로.
       "duty":[{who,what}] (선택) — 재대본 발령에 맞춰 직접 쓴 비상근무 내용. 없으면 기준표(duty.json·duty.js)대로(2026-11-16)
  POST {"action":"stage_pin_check", "pin":"1234"}   지정 번호 확인만(지정 창 [확인] — 맞아야 단계 단추가 켜진다). 틀리면 횟수에 센다
  POST {"action":"stage_pin", "pin":"1234" | null}   지정 번호 정하기(4~8자리 숫자) · null 이면 지우기 (관리자만)
       └ .data/stage_pin.json 에 소금 친 해시로만 둔다(번호 자체는 저장하지 않는다)
       └ .data/stage.json · 바꾼 기록은 .data/stage_log.jsonl(시각·주소·단계)
       └ .data/notices.json 에 둔다. notices.js 안의 기본 공지 위에 id 로 덮어쓴다(2026-11-12).
         코드 반영(git)으로는 지워지지 않고, 코드로 새 공지를 넣어도 여기서 고친 것과 함께 보인다.

저장: <저장소>/.data/feedback.csv   — 엑셀로 바로 여는 원본(덧붙이기만 한다, UTF-8 BOM)
      <저장소>/.data/feedback.jsonl — 관리자.html 이 읽는 같은 내용
      <저장소>/.data/feedback_status.json — 처리 상태(대기·처리 완료·보류·미수용)와 처리 내용(2026-11-12)
        · 의견 원본은 관리자가 지울 때만 고친다(그 줄만 빼고 다시 쓴다). 의견 번호(id)는 시각·이름·내용으로 만든 고정값이라 따로 저장하지 않는다.
  · 점(.)으로 시작하는 폴더라 nginx·서버.bat 이 밖으로 내주지 않는다.
  · 깃에 올리지 않는다(.gitignore). 소스 반영(update-code.sh 의 git reset)은 추적하지 않는 파일을 지우지 않는다.

관리자 권한(관리자.html — 받은 의견·공지사항)
  · 서버 자신(127.0.0.1)에서 열면 바로 보인다 — 서버.bat 을 켠 PC 에서 http://localhost:8000/관리자.html
  · 다른 PC 는 http://<서버>/관리자.html 을 열고 화면에서 .env 의 FEEDBACK_ADMIN_KEY 를 넣는다(2026-11-12 —
    예전엔 주소 #k=키 였으나 주소창·기록에 키가 보여 화면 입력으로 바꿈. 옛 주소로 열면 키를 옮겨 담고 주소에서 지운다).
    키는 요청 머리글(X-Admin-Key)로만 간다. 키가 비어 있으면 서버 자신만 볼 수 있다.
    키가 샜으면 .env 의 키만 바꾸면 된다(서버 재시작 불필요).

안전장치(행정망 서버의 첫 '쓰기' 기능이라)
  · 본문 16KB · 의견 2,000자 · 부서/이름 40자까지
  · 같은 PC 는 20초에 한 번, 하루 30건까지
  · 다른 사이트가 몰래 보내지 못하게 X-Requested-With 머리글을 요구한다(일반 폼으로는 못 붙인다)
  · 저장만 하고 실행하지 않는다. 관리자.html 은 글자를 그대로(textContent) 보여 준다.
"""
import csv
import hashlib
import hmac
import io
import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / '.data' / 'feedback.jsonl'
STORE_CSV = ROOT / '.data' / 'feedback.csv'
STORE_STATUS = ROOT / '.data' / 'feedback_status.json'
STATUSES = ('대기', '처리 완료', '보류', '미수용')
STORE_NOTICES = ROOT / '.data' / 'notices.json'
STORE_DUTY = ROOT / '.data' / 'duty.json'
STORE_STAGE = ROOT / '.data' / 'stage.json'        # 재대본 비상단계 직접 지정(2026-11-16)
STAGE_LOG = ROOT / '.data' / 'stage_log.jsonl'
STAGE_HOURS = 24                                    # 직접 지정은 이 시간이 지나면 저절로 자동(특보 기준)으로
STORE_STAGE_PIN = ROOT / '.data' / 'stage_pin.json'  # 지정 번호(해시)
_pin_fail = {}                                       # 주소 → [틀린 시각들] — 10분에 5번 틀리면 막는다
DUTY_KEYS = ('s1', 's2', 's3', 's4', 'snow')   # 준비 · 1단계 · 2단계 · 3단계 · 1단계(대설주의보로 난 경우)
NOTICE_KINDS = ('새 기능', '개선', '오류 수정', '안내')
NOTICE_ID = re.compile(r'^\d{4}-\d{2}-\d{2}-[0-9A-Za-z]{1,8}$')
MAX_NOTICES = 300
MAX_NOTE = 500
KINDS = ('오류', '기능 제안', '새 사이트 제안', '기타')
# 이름을 비우면 익명 — 그래서 접속 주소(IP)는 저장하지 않는다(연속 전송 제한에만 잠깐 메모리에 둔다)
CSV_COLS = [('ts', '시각'), ('kind', '구분'), ('page', '화면'), ('station', '관서'), ('who', '부서·이름'), ('text', '내용')]
MAX_BODY = 16 * 1024
MAX_TEXT, MAX_SHORT = 2000, 40
GAP_SEC, DAY_MAX = 20, 30
ALL_DAY_MAX = 300                 # 모든 주소 합쳐 하루 — 여러 주소로 나눠 보내는 도배 대비(2026-11-18)
STORE_MAX_BYTES = 20 * 1024 * 1024   # 의견 파일이 이보다 크면 접수를 멈춘다(디스크 가득 참 방지)
_lock = threading.Lock()
_seen = {}          # ip -> [마지막 시각, 오늘 날짜, 오늘 건수]
_all = ['', 0]      # [오늘 날짜, 오늘 전체 건수]


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


def _is_admin(ip, headers):
    """목록 보기·처리 상태 바꾸기 권한 — 서버 PC 자신이거나 비밀 키를 가진 주소."""
    if _is_local(ip):
        return True
    key = _env_key()
    given = (headers.get('X-Admin-Key') or '').strip()
    return bool(key and given and hmac.compare_digest(key.encode(), given.encode()))


def _rec_id(rec):
    """의견 번호 — 시각·이름·내용으로 만든 고정값(예전 의견에도 그대로 붙는다)."""
    src = '|'.join(str(rec.get(k) or '') for k in ('ts', 'who', 'text'))
    return hashlib.sha1(src.encode('utf-8')).hexdigest()[:12]


def _load_status():
    try:
        d = json.loads(STORE_STATUS.read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _set_status(ip, headers, j):
    if not _is_admin(ip, headers):
        return 403, {'ok': False, 'err': '처리 상태를 바꿀 수 없는 주소입니다'}
    rid = _clean(j.get('id'), 20)
    status = _clean(j.get('status'), 10)
    note = _clean(j.get('note'), MAX_NOTE)
    if not rid or status not in STATUSES:
        return 400, {'ok': False, 'err': '형식 오류'}
    with _lock:
        d = _load_status()
        if status == '대기' and not note:
            d.pop(rid, None)
        else:
            d[rid] = {'status': status, 'note': note, 'at': datetime.now().strftime('%Y-%m-%d %H:%M')}
        STORE_STATUS.parent.mkdir(parents=True, exist_ok=True)
        tmp = STORE_STATUS.with_name(STORE_STATUS.name + '.tmp')
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(tmp, STORE_STATUS)
    return 200, {'ok': True, 'id': rid, **(d.get(rid) or {'status': '대기', 'note': '', 'at': ''})}


def _delete(ip, headers, j):
    """의견 한 건을 원본(jsonl·csv)과 처리 상태에서 모두 지운다."""
    if not _is_admin(ip, headers):
        return 403, {'ok': False, 'err': '지울 수 없는 주소입니다'}
    rid = _clean(j.get('id'), 20)
    if not re.fullmatch(r'[0-9a-f]{12}', rid or ''):
        return 400, {'ok': False, 'err': '형식 오류'}
    with _lock:
        try:
            lines = STORE.read_text(encoding='utf-8').splitlines(keepends=True)
        except FileNotFoundError:
            lines = []
        keep, gone = [], None
        for line in lines:
            try:
                rec = json.loads(line)
            except ValueError:
                keep.append(line)                    # 읽지 못하는 줄은 손대지 않는다
                continue
            if gone is None and _rec_id(rec) == rid:
                gone = rec
            else:
                keep.append(line)
        if gone is None:
            return 404, {'ok': False, 'err': '이미 지워졌거나 없는 의견입니다'}
        _write_atomic(STORE, ''.join(keep), 'utf-8')
        # 엑셀용 CSV — 시각·이름·내용이 같은 줄 하나만 뺀다
        if STORE_CSV.exists():
            raw = STORE_CSV.read_text(encoding='utf-8-sig')
            rows = list(csv.reader(io.StringIO(raw)))
            want = [_csv_cell(gone.get(k)) for k, _ in CSV_COLS]
            col = {k: i for i, (k, _) in enumerate(CSV_COLS)}
            for i, r in enumerate(rows[1:], 1):
                if len(r) == len(want) and all(r[col[k]] == want[col[k]] for k in ('ts', 'who', 'text')):
                    del rows[i]
                    buf = io.StringIO()
                    csv.writer(buf, lineterminator='\r\n').writerows(rows)
                    _write_atomic(STORE_CSV, buf.getvalue(), 'utf-8-sig')
                    break
        st = _load_status()
        if st.pop(rid, None) is not None:
            _write_atomic(STORE_STATUS, json.dumps(st, ensure_ascii=False, indent=1), 'utf-8')
    return 200, {'ok': True, 'id': rid}


def _write_atomic(path, text, enc):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w', encoding=enc, newline='') as f:
        f.write(text)
    os.replace(tmp, path)


# 예전에 notices.js(코드)에 있던 기본 공지 — 공지를 서버에만 두기로 하면서(2026-11-18) 처음 한 번 서버로 옮긴다.
# 이미 같은 id 가 서버에 있으면(관리자 페이지에서 고쳤거나 지운 것) 건드리지 않는다. 옮긴 뒤엔 다시 넣지 않는다.
_SEED_NOTICES = [
    {'id': '2026-11-17-3', 'date': '2026-11-17', 'kind': '개선', 'title': '화면 안정성 개선 · 휴대폰 화면 정리',
     'body': '접속 순간 자료를 다 받지 못하면 빈 화면 대신 "실시간 자료를 불러오는 중"이 뜨고, 받아지는 대로 자동으로 화면이 열립니다.\n'
             '종합현황 맨 위, 상황실 휴대폰 화면 맨 위에 "자료 ○○:○○ 기준"이 표시됩니다. 15분 넘게 갱신되지 않으면 빨간색으로 알려 드립니다.\n'
             '휴대폰에서는 새 특보·재난문자 알림 팝업과 알림음이 뜨지 않습니다(화면 칸에는 그대로 나옵니다).\n'
             '화면에 남아 있던 예전 예시 자료를 모두 지우고 충청북도 자료만 보이게 했습니다.'},
    {'id': '2026-11-10-2', 'date': '2026-11-10', 'kind': '새 기능', 'title': '💬 의견 보내기가 생겼습니다',
     'body': '종합 현황 맨 위 오른쪽, 119종합상황실 왼쪽 위의 💬 버튼으로 의견을 보낼 수 있습니다.\n'
             '보내 주신 의견은 개발 담당자가 확인하고, 반영되면 이 공지사항으로 알려 드립니다.'},
]
SEEDED_FLAG = ROOT / '.data' / 'notices_seeded'


def _load_notices():
    try:
        d = json.loads(STORE_NOTICES.read_text(encoding='utf-8'))
        d = d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        d = {}
    if not SEEDED_FLAG.exists():
        add = [n for n in _SEED_NOTICES if n['id'] not in d]
        try:
            if add:
                for n in add:
                    d[n['id']] = dict(n, at=datetime.now().strftime('%Y-%m-%d %H:%M'))
                _save_notices(d)
            SEEDED_FLAG.write_text(datetime.now().strftime('%Y-%m-%d %H:%M'), encoding='utf-8')
        except OSError:
            pass
    return d


def _save_notices(d):
    STORE_NOTICES.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_NOTICES.with_name(STORE_NOTICES.name + '.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, STORE_NOTICES)


def _get_duty():
    try:
        d = json.loads(STORE_DUTY.read_text(encoding='utf-8'))
        if not isinstance(d, dict) or not isinstance(d.get('rows'), list):
            d = None
    except (OSError, ValueError):
        d = None
    return 200, {'ok': True, 'duty': d}


def _save_duty(ip, headers, j):
    """비상근무 기준표 저장 — 관리자만. rows 가 null 이면 파일을 지워 기본값(duty.js)으로."""
    if not _is_admin(ip, headers):
        return 403, {'ok': False, 'err': '비상근무 기준을 바꿀 수 없는 주소입니다'}
    rows = j.get('rows')
    with _lock:
        if rows is None:
            try:
                STORE_DUTY.unlink()
            except FileNotFoundError:
                pass
            return 200, {'ok': True, 'duty': None}
        if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
            return 400, {'ok': False, 'err': '부서는 1~8개까지입니다'}
        out = []
        for r in rows:
            r = r if isinstance(r, dict) else {}
            one = lambda v, n: ' '.join(_clean(v, n).split())   # 한 줄로
            who = one(r.get('who'), 20)
            if not who:
                return 400, {'ok': False, 'err': '부서 이름을 적어 주세요'}
            out.append({'who': who, **{k: one(r.get(k), 40) for k in DUTY_KEYS}})
        d = {'rows': out, 'at': datetime.now().strftime('%Y-%m-%d %H:%M')}
        _write_atomic(STORE_DUTY, json.dumps(d, ensure_ascii=False, indent=1), 'utf-8')
    return 200, {'ok': True, 'duty': d}


def _get_stage():
    """직접 지정된 재대본 비상단계. 없거나 24시간이 지났으면 None(= 자동)."""
    try:
        d = json.loads(STORE_STAGE.read_text(encoding='utf-8'))
        if not isinstance(d, dict) or not isinstance(d.get('rank'), int) or float(d.get('until') or 0) < time.time():
            d = None
    except (OSError, ValueError, TypeError):
        d = None
    return 200, {'ok': True, 'stage': d, 'pin': _load_pin() is not None}


def _load_pin():
    try:
        p = json.loads(STORE_STAGE_PIN.read_text(encoding='utf-8'))
        return p if isinstance(p, dict) and p.get('hash') and p.get('salt') else None
    except (OSError, ValueError):
        return None


def _pin_hash(salt, pin):
    return hashlib.sha256((salt + '|' + pin).encode('utf-8')).hexdigest()


def _save_pin(ip, headers, j):
    """지정 번호 정하기·지우기 — 관리자만."""
    if not _is_admin(ip, headers):
        return 403, {'ok': False, 'err': '지정 번호를 바꿀 수 없는 주소입니다'}
    pin = j.get('pin')
    with _lock:
        if pin is None:
            try:
                STORE_STAGE_PIN.unlink()
            except FileNotFoundError:
                pass
            return 200, {'ok': True, 'pin': False}
        pin = str(pin).strip()
        if not re.fullmatch(r'\d{4,8}', pin):
            return 400, {'ok': False, 'err': '번호는 숫자 4~8자리로 정해 주세요'}
        salt = os.urandom(8).hex()
        _write_atomic(STORE_STAGE_PIN, json.dumps({'salt': salt, 'hash': _pin_hash(salt, pin),
                                                   'at': datetime.now().strftime('%Y-%m-%d %H:%M')}), 'utf-8')
    return 200, {'ok': True, 'pin': True}


def _pin_ok(ip, headers, j):
    """(통과 여부, 거절 응답). 관리자는 번호 없이 통과. 번호가 없으면 관리자만."""
    if _is_admin(ip, headers):
        return True, None
    p = _load_pin()
    if p is None:
        return False, (403, {'ok': False, 'err': '지정 번호가 아직 없습니다 — 관리자에게 문의하세요'})
    now = time.time()
    fails = [t for t in _pin_fail.get(ip, []) if now - t < 600]
    if len(fails) >= 5:
        return False, (429, {'ok': False, 'err': '번호를 여러 번 틀려 10분 동안 바꿀 수 없습니다'})
    pin = str(j.get('pin') or '').strip()
    if pin and hmac.compare_digest(_pin_hash(p['salt'], pin), p['hash']):
        _pin_fail.pop(ip, None)
        return True, None
    fails.append(now)
    _pin_fail[ip] = fails
    return False, (403, {'ok': False, 'err': '번호가 맞지 않습니다' + (f' ({5 - len(fails)}번 남음)' if len(fails) < 5 else '')})


def _set_stage(ip, headers, j):
    """재대본 비상단계 직접 지정 — 누구나(상황실 벽면 화면). rank None 이면 자동으로 되돌린다. 바꿀 때마다 기록을 남긴다."""
    rank = j.get('rank')
    if rank is not None and (not isinstance(rank, int) or isinstance(rank, bool) or not 0 <= rank <= 4):
        return 400, {'ok': False, 'err': '단계 값이 잘못됐습니다'}
    ok, deny = _pin_ok(ip, headers, j)
    if not ok:
        return deny
    duty = None
    if rank and isinstance(j.get('duty'), list):          # 직접 쓴 비상근무 내용 — 한 줄로, 부서 20자·내용 40자, 8줄까지
        one = lambda v, n: ' '.join(_clean(v, n).split())
        duty = [{'who': one(r.get('who'), 20), 'what': one(r.get('what'), 40)}
                for r in j['duty'][:8] if isinstance(r, dict)]
        duty = [r for r in duty if r['who'] and r['what']] or None
    now = datetime.now()
    with _lock:
        if rank is None:
            try:
                STORE_STAGE.unlink()
            except FileNotFoundError:
                pass
            d = None
        else:
            d = {'rank': rank, 'at': now.strftime('%Y-%m-%d %H:%M'), 'until': round(time.time() + STAGE_HOURS * 3600)}
            if duty:
                d['duty'] = duty
            _write_atomic(STORE_STAGE, json.dumps(d, ensure_ascii=False), 'utf-8')
        try:
            STAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
            with STAGE_LOG.open('a', encoding='utf-8') as f:
                f.write(json.dumps({'at': now.strftime('%Y-%m-%d %H:%M:%S'), 'ip': ip,
                                    'rank': rank if rank is not None else 'auto', 'duty': duty}, ensure_ascii=False) + '\n')
        except OSError:
            pass
    return 200, {'ok': True, 'stage': d, 'pin': _load_pin() is not None}


def _get_notices():
    d = _load_notices()
    return 200, {'ok': True, 'items': list(d.values())}


def _notice(ip, headers, j):
    """공지 쓰기·고치기·지우기 — 관리자만. 지운 것은 {id, deleted:true} 로 남겨 notices.js 기본 공지도 가린다."""
    if not _is_admin(ip, headers):
        return 403, {'ok': False, 'err': '공지를 바꿀 수 없는 주소입니다'}
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    if j.get('action') == 'notice_delete':
        nid = _clean(j.get('id'), 24)
        if not NOTICE_ID.match(nid):
            return 400, {'ok': False, 'err': '형식 오류'}
        rec = {'id': nid, 'deleted': True, 'at': now}
    else:
        it = j.get('item') if isinstance(j.get('item'), dict) else {}
        nid = _clean(it.get('id'), 24)
        date = _clean(it.get('date'), 10)
        kind = _clean(it.get('kind'), 10)
        title = _clean(it.get('title'), 100)
        body = str(it.get('body') or '').replace('\r\n', '\n').strip()[:3000]
        if not NOTICE_ID.match(nid) or not re.match(r'^\d{4}-\d{2}-\d{2}$', date) or len(title) < 2:
            return 400, {'ok': False, 'err': '제목·날짜를 확인해 주세요'}
        rec = {'id': nid, 'date': date, 'kind': kind if kind in NOTICE_KINDS else '안내',
               'title': title, 'body': body, 'from': _clean(it.get('from'), 40), 'at': now}
    with _lock:
        d = _load_notices()
        if nid not in d and len(d) >= MAX_NOTICES:
            return 400, {'ok': False, 'err': '공지가 너무 많습니다'}
        d[nid] = rec
        _save_notices(d)
    return 200, {'ok': True, 'item': rec}


def handle(method, ip, headers, body=b'', path=''):
    """(상태코드, 응답 dict) 를 돌려준다. headers 는 대소문자 무시 조회가 되는 객체(http.server 의 self.headers).
    path 는 요청 주소(물음표 뒤 포함) — ?notices=1 이면 공지사항."""
    if method == 'POST':
        return _post(ip, headers, body)
    if method == 'GET':
        q = path.split('?', 1)[1] if '?' in path else ''
        if 'notices=1' in q:
            return _get_notices()
        if 'duty=1' in q:
            return _get_duty()
        if 'errors=1' in q:                          # 화면 오류 최근 50건 — 관리자만
            if not _is_admin(ip, headers):
                return 403, {'ok': False, 'err': '관리자만 볼 수 있습니다'}
            try:
                lines = STORE_ERRORS.read_text(encoding='utf-8').splitlines()[-50:]
                items = [json.loads(l) for l in lines if l.strip()]
            except (OSError, ValueError):
                items = []
            return 200, {'ok': True, 'items': items[::-1]}
        if 'stage=1' in q:
            return _get_stage()
        return _get(ip, headers)
    return 405, {'ok': False, 'err': '지원하지 않는 방식'}


# 화면 오류 기록(2026-11-20) — 직원 PC·휴대폰에서 스크립트 오류가 나면 error-report.js 가 보낸다.
# .data/client_errors.jsonl 에 한 줄씩. 주소당 하루 50건 · 파일 5MB 넘으면 더 받지 않는다(오류가 반복돼도 디스크가 차지 않게).
STORE_ERRORS = ROOT / '.data' / 'client_errors.jsonl'
ERR_DAY_MAX, ERR_MAX_BYTES = 50, 5 * 1024 * 1024
_err_seen = {}   # ip -> [오늘 날짜, 오늘 건수]


def _client_error(ip, headers, j):
    today = datetime.now().strftime('%Y-%m-%d')
    with _lock:
        day, cnt = _err_seen.get(ip, [today, 0])
        if day != today:
            cnt = 0
        if cnt >= ERR_DAY_MAX:
            return 429, {'ok': False}
        try:
            if STORE_ERRORS.exists() and STORE_ERRORS.stat().st_size > ERR_MAX_BYTES:
                return 507, {'ok': False}
        except OSError:
            pass
        rec = {'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
               'page': _clean(j.get('page'), 60), 'msg': _clean(j.get('msg'), 300),
               'src': _clean(j.get('src'), 160), 'line': _clean(j.get('line'), 20),
               'stack': _clean(j.get('stack'), 1200), 'ua': _clean(headers.get('User-Agent'), 160)}
        STORE_ERRORS.parent.mkdir(parents=True, exist_ok=True)
        with open(STORE_ERRORS, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        _err_seen[ip] = [today, cnt + 1]
    return 200, {'ok': True}


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
    if j.get('action') == 'admin_view':              # 관리자 접속 통계 — 키가 맞아 관리자 화면이 열렸을 때만 센다
        if not _is_admin(ip, headers):
            return 403, {'ok': False}
        try:
            import access_log
            ua = headers.get('User-Agent', '')
            access_log.log('관리자.html', ip, ua, access_log.visitor(ip, ua, headers.get('Cookie', ''))[0])
        except Exception:
            pass
        return 200, {'ok': True}
    if j.get('action') == 'client_error':            # 화면 스크립트 오류 기록(error-report.js)
        return _client_error(ip, headers, j)
    if j.get('action') == 'status':
        return _set_status(ip, headers, j)
    if j.get('action') == 'delete':
        return _delete(ip, headers, j)
    if j.get('action') == 'duty_save':
        return _save_duty(ip, headers, j)
    if j.get('action') == 'stage_set':
        return _set_stage(ip, headers, j)
    if j.get('action') == 'stage_pin':
        return _save_pin(ip, headers, j)
    if j.get('action') == 'stage_pin_check':         # 지정 창 [확인] — 번호만 확인(틀리면 횟수에 센다)
        ok, deny = _pin_ok(ip, headers, j)
        return (200, {'ok': True}) if ok else deny
    if j.get('action') in ('notice_save', 'notice_delete'):
        return _notice(ip, headers, j)
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
        if _all[0] != today:
            _all[0], _all[1] = today, 0
        if _all[1] >= ALL_DAY_MAX:
            return 429, {'ok': False, 'err': '오늘 받을 수 있는 의견 수를 넘었습니다. 내일 다시 보내 주세요'}
        try:
            size = sum(p.stat().st_size for p in (STORE, STORE_CSV) if p.exists())
        except OSError:
            size = 0
        if size > STORE_MAX_BYTES:
            return 507, {'ok': False, 'err': '의견 저장 공간이 가득 찼습니다. 관리자에게 알려 주세요'}
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
        _all[1] += 1
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
    if not _is_admin(ip, headers):
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
    st = _load_status()
    for x in items:
        x.pop('ua', None)                   # 화면에 쓰지 않는다
        x['id'] = _rec_id(x)
        s = st.get(x['id']) or {}
        x['status'] = s.get('status') or '대기'
        x['note'] = s.get('note') or ''
        x['statusAt'] = s.get('at') or ''
    return 200, {'ok': True, 'n': len(items), 'items': items[:2000]}
