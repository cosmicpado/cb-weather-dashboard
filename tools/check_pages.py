# -*- coding: utf-8 -*-
"""화면 파일이 지역 설정을 제대로 물고 있는지 검사.

왜 필요한가
  화면 하나가 region.js 를 안 불러오면 data-adapter.js 가 지역 설정을 못 찾아 기본값으로
  떨어진다. 화면은 멀쩡해 보이는데 관서·자료가 엉뚱한 상태라 눈으로는 놓치기 쉽다
  — 그래서 기계가 본다.

검사 항목
  1) 데이터를 쓰는 화면은 region.js 를 부르는가
  2) region.js 가 data-adapter.js 보다 먼저 오는가 (순서가 뒤집히면 무효)
  3) 지역이 갈리는 값(기본 관서 등)이 코드에 박혀 있지 않은가

실행:  python tools/check_pages.py     (문제 있으면 종료코드 1)
"""
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent

# 실시간 데이터를 그리는 화면들. 여기 있는 파일은 반드시 region.js를 물어야 한다.
DATA_PAGES = ['종합.html', '재해.html', '상황실.html']

# 지역마다 달라지는데 코드에 박히기 쉬운 값들 → REGION_CONF 를 거치는지 본다.
# (주석·시연용 더미 데이터에는 있어도 되므로, '기본값으로 쓰는 자리'만 잡는다)
HARDCODED = [
    (r"localStorage\.getItem\('ggMyStation'\)\s*\|\|\s*'[가-힣]+'",
     "기본 관서가 코드에 박힘 — REGION_CONF.home 을 쓸 것"),
]


def main():
    problems = []
    print('=== 화면별 지역 설정 연결 검사 ===')
    for name in DATA_PAGES:
        p = ROOT / name
        if not p.exists():
            problems.append(f'{name}: 파일 없음')
            continue
        t = p.read_text(encoding='utf-8')

        # ⚠ 순서를 볼 땐 반드시 '<script src=...>' 태그 위치로 본다.
        #   그냥 문자열로 찾으면 이 파일을 설명하는 주석("data-adapter.js보다 먼저")까지
        #   걸려서 멀쩡한 파일을 문제로 잡는다 — 실제로 겪음.
        def tag_pos(fname):
            m = re.search(r'<script[^>]+src="[^"]*' + re.escape(fname) + r'"', t)
            return m.start() if m else -1

        has_region = tag_pos('region.js') >= 0
        i_region = tag_pos('region.js')
        i_adapter = tag_pos('data-adapter.js')
        # 상황실은 어댑터를 안 쓰고 자체 변환기를 쓴다 → 순서는 data.js 기준으로 본다
        i_after = i_adapter if i_adapter >= 0 else tag_pos('data.js')

        ok_order = (not has_region) or (i_after < 0) or (i_region < i_after)

        marks = []
        if not has_region:
            marks.append('region.js 안 부름')
        if not ok_order:
            marks.append('region.js 가 데이터보다 늦음')

        for pat, why in HARDCODED:
            for m in re.finditer(pat, t):
                line = t[:m.start()].count('\n') + 1
                marks.append(f'{why} ({name}:{line})')

        print(f'  {"X" if marks else "O"} {name:12s} ' + ('· '.join(marks) if marks else '정상'))
        problems += [f'{name}: {x}' for x in marks]

    print()
    if problems:
        print('==> 문제 있음 — 배포 금지')
        for x in problems:
            print('   ·', x)
        return 1
    print('==> 전부 정상')
    return 0


if __name__ == '__main__':
    sys.exit(main())
