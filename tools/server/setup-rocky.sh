#!/usr/bin/env bash
# 행정망 운영 서버(Rocky Linux 9·10) 설치 스크립트.
#
# 하는 일: 접속 확인 · 시간대(KST) · 패키지 · 전용 계정 · 저장소 받기 · .env 견본 · 시험 수집
#          · 5분 수집 타이머 · 1분 레이더 타이머 · 의견 받기 서비스(systemd) · nginx 웹서버(80) · SELinux · 방화벽
# GitHub 에 올리지 않는다(--no-push). 이 서버가 데이터를 모으고 화면도 직접 띄운다 — Cloudflare 불필요.
# 여러 번 실행해도 안전하다(이미 된 단계는 건너뛴다). 중간에 멈추면 안내대로 한 뒤 다시 실행하면 된다.
#
# 실행 (root 로 접속한 뒤):
#   dnf install -y git
#   git clone https://github.com/cosmicpado/cb-weather-dashboard.git /opt/cbweather
#   bash /opt/cbweather/tools/server/setup-rocky.sh
set -euo pipefail

REPO_URL="https://github.com/cosmicpado/cb-weather-dashboard.git"
DIR="/opt/cbweather"
SVC_USER="cbweather"
UNIT="cbweather-collect"
say()  { printf '\n\033[1;34m▶ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
stop() { printf '\n\033[1;33m■ %s\033[0m\n' "$*"; exit 0; }

[ "$(id -u)" = 0 ] || { echo "root 로 실행하세요"; exit 1; }
. /etc/os-release
case "${ID:-} ${ID_LIKE:-}" in *rhel*|*rocky*|*almalinux*) ;; *) echo "Rocky Linux(RHEL 계열) 전용입니다 — 지금: ${PRETTY_NAME:-?}"; exit 1;; esac

say "1. 외부 접속 확인 (행정망 방화벽)"
# 수집기가 부르는 곳 + 소스를 받는 GitHub. 000 이면 방화벽에서 막힌 것.
BLOCKED=""
for h in github.com apis.data.go.kr apihub.kma.go.kr data.kma.go.kr www.weather.go.kr \
         api.hrfco.go.kr n.flood.go.kr www.safetydata.go.kr d.kbs.co.kr; do
  code=$(curl -s -o /dev/null -m 8 -w '%{http_code}' "https://$h" || true)
  if [ "${code:-000}" = 000 ]; then warn "막힘  $h"; BLOCKED="$BLOCKED $h"; else ok "$code  $h"; fi
done
if [ -n "$BLOCKED" ]; then
  case "$BLOCKED" in *github.com*) [ -d "$DIR/.git" ] || stop "github.com 이 막혀 소스를 받을 수 없습니다 — 방화벽 예외를 신청한 뒤 다시 실행하세요";; esac
  warn "막힌 주소의 자료는 화면에 빠집니다 — 방화벽 예외 신청 대상:$BLOCKED"
fi

say "2. 시간대 → 한국 표준시"
timedatectl set-timezone Asia/Seoul && ok "$(date '+%F %T %Z')"

say "3. 패키지 (git · python3 · requests · nginx · SELinux 도구)"
dnf install -y -q git python3 python3-requests nginx policycoreutils-python-utils >/dev/null
ok "$(git --version) / $(python3 --version) / $(nginx -v 2>&1)"

say "4. 전용 계정 ($SVC_USER — 수집기는 root 가 아니라 이 계정으로 돈다)"
if id "$SVC_USER" >/dev/null 2>&1; then ok "이미 있음"; else
  useradd -r -M -d "$DIR" -s /sbin/nologin "$SVC_USER" && ok "생성"
fi

say "5. 저장소"
if [ -d "$DIR/.git" ]; then ok "이미 있음 — $DIR"; else git clone -q "$REPO_URL" "$DIR" && ok "받음 — $DIR"; fi
chown -R "$SVC_USER:$SVC_USER" "$DIR"
chmod 755 "$DIR"                              # nginx 가 들어가 읽을 수 있게
G() { runuser -u "$SVC_USER" -- git -C "$DIR" "$@"; }
G checkout -q main
ok "main @ $(G log --oneline -1)"

say "6. API 키 (.env)"
if [ ! -f "$DIR/.env" ]; then
  cat > "$DIR/.env" <<'EOF'
# 충북소방 기상종합상황판 — 행정망 서버 API 키 (깃에 올라가지 않는다)
DATA_GO_KR_KEY=
KMA_APIHUB_KEY=
HRFCO_KEY=
SAFETY_DATA_KEY=
EOF
fi
chown "$SVC_USER:$SVC_USER" "$DIR/.env"; chmod 600 "$DIR/.env"
if ! grep -qE '^DATA_GO_KR_KEY=.+' "$DIR/.env" || ! grep -qE '^KMA_APIHUB_KEY=.+' "$DIR/.env"; then
  stop ".env 에 키를 넣은 뒤 이 스크립트를 다시 실행하세요:
     vi $DIR/.env      (i 로 입력 시작 / 붙여넣기: 마우스 오른쪽 클릭 / 저장·종료: Esc 누르고 :wq Enter)"
fi
ok "키 확인 (DATA_GO_KR_KEY · KMA_APIHUB_KEY 있음)"
# 받은 의견을 다른 PC 에서 보는 비밀 주소(의견.html#k=<키>)용 키 — 없으면 하나 만든다(서버 자신에서는 키 없이 보인다)
if ! grep -qE '^FEEDBACK_ADMIN_KEY=.+' "$DIR/.env"; then
  K=$(python3 -c 'import secrets; print(secrets.token_hex(12))')
  sed -i '/^FEEDBACK_ADMIN_KEY=/d' "$DIR/.env"
  printf '\n# 의견.html 관리자 키 — 다른 PC 에서 받은 의견을 볼 때 넣는다\nFEEDBACK_ADMIN_KEY=%s\n' "$K" >> "$DIR/.env"
  ok "의견 비밀 주소용 키 만듦 (맨 끝 '완료'에 주소가 나온다)"
fi

say "7. 시험 수집 (1~2분 걸린다)"
if runuser -u "$SVC_USER" -- env PYTHONUTF8=1 python3 "$DIR/tools/update_data.py" --no-push > /tmp/cb-first-run.log 2>&1; then
  grep -m12 '✓' /tmp/cb-first-run.log | sed 's/^/  /'
  ok "수집 성공 — 전체 기록: /tmp/cb-first-run.log"
else
  tail -20 /tmp/cb-first-run.log; stop "수집 실패 — 위 기록을 확인하세요"
fi

say "8. 5분마다 자동 수집 (systemd 타이머)"
# oneshot 이라 한 회차가 5분을 넘기면 다음 회차는 끝날 때까지 기다린다(겹쳐 돌지 않는다).
cat > /etc/systemd/system/$UNIT.service <<EOF
[Unit]
Description=충북소방 기상종합상황판 데이터 수집
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$SVC_USER
WorkingDirectory=$DIR
Environment=PYTHONUTF8=1
Nice=10
TimeoutStartSec=15min
# 원자적 저장이 비정상 종료로 남긴 임시파일 정리
ExecStartPre=-/usr/bin/find $DIR -maxdepth 2 -name '*.tmp.*' -mmin +60 -delete
ExecStart=/usr/bin/python3 tools/update_data.py --no-push
# 새로 쓴 파일도 nginx 가 읽을 수 있게 SELinux 표시를 맞춘다(root 로 실행, 실패는 무시)
ExecStartPost=+-/usr/sbin/restorecon -R $DIR
EOF
cat > /etc/systemd/system/$UNIT.timer <<EOF
[Unit]
Description=충북소방 기상종합상황판 데이터 수집 — 5분마다

[Timer]
OnCalendar=*:0/5
AccuracySec=10s
Persistent=true

[Install]
WantedBy=timers.target
EOF
# 레이더만 1분마다 따로 — 5분 수집만 기다리면 상황실 레이더가 실제보다 10분 넘게 늦는다.
# 이미 받은 5분 칸이면 기상청을 부르지 않으므로 실제 호출은 5분에 한두 번이다(update_data.py fetch_radar_frames).
cat > /etc/systemd/system/cbweather-radar.service <<EOF
[Unit]
Description=충북소방 기상종합상황판 레이더 영상 받기
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$SVC_USER
WorkingDirectory=$DIR
Environment=PYTHONUTF8=1
Nice=10
TimeoutStartSec=3min
ExecStart=/usr/bin/python3 tools/update_data.py --radar-only
ExecStartPost=+-/usr/sbin/restorecon -R $DIR/images
EOF
cat > /etc/systemd/system/cbweather-radar.timer <<EOF
[Unit]
Description=충북소방 기상종합상황판 레이더 — 1분마다

[Timer]
OnCalendar=*:*:20
AccuracySec=5s

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now $UNIT.timer >/dev/null 2>&1
systemctl enable --now cbweather-radar.timer >/dev/null 2>&1
ok "다음 실행: $(systemctl list-timers $UNIT.timer --no-legend | awk '{print $1, $2, $3}') · 레이더는 1분마다"

say "8-2. 의견 받기 (화면의 💬 → 127.0.0.1:8081 → $DIR/.data/feedback.jsonl)"
install -d -o "$SVC_USER" -g "$SVC_USER" -m 750 "$DIR/.data"
cat > /etc/systemd/system/cbweather-feedback.service <<EOF
[Unit]
Description=충북소방 기상종합상황판 의견 받기
After=network.target

[Service]
User=$SVC_USER
WorkingDirectory=$DIR
Environment=PYTHONUTF8=1
ExecStart=/usr/bin/python3 tools/server/feedback_server.py
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$DIR/.data

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now cbweather-feedback >/dev/null 2>&1
systemctl restart cbweather-feedback
sleep 1
systemctl is-active -q cbweather-feedback && ok "의견 받기 동작" || warn "의견 받기 시작 실패 — journalctl -u cbweather-feedback -n 30"

say "9. 웹서버 (nginx · 80 포트)"
# 저장소 폴더를 그대로 여는 것이라 .env(API 키)·.git·tools·로그가 같이 노출되지 않게
# 화면에 필요한 확장자만 허용하고 나머지는 전부 404.
sed -i 's/ default_server//' /etc/nginx/nginx.conf      # 기본 예제 서버 대신 상황판이 80 을 받는다
cat > /etc/nginx/conf.d/cbweather.conf <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    root $DIR;
    index index.html;
    charset utf-8;
    access_log off;

    location ~ /\\.          { return 404; }          # .env · .git · .tmp
    location ^~ /tools/     { return 404; }
    location = /            { }                       # → index.html → 지도.html
    location = /api/feedback {                        # 화면의 💬 의견 보내기 · 의견.html (tools/server/feedback_server.py)
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header X-Real-IP \$remote_addr;
        client_max_body_size 16k;
        proxy_read_timeout 10s;
    }
    location ~* \\.(html|js|css|json|svg|png|jpe?g|gif|webp|ico|woff2?)\$ {
        add_header Cache-Control "no-cache";          # data.js 가 5분마다 바뀌므로 매번 확인
    }
    location /              { return 404; }
}
EOF
nginx -t -q
semanage fcontext -a -t httpd_sys_content_t "$DIR(/.*)?" 2>/dev/null \
  || semanage fcontext -m -t httpd_sys_content_t "$DIR(/.*)?"
restorecon -R "$DIR"
# nginx 가 의견 받기(127.0.0.1:8081)로 넘길 수 있게 — SELinux 기본값은 웹서버의 외부 연결을 막는다
getsebool httpd_can_network_connect 2>/dev/null | grep -q ' on$' || setsebool -P httpd_can_network_connect 1
systemctl enable --now nginx >/dev/null 2>&1
systemctl reload nginx
ok "nginx 동작 — SELinux: $(getenforce)"

say "10. 방화벽 (http 허용)"
if systemctl is-active -q firewalld; then
  firewall-cmd -q --permanent --add-service=http && firewall-cmd -q --reload && ok "http(80) 허용"
else
  ok "firewalld 꺼져 있음 — 건너뜀"
fi

IP=$(hostname -I | awk '{print $1}')
code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "http://127.0.0.1/%EC%A7%80%EB%8F%84.html" || true)
[ "$code" = 200 ] && ok "화면 응답 확인 (200)" || warn "화면 응답 $code — nginx 기록: journalctl -u nginx"

say "완료"
echo "  · 이 서버에서     : http://localhost/지도.html"
echo "  · 행정망 PC 에서  : http://$IP/지도.html"
FBK=$(grep -m1 '^FEEDBACK_ADMIN_KEY=' "$DIR/.env" | cut -d= -f2-)
echo "  · 받은 의견(비밀) : http://$IP/의견.html#k=$FBK   ← 즐겨찾기 해 두고 남에게 알리지 마세요"
echo "                      원본 CSV: $DIR/.data/feedback.csv   · 주소가 샜으면 .env 의 FEEDBACK_ADMIN_KEY 만 바꾸면 된다"
echo "  · 수집 기록 보기  : journalctl -u $UNIT -n 50   (레이더: journalctl -u cbweather-radar -n 20)"
echo "  · 소스 반영       : bash $DIR/tools/server/update-code.sh   (GitHub main 에 올린 뒤)"
