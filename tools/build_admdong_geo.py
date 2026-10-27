# -*- coding: utf-8 -*-
"""최신 행정동 경계 → 시군구 경계(tools/geo/<key>.geojson) 생성.

왜 필요한가
  build_map_geo.py 의 기본 원본(통계청 2013 시군구)은 2014년 청주·청원 통합 이전 자료라
  청주시가 '청원군 + 옛 상당구 + 옛 흥덕구'로만 나뉘어 있다(서원구·청원구가 없다).
  그래서 청주동부(상당·청원)·청주서부(흥덕·서원) 관할을 바르게 그릴 수 없었다.
  최신 행정동 경계(vuski/admdongkor)를 시군구 단위로 합쳐 새 원본을 만든다.

원본 받기 (사내망에서는 raw.githubusercontent.com 이 막혀 있어 git 으로 한 파일만 받는다)
  git clone --depth 1 --filter=blob:none --no-checkout https://github.com/vuski/admdongkor <폴더>
  git -C <폴더> checkout HEAD -- ver20261001/HangJeongDong_ver20261001.geojson

실행
  python tools/build_admdong_geo.py <HangJeongDong_verYYYYMMDD.geojson> [시도명=충청북도] [출력=tools/geo/chungbuk.geojson]

출력 형식은 통계청 원본과 같다(properties: code=통계청 시군구 코드 5자리, name='청주시상당구' 식).
행정동끼리는 경계 꼭짓점을 정확히 공유하므로, 같은 시군구의 동을 merge_rings 로 합치면 외곽선만 남는다.
좌표는 소수 4자리(약 10m)로 반올림한다 — 1000px 지도에서 0.1px 미만이라 보이는 차이는 없다.
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_map_geo import merge_rings  # noqa: E402

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
NDIGITS = 4


def rings_of(feature):
    g = feature['geometry']
    polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
    out = []
    for poly in polys:
        ring = []
        for x, y in poly[0]:
            p = [round(x, NDIGITS), round(y, NDIGITS)]
            if not ring or ring[-1] != p:
                ring.append(p)
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        if len(ring) >= 4:
            out.append(ring)
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = Path(sys.argv[1])
    sido = sys.argv[2] if len(sys.argv) > 2 else '충청북도'
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / 'tools' / 'geo' / 'chungbuk.geojson'

    geo = json.loads(src.read_text(encoding='utf-8'))
    rings, codes = collections.defaultdict(list), {}
    for f in geo['features']:
        p = f['properties']
        if p['sidonm'] != sido:
            continue
        rings[p['sggnm']].extend(rings_of(f))
        codes[p['sggnm']] = str(p['adm_cd'])[:5]      # 통계청 행정동 코드 앞 5자리 = 시군구
    if not rings:
        raise SystemExit(f'{sido} 행정동을 찾지 못했습니다')

    features = []
    for name in sorted(rings, key=lambda n: codes[n]):
        merged = merge_rings(rings[name])
        geom = ({'type': 'Polygon', 'coordinates': [merged[0]]} if len(merged) == 1 else
                {'type': 'MultiPolygon', 'coordinates': [[r] for r in merged]})
        features.append({'type': 'Feature', 'properties': {'code': codes[name], 'name': name},
                         'geometry': geom})
        print(f'  {codes[name]} {name:10s} 조각 {len(merged)}  꼭짓점 {sum(len(r) for r in merged):,}')

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'type': 'FeatureCollection', 'source': src.name, 'features': features},
                              ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'생성 → {out} ({out.stat().st_size:,} bytes, 시군구 {len(features)}개)')


if __name__ == '__main__':
    main()
