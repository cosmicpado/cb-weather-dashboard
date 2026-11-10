# 운영 수집 서버 (네이버클라우드 Ubuntu)

5분마다 데이터를 모아 이 저장소 `main` 에 커밋하고, 필요할 때 Cloudflare 배포를 띄우는 서버.
한강홍수통제소 API 가 외국 IP 를 막으므로 **한국 IP** 서버여야 한다(GitHub Actions 는 하천 수위 불가).

| 항목 | 값 |
|---|---|
| 서버 | 네이버클라우드 VPC · Micro `mi1-g3` (vCPU 1, 메모리 1GB) · Ubuntu 24.04 · 디스크 10GB |
| 네트워크 | VPC `cb-weather-vpc` · Public 서브넷 `cb-weather-public` · 공인 IP |
| 접속 | `ssh root@<공인IP>` — 비밀번호는 콘솔 › 서버 › 관리자 비밀번호 확인(인증키 `.pem` 필요) |
| 저장소 위치 | `/root/cb-weather-dashboard` (항상 `main`) |
| 실행 | cron `*/5 * * * * /bin/bash /root/cb-weather-dashboard/update.sh` |

## 처음 설치

```bash
ssh root@<공인IP>
git clone https://github.com/cosmicpado/cb-weather-dashboard.git /root/cb-weather-dashboard
bash /root/cb-weather-dashboard/tools/server/setup-ubuntu.sh
```

스크립트가 멈추는 곳 두 군데:
1. **API 키** — `nano /root/cb-weather-dashboard/.env` 로 키를 넣고 스크립트를 다시 실행
2. **GitHub 토큰** — Username `cosmicpado`, Password 에 토큰(`ghp_…`, repo 권한) 붙여넣기. 한 번 넣으면 저장된다

## 평소 확인

```bash
tail -50 /root/cb-weather-dashboard/cron.log    # 최근 회차 기록
crontab -l                                      # 등록 확인
df -h /                                         # 디스크(10GB)
```

## 알아둘 것

- **코드 반영**: PR 을 `main` 에 Merge 하면 다음 회차(5분 안)에 서버가 받고, 그 회차에 바로 Cloudflare 배포까지 띄운다
  (`update.sh` 가 원격이 앞서면 맞추고 `--deploy-now` 로 수집기를 돌린다). `cron.log` 에 `⬇ 새 코드 받음` 이 찍힌다.
- **히스토리 압축**: `.git` 이 600MB 를 넘으면 `update.sh` 가 기록을 1커밋으로 눌러 강제 푸시한다(약 2~3주마다).
  그 뒤 개발 PC 의 작업 브랜치는 공통 조상이 없어져 PR 이 꼬일 수 있다 — 압축 전에 PR 을 Merge 해 두는 게 좋다.
- **개발 PC 에서는 푸시 모드로 돌리지 않는다**: `update_data.py` 는 현재 브랜치를 `main` 으로 밀어 올린다.
  개발 PC에서는 `python tools/update_data.py --no-push` 만 쓴다.
- **Cloudflare**: 저장소 Secrets `CLOUDFLARE_API_TOKEN` · `CLOUDFLARE_ACCOUNT_ID` 가 있어야 배포가 성공한다.

---

# 행정망 운영 서버 (Rocky Linux)

행정망 안에서 데이터를 모으고 화면도 직접 띄우는 서버. GitHub 에 올리지 않고(`--no-push`) Cloudflare 도 쓰지 않는다.
행정망 PC 는 `http://<서버IP>/지도.html` 로 본다.

| 항목 | 값 |
|---|---|
| OS | Rocky Linux 9 또는 10 (10 은 2013년 이후 CPU(x86-64-v3) 필요 — 오래된 가상서버면 9) |
| 저장소 위치 | `/opt/cbweather` (계정 `cbweather` 소유, 항상 `main`) |
| 수집 | systemd 타이머 `cbweather-collect.timer` — 5분마다 `update_data.py --no-push` |
| 레이더 | systemd 타이머 `cbweather-radar.timer` — 1분마다 `update_data.py --radar-only` (이미 받은 5분 칸이면 기상청을 부르지 않는다) |
| 화면 | nginx 80 포트, 화면 파일(html·js·png 등)만 연다 — `.env`·`.git`·`tools/`·`.data/` 는 404 |
| 의견 받기 | `cbweather-feedback.service`(127.0.0.1:8081, `tools/server/feedback_server.py`) ← nginx 가 `/api/feedback` 만 넘긴다. 저장 `/opt/cbweather/.data/feedback.csv`(엑셀용 원본) · `feedback.jsonl`, 보기는 비밀 주소 `http://<서버>/의견.html#k=<.env 의 FEEDBACK_ADMIN_KEY>`(설치 때 키 자동 생성, '완료'에 주소 출력 · 서버 자신은 키 없이). SELinux `httpd_can_network_connect` 를 켠다 |
| 나가는 주소 | `github.com`(소스 받을 때만) · `apis.data.go.kr` · `apihub.kma.go.kr` · `data.kma.go.kr` · `www.weather.go.kr` · `api.hrfco.go.kr` · `n.flood.go.kr` · `www.safetydata.go.kr` · `d.kbs.co.kr` (모두 443) |

## 처음 설치

```bash
dnf install -y git
git clone https://github.com/cosmicpado/cb-weather-dashboard.git /opt/cbweather
bash /opt/cbweather/tools/server/setup-rocky.sh
```

첫 단계에서 나가는 주소를 확인하고, `.env` 에 키가 없으면 멈춘다 — `vi /opt/cbweather/.env` 로 키를 넣고 다시 실행.

## 소스 반영 (직접 실행할 때만)

개발 PC 에서 고친 것을 GitHub `main` 에 올린 뒤 서버에서:

```bash
bash /opt/cbweather/tools/server/update-code.sh            # 최신 main 반영
bash /opt/cbweather/tools/server/update-code.sh <커밋>     # 문제가 생기면 이전 커밋으로 되돌리기
```

수집기가 만든 데이터(`data.js`·기상영상·강수 누적)는 그대로 두고 코드만 바꾼다. 화면은 F5 로 바로 반영.

## 평소 확인

```bash
journalctl -u cbweather-collect -n 50     # 최근 수집 기록
systemctl list-timers cbweather-collect   # 다음 실행 시각
df -h /
```
