/* 비상근무 기준표(2026-11-16) — 상황실 '비상근무' 칸과 관리자 페이지 '비상단계 · 근무' 탭이 같이 쓴다.
   기본값 = 「기상특보 단계별 비상근무체계(충청북도 재난안전대책본부)」의 소방본부·119종합상황실 칸.
   관리자 페이지에서 고치면 서버(.data/duty.json — tools/feedback.py)에 저장되고, 상황실 화면은 5분마다 다시 읽는다.
   서버에 저장본이 없거나 읽지 못하면 아래 기본값.
   칸: s1 준비 · s2 1단계 · s3 2단계 · s4 3단계 (= 재대본 비상단계 rank 1~4) · snow 1단계가 대설주의보로 난 경우(비우면 1단계 그대로) */
(function () {
  var DEFAULT = { rows: [
    { who: '소방본부',      s1: '현행 유지',     s2: '전직원 상황공유',     s3: '대책상황실 1개조',   s4: '대책상황실 2개조', snow: '' },
    { who: '119종합상황실', s1: '비상소집 예령', s2: '다음근무팀 1/5 이상', s3: '다음근무팀 1/2 이상', s4: '1개팀 이상',       snow: '비상소집 예령' }
  ] };
  var cur = null;
  function load() {
    if (!window.fetch) return;
    fetch('api/feedback?duty=1', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { if (j && j.ok) cur = (j.duty && j.duty.rows && j.duty.rows.length) ? j.duty : null; })
      .catch(function () {});
  }
  window.cbDuty = {
    DEFAULT: DEFAULT,
    STAGES: ['준비', '1단계', '2단계', '3단계'],
    get: function () { return cur || DEFAULT; },
    set: function (d) { cur = (d && d.rows && d.rows.length) ? d : null; },
    load: load
  };
  if (!window.CB_DUTY_NOAUTO) { load(); setInterval(load, 5 * 60 * 1000); }
})();
