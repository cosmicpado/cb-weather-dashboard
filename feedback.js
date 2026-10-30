/* 💬 문의 안내 — 기능 개선·오류 신고는 담당 부서로 직접. window.cbFeedbackOpen() */
(function () {
  var CONTACT = { team: '소방정보통신팀', tel: '4944', mail: 'retriever@korea.kr' };
  var box = null;

  function el(tag, css, text) { var e = document.createElement(tag); if (css) e.style.cssText = css; if (text != null) e.textContent = text; return e; }
  function close() { if (box) { box.remove(); box = null; } }

  window.cbFeedbackOpen = function () {
    close();
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    var bg = dark ? '#111a2c' : '#fff', fg = dark ? '#e9eef9' : '#0f1b2d', sub = dark ? '#9fb0cf' : '#4b5a74', bd = dark ? '#354364' : '#d3dbe9', soft = dark ? '#18233b' : '#f3f7fc';
    box = el('div', 'position:fixed;inset:0;z-index:12000;background:rgba(8,13,24,.45);display:flex;align-items:center;justify-content:center;padding:16px;');
    box.onclick = function (e) { if (e.target === box) close(); };
    var card = el('div', 'width:100%;max-width:400px;background:' + bg + ';color:' + fg + ';border:1px solid ' + bd + ';border-radius:16px;padding:18px;box-shadow:0 18px 50px -12px rgba(0,0,0,.4);font-family:inherit;');
    card.appendChild(el('div', 'font-size:16px;font-weight:900;margin-bottom:6px;', '💬 기능 개선·오류 신고'));
    card.appendChild(el('div', 'font-size:13px;color:' + sub + ';line-height:1.6;margin-bottom:12px;', '상황판 오류나 바라는 기능은 아래로 문의해 주세요.'));
    var info = el('div', 'background:' + soft + ';border:1px solid ' + bd + ';border-radius:12px;padding:12px 14px;font-size:14px;line-height:1.9;');
    info.appendChild(el('div', 'font-weight:900;', CONTACT.team));
    info.appendChild(el('div', '', '☎ ' + CONTACT.tel));
    var mail = el('a', 'color:#2563eb;font-weight:800;text-decoration:none;', '✉ ' + CONTACT.mail);
    mail.href = 'mailto:' + CONTACT.mail + '?subject=' + encodeURIComponent('[상황판] 기능 개선·오류 신고');
    var mrow = el('div'); mrow.appendChild(mail); info.appendChild(mrow);
    card.appendChild(info);
    var act = el('div', 'display:flex;justify-content:flex-end;margin-top:14px;');
    var ok = el('button', 'padding:9px 16px;border-radius:10px;border:0;background:#2563eb;color:#fff;font:800 13px inherit;font-family:inherit;cursor:pointer;', '닫기');
    ok.type = 'button'; ok.onclick = close; act.appendChild(ok); card.appendChild(act);
    box.appendChild(card); document.body.appendChild(box);
  };
})();
