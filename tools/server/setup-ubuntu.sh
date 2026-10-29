#!/usr/bin/env bash
# 운영 수집 서버(Ubuntu 24.04, 네이버클라우드 Micro) 설치 스크립트.
#
# 하는 일: 시간대(KST) · 스왑 1GB · git/python 설치 · 저장소 받기 · .env 견본 · 시험 수집 · 5분 cron 등록
# 여러 번 실행해도 안전하다(이미 된 단계는 건너뛴다). 중간에 멈추면 안내대로 한 뒤 다시 실행하면 된다.
#
# 실행 (root 로 접속한 뒤):
#   git clone https://github.com/cosmicpado/cb-weather-dashboard.git /root/cb-weather-dashboard
#   bash /root/cb-weather-dashboard/tools/server/setup-ubuntu.sh
set -euo pipefail

REPO_URL="https://github.com/cosmicpado/cb-weather-dashboard.git"
DIR="/root/cb-weather-dashboard"
say()  { printf '\n\033[1;34m▶ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
stop() { printf '\n\033[1;33m■ %s\033[0m\n' "$*"; exit 0; }

[ "$(id -u)" = 0 ] || { echo "root 로 실행하세요"; exit 1; }

say "1. 시간대 → 한국 표준시"
timedatectl set-timezone Asia/Seoul && ok "$(date '+%F %T %Z')"

say "2. 스왑 1GB (메모리 1GB 서버가 git·python 동시 실행 중 멈추지 않게)"
if swapon --show | grep -q /swapfile; then ok "이미 있음"; else
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap -q /swapfile && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ok "생성"
fi

say "3. 패키지 (git · python3 · requests · cron)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3 python3-requests cron >/dev/null
systemctl enable --now cron >/dev/null 2>&1 || true
ok "$(git --version) / $(python3 --version)"

say "4. 저장소"
if [ -d "$DIR/.git" ]; then ok "이미 있음 — $DIR"; else git clone -q "$REPO_URL" "$DIR" && ok "받음 — $DIR"; fi
cd "$DIR"
git checkout -q main
git config user.name  "cb-weather-server"
git config user.email "cosmicpado@gmail.com"
git config credential.helper store          # GitHub 토큰을 /root/.git-credentials 에 저장(root 만 읽기)
ok "main @ $(git log --oneline -1)"

say "5. API 키 (.env)"
if [ ! -f .env ]; then
  cat > .env <<'EOF'
# 충청북도 기상·재난 상황판 — 운영 서버 API 키 (깃에 올라가지 않는다)
DATA_GO_KR_KEY=
KMA_APIHUB_KEY=
HRFCO_KEY=
SAFETY_DATA_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
EOF
  chmod 600 .env
fi
if ! grep -qE '^DATA_GO_KR_KEY=.+' .env || ! grep -qE '^KMA_APIHUB_KEY=.+' .env; then
  stop ".env 에 키를 넣은 뒤 이 스크립트를 다시 실행하세요:
     nano $DIR/.env      (붙여넣기: 마우스 오른쪽 클릭 / 저장: Ctrl+O, Enter / 종료: Ctrl+X)"
fi
ok "키 확인 (DATA_GO_KR_KEY · KMA_APIHUB_KEY 있음)"

say "6. 시험 수집 (푸시 없이)"
if python3 tools/update_data.py --no-push > /tmp/cb-first-run.log 2>&1; then
  grep -E '✓' /tmp/cb-first-run.log | head -12 | sed 's/^/  /'
  ok "수집 성공 — 전체 기록: /tmp/cb-first-run.log"
else
  tail -20 /tmp/cb-first-run.log; stop "수집 실패 — 위 기록을 확인하세요"
fi
git checkout -q -- . 2>/dev/null || true      # 시험 수집 결과는 버린다(첫 cron 회차가 다시 만든다)

say "7. GitHub 올리기 권한"
if [ -s /root/.git-credentials ] && GIT_TERMINAL_PROMPT=0 git push --dry-run -q origin HEAD:main 2>/dev/null; then
  ok "저장된 토큰으로 올리기 가능"
else
  echo "  아래에서 Username 은 cosmicpado, Password 에는 GitHub 토큰(ghp_...)을 붙여넣으세요."
  echo "  (입력해도 화면에 안 보이는 게 정상입니다)"
  git push --dry-run origin HEAD:main && ok "토큰 저장됨 — 다음부터 묻지 않음" \
    || stop "올리기 권한 확인 실패 — 토큰(repo 권한)을 확인하고 다시 실행하세요"
fi

say "8. 5분마다 자동 실행 (cron)"
LINE="*/5 * * * * /bin/bash $DIR/update.sh"
if crontab -l 2>/dev/null | grep -qF "$DIR/update.sh"; then ok "이미 등록됨"; else
  ( crontab -l 2>/dev/null; echo "$LINE" ) | crontab - && ok "등록: $LINE"
fi

say "완료"
echo "  · 5분 안에 첫 회차가 돈다. 기록 보기:  tail -f $DIR/cron.log"
echo "  · GitHub 저장소 main 에 '데이터 갱신' 커밋이 쌓이면 정상"
echo "  · 코드 수정은 PR 을 Merge 하면 서버가 다음 회차에 알아서 받는다(update.sh)"
