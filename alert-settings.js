/* 🔔 알림 설정 창(종합 현황·재해별 집중 감시 공용, 2026-11-20).
   켜고 끄는 값은 이 PC 브라우저에 기억하고(끈 것만 '1'), 두 화면이 같은 값을 쓴다.
     ggMuted 경보음 · ggNoBlink 테두리 점멸 · cbAlertCardsOff 화면 알림 카드 · cbOsNotifyOff Windows 알림 ·
     cbAlertDamOff 댐 방류량 급증 · cbNoticeToastOff 새 공지 알림
   쓰는 법: cbAlertSettings.toggle(누른 단추, 바꾼 뒤 부를 함수) — 단추 아래에 창이 열리고, 바깥을 누르거나 Esc 로 닫힌다. */
(function () {
  var css = document.createElement('style');
  css.textContent =
    '.cbap{position:fixed;z-index:9700;width:min(370px,calc(100vw - 32px));background:var(--card,var(--surface,#fff));color:var(--ink,#101828);border:1px solid var(--border2,#d3dbe9);border-radius:14px;box-shadow:0 18px 40px rgba(16,24,40,.22);padding:8px;font-family:inherit}' +
    '.cbap h4{font-size:15.5px;padding:8px 10px 6px;margin:0}.cbap h4 small{font-size:13px;color:var(--ink3,#5f6d85);font-weight:600;margin-left:6px}' +
    '.cbap .sw{display:flex;align-items:center;gap:12px;padding:10px;border-radius:10px;cursor:pointer}.cbap .sw:hover{background:var(--soft,var(--surface2,#f3f6fa))}' +
    '.cbap .sw b{display:block;font-size:14.5px}.cbap .sw span{display:block;font-size:13px;color:var(--ink3,#5f6d85);margin-top:2px;line-height:1.45}' +
    '.cbap .tg{flex:none;width:44px;height:24px;border-radius:12px;position:relative;background:var(--border2,#d3dbe9)}.cbap .tg::after{content:"";position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:#fff;transition:left .15s}' +
    '.cbap .sw.on .tg{background:var(--brand,#1d4ed8)}.cbap .sw.on .tg::after{left:23px}';
  (document.head || document.documentElement).appendChild(css);

  function off(k) { try { return localStorage.getItem(k) === '1'; } catch (e) { return false; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  var panel = null, anchor = null, after = null;

  function rows() {
    var perm = (typeof Notification !== 'undefined') ? Notification.permission : 'unsupported';
    return [
      { k: 'ggMuted', label: '경보음', desc: '새 특보·재난문자가 들어오거나 3단계일 때 소리', on: !off('ggMuted') },
      { k: 'ggNoBlink', label: '테두리 점멸', desc: '재대본 3단계·관서 경보·하천 경계일 때 화면 가장자리가 붉게 깜빡임(종합 현황)', on: !off('ggNoBlink') },
      { k: 'cbAlertCardsOff', label: '화면 알림 카드', desc: '새 특보·재난문자·해제가 있으면 오른쪽 위에 카드', on: !off('cbAlertCardsOff') },
      { k: 'cbOsNotifyOff', label: 'Windows 알림', os: true, perm: perm,
        desc: perm === 'denied' ? '브라우저에서 막혀 있습니다 — 주소창 왼쪽 자물쇠에서 알림을 허용하세요'
            : perm === 'unsupported' ? '이 브라우저는 지원하지 않습니다'
            : '창을 내려 둬도 화면 오른쪽 아래 Windows 알림',
        on: perm === 'granted' && !off('cbOsNotifyOff') },
      { k: 'cbAlertDamOff', label: '댐 방류량 급증', desc: '괴산·충주·용담·대청댐 방류량이 수문 방류 수준을 넘어 3시간 사이 크게 늘면 카드·소리', on: !off('cbAlertDamOff') },
      { k: 'cbNoticeToastOff', label: '새 공지 알림', desc: '공지사항에 새 글이 올라오면 오른쪽 아래 카드', on: !off('cbNoticeToastOff') }];
  }
  function place() {
    if (!panel || !anchor) return;
    var r = anchor.getBoundingClientRect(), w = panel.offsetWidth || 370;
    panel.style.top = (r.bottom + 8) + 'px';
    panel.style.left = Math.max(12, Math.min(window.innerWidth - w - 12, r.right - w)) + 'px';
  }
  function draw() {
    var R = rows();
    panel.innerHTML = '<h4>알림 설정<small>이 PC에 기억 · 종합 현황·재해별 집중 감시 같이 적용</small></h4>' + R.map(function (x, i) {
      return '<div class="sw' + (x.on ? ' on' : '') + '" data-i="' + i + '" role="switch" aria-checked="' + x.on + '"><div style="flex:1;min-width:0"><b>' + x.label + '</b><span>' + x.desc + '</span></div><i class="tg"></i></div>'; }).join('');
    panel.onclick = function (e) {
      e.stopPropagation();
      var el = e.target.closest && e.target.closest('[data-i]'); if (!el) return;
      var x = R[+el.getAttribute('data-i')];
      if (x.os && x.perm === 'default') { set('cbOsNotifyOff', '0'); try { Notification.requestPermission().then(draw); } catch (e2) {} return; }
      if (x.os && x.perm !== 'granted') return;
      set(x.k, off(x.k) ? '0' : '1');
      draw(); if (after) try { after(x.k); } catch (e3) {}
    };
  }
  function close() { if (panel) { panel.remove(); panel = null; } if (anchor) anchor.setAttribute('aria-expanded', 'false'); }
  window.cbAlertSettings = {
    toggle: function (btn, onChange) {
      if (panel) { close(); return; }
      anchor = btn; after = onChange || null;
      panel = document.createElement('div'); panel.className = 'cbap'; panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', '알림 설정');
      document.body.appendChild(panel); draw(); place();
      if (btn) btn.setAttribute('aria-expanded', 'true');
    },
    close: close
  };
  document.addEventListener('click', function (e) { if (panel && !panel.contains(e.target) && !(anchor && anchor.contains(e.target))) close(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  window.addEventListener('resize', place);
  window.addEventListener('scroll', place, true);
})();
