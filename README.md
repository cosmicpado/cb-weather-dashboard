# 충북소방 기상재난 통합플랫폼

충청북도 11개 시군(12개 관서 — 청주는 동부·서부)의 기상·특보·재난문자·하천 수위·산불위험을 한 화면에 모아 보는 상황판.

## 운영 구조

- 네이버클라우드 서버가 5분마다 `tools/update_data.py` 로 수집해 `main` 에 커밋·푸시한다(`update.sh`, 설치는 `tools/server/README.md`).
- 배포가 필요하면 서버가 `deploy-trigger` 브랜치를 밀고, GitHub Actions 가 Cloudflare Workers 로 배포한다.
- PR 을 Merge 하면 서버가 다음 회차에 새 코드를 받아 바로 배포한다.
- 이 PC 에서 상황판을 띄우려면 **`서버.bat` 더블클릭** (= `python tools/live_local.py --port 8000 --lan --collect`)
  → 이 PC 는 `http://localhost:8000/지도.html`, 내부망의 다른 PC 는 `http://<이 PC IP>:8000/지도.html`.
  이 PC 가 5분마다 직접 API 로 수집하고(`.env` 필요, GitHub 에는 올리지 않음) 웹서버도 같이 띄운다.
  `--collect` 를 빼면 API 를 부르지 않고 운영 서버가 올린 데이터를 1분마다 받아 온다.
  이 PC 에서만 볼 때는 `--lan` 을 뺀다(데이터만: `--no-serve`). 수집·수신한 데이터 파일은 커밋하지 말 것.
- API 를 직접 불러 시험하려면 `python tools/update_data.py --no-push` (푸시 모드는 서버 커밋과 엇갈리니 쓰지 말 것).

데이터 수집에는 공공 API 키가 필요하다. 저장소 루트에 `.env` 를 만들고 아래 값을 넣는다(커밋 금지, `.gitignore` 처리됨).

```
DATA_GO_KR_KEY=...      # 공공데이터포털 (기상청 단기예보·에어코리아·재난문자 등)
HRFCO_KEY=...           # 한강홍수통제소 수문 API
SAFETY_DATA_KEY=...     # 행정안전부 재난안전데이터
KMA_APIHUB_KEY=...      # 기상청 API 허브 (AWS·특보)
```

## 사용하는 API

모두 `tools/update_data.py` 가 서버에서 부르고, 결과를 `data.js`·`data-cctv.js`·`images/*.png` 에 담는다(화면은 API 를 직접 부르지 않는다).

### 공공데이터포털 (`DATA_GO_KR_KEY`)

| 기관 | API | 쓰는 곳 |
|---|---|---|
| 기상청 | 단기예보 `VilageFcstInfoService_2.0` — 초단기실황 `getUltraSrtNcst`, 초단기예보 `getUltraSrtFcst`, 단기예보 `getVilageFcst` | 관서별 현재 날씨, 시간대별 예보 |
| 기상청 | 중기예보 `MidFcstInfoService/getMidFcst` | 중기 전망 문구 |
| 기상청 | 기상특보 `WthrWrnInfoService` — `getPwnStatus`, `getWthrWrnList`, `getWthrWrnMsg`, `getWthrInfoList` | 특보 현황, 통보문 전문, 기상정보 |
| 한국천문연구원 | 출몰시각 `RiseSetInfoService/getLCRiseSetInfo` | 관서별 일출·일몰 (하루 1회, 실패하면 화면에서 계산) |
| 한국환경공단 | 에어코리아 `ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty` | 미세먼지 |
| 산림청 | 산불발생통계 `forestStusService/getfirestatsservice` | 최근 1년 산불 발생 |
| 국립산림과학원 | 산불위험예보 `forestPointV2/forestPointListSigunguSearchV2` | 시군별 산불위험도 |

### 기상청 API 허브 (`KMA_APIHUB_KEY`)

| API | 쓰는 곳 |
|---|---|
| `nph-aws2_min` AWS 분자료 | 관측소별 실시간 강수 |
| `wrn_now_data_new.php`, `nph-wrn7` | 현재 특보·예비특보, 특보 구역 그림 |
| `typ_lst.php`, `typ_data.php` | 태풍 목록·경로·예측 |
| `rdr_cmp_file.php` | 레이더 합성 영상 → `images/kma_radar.png` |
| `GK2A/LE1B/IR105` | 천리안 2A 위성 영상 → `images/kma_satellite.png` |

### 그 밖의 기관

| 기관 | API | 인증 | 쓰는 곳 |
|---|---|---|---|
| 한강홍수통제소 | `api.hrfco.go.kr` 수위·우량·댐, 홍수예보 `fldfct` | `HRFCO_KEY` | 하천 수위, 홍수특보 |
| 행정안전부 | 재난안전데이터 `DSSP-IF-00247` 긴급재난문자 | `SAFETY_DATA_KEY` | 재난문자 |
| 기상청 기상자료개방포털 | 실효습도 표 (`data.kma.go.kr/climate/ehum`) | 없음 | 공식 실효습도 (참고 표시) |
| 기상청 날씨누리 | 통보문 화면 (`weather.go.kr/w/special-report`) | 없음 | 지방청 날씨해설 (공개 API 없음) |
| 기상청 날씨누리 | 메인 화면 조각 (`wnuri-fct2021/main/current-weather.do`, `digital-forecast.do`) | 없음 | 관서별 시간별 예보, 오늘 최고·최저 (끊기면 초단기·단기예보로 대체) |
| 홍수통제소 | 홍수정보 CCTV 목록 (`n.flood.go.kr`) | 없음 | 하천 CCTV → `data-cctv.js` (6시간 캐시) |
| KBS | 재난 CCTV 목록 (`d.kbs.co.kr`) | 없음 | 도로·재난 CCTV → `data-cctv.js` (6시간 캐시) |

인증이 없는 곳은 웹 화면이 부르는 주소를 그대로 쓰는 것이라 기관이 화면을 바꾸면 끊길 수 있다. 끊겨도 직전 값이나 빈 값으로 화면은 계속 돈다.

화면에서 직접 쓰는 외부 자원은 브이월드 배경지도(`지도.html` 의 `VWORLD_KEY`)와 CCTV 영상 재생 주소뿐이다.

## 화면

| 파일 | 내용 |
|---|---|
| `지도.html` | 종합 현황(메인) — 관서 지도, 특보·재난문자·하천·시간대별 예보 (`index.html` 이 여기로 보냄) |
| `재해.html` | 재해별 집중 감시 — 🌧 호우 · ❄ 대설·한파 · 🔥 건조·산불 탭 (`호우.html` 은 호우 탭으로 넘기는 옛 주소) |
| `상황실.html` | 119종합상황실 화면(벽면 대형화면) — 관서를 차례로 순환 표출(한 바퀴 약 3분) |
| `쉬운.html` | 큰 글씨 보기 |
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
| `wnuri_dong` | 관서별 날씨누리 동 코드 | `stations_all` 좌표의 동. 청주서부(복대1동)·영동(영동읍)은 직접 지정. 시간별 예보가 이 동의 날씨누리 값과 같다 |
| `aws_rep` | 관서별 대표 관측소 | 현재 기온·습도·바람·강수의 지점(순간풍속만 관할 최대). 2026-11-06 네이버 '지역 날씨'의 온도·습도와 대조해 정했다 (네이버는 약 50분 전 관측값으로 보였다) |
| `aws_meta` | AWS 좌표·주소 | 관서 상세 지도의 ▲ 표시 |
| `river_stations` 의 `name`·`sigun` | 흥덕교(3011645)·환희교(3011660)·미호강교(3011665) = 청주서부, 3011663 이름 = (청주서부) 석남천(`nearby` 삭제) | 흥덕구 소재라 `map_alias` 관할대로 옮겼다. 생성기는 앞 3곳을 청주동부로, 석남천을 '인근'으로 넣는다. 고친 뒤 `build_region_js.py` 로 `riverCodes` 다시 생성 |
| `map_simplify` | `0.0008` | 상세 경계를 지도용으로 단순화하는 허용오차(경위도, 약 0.7px) |

### 지도 경계 원본

`tools/geo/chungbuk.geojson` 은 최신 행정동 경계([vuski/admdongkor](https://github.com/vuski/admdongkor))를
시군구로 합친 것이다(현재 ver20261001). 
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
