#!/usr/bin/env bash
# 행정망 서버 소스 반영 — GitHub main 의 새 코드를 받는다. 반영하고 싶을 때만 직접 실행한다.
# 수집기가 만든 데이터(data.js·영상·강수 누적 등)는 그대로 둔다 — 받는 동안 화면이 옛 데이터로 돌아가지 않게.
# 받은 의견(.data/feedback.jsonl)·레이더 프레임(images/radar)은 깃이 추적하지 않아 reset 해도 그대로 남는다.
# ⚠ 1분 레이더 타이머·의견 받기 서비스가 아직 없는 서버면 setup-rocky.sh 를 한 번 다시 실행한다(여러 번 실행해도 안전).
#
#   bash /opt/cbweather/tools/server/update-code.sh            # 최신 main 반영
#   bash /opt/cbweather/tools/server/update-code.sh <커밋>     # 그 커밋으로 되돌리기(문제가 생겼을 때)
set -euo pipefail

DIR="/opt/cbweather"
SVC_USER="cbweather"
UNIT="cbweather-collect"
# 수집기가 쓰는 파일 — 깃에도 들어 있어서 reset 하면 저장소의 옛 값으로 덮인다
KEEP="data.js data-cctv.js 상황판.html images/kma_radar.png images/kma_satellite.png images/kma_warn.png .tmp/rain_history.json"

[ "$(id -u)" = 0 ] || { echo "root 로 실행하세요 (sudo bash $0)"; exit 1; }
G() { runuser -u "$SVC_USER" -- git -C "$DIR" "$@"; }

G fetch -q origin main
TARGET=$(G rev-parse "${1:-origin/main}")
if [ "$(G rev-parse HEAD)" = "$TARGET" ]; then echo "이미 최신 — $(G log --oneline -1)"; exit 0; fi
echo "바뀌는 내용:"
G log --oneline -20 --invert-grep --grep='^데이터 갱신' "HEAD..$TARGET" | sed 's/^/  /'   # 옛 운영 서버의 데이터 커밋은 빼고

# 수집 중에 파일을 바꾸지 않게 타이머를 멈추고, 돌고 있는 회차가 끝나길 기다린다
systemctl stop $UNIT.timer cbweather-radar.timer 2>/dev/null || true
while systemctl is-active -q $UNIT.service || systemctl is-active -q cbweather-radar.service; do sleep 2; done

BAK=$(mktemp -d)
for f in $KEEP; do [ -e "$DIR/$f" ] && (cd "$DIR" && cp -a --parents "$f" "$BAK/"); done
G reset -q --hard "$TARGET"
cp -a "$BAK/." "$DIR/" && rm -rf "$BAK"
chown -R "$SVC_USER:$SVC_USER" "$DIR"
restorecon -R "$DIR"

systemctl start $UNIT.timer
systemctl start cbweather-radar.timer 2>/dev/null || true
systemctl try-restart cbweather-feedback 2>/dev/null || true     # 의견 받기 새 코드 반영(받은 의견 .data/ 는 그대로)
echo "✓ 반영 완료 — $(G log --oneline -1)"
echo "  화면은 브라우저 새로고침(F5)으로 바로 보인다. 되돌리려면: bash $0 <위 목록의 이전 커밋>"
