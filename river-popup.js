/* 하천 관측소 상세 팝업 본문 — 지도(종합 현황)와 재해별 집중 감시가 같이 쓴다.
   self = 화면 컴포넌트. self.working() 이 { flood:[…] } 를 주고, self.state.riverCctvResume /
   self.setState 로 CCTV 90초 멈춤·계속 보기를 다룬다. 종합.html 에서 2026-11-09 옮겨 옴. */
(function(){
  /* 24시간 그래프 세로 폭의 최소값(m) — 2026-11-16.
     최저~최고로만 잡으면 1cm 잡음도 그래프 높이 전체로 늘어나(괴산댐 132.91↔132.92) 늘 출렁여 보였다.
     기준 U = 관측소의 '관심→경계' 수위 간격(관측소마다 홍수통제소가 정한 값 — 충북 0.6~7.7m).
       안전 U×0.5 · 관심 U×0.25 · 경계 이상 U×0.12  (하한 하천 0.1m · 댐 0.3m)
     → 평상시 잡음(충북 하천 24시간 폭 0~0.15m = 0.5U 의 0~17%)은 거의 평평하고,
       관심·경계에 들면 폭이 좁아져 같은 10cm 상승도 2~4배 크게 보인다. 실제 큰 변화는 원래대로 최저~최고. */
  window.cbRiverMinSpan = function(r){
    const isDam = r.api==='dam' || !!r.dam || !!r.dam_info;
    const w = (r.warning!=null && !isNaN(r.warning)) ? +r.warning : null, d = (r.danger!=null && !isNaN(r.danger)) ? +r.danger : null;
    const U = (w!=null && d!=null && d>w) ? d-w : (isDam ? 3 : (d ? d*0.3 : 1));
    const v = +r.value;
    const lvl = (d!=null && v>=d) ? 2 : (w!=null && v>=w) ? 1 : 0;
    return Math.max(U*[0.5, 0.25, 0.12][lvl], isDam ? 0.3 : 0.1);
  };
  window.cbRiverBody = function(self, r){
    const R=window.React.createElement;
    const d=self.working();
    const _rm=self.RIVER_META||(window.REGION_CONF||{}).riverMeta||{};
    const meta=_rm[r.code]||null;
    const isDam=!!r.dam || (meta&&meta.kind==='dam');
    const H=(r.history||[]).filter(v=>typeof v==='number'&&!isNaN(v));
    const times=(r.histRaw&&r.histRaw.length===H.length)?r.histRaw.map(o=>o.t):null;
    const num=(v,dg)=>(v!=null && !isNaN(v)) ? Number(v).toFixed(dg==null?1:dg) : '-';
    const fmtHM=(s)=>{ s=String(s||''); return s.length>=10 ? (+s.slice(8,10))+'시' : ''; };
    const dcell=(k,v)=>R('div',{style:{padding:'9px 12px', background:'var(--surface2)', borderRadius:'10px', border:'1px solid var(--border)'}}, R('div',{style:{fontSize:'10.5px', color:'var(--ink3)'}}, k), R('div',{style:{fontSize:'15px', fontWeight:800, color:'var(--ink)'}}, v));
    const minfo=(k,v)=> (v==null||v==='')?null : R('div',{style:{display:'flex', gap:'8px'}}, R('span',{style:{color:'var(--ink3)', minWidth:'66px', flexShrink:0}}, k), R('span',{style:{fontWeight:600}}, v));

    // ---- 홍수위험 단계 임계값 ----
    let thresholds, curStage;
    if(isDam){
      thresholds=[];
      /* 댐의 danger 는 계획홍수위 그 자체(build_dams)라 '위험'과 '계획홍수위'가 같은 값으로 두 번 붙었다 → 하나로(2026-11-16) */
      if(r.warning!=null) thresholds.push({v:+r.warning, name:'관심', col:'var(--caution)'});
      const _pfh=(meta&&meta.pfh!=null)?+meta.pfh:null;
      if(r.danger!=null && (_pfh==null || Math.abs(+r.danger-_pfh)>0.005)) thresholds.push({v:+r.danger, name:'위험', col:'var(--severe)'});
      if(_pfh!=null || r.danger!=null) thresholds.push({v:(_pfh!=null?_pfh:+r.danger), name:'계획홍수위', col:'var(--severe)'});
      curStage=(r.danger!=null&&r.value>=r.danger)?4:(r.warning!=null&&r.value>=r.warning)?2:0;
    } else if(meta){
      thresholds=[{v:+meta.att,name:'관심',col:'var(--brand)'},{v:+meta.wrn,name:'주의',col:'var(--caution)'},{v:+meta.alm,name:'경계',col:'var(--warn)'},{v:+meta.srs,name:'심각',col:'var(--severe)'}];
      curStage = r.value>=+meta.srs?4 : r.value>=+meta.alm?3 : r.value>=+meta.wrn?2 : r.value>=+meta.att?1 : 0;
    } else {
      thresholds=[];
      if(r.warning!=null) thresholds.push({v:+r.warning, name:'관심', col:'var(--caution)'});
      if(r.danger!=null) thresholds.push({v:+r.danger, name:'경계', col:'var(--severe)'});
      curStage=(r.danger!=null&&r.value>=r.danger)?4:(r.warning!=null&&r.value>=r.warning)?2:0;
    }
    const curCol = isDam ? (curStage>=4?'var(--severe)':curStage>=2?'var(--caution)':'var(--safe)')
                         : ['var(--safe)','var(--brand)','var(--caution)','var(--warn)','var(--severe)'][curStage];
    const curName = isDam ? (curStage>=4?'위험':curStage>=2?'주의':'정상')
                          : ['정상','관심','주의','경계','심각'][curStage];

    // ---- 변화량 (1/3/6시간) ----
    const d1=r.delta1, d3=r.delta3;
    const d6=(H.length>=7)?+(H[H.length-1]-H[H.length-7]).toFixed(2):null;
    const chg=(v)=> (v==null)?'-': v>0.005?('▲ +'+v.toFixed(2)+'m'): v<-0.005?('▼ '+v.toFixed(2)+'m'):'— 변화없음';
    const chgCol=(v)=> (v==null)?'var(--ink3)': v>0.03?'var(--severe)': v<-0.03?'var(--safe)':'var(--ink2)';

    // ---- 상승속도·예측 ----
    const rate = (d3!=null&&Math.abs(d3)>=0.01)? d3/3 : (d1||0);
    const ups = thresholds.filter(t=>t.v>r.value).sort((a,b)=>a.v-b.v);
    let projTxt, projCol;
    if(rate>0.02 && ups.length){
      const nx=ups[0], hrs=(nx.v-r.value)/rate;
      projTxt='현재 상승속도 ≈ '+rate.toFixed(2)+'m/h · '+nx.name+' 수위('+num(nx.v,1)+'m)까지 '+(hrs>48?'48시간 이상':(hrs<1?'1시간 이내':'약 '+Math.round(hrs)+'시간'));
      projCol='var(--warn)';
    } else if(rate<-0.02){
      projTxt='하강 중 ≈ '+Math.abs(rate).toFixed(2)+'m/h · 위험도 완화'; projCol='var(--safe)';
    } else {
      projTxt='수위 안정 (변화 미미)'; projCol='var(--ink2)';
    }

    // ---- 24시간 추이 차트 (최고수위 지점·시각 표시) ----
    let chart=null;
    if(H.length>=2){
      let mn=Math.min.apply(null,H), mx=Math.max.apply(null,H);
      /* 세로 폭 최소값 — 위 cbRiverMinSpan(관심→경계 간격 기준, 단계가 오를수록 좁게). 좁으면 가운데를 두고 넓힌다 */
      { const ms=window.cbRiverMinSpan(r); if(mx-mn<ms){ const c=(mx+mn)/2; mn=c-ms/2; mx=c+ms/2; } }
      /* ⚠ 이 차트는 좌표계(100×34)를 실제 크기(약 500×116)로 preserveAspectRatio:none으로
         늘린다. 그대로 두면 가로 5배·세로 3.4배로 '선 굵기'까지 불균등하게 늘어나 선이
         뭉개져 보이고, <circle>은 타원으로 찌그러진다(빨간 최고점이 실제로 그랬다).
         → 선·눈금은 vector-effect:non-scaling-stroke로 항상 지정한 px 굵기를 유지하고,
           점은 SVG 원 대신 HTML 요소를 %좌표로 얹어 완전한 정원으로 그린다.
         좌우 3% 여백을 둬 선과 점이 카드 모서리에 붙거나 잘리지 않게 한다. */
      const pv=(mx-mn)*0.2, lo=mn-pv, hi=mx+pv, W=100, HT=34, PADX=3;
      const px=(i)=>+(PADX + i/((H.length-1)||1)*(W-PADX*2)).toFixed(2);
      const pts=H.map((v,i)=>[px(i), +(HT-(v-lo)/(hi-lo)*HT).toFixed(2)]);
      const line=pts.map(p=>p.join(',')).join(' ');
      const area=PADX+','+HT+' '+line+' '+(W-PADX)+','+HT;
      let pk=0; for(let i=1;i<H.length;i++) if(H[i]>H[pk]) pk=i;
      const pkPt=pts[pk], last=pts[pts.length-1];
      /* 기준수위 선 — 그래프 범위 안에 들어온 단계선만(관심·경계에 다가가면 보인다) */
      const yOf=v=>+(HT-(v-lo)/(hi-lo)*HT).toFixed(2);
      const tIn=thresholds.filter(t=>isFinite(t.v) && t.v>lo && t.v<hi);
      const dot=(p,size,bg,ring)=>R('span',{style:{position:'absolute', left:p[0]+'%', top:(p[1]/HT*100)+'%',
        width:size+'px', height:size+'px', borderRadius:'50%', background:bg, boxSizing:'border-box',
        border:(ring?('2px solid '+ring):'none'), transform:'translate(-50%,-50%)', pointerEvents:'none'}});
      chart=R('div',{style:{marginTop:'6px'}},
        // ⚠ width:100%를 반드시 준다. 이 래퍼가 flex 안에 놓이면 너비가 내용에 맞춰 줄고,
        //   자식 svg의 width:100%가 그 줄어든 너비를 따라가 차트가 2px로 찌그러진다(실측).
        R('div',{style:{position:'relative', width:'100%'}},
        R('svg',{viewBox:'0 0 100 34', preserveAspectRatio:'none', style:{width:'100%', height:'116px', background:'var(--surface2)', borderRadius:'12px', border:'1px solid var(--border)', display:'block'}},
          [0.25,0.5,0.75].map((f,gi)=>R('line',{key:'g'+gi, x1:0, y1:+(HT*f).toFixed(2), x2:W, y2:+(HT*f).toFixed(2),
            stroke:'var(--border2)', strokeWidth:1, strokeDasharray:'4 4', opacity:0.65, vectorEffect:'non-scaling-stroke'})),
          R('polyline',{points:area, fill:curCol, opacity:0.13, stroke:'none'}),
          tIn.map((t,ti)=>R('line',{key:'t'+ti, x1:0, y1:yOf(t.v), x2:W, y2:yOf(t.v), stroke:t.col, strokeWidth:1.5, strokeDasharray:'6 4', vectorEffect:'non-scaling-stroke'})),
          R('polyline',{points:line, fill:'none', stroke:curCol, strokeWidth:2, strokeLinecap:'round', strokeLinejoin:'round', vectorEffect:'non-scaling-stroke'})),
        tIn.map((t,ti)=>R('span',{key:'tl'+ti, style:{position:'absolute', left:'8px', top:(yOf(t.v)/HT*100)+'%', transform:'translateY(-110%)',
          fontSize:'10.5px', fontWeight:800, color:t.col, background:'var(--surface2)', padding:'0 3px', borderRadius:'3px', pointerEvents:'none'}}, t.name+' '+num(t.v,2)+'m')),
        dot(pkPt, 7, 'var(--severe)', null),
        dot(last, 10, curCol, 'var(--surface)')),
        R('div',{style:{display:'flex', justifyContent:'space-between', fontSize:'10.5px', color:'var(--ink3)', marginTop:'4px'}},
          R('span',{}, '24시간 전'),
          R('span',{style:{color:'var(--severe)', fontWeight:700}}, '최고 '+num(H[pk],2)+'m'+(times?(' · '+fmtHM(times[pk])):'')),
          R('span',{}, '현재'))
      );
    }

    // ---- 홍수위험 단계 게이지 ----
    let gauge=null;
    if(thresholds.length){
      const allV=thresholds.map(t=>t.v).concat([r.value]);
      /* 댐은 수위가 해발 높이(충주조정지댐 64m)라 0m 부터 그리면 늘 초록 한가운데였다(2026-11-16).
         → 24시간 최저와 가장 높은 기준 사이 폭의 절반만큼 아래에서 시작. 하천은 그대로 0m(바닥)부터 */
      const _top=Math.max.apply(null,allV);
      const g0 = isDam ? (function(){ const lowV=Math.min.apply(null,H.concat([+r.value])); return lowV-Math.max(1,(_top-lowV)*0.5); })() : 0;
      const dmax = isDam ? _top+(_top-g0)*0.06 : ((_top||1)*1.04);
      // 칸마다 최소 너비 — 기준이 붙어 있어도(관심 0.7m·주의 1.0m) 이름·수치가 안 겹치게. 구간 너비 = max(실제 비율, 12%)
      // 를 다시 100% 로 맞춘 눈금. 현재 수위 표식은 자기 구간 안에서 비례 위치.
      const _ts=thresholds.slice().sort((a,b)=>(+a.v||0)-(+b.v||0));
      const _bnd=[g0].concat(_ts.map(t=>Math.max(g0,+t.v||0)), [dmax]);
      // 칸 최소 너비 = 이웃한 두 이름표가 반씩 들어가고 6px 남는 폭. 고정 12% 는 좁은 화면(게이지 290px)에서
      // '계획홍수위'(41px)를 못 담아 여전히 겹쳤다. 이름표 폭은 글자 수로, 게이지 폭은 창 너비로 어림한다.
      const _gw=Math.max(200, Math.min(560, ((typeof window!=='undefined'&&window.innerWidth)||800)-90));
      const _lw=_ts.map(t=>Math.max(String(t.name||'').length*9.5, (num(t.v,1)+'m').length*5.6)+4);
      const _w=[]; let _sum=0;
      for(let i=0;i<_bnd.length-1;i++){
        const need=((i>0?_lw[i-1]/2:0)+(i<_lw.length?_lw[i]/2:0)+6)/_gw;      // 앞 이름표 반 + 뒤 이름표 반 + 여유
        const w=Math.max((_bnd[i+1]-_bnd[i])/(dmax-g0), 0.08, need); _w.push(w); _sum+=w; }
      const _cum=[0]; _w.forEach((w,i)=>_cum.push(_cum[i]+w/_sum));
      const pct=(v)=>{ v=Math.max(g0,Math.min(dmax,+v||0));
        for(let i=0;i<_bnd.length-1;i++){ if(v<=_bnd[i+1]){ const span=_bnd[i+1]-_bnd[i]; const f=span>0?(v-_bnd[i])/span:1; return Math.max(0,Math.min(100,(_cum[i]+f*(_cum[i+1]-_cum[i]))*100)); } }
        return 100; };
      let grad;
      if(!isDam && meta){
        grad='linear-gradient(90deg, var(--safe) 0 '+pct(+meta.att)+'%, var(--brand) '+pct(+meta.att)+'% '+pct(+meta.wrn)+'%, var(--caution) '+pct(+meta.wrn)+'% '+pct(+meta.alm)+'%, var(--warn) '+pct(+meta.alm)+'% '+pct(+meta.srs)+'%, var(--severe) '+pct(+meta.srs)+'% 100%)';
      } else {
        /* 칸마다 '그 칸이 넘은 기준'의 색 — 관심이 없는 댐(충주조정지댐)에서 색 계산이 꼬여 전부 초록이던 것 고침(2026-11-16) */
        const _cols=['var(--safe)'].concat(_ts.map(t=>t.col));
        grad='linear-gradient(90deg, '+_cols.map((c,i)=>c+' '+(_cum[i]*100).toFixed(2)+'% '+(_cum[i+1]*100).toFixed(2)+'%').join(', ')+')';
      }
      const cpct=pct(r.value);
      gauge=R('div',{style:{marginTop:'4px', paddingTop:'15px'}},
        R('div',{style:{position:'relative', height:'12px', borderRadius:'6px', background:grad, border:'1px solid var(--border)'}},
          R('div',{style:{position:'absolute', left:cpct+'%', top:'-15px', transform:'translateX(-50%)', fontSize:'11px', fontWeight:900, color:'var(--ink)', lineHeight:1, whiteSpace:'nowrap'}}, '▼'),
          R('div',{style:{position:'absolute', left:cpct+'%', top:'-2px', bottom:'-2px', width:'2px', transform:'translateX(-1px)', background:'var(--ink)'}})),
        // 이름표는 값이 아니라 칸 경계 순번에 — 값이 같은 기준(댐 위험 52.0m = 계획홍수위 52.0m)도 겹치지 않게
        R('div',{style:{position:'relative', height:'24px', marginTop:'3px'}}, _ts.map((t,i)=>{ const lp=_cum[i+1]*100; return (
          R('div',{key:i, style:{position:'absolute', left:lp+'%', transform:'translateX(-50%)', textAlign:'center', whiteSpace:'nowrap'}},
            R('div',{style:{fontSize:'9.5px', fontWeight:800, color:t.col, lineHeight:1.15}}, t.name),
            R('div',{style:{fontSize:'9px', color:'var(--ink3)', lineHeight:1.15}}, num(t.v,1)+'m'))); }))
      );
    }

    // ---- 홍수예보 발령 연계 ----
    const ff=(d.flood||[]).filter(f=>{ const rv=f.river||'', ob=f.obs||''; return (rv&&r.name.indexOf(rv)>=0)||(ob&&r.name.indexOf(ob)>=0); });

    return R('div',{},
      // 헤더: 현재 수위 + 단계
      R('div',{style:{display:'flex', gap:'16px', alignItems:'flex-end', flexWrap:'wrap', marginBottom:'12px'}},
        R('div',{}, R('div',{style:{fontSize:'11px', color:'var(--ink3)', fontWeight:600}}, isDam?'현재 저수위':'현재 수위'),
          R('div',{style:{fontSize:'34px', fontWeight:800, color:'var(--ink)', lineHeight:1.05}}, num(r.value,2), R('span',{style:{fontSize:'15px', color:'var(--ink3)'}}, 'm'))),
        R('div',{style:{display:'flex', gap:'7px', alignItems:'center', paddingBottom:'4px'}},
          R('span',{style:{fontSize:'12.5px', fontWeight:800, color:'#fff', background:curCol, padding:'5px 13px', borderRadius:'8px'}}, curName+' 단계'),
          R('span',{style:{fontSize:'11.5px', fontWeight:700, color:chgCol(d1), background:'var(--surface2)', padding:'5px 11px', borderRadius:'8px', border:'1px solid var(--border)'}}, '1시간 '+chg(d1)))),

      // 변화량 1/3/6시간
      R('div',{style:{display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:'8px', marginBottom:'4px'}},
        [['1시간',d1],['3시간',d3],['6시간',d6]].map((it,i)=>R('div',{key:i, style:{padding:'8px 10px', background:'var(--surface2)', borderRadius:'10px', border:'1px solid var(--border)', textAlign:'center'}},
          R('div',{style:{fontSize:'10.5px', color:'var(--ink3)'}}, it[0]+' 변화'),
          R('div',{style:{fontSize:'13px', fontWeight:800, color:chgCol(it[1])}}, chg(it[1]))))),

      // 24시간 추이
      R('div',{style:{marginTop:'12px'}},
        R('div',{style:{fontSize:'12px', fontWeight:800, color:'var(--ink2)', marginBottom:'2px'}}, '최근 24시간 추이'),
        chart),

      // 예측
      R('div',{style:{marginTop:'10px', padding:'9px 13px', background:'var(--surface2)', borderRadius:'10px', border:'1px solid var(--border)', fontSize:'12px', fontWeight:600, color:projCol}}, '📈 '+projTxt),

      // 홍수위험 단계 게이지
      R('div',{style:{marginTop:'16px'}},
        R('div',{style:{fontSize:'12px', fontWeight:800, color:'var(--ink2)', marginBottom:'2px'}}, '홍수위험 단계'),
        gauge || R('div',{style:{fontSize:'12px', color:'var(--ink3)', padding:'6px 0'}}, '기준수위 정보 없음')),

      // 댐 운영 현황
      (isDam&&r.dam)? R('div',{style:{marginTop:'18px'}},
        R('div',{style:{fontSize:'12px', fontWeight:800, color:'var(--ink2)', marginBottom:'7px'}}, '💧 댐 운영 현황',
          /* 언제 값인지 — 유입·방류·저수량은 10분 자료, 방류 변화(하류 영향 판단)는 시간 자료 */
          (function(){ const t=String(r.dam.time||''), h=String(r.dam.out_time||'');
            const f=(s)=> s.length>=12 ? (+s.slice(4,6))+'.'+(+s.slice(6,8))+' '+s.slice(8,10)+':'+s.slice(10,12) : s.length>=10 ? (+s.slice(4,6))+'.'+(+s.slice(6,8))+' '+s.slice(8,10)+'시' : '';
            const txt=[f(t)?f(t)+' 관측(10분 자료)':'', f(h)?'방류 변화는 '+f(h)+' 시간 자료':''].filter(Boolean).join(' · ');
            return txt ? R('span',{style:{marginLeft:'8px', fontSize:'13px', fontWeight:600, color:'var(--ink3)'}}, txt) : null; })()),
        R('div',{style:{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'8px'}},
          /* 홍수통제소 명세대로(2026-11-16): sfw=저수량, ecpc=공용량. 예전 이름(outflow·storage_rate)으로 온 자료도 같은 뜻으로 읽는다 */
          dcell('유입량', num(r.dam.inflow,1)+' ㎥/s'),
          dcell('총 방류량', num(r.dam.total_outflow,1)+' ㎥/s'),
          dcell('저수량', num(r.dam.storage!=null?r.dam.storage:r.dam.outflow,1)+' 백만㎥'),
          dcell('공용량', num(r.dam.free_cap!=null?r.dam.free_cap:r.dam.storage_rate,1)+' 백만㎥')),
        R('div',{style:{marginTop:'8px', fontSize:'11px', color:'var(--ink3)', lineHeight:1.5}}, '※ 저수위는 유입·유출 외 수문 조작으로 조절됩니다. 하류 위험은 방류량 급증에 유의.'),
        /* 하류 영향·과거 사례 (dam-watch.js — 충북에 영향 주는 댐만, 2026-11-16) */
        (function(){ const w=window.cbDamWatch&&window.cbDamWatch.judge(r); if(!w) return null;
          const c = w.state==='surge'?'var(--severe)':w.state==='gate'?'var(--warn)':'var(--safe)';
          return R('div',{style:{marginTop:'10px', padding:'10px 12px', borderRadius:'10px', background:'var(--surface2)', border:'1px solid '+(w.state==='normal'?'var(--border)':c), fontSize:'12.5px', color:'var(--ink2)', lineHeight:1.6}},
            R('div',{}, R('b',{style:{color:c}}, w.label), ' · 수문 방류 수준 '+w.gate.toLocaleString()+'㎥/s 이상'+(w.d3!=null?(' · 3시간 '+(w.d3>0?'+':'')+Math.round(w.d3)+'㎥/s'):'')),
            R('div',{}, R('b',{}, '하류 '+w.down.join('·')), ' — '+w.path),
            w.past ? R('div',{style:{marginTop:'3px'}}, '📌 과거 사례 · '+w.past) : null); })()
      ):null,

      // 홍수예보 발령
      ff.length? R('div',{style:{marginTop:'18px'}},
        R('div',{style:{fontSize:'12px', fontWeight:800, color:'var(--severe)', marginBottom:'7px'}}, '🚨 홍수예보 발령'),
        ff.map((f,i)=>R('div',{key:i, style:{padding:'10px 13px', background:'var(--severeSoft)', borderRadius:'11px', border:'1px solid var(--severe)', marginBottom:'6px'}},
          R('div',{style:{fontSize:'13px', fontWeight:800, color:'var(--severe)'}}, (f.river||'')+' '+(f.kind||'')),
          R('div',{style:{fontSize:'11.5px', color:'var(--ink2)', marginTop:'3px'}}, (f.area?('대상: '+f.area+'  '):'')+(f.forecast?('· 도달예상 '+f.forecast):''))))
      ):null,

      // 관측소 정보
      meta? R('div',{style:{marginTop:'18px', padding:'11px 14px', background:'var(--surface2)', borderRadius:'11px', border:'1px solid var(--border)'}},
        R('div',{style:{fontSize:'11.5px', fontWeight:800, color:'var(--ink2)', marginBottom:'6px'}}, '관측소 정보'),
        R('div',{style:{display:'flex', flexDirection:'column', gap:'3px', fontSize:'11.5px', color:'var(--ink2)'}},
          minfo('관할', meta.agc),
          isDam?null:minfo('영점표고', meta.gdt!=null?num(meta.gdt,2)+'m':null),
          minfo('계획홍수위', meta.pfh!=null?num(meta.pfh, isDam?0:2)+'m':null),
          isDam?null:minfo('홍수예보지점', meta.fstn?'지정':'미지정'),
          minfo('주소', meta.addr))
      ):null,

      // CCTV
      // 장치번호(cctv-hrfco.js)가 있으면 통제소 HLS 를 직접 튼다(팝업 UI 없음, 90초 뒤 멈춤·계속 보기). 없으면 종전 팝업 iframe.
      r.cctv? R('div',{style:{marginTop:'18px'}},
        R('div',{style:{fontSize:'12px', color:'var(--brand)', fontWeight:800, marginBottom:'7px', display:'flex', alignItems:'center', gap:'6px'}}, '📹 실시간 CCTV', R('span',{style:{fontSize:'9px', fontWeight:800, color:'#fff', background:'var(--severe)', padding:'1px 5px', borderRadius:'4px'}}, 'LIVE'),
          R('a',{href:'https://n.flood.go.kr/main/cctvView.do?obscd='+r.code+'&fcodvcd=01', target:'_blank', rel:'noopener', style:{marginLeft:'auto', fontSize:'10.5px', fontWeight:700, color:'var(--ink3)', textDecoration:'none'}}, '홍수통제소에서 보기 ↗')),
        (window.hrfcoCam && window.hrfcoCam(r.code)) ?
        R('div',{style:{position:'relative', width:'100%', borderRadius:'12px', overflow:'hidden', background:'#000', border:'1px solid var(--border)'}},
          R('video',{key:'hr'+r.code, muted:true, playsInline:true, controls:true, style:{display:'block', width:'100%', aspectRatio:'16 / 9', background:'#000'},
            ref:(el)=>{ if(!el) return; if(el._code===r.code && !self.state.riverCctvResume) return; el._code=r.code;
              const msg=(s)=>{ const n=el.parentNode&&el.parentNode.querySelector('[data-cctv-msg]'); if(n) n.textContent=s; };
              msg('연결 중… (통제소 스트림을 켜는 데 몇 초 걸립니다)');
              window.cctvPlay(el, {hrfco:String(r.code)}, function(why){ msg('재생 실패('+why+') — 홍수통제소에서 보기'); }, function(){ msg('⏸ 90초가 지나 멈췄습니다 — 눌러서 계속 보기'); self.setState({riverCctvPaused:true, riverCctvResume:false}); }.bind(self));
              el.addEventListener('playing', function(){ msg(''); }, {once:true});
              if(self.state.riverCctvResume) self.setState({riverCctvResume:false}); }}),
          R('div',{'data-cctv-msg':'1', onClick:()=>{ if(self.state.riverCctvPaused) self.setState({riverCctvPaused:false, riverCctvResume:true}); }, style:{position:'absolute', left:0, right:0, bottom:0, padding:'6px 10px', color:'#ffd166', fontSize:'11px', fontWeight:700, background:'linear-gradient(0deg, rgba(0,0,0,.55), transparent)', cursor:'pointer'}}, ''))
        :
        R('div',{style:{position:'relative', width:'100%', aspectRatio:'16 / 10', borderRadius:'12px', overflow:'hidden', background:'#000', border:'1px solid var(--border)'}},
          R('iframe',{src:'https://n.flood.go.kr/main/cctvView.do?obscd='+r.code+'&fcodvcd=01', style:{position:'absolute', top:0, left:0, width:'200%', height:'200%', border:0, transformOrigin:'top left', transform:'scale(1.0) translateY(-7%)'}, loading:'lazy'}))
      ):null
    );
  };
})();
