/* 선 아이콘 한 벌 — 화면 곳곳의 색 이모지를 대신한다.
   모양은 Lucide(ISC 라이선스, lucide.dev) 아이콘을 본떠 24×24 선으로 그렸다. 색은 글자색(currentColor)을 따른다.
   쓰는 법
   · 문자열 HTML:  cbIcon('bell')            → '<svg class="cbi" …>…</svg>'
                   cbIcon('alert', 'var(--warn)')  → 색을 따로 줄 때
   · React:        cbIconEl('bell')          → <span> 안에 그린 아이콘
   날씨 예보 그림(해·구름·비)은 종합 화면의 wxSvg 를 쓴다. 이 파일은 메뉴·제목·알림 줄의 아이콘만 다룬다. */
(function () {
  var P = {
    alert: '<path d="m21.7 18-8-14a2 2 0 0 0-3.5 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4M12 17h.01"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a2 2 0 0 0 3.4 0"/>',
    book: '<path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/>',
    chart: '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 6-6"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-6.4A8 8 0 1 1 21 12Z"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    clip: '<rect x="8" y="2.5" width="8" height="4" rx="1"/><path d="M16 4.5h2a2 2 0 0 1 2 2V20a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2h2"/>',
    cloud: '<path d="M17.5 19H9a7 7 0 1 1 6.7-9h1.8a4.5 4.5 0 0 1 0 9Z"/>',
    compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>',
    doc: '<path d="M14 2.5H6a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8.5Z"/><path d="M14 2.5v6h6M8 13h8M8 17h5"/>',
    drop: '<path d="M12 21.5a6.5 6.5 0 0 0 6.5-6.5c0-1.9-1-3.6-2.8-5.1S12.5 6.3 12 3.5c-.5 2.8-1.9 4.9-3.7 6.4S5.5 13.1 5.5 15a6.5 6.5 0 0 0 6.5 6.5Z"/>',
    flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.4-.5-2-1-3-1.1-2.1-.2-4 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.2.4-2.3 1-3a2.5 2.5 0 0 0 2.5 2.5Z"/>',
    gust: '<path d="M3 8h10a3 3 0 1 0-3-3"/><path d="M3 12h15a3 3 0 1 1-3 3"/><path d="M3 16h6"/>',
    haze: '<path d="M17.5 15H9a6 6 0 1 1 5.7-8h1.8a4 4 0 0 1 1 7.9"/><path d="M4 19h10M8 22h12"/>',
    mail: '<rect x="2.5" y="4.5" width="19" height="15" rx="2"/><path d="m22 7-10 6L2 7"/>',
    mapPin: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    megaphone: '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    pin: '<path d="M12 17v5"/><path d="M9 10.8V4h6v6.8l2.5 3.2h-11z"/>',
    pulse: '<path d="M22 12h-4l-3 8L9 4l-3 8H2"/>',
    radar: '<path d="M19.1 4.9A10 10 0 1 0 22 12"/><path d="M16.2 7.8A6 6 0 1 0 18 12"/><circle cx="12" cy="12" r="2"/><path d="m13.4 10.6 6-6"/>',
    rain: '<path d="M4 14.9A7 7 0 1 1 15.7 8h1.8a4.5 4.5 0 0 1 2.5 8.2"/><path d="M16 14v6M8 14v6M12 16v6"/>',
    satellite: '<path d="M13 7 9 3 5 7l4 4"/><path d="m17 11 4 4-4 4-4-4"/><path d="m8 12 4 4 6-6-4-4Z"/><path d="m16 8 3-3"/><path d="M9 21a6 6 0 0 0-6-6"/>',
    siren: '<path d="M7 18v-6a5 5 0 0 1 10 0v6"/><path d="M4 21v-1a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v1z"/><path d="M12 2v1M4.9 4.9l.7.7M19.1 4.9l-.7.7M2 12h1M21 12h1"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    thermo: '<path d="M14 4v10.5a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>',
    typhoon: '<circle cx="12" cy="12" r="2.5"/><path d="M12 2.5C7 2.5 4 6 4 9.5M12 21.5c5 0 8-3.5 8-7M21.5 12c0-5-3.5-8-7-8M2.5 12c0 5 3.5 8 7 8"/>',
    umbrella: '<path d="M22 12a10 10 0 0 0-20 0Z"/><path d="M12 12v7a2 2 0 0 0 4 0"/><path d="M12 2v1"/>',
    video: '<path d="m16 13 5.2 3.5a.5.5 0 0 0 .8-.4V7.9a.5.5 0 0 0-.8-.4L16 11"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
    waves: '<path d="M2 7c1.5 1 3 1 4.5 0s3-1 4.5 0 3 1 4.5 0 3-1 4.5 0"/><path d="M2 12c1.5 1 3 1 4.5 0s3-1 4.5 0 3 1 4.5 0 3-1 4.5 0"/><path d="M2 17c1.5 1 3 1 4.5 0s3-1 4.5 0 3 1 4.5 0 3-1 4.5 0"/>',
    wind: '<path d="M17.7 7.7A2.5 2.5 0 1 1 19.5 12H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/>',
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z"/>'
  };

  var css = document.createElement('style');
  css.textContent = '.cbi{display:inline-block;width:1.1em;height:1.1em;vertical-align:-.17em;margin-right:.32em;flex:none;' +
    'fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}' +
    '.cbi.solo{margin-right:0}';
  (document.head || document.documentElement).appendChild(css);

  /* name: 위 목록의 이름. color: 글자색과 다르게 칠할 때만. solo: 글자 없이 아이콘만 둘 때(오른쪽 여백 없음) */
  window.cbIcon = function (name, color, solo) {
    var p = P[name]; if (!p) return '';
    return '<svg class="cbi' + (solo ? ' solo' : '') + '" viewBox="0 0 24 24" aria-hidden="true"' +
      (color ? ' style="color:' + color + '"' : '') + '>' + p + '</svg>';
  };
  window.cbIconEl = function (name, color, solo) {
    return window.React ? React.createElement('span', { style: { display: 'contents' }, dangerouslySetInnerHTML: { __html: window.cbIcon(name, color, solo) } }) : null;
  };
})();
