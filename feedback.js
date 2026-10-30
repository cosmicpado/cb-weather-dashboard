/* 의견 보내기(오류 신고·기능 개선) — window.cbFeedbackOpen({page, station})
   [보내기] 는 같은 서버의 /api/feedback 로 POST 한다(tools/live_local.py 가 feedback/feedback.jsonl 에 쌓는다).
   접수 기능이 없는 곳(Cloudflare 정적 사이트 등)에서는 실패하므로, 내용을 복사해 메신저로 보내도록 안내한다. */
(function () {
  var box = null;

  function el(tag, css, text) { var e = document.createElement(tag); if (css) e.style.cssText = css; if (text != null) e.textContent = text; return e; }

  function close() { if (box) { box.remove(); box = null; } }

  function summary(f, ctx) {
    return '[상황판 의견] ' + f.kind + '\n' + f.text + '\n— ' + (f.name || '이름 없음') + ' · ' + (ctx.page || '') +
      (ctx.station ? ' · ' + ctx.station : '') + ' · ' + new Date().toLocaleString('ko-KR');
  }

  function copy(text) {
    try { if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text); } catch (e) {}
    var t = el('textarea'); t.value = text; document.body.appendChild(t); t.select();
    try { document.execCommand('copy'); } catch (e) {}
    t.remove(); return Promise.resolve();
  }

  window.cbFeedbackOpen = function (ctx) {
    ctx = ctx || {};
    close();
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    var bg = dark ? '#111a2c' : '#fff', fg = dark ? '#e9eef9' : '#0f1b2d', sub = dark ? '#9fb0cf' : '#4b5a74', bd = dark ? '#354364' : '#d3dbe9';
    box = el('div', 'position:fixed;inset:0;z-index:12000;background:rgba(8,13,24,.45);display:flex;align-items:center;justify-content:center;padding:16px;');
    box.onclick = function (e) { if (e.target === box) close(); };
    var card = el('div', 'width:100%;max-width:440px;background:' + bg + ';color:' + fg + ';border:1px solid ' + bd + ';border-radius:16px;padding:18px 18px 16px;box-shadow:0 18px 50px -12px rgba(0,0,0,.4);font-family:inherit;');
    card.appendChild(el('div', 'font-size:16px;font-weight:900;margin-bottom:4px;', '💬 의견 보내기'));
    card.appendChild(el('div', 'font-size:12px;color:' + sub + ';margin-bottom:12px;line-height:1.5;', '오류나 바라는 기능을 적어 주세요. 지금 보던 화면 정보(관서·시각)가 같이 전달됩니다.'));

    var kinds = ['오류 신고', '기능 개선', '기타'], kind = kinds[0];
    var row = el('div', 'display:flex;gap:6px;margin-bottom:10px;');
    var btns = kinds.map(function (k) {
      var b = el('button', '', k); b.type = 'button';
      function paint() { var on = (k === kind); b.style.cssText = 'flex:1;padding:8px 6px;border-radius:9px;font:800 12.5px inherit;font-family:inherit;cursor:pointer;border:1px solid ' + (on ? '#2563eb' : bd) + ';background:' + (on ? '#2563eb' : bg) + ';color:' + (on ? '#fff' : sub) + ';'; }
      b._paint = paint; b.onclick = function () { kind = k; btns.forEach(function (x) { x._paint(); }); };
      paint(); row.appendChild(b); return b;
    });
    card.appendChild(row);

    var ta = el('textarea', 'width:100%;min-height:110px;resize:vertical;box-sizing:border-box;padding:10px 11px;border-radius:10px;border:1px solid ' + bd + ';background:' + bg + ';color:' + fg + ';font:14px/1.5 inherit;font-family:inherit;');
    ta.placeholder = '예) 상황실 화면에서 ○○ 칸 글자가 잘립니다 / ○○ 기능이 있으면 좋겠습니다';
    card.appendChild(ta);
    var nm = el('input', 'width:100%;box-sizing:border-box;margin-top:8px;padding:9px 11px;border-radius:10px;border:1px solid ' + bd + ';background:' + bg + ';color:' + fg + ';font:13px inherit;font-family:inherit;');
    nm.placeholder = '이름·부서 (선택 — 답을 받고 싶으면 적어 주세요)';
    card.appendChild(nm);

    var msg = el('div', 'font-size:12px;margin-top:10px;min-height:16px;line-height:1.5;color:' + sub + ';');
    card.appendChild(msg);
    var act = el('div', 'display:flex;gap:8px;justify-content:flex-end;margin-top:8px;');
    var cancel = el('button', 'padding:9px 14px;border-radius:10px;border:1px solid ' + bd + ';background:' + bg + ';color:' + sub + ';font:800 13px inherit;font-family:inherit;cursor:pointer;', '닫기');
    cancel.type = 'button'; cancel.onclick = close;
    var send = el('button', 'padding:9px 16px;border-radius:10px;border:0;background:#2563eb;color:#fff;font:800 13px inherit;font-family:inherit;cursor:pointer;', '보내기');
    send.type = 'button';
    send.onclick = function () {
      var f = { kind: kind, text: ta.value.trim(), name: nm.value.trim() };
      if (!f.text) { msg.style.color = '#e5484d'; msg.textContent = '내용을 적어 주세요.'; ta.focus(); return; }
      send.disabled = true; send.style.opacity = '.6'; msg.style.color = sub; msg.textContent = '보내는 중…';
      var body = JSON.stringify({ kind: f.kind, text: f.text, name: f.name, page: ctx.page || '', station: ctx.station || '',
        url: location.href, ua: navigator.userAgent, at: new Date().toISOString() });
      fetch('api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body })
        .then(function (r) { if (!r.ok) throw new Error('http ' + r.status); return r.json(); })
        .then(function () {
          card.innerHTML = '';
          card.appendChild(el('div', 'font-size:16px;font-weight:900;margin-bottom:6px;', '✅ 보냈습니다'));
          card.appendChild(el('div', 'font-size:13px;color:' + sub + ';line-height:1.6;', '의견 고맙습니다. 담당자가 확인하겠습니다.'));
          setTimeout(close, 1800);
        })
        .catch(function () {
          // 접수 기능이 없는 곳 — 내용을 복사해 두고 메신저로 보내도록
          //   클립보드 권한 응답을 기다리면 안내가 안 뜰 수 있어 기다리지 않는다
          try { copy(summary(f, ctx)).catch(function () {}); } catch (e) {}
          send.disabled = false; send.style.opacity = '1';
          msg.style.color = '#e0930a';
          msg.textContent = '이 화면에서는 바로 보낼 수 없어 내용을 복사했습니다. 담당자에게 메신저로 붙여넣어 보내 주세요.';
        });
    };
    act.appendChild(cancel); act.appendChild(send); card.appendChild(act);
    box.appendChild(card); document.body.appendChild(box);
    setTimeout(function () { ta.focus(); }, 30);
  };
})();
