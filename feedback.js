/* 💬 의견 보내기 — 종합 현황(지도.html)·119종합상황실(상황실.html) 공용.
   cbFeedback.open({page:'화면 이름'}) 으로 입력창을 띄우고 /api/feedback 에 보낸다(서버: tools/feedback.py).
   보던 화면·관서는 붙이지 않는다(2026-11-12 — 보던 관서가 의견 쓴 사람 관서처럼 읽혀 헷갈렸다).
   받은 의견은 관리자.html 에서 본다. */
(function () {
  var box = null, KEY = 'cbFeedbackWho';
  function el(tag, css, txt) { var e = document.createElement(tag); if (css) e.style.cssText = css; if (txt != null) e.textContent = txt; return e; }
  try { localStorage.removeItem(KEY); } catch (e) {}   // 예전에 기억해 둔 이름도 지운다

  function close() { if (box) { box.remove(); box = null; document.removeEventListener('keydown', onKey, true); } }
  function onKey(e) { if (e.key === 'Escape') { e.stopPropagation(); close(); } }

  function open(opt) {
    opt = opt || {};
    close();
    var page = opt.page || document.title || location.pathname;

    box = el('div', 'position:fixed;inset:0;z-index:2147483000;background:rgba(8,12,20,.55);display:flex;align-items:center;justify-content:center;padding:16px;font-family:Pretendard,system-ui,-apple-system,"Malgun Gothic",sans-serif;');
    box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true'); box.setAttribute('aria-label', '의견 보내기');
    box.addEventListener('mousedown', function (e) { if (e.target === box) close(); });
    var card = el('div', 'width:min(520px,100%);background:#fff;color:#1b2333;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.35);padding:22px 22px 18px;display:flex;flex-direction:column;gap:12px;');
    box.appendChild(card);

    var head = el('div', 'display:flex;align-items:center;gap:10px;');
    head.appendChild(el('div', 'font-size:18px;font-weight:800;letter-spacing:-.3px;', '💬 의견 보내기'));
    var x = el('button', 'margin-left:auto;width:32px;height:32px;border-radius:9px;border:1px solid #d5dbe6;background:#f4f6fa;color:#4a5568;font-size:16px;cursor:pointer;', '✕');
    x.setAttribute('aria-label', '닫기'); x.onclick = close; head.appendChild(x);
    card.appendChild(head);

    card.appendChild(el('div', 'font-size:13px;color:#5a6578;line-height:1.5;white-space:pre-line;',   /* pre-line: 글 안의 \n 에서 줄을 바꾼다 */
      '불편한 점, 틀린 값, 기능 제안, 새로 있었으면 하는 사이트 등을 자유롭게 적어 주세요.\n개발 담당자가 확인하고, 반영되면 사용설명서 공지사항으로 알려 드립니다.'));

    /* 구분 — 반드시 하나 고른다 */
    var KINDS = [['오류', '틀린 값·안 되는 기능'], ['기능 제안', '이 정보도 있었으면'], ['새 사이트 제안', '다른 업무용 사이트'], ['기타', '']];
    var kind = '', kbtns = [];
    var krow = el('div', 'display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;');
    KINDS.forEach(function (k) {
      var b = el('button', 'min-height:46px;padding:5px 4px;border-radius:10px;border:1.5px solid #c9d1de;background:#fff;color:#1b2333;cursor:pointer;font-family:inherit;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;');
      b.type = 'button'; b.setAttribute('aria-pressed', 'false');
      b.appendChild(el('span', 'font-size:14px;font-weight:800;', k[0]));
      if (k[1]) b.appendChild(el('span', 'font-size:10.5px;color:#7a8597;', k[1]));
      b.onclick = function () { kind = k[0]; kbtns.forEach(function (x) { var on = x === b; x.setAttribute('aria-pressed', on ? 'true' : 'false');
        x.style.borderColor = on ? '#2563eb' : '#c9d1de'; x.style.background = on ? '#eef3ff' : '#fff'; x.style.color = on ? '#1d4ed8' : '#1b2333'; });
        msg.textContent = ''; siteMode(kind === '새 사이트 제안'); };
      kbtns.push(b); krow.appendChild(b);
    });
    card.appendChild(krow);


    var ta = el('textarea', 'width:100%;box-sizing:border-box;min-height:140px;resize:vertical;border:1px solid #c9d1de;border-radius:10px;padding:10px 12px;font-size:15px;line-height:1.5;font-family:inherit;color:#1b2333;background:#fff;outline:none;');
    ta.maxLength = 2000; ta.placeholder = '예) 기온이 실제와 달라요 / 상황실 레이더를 더 크게 / 출동 차량 현황 사이트가 있으면 좋겠어요';
    var cnt = el('div', 'font-size:11.5px;color:#8a94a6;text-align:right;margin-top:-6px;', '0 / 2000');
    ta.oninput = function () { cnt.textContent = ta.value.length + ' / 2000'; };
    card.appendChild(ta); card.appendChild(cnt);

    var who = el('input', 'width:100%;box-sizing:border-box;border:1px solid #c9d1de;border-radius:10px;padding:9px 12px;font-size:14px;font-family:inherit;color:#1b2333;background:#fff;outline:none;');
    /* 이름은 기억하지 않는다(2026-11-10) — 상황실처럼 여러 사람이 쓰는 PC에서 앞사람 이름이 다음 의견에 붙었다 */
    who.maxLength = 40; who.placeholder = '부서·이름 (비워 두면 익명)'; who.value = '';
    card.appendChild(who);

    /* 새 사이트 제안 — 구체적으로 받으려고 항목 양식을 채워 주고, 부서·이름은 꼭 받는다(되물어 볼 수 있게).
       같은 규칙을 서버(tools/feedback.py)도 다시 확인한다. */
    var SITE_FORM = '① 어떤 사이트가 필요한가요? \n\n② 누가, 언제 쓰나요?\n\n③ 지금은 어떻게 하고 있고, 무엇이 불편한가요?\n\n④ 꼭 있어야 할 화면·자료는?\n(무엇을 보여 주거나 처리하고 싶은지 구체적으로 작성)\n';
    var PH = ta.placeholder;
    function siteMode(on) {
      if (on && !ta.value.trim()) ta.value = SITE_FORM;
      if (!on && ta.value === SITE_FORM) ta.value = '';
      ta.style.minHeight = on ? '230px' : '140px';
      ta.placeholder = on ? '위 네 가지를 구체적으로 적어 주세요' : PH;
      who.placeholder = on ? '부서·이름 (필수)' : '부서·이름 (비워 두면 익명)';
      who.style.borderColor = on ? '#2563eb' : '#c9d1de';
      ta.oninput();
    }
    function answerLen(t) { return t.split('\n').filter(function (l) { return !/^\s*[①②③④]/.test(l); }).join('').replace(/\s/g, '').length; }

    var msg = el('div', 'font-size:13px;min-height:18px;color:#c0392b;');
    var row = el('div', 'display:flex;align-items:center;gap:10px;');
    row.appendChild(msg); msg.style.flex = '1';
    var send = el('button', 'height:40px;padding:0 20px;border-radius:10px;border:none;background:#2563eb;color:#fff;font-size:14.5px;font-weight:800;cursor:pointer;font-family:inherit;', '보내기');
    row.appendChild(send); card.appendChild(row);

    send.onclick = function () {
      var text = ta.value.trim();
      if (!kind) { msg.style.color = '#c0392b'; msg.textContent = '구분(오류·기능 제안·새 사이트 제안·기타)을 골라 주세요'; return; }
      if (text.length < 2) { msg.style.color = '#c0392b'; msg.textContent = '내용을 적어 주세요'; ta.focus(); return; }
      if (kind === '새 사이트 제안') {
        if (!who.value.trim()) { msg.style.color = '#c0392b'; msg.textContent = '새 사이트 제안은 부서·이름을 꼭 적어 주세요'; who.focus(); return; }
        if (answerLen(text) < 30) { msg.style.color = '#c0392b'; msg.textContent = '조금 더 구체적으로 적어 주세요 (항목별 답 30자 이상)'; ta.focus(); return; }
      }
      send.disabled = true; send.style.opacity = '.6'; msg.style.color = '#5a6578'; msg.textContent = '보내는 중…';
      fetch('api/feedback', {
        method: 'POST', cache: 'no-store',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'cbweather' },
        body: JSON.stringify({ kind: kind, text: text, who: who.value.trim() })
      }).then(function (r) {
        return r.json().catch(function () { return { ok: false, err: r.status === 404 || r.status === 405 || r.status === 501 ? '이 서버에서는 아직 의견 받기가 켜져 있지 않습니다' : '서버 응답 오류 (' + r.status + ')' }; });
      }).then(function (j) {
        if (j && j.ok) {
          card.innerHTML = '';
          card.appendChild(el('div', 'font-size:44px;text-align:center;padding-top:6px;', '✅'));
          card.appendChild(el('div', 'font-size:17px;font-weight:800;text-align:center;', '보냈습니다. 고맙습니다!'));
          card.appendChild(el('div', 'font-size:13px;color:#5a6578;text-align:center;', '반영되면 사용설명서 공지사항으로 알려 드립니다.'));
          var ok = el('button', 'align-self:center;margin-top:6px;height:38px;padding:0 22px;border-radius:10px;border:1px solid #c9d1de;background:#f4f6fa;color:#1b2333;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;', '닫기');
          ok.onclick = close; card.appendChild(ok); ok.focus();
          setTimeout(close, 4000);
        } else {
          send.disabled = false; send.style.opacity = '1'; msg.style.color = '#c0392b';
          msg.textContent = (j && j.err) || '보내지 못했습니다';
        }
      }).catch(function () {
        send.disabled = false; send.style.opacity = '1'; msg.style.color = '#c0392b';
        msg.textContent = '서버에 연결하지 못했습니다';
      });
    };

    document.body.appendChild(box);
    document.addEventListener('keydown', onKey, true);
    setTimeout(function () { ta.focus(); }, 30);
  }

  window.cbFeedback = { open: open, close: close };
})();
