/* 외부 하천 CCTV — 홍수통제소(n.flood.go.kr, 하천 상세에 이미 삽입) 밖에서 일반에 공개된 실시간 영상.
   2026-09-21 16개 시도 조사(지자체·홍수통제소·KBS 재난포털·유튜브 라이브). 운영 주체가 바뀌거나 주소가 죽으면 여기만 고친다.
   · 시도 키(region.js 의 key) → 관서 이름 → 항목 목록. '*' 는 그 시도 모든 관서에.
   · 항목 종류(화면이 이 순서로 판정):
       {n, kbs:id}          KBS 재난감시 CCTV — 서버가 올리는 data-cctv.js(하루 토큰)에서 재생 주소를 찾아 화면 안 hls 재생
       {n, hls:m3u8, thumb} 직접 HLS(CORS 허용 확인된 곳: 포항시 방재 CCTV) — 화면 안 재생
       {n, frame:url}       뷰어 페이지 iframe(https·X-Frame-Options 없음 확인: 춘천시 하천 CCTV)
       {n, hrfco:obscd}     홍수통제소 수위관측소 CCTV — 장치번호표(cctv-hrfco.js)로 켜고(getCctvScreen.do no-cors POST) 직접 HLS 재생
       {n, u}               새 창 링크(제주시·서귀포·부산 안전ON·용인 등 — 세션/CSRF·http 전용·SPA 라 삽입 불가)
   · 예의: 지자체 뷰어는 30초 뒤 스스로 멈추게 만들어 두었으므로 우리도 직접 재생은 90초 뒤 멈추고 '계속 보기'를 띄운다.
   · 조사 기록: workflows/운영현황.md '하천 CCTV 출처 조사'. */
(function () {
  var KBS = function (id, name) { return { n: 'KBS ' + name, u: 'https://d.kbs.co.kr/special/cctvShare?cctvId=' + id, kbs: id }; };
  var CHEONGJU = [KBS('9968', '사직동 (무심천)')];
  window.CCTV_LINKS = {
    chungbuk: { '청주동부': CHEONGJU, '청주서부': CHEONGJU, '단양': [KBS('9975', '도담삼봉 (남한강)')] },
  };

  /* ── 항목 판정 ── */
  window.cctvKey = function (x) { return x.kbs ? 'kbs:' + x.kbs : x.hls ? 'hls:' + x.hls : x.frame ? 'frame:' + x.frame : null; };
  /* KBS 카메라의 재생 요청·정지영상 주소 — 서버가 올리는 data-cctv.js(window.KBS_CCTV, 하루 토큰) 에서 */
  window.kbsCam = function (id) {
    var L = (window.KBS_CCTV && window.KBS_CCTV.cams) || [];
    for (var i = 0; i < L.length; i++) if (String(L[i].id) === String(id)) return L[i];
    return null;
  };
  /* 홍수통제소 관측소의 장치번호 — 서버가 매일 올리는 표(data-cctv.js window.HRFCO_CCTV_LIVE, 새 카메라 자동 반영) 먼저,
     없으면 화면에 박아 둔 표(cctv-hrfco.js) */
  window.hrfcoCam = function (obscd) {
    var L = (window.HRFCO_CCTV_LIVE && window.HRFCO_CCTV_LIVE.table) || {}, T = window.HRFCO_CCTV || {}, k = String(obscd);
    var e = L[k] || T[k]; return (e && (e.ld || e.hd)) ? e : null;
  };
  /* ★ KBS 중계서버가 2026-10-08 부터 핫링크를 막았다 — 스트림(kbscctv-cache.loomex.net)이 Referer 가
     'https://d.kbs.co.kr/' 일 때만 200 이고 우리 출처로는 403. 브라우저는 Referer 를 못 바꾸므로
     화면 안 재생이 불가능하다(정지영상 cctvImg 는 그대로 열린다). → KBS 는 새 창(KBS 포털) 링크로만.
     되살아났는지 가끔 확인: 아래 값을 false 로 두고 재생되면 KBS 가 다시 푼 것. */
  window.KBS_STREAM_BLOCKED = true;
  /* 화면 안에서 틀 수 있나(홍수통제소는 장치번호표가 있을 때만) */
  window.cctvInline = function (x) { return !!(x.hls || x.frame || (x.kbs && !window.KBS_STREAM_BLOCKED && window.kbsCam(x.kbs)) || (x.hrfco && window.hrfcoCam(x.hrfco))); };
  window.cctvPoster = function (x) { if (x.thumb) return x.thumb + (x.thumb.indexOf('?') < 0 ? '?' : '&') + '_t=' + Math.floor(Date.now() / 30000); var c = x.kbs ? window.kbsCam(x.kbs) : null; return c ? c.img : ''; };

  /* 홍수통제소 영상 서버는 유역(fc)마다 다르다 — getCctvScreen.do 응답의 videoOutputSSL 실측.
     예전엔 한강(lw.hrfco.go.kr)으로 고정해서, 충북 CCTV 20곳 중 금강 13곳은 없는 주소를 15초씩 붙잡고
     재시도하다 늦게 뜨거나 실패했다. 응답은 CORS 로 못 읽으므로 주소 규칙을 여기 둔다. */
  var HRFCO_HOST = { '01': ['lw.hrfco.go.kr', 'hi.hrfco.go.kr'],
                     '02': ['cctvlo.nakdongriver.go.kr', 'cctvhi.nakdongriver.go.kr'],
                     '03': ['cctvlo.geumriver.go.kr', 'cctvhi.geumriver.go.kr'],
                     '04': ['cctvlo.yeongsanriver.go.kr', 'cctvhi.yeongsanriver.go.kr'] };
  function hrfcoM3u8(e) { var h = HRFCO_HOST[e.fc || '01'] || HRFCO_HOST['01'];
    return 'https://' + (e.ld ? h[0] : h[1]) + '/live/cctv' + (e.ld || e.hd) + '/hls.m3u8'; }

  /* ── HLS 재생(hls.js 는 처음 필요할 때 한 번만 내려받음, 사파리는 기본 재생) ── */
  var HLS_SRC = 'https://cdn.jsdelivr.net/npm/hls.js@1.5.15/dist/hls.min.js', hlsLoading = null;
  function loadHls(cb) {
    if (window.Hls) { cb(true); return; }
    if (!hlsLoading) { hlsLoading = []; var s = document.createElement('script'); s.src = HLS_SRC;
      s.integrity = 'sha384-oJR5PTkR0gvqJ/UnX1IkFQgxg6BByX7jPWmgSSY5dz0+Yc7O3mloo717zZpF/xpb'; s.crossOrigin = 'anonymous';   /* 버전을 올리면 이 값도 다시 계산 */
      s.onload = function () { var q = hlsLoading; hlsLoading = null; q.forEach(function (f) { f(true); }); };
      s.onerror = function () { var q = hlsLoading; hlsLoading = null; q.forEach(function (f) { f(false); }); };
      document.head.appendChild(s); }
    hlsLoading.push(cb);
  }
  function startHls(video, m3u8, onError) {
    /* MSE 가 있으면 hls.js 로(일부 크로미움이 자체 HLS 를 '될지도'라 하지만 실황에서 멈추는 일이 있어 — 2026-09-22 실측),
       없으면(iOS 사파리) 브라우저 자체 HLS 로 */
    var mse = !!(window.MediaSource || window.WebKitMediaSource);
    if (!mse && video.canPlayType('application/vnd.apple.mpegurl')) {
      /* 브라우저 자체 HLS: 실황 목록은 처음 play() 때 아직 준비가 안 돼 거부되기도 한다 → 준비되면 다시 */
      var tryPlay = function () { video.play().catch(function () {}); };
      video.addEventListener('canplay', tryPlay, { once: true }); video.addEventListener('loadedmetadata', tryPlay, { once: true });
      video.src = m3u8; video.load(); tryPlay(); return;
    }
    var go = function () {
      if (!window.Hls || !window.Hls.isSupported()) { if (onError) onError('hls'); return; }
      if (video._hls) { try { video._hls.destroy(); } catch (e) {} }
      // 실황은 조각이 1.5~2초라 끝에서 2조각 뒤부터 틀어도 끊기지 않는다(기본 3조각 → 시작이 2~3초 빠름)
      var h = new window.Hls({ enableWorker: true, lowLatencyMode: false, liveSyncDurationCount: 2 }); video._hls = h;
      h.on(window.Hls.Events.ERROR, function (ev, d) { if (d && d.fatal && onError) onError(d.type); });
      h.loadSource(m3u8); h.attachMedia(video);
      h.on(window.Hls.Events.MANIFEST_PARSED, function () { video.play().catch(function () {}); });
    };
    loadHls(function (ok) { if (ok) go(); else if (onError) onError('load'); });
  }
  /* video 요소에 항목을 튼다. KBS 는 요청 주소를 먼저 GET 하면 본문에 서명된 m3u8 주소가 온다(CORS 허용, 2026-09-21 실측).
     90초 뒤 스스로 멈추고 onStop 을 부른다(지자체 서버 예의; 화면이 '계속 보기' 버튼을 띄운다). */
  /* 탭이 가려지면 크로미움이 무음 영상을 멈춘다 → 다시 보이면 살아 있는 재생기만 이어 튼다 */
  if (!window._cctvVisHook) { window._cctvVisHook = true; document.addEventListener('visibilitychange', function () {
    if (document.hidden) return; document.querySelectorAll('video').forEach(function (v) { if (v._live && v.paused) v.play().catch(function () {}); }); }); }
  window.cctvPlay = function (video, x, onError, onStop) {
    if (!video || !x) return;
    window.cctvStop(video); video._live = true;
    /* 켜는 도중(통제소 켜기 대기·KBS 토큰 요청) 다른 항목을 누르면 먼저 것이 나중에 덮어쓰지 않게 — 순번이 바뀌면 옛 요청은 버린다 */
    var seq = video._seq = (video._seq || 0) + 1, live = function () { return video._seq === seq; };
    /* x.stopAfter(ms): 0 이면 스스로 멈추지 않는다 — 상황실 벽면처럼 화면이 60초마다 다음 지점으로 넘기는 곳용. 기본 90초. */
    var stopMs = (x.stopAfter != null) ? +x.stopAfter : 90000;
    var armStop = function () { if (video._stopT) clearTimeout(video._stopT); if (stopMs > 0) video._stopT = setTimeout(function () { window.cctvStop(video); if (onStop) onStop(); }, stopMs); };
    if (x.hls) { startHls(video, x.hls, onError); armStop(); return; }
    if (x.hrfco) {
      /* 통제소 스트림은 누가 보기 시작해야 켜진다 — 켜기 요청(응답은 못 읽어도 됨) 뒤 m3u8 이 200 될 때까지 기다린다 */
      var e = window.hrfcoCam(x.hrfco); if (!e) { if (onError) onError('device'); return; }
      var id = e.ld || e.hd, m3u8 = hrfcoM3u8(e);
      var body = new URLSearchParams({ deviceId: id, fcodvcd: e.fc || '01', type: e.ld ? 'low' : 'high' });
      try { fetch('https://n.flood.go.kr/getCctvScreen.do', { method: 'POST', mode: 'no-cors', body: body }).catch(function () {}); } catch (err) {}
      if (!window.Hls && (window.MediaSource || window.WebKitMediaSource)) loadHls(function () {});   // 켜지는 동안 재생기도 미리 받아 둔다
      /* 켜기 요청 직후부터 확인한다. 아직 안 켜졌으면 서버가 요청을 붙잡고 있다가 켜지는 순간 200 을 준다(실측 2~3초) */
      var tries = 0, wait = function () {
        if (!live()) return; tries++;
        fetch(m3u8, { cache: 'no-store' }).then(function (r) {
          if (!live()) return;
          if (r.ok) { startHls(video, m3u8, onError); armStop(); }
          else if (tries < 6) setTimeout(wait, 1000); else if (onError) onError('start');
        }).catch(function () { if (!live()) return; if (tries < 6) setTimeout(wait, 1000); else if (onError) onError('net'); });
      };
      setTimeout(wait, 300); return;
    }
    var cam = x.kbs ? window.kbsCam(x.kbs) : null;
    if (cam && window.KBS_STREAM_BLOCKED) { if (onError) onError('KBS 차단'); return; }   /* 위 설명 참고 — 헛되이 기다리지 않는다 */
    if (!cam || !cam.url) { if (onError) onError('token'); return; }
    fetch(cam.url, { cache: 'no-store' }).then(function (r) { return r.ok ? r.text() : ''; })
      .then(function (t) { if (!live()) return; t = String(t || '').trim(); if (/^https?:\/\//.test(t)) { startHls(video, t, onError); armStop(); } else if (onError) onError('token'); })
      .catch(function () { if (!live()) return; if (onError) onError('net'); });
  };
  window.cctvStop = function (video) {
    if (!video) return; video._live = false;
    if (video._stopT) { clearTimeout(video._stopT); video._stopT = null; }
    if (video._hls) { try { video._hls.destroy(); } catch (e) {} video._hls = null; }
    try { video.pause(); video.removeAttribute('src'); video.load(); } catch (e) {}
  };
  /* 하위 호환(예전 이름) */
  window.kbsPlay = function (video, cam, onError) { window.cctvPlay(video, { kbs: cam && cam.id }, onError); };
  window.kbsStop = window.cctvStop;

  /* 관서(또는 그 관서의 본체 시군)에 해당하는 링크 목록 */
  window.cctvLinksFor = function (key, station, sigun) {
    var T = window.CCTV_LINKS[key] || {}; var out = [];
    [station, sigun].forEach(function (k) { if (k && T[k]) T[k].forEach(function (x) { if (out.indexOf(x) < 0) out.push(x); }); });
    (T['*'] || []).forEach(function (x) { if (out.indexOf(x) < 0) out.push(x); });
    return out;
  };
})();
