# -*- coding: utf-8 -*-
"""기상·재난 상황판 데이터 수집기 (지역 프로파일 방식).

기상청·환경공단·산림청·한강홍수통제소·행안부 공공 API를 호출해 data 파일을 갱신한다.
지역마다 다른 값(시군·관측소·특보구역)은 tools/region_profiles.py 에 있고,
이 파일의 함수들은 지역을 가리지 않는다.

실행:
  python tools/update_data.py              충청북도 → data.js (수집 후 git 커밋·푸시·배포)
  python tools/update_data.py --no-push    수집만 (로컬 확인용)
"""
import json
import os
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import requests

# 사내망 HTTPS 검사(중간 인증서) 대응 — 파이썬 기본 인증서 목록(certifi) 대신 Windows 인증서 저장소를 쓴다.
# 사내망에서는 이게 없으면 모든 API 호출이 CERTIFICATE_VERIFY_FAILED 로 실패한다.
# 설치되어 있을 때만 적용(pip install truststore) — 서버·GitHub Actions 는 없어도 그대로 동작한다.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# Windows 콘솔 한글 출력
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# ───────────────────────────────────────────────────────────────
# 모든 시각을 한국 표준시(KST)로 통일.
#
# - GitHub Actions(Linux): 기본 UTC라 datetime.now()가 9시간 전을 반환.
#   → os.environ['TZ']='Asia/Seoul' + time.tzset()으로 KST 적용.
# - Windows(사장님 PC): 시스템 시계가 이미 KST.
#   ⚠️ 주의: Windows Python은 'Asia/Seoul'(IANA 형식)을 파싱하지 못하고
#   tzset()도 없어서, os.environ['TZ']='Asia/Seoul'을 설정하면 오히려
#   datetime.now()가 UTC로 깨진다(데이터 시각이 9시간 늦게 찍힘).
#   따라서 Windows에서는 TZ를 절대 건드리지 않는다.
if sys.platform != 'win32':
    os.environ['TZ'] = 'Asia/Seoul'
    time.tzset()        # Unix(GitHub Actions Linux) 전용
# ───────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent


def _atomic_write_text(path, text):
    """상태파일을 원자적으로 저장 — 같은 폴더에 임시파일을 쓴 뒤 os.replace로 교체.

    write_text는 대상 파일을 먼저 0으로 비우고 쓰므로, ①1분/5분 알리미가 동시에
    읽고 쓸 때 다른 쪽이 '비워진 순간'을 읽거나 ②디스크가 꽉 차 쓰기가 실패하면
    파일이 잘려 중복 방지 상태가 통째로 날아간다(→ 같은 특보 반복 발송).
    os.replace는 원자적이라 읽는 쪽은 항상 '완전한 이전' 또는 '완전한 새' 상태만
    보고, 쓰기 실패 시에는 직전 정상 파일이 그대로 보존된다. 실패해도 예외를 올려
    호출부가 '저장 성공'으로 오판하지 않게 한다."""
    path = Path(path)
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp.{os.getpid()}')
    try:
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, path)   # 원자적 교체 (POSIX rename)
    except Exception:
        try:
            tmp.unlink()        # 실패 시 임시파일 청소 (디스크 낭비 방지)
        except OSError:
            pass
        raise


# ───────────────────────────────────────────────────────────────
# 지역 프로파일 — 어느 지역 상황판을 만들 것인가
#
#   python tools/update_data.py                  → 충청북도 (data.js)
#   ... --no-push     : 깃 푸시·배포 생략 (여러 지역을 연달아 돌릴 때 마지막 회차만 푸시)
#
# 지역마다 다른 값(시군 목록·관측소·특보구역)은 전부 tools/region_profiles.py에 있다.
# 아래 상수들은 그 프로파일에서 꺼내 쓰는 것이고, 함수 본문은 지역을 가리지 않는다.
# ───────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
import region_profiles as _rp   # noqa: E402


def _argval(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


PROFILE_NAME = _argval('--profile', _rp.DEFAULT)
P = _rp.get(PROFILE_NAME)
NO_PUSH = '--no-push' in sys.argv

ENV_PATH = ROOT / '.env'
OUTPUT_PATH = ROOT / P['data_file']
TEMPLATE_PATH = ROOT / 'index.html'
COMBINED_OUTPUT_PATH = ROOT / P['combined_file']

# 상태파일 폴더 (강수 누적·알림 중복방지 기록 등)
TMP = ROOT / '.tmp'
TMP.mkdir(parents=True, exist_ok=True)


def load_env(path=ENV_PATH):
    env = {}
    if path.exists():
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    # GitHub Actions 등 .env 없는 환경에서는 OS 환경변수로 fallback
    import os
    for key in ('DATA_GO_KR_KEY', 'HRFCO_KEY', 'SAFETY_DATA_KEY', 'KMA_APIHUB_KEY'):
        env.setdefault(key, os.environ.get(key, ''))
    return env


ENV = load_env()
DATA_KEY = ENV.get('DATA_GO_KR_KEY', '')
HRFCO_KEY = ENV.get('HRFCO_KEY', '')
SAFETY_KEY = ENV.get('SAFETY_DATA_KEY', '')
KMA_APIHUB_KEY = ENV.get('KMA_APIHUB_KEY', '')  # 기상청 API 허브 (apihub.kma.go.kr)

# ───────────────────────────────────────────────────────────────
# 보안: 로그(cron.log)에 API 키가 평문으로 남는 것을 차단.
#
# requests 예외 메시지에는 호출 URL이 통째로 들어있고(serviceKey=…·
# authKey=… 포함), 이를 print하면 키가 cron.log에 그대로 찍힌다.
# 아래에서 stdout/stderr를 감싸 모든 출력에서 알려진 비밀값과
# 자격증명 패턴을 '***'로 치환한다. 새 fetch_* 함수가 추가돼도 자동 보호.
# ───────────────────────────────────────────────────────────────
import re as _re

# .env에서 읽은 실제 비밀값 (빈 값은 제외 — ''.replace는 모든 위치에 끼어듦)
_SECRETS = [v for v in (DATA_KEY, HRFCO_KEY, SAFETY_KEY, KMA_APIHUB_KEY) if v]
# URL 자격증명 패턴 — 값이 .env와 안 맞아도(또는 git 원격 URL의 토큰까지) 잡음
_CRED_QUERY = _re.compile(r'(?i)(serviceKey|authKey)=[^&\s\'"]+')
_CRED_TOKEN = _re.compile(r'(?:ghp_[A-Za-z0-9]{20,}'
                          r'|github_pat_[A-Za-z0-9_]{20,}'
                          r'|bot\d{6,}:[A-Za-z0-9_-]{30,})')


def _redact(text):
    """문자열에서 비밀값·자격증명을 '***'로 가린다. 로그·에러 출력 전용."""
    s = str(text)
    for secret in _SECRETS:
        s = s.replace(secret, '***')
    s = _CRED_QUERY.sub(r'\1=***', s)
    s = _CRED_TOKEN.sub('***', s)
    return s


class _RedactingStream:
    """stdout/stderr 프록시 — write되는 모든 텍스트에서 비밀값을 가린다."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, data):
        return self._stream.write(_redact(data))

    def flush(self):
        return self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


sys.stdout = _RedactingStream(sys.stdout)
sys.stderr = _RedactingStream(sys.stderr)

# 시군 목록 + 기상청 격자좌표(nx,ny) + 산불위험 시군구코드 — 지역 프로파일에서
REGIONS = P['regions']

# 미세먼지 측정소: 시군 → 대표 측정소명 매핑 (에어코리아 실제 등록명 기준)
PM_STATIONS = P['pm_stations']

# 이 상황판이 담당하는 시군 집합 — 특보·재난문자·산불통계 필터의 공통 기준.
SIGUN_SET = {r['name'] for r in REGIONS}
# 시(市)가 아니라 군(郡)인 곳 — 재난문자 발신처 표기('연천군' vs '파주시')에 쓴다.
GUN_NAMES = set(P.get('gun_names') or ['연천', '가평', '양평']) & SIGUN_SET
# ── 시도 상수 (전국 확장 1단계) ─────────────────────────────
# 경기 전용으로 박혀 있던 값들. 손으로 쓴 경기 프로파일에는 이 키가 없으므로 기본값이
# 경기 값이다 — 운영(북부·남부) 동작은 한 글자도 안 바뀐다. 생성 프로파일(tools/profiles/*.json)은
# 자기 시도 값을 들고 온다.
SIDO_WORDS = list(P.get('sido_words') or ['경기'])          # 주소·발신처가 이 말로 시작하면 우리 시도
WIDE_LABEL = P.get('wide_label', '경기도')                   # 시도 전역 발표의 표시명
WRN_STN = int(P.get('wrn_stn', 109))                        # 기상청 특보 API stnId (109 수도권·105 강원…)
_wp = P.get('wrn_prefix', 'L101')
WRN_PREFIX = tuple(_wp) if isinstance(_wp, (list, tuple)) else _wp   # 시도 육상 특보구역 코드 접두(통합시는 둘)
PM_SIDO = P.get('pm_sido', '경기')                           # 에어코리아 sidoName
# 발신처 '경기도 광주시'·'경기북부 동두천시'·'강원특별자치도 춘천시' 에서 시군을 뽑는 정규식
_SIDO_SIGUN_RE = _re.compile('(?:' + '|'.join(_re.escape(w) for w in SIDO_WORDS)
                             + r')(?:특별자치도|특별자치시|광역시|특별시|도|북부|남부)*\s*([가-힣]+?)(시|군|구)')
UNIT_ALIAS = P.get('unit_alias') or {}                      # 새 이름 → 프로파일 단위 (인천 제물포구→중구)


def _unit_from_match(m):
    """정규식 결과 → 프로파일 단위명. 시·군은 접미사를 뗀 이름('춘천'), 구는 붙인 이름('남동구')."""
    name = m.group(1) if m.group(2) in ('시', '군') else m.group(1) + m.group(2)
    return UNIT_ALIAS.get(name, name)



def now_str():
    return datetime.now().strftime('%H:%M:%S')


# ============================================================
# 1-A. AWS 방재기상관측 — 관서별 실측 강수 (기상청 공식 누적)
# ============================================================
# 왜 필요한가: rain_cumul(자체누적)은 RN1을 우리가 직접 쌓아 만든 값이라
#   서버·cron이 한 시간 멈추면 그 시간이 0으로 빠져 '실제보다 적게' 나온다
#   — 호우 상황에서 가장 나쁜 실패 방향. AWS는 기상청이 계산한 공식 누적을 준다.
# 지점 목록은 apihub stn_inf(inf=AWS)를 법정동코드(LAW_ID 앞5자리)로 매칭해 뽑았다.
#   ※ 지점'명'으로 매칭하면 오탐남(포항시남구 → '구리'로 걸림). 코드로만 매칭할 것.
#   ※ 이 매핑 덕에 고양(덕양 41281)과 일산(41285/41287)이 처음으로 진짜 분리된다.
AWS_STATIONS = P['aws_stations']
AWS_REP = P.get('aws_rep') or {}   # 관서 대표 관측소(기온·습도·바람) — 네이버 '지역 날씨'가 보여 주는 지점과 같게 정했다
# 일산은 관측소가 1개뿐 → 그게 결측이면 인접 관서로 대체하고 화면에 대체 사실을 표기한다
AWS_FALLBACK = P['aws_fallback']


def _aws_num(v):
    """AWS 강수·풍속 값 → float. 결측은 None.

    ⚠ 0으로 바꾸면 호우 중에 '비 안 옴'으로 표시된다 — 가장 위험한 오표시.
    결측 표기가 -99/-99.9/-9 등으로 섞여 나오므로 특정 값이 아니라 '음수 전체'를
    결측으로 본다. 강수량·풍속은 음수가 존재할 수 없으므로 안전하다.
    (기온 등 음수가 정상인 항목에는 이 함수를 쓰지 말 것.)
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f < 0 else f


# ============================================================
# 0. 전국 공통 자료 공유 캐시 (2026-09-19 전국 확장 — 공공데이터포털 한도 대책)
#
# 특보·재난문자·산불·AWS·하천수위·미세먼지는 '전국 자료를 통째로' 받아 시도별로 골라 쓰는데,
# 시도 프로파일이 각자 부르면 같은 응답을 시도 수만큼 다시 받는다(경기 둘일 땐 2배, 17개면 17배 —
# 하루 9만 회, 포털 한도 초과). 여기서는 한 회차에 한 번만 받아 .tmp/shared/ 에 두고 나눠 쓴다.
#   · 프로파일들이 동시에 뜨므로 파일 잠금으로 '먼저 온 쪽이 받고 나머지는 기다렸다 읽는다'.
#   · 응답 원문(바이트)만 저장 — 파싱·관할 판정은 프로파일마다 지금처럼 각자 한다.
#   · 실패 응답은 저장하지 않는다(호출측이 예외를 받아 이전 값 보존).
# ============================================================
import base64 as _b64
import os as _os
import time as _time

SHARED_DIR = ROOT / '.tmp' / 'shared'
SHARED_MAX_AGE = None        # None=호출측 기본값, 0=항상 새로 받기(알리미), 숫자=초


class _CachedResp:
    """requests.Response 의 최소 흉내 — 호출측 코드를 안 바꾸기 위해."""
    def __init__(self, content, status_code, encoding=None):
        self.content = content
        self.status_code = status_code
        self.encoding = encoding

    @property
    def text(self):
        return self.content.decode(self.encoding or 'utf-8', errors='replace')

    def json(self):
        return json.loads(self.content.decode(self.encoding or 'utf-8', errors='replace'))

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code} Server Error (cached fetch)')


def shared_get(key, url, params=None, timeout=15, max_age=240, headers=None):
    """전국 공통 GET — key 별로 .tmp/shared/<key>.json 에 max_age 초 동안 공유.
    같은 key 를 프로파일마다 다른 매개변수로 부르면 안 된다(stnId 처럼 다르면 key 에 넣을 것)."""
    age_limit = SHARED_MAX_AGE if SHARED_MAX_AGE is not None else max_age
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    path = SHARED_DIR / f'{key}.json'
    lock = SHARED_DIR / f'{key}.lock'

    def _read():
        try:
            j = json.loads(path.read_text(encoding='utf-8'))
            if _time.time() - j['ts'] <= age_limit:
                return _CachedResp(_b64.b64decode(j['b64']), j['status'])
        except Exception:
            pass
        return None

    cached = _read()
    if cached is not None and age_limit > 0:
        return cached

    # 잠금 — 먼저 온 프로세스가 받는다. 다른 프로세스는 최대 25초 기다렸다가 캐시를 읽는다.
    got_lock = False
    try:
        try:
            if lock.exists() and _time.time() - lock.stat().st_mtime > 90:
                lock.unlink()                       # 죽은 프로세스가 남긴 잠금
            fd = _os.open(str(lock), _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
            _os.close(fd)
            got_lock = True
        except FileExistsError:
            for _ in range(125):
                _time.sleep(0.2)
                cached = _read()
                if cached is not None and age_limit > 0:
                    return cached
                if not lock.exists():
                    break
        # API허브가 가끔 첫 응답을 15초 넘게 끌다 끊는다(2026-09-20 실측: 직접 호출 1~3초, 간헐적 ReadTimeout).
        # 한 번 더, 두 배 여유로 다시 묻는다 — 전국 공통 자료라 한 번 실패하면 시도 15개가 같이 빈다.
        try:
            r = requests.get(url, params=params, timeout=timeout, headers=headers)
        except requests.exceptions.Timeout:
            _time.sleep(1.5)
            r = requests.get(url, params=params, timeout=timeout * 2, headers=headers)
        if r.status_code == 200:
            try:
                _atomic_write_text(path, json.dumps({'ts': _time.time(), 'status': r.status_code,
                                                     'b64': _b64.b64encode(r.content).decode('ascii')}))
            except Exception:
                pass
            # 시각이 든 키(aws_min_<5분칸>·mid_fcst_<발표시각>)가 하루 300개씩 쌓이지 않게 — 6시간 지난 캐시는 지운다
            try:
                _cut = _time.time() - 6 * 3600
                for _f in SHARED_DIR.glob('*.json'):
                    if _f.stat().st_mtime < _cut:
                        _f.unlink()
            except Exception:
                pass
        return _CachedResp(r.content, r.status_code)
    finally:
        if got_lock:
            try:
                lock.unlink()
            except Exception:
                pass


def _aws_request():
    """AWS 매분자료 요청 주소와 공유 캐시 키. tm2 = 지금−10분(완결 자료), 키는 5분 칸.
    캐시 키에 5분 칸을 넣는 이유: 키가 'aws_min' 하나면 다음 회차(5분 뒤)가 앞 회차 묶음이 3~4분 전에 쓴 응답을
    물려받아 자료가 설계(10분)보다 5~8분 더 늦었다(2026-09-20 실측: 12:36 회차가 12:21 자료). 같은 회차의
    북부·남부·시도 15 프로세스는 같은 칸이라 한 번만 받는다."""
    tm = (datetime.now() - timedelta(minutes=10)).strftime('%Y%m%d%H%M')
    url = ('https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-aws2_min'
           f'?tm2={tm}&stn=0&disp=0&help=0&authKey={KMA_APIHUB_KEY}')
    bucket = tm[:-2] + f'{int(tm[-2:]) // 5 * 5:02d}'
    return f'aws_min_{bucket}', url


def _aws_rn12_fill(obs):
    """대표 관측소 12시간 강수(RN-12H)가 결측일 때 대신 쓸 값 {stn: mm}.

    단양(601)처럼 기상청이 RN-12H 만 -99.9 로 보내는 지점이 있다(2026-11-12 확인 — 일누적·1시간은 정상).
    같은 지점의 일누적(RN-DAY) 기록으로 계산한다: 12시간 = 지금 누적 − 12시간 전 누적
    (자정을 넘으면 어제 마지막 누적을 더한다). 다른 지점 값은 섞지 않는다(2026-11-06 결정).
    12시간 전 기록이 없거나(서버 시작 직후) 중간에 1시간 넘게 비면 계산하지 않는다 → 화면은 '—' 그대로.
    """
    path = TMP / 'aws_rnday_hist.json'
    try:
        hist = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        hist = {}
    reps = {str(v) for v in AWS_REP.values()}
    fill = {}
    for stn, o in obs.items():
        if str(stn) not in reps or o.get('rnday') is None or not o.get('tm'):
            continue
        try:
            now = datetime.strptime(str(o['tm'])[:12], '%Y%m%d%H%M')
        except ValueError:
            continue
        h = hist.setdefault(str(stn), {})
        h[now.strftime('%Y%m%d%H%M')] = o['rnday']
        # 13시간 넘은 기록은 버린다
        for k in [k for k in h if datetime.strptime(k, '%Y%m%d%H%M') < now - timedelta(hours=13)]:
            del h[k]
        if o.get('rn12h') is not None:
            continue
        pts = sorted((datetime.strptime(k, '%Y%m%d%H%M'), v) for k, v in h.items())
        start = now - timedelta(hours=12)
        base = [p for p in pts if abs((p[0] - start).total_seconds()) <= 600]
        if not base:
            # 기록이 아직 없어도 정오가 지났고 오늘 누적이 0이면 12시간도 0(12시간이 전부 오늘 안이다)
            if now.hour >= 12 and o['rnday'] == 0:
                fill[stn] = 0.0
            continue
        seq = [p for p in pts if p[0] >= base[0][0]]
        if any((b[0] - a[0]) > timedelta(hours=1) for a, b in zip(seq, seq[1:])):
            continue
        # 날짜가 바뀌는 곳마다 그 전날 마지막 누적을 더해 이어 붙인다
        total, prev = 0.0, seq[0]
        day = lambda t: (t - timedelta(minutes=1)).date()   # 00:00 기록은 '어제 하루 합계'라 어제 쪽으로 친다
        for p in seq[1:]:
            if day(p[0]) != day(prev[0]):
                total += (prev[1] or 0)
            prev = p
        val = round(total + (seq[-1][1] or 0) - (seq[0][1] or 0), 1)
        if val >= 0:
            fill[stn] = val
    try:
        _atomic_write_bytes(path, json.dumps(hist, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    except Exception:
        pass
    return fill


def fetch_aws_rain():
    """AWS 매분자료 1회 호출로 전 관서 실측 강수·돌풍 수집.

    엔드포인트는 cgi-bin 경로이고 EUC-KR이다(/url/ 경로로 부르면 404).
    컬럼: YYMMDDHHMI STN WD1 WS1 WDS WSS WD10 WS10 TA RE RN-15m RN-60m RN-12H RN-DAY HM PA PS TD
    반환: {관서: {rn15, rn60, rn12h, rnday, wss, station, stn, ok, total, (alt)}}
          자료 없으면 {'ok': 0, 'total': N} — 0으로 채우지 않는다.
    실패 시 예외 → 호출측이 이전 값 보존.
    """
    if not KMA_APIHUB_KEY:
        return {}
    key, url = _aws_request()
    r = shared_get(key, url, timeout=15, max_age=240)
    r.raise_for_status()
    r.encoding = 'euc-kr'
    text = r.text
    if '활용신청' in text[:300]:
        raise RuntimeError('AWS 활용신청 필요(403)')

    obs = {}
    for line in text.split('\n'):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        f = s.split()
        if len(f) < 14:
            continue
        try:
            stn = int(f[1])
        except ValueError:
            continue
        obs[stn] = {'wds': _aws_num(f[4]), 'wss': _aws_num(f[5]), 'wd10': _aws_num(f[6]),
                    'ws10': _aws_num(f[7]), 'ta': _aws_num(f[8]),
                    'rn15': _aws_num(f[10]), 'rn60': _aws_num(f[11]),
                    'rn12h': _aws_num(f[12]), 'rnday': _aws_num(f[13]),
                    'hm': _aws_num(f[14]) if len(f) > 14 else None, 'tm': f[0]}
    if not obs:
        raise RuntimeError('AWS 응답에 관측 지점 없음')

    def pick(area):
        """강수 지점 — 기온·습도와 같은 대표 관측소(aws_rep). 값을 여러 지점에서 섞으면 헷갈린다(2026-11-06 결정).
        대표 관측소 강수 자료가 없을 때만 관할에서 가장 많이 온 지점으로 대신한다."""
        best, ok, rep = None, 0, None
        for stn, sname in AWS_STATIONS.get(area, []):
            o = obs.get(stn)
            if not o or all(o[k] is None for k in ('rn15', 'rn60', 'rn12h', 'rnday')):
                continue
            ok += 1
            key = (o['rn60'] or 0, o['rn12h'] or 0, o['rnday'] or 0)
            if stn == AWS_REP.get(area):
                rep = (key, stn, sname, o)
            if best is None or key > best[0]:
                best = (key, stn, sname, o)
        return rep or best, ok

    def pick_wind(area):
        """관서 안에서 '바람이 가장 센 지점'을 따로 고른다.
        ⚠ 대표 관측소의 돌풍을 그대로 쓰면 관할 최대 돌풍을 놓친다 — 강풍은 별도로 뽑아야 한다."""
        best = None
        for stn, sname in AWS_STATIONS.get(area, []):
            o = obs.get(stn)
            if not o or o.get('wss') is None:
                continue
            if best is None or o['wss'] > best[0]:
                best = (o['wss'], stn, sname, o)
        if not best:
            return None
        _, stn, sname, o = best
        return {'wss': o['wss'], 'wds': o.get('wds'), 'ws10': o.get('ws10'),
                'station': sname, 'stn': stn}

    def pick_obs(area):
        """기온·습도·풍향의 대표 지점 — 프로파일 aws_rep 지점 먼저, 없으면 목록 순서로 기온이 있는 곳."""
        po = None
        for stn, sname in sorted(AWS_STATIONS.get(area, []), key=lambda x: x[0] != AWS_REP.get(area)):
            o = obs.get(stn)
            if not o:
                continue
            if po is None and o.get('ta') is not None and -60 < o['ta'] < 60:
                po = {'ta': o['ta'], 'hm': o.get('hm'), 'wd10': o.get('wd10'), 'ws10': o.get('ws10'),
                      'tm': o.get('tm'), 'station': sname, 'stn': stn}
            elif po is not None:
                # 대표 지점에 습도·바람 센서가 없으면(양주 남면처럼) 관할 안 다른 지점 값으로 채운다
                for k in ('hm', 'wd10', 'ws10'):
                    if po.get(k) is None and o.get(k) is not None:
                        po[k] = o[k]
        return po

    rn12_fill = _aws_rn12_fill(obs)   # 대표 관측소 12시간 강수가 결측(-99.9)일 때 같은 지점 일누적 기록으로 메운다

    out = {}
    for area in AWS_STATIONS:
        best, ok = pick(area)
        total = len(AWS_STATIONS.get(area, []))
        alt = None
        if best is None:
            # 일산처럼 관측소가 전멸한 경우 — 프로파일이 정한 대체 관서, 그다음 가까운 이웃 순서(전국판:
            # 부산 해운대 937 처럼 원장엔 있는데 자료를 안 보내는 지점이 있다). 대체분은 alt 로 표기한다.
            for cand in [AWS_FALLBACK.get(area)] + list((P.get('aws_neighbors') or {}).get(area, [])):
                if not cand or cand == area:
                    continue
                b2, ok2 = pick(cand)
                if b2 is not None:
                    alt, best, ok = cand, b2, ok2          # ⚠ ok도 대체분으로 갱신(안 하면 화면에 '자료없음'으로 뜸)
                    total = len(AWS_STATIONS.get(cand, []))   # ok/total을 같은 관서 기준으로 통일
                    break
        if best is None:
            out[area] = {'ok': 0, 'total': total}      # 자료없음 (0 아님)
            continue
        _, stn, sname, o = best
        out[area] = {'rn15': o['rn15'], 'rn60': o['rn60'], 'rn12h': o['rn12h'],
                     'rnday': o['rnday'], 'wss': o['wss'], 'station': sname,
                     'stn': stn, 'ok': ok, 'total': total}
        if o['rn12h'] is None and rn12_fill.get(stn) is not None:
            out[area]['rn12h'] = rn12_fill[stn]
            out[area]['rn12h_calc'] = True      # 기상청이 12시간 값을 안 보내 같은 지점 일누적으로 계산한 값
        # 강풍은 별도 지점 — 관할 내 '가장 센 바람'(대체 관서를 썼으면 그쪽 기준)
        w = pick_wind(alt or area)
        if w:
            out[area]['wind'] = w
        po = pick_obs(alt or area)
        if po:
            po['feels'] = feels_like(po['ta'], po.get('hm'), po.get('ws10'))   # 시를 나눠 맡는 관서(청주서부)가 자기 체감온도를 쓴다
            out[area]['obs'] = po                      # 실황 대체용(기온·습도·풍향) — 아래 fetch_all_regions 참조
        if alt:
            out[area]['alt'] = alt                     # 대체 관서 — 화면에 반드시 표기
    # 지점별 실측 — 관서 상세 지도의 ▲ 에 마우스를 올리면 보인다
    for area, row in out.items():
        row['stations'] = {str(stn): {k: obs[stn].get(k) for k in ('ta', 'hm', 'rn60', 'rn12h', 'rnday', 'ws10', 'wss', 'wd10', 'tm')}
                           for stn, _ in AWS_STATIONS.get(area, []) if stn in obs}
    return out


# ============================================================
# 1. 기상청 단기예보 (시군별 현재 기온/강수/풍속/습도/날씨)
# ============================================================

def fcst_base_time():
    """단기예보 발표시각: 02/05/08/11/14/17/20/23시.
    발표 후 10분 이내엔 이전 발표분 사용."""
    now = datetime.now()
    issue = [23, 20, 17, 14, 11, 8, 5, 2]
    target = now - timedelta(minutes=10)
    for h in issue:
        cand = target.replace(hour=h, minute=0, second=0, microsecond=0)
        if cand <= target:
            return cand.strftime('%Y%m%d'), f'{h:02d}00'
    # 새벽 0~1시: 전날 23시
    prev = (target - timedelta(days=1)).replace(hour=23, minute=0, second=0)
    return prev.strftime('%Y%m%d'), '2300'


def parse_pcp(val):
    """PCP(1시간 강수량) 문자열을 mm 숫자로.

    기상청 표기: '강수없음' | '1.0mm 미만' | '1.2mm' | '30.0~50.0mm' | '50.0mm 이상'
    ⚠ 'mm'을 먼저 지우므로, 이 아래 비교문에 'mm'을 넣으면 영원히 안 맞는다.
      (과거 `val == '1mm 미만'` 검사가 이 때문에 죽은 코드였고, 실제 값 '1.0mm 미만'이
       숫자변환 실패로 0이 되어 '약한 비'가 '비 안 옴'으로 표시됐다.)
    """
    if val is None:
        return 0
    s = str(val).strip()
    if not s or s in ('강수없음', '-', 'null'):
        return 0
    s = s.replace('mm', '').strip()          # '1.0 미만' · '30.0~50.0' · '50.0 이상'
    try:
        if '미만' in s:                       # '1.0 미만' → 절반으로 대표(0.5)
            return float(s.replace('미만', '').strip()) / 2
        if '~' in s:                          # '30.0~50.0' → 중간값(40)
            lo, hi = s.split('~')[:2]
            return (float(lo.strip()) + float(hi.strip())) / 2
        if '이상' in s:                       # '50.0 이상' → 하한 + 10(60)
            return float(s.replace('이상', '').strip()) + 10
        return float(s)
    except ValueError:
        return 0


def parse_sno(val):
    """SNO(1시간 신적설) 문자열을 cm 숫자로 — 단기예보 응답에 이미 들어 있던 항목(2026-10-30부터 읽는다).
    기상청 표기: '적설없음' | '1.0cm 미만' | '1.2cm' | '5.0cm 이상'  (parse_pcp 와 같은 대표값 규칙)"""
    if val is None:
        return 0
    s = str(val).strip()
    if not s or s in ('적설없음', '-', 'null', '0'):
        return 0
    s = s.replace('cm', '').strip()
    try:
        if '미만' in s:
            return float(s.replace('미만', '').strip()) / 2
        if '~' in s:
            lo, hi = s.split('~')[:2]
            return (float(lo.strip()) + float(hi.strip())) / 2
        if '이상' in s:
            return float(s.replace('이상', '').strip()) + 5
        return float(s)
    except ValueError:
        return 0


def deg_to_dir(deg):
    """풍향 0~360° → 16방위 한글."""
    try:
        deg = float(deg)
    except (TypeError, ValueError):
        return '-'
    dirs = ['북', '북북동', '북동', '동북동', '동', '동남동', '남동', '남남동',
            '남', '남남서', '남서', '서남서', '서', '서북서', '북서', '북북서']
    idx = int((deg + 11.25) // 22.5) % 16
    return dirs[idx]


def feels_like(temp, humid, wind):
    """체감온도 (간이식). 기온·습도·풍속 기반.
    - 10°C 이하: 윈드칠(풍속 영향 큼)
    - 27°C 이상: 열지수(습도 영향 큼)
    - 그 사이: 기온 거의 그대로 (풍속 약간 보정)
    """
    if temp is None or humid is None or wind is None:
        return None
    try:
        t, h, w = float(temp), float(humid), float(wind)
    except (TypeError, ValueError):
        return None
    # 윈드칠 (기온이 낮을 때)
    if t <= 10 and w >= 1.3:
        v = w * 3.6  # m/s → km/h
        wc = 13.12 + 0.6215 * t - 11.37 * (v ** 0.16) + 0.3965 * t * (v ** 0.16)
        return round(wc, 1)
    # 열지수 (기온이 높을 때)
    if t >= 27 and h >= 40:
        # 간이 열지수
        hi = t + 0.348 * (h / 100 * 6.105 * 2.71828 ** (17.27 * t / (237.7 + t))) - 0.7 * w - 4.25
        return round(hi, 1)
    # 보통 범위: 기온 - 풍속 영향
    return round(t - max(0, (w - 2) * 0.3), 1)


VILAGE_CACHE_PATH = TMP / 'vilage_fcst.json'


def _vilage_cache_load():
    try:
        return json.loads(VILAGE_CACHE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _sky_icon(pty, sky, hour):
    """강수형태·하늘상태 → (아이콘, 글자). 아이콘은 밤/낮 구분."""
    pty_map = {'1': '비', '2': '비/눈', '3': '눈', '4': '소나기',
               '5': '빗방울', '6': '진눈깨비', '7': '눈날림'}
    sky_map = {'1': '맑음', '3': '구름많음', '4': '흐림'}
    if pty in ('1', '4', '5'):        icon = '🌧'
    elif pty in ('2', '3', '6', '7'): icon = '🌨'
    elif sky == '4':                  icon = '☁'
    elif sky == '3':                  icon = '🌥'
    else:
        icon = '🌙' if (hour < 6 or hour >= 19) else '☀'
    return icon, (pty_map.get(pty) if pty != '0' else None) or sky_map.get(sky, '맑음')


def blend_hourly(hourly, area, obs):
    """시간대별 예보의 앞부분을 더 새 자료로 덮는다 — 날씨누리 시간별 예보와 같은 방식.
    단기예보는 3시간마다 나와 낮 기온이 3~4도 빗나가기도 한다(2026-11-06 청주 11시: 단기 7도, 초단기 11도).
    지금 칸 = 실측, 앞 6시간 = 초단기예보(1시간마다 발표), 그 뒤 = 단기예보. 강수확률은 초단기에 없어 단기 값을 둔다."""
    ultra = {u['time'][:2]: u for u in (_ULTRA_CACHE.get(area) or [])}
    now_key = datetime.now().strftime('%Y%m%d%H')
    # 새 발표분은 다음 시각부터라(11시 발표 → 12시~) 표에 지금 칸이 없으면 만든다 — 없으면 화면이 12시 값을 '지금'으로 보여 준다
    if hourly and hourly[0]['time'][:10] != now_key and obs.get('t1h') is not None:
        hourly.insert(0, {**hourly[0], 'time': now_key + '00', 'hour': f'{datetime.now().hour}시'})
        del hourly[24:]

    def wind(h, ms, deg):
        if ms is not None:
            h['wind_ms'] = round(float(ms), 1)
        if deg is not None:
            h['wind_deg'] = float(deg)
            h['wind_dir'] = deg_to_dir(deg)

    for h in hourly[:7]:
        if h['time'][:10] == now_key:
            if obs.get('t1h') is None:
                continue
            h['temp'] = round(float(obs['t1h']), 1)
            if obs.get('reh') is not None:
                h['humid'] = int(float(obs['reh']))
            if obs.get('rn1') is not None:
                h['rain_mm'] = float(obs['rn1'])
            wind(h, obs.get('wsd'), obs.get('vec'))
        else:
            u = ultra.get(h['time'][8:10])
            if not u or u.get('temp') is None:
                continue
            h['temp'] = round(float(u['temp']), 1)
            if u.get('reh') is not None:
                h['humid'] = int(u['reh'])
            if u.get('rain_mm') is not None:
                h['rain_mm'] = u['rain_mm']
            wind(h, u.get('wsd'), u.get('vec'))
            if u.get('sky') is not None:
                h['icon'], h['weather'] = _sky_icon(str(int(u.get('pty') or 0)), str(int(u['sky'])), int(h['time'][8:10]))
        fl = feels_like(h['temp'], h['humid'], h['wind_ms'])
        h['feels_like'] = round(fl, 1) if fl is not None else h['temp']


# 날씨누리 메인(https://www.weather.go.kr/w/index.do)이 동을 고르면 부르는 화면 조각.
# 공개 API 가 아니라 화면이 바뀌면 끊길 수 있다 — 끊기면 blend_hourly(초단기·단기예보) 값으로 그대로 돈다.
WNURI_MAIN = 'https://www.weather.go.kr/w/wnuri-fct2021/main/'
WNURI_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.weather.go.kr/w/index.do'}
_DIR16 = ['북', '북북동', '북동', '동북동', '동', '동남동', '남동', '남남동',
          '남', '남남서', '남서', '서남서', '서', '서북서', '북서', '북북서']


def _wnuri_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _wnuri_dir_deg(name):
    return _DIR16.index(name) * 22.5 if name in _DIR16 else None


def _parse_wnuri_current(t):
    """current-weather.do → 메인 '현재 날씨' 칸의 값. 기온이 없으면 None."""
    import re as _re
    m = _re.search(r'class="tmp">\s*(-?[\d.]+)', t)
    if not m:
        return None
    out = {'temp': float(m.group(1))}
    m = _re.search(r'updated-at[^>]*>\s*<span>[^<]*?(\d{1,2}:\d{2})\s*</span>', t)
    out['time'] = m.group(1) if m else ''
    m = _re.search(r'체감\((-?[\d.]+)', t)
    out['feels'] = float(m.group(1)) if m else None
    m = _re.search(r'<span>최저</span>\s*<span>([^<]*)</span>\s*<span>최고</span>\s*<span>([^<]*)</span>', t)
    out['tmin'] = _wnuri_num(m.group(1).replace('℃', '')) if m else None
    out['tmax'] = _wnuri_num(m.group(2).replace('℃', '')) if m else None
    m = _re.search(r'ic-hm.*?class="val">\s*(\d+)', t, _re.S)
    out['humid'] = int(m.group(1)) if m else None
    m = _re.search(r'ic-wind.*?class="val">\s*([가-힣]*)\s*(-?[\d.]+)', t, _re.S)
    out['wind_dir'] = m.group(1) if m else None
    out['wind'] = float(m.group(2)) if m else None
    return out


def _parse_wnuri_hourly(t):
    """digital-forecast.do → {'YYYYMMDDHHMM': 시각별 값}. 메인 '시간별 예보' 1시간 간격 표."""
    import re as _re
    rows = {}
    for m in _re.finditer(r'<ul class="item (?:vs|s)-item[^"]*"[^>]*?data-date="([\d-]+)"\s+data-time="(\d\d):00"[^>]*>(.*?)</ul>', t, _re.S):
        d, hh, b = m.groups()
        tm = _re.search(r'class="hid feel">\s*(-?\d+(?:\.\d+)?)℃\s*<span class="chill">\((-?\d+(?:\.\d+)?)℃', b)
        if not tm:
            continue
        row = {'temp': float(tm.group(1)), 'feels_like': float(tm.group(2))}
        x = _re.search(r'class="wic [^"]*" title="([^"]*)"', b)
        if x:
            row['weather'] = x.group(1)
        x = _re.search(r'강수량: </span><span>([^<]*)</span>', b)
        if x:
            row['rain_mm'] = parse_pcp(x.group(1))
        x = _re.search(r'강수확률: </span><span>(\d+)%', b)
        if x:
            row['rain_pop'] = int(x.group(1))
        x = _re.search(r'class="wdic [^"]*" title="([가-힣]+?)풍?"', b)
        if x:
            row['wind_dir'] = x.group(1)
            row['wind_deg'] = _wnuri_dir_deg(x.group(1))
        x = _re.search(r'class="wspd">\s*(-?[\d.]+)', b)
        if x:
            row['wind_ms'] = float(x.group(1))
        x = _re.search(r'습도: </span><span>(\d+)%', b)
        if x:
            row['humid'] = int(x.group(1))
        rows[d.replace('-', '') + hh + '00'] = row
    return rows


def fetch_wnuri_local():
    """관서별 날씨누리 메인 값 — 프로파일 wnuri_dong 의 동 기준. 반환 {관서: {now, hourly}}. 실패한 관서는 빠진다."""
    out = {}
    for nm, d in (P.get('wnuri_dong') or {}).items():
        q = {'code': d['code'], 'unit': 'm/s', 'lat': d['lat'], 'lon': d['lon']}
        try:
            r = shared_get(f"wnuri_cur_{d['code']}", WNURI_MAIN + 'current-weather.do', max_age=240,
                           params={**q, 'aws': 'N'}, timeout=15, headers=WNURI_HEADERS)
            r.raise_for_status()
            now = _parse_wnuri_current(r.content.decode('utf-8', 'replace'))
            if not now:
                print(f'    날씨누리 {nm}: 현재값 없음')
                continue
            r = shared_get(f"wnuri_dig_{d['code']}", WNURI_MAIN + 'digital-forecast.do', max_age=540,
                           params={**q, 'hr1': 'Y'}, timeout=20, headers=WNURI_HEADERS)
            r.raise_for_status()
            out[nm] = {'now': now, 'hourly': _parse_wnuri_hourly(r.content.decode('utf-8', 'replace'))}
        except Exception as e:
            print(f'    날씨누리 {nm}: {type(e).__name__}')
    return out


def _wnuri_merge_hourly(hourly, wn):
    """시간대별 표를 날씨누리 값으로 덮는다. 지금 칸은 대표 관측소 실측을 두고,
    적설(snow_cm)은 날씨누리 표에 숫자가 없어 단기예보 값을 둔다."""
    now_key = datetime.now().strftime('%Y%m%d%H')
    for h in hourly:
        row = wn['hourly'].get(h['time'])
        if not row or h['time'][:10] == now_key:
            continue
        h.update(row)
        w = row.get('weather') or ''
        hr = int(h['time'][8:10])
        if any(k in w for k in ('비', '소나기')):
            h['icon'] = '🌧'
        elif '눈' in w:
            h['icon'] = '🌨'
        elif w == '흐림':
            h['icon'] = '☁'
        elif w == '구름많음':
            h['icon'] = '🌥'
        elif w:
            h['icon'] = '🌙' if (hr < 6 or hr >= 19) else '☀'


def _today_tmn(nx, ny):
    """그 격자의 오늘 최저(TMN). 오늘 02시 발표분에 들어 있어 낮에 불러도 받을 수 있다(자정~02시엔 전날 23시 발표분)."""
    now = datetime.now()
    today = now.strftime('%Y%m%d')
    if now.hour >= 3:
        base_date, base_time = today, '0200'
    else:
        base_date, base_time = (now - timedelta(days=1)).strftime('%Y%m%d'), '2300'
    r = requests.get('https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst',
                     params={'serviceKey': DATA_KEY, 'pageNo': 1, 'numOfRows': 1000, 'dataType': 'JSON',
                             'base_date': base_date, 'base_time': base_time, 'nx': nx, 'ny': ny}, timeout=15)
    r.raise_for_status()
    for it in r.json()['response']['body']['items']['item']:
        if it['category'] == 'TMN' and it['fcstDate'] == today:
            return float(it['fcstValue'])
    return None


def _wnuri_today_minmax(wn):
    """날씨누리의 오늘 최고·최저를 자정까지 유지한다. 날씨누리는 때가 지나면 값을 '-' 로 비우기 때문이다.
    시를 나눠 맡는 관서는 비었을 때 자기 격자의 단기예보 TMN 으로 채운다(본 관서 값을 빌려 쓰지 않게)."""
    path = TMP / 'today_wnuri_minmax.json'
    today = datetime.now().strftime('%Y%m%d')
    try:
        store = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        store = {}
    if store.get('date') != today:
        store = {'date': today, 'regions': {}}
    recs = store['regions']
    for nm, w in wn.items():
        rec = recs.setdefault(nm, {})
        for k in ('tmax', 'tmin'):
            if w['now'].get(k) is not None:
                rec[k] = w['now'][k]
    for nm in (P.get('alias') or {}):
        d = (P.get('wnuri_dong') or {}).get(nm) or {}
        rec = recs.setdefault(nm, {})
        if rec.get('tmin') is None and d.get('nx') is not None:
            try:
                rec['tmin'] = _today_tmn(d['nx'], d['ny'])
            except Exception as e:
                print(f'    {nm} 오늘 최저 수집 실패(본 관서 값 사용): {type(e).__name__}')
    try:
        _atomic_write_text(path, json.dumps(store, ensure_ascii=False))
    except Exception as e:
        print(f'    오늘 최고·최저 저장 실패(무시): {type(e).__name__}')
    return recs


def apply_wnuri_local(data):
    """시간대별 예보와 오늘 최고·최저를 날씨누리 메인 값으로 맞춘다. 현재값은 대표 관측소(AWS_REP) 실측 그대로.
    시를 나눠 맡는 관서(청주서부)는 regions 에 없어 현재값·예보를 data['local'] 로 따로 싣는다."""
    import copy as _copy
    wn = fetch_wnuri_local()
    print(f'  ✓ 날씨누리 {len(wn)}/{len(P.get("wnuri_dong") or {})}개 관서')
    day = _wnuri_today_minmax(wn)
    by = {r.get('name'): r for r in data.get('regions') or []}
    for r in data.get('regions') or []:
        w = wn.get(r.get('name'))
        rec = day.get(r.get('name')) or {}
        det = r.setdefault('detail', {})
        for k in ('tmax', 'tmin'):
            if rec.get(k) is not None:
                r[k] = rec[k]
                det[k] = rec[k]
        if w:
            _wnuri_merge_hourly(det.get('hourly') or [], w)

    local = {}
    now_key = datetime.now().strftime('%Y%m%d%H')
    for nm, sg in (P.get('alias') or {}).items():
        base, w = by.get(sg), wn.get(nm)
        po = ((data.get('aws') or {}).get(nm) or {}).get('obs') or {}
        if not base or po.get('ta') is None:
            continue
        hourly = _copy.deepcopy((base.get('detail') or {}).get('hourly') or [])
        if w:
            _wnuri_merge_hourly(hourly, w)
        humid = round(po['hm']) if po.get('hm') is not None else None
        for h in hourly:
            if h['time'][:10] == now_key:
                h['temp'] = po['ta']
                if po.get('feels') is not None:
                    h['feels_like'] = po['feels']
                if humid is not None:
                    h['humid'] = humid
                if po.get('ws10') is not None:
                    h['wind_ms'] = po['ws10']
        tm = str(po.get('tm') or '')
        local[nm] = {'temp': po['ta'], 'humid': humid, 'wind': po.get('ws10'),
                     'wind_dir': deg_to_dir(po['wd10']) if po.get('wd10') is not None else None, 'vec': po.get('wd10'),
                     'feels': po.get('feels'), 'time': tm[8:10] + ':' + tm[10:12] if len(tm) >= 12 else '',
                     'station': po.get('station', ''), 'src': 'aws',
                     'tmax': (day.get(nm) or {}).get('tmax'), 'tmin': (day.get(nm) or {}).get('tmin'), 'hourly': hourly}
    data['local'] = local


def fetch_one_region_forecast(region):
    """단기예보(3일치). 발표시각(base_time)이 같으면 응답도 같으므로 캐시한다.

    왜: 단기예보는 하루 8번(02·05·08·11·14·17·20·23시)만 새로 나온다. 5분 cron이
    매번 부르면 시군 하나당 하루 288번 부르면서 같은 답을 받는다. 지역이 둘로 늘면
    공공데이터포털 호출이 하루 9천여 건 늘어 일일 한도를 건드릴 수 있다.
    발표시각을 열쇠로 캐시하면 시군당 하루 8번이면 끝난다(≈97% 감소).
    ⚠ 캐시 열쇠에 nx·ny를 반드시 넣을 것 — 빼면 모든 시군이 첫 시군의 예보를 쓴다.
    """
    base_date, base_time = fcst_base_time()
    ck = f"{region['nx']},{region['ny']},{base_date},{base_time}"
    cache = _vilage_cache_load()

    if ck in cache:
        # 캐시엔 '가공 전 예보표'만 담는다. 완성된 결과를 담으면 '지금 이후 24시간'
        # 구간이 발표시각에 얼어붙어 시간이 지나도 옛 시간대가 계속 보인다.
        by_time = {tuple(k.split('|')): v for k, v in cache[ck].items()}
    else:
        url = 'https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst'
        params = {
            'serviceKey': DATA_KEY,
            'pageNo': 1,
            'numOfRows': 1000,
            'dataType': 'JSON',
            'base_date': base_date,
            'base_time': base_time,
            'nx': region['nx'],
            'ny': region['ny'],
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        body = r.json()['response']['body']
        items = body['items']['item']

        # 시각별 카테고리 모음
        by_time = {}
        for it in items:
            key = (it['fcstDate'], it['fcstTime'])
            by_time.setdefault(key, {})[it['category']] = it['fcstValue']

        # 같은 발표시각 것만 남기고 저장 (지난 발표분은 버려 파일이 안 커지게)
        try:
            fresh = {k: v for k, v in cache.items()
                     if k.endswith(f'{base_date},{base_time}')}
            fresh[ck] = {'|'.join(k): v for k, v in by_time.items()}
            _atomic_write_text(VILAGE_CACHE_PATH,
                               json.dumps(fresh, ensure_ascii=False, separators=(',', ':')))
        except Exception as e:
            print(f'    단기예보 캐시 저장 실패(무시): {type(e).__name__}')

    # 시간순 정렬, 현재 시각 이후 24시간
    now = datetime.now()
    sorted_keys = sorted(by_time.keys())
    future = []
    for d, t in sorted_keys:
        dt = datetime.strptime(d + t, '%Y%m%d%H%M')
        if dt >= now.replace(minute=0, second=0, microsecond=0):
            future.append((d, t, dt))
    if not future and sorted_keys:
        d, t = sorted_keys[0]
        future = [(d, t, datetime.strptime(d + t, '%Y%m%d%H%M'))]

    # 24시간 hourly 상세 데이터 구성
    hourly = []
    for d, t, dt in future[:24]:
        cats = by_time[(d, t)]
        pty = cats.get('PTY', '0')
        sky = cats.get('SKY', '1')
        temp = float(cats.get('TMP', 0))
        humid = int(float(cats.get('REH', 0)))
        wind = float(cats.get('WSD', 0))
        rain = parse_pcp(cats.get('PCP', '0'))
        snow = parse_sno(cats.get('SNO'))          # 1시간 신적설(cm) — 대설·결빙 카드
        pop = int(float(cats.get('POP', 0))) if cats.get('POP') else 0
        try: vec = float(cats.get('VEC', 0))
        except: vec = 0

        icon, weather_text = _sky_icon(pty, sky, dt.hour)
        feel = feels_like(temp, humid, wind)

        hourly.append({
            'time': d + t,
            'hour': f'{dt.hour}시',
            'icon': icon,
            'weather': weather_text,
            'temp': round(temp, 1),
            'feels_like': round(feel, 1) if feel is not None else round(temp, 1),
            'rain_mm': rain,
            'snow_cm': snow,
            'rain_pop': pop,
            'wind_ms': round(wind, 1),
            'wind_deg': vec,
            'wind_dir': deg_to_dir(vec),
            'humid': humid,
        })

    # 첫 번째 항목을 현재 값으로 사용 (광역 모드 카드용)
    result = {'name': region['name'], 'temp': 0.0, 'weather': '맑음',
              'rain': 0, 'wind': 0, 'humid': 0, 'level': 'normal',
              'vec': None, 'tmax': None, 'tmin': None, 'pop': 0,
              '_hourly': hourly}

    if hourly:
        h0 = hourly[0]
        result['temp']    = h0['temp']
        result['weather'] = h0['weather']
        result['rain']    = h0['rain_mm']
        result['wind']    = h0['wind_ms']
        result['humid']   = h0['humid']
        result['vec']     = h0['wind_deg']
        result['pop']     = h0['rain_pop']

    # 오늘 일 최고/최저
    # ⚠ 반드시 by_time으로 순회할 것 — items는 '캐시를 안 쓴 회차'에만 만들어진다.
    #   예전엔 여기서 items를 써서, 캐시가 맞는 회차(=5분 주기의 약 97%)마다
    #   UnboundLocalError로 이 함수가 통째로 죽었다. 죽으면 호출부가 '수집 실패'로 보고
    #   직전 값을 되살리므로, 시군 기온·습도가 예보 발표시각 사이(최대 3시간) 얼어붙었다.
    #   갱신 시각(updated)은 매 회차 새로 찍혀서 화면에는 정상으로 보였다 — 그래서
    #   2026-08-17 전체 점검 전까지 아무도 몰랐다. (실측: 의정부 05:10~07:11 22.8° 고정)
    #   by_time은 캐시·비캐시 양쪽 모두에 있다.
    today = now.strftime('%Y%m%d')
    for (fdate, _ftime), cats in by_time.items():
        if fdate != today: continue
        if result['tmax'] is None and 'TMX' in cats:
            try: result['tmax'] = float(cats['TMX'])
            except: pass
        if result['tmin'] is None and 'TMN' in cats:
            try: result['tmin'] = float(cats['TMN'])
            except: pass

    # (weather는 위 308-310에서 hourly[0]=현재 시각 값으로 이미 설정됨.
    #  여기서 루프 마지막 pty/sky로 덮으면 '24시간 뒤' 날씨가 되어버려 제거함.)

    # 위험도 판정: 강수량 기반 (예보값 기준 초기 산정 — 실측 수신 시 fetch_all_regions에서 재산정)
    if result['rain'] >= 20: result['level'] = 'danger'; result['tag'] = '경보'
    elif result['rain'] >= 10: result['level'] = 'warning'; result['tag'] = '호우'
    elif result['rain'] >= 3: result['level'] = 'warning'

    return result


ULTRA_FCST_PATH = TMP / 'ultra_fcst.json'


def _ultra_base():
    """초단기예보 발표시각 — 매시 30분 발표, 안정까지 ~15분. 45분 여유를 둔다."""
    b = datetime.now() - timedelta(minutes=45)
    return b.strftime('%Y%m%d'), b.strftime('%H') + '30'


def fetch_ultra_short_fcst_all():
    """초단기예보 — 관서별 '앞으로 6시간' 강수 예측. (지금 상황판엔 1~6시간 앞을 볼 수단이 없다)

    ⚠ 함정 1: 초단기'실황' RN1은 숫자(0.5)인데 초단기'예보' RN1은 글자('강수없음','1.0mm 미만')다.
              이름이 같아 실황 파서를 재사용하면 조용히 깨진다 → parse_pcp()로 변환.
    ⚠ 함정 2: 초단기예보는 1시간에 한 번(매시 30분)만 갱신된다. 5분 cron마다 10관서를 부르면
              하루 2,880회가 낭비되고 일일 한도를 넘으면 '같은 키'를 쓰는 단기예보·실황까지
              전부 막혀 대시보드가 죽는다. → 발표시각이 바뀔 때만 호출하고 .tmp에 캐시.

    반환: {관서: [{time,'rain_mm','pop','pty','sky','temp','lgt'} …최대 6개]}
    """
    base_date, base_time = _ultra_base()
    # ⚠ 캐시 키에 '스키마 버전'을 붙인다. 발표시각만으로 키를 만들면, 코드에 필드를 새로
    #   추가해도 같은 발표분 동안(최대 1시간) 옛 모양 캐시가 계속 나가 새 필드가 비어 보인다.
    #   (실제로 바람 wsd/vec를 추가한 날 그 증상이 났다.) 필드를 바꿀 때 이 숫자를 올릴 것.
    SCHEMA = 2
    key = f'{base_date}{base_time}v{SCHEMA}'

    # 같은 발표분이면 재호출하지 않는다
    try:
        if ULTRA_FCST_PATH.exists():
            cached = json.loads(ULTRA_FCST_PATH.read_text(encoding='utf-8'))
            if cached.get('key') == key and cached.get('data'):
                print(f'  · 초단기예보 캐시 재사용 ({base_time} 발표분)')
                return cached['data']
    except Exception:
        pass

    url = 'https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst'
    PTY_TXT = {0: '없음', 1: '비', 2: '비/눈', 3: '눈', 4: '소나기',
               5: '빗방울', 6: '진눈깨비', 7: '눈날림'}
    out = {}
    for r in REGIONS:
        try:
            resp = requests.get(url, params={
                'serviceKey': DATA_KEY, 'pageNo': 1, 'numOfRows': 300, 'dataType': 'JSON',
                'base_date': base_date, 'base_time': base_time,
                'nx': r['nx'], 'ny': r['ny'],
            }, timeout=10)
            resp.raise_for_status()
            j = resp.json()
            if str(j['response']['header']['resultCode']) != '00':
                raise RuntimeError(j['response']['header'].get('resultMsg', '?'))
            items = j['response']['body']['items']['item']
        except Exception as e:
            print(f'  · 초단기예보 {r["name"]} 실패: {type(e).__name__}')
            continue

        by = {}
        for it in items:
            # ⚠ 날짜+시각으로 키를 잡는다. fcstTime('HHMM')만 쓰면 저녁 발표분이 자정을 넘길 때
            #   '2300'→'0000'이 문자열 정렬에서 뒤집혀 6시간 예보 순서가 꼬인다(자정 전후 몇 시간).
            by.setdefault(it['fcstDate'] + it['fcstTime'], {})[it['category']] = it['fcstValue']
        rows = []
        for t in sorted(by):
            c = by[t]
            try:
                pty = int(float(c.get('PTY', 0)))
            except (TypeError, ValueError):
                pty = 0
            def _num(k):
                try:
                    return float(c[k])
                except (KeyError, TypeError, ValueError):
                    return None
            rows.append({
                'time': f'{t[8:10]}:{t[10:12]}',   # t = 'YYYYMMDDHHMM'
                'rain_mm': parse_pcp(c.get('RN1', '강수없음')),   # ⚠ 글자 → mm
                'pop': _num('POP'),
                'pty': pty,
                'pty_txt': PTY_TXT.get(pty, '?'),
                'sky': _num('SKY'),
                'temp': _num('T1H'),
                'reh': _num('REH'),
                'lgt': _num('LGT'),          # 낙뢰
                'wsd': _num('WSD'),          # 풍속 — 응답에 이미 오는데 안 읽고 있었다
                'vec': _num('VEC'),          # 풍향(도)
            })
        if rows:
            out[r['name']] = rows[:6]

    if out:
        try:
            ULTRA_FCST_PATH.parent.mkdir(parents=True, exist_ok=True)
            ULTRA_FCST_PATH.write_text(json.dumps({'key': key, 'data': out}, ensure_ascii=False),
                                       encoding='utf-8')
        except Exception:
            pass
    return out


# ============================================================
# 1-B2. 물때(조석) — 파주 임진강 하구. 국립해양조사원 조석예보(고,저조)
# ============================================================
TIDE_PATH = TMP / 'tide.json'

# 강화대교 관측소코드(DT_0032). 강화 만조/간조 시각 +2시간 = 임진강 두포리(파주).
#   → 파주 현장 실무 방식. 두포리 자체 조위관측소는 없어 강화 예보를 위상보정해 쓴다.
TIDE_OBSCODE = 'DT_0032'
TIDE_SHIFT_MIN = 120          # 두포리 위상지연(분)
TIDE_STATION = '강화대교'
TIDE_TARGET = '임진강 두포리(파주)'
TIDE_SV = 2                   # 캐시 스키마 버전 — 필드 추가 시 올려 옛 캐시 무효화


def _mulddae(lun_day):
    """음력일(1~30) → 서해(강화) 물때(몇물). '7물때식'.
    검증: badatime 강화대교 8일 연속 대조 통과(음력11→2물·12→3물 … 음력16→7물).
    i=((L-1)%15)+1 ; i1~7→(i+6)물[7~13물], i8→조금, i9→무시, i10~15→(i-9)물[1~6물]."""
    try:
        L = int(lun_day)
    except (TypeError, ValueError):
        return None
    i = ((L - 1) % 15) + 1
    if 1 <= i <= 7:
        return f'{i + 6}물'
    if i == 8:
        return '조금'
    if i == 9:
        return '무시'
    return f'{i - 9}물'   # 10~15 → 1~6물(6물=사리)


def _moon_phase(lun_day):
    """음력일(1~30) → 달 위상 {emoji,name}. (달이 차고 기우는 대략적 위상)"""
    try:
        L = int(lun_day)
    except (TypeError, ValueError):
        return None
    if L <= 1 or L >= 30:
        return {'emoji': '🌑', 'name': '삭(그믐)'}
    if L <= 6:
        return {'emoji': '🌒', 'name': '초승달'}
    if L <= 8:
        return {'emoji': '🌓', 'name': '상현달'}
    if L <= 13:
        return {'emoji': '🌔', 'name': '상현망간'}
    if L <= 16:
        return {'emoji': '🌕', 'name': '보름달'}
    if L <= 21:
        return {'emoji': '🌖', 'name': '하현망간'}
    if L <= 23:
        return {'emoji': '🌗', 'name': '하현달'}
    return {'emoji': '🌘', 'name': '그믐달'}


def _load_klc():
    """음력 변환 클래스 로드 — 저장소 vendor 우선(서버 pip 불필요), 없으면 설치본.
    tools/가 sys.path에 있어(스크립트 실행/모듈 import 모두) 'vendor.…'로 잡힌다."""
    try:
        from vendor.korean_lunar_calendar import KoreanLunarCalendar
        return KoreanLunarCalendar
    except Exception:
        pass
    try:
        from korean_lunar_calendar import KoreanLunarCalendar
        return KoreanLunarCalendar
    except Exception:
        return None


SUN_PATH = TMP / 'sun_kasi.json'


def fetch_sun_times():
    """한국천문연구원 출몰시각(공공데이터포털 RiseSetInfoService.getLCRiseSetInfo) — 관서별 오늘 일출·일몰.
    좌표(시·군청, 프로필 office_latlon)로 묻는다. 하루 한 번만 실제로 부르고 그날은 파일 캐시를 쓴다.
    Returns: {'date': 'YYYYMMDD', 'src': 'kasi', 'by': {관서: {'rise': 'HH:MM', 'set': 'HH:MM'}}} 또는 None
    실패하면 None — 화면(stage.js cbSun)이 같은 좌표로 계산한 값으로 대신한다."""
    pts = P.get('office_latlon') or {}
    if not pts or not DATA_KEY:
        return None
    today = datetime.now().strftime('%Y%m%d')
    try:
        cache = json.loads(SUN_PATH.read_text(encoding='utf-8')) if SUN_PATH.exists() else {}
    except Exception:
        cache = {}
    if cache.get('date') == today and len(cache.get('by') or {}) == len(pts):
        return cache
    by, seen = {}, {}
    for nm, (lat, lon) in pts.items():
        key = f'{lat},{lon}'
        if key in seen:                       # 청주동부·서부처럼 같은 좌표는 한 번만
            by[nm] = seen[key]
            continue
        r = requests.get('https://apis.data.go.kr/B090041/openapi/service/RiseSetInfoService/getLCRiseSetInfo',
                         params={'serviceKey': DATA_KEY, 'locdate': today, 'longitude': lon, 'latitude': lat, 'dnYn': 'Y'},
                         timeout=10)
        txt = r.text
        rise = _re.search(r'<sunrise>\s*(\d{4})', txt)
        sset = _re.search(r'<sunset>\s*(\d{4})', txt)
        if not (rise and sset):
            _brief = _re.sub(r'\s+', ' ', txt)[:80]   # 파이썬 3.11 이하는 f-string 안 역슬래시를 못 쓴다
            print(f'  · 출몰시각 응답 이상({nm}): {_brief}')
            return None
        v = {'rise': rise.group(1)[:2] + ':' + rise.group(1)[2:], 'set': sset.group(1)[:2] + ':' + sset.group(1)[2:]}
        by[nm] = seen[key] = v
    out = {'date': today, 'src': 'kasi', 'by': by}
    try:
        _atomic_write_text(SUN_PATH, json.dumps(out, ensure_ascii=False))
    except Exception:
        pass
    return out


def fetch_tide():
    """파주 임진강 물때 — 강화대교 조석예보 고저조를 받아 두포리(+2h)로 환산.

    ⚠ 함정 1: 이 게이트웨이(apis.data.go.kr/1192136)는 User-Agent 헤더가 없으면
              파이썬 기본 UA를 막아 403 Forbidden을 준다. 헤더 필수.
    ⚠ 함정 2: date 파라미터는 어떤 이름/형식으로도 무시되고 '오늘'만 준다.
              조석 극값은 하루 종일 불변이므로, 날짜로 캐시해 하루 1회만 실제 호출.
    ⚠ 함정 3: extrSe는 만조/간조 구분이 아니라 그날의 순번(1·2·3·4)이다.
              만조/간조는 조위값 크기(이웃 대비 극대=만조)로 판정한다.

    반환: {station,target,obscode,shift_min,date,amp_cm,spring,events:[{kind,ganghwa,dupo,cm}]} 또는 None
    """
    if not DATA_KEY:
        return None
    today = datetime.now().strftime('%Y-%m-%d')

    # 음력 라이브러리 가용 여부 — vendor(저장소내장) 우선. 있으면 물때/음력을 채운다.
    _KLC = _load_klc()
    _klc_ok = _KLC is not None

    # 날짜 캐시 — 같은 날+같은 스키마면 재호출하지 않는다(하루 1회).
    #   단, 라이브러리가 새로 설치돼 물때를 채울 수 있게 됐는데 캐시엔 없으면 재계산한다
    #   (서버 자가설치 후 당일 바로 물때가 뜨도록).
    try:
        if TIDE_PATH.exists():
            cached = json.loads(TIDE_PATH.read_text(encoding='utf-8'))
            if (cached.get('date') == today and cached.get('events') and cached.get('_sv') == TIDE_SV
                    and (cached.get('mulddae') or not _klc_ok)):
                return cached
    except Exception:
        pass

    url = 'https://apis.data.go.kr/1192136/tideFcstHghLw/GetTideFcstHghLwApiService'
    try:
        r = requests.get(url, params={
            'serviceKey': DATA_KEY, 'pageNo': 1, 'numOfRows': 100,
            'obsCode': TIDE_OBSCODE,
        }, headers={'User-Agent': 'Mozilla/5.0'}, timeout=12)
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception as e:
        print(f'  · 조석예보 실패: {type(e).__name__}')
        return None

    raw = []
    for it in root.iter('item'):
        dt = (it.findtext('predcDt') or '').strip()       # 'YYYY-MM-DD HH:MM'
        val = (it.findtext('predcTdlvVl') or '').strip()   # 조위 cm
        if len(dt) < 16:
            continue
        try:
            cm = float(val)
        except (TypeError, ValueError):
            cm = None
        raw.append({'dt': dt, 'cm': cm})
    if not raw:
        return None
    raw.sort(key=lambda x: x['dt'])

    # 만조/간조 판정: 이웃 대비 극대=만조, 극소=간조 (극값은 시간순 교대)
    events = []
    for i, e in enumerate(raw):
        neigh = []
        if i > 0 and raw[i - 1]['cm'] is not None:
            neigh.append(raw[i - 1]['cm'])
        if i < len(raw) - 1 and raw[i + 1]['cm'] is not None:
            neigh.append(raw[i + 1]['cm'])
        kind = 'high'
        if e['cm'] is not None and neigh:
            kind = 'high' if e['cm'] >= max(neigh) else 'low'
        gh = e['dt'][11:16]                                 # 강화 'HH:MM'
        try:
            base = datetime.strptime(e['dt'], '%Y-%m-%d %H:%M')
            dupo = (base + timedelta(minutes=TIDE_SHIFT_MIN)).strftime('%H:%M')
        except ValueError:
            dupo = gh
        events.append({'kind': kind, 'ganghwa': gh, 'dupo': dupo, 'cm': e['cm']})

    cms = [e['cm'] for e in raw if e['cm'] is not None]
    amp = round(max(cms) - min(cms)) if cms else 0          # 강화 기준 조차(cm)
    # 물때(사리/조금) 정성 판정 — 강화대교 조차 기준(대조차 700cm+, 소조차 200cm대)
    spring = '사리' if amp >= 600 else '중간' if amp >= 400 else '조금'

    result = {
        'station': TIDE_STATION, 'target': TIDE_TARGET, 'obscode': TIDE_OBSCODE,
        'shift_min': TIDE_SHIFT_MIN, 'date': today, 'amp_cm': amp,
        'spring': spring, 'events': events, '_sv': TIDE_SV,
    }

    # 음력·물때(몇물)·달모양 — vendor 음력 라이브러리로 계산(순수 오프라인·무료).
    #   물때 공식은 badatime 대조로 검증됨(_mulddae). 실패해도 나머지는 정상 표출.
    if _KLC is not None:
        try:
            _n = datetime.now()
            _cal = _KLC()
            _cal.setSolarDate(_n.year, _n.month, _n.day)
            _ld = _cal.lunarDay
            result['lunar'] = f'{_cal.lunarMonth}.{_ld}'
            result['mulddae'] = _mulddae(_ld)
            result['moon'] = _moon_phase(_ld)
        except Exception:
            pass
    try:
        TIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TIDE_PATH.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass
    return result


# ============================================================
# 1-C. 태풍 (기상청 apihub) — 진행 중인 태풍의 진로·제원
# ============================================================
def _typ_num(v):
    """태풍 수치 — 결측은 -999로 온다. None으로 바꾼다."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f <= -900 else f


def fetch_typhoon():
    """진행 중인 태풍과 그 진로. 태풍이 없으면 [] (에러가 아니라 정상 — 1년의 대부분).

    typ_lst(연도별 목록)에서 NOW=1(진행중)을 찾고, typ_data로 그 태풍의 진로를 받는다.
      · FT=0 → 지나온 경로(분석), FT=1 → 예상 진로(예측)
      · EFF: 1상륙 2직접영향 3간접영향 4없음  ← 한반도 영향 여부를 API가 직접 알려준다
    ⚠ 파싱 함정: 마지막 LOC('일본 도쿄 남')에 공백이 있어 split()하면 뒤가 깨진다.
      필요한 값(좌표·기압·풍속·반경)은 전부 앞 16칸이라 f[0:16]만 쓴다.
    ⚠ 예측(FT=1)은 '진행 중인 태풍'에만 붙는다. 종료된 태풍은 분석만 남는다
      → 예측 경로는 실제 태풍이 와야 실물 검증된다(파싱은 분석과 동일 포맷이라 안전).
    """
    if not KMA_APIHUB_KEY:
        return []
    base = 'https://apihub.kma.go.kr/api/typ01/url'
    yy = datetime.now().year

    def _get(url, cache_key=None):
        # ★ 공유 캐시 key 는 '부르는 주소마다' 달라야 한다. 전엔 파일명(typ_data.php)만 썼더니
        #   태풍이 둘 이상일 때 두 번째 태풍이 첫 번째 태풍의 응답을 그대로 읽었다
        #   (2026-10-08 실제 발생: 29호 고구마가 28호 놀로의 위치·진로로 표시됨).
        r = shared_get(cache_key or ('typhoon_' + url.split('/')[-1].split('?')[0]), url, timeout=12, max_age=600)
        r.raise_for_status()
        r.encoding = 'euc-kr'
        if '활용신청' in r.text[:300]:
            raise RuntimeError('태풍 API 활용신청 필요')
        return r.text

    # 1) 올해 목록에서 진행 중인 태풍 찾기
    lst = _get(f'{base}/typ_lst.php?YY={yy}&disp=0&help=0&authKey={KMA_APIHUB_KEY}')
    active = []
    for line in lst.split('\n'):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        f = s.split()
        if len(f) < 7:
            continue
        try:
            seq, now, eff = f[1], f[2], f[3]
        except IndexError:
            continue
        if now != '1':                      # 1=진행중, 2=종료
            continue
        active.append({'seq': seq, 'eff': eff, 'name': f[6] if len(f) > 6 else '',
                       'name_en': f[7] if len(f) > 7 else ''})
    if not active:
        return []                            # 태풍 없음 — 정상

    EFF_TXT = {'1': '상륙', '2': '직접영향', '3': '간접영향', '4': '영향없음'}
    out = []
    for a in active:
        try:
            d = _get(f'{base}/typ_data.php?YY={yy}&typ={a["seq"]}&mode=1&disp=0&help=0'
                     f'&authKey={KMA_APIHUB_KEY}',
                     cache_key=f'typhoon_data_{yy}_{a["seq"]}')
        except Exception as e:
            print(f'    태풍 {a["seq"]}호 진로 실패: {type(e).__name__}')
            continue
        past, fcst = [], []
        for line in d.split('\n'):
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            f = s.split()
            if len(f) < 16:
                continue
            lat, lon = _typ_num(f[7]), _typ_num(f[8])
            if lat is None or lon is None:
                continue
            pt = {
                'tm': f[6],                       # 예측시각(UTC) — FT=0이면 분석시각과 같다
                'lat': lat, 'lon': lon,
                'dir': f[9] if f[9] != '-999' else '',
                'sp': _typ_num(f[10]),            # 진행속도 km/h
                'ps': _typ_num(f[11]),            # 중심기압 hPa
                'ws': _typ_num(f[12]),            # 최대풍속 m/s
                'rad15': _typ_num(f[13]),         # 강풍반경(15m/s) km
                'rad25': _typ_num(f[14]),         # 폭풍반경(25m/s) km
                'rad70': _typ_num(f[15]),         # 70% 예상확률반경(예보원) km
            }
            (fcst if f[0] == '1' else past).append(pt)
        if not past and not fcst:
            continue
        cur = past[-1] if past else fcst[0]       # 현재 = 마지막 분석값
        out.append({
            'seq': a['seq'], 'name': a['name'], 'name_en': a['name_en'],
            'eff': a['eff'], 'eff_txt': EFF_TXT.get(a['eff'], a['eff']),
            'near_kr': a['eff'] in ('1', '2', '3'),
            'now': {'lat': cur['lat'], 'lon': cur['lon'], 'ps': cur['ps'], 'ws': cur['ws'],
                    'dir': cur['dir'], 'sp': cur['sp'],
                    'rad15': cur['rad15'], 'rad25': cur['rad25'], 'tm': cur['tm']},
            'past': past[-40:], 'fcst': fcst[:12],
        })
    # 한반도 영향 태풍을 앞으로
    out.sort(key=lambda x: (0 if x['near_kr'] else 1, x['seq']))
    return out


# ── 지진·낙뢰·영향예보 (2026-11-09 활용신청) ──────────────────────────────
def _km(lat1, lon1, lat2, lon2):
    """두 좌표 사이 거리(km) — 하버사인."""
    from math import radians, sin, cos, asin, sqrt
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def _stations_ll():
    return [(s['name'], float(s['lat']), float(s['lon']))
            for s in (P.get('stations_all') or []) if s.get('lat') and s.get('lon')]


def _nearest_station(lat, lon):
    best = None
    for nm, a, b in _stations_ll():
        d = _km(lat, lon, a, b)
        if best is None or d < best[1]:
            best = (nm, d)
    return best or ('', 9999.0)


def _hub_text(r):
    """API 허브 응답 본문 — UTF-8 이 아니면 EUC-KR. 활용신청 안내면 예외."""
    try:
        t = r.content.decode('utf-8')
    except UnicodeDecodeError:
        t = r.content.decode('euc-kr', errors='replace')
    if '활용신청' in t[:300]:
        raise RuntimeError('활용신청 필요')
    return t


QUAKE_TP = {'2': '국외지진정보', '3': '국내지진통보', '5': '지진정보(재통보)', '10': '지진현장경보',
            '11': '지진조기경보', '12': '국외지진조기경보', '14': '지진속보'}
_ROMAN = 'ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ'


def _roman_num(s):
    m = _re.search('[' + _ROMAN + ']+', s or '')
    if not m:
        return None
    # Ⅰ~Ⅹ는 한 글자씩 따로 있는 문자다(Ⅳ도 한 글자) — 첫 글자의 순번이 곧 진도.
    return _ROMAN.index(m.group(0)[0]) + 1


def fetch_quake():
    """기상청 지진 통보(eqk_now) — 국내 지진만, 관서 거리·충북 진도를 붙인다.
    한 줄 형식: TP TM_FC SEQ TM_EQK.MSC MT LAT LON LOC,INT,REM,COR,=
    ⚠ INT(진도)가 '최대진도 Ⅳ(전북),Ⅲ(전남),Ⅱ(광주)'처럼 쉼표로 여러 칸이라 쉼표로 자르면 안 된다
      → 로마숫자 진도로 시작하는 칸만 진도로 모으고 나머지를 비고로 본다.
    실패하면 예외(호출측이 이전 값 보존). 지진이 없으면 []."""
    if not KMA_APIHUB_KEY:
        return []
    tm = datetime.now().strftime('%Y%m%d%H%M')
    r = shared_get('quake_now', f'https://apihub.kma.go.kr/api/typ01/url/eqk_now.php'
                   f'?tm={tm}&disp=0&help=0&authKey={KMA_APIHUB_KEY}', timeout=12, max_age=120)
    r.raise_for_status()
    out = []
    for raw in _hub_text(r).split('\n'):
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        f = s.split(None, 7)
        if len(f) < 8 or f[0] not in QUAKE_TP or f[0] in ('2', '12'):   # 국외는 뺀다
            continue
        try:
            mt, lat, lon = float(f[4]), float(f[5]), float(f[6])
        except ValueError:
            continue
        rest = f[7].rstrip('=').rstrip(',').strip()
        parts = [x.strip() for x in rest.split(',')]
        loc, i, ints = parts[0], 1, []
        while i < len(parts) and _re.match(r'^(최대진도\s*)?[' + _ROMAN + r']+\s*\(', parts[i]):
            ints.append(parts[i]); i += 1
        if not ints and i < len(parts) and parts[i] == '':
            i += 1
        rem = ','.join(p for p in parts[i:] if p).strip()
        cb = next((x for x in ints if _re.search(r'충북|충청북', x)), '')
        te = f[3].split('.')[0]
        near_nm, near_km = _nearest_station(lat, lon)
        out.append({
            'tp': f[0], 'tp_txt': QUAKE_TP[f[0]], 'tm_fc': f[1], 'seq': f[2],
            'tm_eqk': f'{te[0:4]}-{te[4:6]}-{te[6:8]} {te[8:10]}:{te[10:12]}:{te[12:14]}',
            'mt': mt, 'lat': lat, 'lon': lon, 'loc': loc,
            'int': ','.join(ints), 'int_max': _roman_num(ints[0]) if ints else None,
            'int_cb': _roman_num(cb) if cb else None, 'rem': rem[:200],
            'near': near_nm, 'dist_km': round(near_km),
        })
    return out


def merge_quake(prev_list, new_list, days=7):
    """eqk_now 는 최근 통보 몇 건만 준다 → 회차마다 이전 목록과 합쳐 7일치를 쌓는다.
    같은 지진은 통보가 여러 번(속보→통보→재통보) 오니 진앙시 기준 마지막 통보만 남긴다."""
    cut = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    by = {}
    for q in (prev_list or []) + (new_list or []):
        if not isinstance(q, dict) or q.get('tm_eqk', '') < cut:
            continue
        k = q.get('tm_eqk', '')[:16]
        if k not in by or str(q.get('tm_fc', '')) >= str(by[k].get('tm_fc', '')):
            by[k] = q
    return sorted(by.values(), key=lambda q: q.get('tm_eqk', ''), reverse=True)[:30]


def fetch_lightning(radius_km=20, minutes=60):
    """기상청 낙뢰 관측(lgt_pnt) — 최근 1시간, 관서마다 반경 20km 안 횟수·가장 가까운 거리·마지막 시각.
    낙뢰가 없으면(겨울 대부분) by={} 이고 정상이다. 실패하면 예외."""
    if not KMA_APIHUB_KEY:
        return None
    now = datetime.now()
    # ⚠ lgt_pnt 는 tm 앞뒤로 itv분씩 준다(2026-11-09 실측: tm=17:00·itv=60 → 16:00~17:59).
    #   최근 1시간 = 가운데를 30분 전으로 두고 itv=30.
    tm = (now - timedelta(minutes=minutes // 2)).strftime('%Y%m%d%H%M')
    r = shared_get('lgt_pnt', f'https://apihub.kma.go.kr/api/typ01/url/lgt_pnt.php'
                   f'?tm={tm}&itv={minutes // 2}&authKey={KMA_APIHUB_KEY}', timeout=12, max_age=120)
    r.raise_for_status()
    cut = (now - timedelta(minutes=minutes)).strftime('%Y%m%d%H%M%S')
    cut10 = (now - timedelta(minutes=10)).strftime('%Y%m%d%H%M%S')
    sts = _stations_ll()
    by, pts = {}, []
    for raw in _hub_text(r).split('\n'):
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        f = s.split()
        if len(f) < 4 or len(f[0]) < 12:
            continue
        try:
            t, lon, lat, st = f[0], float(f[1]), float(f[2]), float(f[3])
        except ValueError:
            continue
        if t < cut:
            continue
        hit = False
        for nm, a, b in sts:
            d = _km(lat, lon, a, b)
            if d > radius_km:
                continue
            hit = True
            o = by.setdefault(nm, {'n': 0, 'n10': 0, 'near_km': None, 'last': ''})
            o['n'] += 1
            if t >= cut10:
                o['n10'] += 1
            if o['near_km'] is None or d < o['near_km']:
                o['near_km'] = round(d, 1)
            if t > o['last']:
                o['last'] = t
        if hit and len(pts) < 300:
            pts.append({'tm': t, 'lat': lat, 'lon': lon, 'st': st})
    for o in by.values():
        lt = o['last']
        o['last'] = f'{lt[8:10]}:{lt[10:12]}' if len(lt) >= 12 else ''
    return {'tm': now.strftime('%Y-%m-%d %H:%M'), 'minutes': minutes, 'radius_km': radius_km,
            'n': len(pts), 'by': by, 'pts': pts}


IMPACT_ORDER = {'관심': 1, '주의': 2, '경고': 3, '위험': 4}


def fetch_impact():
    """기상청 영향예보(폭염 hw·한파 cw) — 충북 구역(L104…)만 관서별로 나눈다.
    결과: {'hw': {관서: [{tmEf, value, clsfc[]}]}, 'cw': {...}}. 해당 없음(NO_DATA)은 빈 dict(정상)."""
    if not DATA_KEY:
        return None
    pre = tuple(P.get('wrn_prefix') or ['L104'])
    reg_map, areas = P.get('reg_map') or {}, P.get('wrn_areas') or {}
    names = [nm for nm, _, _ in _stations_ll()]
    today = datetime.now().strftime('%Y%m%d')

    def targets(it):
        rid, rn = str(it.get('regId', '')), str(it.get('regName', ''))
        if rid.endswith('0000'):                          # 도 전체
            return names
        for k in (rn, _re.sub(r'(시|군)$', '', rn)):
            if k in areas:
                return areas[k]
            if k in names:
                return [k]
        nm = reg_map.get(rid)
        if nm and nm in areas:
            return areas[nm]
        return [nm] if nm in names else []

    out = {}
    for kind, op in (('hw', 'getHWImpactValueV2'), ('cw', 'getCWImpactValueV2')):
        r = shared_get(f'impact_{kind}_{today}',
                       f'https://apis.data.go.kr/1360000/ImpactInfoServiceV2/{op}',
                       params={'serviceKey': DATA_KEY, 'pageNo': 1, 'numOfRows': 2000,
                               'dataType': 'JSON', 'tm': today}, timeout=15, max_age=1800)
        r.raise_for_status()
        j = r.json()
        hd = (j.get('response') or {}).get('header') or {}
        if hd.get('resultCode') not in ('00', '03'):
            raise RuntimeError(f'영향예보 {kind} {hd.get("resultCode")} {hd.get("resultMsg", "")}')
        items = (((j.get('response') or {}).get('body') or {}).get('items') or {}).get('item') or []
        if isinstance(items, dict):
            items = [items]
        by = {}
        for it in items:
            if not str(it.get('regId', '')).startswith(pre) or str(it.get('tmEf', '')) < today:
                continue
            v = str(it.get('value', ''))
            if v not in IMPACT_ORDER:
                continue
            for nm in targets(it):
                days = by.setdefault(nm, {})
                d = days.setdefault(str(it['tmEf']), {'tmEf': str(it['tmEf']), 'value': v, 'clsfc': []})
                if IMPACT_ORDER[v] > IMPACT_ORDER[d['value']]:
                    d['value'], d['clsfc'] = v, []
                if v == d['value'] and it.get('clsfc') and it['clsfc'] not in d['clsfc']:
                    d['clsfc'].append(it['clsfc'])
        out[kind] = {nm: sorted(days.values(), key=lambda d: d['tmEf']) for nm, days in by.items()}
    return out


NCST_CACHE_PATH = TMP / 'ncst_cache.json'


def _ncst_cache_load():
    try:
        return json.loads(NCST_CACHE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def fetch_current_observation(region):
    """초단기실황 — 매 정시 발표, 발표 후 ~10분에 안정.
    실제 측정값(예보 아님): T1H 기온, RN1 1시간 강수, REH 습도, WSD 풍속, VEC 풍향, PTY 강수형태.

    발표시각(base_time) 캐시 (2026-09-18 전국 확장 0단계): 실황은 1시간에 한 번만 바뀌는데
    5분마다 시군 수만큼 불렀다(경기 34곳 → 하루 9,800회). 같은 격자·같은 발표시각이면
    캐시를 돌려주고, 미발표(NO_DATA)만 다음 회차에 다시 묻는다 → 시군당 하루 24회."""
    now = datetime.now()
    url = 'https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst'
    cache = _ncst_cache_load()

    def _try(base):
        base_date = base.strftime('%Y%m%d')
        base_time = base.strftime('%H00')
        r = requests.get(url, params={
            'serviceKey': DATA_KEY,
            'pageNo': 1, 'numOfRows': 30,
            'dataType': 'JSON',
            'base_date': base_date, 'base_time': base_time,
            'nx': region['nx'], 'ny': region['ny'],
        }, timeout=10)
        r.raise_for_status()
        resp = r.json()['response']
        if str(resp.get('header', {}).get('resultCode', '')) != '00':
            return None   # NO_DATA(03) 등 — 아직 미발표
        items = (resp.get('body', {}).get('items', {}) or {}).get('item')
        if not items:
            return None
        obs = {}
        for it in items:
            cat, val = it['category'], it['obsrValue']
            if cat == 'T1H':   obs['t1h'] = float(val)
            elif cat == 'RN1':
                try:    obs['rn1'] = float(val)
                except: obs['rn1'] = 0
            elif cat == 'REH': obs['reh'] = int(float(val))
            elif cat == 'WSD': obs['wsd'] = float(val)
            elif cat == 'VEC': obs['vec'] = float(val)
            elif cat == 'PTY': obs['pty'] = val
        obs['base_time'] = f'{base_time[:2]}:{base_time[2:]}'
        return obs

    # 15분 지났으면 이번 정시(최신) 우선, 미발표면 직전 정시로 폴백 → 최신성+안정성
    candidates = []
    if now.minute >= 15:
        candidates.append(now)
    candidates.append(now - timedelta(hours=1))
    for base in candidates:
        ck = f"{region['nx']},{region['ny']},{base.strftime('%Y%m%d%H')}"
        if ck in cache:
            return dict(cache[ck])
        obs = _try(base)
        if obs is not None:
            cutoff = (now - timedelta(hours=3)).strftime('%Y%m%d%H')
            cache = {k: v for k, v in cache.items() if k.rsplit(',', 1)[-1] >= cutoff}
            cache[ck] = obs
            try:
                _atomic_write_text(NCST_CACHE_PATH, json.dumps(cache, ensure_ascii=False))
            except Exception:
                pass
            return obs
    raise RuntimeError('초단기실황 NO_DATA (이번·직전 정시 모두)')


def update_rain_history(region_name, rn1):
    """시간별 강수 기록 누적 저장 및 1/3/6/12시간 누적 반환."""
    history_path = TMP / 'rain_history.json'
    history_path.parent.mkdir(exist_ok=True)

    now = datetime.now()
    current_hour = now.strftime('%Y%m%d%H')

    history = {}
    if history_path.exists():
        try:
            with open(history_path, encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = {}

    if region_name not in history:
        history[region_name] = {}
    # 시간 단위로 덮어씀 — 한 시간 안에 여러 번 호출돼도 마지막 값 사용
    history[region_name][current_hour] = float(rn1 or 0)

    # 14시간 이상 된 데이터 정리
    cutoff = (now - timedelta(hours=14)).strftime('%Y%m%d%H')
    history[region_name] = {k: v for k, v in history[region_name].items() if k > cutoff}

    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    def sum_last(n_hours):
        cutoff_h = (now - timedelta(hours=n_hours - 1)).strftime('%Y%m%d%H')
        return round(sum(v for k, v in history[region_name].items() if k >= cutoff_h), 1)

    return {'1h': sum_last(1), '3h': sum_last(3), '6h': sum_last(6), '12h': sum_last(12)}


def persist_today_minmax(region_name, tmax, tmin, hourly):
    """오늘 일 최고/최저 기온을 자정까지 유지.

    기상청 단기예보는 미래만 줘서, 저녁이 되면 오늘의 TMX(최고)·TMN(최저)이
    예보에서 빠진다(낮엔 나오다가 저녁에 사라짐). 그래서:
      1) 낮에 받은 TMX/TMN을 파일에 저장(날짜 바뀌면 리셋)
      2) 저녁에 예보값이 없으면 저장된 오늘 값을 사용
      3) 저장값도 없으면(서버 첫 가동 등) hourly(향후 24h) 기온으로 근사
    반환: (tmax, tmin)"""
    path = TMP / 'today_minmax.json'
    today = datetime.now().strftime('%Y%m%d')

    store = {}
    try:
        if path.exists():
            with open(path, encoding='utf-8') as f:
                store = json.load(f)
    except Exception:
        store = {}
    # 날짜가 바뀌면 초기화
    if store.get('date') != today:
        store = {'date': today, 'regions': {}}

    rec = store.setdefault('regions', {}).setdefault(region_name, {})
    # 새 예보값이 있으면 더 극단으로 갱신
    if tmax is not None:
        rec['tmax'] = tmax if rec.get('tmax') is None else max(rec['tmax'], tmax)
    if tmin is not None:
        rec['tmin'] = tmin if rec.get('tmin') is None else min(rec['tmin'], tmin)

    out_max, out_min = rec.get('tmax'), rec.get('tmin')
    # 저장값도 없으면 hourly로 근사 (오늘 데이터가 아예 없는 경우)
    if (out_max is None or out_min is None) and hourly:
        temps = [h.get('temp') for h in hourly if h.get('temp') is not None]
        if temps:
            if out_max is None:
                out_max = max(temps)
            if out_min is None:
                out_min = min(temps)

    try:
        path.parent.mkdir(exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(store, f, ensure_ascii=False)
    except Exception:
        pass

    return out_max, out_min


OBS_FROM_AWS = bool(P.get('obs_from_aws', True))


def _obs_from_aws(area, aws):
    """AWS 관서값 → 초단기실황과 같은 모양 {t1h, rn1, reh, wsd, vec, pty, base_time}. 없으면 None."""
    a = (aws or {}).get(area) or {}
    po = a.get('obs')
    if not po or po.get('ta') is None:
        return None
    o = {'t1h': float(po['ta']), 'base_time': '', 'src': 'aws', 'station': po.get('station', '')}
    if po.get('hm') is not None:
        o['reh'] = int(round(po['hm']))
    if po.get('ws10') is not None:
        o['wsd'] = float(po['ws10'])
    if po.get('wd10') is not None:
        o['vec'] = float(po['wd10'])
    if a.get('rn60') is not None:
        o['rn1'] = float(a['rn60'])
    tm = str(po.get('tm') or '')
    if len(tm) >= 12:
        o['base_time'] = f'{tm[8:10]}:{tm[10:12]}'
    # 강수형태 — 6시간 예측(초단기예보) 첫 칸. 비가 실측됐는데 예보가 '없음'이면 '비'로.
    try:
        first = (_ULTRA_CACHE.get(area) or [{}])[0]
        pty = first.get('pty')
        if pty not in (None, '', 0, '0'):
            o['pty'] = str(pty)
        elif (o.get('rn1') or 0) > 0:
            o['pty'] = '1'
    except Exception:
        pass
    return o


_ULTRA_CACHE = {}


def fetch_all_regions(aws=None):
    aws = aws or {}
    regions = []
    for r in REGIONS:
        item = {'name': r['name'], 'temp': 0, 'weather': '?', 'rain': 0,
                'wind': 0, 'humid': 0, 'level': 'normal'}
        try:
            item = fetch_one_region_forecast(r)
            print(f'  ✓ {r["name"]}', end='')
        except Exception as e:
            print(f'  ✗ {r["name"]}: {e}')

        # 초단기실황 + 누적 강수
        # 2026-09-19 한도 대책: 실황(기온·습도·바람·1시간 강수)은 AWS 매분자료(전국 1회 호출)에 이미 있다.
        # 전국 233개 시군이 실황 API 를 부르면 하루 5,600회 — 포털 한도(1만/일)의 절반이라 AWS 로 대체한다.
        # 강수형태(PTY)는 AWS 에 없어 6시간 예측(초단기예보) 첫 칸에서 가져오고, AWS 가 없는 단위만 실황을 부른다.
        detail = {}
        try:
            obs = _obs_from_aws(r['name'], aws) if OBS_FROM_AWS else None
            if obs is None:
                obs = fetch_current_observation(r)
            elif obs.get('reh') is None or obs.get('wsd') is None:
                # 관할 AWS 전부에 습도나 바람이 없으면 그 항목만 실황으로 채운다(드문 경우, 호출 1회)
                try:
                    fill = fetch_current_observation(r)
                    for k in ('reh', 'wsd', 'vec'):
                        if obs.get(k) is None and fill.get(k) is not None:
                            obs[k] = fill[k]
                except Exception:
                    pass
            detail['observation'] = obs
            cumul = update_rain_history(r['name'], obs.get('rn1', 0))
            detail['rain_cumul'] = cumul
            print(f'  · 실황 {obs.get("t1h", "-")}° / 강수 {cumul["1h"]}mm')
        except Exception as e:
            print(f'  · 실황 실패: {e}')
            detail['observation'] = {}
            detail['rain_cumul'] = {'1h': 0, '3h': 0, '6h': 0, '12h': 0}

        # AWS 실측(기상청 공식 누적) — 자체누적(rain_cumul)보다 신뢰도가 높다.
        # 화면은 AWS가 있으면 AWS를, 없으면 rain_cumul을 쓰고 출처를 표기한다.
        detail['aws'] = aws.get(r['name'], {})

        # 풍향 한글 + 체감온도
        obs = detail.get('observation', {})

        # === 카드 표시값을 실측(초단기실황)으로 통일 — 상세 모달과 불일치 해소 ===
        # 기존엔 카드=단기예보(TMP/PCP/REH), 상세=실측(T1H/RN1/REH)이라 값이 달랐음.
        # (예: 비 안 오는데 카드에 '강수 6mm' 예보값 표시 → 오해)
        # 카드는 '현재 기상'이므로 실측값을 우선 사용. weather(하늘상태)는
        # 실측에 SKY가 없어 예보값을 유지하되, 강수형태(pty)가 있으면 보정.
        if obs.get('t1h') is not None:
            item['temp'] = round(float(obs['t1h']), 1)
        if obs.get('reh') is not None:
            item['humid'] = int(float(obs['reh']))
        if obs.get('wsd') is not None:
            item['wind'] = round(float(obs['wsd']), 1)
        if obs.get('vec') is not None:
            item['vec'] = float(obs['vec'])
        if obs.get('rn1') is not None:
            item['rain'] = round(float(obs['rn1']), 1)
            # 실측 강수로 위험도·태그 재산정 (카드 숫자와 태그 일치; 예보 기반 잔재 제거)
            rn = item['rain']
            item.pop('tag', None)
            if rn >= 20:   item['level'] = 'danger';  item['tag'] = '경보'
            elif rn >= 10: item['level'] = 'warning'; item['tag'] = '호우'
            elif rn >= 3:  item['level'] = 'warning'
            else:          item['level'] = 'normal'
        # 실측 강수형태로 하늘상태 보정 (비/눈 오는데 '맑음' 표시 방지)
        _pty = obs.get('pty')
        if _pty not in (None, '', 0, '0'):
            _pty_map = {1: '비', 2: '비/눈', 3: '눈', 4: '소나기',
                        5: '빗방울', 6: '진눈깨비/빗방울', 7: '눈날림'}
            try:
                _pi = int(float(_pty))
                if _pi in _pty_map:
                    item['weather'] = _pty_map[_pi]
            except (ValueError, TypeError):
                pass

        if 'vec' in obs:
            detail['wind_dir_name'] = deg_to_dir(obs['vec'])
        elif item.get('vec') is not None:
            detail['wind_dir_name'] = deg_to_dir(item['vec'])
        else:
            detail['wind_dir_name'] = '-'
        t = obs.get('t1h', item.get('temp'))
        h = obs.get('reh', item.get('humid'))
        w = obs.get('wsd', item.get('wind'))
        detail['feels_like'] = feels_like(t, h, w)
        detail['pop'] = item.get('pop', 0)

        # 24시간 hourly를 detail로 옮김 (단기예보에서 추출한 것)
        detail['hourly'] = item.pop('_hourly', [])
        blend_hourly(detail['hourly'], r['name'], obs)

        # 오늘 최고/최저 — 저녁이 되면 단기예보(TMX/TMN)에서 사라지므로
        # 낮에 받은 값을 파일에 저장해 자정까지 유지. 저장값도 없으면(서버 첫 가동 등)
        # hourly(향후 24h) 기온으로 근사 → 빈 값(-) 방지.
        tmx, tmn = persist_today_minmax(r['name'], item.get('tmax'),
                                        item.get('tmin'), detail['hourly'])
        # 오늘 최고가 초단기예보·실측보다 낮게 나오지 않게(최저 TMN 은 아침 기준이라 그대로)
        _today = [h['temp'] for h in detail['hourly'] if h['time'][:8] == datetime.now().strftime('%Y%m%d')]
        if _today and tmx is not None:
            tmx = max(tmx, *_today)
        detail['tmax'] = tmx
        detail['tmin'] = tmn
        item['tmax'] = tmx
        item['tmin'] = tmn

        item['detail'] = detail
        regions.append(item)
    return regions


# ============================================================
# 2. 기상청 단기예보 - 시간대별 12시간 (중점 관서)
# ============================================================
_HOME = next((r for r in REGIONS if r['name'] == P['home']), REGIONS[0])


def fetch_hourly_forecast(nx=None, ny=None, hours=12):
    nx = _HOME['nx'] if nx is None else nx
    ny = _HOME['ny'] if ny is None else ny
    base_date, base_time = fcst_base_time()
    url = 'https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst'
    params = {
        'serviceKey': DATA_KEY,
        'pageNo': 1,
        'numOfRows': 1000,
        'dataType': 'JSON',
        'base_date': base_date,
        'base_time': base_time,
        'nx': nx, 'ny': ny,
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    items = r.json()['response']['body']['items']['item']

    # 시각별로 묶기
    by_time = {}
    for it in items:
        key = (it['fcstDate'], it['fcstTime'])
        by_time.setdefault(key, {})[it['category']] = it['fcstValue']

    # 현재 시각부터 hours개 정렬
    now = datetime.now()
    sorted_keys = sorted(by_time.keys())
    result = []
    for d, t in sorted_keys:
        dt = datetime.strptime(d + t, '%Y%m%d%H%M')
        if dt < now.replace(minute=0):
            continue
        cats = by_time[(d, t)]
        pty = cats.get('PTY', '0')
        sky = cats.get('SKY', '1')
        if pty in ('1', '4', '5'): icon = '🌧'
        elif pty in ('2', '3', '6', '7'): icon = '🌨'
        elif sky == '4': icon = '☁'
        elif sky == '3': icon = '🌥'
        else:
            icon = '🌙' if (dt.hour < 6 or dt.hour >= 19) else '☀'
        result.append({
            'time': f'{dt.hour:02d}시',
            'icon': icon,
            'temp': int(float(cats.get('TMP', 0))),
            'rain': int(float(cats.get('POP', 0))),
        })
        if len(result) >= hours:
            break
    return result


# ============================================================
# 3. 기상특보 (경기북부 발효 현황)
# ============================================================

WRN_TYPES = ['호우경보', '호우주의보', '강풍경보', '강풍주의보', '대설경보', '대설주의보',
             '한파경보', '한파주의보', '폭염경보', '폭염주의보', '풍랑경보', '풍랑주의보',
             '건조경보', '건조주의보', '황사경보', '태풍경보', '태풍주의보']

# 광역시 특보 권역 → 구 (예: 서울동북권 → 8개 구). 권역명도 키워드에 넣어 '서울'이 '서울동북권' 안에서
# 잡히지 않게 한다(_kw_in_text 가 긴 이름을 먼저 지운다) — 2026-09-20 전국 확장 ④.
WRN_AREAS = P.get('wrn_areas') or {}
NORTH_GG_KEYWORDS = list(dict.fromkeys(list(P['keywords']) + list(WRN_AREAS)))


_SEA_ZONE_RE = r'(앞바다|먼바다|전해상|해상|연안바다|평수구역)'


def _drop_sea_zones(text):
    """바다 특보구역을 본문에서 통째로 뺀다 — 육상 관서 매칭 근거가 아니다(2026-09-20 사장님 결정).
    기상청 바다 구역 이름엔 육상 이름이 그대로 들어간다: '인천·경기북부앞바다'→경기북부 전역, '제주도앞바다'→제주 전역,
    '남해동부안쪽먼바다'→남해군, '거제시동부앞바다'→거제, '충남북부앞바다(당진, 태안·서산)'→당진·태안·서산.
    ① '바다구역(세부, 세부)' 묶음은 괄호까지 통째로 ② 남은 조각 중 바다 이름 조각 제거. 허브(S코드) 경로와 같은 결과."""
    import re as _re
    t = _re.sub(r'[^,()]*' + _SEA_ZONE_RE + r'[^,()]*\([^()]*\)', '', text or '')
    parts = [p.strip() for p in t.split(',')]
    return ', '.join(p for p in parts if p and not _re.search(_SEA_ZONE_RE, p))


def _strip_area_wrappers(text):
    """기상청 특보 본문의 '광역(세부, 세부)' 꼴에서 광역 껍데기를 벗긴다 — 세부구역이 적혀 있으면 광역명은
    매칭 근거가 아니다. '경기도(파주시, 양주시), 서울(서울동북권)' → '파주시, 양주시, 서울동북권'.
    (2026-08-17 점검 [높음]: 남부만 발효돼도 '경기도'가 북부에 잡히던 누수.) 괄호가 비었으면 광역명 유지."""
    import re as _re
    return _re.sub(r'([^,()\s]+)\s*\(([^()]*)\)', lambda m: m.group(2).strip() or m.group(1), text or '')


def _expand_areas(s):
    """지역 문자열의 권역명(서울동북권)을 그 권역의 구 목록으로 바꾼다 → 화면·상황실·알림이 전부
    '지역 문자열에 관서 이름이 있나'로 판정하므로 이 한 곳으로 구 단위가 맞아떨어진다.
    권역명은 남기지 않는다 — '서울'이 들어 있으면 전역 표기로 오인돼 25개 구 전부에 뜬다."""
    out = []
    for p in str(s or '').split(','):
        p = p.strip()
        if not p:
            continue
        base = p[:-4] if p.endswith('(전체)') else p     # '인천(전체)' → '인천'
        out.extend(WRN_AREAS.get(base) or [p])           # 낱말 단위 — '인천'이 '인천남부' 안에서 바뀌면 안 된다
    return ', '.join(dict.fromkeys(out))


def _kw_in_text(text, kw):
    """text에 지역 kw가 포함되는지 — '양주'가 '남양주'에 부분포함되는 충돌 방지.
    kw를 부분으로 갖는 더 긴 지역명(남양주⊃양주)을 먼저 제거한 뒤 검사."""
    t = text
    for other in NORTH_GG_KEYWORDS:
        if other != kw and kw in other:
            t = t.replace(other, '')
    return kw in t

# 기상청 API허브 wrn_reg.php 기반 REG_ID → 시군명 정적 매핑
# 경기북부 10개 시군 + 경기도 전체 광역 코드
NORTH_GG_REG_MAP = P['reg_map']


def fetch_weather_commentary():
    """지방청 날씨해설 최신 1건 — 날씨누리 통보문 화면(list.do?kind=cmt)에서 읽는다.
    공개 API 가 없다(WthrWrnInfoService 는 특보·기상정보만). 하루 두 번(새벽·오후) 나오므로
    오늘 것이 아직 없으면(자정~새벽) 어제 것을 쓴다.
    반환: {title, tmFc, seq, period, text, img, img_alt, pdf} 또는 None."""
    import html as _html, re as _re
    for back in (0, 1):
        day = (datetime.now() - timedelta(days=back)).strftime('%Y-%m-%d')
        r = shared_get(f'wcmt_{WRN_STN}_{day}', 'https://www.weather.go.kr/w/special-report/list.do',
                       params={'stn': WRN_STN, 'kind': 'cmt', 'date': day},
                       timeout=15, max_age=1200, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200:
            continue
        t = r.content.decode('utf-8', 'replace')
        m = _re.search(r'<option value="cmt:(\d{12}):(\d+)" selected', t)
        body = _re.search(r'<div class="cmp-view-content">(.*?)<div class="cmp-stack">', t, _re.S)
        if not m or not body:
            continue
        def txt(s):
            s = _re.sub(r'<br\s*/?>', '\n', s)
            return _html.unescape(_re.sub(r'<[^>]+>', '', s)).strip()
        head = _re.search(r'<div class="cmp-view-header">(.*?)</div>', t, _re.S)
        spans = [s for s in _re.findall(r'<span>\s*\|\s*([^<]*)</span>', head.group(1) if head else '') if s.strip()]
        period = _re.search(r'<div class="cmp-view-announce">.*?<em>([^<]*)</em>', t, _re.S)
        img = _re.search(r'<img src="(/w/repositary/image/wrn_img/[^"]+)" alt="([^"]*)"', body.group(1))
        pdf = _re.search(r'href="(/w/repositary/xml/wrn/pdf/[^"]+)"', t)
        p = _re.search(r'<p>(.*?)</p>', body.group(1), _re.S)
        return {
            'title': _html.unescape(spans[-1].strip()) if spans else '날씨해설',
            'tmFc': m.group(1), 'seq': int(m.group(2)),
            'period': _html.unescape(period.group(1).strip()) if period else '',
            'text': txt(p.group(1)) if p else '',
            'img': 'https://www.weather.go.kr' + img.group(1) if img else '',
            'img_alt': _html.unescape(img.group(2)) if img else '',
            'pdf': 'https://www.weather.go.kr' + pdf.group(1) if pdf else '',
        }
    return None


def fetch_warning_bulletins():
    """기상청 통보문·기상정보 목록 + 본문 일괄 수집.
    - getWthrWrnList:  특보 통보문 발표·해제 이력 (최근 7일)
    - getWthrWrnMsg:   특보 통보문 전문 (t1~t7)
    - getWthrInfoList: 기상정보문 목록 (매일 발표되는 기상 해설)"""
    base = 'https://apis.data.go.kr/1360000/WthrWrnInfoService'
    now = datetime.now()
    from_dt = (now - timedelta(days=3)).strftime('%Y%m%d')
    to_dt = now.strftime('%Y%m%d')

    # stn: 화면이 날씨누리 통보문 링크·그림 주소(…_131_4.png)를 만들 때 쓴다
    bulletins = {'warnings_full': [], 'info_list': [], 'stn': WRN_STN}

    # 1) 통보문 본문 (전문)
    try:
        r = shared_get(f'wrn_msg_{WRN_STN}', f'{base}/getWthrWrnMsg', params={
            'serviceKey': DATA_KEY, 'pageNo': 1, 'numOfRows': 15,
            'dataType': 'JSON', 'stnId': WRN_STN,
            'fromTmFc': from_dt, 'toTmFc': to_dt,
        }, timeout=15, max_age=600)
        r.raise_for_status()
        items = r.json()['response']['body'].get('items', {})
        if items:
            items = items.get('item', [])
            if isinstance(items, dict): items = [items]
            for it in items:
                tmFc = str(it.get('tmFc', ''))
                bulletins['warnings_full'].append({
                    'title': it.get('t1', '') or '특보 통보문',
                    'current': it.get('t2', ''),   # 해당구역
                    'time': it.get('t3', ''),       # 발효시각
                    'extra': it.get('t4', ''),      # 내용
                    'summary': it.get('t6', '') or '',  # 이 통보문 뒤의 특보 발효현황
                    'prelim': it.get('t7', '') or '',   # 예비특보
                    'other': it.get('other', ''),   # 참고사항
                    'tmFc': tmFc,
                    'tmFc_display': f'{tmFc[:4]}-{tmFc[4:6]}-{tmFc[6:8]} {tmFc[8:10]}:{tmFc[10:12]}' if len(tmFc) >= 12 else tmFc,
                    'seq': it.get('tmSeq', ''),
                })
    except Exception as e:
        print(f'    통보문: {e}')

    # 2) 기상정보 목록 (매일 발표되는 기상 해설)
    try:
        r = shared_get(f'wrn_info_{WRN_STN}', f'{base}/getWthrInfoList', params={
            'serviceKey': DATA_KEY, 'pageNo': 1, 'numOfRows': 10,
            'dataType': 'JSON', 'stnId': WRN_STN,
            'fromTmFc': from_dt, 'toTmFc': to_dt,
        }, timeout=15, max_age=600)
        r.raise_for_status()
        items = r.json()['response']['body'].get('items', {})
        if items:
            items = items.get('item', [])
            if isinstance(items, dict): items = [items]
            for it in items:
                tmFc = str(it.get('tmFc', ''))
                bulletins['info_list'].append({
                    'title': it.get('title', ''),
                    'tmFc': tmFc,
                    'tmFc_display': f'{tmFc[:4]}-{tmFc[4:6]}-{tmFc[6:8]} {tmFc[8:10]}:{tmFc[10:12]}' if len(tmFc) >= 12 else tmFc,
                    'seq': it.get('tmSeq', ''),
                })
    except Exception as e:
        print(f'    기상정보: {e}')

    # 3) 기상정보 본문 (전국 해설 — 소나기·안개·폭염 등 현황/전망) — getWthrInfo
    #    레이더 카드 옆에 표시할 최신 기상정보 1건. 108(전국) 우선, 없으면 109(수도권).
    try:
        for stn in ('108', str(WRN_STN)):
            r = shared_get(f'wrn_infotext_{stn}', f'{base}/getWthrInfo', params={
                'serviceKey': DATA_KEY, 'pageNo': 1, 'numOfRows': 5,
                'dataType': 'JSON', 'stnId': stn,
                'fromTmFc': from_dt, 'toTmFc': to_dt,
            }, timeout=15)
            r.raise_for_status()
            items = r.json()['response']['body'].get('items', {})
            its = items.get('item', []) if items else []
            if isinstance(its, dict):
                its = [its]
            if its:
                # 최신(tmFc 최대) 1건 선택
                latest = max(its, key=lambda x: str(x.get('tmFc', '')))
                tmFc = str(latest.get('tmFc', ''))
                content = (latest.get('t1') or '').strip()
                if content:
                    bulletins['info_detail'] = {
                        'content': content,
                        'tmFc': tmFc,
                        'tmFc_display': f'{tmFc[:4]}-{tmFc[4:6]}-{tmFc[6:8]} {tmFc[8:10]}:{tmFc[10:12]}' if len(tmFc) >= 12 else tmFc,
                        'stnId': stn,
                        'region': '전국' if stn == '108' else '수도권',
                    }
                    break  # 찾으면 종료 (108 우선)
    except Exception as e:
        print(f'    기상정보 본문: {type(e).__name__}')

    # 4) 지방청 기상정보 본문 (충북 안개·비 현황과 전망 등) — 화면 '기상정보·날씨해설' 카드
    try:
        r = shared_get(f'wrn_infofull_{WRN_STN}', f'{base}/getWthrInfo', params={
            'serviceKey': DATA_KEY, 'pageNo': 1, 'numOfRows': 10,
            'dataType': 'JSON', 'stnId': WRN_STN,
            'fromTmFc': from_dt, 'toTmFc': to_dt,
        }, timeout=15, max_age=600)
        r.raise_for_status()
        items = r.json()['response']['body'].get('items', {})
        its = items.get('item', []) if items else []
        if isinstance(its, dict):
            its = [its]
        out = []
        for it in its:
            # 본문 끝에 글자 그대로의 '\n\n'(역슬래시+n)이 붙어 온다
            text = str(it.get('t1') or '').replace('\\n', '\n').replace('\r', '').strip()
            if text:
                out.append({'text': text, 'tmFc': str(it.get('tmFc', '')), 'seq': it.get('tmSeq', '')})
        out.sort(key=lambda x: x['tmFc'], reverse=True)
        bulletins['info_full'] = out[:6]
    except Exception as e:
        print(f'    지방청 기상정보: {type(e).__name__}')

    # 5) 날씨해설 (지방청 단기 전망 — 하루 두 번) — 공개 API 가 없어 날씨누리 통보문 화면에서 읽는다
    try:
        cmt = fetch_weather_commentary()
        if cmt:
            bulletins['commentary'] = cmt
    except Exception as e:
        print(f'    날씨해설: {type(e).__name__}')

    # 최신순 정렬
    bulletins['warnings_full'].sort(key=lambda x: x['tmFc'], reverse=True)
    bulletins['info_list'].sort(key=lambda x: x['tmFc'], reverse=True)
    return bulletins


def fetch_mid_forecast():
    """기상청 중기전망(날씨해설) — 8~14일 중기 육상 전망 전문(wfSv).
    MidFcstInfoService/getMidFcst. 발표시각 06시/18시.
    날씨누리 '날씨해설'의 중기전망 내용과 동일.
    반환: {'content', 'tmFc', 'tmFc_display'} 또는 None."""
    now = datetime.now()
    hh = now.hour
    # 가장 최근 발표시각 (06시/18시). 발표 직후 30분은 미생산 가능 → 한 단계 이전도 폴백.
    candidates = []
    if hh >= 18:
        candidates = [now.strftime('%Y%m%d') + '1800', now.strftime('%Y%m%d') + '0600']
    elif hh >= 6:
        candidates = [now.strftime('%Y%m%d') + '0600', (now - timedelta(days=1)).strftime('%Y%m%d') + '1800']
    else:
        candidates = [(now - timedelta(days=1)).strftime('%Y%m%d') + '1800', (now - timedelta(days=1)).strftime('%Y%m%d') + '0600']

    for tmfc in candidates:
        try:
            r = shared_get(
                f'mid_fcst_{tmfc}',
                'https://apis.data.go.kr/1360000/MidFcstInfoService/getMidFcst',
                params={'serviceKey': DATA_KEY, 'pageNo': 1, 'numOfRows': 1,
                        'dataType': 'JSON', 'stnId': '108', 'tmFc': tmfc},
                timeout=15, max_age=1800)
            if r.status_code != 200:
                continue
            items = r.json()['response']['body'].get('items', {})
            its = items.get('item', []) if items else []
            if isinstance(its, dict):
                its = [its]
            if its and its[0].get('wfSv'):
                return {
                    'content': its[0]['wfSv'].strip(),
                    'tmFc': tmfc,
                    'tmFc_display': f'{tmfc[:4]}-{tmfc[4:6]}-{tmfc[6:8]} {tmfc[8:10]}:{tmfc[10:12]}',
                }
        except Exception as e:
            print(f'    중기전망({tmfc}): {type(e).__name__}')
    return None


class _SkipSatellite(Exception):
    """위성영상 갱신 건너뜀 — 아직 30분이 안 지났다는 신호(오류 아님)."""


RADAR_STEP_MIN, RADAR_FRAMES = 5, 7      # 상황실 움직이는 레이더 — 최근 30분을 5분 간격 7장


def fetch_radar_frames(img_dir=None):
    """기상청 레이더 합성영상(rdr_cmp_file.php) — 5분 주기, 공개는 약 5분 늦다(2026-11-09 실측: 17:45 에 17:40 까지 있음).
    · 최신 = 올라와 있는 가장 최근 5분 칸. kma_radar.png 로도 저장(지도·재해 화면용).
    · 상황실용으로 최근 30분 5분 간격 7장을 images/radar/RDR_<tm>.png 로 모으고, 목록을 images/radar/frames.json 에 쓴다.
      이미 받은 시각은 다시 받지 않고 2시간 지난 파일은 지운다(.gitignore — 깃에 안 올린다).
    · 서버(live_local --collect)가 1분마다 --radar-only 로 이것만 따로 부른다 → 화면 지연이 '공개 5분 + 최대 2분'."""
    if img_dir is None:
        img_dir = os.path.join(str(ROOT), 'images')
    now = datetime.now()

    def _rdr(tm):
        u = f'https://apihub.kma.go.kr/api/typ04/url/rdr_cmp_file.php?tm={tm}&data=img&cmp=cmb&authKey={KMA_APIHUB_KEY}'
        rr = requests.get(u, timeout=20)
        return rr.content if (rr.status_code == 200 and rr.content.startswith(b'\x89PNG')) else None

    rdir = os.path.join(img_dir, 'radar')
    os.makedirs(rdir, exist_ok=True)
    base = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
    latest_dt, latest_png = None, None
    # 호출 아끼기 — 다음 5분 칸은 그 시각보다 약 5분 뒤에 올라온다. 가진 최신 칸에서 9분이 안 지났으면 묻지 않는다
    #   (1분마다 불러도 실제 호출은 5분에 1~2번, 하루 약 400번).
    have = sorted(fn[4:16] for fn in os.listdir(rdir) if fn.startswith('RDR_') and fn.endswith('.png'))
    hd = None
    if have:
        try:
            hd = datetime.strptime(have[-1], '%Y%m%d%H%M')
        except ValueError:
            hd = None
    if hd and now - hd > timedelta(minutes=45):
        hd = None                                  # 너무 오래된 칸은 없는 셈 치고 처음부터 찾는다
    if hd and now - hd < timedelta(minutes=9):
        latest_dt = hd
    elif hd:
        # 2026-11-12 — 기상청이 10:40~ 합성영상을 늦게 올렸을 때 예전 코드는 25·35·40분 전 칸을 건너뛰어
        #   이미 받은 10:35 대신 10:30 으로 물러났다. 이제 가진 최신 칸 '다음'부터 차례로 묻는다(밀린 칸도 채운다).
        #   빠진 칸이 있으면 가장 새 칸·그 앞 칸만 한 번 더 확인 → 기상청 지연 중에도 1분에 최대 3번만 묻는다.
        latest_dt = hd
        t = hd + timedelta(minutes=RADAR_STEP_MIN)
        while t <= base:
            png = _rdr(t.strftime('%Y%m%d%H%M'))
            if not png:
                break
            _atomic_write_bytes(os.path.join(rdir, f'RDR_{t:%Y%m%d%H%M}.png'), png)
            latest_dt, latest_png = t, png
            t += timedelta(minutes=RADAR_STEP_MIN)
        if t <= base:                               # 중간 칸이 비었다 — 더 새 칸이 따로 올라왔는지
            for cand in (base, base - timedelta(minutes=RADAR_STEP_MIN)):
                if cand <= t:
                    continue
                png = _rdr(cand.strftime('%Y%m%d%H%M'))
                if png:
                    latest_dt, latest_png = cand, png
                    break
    else:
        for back in range(0, 50, RADAR_STEP_MIN):   # 받은 칸이 없을 때 — 지금부터 45분 전까지 5분마다
            cand = base - timedelta(minutes=back)
            png = _rdr(cand.strftime('%Y%m%d%H%M'))
            if png:
                latest_dt, latest_png = cand, png
                break
    if latest_dt is None:
        return {'ok': False, 'err': 'no PNG (최근 45분 없음)'}
    radar_tm = latest_dt.strftime('%Y%m%d%H%M')
    if latest_png:
        _atomic_write_bytes(os.path.join(rdir, f'RDR_{radar_tm}.png'), latest_png)
        _atomic_write_bytes(os.path.join(img_dir, 'kma_radar.png'), latest_png)
    frames = []
    for k in range(RADAR_FRAMES - 1, -1, -1):          # 30분 전 → 최신
        t = (latest_dt - timedelta(minutes=RADAR_STEP_MIN * k)).strftime('%Y%m%d%H%M')
        fp = os.path.join(rdir, f'RDR_{t}.png')
        if not os.path.exists(fp):
            png = _rdr(t)
            if not png:
                continue
            _atomic_write_bytes(fp, png)
        frames.append(t)
    cut = (now - timedelta(hours=2)).strftime('%Y%m%d%H%M')
    for fn in os.listdir(rdir):
        if fn.startswith('RDR_') and fn[4:16] < cut:
            try:
                os.remove(os.path.join(rdir, fn))
            except OSError:
                pass
    info = {'ok': True, 'ts': now.strftime('%Y-%m-%d %H:%M'), 'tm': radar_tm, 'frames': frames}
    _atomic_write_text(os.path.join(rdir, 'frames.json'), json.dumps(info, ensure_ascii=False))
    return info


def _atomic_write_bytes(path, data):
    tmp = f'{path}.tmp.{os.getpid()}'     # 5분 수집과 1분 레이더가 같은 파일을 동시에 써도 임시파일이 겹치지 않게
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)


def download_kma_images():
    """기상청 API 허브 이미지(충북 특보 발효현황·레이더·천리안 위성)를 images/ 에 저장한다.
    인증키가 주소에 들어가므로 서버에서만 받고, 사이트에는 그림 파일만 올린다.
    Returns: {wrn|radar|satellite: {ok, ts, ...}}"""
    import os
    if not KMA_APIHUB_KEY:
        return {'wrn': {'ok': False}}

    # 프로젝트 루트의 images/ 폴더
    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    img_dir = os.path.join(proj_root, 'images')
    os.makedirs(img_dir, exist_ok=True)

    now = datetime.now()
    tm = now.strftime('%Y%m%d%H%M')
    ts = now.strftime('%Y-%m-%d %H:%M')

    result = {}

    # 1) nph-wrn7 (특보 발효 현황) — 충청북도를 가운데 둔 확대 그림.
    #    lon·lat 가 중심, range 가 반경(km). 105km 면 충북 전역(영동~단양)이 한 장에 들어온다.
    #    city·name=1 시군 경계·이름, tmef=1 발효시각 표기, wrn 은 특보 종류 전체.
    try:
        wm = P.get('wrn_map') or {'lon': 127.9, 'lat': 36.68, 'range': 105}
        url = (f'https://apihub.kma.go.kr/api/typ03/cgi/wrn/nph-wrn7?tm={tm}'
               f'&lon={wm["lon"]}&lat={wm["lat"]}&range={wm["range"]}&size=600'
               f'&city=1&name=1&tmef=1&wrn=W,R,C,D,O,V,T,S,Y,H,&authKey={KMA_APIHUB_KEY}')
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and r.headers.get('Content-Type', '').startswith('image/'):
            path = os.path.join(img_dir, 'kma_warn.png')
            with open(path, 'wb') as f:
                f.write(r.content)
            result['wrn'] = {'ok': True, 'ts': ts, 'bytes': len(r.content)}
        else:
            result['wrn'] = {'ok': False, 'err': f'HTTP {r.status_code}'}
    except Exception as e:
        result['wrn'] = {'ok': False, 'err': _redact(e)}

    def _is_real_image_png(content):
        """기상청이 자료가 없을 때 주는 'err = -11' 글자 그림(1-bit, 1KB 미만)을 걸러낸다.
        정상 그림은 8-bit 이상이다. 크기 하한은 잘린 응답 방어용으로만 둔다(정상은 비가 적으면 20KB대까지 작아진다)."""
        if not content.startswith(b'\x89PNG') or len(content) < 26:
            return False
        if content[24] < 4:          # IHDR bit_depth
            return False
        return len(content) >= 5000

    # 3) 레이더 — fetch_radar_frames() (서버가 1분마다 --radar-only 로도 따로 부른다)
    try:
        result['radar'] = fetch_radar_frames(img_dir)
    except Exception as e:
        result['radar'] = {'ok': False, 'err': _redact(e)}

    # 4) 천리안 GK2A 위성 IR105 + 한반도 (10분 주기, 자료 publish 약 6시간 지연)
    # 06시 발표 자료가 12시쯤 공개되는 식. 안전하게 6시간 전부터 10분 배수로 시도.
    #
    # ⚠ 이 파일만 900KB로 다른 이미지(8~26KB)보다 40배 무겁다. 5분마다 새로 받아
    #   커밋하면 하루 260MB가 깃에 쌓이고(전체 증가량의 절반), 그만큼 히스토리 압축이
    #   자주 돌아 다른 클론의 히스토리를 깨뜨린다.
    #   어차피 6시간 지연 공개 자료라 5분 단위 신선도가 의미 없으므로 30분마다만 갱신한다.
    #   (건너뛰면 result에 'satellite' 키를 안 넣는다 → main()이 이전 메타를 그대로 보존)
    try:
        sat_path = os.path.join(img_dir, 'kma_satellite.png')
        _sat_fresh = False
        try:
            if os.path.exists(sat_path):
                _age_min = (time.time() - os.path.getmtime(sat_path)) / 60
                _sat_fresh = _age_min < 30
        except OSError:
            _sat_fresh = False
        if _sat_fresh:
            raise _SkipSatellite()
        ok = False
        # 6시간 전부터 24시간 전까지 1시간 간격으로 폴백
        for back_min in (360, 420, 480, 540, 600, 720, 1080, 1440):
            sat_dt = now - timedelta(minutes=back_min)
            sat_dt = sat_dt.replace(minute=(sat_dt.minute // 10) * 10, second=0, microsecond=0)
            sat_date = sat_dt.strftime('%Y%m%d%H%M')
            url = f'https://apihub.kma.go.kr/api/typ05/api/GK2A/LE1B/IR105/KO/image?date={sat_date}&authKey={KMA_APIHUB_KEY}'
            r = requests.get(url, timeout=20)
            if r.status_code == 403:
                result['satellite'] = {'ok': False, 'err': '활용신청 대기'}
                ok = True
                break
            if r.status_code == 200 and _is_real_image_png(r.content):
                with open(sat_path, 'wb') as f:
                    f.write(r.content)
                result['satellite'] = {'ok': True, 'ts': ts, 'date': sat_date, 'bytes': len(r.content)}
                ok = True
                break
        if not ok:
            result['satellite'] = {'ok': False, 'err': '최근 24h 정상 이미지 없음'}
    except _SkipSatellite:
        pass          # 30분 안 지남 — 이전 이미지·메타 그대로 사용(깃 커밋량 절감)
    except Exception as e:
        result['satellite'] = {'ok': False, 'err': _redact(e)}

    return result


def fetch_apihub_warnings():
    """기상청 API 허브 wrn_now_data_new.php — 현재 발효 중인 특보·예비특보 종합.

    공공데이터포털 getPwnStatus가 t6/t7 텍스트로만 주는 것을 구조화된 행 데이터로 받음.
    응답: EUC-KR 텍스트, 헤더 #로 시작.
    필드: REG_UP, REG_UP_KO, REG_ID, REG_KO, TM_FC, TM_EF, WRN, LVL, CMD, ED_TM
      - WRN/LVL/CMD: 한글 그대로 ('호우','예비','발표' 등)
      - LVL='예비' → 예비특보, '주의'→주의보, '경보'→경보
      - 이미 '현재 살아있는' 발표만 들어옴 (해제·만료 자동 제외됨)

    이 endpoint는 wrn_met_data.php(이력)보다 정확. 사장님이 본 호우 예비특보가 직접 들어옴.
    """
    if not KMA_APIHUB_KEY:
        return []

    url = 'https://apihub.kma.go.kr/api/typ01/url/wrn_now_data_new.php'
    try:
        r = shared_get('apihub_wrn_now', url, params={'authKey': KMA_APIHUB_KEY}, timeout=15, max_age=240)
        r.raise_for_status()
        # 응답은 EUC-KR 인코딩
        text = r.content.decode('euc-kr', errors='replace')
    except Exception as e:
        print(f'    [apihub] 특보현황: {e}')
        return None   # 수집 실패 — 정상 0건([])과 구분(main에서 이전값 보존)

    north = SIGUN_SET   # 이 상황판 관할 시군 (프로파일)

    items = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # 줄 끝 '=' 제거 후 쉼표 분리
        line = line.rstrip(' =').rstrip(',').rstrip()
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 10:
            continue
        reg_up, reg_up_ko, reg_id, reg_ko, tm_fc, tm_ef, wrn, lvl, cmd, ed_tm = parts[:10]

        # 해제 또는 변경해제는 제외 (현재 살아있는 것만)
        if cmd in ('해제', '대치해제', '변경해제'):
            continue

        # 지역 매칭 — '이름에 글자가 들어있나'가 아니라 특보구역 '코드'로 판정한다.
        # ⚠ 예전엔 f'{reg_up_ko} {reg_ko}'에 관할 시군명이 들어있는지만 봤다. 그래서
        #   관할에 '광주'(경기 광주시)가 있는 경기남부에서, 광주'광역시'의 특보구역인
        #   '광주동부·광주서부'(L1130xxx)가 통째로 우리 관할로 잡혔다. 광주광역시에
        #   호우경보가 나면 경기남부 상황실에 '호우경보 발효'가 뜬다는 뜻이다.
        #   (2026-08-17 전체 점검에서 발견 — 2026-08-15 가짜 재난문자와 같은 부류)
        #   NORTH_GG_REG_MAP은 프로파일이 들고 있는 '관할 특보구역 코드' 정본이라
        #   이름 충돌이 원천적으로 없다. 경기 육상 특보구역은 전부 L101xxxx 계열이다.
        _rid = str(reg_id or '')
        is_north_gg = _rid in NORTH_GG_REG_MAP
        # 경기 전체(관할 밖 경기 시군 포함) — 화면의 '경기도 특보' 집계용
        is_gyeonggi = is_north_gg or _rid.startswith(WRN_PREFIX)

        # 시간 포맷
        def fmt(s):
            s = str(s or '')
            if len(s) >= 12:
                return f'{s[4:6]}/{s[6:8]} {s[8:10]}:{s[10:12]}'
            return s

        items.append({
            'reg_up': reg_up,
            'reg_up_ko': reg_up_ko,
            'reg_id': reg_id,
            'reg_ko': reg_ko,
            'region_name': reg_ko,            # 표시용 (지역명)
            'broader_region': reg_up_ko,      # 상위 광역
            'tm_fc': tm_fc, 'tm_ef': tm_ef,
            'tm_fc_disp': fmt(tm_fc),
            'tm_ef_disp': fmt(tm_ef),
            'wrn_name': wrn,                  # 한글 그대로 ('호우','강풍','풍랑'...)
            'lvl_name': lvl,                  # '예비'/'주의'/'경보'
            'cmd_name': cmd,                  # '발표'/'대치'/'연장'/'변경'
            'ed_tm': ed_tm,                   # 해제 예고 시각 텍스트
            'is_north_gg': is_north_gg,
            'is_gyeonggi': is_gyeonggi,
            'is_prelim': lvl == '예비',
        })

    # 정렬: 북부 > 경기 > 그 외, 예비/주의/경보 순서는 LVL 한글이라 별도 정렬 안 함
    def sort_key(it):
        return (
            0 if it['is_north_gg'] else (1 if it['is_gyeonggi'] else 2),
            0 if it['lvl_name'] == '경보' else (1 if it['lvl_name'] == '주의' else 2),
        )
    items.sort(key=sort_key)
    return items


def parse_prelim_warnings(t7_text, tmFc=''):
    """t7 필드(예비특보)의 텍스트를 구조화된 객체로 파싱.

    t7 예시:
      "(1) 강풍 예비특보\r\n
       o 05월 20일 오후(12시~18시) : 서해5도\r\n
       o 05월 20일 밤(18시~24시) : 제주도(제주도산지, ...)\r\n
       (2) 풍랑 예비특보\r\n
       o 05월 20일 오후(12시~18시) : 서해중부안쪽먼바다, ..."

    리턴: [{type, items:[{time, area, north_match:bool}]}]
    """
    import re as _re
    if not t7_text or t7_text.strip() in ('o 없음', '없음', ''):
        return []

    # 줄 단위 분리 (CRLF·LF 모두)
    lines = [ln.strip() for ln in _re.split(r'[\r\n]+', t7_text) if ln.strip()]

    groups = []
    cur = None
    for ln in lines:
        # 그룹 헤더: "(1) 강풍 예비특보"
        m = _re.match(r'\(\d+\)\s*(.+?예비특보)', ln)
        if m:
            cur = {'type': m.group(1).strip(), 'items': []}
            groups.append(cur)
            continue
        # 항목: "o 05월 20일 오후(12시~18시) : 서해5도"
        m = _re.match(r'^[o○\-•]\s*(.+?)\s*:\s*(.+)$', ln)
        if m and cur is not None:
            time_str = m.group(1).strip()
            area = m.group(2).strip()
            north_match = any(k in _drop_sea_zones(area) for k in NORTH_GG_KEYWORDS)   # 바다 예비특보는 관내 아님
            cur['items'].append({'time': time_str, 'area': area, 'north_match': north_match})

    # 발표 시각 형식 변환
    tmFc_str = ''
    if len(tmFc) >= 12:
        tmFc_str = f'{tmFc[4:6]}/{tmFc[6:8]} {tmFc[8:10]}:{tmFc[10:12]}'

    # 각 그룹에 발표 시각 부여 + 빈 그룹 제거
    result = []
    for g in groups:
        if not g['items']:
            continue
        north_count = sum(1 for it in g['items'] if it['north_match'])
        g['tmFc'] = tmFc_str
        g['north_count'] = north_count   # 경기북부 매칭 항목 수
        g['total_count'] = len(g['items'])
        result.append(g)
    return result


def fetch_warnings():
    """현재 발효 중인 기상특보(t6) + 예비특보(t7) — 경기북부 시군 매칭."""
    url = 'https://apis.data.go.kr/1360000/WthrWrnInfoService/getPwnStatus'
    params = {
        'serviceKey': DATA_KEY,
        'pageNo': 1,
        'numOfRows': 50,
        'dataType': 'JSON',
        'stnId': WRN_STN,  # 시도 담당 지방기상청 (109 수도권 · 105 강원 …)
    }
    r = shared_get(f'pwn_status_{WRN_STN}', url, params=params, timeout=15, max_age=240)
    r.raise_for_status()
    resp = r.json()['response']
    code = str(resp.get('header', {}).get('resultCode', ''))
    # data.go.kr은 인증오류·쿼터초과·일시장애에도 HTTP 200 + 비정상 resultCode를 준다.
    # '00'(정상)이 아니면 예외로 올려 main에서 이전 특보 보존(해제→재발효 오알림 방지).
    if code != '00':
        raise RuntimeError(f"기상특보 API resultCode={code} "
                           f"{resp.get('header', {}).get('resultMsg', '')}")
    body = resp['body']
    items_obj = body.get('items', {})
    if not items_obj:
        return {'active': [], 'prelim': []}
    items = items_obj.get('item', []) if isinstance(items_obj, dict) else items_obj
    if isinstance(items, dict):
        items = [items]

    active = []
    prelim_all = []
    seen = set()
    for it in items:
        tmFc = str(it.get('tmFc', ''))
        time_str = f'{tmFc[8:10]}:{tmFc[10:12]}' if len(tmFc) >= 12 else ''

        # t6 = 발효 중 특보 (예: "호우주의보 : 동두천시, 양주시, ...")
        # 여러 줄 가능, 각 줄이 하나의 특보
        t6 = it.get('t6', '') or ''
        for line in t6.split('\n'):
            line = line.strip().lstrip('o○').strip()
            if ':' not in line:
                continue
            head, body_text = line.split(':', 1)
            head, body_text = head.strip(), body_text.strip()
            wrn_type = next((w for w in WRN_TYPES if w in head), None)
            if not wrn_type:
                continue
            body_text = _strip_area_wrappers(_drop_sea_zones(body_text))   # 바다 구역 제외, '경기도(수원)' 의 '경기도'는 근거가 아니다
            matched = [k for k in NORTH_GG_KEYWORDS if _kw_in_text(body_text, k)]
            if not matched:
                continue
            area_text = _expand_areas(', '.join(matched))
            key = (wrn_type, area_text)
            if key in seen:
                continue
            seen.add(key)
            level = 'severe' if '경보' in wrn_type else 'warning'
            active.append({'type': wrn_type, 'area': area_text, 'time': time_str, 'level': level})

        # t7 = 예비특보 (별도 구조라 별도 파서 사용)
        t7 = it.get('t7', '') or ''
        prelim_all.extend(parse_prelim_warnings(t7, tmFc))

    return {'active': active[:8], 'prelim': prelim_all}


# ============================================================
# 4. 미세먼지 (에어코리아 - 시도별 실시간 측정정보)
# ============================================================

def pm_grade(pm10, pm25):
    # 측정 누락(None)은 등급에서 제외. 둘 다 없으면 '정보없음'.
    if pm10 is None and pm25 is None:
        return 'none', '정보없음'
    def g10(v):
        if v is None: return -1
        return 0 if v <= 30 else 1 if v <= 80 else 2 if v <= 150 else 3
    def g25(v):
        if v is None: return -1
        return 0 if v <= 15 else 1 if v <= 35 else 2 if v <= 75 else 3
    lvl = max(g10(pm10), g25(pm25), 0)   # 측정된 항목 중 가장 나쁜 등급
    return [('good', '좋음'), ('normal', '보통'), ('bad', '나쁨'), ('vbad', '매우나쁨')][lvl]


PM_CACHE_AGE = 7200     # 시각 칸 키와 함께 — 한 시간 칸 안에서는 다시 안 받는다(한도 대책, 2026-09-20)


def _pm_bucket():
    """에어코리아는 정시 측정값을 :10~:20 쯤 낸다 → '지금−20분'의 시(時)를 칸으로. 13:25 부터 13시 자료를 새로 받고,
    13:05 엔 12시 칸(이미 받은 것)을 그대로 쓴다 → 시간마다 정확히 1회."""
    return (datetime.now() - timedelta(minutes=20)).strftime('%Y%m%d%H')


def _pm_items_nationwide(url, sidos):
    """전국 1회 호출(sidoName=전국) → 우리 시도 항목만. 회차당 1회를 모든 프로파일이 공유한다(한도 대책).
    응답이 이상하거나(시도 표시 없음·빈 결과) 우리 시도가 하나도 없으면 None → 호출측이 시도별 호출로 되돌아간다."""
    params = {'serviceKey': DATA_KEY, 'returnType': 'json', 'numOfRows': 1000, 'pageNo': 1,
              'sidoName': '전국', 'ver': '1.3'}
    r = shared_get(f'pm_전국_{_pm_bucket()}', url, params=params, timeout=20, max_age=PM_CACHE_AGE)
    r.raise_for_status()
    body = (r.json().get('response') or {}).get('body') or {}
    items = body.get('items') or []
    if not items or not any(it.get('sidoName') for it in items):
        return None
    try:
        total = int(body.get('totalCount') or 0)
    except (TypeError, ValueError):
        total = 0
    if total and len(items) < total:          # 한 쪽에 다 안 담김(numOfRows 상한) → 일부 시도가 빠질 수 있어 못 쓴다
        return None
    mine = [it for it in items if it.get('sidoName') in sidos]
    return mine or None


def fetch_pm():
    url = 'https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty'
    # 통합시(전남광주)는 에어코리아가 아직 광주·전남으로 나눠 준다 → 시도 목록으로 거른다
    sidos = [PM_SIDO] if isinstance(PM_SIDO, str) else list(PM_SIDO)
    # 2026-09-20 일일 한도 초과(429): 시도 16곳 × 25분 ≈ 930회/일 > 한도. 전국 1회 호출을 먼저, 안 되면 시도별.
    items = None
    try:
        items = _pm_items_nationwide(url, sidos)
    except Exception as e:
        print(f'  · 미세먼지 전국 호출 실패({type(e).__name__}) — 시도별 호출로')
    if items is None:
        items = []
        for sido in sidos:
            params = {
                'serviceKey': DATA_KEY,
                'returnType': 'json',
                'numOfRows': 200,
                'pageNo': 1,
                'sidoName': sido,
                'ver': '1.3',
            }
            r = shared_get(f'pm_{sido}_{_pm_bucket()}', url, params=params, timeout=15, max_age=PM_CACHE_AGE)
            r.raise_for_status()
            body = r.json()['response']['body']
            items += body.get('items', []) or []

    by_station = {it['stationName']: it for it in items if it.get('stationName')}

    result = []
    for region_name, station in PM_STATIONS.items():
        it = by_station.get(station)
        if not it:
            # 측정소명이 정확히 일치하지 않으면 부분 일치 시도
            for sname, sit in by_station.items():
                if region_name in sname or sname in (PM_STATIONS.get(region_name, '')):
                    it = sit; break
        if not it:
            continue
        try:
            def _pmv(key):
                v = it.get(key, '')
                try:
                    return int(float(v)) if v not in ('', '-', None) else None
                except (ValueError, TypeError):
                    return None
            pm10 = _pmv('pm10Value')
            pm25 = _pmv('pm25Value')
            grade, grade_text = pm_grade(pm10, pm25)
            # 오존·통합대기지수(CAI) — 응답에 이미 포함, 파싱만 추가
            def _f(key):
                v = it.get(key, '')
                try:
                    return float(v) if v not in ('', '-', None) else None
                except (ValueError, TypeError):
                    return None
            o3 = _f('o3Value')             # 오존 농도 (ppm)
            khai = _f('khaiValue')         # 통합대기환경지수 (0~500)
            khai_grade = it.get('khaiGrade', '') or ''   # 1좋음 2보통 3나쁨 4매우나쁨
            cai_text = {'1': '좋음', '2': '보통', '3': '나쁨', '4': '매우나쁨'}.get(str(khai_grade), '')
            result.append({
                'region': region_name, 'pm10': pm10, 'pm25': pm25,
                'grade': grade, 'gradeText': grade_text,
                'o3': o3, 'khai': khai, 'cai_grade': khai_grade, 'cai_text': cai_text,
            })
        except Exception:
            continue
    return result


# ============================================================
# 5. 산불 위험도 (국립산림과학원)
# ============================================================

def fetch_fire_incidents():
    """산림청 산불발생통계정보 — 최근 1년치 산불 발생 통계.
    endpoint: https://apis.data.go.kr/1400000/forestStusService/getfirestatsservice
    응답: XML. 필드 — damagearea, firecause, locsi(시도), locgungu(시군구),
                       startyear/startmonth/startday/starttime."""
    import re as _re
    url = 'https://apis.data.go.kr/1400000/forestStusService/getfirestatsservice'
    now = datetime.now()
    # 최근 365일치 수집
    sdt = (now - timedelta(days=365)).strftime('%Y%m%d')
    edt = now.strftime('%Y%m%d')

    try:
        r = shared_get('fire_incidents', url, max_age=3600, params={
            'ServiceKey': DATA_KEY,  # 활용가이드 표기대로 대문자 S
            'searchStDt': sdt,
            'searchEdDt': edt,
            'numOfRows': 2000,  # 1년치 충분히
            'pageNo': 1,
        }, timeout=60)
        if r.status_code != 200:
            print(f'    산불발생: HTTP {r.status_code}')
            return {'incidents': [], 'summary': None}

        # XML 파싱 (간단한 정규식)
        items = []
        for m in _re.finditer(r'<item>(.*?)</item>', r.text, _re.DOTALL):
            block = m.group(1)
            rec = {}
            for tag in _re.findall(r'<([a-zA-Z]+)>([^<]*)</\1>', block):
                rec[tag[0]] = tag[1]
            items.append(rec)

        if not items:
            return {'incidents': [], 'summary': {
                'total': 0, 'north': 0, 'gyeonggi': 0,
                'this_year_total': 0, 'this_year_north': 0,
                'latest_north': [], 'latest_all': [],
            }}

        # 정규화: 시작일·발생일 텍스트, 지역 정리
        north_sigun = SIGUN_SET   # 이 상황판 관할 시군 (프로파일)
        cur_year = now.strftime('%Y')

        def norm(it):
            sigun = it.get('locgungu', '')
            sido = it.get('locsi', '')
            occr_dt = f"{it.get('startyear','')}-{it.get('startmonth','').zfill(2)}-{it.get('startday','').zfill(2)} {it.get('starttime','')}"
            end_dt = f"{it.get('endyear','')}-{it.get('endmonth','').zfill(2)}-{it.get('endday','').zfill(2)} {it.get('endtime','')}"
            try:
                damage = float(it.get('damagearea', 0) or 0)
            except ValueError:
                damage = 0
            return {
                'sido': sido,
                'sigungu': sigun,
                'address': f"{sido} {sigun} {it.get('locmenu','')} {it.get('locdong','')} {it.get('locbunji','')}".strip(),
                'cause': it.get('firecause', ''),
                'occur_time': occr_dt.strip(' :-'),
                'end_time': end_dt.strip(' :-'),
                'damage_area': damage,
                'year': it.get('startyear', ''),
                'is_north': sigun in north_sigun,
                'is_gyeonggi': any(w in sido for w in SIDO_WORDS),
                'is_this_year': it.get('startyear', '') == cur_year,
            }

        normalized = [norm(it) for it in items]
        # 최신순 정렬 (occur_time desc)
        normalized.sort(key=lambda x: x['occur_time'], reverse=True)

        north_all = [x for x in normalized if x['is_north']]
        gg_all    = [x for x in normalized if x['is_gyeonggi']]
        this_yr_total = sum(1 for x in normalized if x['is_this_year'])
        this_yr_north = sum(1 for x in normalized if x['is_this_year'] and x['is_north'])

        summary = {
            'total': len(normalized),            # 최근 1년 전국
            'north': len(north_all),             # 최근 1년 경기북부
            'gyeonggi': len(gg_all),             # 최근 1년 경기도 전체
            'this_year_total': this_yr_total,    # 올해 전국
            'this_year_north': this_yr_north,    # 올해 경기북부
            'latest_north': north_all[:8],       # 최근 경기북부 산불 8건
            'latest_all': normalized[:5],        # 최근 전국 5건
        }
        return {'incidents': north_all, 'summary': summary}
    except Exception as e:
        print(f'    산불발생: {e}')
        return {'incidents': [], 'summary': None}


def fetch_fire():
    """국립산림과학원 산불위험예보 V2 — 시군구별 위험도.
    단계는 공식 판정과 같이 시군 평균 지수(meanavg)로 정한다(2026-11-11):
      낮음 50 이하 · 다소높음 51~65 · 높음 66~85 · 매우높음 86 이상
      (국립산림과학원 「산불발생위험예측」 등급표, 산불위험예보시스템 '산불위험지역(높음 이상)' 목록도 시군구 평균값 기준)
    d1~d4 는 시군 안 단계별 면적 비율(%) — 일부만 높은지 보여 주는 참고값으로만 싣는다.
    예전엔 높은 단계가 1%라도 있으면 그 단계로 쳐서 공식 판정보다 높게 나왔다."""
    url = 'https://apis.data.go.kr/1400377/forestPointV2/forestPointListSigunguSearchV2'
    r = shared_get('fire_point', url, max_age=1500, params={
        'serviceKey': DATA_KEY,
        'pageNo': 1,
        'numOfRows': 300,
        '_type': 'json',
    }, timeout=15)
    r.raise_for_status()
    body = r.json()['response']['body']
    items_obj = body.get('items', {})
    if not items_obj:
        return []
    items = items_obj.get('item', [])
    if isinstance(items, dict):
        items = [items]

    # 산불 API의 시군 표기 → 관서명 (구가 있는 시는 구 단위로 내려온다)
    sigun_map = P['fire_sigun_map']

    # 시를 나눠 맡는 관서(청주동부·청주서부)는 시 이름 하나로 — 산불 API 가 청주시를 한 줄로 준다
    parent_of = {s: p for p, subs in (P.get('splits') or {}).items() for s in subs}

    # 2026-11-11 시군별로 바꿈 — 예전엔 북→남 3개씩 묶은 '권역'의 최댓값을 보여 줘서
    #   단양만 높아도 충주 관서에 '높음'이 떴다(권역은 국립산림과학원이 아니라 우리가 만든 묶음이었다).
    by_name = {}
    for it in items:
        if not str(it.get('doname', '')).startswith(tuple(SIDO_WORDS)):
            continue
        sigun = str(it.get('sigun', '')).strip()
        target = sigun_map.get(sigun)
        if not target:
            continue
        name = parent_of.get(target, target)
        pct = [float(it.get(k, 0) or 0) for k in ('d1', 'd2', 'd3', 'd4')]
        try:
            mean = float(str(it.get('meanavg', '')).replace(',', ''))
        except ValueError:
            continue
        idx = round(mean)
        level = 4 if idx >= 86 else 3 if idx >= 66 else 2 if idx >= 51 else 1
        try:
            mx = round(float(str(it.get('maxi', '')).replace(',', '')))
        except ValueError:
            mx = None
        old = by_name.get(name)
        if not old or idx > old['index']:   # 구 단위로 여러 줄이 오는 시는 가장 높은 구
            by_name[name] = {'level': level, 'index': idx, 'max': mx, 'pct': [round(v) for v in pct]}

    # 순서는 관서 순서(region_order — 청주동부·청주서부·충주·제천·…·단양, 2026-11-12 사용자 지정)를 따른다.
    #   [0]은 시도 전역 이름이라 뺀다. 청주동부·청주서부는 '청주' 한 칸.
    order = []
    for members in [list(P.get('region_order') or [])[1:]] + list(P['fire_groups'].values()):
        for m in members:
            m = parent_of.get(m, m)
            if m not in order:
                order.append(m)
    order += [n for n in by_name if n not in order]
    text_map = {1: '낮음', 2: '다소높음', 3: '높음', 4: '매우높음'}
    result = []
    for name in order:
        v = by_name.get(name)
        if not v:
            continue
        result.append({'region': name, 'level': v['level'], 'levelText': text_map[v['level']],
                       'index': v['index'], 'max': v['max'], 'pct': v['pct']})
    return result


# ============================================================
# 6. 하천 수위 (한강홍수통제소)
# ============================================================

# 경기북부 주요 관측소 — 한강홍수통제소 실제 등록 코드 및 기준수위
# has_cctv: CCTV iframe 표시 여부 (False 시 자료 페이지 링크)
# api: 'waterlevel' (일반 하천) 또는 'dam' (댐 시설 — 저수위·저수율·유입·방류)
# 하천·댐 관측소.
#  · warning/danger = 한강홍수통제소 info API의 attwl(관심)/almwl(경계). 임의값 아님.
#    (2026-07-23 API 조회로 확정. 기존 8개소는 이 매핑과 이미 일치함을 실측 확인.)
#  · 댐은 attwl이 없어 fldlmtwl(홍수기제한수위)/pfh(계획홍수위)를 쓴다. 없으면 warning=None
#    (riverLevel이 null을 안전하게 건너뜀). 군남댐은 기존 수동값 유지.
#  · sigun = 관서 매칭용 명시 필드. 예전엔 이름 문자열로 매칭해서 '양주'가 '남양주'에도
#    걸려 남양주 하천이 양주 관서에 뜨는 충돌이 있었다. 이름에 의존하지 않는다.
RIVER_STATIONS = P['river_stations']


def river_level(value, warning, danger):
    """수위 → 단계. 기준값이 없는 관측소(댐 중 제한수위 미제공)가 있어 None을 견뎌야 한다.
    None 비교는 파이썬에서 TypeError라, 방어 없이 쓰면 그 관측소가 통째로 사라진다."""
    if value is None:
        return 'safe'
    if danger is not None and value >= danger:
        return 'danger'
    if warning is not None and value >= warning:
        return 'warning'
    return 'safe'


def fetch_rivers_by_station():
    """[폴백] 관측소별 24시간 수위 시계열 수집 — 일괄 수신(fetch_rivers)이 실패했을 때만.
    한강홍수통제소(api.hrfco.go.kr)가 외국 IP(GitHub Actions 미국 서버 등)에서
    매우 느리거나 timeout. 환경별 차등 처리:
    - 정상(한국 IP): timeout 8초 × 2회 재시도 → 첫 시도에서 거의 성공
    - 외국 IP: timeout 5초 × 1회 → 약 5-10초 안에 fail, main()에서 기존 데이터 보존
    """
    import os
    # GitHub Actions 환경 감지 — 자동 단축 모드
    is_ci = bool(os.environ.get('GITHUB_ACTIONS'))
    max_attempts = 1 if is_ci else 2
    req_timeout = 5 if is_ci else 8
    retry_wait = 1 if is_ci else 2
    station_gap = 0.2 if is_ci else 0.8

    result = []
    now = datetime.now()
    sdt = (now - timedelta(hours=24)).strftime('%Y%m%d%H')
    edt = now.strftime('%Y%m%d%H')

    sess = requests.Session()
    sess.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'application/json',
        'Connection': 'close',
    })

    # 같은 관측소를 여러 관서가 나눠 쓰는 경우가 있다(안양천 충훈1교 = 안양·과천·군포·의왕).
    # 코드별로 한 번만 부르고 결과를 돌려쓴다 — 안 그러면 5분마다 같은 호출을 네 번 한다.
    fetched = {}

    for st_idx, st in enumerate(RIVER_STATIONS):
        cache_key = (st['code'], st.get('api', 'waterlevel'))
        if cache_key in fetched:
            base = fetched[cache_key]
            if base is not None:
                item = dict(base)
                item.update({'name': st['name'], 'sigun': st.get('sigun', ''),
                             'warning': st.get('warning'), 'danger': st.get('danger'),
                             'has_cctv': st.get('has_cctv', False)})
                item['level'] = river_level(item.get('value'), st.get('warning'),
                                            st.get('danger'))
                result.append(item)
            continue

        if st_idx > 0:
            time.sleep(station_gap)  # 관측소 사이 텀

        last_err = None
        api = st.get('api', 'waterlevel')
        wl_field = 'swl' if api == 'dam' else 'wl'  # 댐은 저수위(swl), 하천은 수위(wl)
        fetched[cache_key] = None   # 실패해도 같은 코드를 다시 부르지 않도록 자리 예약

        for attempt in range(max_attempts):
            try:
                url = f'https://api.hrfco.go.kr/{HRFCO_KEY}/{api}/list/1H/{st["code"]}/{sdt}/{edt}.json'
                r = sess.get(url, timeout=req_timeout)
                r.raise_for_status()
                content = r.json().get('content', [])
                if not content:
                    break

                # 시계열 history 구성 (시간 오름차순으로 정렬)
                history = []
                dam_info_latest = None
                for entry in content:
                    v = entry.get(wl_field, '')
                    if v in ('', None) or str(v).strip() == '':
                        continue
                    try:
                        vf = float(v)
                    except ValueError:
                        continue
                    ymdhm = str(entry.get('ymdhm', ''))
                    history.append({'time': ymdhm, 'value': vf})
                    # 댐이면 추가 필드도 같이
                    if api == 'dam':
                        def safe_f(k):
                            x = entry.get(k, '')
                            try: return float(x)
                            except: return None
                        dam_info_latest = {
                            'storage_rate': safe_f('ecpc'),   # 저수율 %
                            'inflow': safe_f('inf'),          # 유입량 m³/s
                            'outflow': safe_f('sfw'),         # 방류량 m³/s
                            'total_outflow': safe_f('tototf'),# 총유출량
                        }

                if not history:
                    break
                history.sort(key=lambda h: h['time'])
                latest = history[-1]['value']
                level = river_level(latest, st.get('warning'), st.get('danger'))

                def delta(hours_ago):
                    if len(history) < hours_ago + 1: return None
                    return round(latest - history[-(hours_ago + 1)]['value'], 2)

                item = {
                    'name': st['name'],
                    'code': st['code'],
                    'sigun': st.get('sigun', ''),   # 관서 매칭용(이름 문자열 매칭의 양주/남양주 충돌 방지)
                    'value': latest,
                    'warning': st['warning'],
                    'danger': st['danger'],
                    'level': level,
                    'history': history[-24:],
                    'delta_1h': delta(1),
                    'delta_3h': delta(3),
                    'has_cctv': st.get('has_cctv', True),
                    'api': api,
                }
                if api == 'dam' and dam_info_latest:
                    item['dam_info'] = dam_info_latest
                fetched[cache_key] = item
                result.append(item)
                break
            except Exception as e:
                last_err = e
                time.sleep(retry_wait)
        else:
            print(f'    하천 {st["name"]}: {max_attempts}회 실패 — {type(last_err).__name__}')
    return result


# ------------------------------------------------------------
# 하천 수위 — 일괄 수신 (2026-09-18 전국 확장 0단계)
#
# 왜 바꿨나: 관측소마다 24시간 이력을 따로 불렀다(경기 58곳 × 0.8초 간격 ≈ 1분,
# 1분 알리미는 매분 58회 = 하루 8만 회). 전국(700곳)은 이 방식으로 5분 안에 못 끝난다.
# 한강홍수통제소는 '전 관측소 최신값'을 한 번에 주는 주소가 있다
# (waterlevel/list/10M.json = 1,203곳 0.8초 · dam/list/10M.json = 댐 50곳).
#   · 최신값(value)  ← 10분 일괄 (예전 1시간 값보다 최대 1시간 신선하다)
#   · 24시간 이력    ← 1시간 일괄(list/1H.json)로 받은 값을 .tmp/river_hist.json 에 쌓는다
#   · 처음 보는 관측소만 예전 방식(관측소별 24시간)으로 한 번 채운다 — 부트스트랩
# 일괄 주소가 통째로 실패하면 fetch_rivers_by_station() 으로 물러난다.
# ------------------------------------------------------------
RIVER_HIST_PATH = TMP / 'river_hist.json'
RIVER_HIST_KEEP = 30           # 관측소당 보관 점 수(24시간 + 여유)
RIVER_BOOT_PER_RUN = 40        # 한 회차에 부트스트랩할 최대 관측소 수(첫 가동 때만 의미)


def _hrfco_session():
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
                      'Accept': 'application/json', 'Connection': 'close'})
    return s


def _fnum(v):
    try:
        if v in ('', None) or str(v).strip() == '':
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def fetch_hrfco_bulk(kind, unit, sess=None):
    """전 관측소 일괄 조회. kind='waterlevel'|'dam', unit='10M'|'1H' → {코드: 행}.
    행: {'time': ymdhm, 'value': 수위(하천 wl / 댐 swl), 'row': 원본}. 실패 시 예외."""
    r = shared_get(f'hrfco_{kind}_{unit}', f'https://api.hrfco.go.kr/{HRFCO_KEY}/{kind}/list/{unit}.json',
                   timeout=20, max_age=240, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    r.raise_for_status()
    content = r.json().get('content', [])
    if not content:
        raise RuntimeError(f'{kind}/{unit} 일괄 응답이 비었다')
    code_f = 'dmobscd' if kind == 'dam' else 'wlobscd'
    val_f = 'swl' if kind == 'dam' else 'wl'
    out = {}
    for row in content:
        code = str(row.get(code_f, '')).strip()
        v = _fnum(row.get(val_f))
        if not code or v is None:
            continue
        out[code] = {'time': str(row.get('ymdhm', '')), 'value': v, 'row': row}
    return out


def _river_hist_load():
    try:
        return json.loads(RIVER_HIST_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _river_hist_save(hist):
    try:
        _atomic_write_text(RIVER_HIST_PATH, json.dumps(hist, ensure_ascii=False))
    except Exception as e:
        print(f'    하천 이력 저장 실패: {type(e).__name__}')


def _hist_add(hist, key, time_s, value):
    """시간(YYYYMMDDHH) 단위 점을 넣는다 — 같은 시각이면 덮어쓰고, 정렬·보관수 유지."""
    pts = {str(p['time']): p['value'] for p in hist.get(key, []) if p.get('time')}
    pts[str(time_s)] = value
    keys = sorted(pts)[-RIVER_HIST_KEEP:]
    hist[key] = [{'time': k, 'value': pts[k]} for k in keys]


def _river_bootstrap(hist, stations, sess):
    """이력이 없는 관측소만 예전 방식(관측소별 24시간)으로 채운다. 첫 가동·캐시 유실 때만 돈다."""
    now = datetime.now()
    sdt = (now - timedelta(hours=24)).strftime('%Y%m%d%H')
    edt = now.strftime('%Y%m%d%H')
    done = 0
    seen = set()
    for st in stations:
        api = st.get('api', 'waterlevel')
        key = f"{st['code']}|{api}"
        if key in seen or len(hist.get(key, [])) >= 2:
            continue
        seen.add(key)
        if done >= RIVER_BOOT_PER_RUN:
            print(f'    부트스트랩 {RIVER_BOOT_PER_RUN}곳 한도 — 나머지는 다음 회차')
            break
        wl_field = 'swl' if api == 'dam' else 'wl'
        try:
            time.sleep(0.3)
            r = sess.get(f'https://api.hrfco.go.kr/{HRFCO_KEY}/{api}/list/1H/{st["code"]}/{sdt}/{edt}.json',
                         timeout=8)
            r.raise_for_status()
            for entry in r.json().get('content', []):
                v = _fnum(entry.get(wl_field))
                if v is not None and entry.get('ymdhm'):
                    _hist_add(hist, key, entry['ymdhm'], v)
            done += 1
        except Exception as e:
            print(f'    부트스트랩 실패 {st["name"]}: {type(e).__name__}')
    if done:
        print(f'    이력 부트스트랩 {done}곳(처음 보는 관측소)')
    return done


def _assemble_river(st, latest, hist):
    """관측소 1건을 화면 형식으로 조립. latest={'time','value','row'}|None, hist=시간 단위 점 목록."""
    api = st.get('api', 'waterlevel')
    series = list(hist)
    if latest and (not series or str(latest['time'])[:10] >= str(series[-1]['time'])[:10]):
        series.append({'time': latest['time'], 'value': latest['value']})
    if not series:
        return None
    value = series[-1]['value']

    def delta(n):
        return round(value - series[-(n + 1)]['value'], 2) if len(series) > n else None

    item = {
        'name': st['name'], 'code': st['code'], 'sigun': st.get('sigun', ''),
        'value': value, 'warning': st.get('warning'), 'danger': st.get('danger'),
        'level': river_level(value, st.get('warning'), st.get('danger')),
        'history': series[-24:], 'delta_1h': delta(1), 'delta_3h': delta(3),
        'has_cctv': st.get('has_cctv', True), 'api': api,
    }
    if api == 'dam' and latest:
        row = latest['row']
        item['dam_info'] = {'storage_rate': _fnum(row.get('ecpc')), 'inflow': _fnum(row.get('inf')),
                            'outflow': _fnum(row.get('sfw')), 'total_outflow': _fnum(row.get('tototf'))}
    return item


def fetch_rivers():
    """하천·댐 수위 — 일괄 수신(최대 4회 호출) + 이력 누적. 일괄이 안 되면 관측소별로 폴백."""
    if not RIVER_STATIONS:
        return []
    sess = _hrfco_session()
    kinds = sorted({st.get('api', 'waterlevel') for st in RIVER_STATIONS})
    latest, hourly = {}, {}
    try:
        for kind in kinds:
            latest[kind] = fetch_hrfco_bulk(kind, '10M', sess)
    except Exception as e:
        print(f'    일괄 최신값 실패({type(e).__name__}) → 관측소별 수집으로 폴백')
        return fetch_rivers_by_station()
    for kind in kinds:
        try:
            hourly[kind] = fetch_hrfco_bulk(kind, '1H', sess)
        except Exception as e:
            hourly[kind] = {}
            print(f'    1시간 일괄 실패({kind}, {type(e).__name__}) — 이력은 이전 것 유지')

    hist = _river_hist_load()
    for st in RIVER_STATIONS:
        api = st.get('api', 'waterlevel')
        row = hourly.get(api, {}).get(st['code'])
        if row and row['time']:
            _hist_add(hist, f"{st['code']}|{api}", row['time'][:10], row['value'])
    _river_bootstrap(hist, RIVER_STATIONS, sess)
    _river_hist_save(hist)

    result, missing = [], []
    for st in RIVER_STATIONS:
        api = st.get('api', 'waterlevel')
        item = _assemble_river(st, latest.get(api, {}).get(st['code']),
                               hist.get(f"{st['code']}|{api}", []))
        if item is None:
            missing.append(st['name'])
            continue
        result.append(item)
    if missing:
        print(f'    자료 없는 관측소 {len(missing)}곳: {", ".join(missing[:5])}{" …" if len(missing) > 5 else ""}')
    print(f'    일괄 수신 {len(result)}/{len(RIVER_STATIONS)}곳 (호출 {len(kinds) * 2}회)')
    return result


# ============================================================
# 7. 재난문자 (행안부 — 키 발급 시 활성화)
# ============================================================

def fetch_flood_forecast():
    """한강홍수통제소 홍수예보 발령 정보.
    endpoint: https://api.hrfco.go.kr/{KEY}/fldfct/list.json
    응답: 최근 24시간 전체 관측소 발령 정보 (관측소 코드 미명시 시 전체).
    평상시는 code=990(자료없음)으로 빈 응답.

    응답 필드: ANCDT(발표일시), ANCNM(발표자), FCTDT(수위도달예상),
              KIND(주의보/경보), NO(번호), OBSNM(지점), RVRNM(강명),
              STTCURDT(현재일시), STTCURHGT(현재수위표수위), STTCURSEALVL(현재해발수위),
              STTNM(관측소코드), WRNARANM(주의지역).
    """
    if not HRFCO_KEY:
        return []
    import os
    # CI 환경에서는 짧은 timeout — 외국 IP는 어차피 막히면 빠르게 포기
    ci_timeout = 5 if os.environ.get('GITHUB_ACTIONS') else 15
    url = f'https://api.hrfco.go.kr/{HRFCO_KEY}/fldfct/list.json'
    try:
        r = shared_get('flood_fcst', url, timeout=ci_timeout, max_age=240, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
        })
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f'    홍수예보: {type(e).__name__}')
        return []

    code = str(data.get('code', ''))
    if code != '200':
        # 990 = 자료 없음 (평상시 정상), 그 외 코드는 오류
        return []
    items = data.get('links', []) or []

    # 경기북부 관련 키워드: 시군명 + 북부 흐르는 주요 강·하천
    north_keywords = P['flood_keywords']   # 관할 시군 + 그 지역 주요 하천명

    result = []
    for it in items:
        wrn_area = str(it.get('WRNARANM', ''))
        rvr = str(it.get('RVRNM', ''))
        obs = str(it.get('OBSNM', ''))
        kind = str(it.get('KIND', ''))

        # 종류 → 단계
        if '경보' in kind:    level = 'severe'
        elif '주의보' in kind: level = 'warning'
        else:                 level = 'info'

        # 경기북부 매칭
        search_text = f'{wrn_area} {rvr} {obs}'
        north_match = any(k in search_text for k in north_keywords)

        # 시간 포맷 (yyyymmddhhmm → mm/dd hh:mm)
        def fmt_dt(s):
            s = str(s or '')
            if len(s) >= 12:
                return f'{s[4:6]}/{s[6:8]} {s[8:10]}:{s[10:12]}'
            return s

        result.append({
            'kind': kind,
            'no': str(it.get('NO', '')),
            'announce_time': fmt_dt(it.get('ANCDT', '')),
            'forecast_time': fmt_dt(it.get('FCTDT', '')),
            'announcer': str(it.get('ANCNM', '')),
            'river': rvr,
            'station': obs,
            'station_code': str(it.get('STTNM', '')),
            'area': wrn_area,
            'current_level': str(it.get('STTCURHGT', '')),
            'sea_level': str(it.get('STTCURSEALVL', '')),
            'level': level,
            'north_match': north_match,
        })
    # 최신순(발표일시 내림차순) — fmt_dt 변환 전 ANCDT 기준 정렬은 어렵지만 API가 일반적으로 최신순 제공
    return result


def fetch_messages():
    """행안부 긴급재난문자 (safetydata.go.kr DSSP-IF-00247).
    경기도 전역 메시지를 받고, region 필드에 정확한 시군명을 부여.
    HTML의 동두천 중점 모드는 region이 '동두천' 또는 '경기도'(전역)만 표시.
    광역 모드는 모든 경기도 메시지 표시."""
    if not SAFETY_KEY:
        print('    재난문자: SAFETY_DATA_KEY 미설정')
        return []

    url = 'https://www.safetydata.go.kr/V2/api/DSSP-IF-00247'
    now = datetime.now()
    today = now.strftime('%Y%m%d')
    # 최근 6시간만 보여 준다(2026-11-09 결정 — '오늘 날짜' 기준이면 아침 문자가 밤까지 남고 23:50 문자는 15분 만에 사라졌다).
    # API 는 날짜(crtDt) 단위라 0~6시에는 어제 날짜도 함께 묻는다.
    MSG_HOURS = 6
    since = (now - timedelta(hours=MSG_HOURS)).strftime('%Y/%m/%d %H:%M:%S')
    days = [today] + ([(now - timedelta(days=1)).strftime('%Y%m%d')] if now.hour < MSG_HOURS else [])

    north_sigun = [r['name'] for r in REGIONS]   # 관할 시군 (프로파일)
    gun_names = GUN_NAMES

    import re as _re

    def is_north_gyeonggi(rcptn):
        """이 상황판 관할 메시지만 통과.
        - 관할 시군이 포함되면 → 포함 (예: 경기도 동두천시)
        - 시군명 없는 '경기도' 전역 → 포함 (관할도 해당)
        - 반대편 광역('경기남부'↔'경기북부') 또는 관할 밖 시군 → 제외
        - 서울·인천 등 비경기 → 제외"""
        s = rcptn.strip()
        if not s.startswith(tuple(SIDO_WORDS)):
            return False
        if P['exclude_prefix'] and s.startswith(P['exclude_prefix']):
            return False
        if any(k in s for k in north_sigun):
            return True
        m = _SIDO_SIGUN_RE.search(s)
        if m:
            return _unit_from_match(m) in north_sigun   # 특정 시군이면 관할만
        return True   # 시군명 없는 경기 전역

    def _page(day, page):
        r = shared_get(f'safety_msgs_{day}_{page}', url, max_age=240, params={
            'serviceKey': SAFETY_KEY, 'pageNo': page, 'numOfRows': 100, 'crtDt': day,
        }, timeout=15)
        r.raise_for_status()
        j = r.json()
        return (j.get('body') or []), int(j.get('totalCount') or 0)

    def _day(day):
        """⚠ 응답은 오래된 순(2026-11-09 실측: 06:54 → 13:46). 하루 전국 문자가 100건을 넘으면 1쪽만 받아선
        최신 문자를 놓친다 → 전체 건수를 보고 마지막 두 쪽(최신 200건)을 받는다."""
        first, total = _page(day, 1)
        pages = max(1, -(-total // 100))
        if pages == 1:
            return first
        out = []
        for pg in sorted({max(1, pages - 1), pages}):
            out += first if pg == 1 else _page(day, pg)[0]
        return out

    items = []
    for i, day in enumerate(days):
        try:
            items += _day(day)
        except Exception as e:
            print(f'    재난문자({day}): {_redact(str(e))[:120]}')
            if i == 0:
                return None   # 오늘 수집 실패 — 정상 0건([])과 구분(main에서 이전 목록 보존)

    result = []
    for it in items:
        rcptn = str(it.get('RCPTN_RGN_NM', ''))
        if not is_north_gyeonggi(rcptn):
            continue
        msg = str(it.get('MSG_CN', '')).strip()
        crt = str(it.get('CRT_DT', ''))
        if crt[:19] < since:          # 'YYYY/MM/DD HH:MM:SS' 끼리 문자열 비교 = 시각 비교
            continue
        time_str = crt[11:16] if len(crt) >= 16 else ''

        # 송출 시군 추출 - 우리 북부 시군 우선
        sender, region = None, None
        for k in north_sigun:
            if k in rcptn:
                sender = k + ('군' if k in gun_names else '시')
                region = k
                break

        # 북부가 아니면: "경기도 광주시" 같은 패턴에서 시군명 추출
        if not region:
            m = _SIDO_SIGUN_RE.search(rcptn)
            if m:
                sender = m.group(1) + m.group(2)
                region = _unit_from_match(m)
            else:
                # "경기도", "경기북부" 등 도 전역
                sender = WIDE_LABEL
                region = WIDE_LABEL

        result.append({
            'sender': sender,
            'time': time_str,
            'date': crt[:10],   # 'YYYY/MM/DD' — 알림 중복판정 키 안정화용(화면 미표시)
            'crt': crt[:19],    # 발송 시각 전체 — 화면이 6시간 지난 문자를 스스로 빼는 데 쓴다
            'text': msg[:300],
            'region': region,
            'sn': int(it.get('SN', 0)),   # 고유번호 — 알림 중복판정 키용(화면 미표시)
        })

    # 최신 발송 우선 — 발송 시각, 같으면 SN(어제·오늘을 합치면 SN 만으로는 순서가 안 맞을 수 있다)
    seen, uniq = set(), []
    for m in sorted(result, key=lambda x: (x['crt'], x['sn']), reverse=True):
        if m['sn'] in seen:
            continue
        seen.add(m['sn'])
        uniq.append(m)
    result = uniq

    return result[:20]


# ============================================================
# 저장
# ============================================================

def save_data(data):
    """data.js 저장 — 공백·들여쓰기 제거하여 약 50% 압축."""
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write('// 자동 생성. ')
        f.write(f'마지막 갱신: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write('window.DASHBOARD_DATA = ')
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')


def git_push_data():
    """수집한 데이터를 GitHub에 자동 푸시.
    .git/config의 PAT가 박힌 remote URL을 사용하므로 인증 자동.

    핵심: 사장님 PC와 GitHub Actions가 둘 다 5분마다 push하면 origin이 앞서있어
    push가 거부(non-fast-forward)됨. 그대로 두면 local에 commit이 수백 개 누적.
    → push 실패 시 'git pull --rebase'로 원격 변경을 가져와 내 commit을 그 위에 얹고,
      데이터 파일 충돌은 내 최신값 우선(--strategy-option=theirs)으로 자동 해결 후 재push.
    이렇게 하면 양쪽이 충돌 없이 공존(누적 0)."""
    try:
        # 1. 모든 변경사항 stage (.gitignore가 .env·.tmp 등 자동 제외)
        subprocess.run(
            ['git', 'add', '-A'],
            cwd=str(ROOT), check=False, capture_output=True
        )
        # 2. 변경사항 있는지 확인
        diff = subprocess.run(
            ['git', 'diff', '--staged', '--quiet'],
            cwd=str(ROOT), capture_output=True
        )
        if diff.returncode == 0:
            print('  · 변경사항 없음 — 푸시 생략')
            return
        # 3. commit
        msg = f'데이터 갱신 {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        subprocess.run(
            ['git', 'commit', '-m', msg],
            cwd=str(ROOT), check=False, capture_output=True
        )
        # 4. push 시도 → 실패하면 원격 동기화(rebase) 후 재시도 (최대 2회)
        for attempt in range(2):
            # 목적지 명시(origin HEAD:main) — .git 재생성 등으로 upstream이 날아가도
            # 'git push'가 "no upstream"으로 실패하지 않도록. (2026-07-12 프리즈 원인 차단)
            push = subprocess.run(
                ['git', 'push', 'origin', 'HEAD:main'],
                cwd=str(ROOT), capture_output=True, text=True, timeout=60
            )
            if push.returncode == 0:
                print('  ✓ GitHub 푸시 완료')
                return
            # push 실패 — origin이 앞서있을 가능성. rebase로 동기화.
            print(f'  · 푸시 거부(시도 {attempt + 1}) — 원격 변경 가져와 재시도')
            pull = subprocess.run(
                ['git', 'pull', '--rebase', '--strategy-option=theirs',
                 'origin', 'main'],
                cwd=str(ROOT), capture_output=True, text=True, timeout=120
            )
            if pull.returncode != 0:
                # rebase 실패(드묾) — 안전하게 중단. 다음 회차에 재시도.
                subprocess.run(['git', 'rebase', '--abort'],
                               cwd=str(ROOT), check=False, capture_output=True)
                err = (pull.stderr or pull.stdout or '').strip()[:150]
                print(f'  ✗ 원격 동기화 실패 — 다음 회차 재시도: {err}')
                return
        print('  ✗ 재시도 후에도 푸시 실패 — 다음 회차 재시도')
    except subprocess.TimeoutExpired:
        print('  ✗ GitHub 푸시 타임아웃 (다음 회차 재시도)')
        subprocess.run(['git', 'rebase', '--abort'],
                       cwd=str(ROOT), check=False, capture_output=True)
    except FileNotFoundError:
        print('  ! git 명령 못 찾음 — Git for Windows 설치 필요')
    except Exception as e:
        print(f'  ✗ GitHub 푸시 오류: {e}')


# ============================================================
# 적응형 배포 — GitHub Actions 무료시간 절약
# ============================================================
DEPLOY_STATE_PATH = TMP / 'last_deploy.json'


def _load_deploy_state():
    try:
        return json.loads(DEPLOY_STATE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_deploy_state(ts, sig):
    try:
        _atomic_write_text(DEPLOY_STATE_PATH, json.dumps({'ts': ts, 'sig': sig}, ensure_ascii=False))
    except Exception:
        pass


def _trigger_deploy():
    """deploy-trigger 브랜치에 현재 HEAD를 push해 Cloudflare 배포를 띄운다.
    기존 git push(원격 URL의 PAT) 재사용 → 새 토큰·도구 불필요. 성공 시 True."""
    try:
        r = subprocess.run(['git', 'push', 'origin', 'HEAD:deploy-trigger', '-f'],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def deploy_decision(data, extra=None):
    """배포가 필요한지 '판단만' 한다(실행 없음). → (사유 or None, 서명, 경과분)
    extra: 함께 볼 다른 지역의 data (한 번의 배포가 두 사이트를 같이 올리므로,
           남부에만 특보가 떠도 즉시 나가야 한다).

    · 이슈(특보/예비특보/하천 주의·위험 목록 '변화') → 즉시 (중복 방지 4분 쿨다운)
    · 특보 발효 중 → 20분마다
    · 평소 → 40분마다

    실행에서 분리한 이유: 커밋도 이 판단을 따르게 하려고. 예전엔 5분마다 무조건
    커밋하고 배포만 걸렀는데, 배포는 평균 40분에 한 번이라 나머지 커밋 7개는
    아무도 보지 않는 데이터였다. 그 커밋들이 저장소를 하루 수십MB씩 불려
    히스토리 압축을 자주 부르고, 압축이 돌 때마다 개발 PC 클론의 공통 조상이
    사라져 작업이 끊겼다."""
    now = datetime.now()
    st = _load_deploy_state()
    last = _safe_dt(st.get('ts', '')) if st.get('ts') else None
    mins = (now - last).total_seconds() / 60 if last else 1e9
    parts = [_deploy_sig(d) for d in ([data] + list(extra or []))]
    sig = '@@'.join(p[0] for p in parts)      # 지역별 서명을 이어붙임
    rapid = any(p[1] for p in parts)
    changed = (sig != st.get('sig', ''))

    if '--deploy-now' in sys.argv:
        reason = '코드반영'   # update.sh 가 원격의 새 코드(PR Merge)를 받은 회차 — 화면도 바로 새 코드로
    elif changed and mins >= 4:
        reason = '이슈변화'
    elif rapid and mins >= 20:
        reason = '급변특보중'
    elif mins >= 40:
        reason = '평소'
    else:
        reason = None   # 배포 안 함 — 상태 미변경(변화 있으면 쿨다운 후 다음 회차에 반영)
    return reason, sig, mins


def _deploy_sig(data):
    """한 지역 데이터의 '상황 서명'과 급변 여부. 서명이 바뀌면 화면을 새로 내보낸다."""
    warns = sorted((str(w.get('type', '')) + '|' + str(w.get('area', ''))) for w in (data.get('warnings') or []))
    prelims = sorted(str(g.get('type', '')) for g in (data.get('prelim_warnings') or []))
    risky = sorted((str(r.get('code', '')) + ':' + str(r.get('level', '')))
                   for r in (data.get('rivers') or []) if r.get('level') in ('warning', 'danger'))
    # ⚠ 홍수예보 발령·태풍·새 재난문자도 화면을 빨리 갱신해야 한다. 예전엔 sig에 없어서,
    #   특보 변화가 없으면 이것들이 새로 떠도 화면이 최대 40분 늦었다.
    flood = sorted(str(f.get('river', '')) + '!' + str(f.get('kind', '')) for f in (data.get('flood_forecast') or []))
    typ = sorted(str(t.get('seq', '')) + '!' + str(t.get('eff', '')) for t in (data.get('typhoon') or []))
    _sns = [str(m.get('sn', '')) for m in (data.get('messages') or []) if m.get('sn')]
    msg_fp = str(len(_sns)) + ':' + (max(_sns) if _sns else '')   # 새 재난문자 오면 fp 변함
    # 물때(조석) — 하루 1회(자정) 날짜가 바뀔 때만 변한다. sig에 없으면 새 날짜 물때가
    #   최대 40분 늦게 뜬다(홍수예보·태풍을 sig에 넣은 것과 같은 이유). 낮 동안은 불변.
    _tide = data.get('tide') or {}
    tide_fp = str(_tide.get('date', '')) + ':' + '/'.join(
        e.get('dupo', '') for e in (_tide.get('events') or []) if e.get('kind') == 'high')
    sig = '#'.join(['/'.join(warns), '/'.join(prelims), '/'.join(risky),
                    '/'.join(flood), '/'.join(typ), msg_fp, tide_fp])   # +물때(날짜변경시)
    # 급변 특보(호우·태풍 등)·하천 위험·홍수예보·태풍은 20분(빠르게), 안정 특보(폭염·한파 등)·평소는 40분.
    # 폭염특보가 며칠 이어져도 화면을 20분마다 새로 그릴 필요는 없어 용량을 아낀다.
    RAPID = ('호우', '태풍', '대설', '강풍', '풍랑', '홍수', '해일')
    rapid = bool(risky) or bool(flood) or bool(typ) \
                        or any(any(k in x for k in RAPID) for x in warns) \
                        or any(any(k in x for k in RAPID) for x in prelims)
    return sig, rapid


def run_deploy(reason, sig, mins):
    """배포 트리거 실행 — deploy-trigger 브랜치 push(cloudflare-deploy.yml)."""
    if _trigger_deploy():
        _save_deploy_state(datetime.now().isoformat(timespec='seconds'), sig)
        print(f'  ✈ Cloudflare 배포 트리거 ({reason}, 이전 배포 {mins:.0f}분 전)')
        return True
    print('  ✗ 배포 트리거 실패(git push deploy-trigger) — 다음 회차/안전스케줄에 재시도')
    return False


def maybe_deploy(data):
    """판단 → 필요하면 배포. 조건 미충족이면 아무것도 안 함(=Actions 무료시간 0)."""
    reason, sig, mins = deploy_decision(data)
    if not reason:
        return False
    return run_deploy(reason, sig, mins)


def save_combined_html(data):
    """index.html에 data를 인라인으로 박은 자급자족 단일 HTML 생성.
    이 파일 하나만 들고 다녀도 모든 데이터+디자인이 들어있다."""
    if not TEMPLATE_PATH.exists():
        print(f'  ✗ 템플릿 없음: {TEMPLATE_PATH}'); return
    with open(TEMPLATE_PATH, encoding='utf-8') as f:
        html = f.read()

    # <script src="data.js" ...> 부분을 인라인 데이터로 치환 (minify)
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    snapshot_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    inline_script = (
        f'<!-- {snapshot_time} 스냅샷. 이 파일 하나로 작동. -->\n'
        f'<script>window.DASHBOARD_DATA = {data_json};</script>'
    )

    import re
    pattern = r'<script src="data\.js"[^>]*></script>'
    if re.search(pattern, html):
        html = re.sub(pattern, inline_script, html)
    else:
        print('  ⚠ index.html 안에서 data.js 참조를 못 찾음 — 단일 HTML 미생성')
        return

    # 단일 HTML에선 5분 자동 새로고침 의미 없음. 제거.
    html = re.sub(
        r"setInterval\(\(\) => \{ location\.reload\(\); \}, 5 \* 60 \* 1000\);",
        f"// 단일 HTML 스냅샷 — 자동 새로고침 비활성 (생성 시각: {snapshot_time})",
        html
    )

    with open(COMBINED_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)


def load_previous_data(path=None):
    """data.js에서 window.DASHBOARD_DATA JSON 부분을 파싱해서 dict로 반환.
    GitHub Actions에서 hrfco(한강홍수통제소)가 외국 IP로 접근 불가일 때
    rivers·flood_forecast 같은 필드를 이전 값으로 보존하기 위한 폴백 소스.
    path를 주면 다른 지역의 data.js도 읽는다(전국 공통 이미지 메타 공유용)."""
    try:
        path = OUTPUT_PATH if path is None else Path(path)
        if not path.exists():
            return {}
        text = path.read_text(encoding='utf-8')
        # 'window.DASHBOARD_DATA = ' 다음의 JSON을 추출
        marker = 'window.DASHBOARD_DATA = '
        idx = text.find(marker)
        if idx < 0:
            return {}
        json_text = text[idx + len(marker):].rstrip().rstrip(';').strip()
        return json.loads(json_text)
    except Exception as e:
        print(f'  · data.js 로드 실패: {type(e).__name__}')
        return {}


# ============================================================
# 허브 특보 병합
# ============================================================


def merge_apihub_warnings(d):
    """index.html normalizeWarningsFromApihub의 서버판 —
    화면과 알림이 같은 특보를 보도록, 허브 특보(apihub_warnings)의 북부 발효특보를
    warnings에 dedup 병합하고 예비특보를 prelim_warnings로 그룹화한다.
    (화면엔 떠도 알림은 안 가던 누락 방지. 클라이언트 병합과 멱등.)"""
    aw = d.get('apihub_warnings') or []
    if not aw:
        return
    # 예비특보 그룹화 (wrn_name 기준)
    prelim_by = {}
    for w in aw:
        if not w.get('is_prelim'):
            continue
        group = (w.get('wrn_name') or '특보') + ' 예비특보'
        g = prelim_by.setdefault(group, {'type': group, 'items': []})
        time_label = f"{w.get('tm_ef_disp')} 발효" if w.get('tm_ef_disp') else (w.get('tm_fc_disp') or '')
        rn, br = w.get('region_name'), w.get('broader_region')
        area_label = f"{rn} ({br})" if rn and rn != br else (rn or br or w.get('reg_id'))
        g['items'].append({'time': time_label, 'area': area_label,
                           'north_match': bool(w.get('is_north_gg'))})
    if prelim_by:
        groups = []
        for g in prelim_by.values():
            g['north_count'] = sum(1 for it in g['items'] if it['north_match'])
            g['total_count'] = len(g['items'])
            groups.append(g)
        d['prelim_warnings'] = groups
    # 발효특보 (북부만) warnings에 dedup 병합
    existing = {f"{w.get('type')}|{w.get('area')}" for w in (d.get('warnings') or [])}
    add = []
    for w in aw:
        if w.get('is_prelim') or not w.get('is_north_gg'):
            continue
        typ = f"{w.get('wrn_name')}{'경보' if w.get('lvl_name') == '경보' else '주의보'}"
        # ⚠ 허브는 특보가 아닌 '현상'도 같이 보낸다(실측: 폭염 91·열대야 63·강풍 19·풍랑 10건).
        #   '열대야'에 주의보를 갖다붙이면 '열대야주의보'라는 없는 특보가 만들어지고,
        #   warnings에 섞여 화면에 뜬다. 정식 특보명만 통과시킨다.
        if typ not in WRN_TYPES:
            continue
        area = _expand_areas(w.get('region_name') or w.get('reg_ko'))
        key = f"{typ}|{area}"
        if key in existing:
            continue
        existing.add(key)
        add.append({'type': typ, 'area': area, 'time': w.get('tm_fc_disp') or '',
                    'level': 'severe' if w.get('lvl_name') == '경보' else 'warning'})
    if add:
        d['warnings'] = (d.get('warnings') or []) + add


def _safe_dt(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


EFF_HUMID_PATH = TMP / 'humid_hourly.json'
EFF_OFFICIAL_PATH = TMP / 'eff_humid_official.json'
EFF_R = 0.7


def fetch_eff_humid_official():
    """기상청 공식 실효습도 — 기상자료개방포털(data.kma.go.kr) '실효습도' 표가 부르는 주소 (2026-10-30).
    ASOS(종관) 관측소만 있고, 시각별로 he(실효습도)와 hm0~hm4(같은 시각 오늘~4일 전 상대습도)를 준다.
    인증키·로그인 없이 POST 한 번. 포털 반영이 몇 시간 늦어 '마지막 시각' 값을 쓴다. 30분 캐시.
    실패하면 직전 캐시(없으면 {}) — 공식값은 참고 표시용이라 없어도 화면은 돈다."""
    stns = sorted({int(v) for v in (P.get('eff_humid_asos') or {}).values()})
    if not stns:
        return {}
    try:
        cache = json.loads(EFF_OFFICIAL_PATH.read_text(encoding='utf-8')) if EFF_OFFICIAL_PATH.exists() else {}
    except Exception:
        cache = {}
    if cache.get('_ts') and _time.time() - cache['_ts'] < 1800:
        return cache.get('data', {})
    out = {}
    # 오늘·어제 둘 다 받는다 — 포털은 몇 시간 늦게 올라와 '지금 시각' 행이 없을 때가 많은데,
    #   어제 같은 시각 행의 hm0~hm3 이 곧 1~4일 전 습도라 그것으로 빈 날을 채울 수 있다.
    for day in (datetime.now(), datetime.now() - timedelta(days=1)):
        try:
            r = requests.post('https://data.kma.go.kr/climate/ehum/selectEhumChartAjax.do', timeout=20,
                              headers={'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'},
                              data={'serviceSe': 'F00101', 'selectType': '2', 'mddlClssCd': 'SFC01',
                                    'schStnId': ','.join(map(str, stns)), 'startDt': day.strftime('%Y%m%d')})
            j = r.json()
        except Exception as e:
            print(f'  · 공식 실효습도 수집 실패: {type(e).__name__}')
            break
        if j.get('code') != '00':
            continue
        for it in j.get('data') or []:
            try:
                sid = str(it['stnId']); he = float(str(it.get('he', '')).strip())
            except (KeyError, ValueError):
                continue
            rec = out.setdefault(sid, {'nm': it.get('stnNm', ''), 'hours': {}})
            rec['hours'][str(it.get('tmHh', ''))] = {'he': round(he, 1), 'hm': [it.get('hm%d' % i) for i in range(5)]}
    if not out:
        return cache.get('data', {})
    for rec in out.values():   # 마지막 시각 값을 따로 꺼내 둔다
        last = max(rec['hours'])
        rec['tm'], rec['he'] = last, rec['hours'][last]['he']
    try:
        _atomic_write_text(EFF_OFFICIAL_PATH, json.dumps({'_ts': _time.time(), 'data': out}, ensure_ascii=False))
    except Exception:
        pass
    return out


def apply_effective_humidity(regions):
    """실효습도(effective humidity) — 건조특보·산불 위험 지표. 기상청과 같은 식으로 계산한다:
        He = (1-r)·(H0 + r·H1 + r²·H2 + r³·H3 + r⁴·H4),  r = 0.7
        H0~H4 = '같은 시각'의 상대습도 — 오늘, 1~4일 전 (기상청 포털의 hm0~hm4)
      ⚠ 2026-10-30 전까지는 '하루 최저습도'로 계산해서 공식값보다 20~30%p 낮게(더 메마르게) 나왔다
        (충주 공식 57.8% ↔ 우리 30%). 그 방식은 버렸다.
    관서별 매 시각 습도(AWS 실측)를 .tmp/humid_hourly.json 에 쌓는다(5일 유지).
    이력이 모자란 날은 같은 시각의 가까운 ASOS 관측소 습도(공식 자료의 hm1~hm4)로 채우고,
    그것도 없으면 있는 날만으로 가중평균한 뒤 5일 가중합 비율(0.832)을 곱한다.
    공식 ASOS 값은 reg['effHumidOfficial'] 로 같이 실어 화면이 나란히 보여준다."""
    now = datetime.now()
    try:
        store = json.loads(EFF_HUMID_PATH.read_text(encoding='utf-8')) if EFF_HUMID_PATH.exists() else {}
    except Exception:
        store = {}
    try:
        official = fetch_eff_humid_official()
    except Exception as e:
        print(f'  · 공식 실효습도 건너뜀: {type(e).__name__}')
        official = {}
    asos = P.get('eff_humid_asos') or {}
    full = sum(EFF_R ** n for n in range(5))
    keep = (now - timedelta(days=5)).strftime('%Y-%m-%d %H')
    for reg in regions or []:
        nm = reg.get('name')
        h = reg.get('humid')
        if not nm or h is None:
            continue
        try:
            h = float(h)
        except (TypeError, ValueError):
            continue
        # 관측 시각(HH:MM)을 가까운 정시로 — 기상청 값은 정시 관측이다
        bt = str(((reg.get('detail') or {}).get('observation') or {}).get('base_time') or '')
        t = now
        try:
            hh, mm = int(bt[:2]), int(bt[3:5])
            t = now.replace(hour=hh, minute=0, second=0, microsecond=0) + timedelta(hours=1 if mm >= 30 else 0)
            if t > now + timedelta(hours=1):
                t -= timedelta(days=1)
        except (ValueError, IndexError):
            pass
        rec = {k: v for k, v in store.get(nm, {}).items() if k >= keep}
        rec[t.strftime('%Y-%m-%d %H')] = h
        store[nm] = rec
        off = official.get(str(asos.get(nm, '')), {})
        oh = off.get('hours') or {}

        def asos_hm(day_t):
            # day_t 시각의 ASOS 습도 — 그날부터 k일 뒤 같은 시각 행의 hm[k] 에 들어 있다
            for k in range(5):
                row = oh.get((day_t + timedelta(days=k)).strftime('%Y-%m-%d %H:00'))
                if row and row['hm'][k] is not None:
                    return float(row['hm'][k])
            return None
        vals, used = [], 0
        for n in range(5):
            v = rec.get((t - timedelta(days=n)).strftime('%Y-%m-%d %H'))
            if v is not None:
                used += 1                            # 우리 관서 실측
            elif n:
                v = asos_hm(t - timedelta(days=n))   # 이력이 없으면 같은 시각 가까운 ASOS 습도로
            if v is not None:
                vals.append((n, v))
        if vals:
            wsum = sum(EFF_R ** n for n, _ in vals)
            he = (1 - EFF_R) * full * sum((EFF_R ** n) * v for n, v in vals) / wsum
            reg['effHumid'] = round(he)
            reg['effHumidDays'] = used
        if off.get('he') is not None:
            reg['effHumidOfficial'] = {'stn': off.get('nm', ''), 'he': off['he'], 'tm': off.get('tm', '')}
    try:
        _atomic_write_text(EFF_HUMID_PATH, json.dumps(store, ensure_ascii=False))
    except Exception:
        pass


KBS_CCTV_PATH = ROOT / 'data-cctv.js'


def build_kbs_cctv():
    """KBS 재난포털 재난감시 CCTV 목록(전국 45대, 하천 15곳) → data-cctv.js (2026-09-21).
    재생 요청 주소(cctvRequest/…/{토큰}!hls → 서명된 m3u8 주소를 돌려줌)와 정지영상 주소에 하루짜리 토큰이 박혀 있고
    목록 API 는 다른 주소에서 못 부르므로(CORS 없음) 서버가 대신 받아 둔다. 화면(cctv-links.js kbsCam)이 id 로 찾는다.
    목록은 6시간 캐시(토큰이 하루 단위) — 배포 회차마다 불러도 하루 28회."""
    cams = []
    bucket = datetime.now().strftime('%Y%m%d') + str(datetime.now().hour // 6)
    for area in range(1, 8):
        try:
            r = shared_get(f'kbs_cctv_{area}_{bucket}', 'https://d.kbs.co.kr/special/cctv/list',
                           params={'area': area, 'disaster': 8}, timeout=15, max_age=6 * 3600,
                           headers={'X-Requested-With': 'XMLHttpRequest', 'User-Agent': 'Mozilla/5.0'})
            if r.status_code != 200:
                continue
            for c in (r.json().get('cctvList') or []):
                if c.get('available') != 'Y' or not c.get('cctvId'):
                    continue
                cams.append({'id': str(c['cctvId']), 'name': c.get('subtitleMainText') or c.get('name') or '',
                             'addr': c.get('adressFull') or '', 'lat': c.get('lat'), 'lng': c.get('lng'),
                             'url': c.get('url') or '', 'img': c.get('imgUrl') or ''})
        except Exception as e:
            print(f'  · KBS CCTV 목록 area={area} 실패({type(e).__name__})')
    return cams


def build_hrfco_cctv_table():
    """홍수통제소 수위관측소 CCTV 장치번호표 (2026-09-22). 화면이 통제소 중계서버(lw.hrfco.go.kr)의 HLS 를 직접 틀 때
    obscd → 장치번호(ldUrl 저해상도·hdUrl 고해상도)가 필요하다. 화면에 박아 둔 표(cctv-hrfco.js, tools/build_hrfco_cctv.py)는
    손으로 다시 만들어야 새 카메라가 붙으므로, 서버가 같은 목록을 6시간마다 받아 data-cctv.js 에 같이 올린다 — 화면은 이쪽을 먼저 본다.
    실패하면 None (화면은 박아 둔 표로 돈다)."""
    now = datetime.now()
    bucket = now.strftime('%Y%m%d') + str(now.hour // 6)
    tm = (now - timedelta(minutes=10)).strftime('%Y%m%d%H%M')
    r = shared_get(f'hrfco_cctv_{bucket}', 'https://n.flood.go.kr/main/getData.do',
                   params={'dataType': 'cctv', 'ymdhm': tm}, timeout=30, max_age=6 * 3600,
                   headers={'User-Agent': 'Mozilla/5.0'})
    if r.status_code != 200:
        return None
    table = {}
    for it in r.json():
        code, ld, hd = str(it.get('obscd') or ''), str(it.get('ldUrl') or ''), str(it.get('hdUrl') or '')
        if not code or not (ld or hd):
            continue
        table[code] = {'n': it.get('obsnm') or it.get('media_nm') or '', 'ld': ld, 'hd': hd, 'fc': it.get('fcodvcd') or '01'}
    return table or None


def build_cctv_files():
    """data-cctv.js = KBS 목록(window.KBS_CCTV) + 통제소 장치번호표(window.HRFCO_CCTV_LIVE). 둘 다 없으면 파일을 건드리지 않는다.
    한쪽만 실패하면 그 줄만 빠진다(화면은 각각 폴백이 있다)."""
    gen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        cams = build_kbs_cctv()
    except Exception as e:
        print(f'  · KBS CCTV 실패({type(e).__name__}) — 건너뜀'); cams = []
    try:
        table = build_hrfco_cctv_table()
    except Exception as e:
        print(f'  · 통제소 CCTV 장치번호표 실패({type(e).__name__}) — 건너뜀'); table = None
    if not cams and not table:
        return 0, 0
    lines = []
    if cams:
        lines.append('window.KBS_CCTV = ' + json.dumps({'generated': gen, 'cams': cams}, ensure_ascii=False) + ';')
    if table:
        lines.append('window.HRFCO_CCTV_LIVE = ' + json.dumps({'generated': gen, 'table': table}, ensure_ascii=False,
                                                            separators=(',', ':')) + ';')
    _atomic_write_text(KBS_CCTV_PATH, '\n'.join(lines) + '\n')
    return len(cams), len(table or {})


def push_only():
    """수집 없이 커밋·푸시·배포만. 지역별 수집을 동시에 돌린 뒤 마지막에 한 번 호출한다.
    (각 수집은 --no-push로 파일만 만들고, 여기서 한꺼번에 올린다 — 푸시 경합 방지)

    ⚠ 배포할 때만 커밋한다. 배포 안 하는 회차의 데이터는 화면에 안 나가므로
      기록할 이유가 없다. 그동안 쌓인 변경은 파일로 남아 있다가(update.sh가
      함부로 되돌리지 않음) 다음 배포 회차에 한 커밋으로 같이 올라간다.
      → 커밋 수·저장소 증가량이 약 1/8로 줄어 히스토리 압축이 드물어진다."""
    print(f'[{now_str()}] 푸시 전용 모드')
    # 배포 한 번이 두 사이트를 같이 올리므로 판단도 두 지역을 같이 본다.
    others = [load_previous_data(ROOT / p['data_file'])
              for k, p in _rp.PROFILES.items() if k != PROFILE_NAME]
    reason, sig, mins = deploy_decision(load_previous_data(), others)
    if not reason:
        print(f'  · 배포 조건 미충족(이전 배포 {mins:.0f}분 전) — 커밋·푸시 생략, '
              f'변경은 다음 배포 때 함께 올림')
        print(f'[{now_str()}] 종료')
        return
    try:
        _nk, _nh = build_cctv_files()
        print(f'  · CCTV 목록: KBS {_nk}대 · 통제소 장치번호 {_nh}곳 → data-cctv.js')
    except Exception as e:
        print(f'  · CCTV 목록 실패({type(e).__name__}) — 건너뜀')
    git_push_data()
    run_deploy(reason, sig, mins)
    print(f'[{now_str()}] 푸시 완료')


def main():
    if '--push-only' in sys.argv:
        push_only()
        return
    if '--radar-only' in sys.argv:
        # 서버가 1분마다 레이더만 따로 받는다 — data.js 는 건드리지 않는다
        r = fetch_radar_frames()
        print(f'[{now_str()}] 레이더 ' + (f"{r['tm'][8:10]}:{r['tm'][10:12]} 관측 · {len(r['frames'])}장" if r.get('ok') else '실패 ' + str(r.get('err'))))
        return
    print(f'[{now_str()}] 데이터 수집 시작 — {P["label"]}')
    # 이전 data.js — hrfco 실패 시 폴백용
    prev = load_previous_data()
    data = {
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'regions': [], 'warnings': [], 'rivers': [],
        'messages': [], 'forecast': [], 'pm': [], 'fire': [],
        'bulletins': {'warnings_full': [], 'info_list': []},
        'fire_stats': {'incidents_year': [], 'summary': None},
    }

    # AWS 실측 강수 (관서별 공식 누적) — 1회 호출로 전 관서 배분.
    # 실패해도 다른 수집은 계속. 이전 값 보존(호우 중 '자료 사라짐' 방지).
    print('[AWS 실측 강수]')
    try:
        data['aws'] = fetch_aws_rain()
        _ok = sum(1 for v in data['aws'].values() if v.get('ok'))
        print(f'  ✓ AWS {_ok}/{len(data["aws"])}개 관서 수신')
    except Exception as e:
        data['aws'] = prev.get('aws') or {}
        print(f'  ✗ AWS 실패: {type(e).__name__} → 이전 값 보존({len(data["aws"])}개)')

    # 초단기예보 — 앞으로 6시간 강수 예측 (1시간에 1회만 실제 호출, 그 외엔 캐시)
    print('[6시간 강수예측]')
    try:
        data['ultra_fcst'] = fetch_ultra_short_fcst_all()
        _ULTRA_CACHE.update(data['ultra_fcst'] or {})
        print(f'  ✓ 6시간 예측 {len(data["ultra_fcst"])}개 관서')
    except Exception as e:
        data['ultra_fcst'] = prev.get('ultra_fcst') or {}
        print(f'  ✗ 6시간 예측 실패: {type(e).__name__} → 이전 값 보존')

    # 태풍 — 진행 중인 것만. 1년의 대부분은 [](정상)이라 실패와 구분해서 다룬다.
    print('[태풍]')
    try:
        data['typhoon'] = fetch_typhoon()
        if data['typhoon']:
            _t = data['typhoon'][0]
            print(f'  ✓ 진행중 {len(data["typhoon"])}개 — {_t["seq"]}호 {_t["name"]} ({_t["eff_txt"]})')
        else:
            print('  · 진행 중인 태풍 없음')
    except Exception as e:
        # 실패 시 이전 값을 쓰면 '끝난 태풍'이 계속 떠 있게 된다 → 빈 값이 안전
        data['typhoon'] = []
        print(f'  ✗ 태풍 수집 실패: {type(e).__name__} → 표시 안 함')

    # 지진 — 최근 통보를 이전 목록과 합쳐 7일치. 실패하면 이전 목록 그대로.
    print('[지진]')
    try:
        _q = fetch_quake()
        data['quake'] = merge_quake(prev.get('quake'), _q)
        _q0 = data['quake'][0] if data['quake'] else None
        print(f'  ✓ 국내 지진 7일 {len(data["quake"])}건'
              + (f' — 최근 {_q0["tm_eqk"][5:16]} {_q0["loc"]} 규모 {_q0["mt"]}' if _q0 else ''))
    except Exception as e:
        data['quake'] = merge_quake(prev.get('quake'), [])
        print(f'  ✗ 지진 실패: {type(e).__name__}: {_redact(str(e))[:80]} → 이전 목록 보존')

    # 낙뢰 — 최근 1시간. 실패 시 이전 값을 쓰면 '지난 낙뢰'가 계속 떠 있게 되므로 비운다.
    print('[낙뢰]')
    try:
        data['lightning'] = fetch_lightning()
        if data['lightning']:
            _lb = data['lightning']['by']
            print(f'  ✓ 충북 관서 반경 20km 안 {data["lightning"]["n"]}회'
                  + (' — ' + ', '.join(f'{k} {v["n"]}' for k, v in _lb.items()) if _lb else ''))
    except Exception as e:
        data['lightning'] = None
        print(f'  ✗ 낙뢰 실패: {type(e).__name__}: {_redact(str(e))[:80]} → 표시 안 함')

    # 영향예보(폭염·한파) — 하루 1~2회 발표라 30분 캐시. 실패하면 이전 값 보존.
    print('[영향예보]')
    try:
        data['impact'] = fetch_impact()
        _ib = data['impact'] or {}
        print(f'  ✓ 폭염 {len(_ib.get("hw") or {})}개 관서 · 한파 {len(_ib.get("cw") or {})}개 관서 해당')
    except Exception as e:
        data['impact'] = prev.get('impact')
        print(f'  ✗ 영향예보 실패: {type(e).__name__}: {_redact(str(e))[:80]} → 이전 값 보존')

    # 일출·일몰 — 한국천문연구원 공식값(하루 1회). 실패하면 화면이 같은 좌표로 계산한다.
    print('[일출·일몰]')
    try:
        data['sun'] = fetch_sun_times()
        if data['sun']:
            _c = next(iter(data['sun']['by'].values()))
            print(f'  ✓ 한국천문연구원 {len(data["sun"]["by"])}개 관서 (예: 일출 {_c["rise"]} · 일몰 {_c["set"]})')
        else:
            print('  · 출몰시각 없음 → 화면 계산값 사용')
    except Exception as e:
        data['sun'] = None
        print(f'  ✗ 출몰시각 실패: {type(e).__name__} → 화면 계산값 사용')

    # 물때(조석) — 파주 임진강 하구. 강화대교 예보 +2h = 두포리. 하루 1회 실호출(날짜캐시).
    print('[물때(조석)]')
    if not P.get('tide'):
        data['tide'] = None
        print('  · 이 지역은 해당 없음 — 건너뜀')
    else:
        try:
            _tide = fetch_tide()
            if _tide and _tide.get('events'):
                data['tide'] = _tide
                _hi = [e['dupo'] for e in _tide['events'] if e['kind'] == 'high']
                print(f'  ✓ 두포리 만조 {", ".join(_hi) or "-"} · 조차 {_tide["amp_cm"]}cm({_tide["spring"]})')
            else:
                data['tide'] = prev.get('tide') or None
                print('  · 조석 데이터 없음 → 이전 값 보존')
        except Exception as e:
            data['tide'] = prev.get('tide') or None
            print(f'  ✗ 물때 실패: {type(e).__name__} → 이전 값 보존')

    print('[시군별 현재 기상]')
    data['regions'] = fetch_all_regions(data.get('aws') or {})
    # 개별 시군이 forecast+실황 모두 실패하면 weather='?'로 남음 → 이전 정상값 보존
    prev_regions = {r.get('name'): r for r in (prev.get('regions') or [])}
    for i, r in enumerate(data['regions']):
        if r.get('weather') in ('?', None, ''):
            pr = prev_regions.get(r.get('name'))
            if pr and pr.get('weather') not in ('?', None, ''):
                data['regions'][i] = pr
                print(f'  · {r.get("name")} 수집 실패 → 이전 값 보존')

    # 실효습도 — 기상청 식(같은 시각 5일 습도 가중합, r=0.7) + 기상청 공식 ASOS 값
    try:
        apply_effective_humidity(data['regions'])
    except Exception as e:
        print(f'  · 실효습도 계산 건너뜀: {type(e).__name__}')

    print('[날씨누리 시간별 예보]')
    try:
        apply_wnuri_local(data)
    except Exception as e:
        data.setdefault('local', {})
        print(f'  ✗ 날씨누리 건너뜀: {type(e).__name__}')

    print(f'[시간대별 예보 - {P["home"]}]')
    try:
        fc = fetch_hourly_forecast()
        # 예보 수집 실패 시 빈 배열로 덮지 않음 — 화면이 가짜 샘플(폭우)로 대체되는 것 방지
        if not fc and prev.get('forecast'):
            data['forecast'] = prev['forecast']
            print(f'  · 예보 수집 실패 — 이전 {len(data["forecast"])}시간치 보존')
        else:
            data['forecast'] = fc
            print(f'  ✓ {len(data["forecast"])}시간치')
    except Exception as e:
        print(f'  ✗ {e}')
        data['forecast'] = prev.get('forecast', [])

    print('[기상특보]')
    try:
        w_result = fetch_warnings()
        # 하위호환을 위해 data['warnings']는 발효 특보 배열(기존 형식) 유지
        data['warnings'] = w_result['active']
        # 예비특보는 별도 키로 저장
        data['prelim_warnings'] = w_result['prelim']
        print(f'  ✓ 발효 {len(data["warnings"])}건 / 예비 {len(data["prelim_warnings"])}그룹')
    except Exception as e:
        print(f'  ✗ {e}'); traceback.print_exc()
        # 수집 실패 — 이전 값 보존 (특보 해제→재발효 깜빡임 방지)
        data['warnings'] = prev.get('warnings', [])
        data['prelim_warnings'] = prev.get('prelim_warnings', [])
        if data['warnings'] or data['prelim_warnings']:
            print(f'  · 이전 특보 {len(data["warnings"])}건/예비 '
                  f'{len(data["prelim_warnings"])}그룹 보존')

    print('[기상청 API허브 특보자료]')
    try:
        aw = fetch_apihub_warnings()   # 실패 시 None, 성공 시 list(정상 0건이면 [])
        # 수집 실패(None)일 때만 이전 값 보존 — 정상 0건([])은 그대로 저장해 특보 해제 반영
        if aw is None and prev.get('apihub_warnings'):
            data['apihub_warnings'] = prev['apihub_warnings']
            print(f'  · 허브 수집 실패 — 이전 {len(data["apihub_warnings"])}건 보존')
        else:
            data['apihub_warnings'] = aw or []
            gg_n = sum(1 for w in data['apihub_warnings'] if w.get('is_gyeonggi'))
            north_n = sum(1 for w in data['apihub_warnings'] if w.get('is_north_gg'))
            prelim_n = sum(1 for w in data['apihub_warnings'] if w.get('is_prelim'))
            print(f'  ✓ 전체 {len(data["apihub_warnings"])}건 (경기 {gg_n}건 · {P["label"]} {north_n}건 · 예비 {prelim_n}건)')
    except Exception as e:
        print(f'  ✗ {e}')
        data['apihub_warnings'] = prev.get('apihub_warnings', [])

    print('[기상청 이미지 (특보 발효도·강수예측·레이더·위성)]')
    _shared = P.get('share_images_from')
    if _shared:
        # 레이더·위성·특보발효도는 전국 공통 이미지다. 다른 지역 회차가 이미 받아
        # images/ 에 저장해 뒀으므로 그 메타데이터만 가져다 쓴다(중복 다운로드 방지).
        data['kma_images'] = (load_previous_data(ROOT / _shared).get('kma_images')
                              or prev.get('kma_images') or {})
        print(f'  · 전국 공통 이미지 — {_shared} 것을 그대로 사용'
              f' ({len(data["kma_images"])}종)')
    else:
        try:
            data['kma_images'] = download_kma_images()
            # 이미지가 ok=False면 이전 정상 메타데이터 보존
            prev_imgs = prev.get('kma_images') or {}
            for key in ('wrn', 'radar', 'satellite'):
                cur = data['kma_images'].get(key, {})
                prev_meta = prev_imgs.get(key, {})
                if not cur.get('ok') and prev_meta.get('ok'):
                    # 키가 아예 없으면 '아직 갱신 주기가 아님'(위성은 30분 주기),
                    # 키는 있는데 ok=False면 진짜 수집 실패. 로그에서 구분해야
                    # 나중에 로그만 보고 장애로 오해하지 않는다.
                    why = '갱신 주기 아님' if not cur else '수집 실패'
                    data['kma_images'][key] = prev_meta
                    print(f'  · {key}: {why} → 이전 이미지·메타 유지')
            wrn_ok = data['kma_images'].get('wrn', {}).get('ok')
            radar_ok = data['kma_images'].get('radar', {}).get('ok')
            sat_ok = data['kma_images'].get('satellite', {}).get('ok')
            print(f'  특보발효도:{"✓" if wrn_ok else "✗"}  레이더:{"✓" if radar_ok else "✗"}  위성:{"✓" if sat_ok else "✗"}')
        except Exception as e:
            print(f'  ✗ {e}')
            data['kma_images'] = prev.get('kma_images') or {}

    print('[기상청 통보문·기상정보]')
    try:
        b = fetch_warning_bulletins()
        # 일시 장애 시 빈 dict 반환(예외 안 남) → 이전 값 보존(통보문/기상정보 깜빡임 방지)
        if not b.get('warnings_full') and not b.get('info_list') and prev.get('bulletins', {}).get('warnings_full'):
            data['bulletins'] = prev['bulletins']
            print('  · 통보문 수집 실패 — 이전 값 보존')
        else:
            data['bulletins'] = b
            print(f'  ✓ 통보문 {len(b["warnings_full"])}건 / 기상정보 {len(b["info_list"])}건')
    except Exception as e:
        print(f'  ✗ {e}')
        data['bulletins'] = prev.get('bulletins', {'warnings_full': [], 'info_list': []})

    print('[중기전망(날씨해설)]')
    try:
        mid = fetch_mid_forecast()
        if mid:
            data['mid_forecast'] = mid
            print(f'  ✓ {len(mid["content"])}자 ({mid["tmFc_display"]} 발표)')
        elif prev.get('mid_forecast'):
            # 권한 미적용·일시 실패 시 이전 값 보존
            data['mid_forecast'] = prev['mid_forecast']
            print('  · 이번 회차 실패 — 이전 날씨해설 보존')
        else:
            print('  · 데이터 없음 (중기예보 권한 적용 대기 중)')
    except Exception as e:
        print(f'  ✗ {e}')
        if prev.get('mid_forecast'):
            data['mid_forecast'] = prev['mid_forecast']

    print('[미세먼지]')
    try:
        pm = fetch_pm()
        if not pm and prev.get('pm'):
            data['pm'] = prev['pm']
            print(f'  · 미세먼지 수집 실패 — 이전 {len(data["pm"])}개 보존')
        else:
            data['pm'] = pm
            print(f'  ✓ {len(data["pm"])}개 측정소')
    except Exception as e:
        print(f'  ✗ {e}')
        data['pm'] = prev.get('pm', [])

    print('[산불 위험도]')
    try:
        fire = fetch_fire()
        if not fire and prev.get('fire'):
            data['fire'] = prev['fire']
            print(f'  · 산불위험 수집 실패 — 이전 {len(data["fire"])}개 시군 보존')
        else:
            data['fire'] = fire
            print(f'  ✓ {len(data["fire"])}개 시군')
    except Exception as e:
        print(f'  ✗ {e}')
        data['fire'] = prev.get('fire', [])

    print('[산불 발생 통계]')
    try:
        fs = fetch_fire_incidents()
        # summary가 None(HTTP 오류 등)이면 이전 값 보존
        if not fs.get('summary') and prev.get('fire_stats', {}).get('summary'):
            data['fire_stats'] = prev['fire_stats']
            print('  · 산불통계 수집 실패 — 이전 값 보존')
        else:
            data['fire_stats'] = fs
            sm = fs.get('summary') or {}
            print(f'  ✓ 올해 전국 {sm.get("this_year_total", 0)}건 / {P["label"]} {sm.get("this_year_north", 0)}건')
    except Exception as e:
        print(f'  ✗ {e}')
        data['fire_stats'] = prev.get('fire_stats', {'incidents_year': [], 'summary': None})

    print('[하천 수위]')
    try:
        rivers = fetch_rivers()
        # GitHub Actions(외국 IP)에서 hrfco 차단 시 — 이전 data.js 값 보존
        if not rivers and prev.get('rivers'):
            data['rivers'] = prev['rivers']
            print(f'  · hrfco 실패 — 이전 {len(data["rivers"])}개 관측소 데이터 보존 (사장님 PC 갱신 시 최신화)')
        else:
            data['rivers'] = rivers
            print(f'  ✓ {len(data["rivers"])}개 관측소')
    except Exception as e:
        print(f'  ✗ {e}')
        # 예외 시에도 이전 데이터 보존
        if prev.get('rivers'):
            data['rivers'] = prev['rivers']

    print('[홍수예보]')
    try:
        flood = fetch_flood_forecast()
        # hrfco 차단 시 빈 리스트 반환 — 평상시는 원래 빈 게 정상이라
        # 이전 값이 비어있지 않을 때만(즉 실제 발령 중일 때만) 보존
        if not flood and prev.get('flood_forecast'):
            data['flood_forecast'] = prev['flood_forecast']
            print(f'  · hrfco 실패 — 이전 홍수예보 {len(data["flood_forecast"])}건 보존')
        else:
            data['flood_forecast'] = flood
            north_n = sum(1 for f in flood if f.get('north_match'))
            print(f'  ✓ 전국 {len(flood)}건 ({P["label"]} 매칭 {north_n}건)')
    except Exception as e:
        print(f'  ✗ {e}')
        data['flood_forecast'] = prev.get('flood_forecast', [])

    print('[재난문자]')
    fetched_msgs = None
    try:
        fetched_msgs = fetch_messages()   # 실패 시 None, 정상 시 list(빈 것 포함)
    except Exception as e:
        print(f'  ✗ {e}')
    if fetched_msgs is None:
        # 수집 실패 — 이전 목록 보존 (재발송·화면 깜빡임 방지)
        data['messages'] = prev.get('messages', [])
        print(f'  · 수집 실패 — 이전 {len(data["messages"])}건 보존')
    else:
        data['messages'] = fetched_msgs
        print(f'  ✓ {len(fetched_msgs)}건')

    # 화면(normalizeWarningsFromApihub)과 동일하게 허브 특보를 warnings/prelim에 병합.
    try:
        merge_apihub_warnings(data)
    except Exception as e:
        print(f'  · 허브 특보 병합 오류: {e}')


    save_data(data)
    save_combined_html(data)
    print(f'[{now_str()}] ✓ {P["data_file"]} + {P["combined_file"]} 저장 완료')

    if NO_PUSH:
        # 여러 지역을 연달아 돌릴 때 앞 회차는 저장만 하고, 마지막 회차가 한꺼번에
        # 커밋·푸시한다(git add -A 라 다른 지역 파일도 같이 올라간다).
        print('[GitHub 푸시] · --no-push — 저장만 하고 건너뜀')
    else:
        print('[GitHub 푸시]')
        git_push_data()
        maybe_deploy(data)   # 적응형 배포(이슈 즉시·특보중 20분·평소 40분) — Actions 무료시간 절약
    print(f'[{now_str()}] 전체 작업 완료 ({P["label"]})')


if __name__ == '__main__':
    main()
