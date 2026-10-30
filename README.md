# 충청북도 기상·재난 상황판

충청북도 11개 시군(12개 관서 — 청주는 동부·서부)의 기상·특보·재난문자·하천 수위·산불위험을 한 화면에 모아 보는 상황판.

## 운영 구조

- 네이버클라우드 서버가 5분마다 `tools/update_data.py` 로 수집해 `main` 에 커밋·푸시한다(`update.sh`, 설치는 `tools/server/README.md`).
- 배포가 필요하면 서버가 `deploy-trigger` 브랜치를 밀고, GitHub Actions 가 Cloudflare Workers 로 배포한다.
- PR 을 Merge 하면 서버가 다음 회차에 새 코드를 받아 바로 배포한다.
- 내 PC에서 운영 데이터로 화면을 보려면 **`로컬서버.bat` 더블클릭** → `http://localhost:8000/지도.html`
  (= `python tools/live_local.py --port 8000`. 8000 을 이미 다른 서버가 쓰면 데이터만 받는다. 데이터만: `--no-serve`).
- 내부망에서 다른 PC 도 보게 하려면 **`내부망서버.bat`** (= `--port 8000 --lan`) → 다른 PC 는 `http://<이 PC IP>:8000/지도.html`.
- 직원 의견(💬 버튼)은 이 서버 PC 의 `feedback/feedback.jsonl` 에 쌓이고, 이 PC 에서 `http://localhost:8000/의견함.html` 로 본다(커밋하지 않음).
  서버가 올린 최신 데이터를 1분마다 받아 오고 웹서버도 같이 띄운다(API 호출 없음, 받아 온 데이터 파일은 커밋하지 말 것).
- API 를 직접 불러 시험하려면 `python tools/update_data.py --no-push` (푸시 모드는 서버 커밋과 엇갈리니 쓰지 말 것).

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
| `재해.html` | 재해 상황판 — 🌧 호우 · ❄ 대설·한파 · 🔥 건조·산불 탭 (`호우.html` 은 호우 탭으로 넘기는 옛 주소) |
| `상황실.html` | 벽면 대형화면 — 관서를 차례로 순환 표출(한 바퀴 약 3분) |
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

### 손으로 정한 값 (프로파일을 다시 뽑으면 되돌아가니 다시 넣을 것)

`tools/profiles/chungbuk.json` 에서 아래 값은 생성기 결과가 아니라 직접 정한 것이다.

| 키 | 값 | 이유 |
|---|---|---|
| `region_order` | 충청북도, 청주동부, 청주서부, 충주, 제천, 보은, 옥천, 영동, 증평, 진천, 괴산, 음성, 단양 | 관서 표시 순서(화면·특보 목록 공통) |
| `map_alias` | 청주동부 = 상당구·청원구, 청주서부 = 흥덕구·서원구 | 청주 두 소방서 관할 |
| `map_source` | `tools/geo/chungbuk.geojson` | 2014 청주·청원 통합 이후 경계 (아래) |
| `map_simplify` | `0.0008` | 상세 경계를 지도용으로 단순화하는 허용오차(경위도, 약 0.7px) |

### 지도 경계 원본

`tools/geo/chungbuk.geojson` 은 최신 행정동 경계([vuski/admdongkor](https://github.com/vuski/admdongkor))를
시군구로 합친 것이다(현재 ver20261001). 기본 원본(통계청 2013)에는 서원구·청원구가 없어 청주 관할을 그릴 수 없다.
행정구역이 바뀌어 다시 만들 때 (사내망은 raw.githubusercontent.com 이 막혀 git 으로 한 파일만 받는다):

```
git clone --depth 1 --filter=blob:none --no-checkout https://github.com/vuski/admdongkor <폴더>
git -C <폴더> checkout HEAD -- verYYYYMMDD/HangJeongDong_verYYYYMMDD.geojson
python tools/build_admdong_geo.py <폴더>/verYYYYMMDD/HangJeongDong_verYYYYMMDD.geojson
python tools/build_all_sido.py
```

## 배포

- `wrangler.toml` — Cloudflare Workers 정적 자산(`cb-weather-dashboard`). 제외 목록은 `.assetsignore`.
- `.github/workflows/cloudflare-deploy.yml` — `deploy-trigger` 브랜치 push 시 배포. `update_data.py`(푸시 모드)가 배포 조건이 되면 이 브랜치를 민다.
- `.github/workflows/data-refresh.yml` — 수동 실행: 수집 → 배포.
- `update.sh` — 리눅스 서버 cron(5분)용 수집·커밋·푸시 스크립트.
- 저장소 Secrets 필요: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, 그리고 위 API 키들.

## 출처

경기북부 기상·재난 상황판의 코드를 바탕으로 충청북도용으로 정리했다.

- 원작: [visanu81/gyeonggi-dashboard](https://github.com/visanu81/gyeonggi-dashboard)
- 제작: 소방위 한경승 · 동두천소방서
