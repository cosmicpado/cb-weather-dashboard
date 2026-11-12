/* 서버 시각 맞추기(2026-11-12) — 상황판의 '지금'을 화면을 띄운 PC 시계가 아니라 서버 시계로.
   행정망 PC 는 시간 동기화가 안 돼 시계가 밀린 경우가 있어, 오른쪽 위 시계와 'N분 전 관측' 같은 계산이 틀렸다.
   · 서버 응답 머리글(Date)과 이 PC 시계의 차이를 재서, 화면 안의 Date(지금 시각)에 그 차이를 더한다.
   · 왕복 시간이 가장 짧았던 측정을 쓰고, 5분마다 다시 잰다. 1초 미만 차이는 무시한다.
   · 다음 화면에서 처음부터 맞게 이 탭(sessionStorage)에 차이를 기억한다.
   · 파일로 연 화면(file://)이나 Date 머리글이 없으면 PC 시계 그대로.
   · PC 시간대가 한국(UTC+9)이 아니면 9시간이 틀리므로, 화면에 보이는 시각이 한국 시각이 되게 그만큼 더 옮긴다.
     (자료의 '2026-11-12 16:50' 같은 시각도 같은 PC 기준으로 읽혀 'N분 전' 계산은 그대로 맞는다)
   ⚠ 다른 스크립트보다 먼저 불러야 한다(각 화면 <head> 맨 앞). */
(function () {
  var OD = window.Date;
  if (OD.__cbSynced) return;
  var KEY = 'cbClockOffset', sync = 0;
  try { var v = +sessionStorage.getItem(KEY); if (isFinite(v) && Math.abs(v) < 864e5) sync = v; } catch (e) {}
  /* 시간대 보정 — 한국이면 0 */
  var tz = (540 + new OD().getTimezoneOffset()) * 60000;
  var off = sync + tz;

  function now() { return OD.now() + off; }
  function D(a, b, c, d, e, f, g) {
    if (!(this instanceof D)) return new OD(now()).toString();      // Date() 를 함수로 부르면 글자
    var n = arguments.length;
    if (n === 0) return new OD(now());
    if (n === 1) return new OD(a);
    return new OD(a, b, c === undefined ? 1 : c, d || 0, e || 0, f || 0, g || 0);
  }
  D.prototype = OD.prototype;
  D.now = now; D.parse = OD.parse; D.UTC = OD.UTC;
  D.__cbSynced = true; D.__orig = OD;
  window.Date = D;
  window.cbClock = { offset: function () { return off; }, sync: function () { return sync; }, tz: function () { return tz; }, now: function () { return new OD(now()); } };

  if (!/^https?:$/.test(location.protocol) || !window.fetch) return;
  var best = null;
  function measure() {
    var t0 = OD.now();
    return fetch('clock-sync.js?_t=' + t0, { method: 'HEAD', cache: 'no-store' }).then(function (r) {
      var t1 = OD.now(), h = r.headers.get('Date');
      if (!h) return;
      var srv = OD.parse(h);
      if (!isFinite(srv)) return;
      var rtt = t1 - t0;
      var o = srv + 500 - (t0 + t1) / 2;           // Date 머리글은 초 단위 → 가운데(0.5초)로
      if (!best || rtt < best.rtt) best = { rtt: rtt, o: o };
    }).catch(function () {});
  }
  function apply() {
    if (!best) return;
    sync = Math.abs(best.o) < 1000 ? 0 : Math.round(best.o);
    off = sync + tz;
    try { sessionStorage.setItem(KEY, String(sync)); } catch (e) {}
  }
  function round() { best = null; measure().then(measure).then(measure).then(apply); }
  round();
  setInterval(round, 5 * 60 * 1000);
})();
