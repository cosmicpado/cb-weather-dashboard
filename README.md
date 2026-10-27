# 충청북도 기상·재난 상황판

충청북도 11개 시군(12개 관서 — 청주는 동부·서부)의 기상·특보·재난문자·하천 수위·산불위험을 한 화면에 모아 보는 상황판.

## 바로 쓰기

| 하고 싶은 것 | 방법 |
|---|---|
| 내 PC에서 보기 | `상황판열기.bat` — 데이터 갱신(`--no-push`) 후 브라우저로 열기 |
| 사내망 동료와 같이 보기 | `서버시작.bat` — `http://<내 IP>:8000/` 으로 접속 |
| 데이터만 갱신 | `python tools/update_data.py --no-push` |

데이터 수집에는 공공 API 키가 필요하다. 저장소 루트에 `.env` 를 만들고 아래 값을 넣는다(커밋 금지, `.gitignore` 처리됨).

```
DATA_GO_KR_KEY=...      # 공공데이터포털 (기상청 단기예보·에어코리아·재난문자 등)
HRFCO_KEY=...           # 한강홍수통제소 수문 API
SAFETY_DATA_KEY=...     # 행정안전부 재난안전데이터
KMA_APIHUB_KEY=...      # 기상청 API 허브 (AWS·특보)
```

## 화면

| 파일 | 내용 |
|---|---|
| `지도.html` | 메인 — 관서 지도, 특보·재난문자·하천·시간대별 예보 (`index.html` 이 여기로 보냄) |
| `호우.html` | 호우 집중 — 관서별 누적강수 랭킹, 레이더·예측강수 |
| `상황실.html` | 벽면 대형화면 — 관서를 15초마다 순환 표출 |
| `쉬운.html` | 큰 글씨 간단 화면 |
| `도움말.html` | 사용설명서 |

## 구조 — 화면 코드는 그대로, 지역 값만 3개 파일

| 파일 | 역할 | 만드는 곳 |
|---|---|---|
| `data.js` | 수집 데이터 (`window.DASHBOARD_DATA`) | `tools/update_data.py` |
| `region.js` | 관서 순서·배치·행정명·하천 코드 (`window.REGION_CONF`) | `tools/build_region_js.py` |
| `map-geo.js` | 시군 경계 지도 | `tools/build_map_geo.py` |

세 파일의 원천은 `tools/profiles/chungbuk.json`(시군·격자·관측소·특보구역·하천) 하나다.
프로파일을 다시 뽑거나 지도·화면설정을 다시 만들 때:

```
python tools/build_region_profile.py --sido chungbuk   # 프로파일 (공공 API 원장에서 생성)
python tools/build_all_sido.py                          # map-geo.js + region.js
python tools/check_pages.py                             # 화면이 region.js 를 제대로 무는지 검사
```

## 배포 (선택)

- `wrangler.toml` — Cloudflare Workers 정적 자산(`cb-weather-dashboard`). 제외 목록은 `.assetsignore`.
- `.github/workflows/cloudflare-deploy.yml` — `deploy-trigger` 브랜치 push 시 배포. `update_data.py`(푸시 모드)가 배포 조건이 되면 이 브랜치를 민다.
- `.github/workflows/data-refresh.yml` — 수동 실행: 수집 → 배포.
- `update.sh` — 리눅스 서버 cron(5분)용 수집·커밋·푸시 스크립트.
- 저장소 Secrets 필요: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, 그리고 위 API 키들.

## 출처

경기북부 기상·재난 상황판의 코드를 바탕으로 충청북도용으로 정리했다.

- 원작: [visanu81/gyeonggi-dashboard](https://github.com/visanu81/gyeonggi-dashboard)
- 제작: 소방위 한경승 · 동두천소방서

화면 하단의 제작 크레딧은 원작자 표시이므로 지우지 않는다.
