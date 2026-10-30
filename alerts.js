/* ===== 새 특보·재난문자 화면 알림 =====
   상황판을 켜 둔 PC에서, 5분 갱신으로 새 기상특보·예비특보·재난문자가 들어오면
     ① 화면 오른쪽 위에 알림 카드  ② 짧은 알림음(경보음 끄기 🔕 면 소리 없음)  ③ 허용했으면 Windows 알림
   을 띄운다. 특보가 풀리면 '해제' 카드(소리 없음). 지도.html·상황실.html 이 같이 쓴다(2026-10-30).

   · 처음 여는 PC는 지금 떠 있는 것들을 '이미 본 것'으로 기억만 하고 알리지 않는다(켜자마자 쏟아지지 않게).
   · 본 것은 이 PC 브라우저에 기억한다(localStorage) — 새로고침해도 같은 특보를 다시 알리지 않는다.
   · 시연 모드의 가짜 상황은 기억하지 않고, 카드에 [시연]을 붙이며 Windows 알림은 보내지 않는다.
   · 특보는 '종류 × 지역' 단위로 센다 — 호우주의보가 증평으로 넓어지면 증평만 새로 알린다. */
(function () {
  'use strict';
  var KEY = 'cbAlertSeen', ASK = 'cbAlertAsk';   // 본 것 기억은 화면마다 따로(지도·상황실을 같은 PC에 켜 둬도 둘 다 알린다)
  var box = null, demoSeen = null;

  function load(pg) { try { return JSON.parse(localStorage.getItem(KEY + ':' + pg) || 'null'); } catch (e) { return null; } }
  function save(pg, o) { try { localStorage.setItem(KEY + ':' + pg, JSON.stringify(o)); } catch (e) {} }
  function muted() { try { return localStorage.getItem('ggMuted') === '1'; } catch (e) { return false; } }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function areas(a) { return String(a || '').split(/\s*,\s*/).map(function (x) { return x.trim(); }).filter(Boolean); }

  /* 지금 떠 있는 것 → {키: 표시정보} */
  function snapshot(warnings, prelim, messages) {
    var cur = {};
    (warnings || []).forEach(function (w) {
      var t = String(w.type || '특보'), sev = /경보/.test(t) || w.level === 'severe';
      areas(w.area).forEach(function (a) { cur['W|' + t + '|' + a] = { kind: 'W', type: t, area: a, sev: sev, time: w.time || '' }; });
    });
    (prelim || []).forEach(function (g) {
      (g.items || []).forEach(function (it) {
        if (!(it.north || it.north_match)) return;
        var a = String(it.area || '').split('(')[0].trim();
        cur['P|' + g.type + '|' + a] = { kind: 'P', type: g.type, area: a, time: it.time || '' };
      });
    });
    (messages || []).forEach(function (m) {
      var k = 'M|' + (m.sender || '') + '|' + (m.time || '') + '|' + String(m.text || '').slice(0, 40);
      cur[k] = { kind: 'M', sender: m.sender || m.region || '재난문자', time: m.time || '', text: m.text || '' };
    });
    return cur;
  }

  /* 같은 종류끼리 묶어 카드 한 장으로: '호우주의보 발효 · 청주동부, 증평' */
  function group(list, verb) {
    var by = {}, out = [];
    list.forEach(function (x) {
      if (x.kind === 'M') { out.push({ icon: '📢', tone: 'msg', title: '새 재난문자 · ' + x.sender, body: x.text, time: x.time }); return; }
      var g = (x.kind === 'W' ? 'W' : 'P') + x.type; (by[g] = by[g] || { x: x, areas: [] }).areas.push(x.area);
    });
    Object.keys(by).forEach(function (g) {
      var o = by[g], x = o.x, rel = verb === '해제';
      out.unshift({ icon: rel ? '✅' : (x.kind === 'P' ? '⚠️' : '🚨'),
        tone: rel ? 'off' : (x.kind === 'P' ? 'pre' : (x.sev ? 'sev' : 'warn')),
        title: x.type + ' ' + (rel ? '해제' : (x.kind === 'P' ? '' : '발효')),
        body: o.areas.join(', '), time: rel ? '' : x.time });
    });
    var RANK = { sev: 0, warn: 1, pre: 2, off: 3, msg: 4 };   // 경보 → 주의보 → 예비특보 → 해제 → 재난문자
    return out.sort(function (a, b) { return RANK[a.tone] - RANK[b.tone]; });
  }

  var TONE = { sev: ['#d42a2f', '#fbe3e3'], warn: ['#ef6c1a', '#ffece0'], pre: ['#e0930a', '#fff6db'], msg: ['#2563eb', '#e8f0ff'], off: ['#16a34a', '#e6f6ec'] };
  function ensureBox() {
    if (box && document.body.contains(box)) return box;
    box = document.createElement('div');
    box.style.cssText = 'position:fixed;top:72px;right:16px;z-index:9600;display:flex;flex-direction:column;gap:8px;width:min(360px,calc(100vw - 32px));pointer-events:none;';
    document.body.appendChild(box); return box;
  }
  function card(c, demo) {
    var t = TONE[c.tone] || TONE.msg, el = document.createElement('div');
    el.style.cssText = 'pointer-events:auto;background:#fff;color:#0f1b2d;border:1px solid ' + t[0] + ';border-left:5px solid ' + t[0] + ';border-radius:12px;box-shadow:0 10px 30px -8px rgba(15,27,45,.35);padding:11px 13px 11px 12px;font:500 13px/1.5 Pretendard,system-ui,sans-serif;animation:cbAlertIn .25s ease-out;';
    el.innerHTML = '<div style="display:flex;align-items:flex-start;gap:9px">'
      + '<div style="font-size:18px;line-height:1.2">' + c.icon + '</div>'
      + '<div style="flex:1;min-width:0"><div style="display:flex;gap:6px;align-items:baseline;flex-wrap:wrap"><b style="font-size:13.5px;color:' + t[0] + '">' + (demo ? '[시연] ' : '') + esc(c.title) + '</b>'
      + (c.time ? '<span style="font-size:11px;color:#6b7891">' + esc(c.time) + '</span>' : '') + '</div>'
      + '<div style="margin-top:3px;color:#33415c;max-height:6em;overflow:auto;word-break:keep-all">' + esc(c.body) + '</div></div>'
      + '<button title="닫기" style="border:0;background:transparent;font-size:16px;line-height:1;color:#6b7891;cursor:pointer;padding:0 2px">×</button></div>';
    el.title = '누르면 닫힙니다'; el.style.cursor = 'pointer';
    el.onclick = function () { el.remove(); };   // 카드 어디를 눌러도 닫힌다(× 포함)
    ensureBox().prepend(el);
    // 해제·예비특보는 2분, 발효·재난문자는 10분 뒤 스스로 닫힌다(그 사이 다른 일을 보다 와도 볼 수 있게)
    setTimeout(function () { el.remove(); }, (c.tone === 'off' || c.tone === 'pre') ? 120000 : 600000);
    while (box.children.length > 6) box.lastChild.remove();
  }
  function chime() {
    if (muted()) return;
    try {
      var AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      var ac = window.__cbAlertAC || (window.__cbAlertAC = new AC()); if (ac.state === 'suspended') ac.resume();
      [[880, 0], [1175, 0.18]].forEach(function (p) {
        var o = ac.createOscillator(), g = ac.createGain(), t0 = ac.currentTime + p[1];
        o.type = 'sine'; o.frequency.value = p[0]; o.connect(g); g.connect(ac.destination);
        g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(0.25, t0 + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.35);
        o.start(t0); o.stop(t0 + 0.4);
      });
    } catch (e) {}
  }
  function osNotify(c) {
    try {
      if (!('Notification' in window) || Notification.permission !== 'granted') return;
      var n = new Notification(c.title, { body: c.body, icon: 'icon.svg', tag: 'cb-' + c.title + c.body.slice(0, 20) });
      n.onclick = function () { try { window.focus(); n.close(); } catch (e) {} };
    } catch (e) {}
  }
  /* 처음 한 번: Windows 알림도 받을지 묻는 작은 띠(닫으면 다시 안 묻는다) */
  function askOnce() {
    try {
      if (!('Notification' in window) || Notification.permission !== 'default' || localStorage.getItem(ASK)) return;
    } catch (e) { return; }
    var el = document.createElement('div');
    el.style.cssText = 'position:fixed;left:16px;bottom:60px;z-index:9600;max-width:min(420px,calc(100vw - 32px));background:#0f1b2d;color:#fff;border-radius:12px;padding:10px 12px;font:600 12.5px/1.5 Pretendard,system-ui,sans-serif;box-shadow:0 10px 30px -8px rgba(0,0,0,.4);display:flex;gap:10px;align-items:center;flex-wrap:wrap;';
    el.innerHTML = '<span>🔔 새 특보·재난문자를 <b>기기 알림</b>(Windows·휴대폰)으로도 받을까요? (화면 팝업은 이미 켜져 있습니다)</span>'
      + '<span style="display:flex;gap:6px;margin-left:auto"><button data-y style="border:0;border-radius:8px;padding:5px 11px;background:#2563eb;color:#fff;font:700 12px inherit;cursor:pointer">켜기</button>'
      + '<button data-n style="border:1px solid #4b5b78;border-radius:8px;padding:5px 11px;background:transparent;color:#cfd7e6;font:700 12px inherit;cursor:pointer">괜찮아요</button></span>';
    el.querySelector('[data-y]').onclick = function () { try { Notification.requestPermission(); localStorage.setItem(ASK, '1'); } catch (e) {} el.remove(); };
    el.querySelector('[data-n]').onclick = function () { try { localStorage.setItem(ASK, '1'); } catch (e) {} el.remove(); };
    document.body.appendChild(el);
  }

  if (!document.getElementById('cbAlertCss')) {
    var st = document.createElement('style'); st.id = 'cbAlertCss';
    st.textContent = '@keyframes cbAlertIn{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}';
    (document.head || document.documentElement).appendChild(st);
  }

  /* 데이터가 바뀔 때마다 부른다. opts.demo = 시연 데이터, opts.page = 'map' | 'wall' (본 것 기억을 화면별로) */
  window.cbAlerts = function (warnings, prelim, messages, opts) {
    opts = opts || {};
    var cur = snapshot(warnings, prelim, messages);
    if (opts.demo) {                                   // 시연: 기억하지 않고 이 창 안에서만 비교
      var prev = demoSeen; demoSeen = cur; if (!prev) return;
      var add = Object.keys(cur).filter(function (k) { return !prev[k]; }).map(function (k) { return cur[k]; });
      var gone = Object.keys(prev).filter(function (k) { return !cur[k] && prev[k].kind !== 'M'; }).map(function (k) { return prev[k]; });
      group(gone, '해제').forEach(function (c) { card(c, true); });
      var cs = group(add, '발효'); cs.slice().reverse().forEach(function (c) { card(c, true); }); if (cs.length) chime();
      return;
    }
    demoSeen = null;
    var pg = opts.page || 'map', seen = load(pg);
    if (!seen) { save(pg, { keys: Object.keys(cur), active: Object.keys(cur).filter(function (k) { return k[0] !== 'M'; }) }); askOnce(); return; }
    var known = {}; (seen.keys || []).forEach(function (k) { known[k] = 1; });
    var newOnes = Object.keys(cur).filter(function (k) { return !known[k]; });
    var active = (seen.active || []);
    var released = active.filter(function (k) { return !cur[k] && k[0] === 'W'; }).map(function (k) { var p = k.split('|'); return { kind: 'W', type: p[1], area: p[2] }; });
    var cards = group(newOnes.map(function (k) { return cur[k]; }), '발효');
    group(released, '해제').forEach(function (c) { card(c, false); });
    cards.slice().reverse().forEach(function (c) { card(c, false); osNotify(c); });
    if (cards.length) chime();
    // 본 것 기억(최근 400개) — 같은 특보가 풀렸다 다시 나면 다시 알리도록, 해제된 특보 키는 지운다
    var keep = (seen.keys || []).filter(function (k) { return !(k[0] !== 'M' && !cur[k]); }).concat(newOnes);
    save(pg, { keys: keep.slice(-400), active: Object.keys(cur).filter(function (k) { return k[0] !== 'M'; }) });
    askOnce();
  };
})();
