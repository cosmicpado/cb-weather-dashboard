/* ===== 충청북도 재난안전대책본부 비상근무 단계 =====
   '기상특보 단계별 비상근무체계'(충청북도 재대본) 표를 그대로 옮긴 것. 지도.html·상황실.html 이 같이 쓴다.

     구분       준비                 1단계 주의(Yellow)            2단계 경계(Orange)     3단계 심각(Red)
     대설·호우  예비특보 3개 시·군   주의보 3개 시·군 / 경보 1개   경보 3개 시·군 이상    광역적 경보
     태풍       태풍정보 발표        예비특보                      주의보 및 경보         광역적 경보

   표에 없는 부분은 이렇게 정했다(2026-10-30):
     · '광역적 경보' = 경보 6개 시·군 이상(도내 11개 시·군의 과반) 또는 '충청북도 전역'
     · 대설·호우 주의보 1~2개 시·군 = 준비 (표 사이 빈칸 — 주의보가 났는데 평상으로 두지 않는다)
     · 태풍정보 발표 = 진행 중인 태풍이 한반도에 영향(상륙·직접·간접)으로 잡힐 때
     · 폭염·한파·강풍·건조 등 표에 없는 특보는 단계에 넣지 않는다(특보 카드에서 본다)
   시·군 수는 관서가 아니라 시·군으로 센다 — 청주동부·청주서부는 '청주' 하나. */
(function () {
  'use strict';
  var STAGES = [
    { rank: 0, key: 'normal', name: '평상', step: '',          color: 'safe' },
    { rank: 1, key: 'ready',  name: '준비', step: '준비 단계', color: 'brand' },
    { rank: 2, key: 's1',     name: '주의', step: '비상 1단계', color: 'caution' },
    { rank: 3, key: 's2',     name: '경계', step: '비상 2단계', color: 'warn' },
    { rank: 4, key: 's3',     name: '심각', step: '비상 3단계', color: 'severe' }
  ];
  var WIDE_N = 6;   // 광역적 경보 — 이 수 이상의 시·군

  function conf() { return window.REGION_CONF || {}; }
  /* 도내 시·군 이름(짧은 이름) — region.js admin 의 값에서 시/군을 뗀다: 청주·충주·…·단양 (11개) */
  function sigunList() {
    var a = conf().admin || {}, seen = {}, out = [];
    Object.keys(a).forEach(function (k) { var v = String(a[k] || k).replace(/(시|군)$/, ''); if (!seen[v]) { seen[v] = 1; out.push(v); } });
    return out;
  }
  /* 특보 지역 글 → 해당 시·군 집합. 관서명(청주동부)·시군명(청주시)·전역 표기를 모두 받는다. */
  function sigunsIn(area) {
    var a = String(area || ''), RC = conf(), admin = RC.admin || {}, list = sigunList(), hit = {};
    if (/전역/.test(a) || (RC.wideNames || ['충청북도', '충북']).some(function (w) { return a.split(/[,·\/()\s]/).indexOf(w) >= 0; }) && !list.some(function (s) { return a.indexOf(s) >= 0; })) {
      list.forEach(function (s) { hit[s] = 1; }); return hit;            // '충청북도 전역' · 시군 없이 '충청북도'만
    }
    Object.keys(admin).forEach(function (office) { if (a.indexOf(office) >= 0) hit[String(admin[office]).replace(/(시|군)$/, '')] = 1; });
    list.forEach(function (s) { if (a.indexOf(s) >= 0) hit[s] = 1; });
    return hit;
  }
  function count(o) { return Object.keys(o).length; }
  function union(a, b) { var o = {}; Object.keys(a).forEach(function (k) { o[k] = 1; }); Object.keys(b).forEach(function (k) { o[k] = 1; }); return o; }
  function names(o) { return count(o) >= sigunList().length ? '도 전역' : Object.keys(o).join('·'); }

  /* warnings: [{type, area, level}]  prelim: [{type, items:[{area, north|north_match}]}]  typhoon: [{near_kr|eff}] */
  window.cbStage = function (warnings, prelim, typhoon) {
    var RS = /호우|대설/, TY = /태풍/;
    var rsW = {}, rsA = {}, rsP = {}, tyW = {}, tyA = {}, tyP = {}, rsWide = false, tyWide = false;
    (warnings || []).forEach(function (w) {
      var t = String(w.type || ''), isBo = t.indexOf('경보') >= 0 || w.level === 'severe', s = sigunsIn(w.area);
      var all = count(s) >= sigunList().length;
      if (RS.test(t)) { rsA = union(rsA, s); if (isBo) { rsW = union(rsW, s); if (all) rsWide = true; } }
      else if (TY.test(t)) { tyA = union(tyA, s); if (isBo) { tyW = union(tyW, s); if (all) tyWide = true; } }
    });
    (prelim || []).forEach(function (g) {
      var t = String(g.type || '');
      (g.items || []).forEach(function (it) {
        if (!(it.north || it.north_match)) return;                       // 충북에 걸린 항목만
        var s = sigunsIn(String(it.area || '').split('(')[0]);            // '청주 (충청북도)' → 괄호 앞만
        if (!count(s)) s = sigunsIn(it.area);
        if (RS.test(t)) rsP = union(rsP, s); else if (TY.test(t)) tyP = union(tyP, s);
      });
    });
    var tyInfo = (typhoon || []).some(function (x) { return x && (x.near_kr || ['1', '2', '3'].indexOf(String(x.eff)) >= 0); });

    var best = { rank: 0, reason: '' };
    function up(rank, reason) { if (rank > best.rank) best = { rank: rank, reason: reason }; }
    // 대설·호우
    var nW = count(rsW), nA = count(rsA), nP = count(rsP);
    if (rsWide || nW >= WIDE_N) up(4, '광역적 경보 · 경보 ' + nW + '개 시·군(' + names(rsW) + ')');
    else if (nW >= 3) up(3, '경보 ' + nW + '개 시·군(' + names(rsW) + ')');
    else if (nW >= 1) up(2, '경보 ' + nW + '개 시·군(' + names(rsW) + ')');
    if (nA >= 3) up(2, '주의보 이상 ' + nA + '개 시·군(' + names(rsA) + ')');
    else if (nA >= 1) up(1, '주의보 ' + nA + '개 시·군(' + names(rsA) + ')');
    if (nP >= 3) up(1, '예비특보 ' + nP + '개 시·군(' + names(rsP) + ')');
    // 태풍
    var tW = count(tyW), tA = count(tyA);
    if (tyWide || tW >= WIDE_N) up(4, '태풍 광역적 경보 · ' + tW + '개 시·군');
    else if (tA >= 1) up(3, '태풍 ' + (tW ? '경보' : '주의보') + ' ' + tA + '개 시·군(' + names(tyA) + ')');
    if (count(tyP) >= 1) up(2, '태풍 예비특보 ' + count(tyP) + '개 시·군');
    if (tyInfo) up(1, '태풍정보 발표(한반도 영향)');

    var s = STAGES[best.rank];
    var hazard = /태풍/.test(best.reason) ? '태풍' : (best.rank ? '대설·호우' : '');
    return { rank: s.rank, key: s.key, name: s.name, step: s.step, color: s.color, hazard: hazard,
             reason: best.rank ? (hazard === '태풍' ? best.reason : '대설·호우 ' + best.reason) : '대설·호우·태풍 특보 없음', blink: s.rank >= 4 };
  };
  window.cbStage.STAGES = STAGES;
})();
