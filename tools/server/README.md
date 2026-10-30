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
