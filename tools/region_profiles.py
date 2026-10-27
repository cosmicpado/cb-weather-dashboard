# -*- coding: utf-8 -*-
"""지역 프로파일 — 충청북도 상황판의 지역별 상수(시군·격자·관측소·특보구역·하천·산불권역).

값은 tools/profiles/chungbuk.json 에 있다. build_region_profile.py --sido chungbuk 가
공공 API 원장에서 기계로 만든 것이므로 손으로 고치지 말고 다시 생성할 것.
수집기(update_data.py)와 화면 설정 생성기(build_region_js.py)가 이 값을 함께 쓴다.
"""
DEFAULT = 'chungbuk'
PROFILES = {}


def get(name=DEFAULT):
    if name not in PROFILES:
        raise SystemExit(f'알 수 없는 지역 프로파일: {name} (가능: {", ".join(PROFILES)})')
    return PROFILES[name]


import json as _json
import pathlib as _pl

_PROFILE_DIR = _pl.Path(__file__).resolve().parent / 'profiles'


def _from_generated(j):
    prof = dict(j)
    prof['aws_stations'] = {a: [tuple(x) for x in lst] for a, lst in j['aws_stations'].items()}
    prof['flood_keywords'] = set(j['flood_keywords'])
    prof['regions'] = [{'name': r['name'], 'nx': r['nx'], 'ny': r['ny'], 'sgg': r['sgg']}
                       for r in j['regions']]
    return prof


if _PROFILE_DIR.is_dir():
    for _f in sorted(_PROFILE_DIR.glob('*.json')):
        _j = _json.loads(_f.read_text(encoding='utf-8'))
        PROFILES[_j['key']] = _from_generated(_j)
