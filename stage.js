/* ===== 충청북도 재난안전대책본부 비상근무 단계 =====
   '기상특보 단계별 비상근무체계'(충청북도 재대본) 표를 그대로 옮긴 것. 종합 현황(종합.html)·상황실.html 이 같이 쓴다.

     구분       준비                 1단계 주의(Yellow)            2단계 경계(Orange)     3단계 심각(Red)
     대설·호우  예비특보 3개 시·군   주의보 3개 시·군 / 경보 1개   경보 3개 시·군 이상    광역적 경보
     태풍       태풍정보 발표        예비특보                      주의보 및 경보         광역적 경보

   기준은 관리자 화면 '비상단계 · 근무' 탭에서 소방본부·119종합상황실 따로 고칠 수 있다(2026-11-23, 아래 TABLE·규칙).
   기본값(재대본 표 그대로)은 표에 숫자로 정해진 준비 ~ 2단계까지만 자동으로 계산한다(2026-11-18).
     · 3단계(광역적 경보 발령)는 재대본이 판단해 발령하는 것이라 자동으로 올리지 않는다 — 상황실 'stage' 지정(재대본 발령)일 때만.
       대신 경보 6개 시·군 이상(도내 11개의 과반) 또는 '충청북도 전역'이면 2단계에 '3단계 발령 검토' 안내(review)를 붙인다.
     · 준비 = 표 그대로 예비특보 3개 시·군(주의보 1~2개 시·군은 단계에 넣지 않는다)
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
  var WIDE_N = 6;   // 광역적 경보로 보고 '3단계 발령 검토'를 알리는 경보 시·군 수

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

  /* ── 단계 기준(규칙) ── 관리자 화면 '비상단계 · 근무' 탭에서 고친다(2026-11-23). 서버 .data/stage_rules.json, 없으면 아래 TABLE.
     규칙 = 단계(1 준비 · 2 1단계 · 3 2단계 · 4 3단계)마다 '조건 묶음' 목록.
       묶음끼리는 '또는'(하나라도 맞으면) · 묶음 안 조건은 '그리고'(모두 맞아야). 여러 단계가 맞으면 높은 단계.
     조건 = { k: 종류, lv: 특보, n: 시·군 수(이상), sc: 범위 }
       k  : rs 대설·호우 · rain 호우 · snow 대설 · ty 태풍 · tyinfo 태풍정보 발표(lv·n 없음)
       lv : p 예비특보 · a 주의보 이상 · w 경보
       sc : do 도내(충북 몇 개 시·군) — 관서별로 넓힐 때 '관할' 범위를 여기에 더한다
     대상(targets) = hq 소방본부 · room 119종합상황실. 각각 mode 'table'(재대본 표 그대로) 또는 'own'(stages 로 따로).
       관서별로 넓힐 때는 대상 이름을 'office:제천' 처럼 더하면 된다. */
  var TABLE = {   // 「기상특보 단계별 비상근무체계」(충청북도 재대본) 그대로 — 3단계 '광역적 경보 발령'은 재대본 판단이라 자동 조건 없음
    1: [[{ k: 'rs', lv: 'p', n: 3 }], [{ k: 'tyinfo' }]],
    2: [[{ k: 'rs', lv: 'w', n: 1 }], [{ k: 'rs', lv: 'a', n: 3 }], [{ k: 'ty', lv: 'p', n: 1 }]],
    3: [[{ k: 'rs', lv: 'w', n: 3 }], [{ k: 'ty', lv: 'a', n: 1 }]],
    4: []
  };
  var KIND = { rs: '대설·호우', rain: '호우', snow: '대설', ty: '태풍', tyinfo: '태풍정보 발표' };
  var LEVEL = { p: '예비특보', a: '주의보 이상', w: '경보' };
  var TARGETS = { hq: '소방본부', room: '119종합상황실' };

  /* 특보 → 사실(종류·특보별 시·군 집합). 화면 자료로도, 미리 보기의 가상 숫자로도 만든다 */
  function facts(warnings, prelim, typhoon) {
    var S = { rain: { p: {}, a: {}, w: {} }, snow: { p: {}, a: {}, w: {} }, ty: { p: {}, a: {}, w: {} } }, wide = { rs: false, ty: false };
    function kindOf(t) { return /태풍/.test(t) ? 'ty' : /호우/.test(t) ? 'rain' : /대설/.test(t) ? 'snow' : ''; }
    (warnings || []).forEach(function (w) {
      var t = String(w.type || ''), k = kindOf(t); if (!k) return;
      var isBo = t.indexOf('경보') >= 0 || w.level === 'severe', s = sigunsIn(w.area);
      S[k].a = union(S[k].a, s);
      if (isBo) { S[k].w = union(S[k].w, s); if (count(s) >= sigunList().length) wide[k === 'ty' ? 'ty' : 'rs'] = true; }
    });
    (prelim || []).forEach(function (g) {
      var k = kindOf(String(g.type || '')); if (!k) return;
      (g.items || []).forEach(function (it) {
        if (!(it.north || it.north_match)) return;                       // 충북에 걸린 항목만
        var s = sigunsIn(String(it.area || '').split('(')[0]);            // '청주 (충청북도)' → 괄호 앞만
        if (!count(s)) s = sigunsIn(it.area);
        S[k].p = union(S[k].p, s);
      });
    });
    var tyInfo = (typhoon || []).some(function (x) { return x && (x.near_kr || ['1', '2', '3'].indexOf(String(x.eff)) >= 0); });
    return { S: S, wide: wide, tyInfo: tyInfo };
  }
  /* 미리 보기용 — 숫자만으로 사실 만들기. v = { rain:{p,a,w}, snow:{…}, ty:{…}, tyInfo } (a·w 는 '그 특보가 걸린 시·군 수') */
  function factsFromCounts(v) {
    var list = sigunList(), S = {};
    ['rain', 'snow', 'ty'].forEach(function (k) {
      var c = (v && v[k]) || {}, w = Math.min(+c.w || 0, list.length), a = Math.min(Math.max(+c.a || 0, w), list.length), p = Math.min(+c.p || 0, list.length);
      function take(n) { var o = {}; list.slice(0, n).forEach(function (s) { o[s] = 1; }); return o; }
      S[k] = { p: take(p), a: take(a), w: take(w) };
    });
    return { S: S, wide: { rs: false, ty: false }, tyInfo: !!(v && v.tyInfo) };
  }
  function setOf(F, k, lv) {
    if (k === 'rs') return union(F.S.rain[lv], F.S.snow[lv]);
    return (F.S[k] || {})[lv] || {};
  }
  function condText(c, F) {
    if (c.k === 'tyinfo') return KIND.tyinfo + '(한반도 영향)';
    var s = setOf(F, c.k, c.lv), n = count(s);
    return KIND[c.k] + ' ' + LEVEL[c.lv] + ' ' + n + '개 시·군' + (n ? '(' + names(s) + ')' : '');
  }
  function condOk(c, F) {
    if (c.k === 'tyinfo') return !!F.tyInfo;
    if (!KIND[c.k] || !LEVEL[c.lv]) return false;
    return count(setOf(F, c.k, c.lv)) >= Math.max(1, +c.n || 1);
  }
  /* 규칙 계산 — { rank, reason }. reason = 맞은 묶음의 조건들 */
  function evalStages(stages, F) {
    for (var r = 4; r >= 1; r--) {
      var groups = (stages && stages[r]) || [];
      for (var i = 0; i < groups.length; i++) {
        var g = groups[i] || [];
        if (g.length && g.every(function (c) { return condOk(c, F); }))
          return { rank: r, reason: g.map(function (c) { return condText(c, F); }).join(' 그리고 ') };
      }
    }
    return { rank: 0, reason: '' };
  }
  function rulesFor(id, R) {
    R = R || window.cbStageRules;
    var t = R && R.targets && R.targets[id];
    return (t && t.mode === 'own' && t.stages) ? { own: true, stages: t.stages } : { own: false, stages: TABLE };
  }

  /* warnings: [{type, area, level}]  prelim: [{type, items:[{area, north|north_match}]}]  typhoon: [{near_kr|eff}]
     돌려줌 = 소방본부(재대본) 단계 + room(119종합상황실 단계). R(선택) = 저장 전 규칙으로 계산해 볼 때(관리자 미리 보기) */
  window.cbStage = function (warnings, prelim, typhoon, R) {
    var F = facts(warnings, prelim, typhoon);
    return fromFacts(F, warnings, R);
  };
  function fromFacts(F, warnings, R) {
    var rsW = setOf(F, 'rs', 'w'), rsA = setOf(F, 'rs', 'a'), tyW = F.S.ty.w, tyA = F.S.ty.a, rsP = setOf(F, 'rs', 'p'), tyP = F.S.ty.p;

    // 한 줄 기준(short) — 화면에 '주의 · 호우 주의보 3개'처럼 단계 이름 옆에 붙인다. 단계 계산과 별개로 지금 걸린 특보를 그대로
    var rsName = [count(F.S.rain.a) || count(F.S.rain.p) ? '호우' : '', count(F.S.snow.a) || count(F.S.snow.p) ? '대설' : ''].filter(Boolean).join('·') || '호우';
    var nW = count(rsW), nA = count(rsA), nP = count(rsP), nAo = nA - nW, tW = count(tyW), tA = count(tyA);
    var rsShort = rsName + ' ' + [nW ? '경보 ' + nW + '개' : '', nAo > 0 ? '주의보 ' + nAo + '개' : ''].filter(Boolean).join(' · ');
    var tyShort = '태풍 ' + [tW ? '경보 ' + tW + '개' : '', (tA - tW) > 0 ? '주의보 ' + (tA - tW) + '개' : ''].filter(Boolean).join(' · ');

    var hqR = rulesFor('hq', R), roomR = rulesFor('room', R);
    var best = evalStages(hqR.stages, F), room = evalStages(roomR.stages, F);
    function shortOf(b) {
      if (!b.rank) return '';
      if (/^태풍/.test(b.reason)) return /태풍정보/.test(b.reason) ? '태풍정보 발표' : tA ? tyShort : '태풍 예비특보';
      if (/예비특보/.test(b.reason) && !/주의보|경보 /.test(b.reason.replace(/예비특보/g, ''))) return rsName + ' 예비특보 ' + nP + '개';
      return rsShort;
    }
    // 광역적 경보 — 3단계 자동 조건이 없을 때(재대본 표 그대로)만 '3단계 발령 검토'를 알린다
    var review = '';
    if (!(hqR.stages[4] || []).length) {
      if (F.wide.rs || nW >= WIDE_N) review = '광역적 경보(경보 ' + (F.wide.rs ? '도 전역' : nW + '개 시·군') + ') — 3단계 발령 검토';
      if (F.wide.ty || tW >= WIDE_N) review = '태풍 광역적 경보(' + (F.wide.ty ? '도 전역' : tW + '개 시·군') + ') — 3단계 발령 검토';
    }

    // 시·군 수(호우·대설·태풍, 재대본 기준) — 상황실 '특보' 숫자 칸(2026-11-16). 경보 시·군은 주의보에서 뺀다
    var cW = union(rsW, tyW), cA = union(rsA, tyA), cP = union(rsP, tyP), nAo2 = 0;
    Object.keys(cA).forEach(function (k) { if (!cW[k]) nAo2++; });
    var cnt = { w: count(cW), a: nAo2, p: count(cP) };
    /* 단계에 못 미칠 때 한 줄 — 주의보 1~2개 시·군이면 '특보 없음'이 아니라 그 특보를 그대로(단계 기준 미만) */
    var none0 = nA ? rsShort : tA ? tyShort : ((warnings || []).length ? '호우·대설·태풍 특보 없음' : '발효 특보 없음');
    var BIG = ['평상', '준비', '1단계', '2단계', '3단계'];
    var s = STAGES[best.rank];
    var hazard = /^태풍/.test(best.reason) ? '태풍' : (best.rank ? '대설·호우' : '');
    function roomOut(rank, reason) {
      return { rank: rank, big: BIG[rank], name: STAGES[rank].name, step: STAGES[rank].step, color: STAGES[rank].color,
               reason: reason, own: roomR.own, label: TARGETS.room };
    }
    /* 재대본이 직접 발령한 단계(상황실 화면에서 지정, 24시간 유효) — 있으면 자동 계산 대신 그 단계(2026-11-16).
       소방본부·상황실 모두 그 단계. 자동 계산값은 autoRank·autoBig 로 남겨 화면이 '특보 기준 N단계'를 함께 보여 줄 수 있게 한다 */
    var ov = window.cbStageOv && window.cbStageOv.active();
    if (typeof window.CB_DEMO_STAGE === 'number') ov = { rank: window.CB_DEMO_STAGE, at: '시연' };   // 시연 3단계 = 재대본 발령 가정
    if (ov) {
      var auto = s;
      s = STAGES[ov.rank];
      return { rank: s.rank, key: s.key, name: s.name, step: s.step, color: s.color, hazard: hazard, cnt: cnt,
               big: BIG[s.rank], short: best.rank ? shortOf(best) : none0,
               reason: '충북 재대본 발령(' + ov.at + ')',
               manual: true, manualAt: ov.at, manualDuty: ov.duty || null, autoRank: auto.rank, autoBig: BIG[auto.rank], review: '', blink: s.rank >= 4,
               hqOwn: hqR.own, room: roomOut(s.rank, '충북 재대본 발령(' + ov.at + ')') };
    }
    return { rank: s.rank, key: s.key, name: s.name, step: s.step, color: s.color, hazard: hazard, cnt: cnt,
             big: BIG[s.rank],          // 크게 쓰는 글자
             // 한파·폭염 등 단계에 안 넣는 특보만 있을 때 '발효 특보 없음'이라 쓰면 사실과 다르다
             short: (best.rank ? shortOf(best) : none0) + (review ? ' · ⚠ 3단계 발령 검토' : ''),   // 단계 이름 옆 한 줄 기준
             reason: (best.rank ? best.reason : none0) + (review ? ' · ' + review : ''),
             review: review, blink: s.rank >= 4,   // 3단계(자동 조건을 넣었거나 재대본 발령)면 점멸
             hqOwn: hqR.own, room: roomOut(room.rank, room.reason) };
  }
  window.cbStage.STAGES = STAGES;
  window.cbStage.TABLE = TABLE;
  window.cbStage.KIND = KIND;
  window.cbStage.LEVEL = LEVEL;
  window.cbStage.TARGETS = TARGETS;
  /* 미리 보기(관리자 화면) — 가상 숫자 v 와 규칙 R 로 계산 */
  window.cbStage.preview = function (v, R) { return fromFacts(factsFromCounts(v), [], R); };
  window.cbStage.sigunCount = function () { return sigunList().length; };

  /* ── 재대본 비상단계 직접 지정(2026-11-16) ── 서버(.data/stage.json)를 1분마다 읽는다. 24시간 지나면 서버·화면 모두 자동으로.
     set(rank) — 0 평상 ~ 4 3단계, null 이면 자동. 바뀌면 상황실(wallReapply)·다른 화면(cbstage 이벤트)이 다시 그린다 */
  window.cbStageOv = (function () {
    var v = null, key = '';
    function active() { return (v && typeof v.rank === 'number' && (!v.until || v.until * 1000 > Date.now())) ? v : null; }
    function changed() {
      try { if (window.wallReapply) window.wallReapply(); } catch (e) {}
      try { window.dispatchEvent(new Event('cbstage')); } catch (e) {}
    }
    var rkey = '';
    function take(d) { var k = JSON.stringify(d || null); v = d || null; if (k !== key) { key = k; changed(); } }
    /* 비상단계 기준(관리자 '비상단계 · 근무' 탭) — 바뀌면 다시 그린다. 없으면 재대본 표(TABLE) */
    function takeRules(R) { var k = JSON.stringify(R || null); if (k !== rkey) { rkey = k; window.cbStageRules = R || null; changed(); } }
    function load() {
      return fetch('api/feedback?stage=1', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) { if (j && j.ok) { if ('rules' in j) takeRules(j.rules); take(j.stage); } return j; }).catch(function () { return null; });
    }
    /* 지정 번호 확인만 — 지정 창의 [확인]. 맞아야 단계 단추가 켜진다(2026-11-16) */
    function check(pin) {
      return fetch('api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'cbweather' },
        body: JSON.stringify({ action: 'stage_pin_check', pin: pin || '' }) })
        .then(function (r) { return r.json().catch(function () { return { ok: false, err: '서버 응답 오류(' + r.status + ')' }; }); })
        .then(function (j) {
          if (j && !j.ok && /내용을 적어/.test(j.err || '')) j.err = '서버가 아직 예전 버전입니다 — 서버.bat 을 껐다 켠 뒤 다시 하세요';
          return j;
        }).catch(function () { return { ok: false, err: '서버에 연결하지 못했습니다' }; });
    }
    /* pin = 지정 번호(서버 PC 는 없어도 된다) · duty = 직접 쓴 비상근무 [{who,what}] 또는 null(기준표대로) */
    function set(rank, pin, duty) {
      return fetch('api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'cbweather' },
        body: JSON.stringify({ action: 'stage_set', rank: rank, pin: pin || '', duty: duty || null }) })
        .then(function (r) { return r.json().catch(function () { return { ok: false, err: '서버 응답 오류(' + r.status + ')' }; }); })
        .then(function (j) {
          if (j && j.ok) { take(j.stage); return j; }
          var err = (j && j.err) || '저장하지 못했습니다';
          if (/내용을 적어/.test(err)) err = '서버가 아직 예전 버전입니다 — 서버.bat 을 껐다 켠 뒤 다시 하세요';
          return { ok: false, err: err };
        }).catch(function () { return { ok: false, err: '서버에 연결하지 못했습니다' }; });
    }
    if (typeof fetch === 'function' && !window.CB_STAGE_NOAUTO) { load(); setInterval(load, 60000); }
    return { active: active, load: load, set: set, check: check, takeRules: takeRules };
  })();

  /* ❄️ 대설·결빙 카드 판정 — 눈이 오거나 올 때 '침수·수난 출동' 자리에 대신 띄운다(지도·상황실 공통).
     warnTypes: 그 관서 특보 종류들 · hourly: 단기예보 시간별 [{snow(cm), weather}] · fcst6: 초단기예보 [{pty_txt|pty}]
     단계: 대설경보 또는 24시간 예상 적설 20cm↑ = 경계 · 대설주의보 또는 5cm↑ = 주의 · 눈 예보만 = 관심
     (5·20cm 는 대설주의보·경보 기준). 눈 기미가 없으면 null → 침수·수난 카드를 그대로 쓴다. */
  window.cbSnow = function (warnTypes, hourly, fcst6) {
    var T = (warnTypes || []).join(' '), hw = (hourly || []).slice(0, 24);
    var sum = hw.reduce(function (a, h) { var v = +(h && h.snow); return a + (isNaN(v) ? 0 : v); }, 0);
    var SN = /눈|진눈깨비/;
    var snowy = /대설/.test(T) || sum > 0 || hw.some(function (h) { return h && SN.test(String(h.weather || '')); })
              || (fcst6 || []).some(function (f) { return f && SN.test(String(f.pty_txt || f.pty || '')); });
    if (!snowy) return null;
    var k, lv;
    if (/대설경보/.test(T) || sum >= 20) { k = 2; lv = '경계'; }
    else if (/대설주의보/.test(T) || sum >= 5) { k = 1; lv = '주의'; }
    else { k = 1; lv = '관심'; }
    var w = /대설경보/.test(T) ? '대설경보 발효 · ' : (/대설주의보/.test(T) ? '대설주의보 발효 · ' : '');
    var amt = sum > 0 ? ('24시간 예상 적설 ' + (sum < 1 ? '1cm 미만' : (Math.round(sum * 10) / 10) + 'cm')) : '눈 예보';
    return { k: k, level: lv, note: w + amt + ' · 제설·빙판·고립 유의' };
  };

  /* 다음 아침(03~09시) 최저 — 시간별 [{hour:'6시', temp}] 에서. { t, tomorrow:자정을 넘긴 뒤의 아침인가 } */
  window.cbMorningLow = function (hourly) {
    var best = null, tomorrow = false, crossed = false, prev = null;
    (hourly || []).slice(0, 24).some(function (h) {
      var n = parseInt(h && h.hour, 10), t = h ? +h.temp : NaN;
      if (isNaN(n)) return false;
      if (prev !== null && n < prev) crossed = true;
      prev = n;
      if (n >= 3 && n <= 9) { if (!isNaN(t) && (best === null || t < best)) { best = t; tomorrow = crossed; } }
      else if (best !== null && n > 9) return true;
      return false;
    });
    return { t: best, tomorrow: tomorrow };
  };

  /* 폭우 안전장치 — 관서 강수는 대표 관측소 값이라 관할 다른 지점의 집중호우가 안 보인다.
     화면에 쓰는 지점(aws.stn) 말고 다른 지점이 집중호우 기준을 넘으면 돌려준다. 심한 순.
     기준: 1시간 50mm·12시간 180mm 이상 경계, 1시간 30mm·12시간 110mm 이상 주의(자동 위험구역과 같다).
     aws: data.aws[관서] · meta: REGION_CONF.awsStations[관서] [{stn,name,lat,lon}] */
  window.cbRainHot = function (aws, meta) {
    var st = (aws && aws.stations) || {}, out = [];
    (meta || []).forEach(function (m) {
      var o = st[m.stn]; if (!o || m.stn === aws.stn) return;
      var h1 = +o.rn60 || 0, h12 = +o.rn12h || 0;
      var k = (h1 >= 50 || h12 >= 180) ? 2 : ((h1 >= 30 || h12 >= 110) ? 1 : 0);
      if (k) out.push({ stn: m.stn, name: m.name, lat: m.lat, lon: m.lon, h1: h1, h12: h12, k: k, level: k === 2 ? '경계' : '주의' });
    });
    return out.sort(function (a, b) { return (b.k - a.k) || (b.h1 - a.h1) || (b.h12 - a.h12); });
  };
})();

/* 일출·일몰 — 한국천문연구원 공식값(서버가 하루 한 번 받아 data.js 의 sun)을 먼저 쓰고,
   없거나 날짜가 다르면 같은 관서(시·군청) 좌표로 계산한다(NOAA 간이식, 정밀 계산과 1분 이내).
   window.cbSun(date, 관서명) → { rise:'06:52', set:'17:35', riseMin, setMin, src:'kasi'|'calc' } */
(function () {
  var LL = {
    '청주동부': [36.642, 127.489], '청주서부': [36.642, 127.489], '충주': [36.991, 127.926], '제천': [37.132, 128.191],
    '보은': [36.489, 127.729], '옥천': [36.306, 127.571], '영동': [36.175, 127.783], '증평': [36.785, 127.581],
    '진천': [36.855, 127.436], '괴산': [36.815, 127.787], '음성': [36.940, 127.690], '단양': [36.985, 128.366]
  };
  function calc(date, lat, lng, rise) {
    var rad = Math.PI / 180, deg = 180 / Math.PI, y = date.getFullYear(), mo = date.getMonth(), da = date.getDate();
    var N = Math.round((Date.UTC(y, mo, da) - Date.UTC(y, 0, 0)) / 86400000), lngHour = lng / 15;
    var t = rise ? N + ((6 - lngHour) / 24) : N + ((18 - lngHour) / 24);
    var M = 0.9856 * t - 3.289;
    var L = M + 1.916 * Math.sin(rad * M) + 0.020 * Math.sin(rad * 2 * M) + 282.634; L = ((L % 360) + 360) % 360;
    var RA = deg * Math.atan(0.91764 * Math.tan(rad * L)); RA = ((RA % 360) + 360) % 360;
    RA = (RA + (Math.floor(L / 90) * 90 - Math.floor(RA / 90) * 90)) / 15;
    var sinDec = 0.39782 * Math.sin(rad * L), cosDec = Math.cos(Math.asin(sinDec));
    var cosH = (Math.cos(rad * 90.833) - sinDec * Math.sin(rad * lat)) / (cosDec * Math.cos(rad * lat));
    if (cosH > 1 || cosH < -1) return null;
    var H = (rise ? 360 - deg * Math.acos(cosH) : deg * Math.acos(cosH)) / 15;
    var UT = (((H + RA - 0.06571 * t - 6.622 - lngHour) % 24) + 24) % 24;
    return Math.round((((UT + 9) % 24) + 24) % 24 * 60);   // 한국 표준시(서머타임 없음)
  }
  function hm(m) { return m == null ? '--:--' : (String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0')); }
  function toMin(t) { var m = /^(\d\d):(\d\d)$/.exec(String(t || '')); return m ? (+m[1]) * 60 + (+m[2]) : null; }
  window.cbSun = function (date, name) {
    var d = date || new Date();
    var ymd = d.getFullYear() + String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0');
    var K = (window.DASHBOARD_DATA || {}).sun;
    var o = K && K.date === ymd && K.by && (K.by[name] || K.by['청주동부']);
    if (o && toMin(o.rise) != null && toMin(o.set) != null) {
      return { rise: o.rise, set: o.set, riseMin: toMin(o.rise), setMin: toMin(o.set), src: 'kasi' };
    }
    var ll = LL[name] || LL['청주동부'];
    var r = calc(d, ll[0], ll[1], true), s = calc(d, ll[0], ll[1], false);
    return { rise: hm(r), set: hm(s), riseMin: r, setMin: s, src: 'calc' };
  };
})();
