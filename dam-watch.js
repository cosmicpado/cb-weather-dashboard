/* 댐 방류 감시 — 충북에 영향을 주는 댐의 하류 정보와 '수문 방류 수준·급증' 판단 (2026-11-16).
   재해별 집중 감시(호우 탭) '댐 방류' 칸과 하천 상세 팝업(river-popup.js)이 같이 쓴다.

   방류량 = 홍수통제소 오픈API 총 방류량(tototf). 방류 '승인' 문구는 공식 API가 없어 넣지 않았다.
   판단은 시간 단위 값(dam_info.out_h · out_d3)으로 한다 — 10분 값은 발전 방류가 켜졌다 꺼져 출렁인다
   (충주댐 10분 0.4㎥/s ↔ 1시간 124㎥/s).

   gate  = 평소 발전 방류를 넘는 수준. 이 값 이상이면 '수문 방류 수준'(주황).
           충주댐 1,000 — 2022.8 1,500→2,000㎥/s 증량 때 하상도로·둔치 통제
           괴산댐 200 — 홍수기 승인 '초기 수문방류 최대 200㎥/s 이내'(2026.6.20)
           용담댐 300 — 2020.8.7 약 300㎥/s 방류 뒤 하루 만에 2,900㎥/s 로 늘림
           대청댐 500 · 충주조정지댐 1,000 — 평소 발전·조정 방류(수십~수백㎥/s) 위
   급증  = gate 이상이면서 3시간 사이 gate 의 절반 이상 늘어남(빨강).
   과거 사례는 언론 보도로 확인한 것만 적는다. 수치는 보도마다 조금씩 다르다. */
(function(){
  var W = {
    '3001110': { name:'용담댐', river:'금강', gate:300,
      down:['영동','옥천'], path:'금산 → 영동 양산·양강·심천면 → 옥천 동이·이원면 → 대청호',
      gauges:['3004690','3006690','3006680'],
      past:'2020.8.8 하루 만에 약 300 → 2,900㎥/s 로 늘려 방류 — 영동 양산·양강·심천면 침수(329명 대피), 옥천 동이·이원면 주택·농경지 침수' },
    '1004310': { name:'괴산댐', river:'달천', gate:200,
      down:['괴산','충주'], path:'괴산 칠성면(외사·송동리) → 괴산읍 → 불정면 목도 → 충주 달천동 → 남한강',
      gauges:['1004693'],
      past:'2023.7.15 댐 월류(06:30~09:22), 최대 약 2,700㎥/s 방류 — 하류 주민 1,100여 명 대피' },
    '1003110': { name:'충주댐', river:'남한강', gate:1000,
      down:['충주'], path:'충주 시내(탄금대) → 충주조정지댐 → 목계 → 여주',
      gauges:['1005640'],
      past:'2022.8 방류량 1,500 → 2,000㎥/s 증량 때 충북 하상도로·둔치 주차장 통제' },
    '1003611': { name:'충주조정지댐', river:'남한강', gate:1000,
      down:['충주'], path:'충주 목계 → 여주(경기)', gauges:['1005640'], past:'' },
    '3008110': { name:'대청댐', river:'금강', gate:500,
      down:['청주서부'], path:'대청댐 아래 금강 — 청주 현도면 · 대전 신탄진 · 세종 부강', gauges:[], past:'' }
  };
  function num(v){ return (v==null || v==='' || isNaN(v)) ? null : +v; }
  /* 강(하천) 1건 → 판단 결과. 표에 없는 댐이면 null */
  function judge(r){
    var w = W[String(r && r.code)]; if(!w) return null;
    var di = r.dam_info || r.dam || {};
    var out = num(di.out_h); if(out==null) out = num(di.total_outflow);
    var d3 = num(di.out_d3), d1 = num(di.out_d1);
    var state = 'normal';
    if(out!=null && out >= w.gate) state = (d3!=null && d3 >= w.gate*0.5) ? 'surge' : 'gate';
    var hist = (di.out_hist||[]).map(function(p){ return num(p && p.value); }).filter(function(v){ return v!=null; });
    return { code:String(r.code), name:w.name, river:w.river, gate:w.gate, down:w.down, path:w.path, gauges:w.gauges, past:w.past,
             out:out, d1:d1, d3:d3, inflow:num(di.inflow), hist:hist, state:state,
             label: state==='surge' ? '방류량 급증' : state==='gate' ? '수문 방류 수준' : '평상' };
  }
  window.cbDamWatch = {
    TABLE: W,
    judge: judge,
    /* 자료(rivers) 중 감시 댐만, 급증 → 수문 방류 → 평상 순 */
    list: function(rivers){
      /* 급증 → 수문 방류 수준 → 평상. 같은 단계 안에서는 위 표 순서(충북 영향이 큰 댐 먼저) */
      var rk = {surge:0, gate:1, normal:2}, seen = {}, ord = Object.keys(W);
      return (rivers||[]).map(judge).filter(function(x){ if(!x || seen[x.code]) return false; seen[x.code]=1; return true; })
        .sort(function(a,b){ return rk[a.state]-rk[b.state] || ord.indexOf(a.code)-ord.indexOf(b.code); });
    }
  };
})();
