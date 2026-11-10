/* 📢 공지사항 — 사용설명서(도움말.html) '공지사항' 탭에 나온다.
   새 공지는 맨 위에 하나 추가하면 된다(id 는 겹치지 않게, 날짜-순번).
     kind : '새 기능' | '개선' | '오류 수정' | '안내'
     body : 그냥 글(줄바꿈 \n 그대로 보임). from 은 의견을 받아 고친 경우 '의견 반영' 처럼 적는다(선택).
   안 본 공지가 있으면 각 화면의 설명서 버튼(❓·?)에 빨간 점이 붙고, 누르면 공지사항 탭으로 바로 열린다.
   본 공지는 이 PC 브라우저에 기억한다(cbNoticeSeen). */
window.CB_NOTICES = [
  { id: '2026-11-10-2', date: '2026-11-10', kind: '새 기능', title: '💬 의견 보내기가 생겼습니다',
    body: '종합 현황 맨 위 오른쪽, 119종합상황실 왼쪽 위의 💬 버튼으로 의견을 보낼 수 있습니다.\n' +
          '보내 주신 의견은 개발 담당자가 확인하고, 반영되면 이 공지사항으로 알려 드립니다.' }
];

(function () {
  var L = window.CB_NOTICES || [], latest = L.length ? L[0].id : '';
  function seen() { try { return localStorage.getItem('cbNoticeSeen') || ''; } catch (e) { return ''; } }
  window.cbNotices = {
    list: L,
    unseen: function () { var s = seen(); return L.filter(function (n) { return n.id > s; }).length; },
    markSeen: function () { try { if (latest) localStorage.setItem('cbNoticeSeen', latest); } catch (e) {} }
  };

  /* 설명서 버튼에 빨간 점 + 공지사항 탭으로 바로 — 화면(React)이 다시 그려 점이 지워져도 다시 붙인다 */
  function deco() {
    var n = window.cbNotices.unseen();
    var links = document.querySelectorAll('a[href^="도움말.html"]');
    for (var i = 0; i < links.length; i++) {
      var a = links[i], dot = a.querySelector('.cb-ndot');
      if (a.closest('#cb-ntoast')) continue;          // 알림 카드의 [보기] 에는 점을 달지 않는다
      if (n && !dot) {
        if (getComputedStyle(a).position === 'static') a.style.position = 'relative';
        dot = document.createElement('span'); dot.className = 'cb-ndot'; dot.setAttribute('aria-hidden', 'true');
        dot.style.cssText = 'position:absolute;top:-4px;right:-4px;width:11px;height:11px;border-radius:50%;background:#ef4444;border:2px solid #fff;box-sizing:border-box;pointer-events:none;';
        a.appendChild(dot);
        if (a.getAttribute('href') === '도움말.html') a.setAttribute('href', '도움말.html#notice');
        if ((a.title || '').indexOf('새 공지') < 0) a.title = (a.title || '') + ' · 새 공지가 있습니다';
      } else if (!n && dot) { dot.remove(); }
    }
  }
  /* 새 공지 알림 카드 — 종합 현황(지도.html)만 부른다. 상황실 전광판은 누를 사람이 없어 화면을 가리므로 띄우지 않는다.
     [보기] → 공지사항 탭(본 것으로 기억) · [닫기] → 이 창(탭)에서만 숨김, 공지를 볼 때까지 다음에 열면 다시 뜬다. */
  window.cbNotices.toast = function () {
    function run() {
      if (!window.cbNotices.unseen() || document.getElementById('cb-ntoast')) return;
      try { if (localStorage.getItem('cbNoticeToastOff') === '1') return; } catch (e) {}   // 알림 설정에서 끔
      try { if (sessionStorage.getItem('cbNoticeToastClosed') === latest) return; } catch (e) {}
      var n = window.cbNotices.unseen(), top = L[0];
      var c = document.createElement('div'); c.id = 'cb-ntoast'; c.setAttribute('role', 'status');
      c.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:9000;width:min(360px,calc(100vw - 36px));box-sizing:border-box;' +
        'background:var(--surface,#fff);color:var(--ink,#0f1b2d);border:1px solid var(--border2,#d3dbe9);border-left:4px solid var(--brand,#1d4ed8);' +
        'border-radius:12px;box-shadow:0 12px 32px rgba(15,27,45,.22);padding:13px 14px 12px;font-family:inherit;';
      var h = document.createElement('div'); h.style.cssText = 'font-size:12px;font-weight:800;color:var(--brand,#1d4ed8);margin-bottom:3px;';
      h.textContent = '📢 새 공지' + (n > 1 ? ' ' + n + '건' : '');
      var t = document.createElement('div'); t.style.cssText = 'font-size:14px;font-weight:800;line-height:1.4;margin-bottom:10px;';
      t.textContent = top.title || '';
      var row = document.createElement('div'); row.style.cssText = 'display:flex;gap:6px;justify-content:flex-end;';
      var bs = 'height:32px;padding:0 14px;border-radius:8px;font:inherit;font-size:13px;font-weight:800;cursor:pointer;';
      var close = document.createElement('button'); close.type = 'button'; close.textContent = '닫기';
      close.style.cssText = bs + 'border:1px solid var(--border2,#d3dbe9);background:var(--surface2,#f3f7fc);color:var(--ink2,#4b5a74);';
      close.onclick = function () { try { sessionStorage.setItem('cbNoticeToastClosed', latest); } catch (e) {} c.remove(); };
      var go = document.createElement('a'); go.href = '도움말.html#notice'; go.textContent = '보기';
      go.style.cssText = bs + 'display:inline-flex;align-items:center;border:1px solid var(--brand,#1d4ed8);background:var(--brand,#1d4ed8);color:#fff;text-decoration:none;';
      row.appendChild(close); row.appendChild(go);
      c.appendChild(h); c.appendChild(t); c.appendChild(row);
      document.body.appendChild(c);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(run, 1500); });
    else setTimeout(run, 1500);
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', deco); else deco();
  setInterval(deco, 3000);
})();
