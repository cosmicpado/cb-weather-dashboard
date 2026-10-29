// ===== 위험구역 데이터 =====
// [구글시트 실시간 연동] 배포 사이트에서는 RISK_SHEET_URL(웹 게시 CSV)을 자동으로 불러옵니다.
//   시트 열: 지역 | 이름 | 유형 | (등급) | 위도 | 경도
//   지역값은 관서명(청주동부·청주서부·충주…). "충주시" 처럼 써도 "충주" 관서로 자동 매칭됩니다.
//   x·y 는 시트에 넣지 않는다 — 위도·경도로 자동 계산된다(아래 RISK 는 시트를 못 읽을 때의 예비값).
// [VWorld 위치지도] VWORLD_KEY 에 브이월드 인증키를 넣고, 인증키에 배포 도메인을 등록하면
//   위험구역 상세에서 위·경도로 실제 지도(정적지도)가 표시됩니다. (비우면 안내 폴백)
window.VWORLD_KEY = "32219A4F-5ABE-4E0D-8E0D-911ED7E36B1B";
window.RISK_SHEET_URL = "https://docs.google.com/spreadsheets/d/1-tJEhkPtw-4dkiZbfr-0n52dwQ1RikpgbJO21ZuummY/gviz/tq?tqx=out:csv";
window.RISK = [{"id":1,"region":"청주서부","name":"궁평2지하차도","type":"지하차도","level":"주의","note":"충청북도 청주시 흥덕구 오송읍 궁평리 (미호강변로)","lat":36.6226831,"lng":127.3452699,"x":60.7,"y":574.2}];
