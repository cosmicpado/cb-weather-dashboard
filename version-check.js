/* 새 판 자동 반영 — 서버에 새 코드가 올라오면 켜 둔 화면이 스스로 새로고침한다(2026-11-19).
   서버의 tools/server/update-code.sh 가 코드를 받을 때 version.json 에 커밋 번호를 쓴다(약 50바이트).
   화면은 5분마다 그 작은 파일만 확인한다 — 화면 파일 자체(상황실.html 4MB)를 받아 비교하면 행정망에 부담이라 안 된다.
   · version.json 이 없으면(이 PC 서버.bat · Cloudflare) 아무것도 하지 않는다
   · 시연 중(주소 ?demo= · 화면 안 시연 CB_DEMO_ON)·배치 편집 중(WALL_EDITING)이면 끝날 때까지 미룬다(30초마다 다시 봄) */
(function () {
  var first = null, pending = false;
  function busy() {
    return !!(window.WALL_EDITING || window.CB_DEMO_ON || /[?&]demo=/.test(location.search));
  }
  function check() {
    fetch('version.json?_t=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var v = j && j.v ? String(j.v) : null;
        if (!v) return;                       // 파일 없음·읽기 실패 — 그대로 둔다
        if (first === null) { first = v; return; }
        if (v !== first) pending = true;
      })
      .catch(function () {})
      .then(function () { if (pending && !busy()) location.reload(); });
  }
  check();
  setInterval(check, 300000);
  setInterval(function () { if (pending && !busy()) location.reload(); }, 30000);
})();
