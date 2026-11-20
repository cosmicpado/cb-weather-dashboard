/* 화면 점검 — 종합·재해·상황판·도움말을 PC 크기와 휴대폰 크기로 열어 보고 문제를 적는다.

   왜 필요한가
     화면을 고친 뒤 눈으로 네 화면 × 두 크기를 다 열어 보기는 번거롭고, 스크립트 오류는 화면이 멀쩡해 보여도 숨어 있다.
     — 그래서 기계가 먼저 본다. 사진도 남기니 고친 뒤 한눈에 비교할 수 있다.

   보는 것
     1) 스크립트 오류(빨간 오류)            → 문제
     2) 이 서버 파일을 못 받음(404 등)       → 문제
     3) 화면이 옆으로 넘침(가로 스크롤 생김) → 문제
     4) 종합·재해 윗줄 자리(볼 범위·화면 전환·알림 단추)가 PC 에서 같은지 → 문제
     5) 13px 보다 작은 글자                  → 알림만(종료코드에 넣지 않음)

   실행:  서버(서버.bat 또는 python tools/live_local.py)를 켠 상태에서
          node tools/check_screens.mjs                       (기본 주소 http://127.0.0.1:8765)
          node tools/check_screens.mjs --base http://127.0.0.1:8000
   사진:  .tmp/screens/ 에 화면별 PNG (깃에 올라가지 않는다)
   결과:  문제가 있으면 종료코드 1
   필요:  Node 22 이상, Chrome 또는 Edge */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg('--base', 'http://127.0.0.1:8765').replace(/\/$/, '');
const OUT = path.join(ROOT, '.tmp', 'screens');
const WAIT = +arg('--wait', 8000);   // 화면이 자료를 받아 다 그릴 때까지 기다리는 시간(ms)

const PAGES = [['종합.html', '종합'], ['재해.html', '재해'], ['상황실.html', '상황판'], ['도움말.html', '도움말']];
const SIZES = [['PC', { width: 1600, height: 900, deviceScaleFactor: 1, mobile: false }],
               ['휴대폰', { width: 390, height: 780, deviceScaleFactor: 2, mobile: true }]];
const HEAD = ['.scope', '.pgs', '[aria-label="알림 설정"]'];   // 종합·재해가 같은 자리여야 하는 윗줄 칸

function findBrowser() {
  const pf = [process.env['ProgramFiles'], process.env['ProgramFiles(x86)'], process.env.LOCALAPPDATA].filter(Boolean);
  const c = [];
  for (const b of pf) c.push(path.join(b, 'Google/Chrome/Application/chrome.exe'), path.join(b, 'Microsoft/Edge/Application/msedge.exe'));
  c.push('/usr/bin/google-chrome', '/usr/bin/chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');
  return c.find(p => { try { return fs.statSync(p).isFile(); } catch { return false; } });
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  try { await fetch(BASE + '/종합.html', { method: 'HEAD' }); }
  catch { console.log(`서버에 연결하지 못했습니다: ${BASE}\n서버를 켜거나 --base 로 주소를 알려 주세요.`); process.exit(2); }
  const exe = findBrowser();
  if (!exe) { console.log('Chrome 또는 Edge 를 찾지 못했습니다.'); process.exit(2); }
  fs.mkdirSync(OUT, { recursive: true });

  const port = 9300 + Math.floor(Math.random() * 500);
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'cb-check-'));
  const br = spawn(exe, ['--headless=new', '--remote-debugging-port=' + port, '--user-data-dir=' + prof, '--no-first-run', 'about:blank'], { stdio: 'ignore' });
  let tab;
  for (let i = 0; i < 40 && !tab; i++) {
    await sleep(250);
    try { tab = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(x => x.type === 'page'); } catch {}
  }
  if (!tab) { console.log('브라우저를 띄우지 못했습니다.'); br.kill(); process.exit(2); }

  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  let id = 0; const wait = {}; let log = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && wait[m.id]) { wait[m.id](m.result || {}); delete wait[m.id]; }
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails;
      log.push(['오류', ((d.exception && d.exception.description) || d.text || '').split('\n')[0].slice(0, 200) + (d.url ? ` (${decodeURIComponent(d.url.split('/').pop())}:${d.lineNumber + 1})` : '')]);
    }
    if (m.method === 'Network.responseReceived') {
      const r = m.params.response;
      // 없어도 되는 것은 뺀다: 짧은 주소 확인(short-url.js) · 새 판 확인(version-check.js) · 서버 기능(api) · 브라우저가 알아서 찾는 favicon
      const u = r.url.slice(BASE.length).split('?')[0];
      const optional = /^\/(map|watch|wall|room|help|admin|version\.json|favicon\.ico)$/.test(u) || u.startsWith('/api/');
      if (r.status >= 400 && r.url.startsWith(BASE) && !optional) log.push(['파일 없음', r.status + ' ' + decodeURIComponent(r.url.slice(BASE.length))]);
    }
  };
  const send = (method, params = {}) => new Promise(r => { const i = ++id; wait[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
  const ev = async s => (await send('Runtime.evaluate', { expression: s, returnByValue: true })).result?.value;
  await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');

  let bad = 0; const heads = {};
  for (const [sz, metrics] of SIZES) {
    await send('Emulation.setDeviceMetricsOverride', metrics);
    for (const [file, name] of PAGES) {
      log = [];
      await send('Page.navigate', { url: BASE + '/' + encodeURIComponent(file) });
      await sleep(WAIT);
      const r = await ev(`(() => {
        const over = document.documentElement.scrollWidth - innerWidth;
        const small = [];
        const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        for (let n; (n = tw.nextNode());) {
          if (!n.textContent.trim()) continue;
          const el = n.parentElement; if (!el || el.closest('svg,.leaflet-container,script,style')) continue;
          const cs = getComputedStyle(el), fs = parseFloat(cs.fontSize);
          if (fs >= 13 || cs.visibility === 'hidden' || !el.getClientRects().length) continue;
          small.push(fs + 'px "' + n.textContent.trim().slice(0, 18) + '"');
        }
        const head = ${JSON.stringify(HEAD)}.map(s => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.right), Math.round(b.top + b.height / 2)]; });
        return { over, small: [...new Set(small)], head };
      })()`) || { over: 0, small: [], head: [] };
      const shot = await send('Page.captureScreenshot', { format: 'png' });
      const png = `${name}_${sz}.png`;
      if (shot.data) fs.writeFileSync(path.join(OUT, png), Buffer.from(shot.data, 'base64'));
      if (r.over > 1) log.push(['옆 넘침', `화면보다 ${r.over}px 넓음 — 가로 스크롤이 생긴다`]);
      if (sz === 'PC' && (name === '종합' || name === '재해')) heads[name] = r.head;

      const probs = log.filter((x, i, a) => a.findIndex(y => y[1] === x[1]) === i);
      bad += probs.length;
      console.log(`${probs.length ? '✗' : '✓'} ${name} · ${sz}${probs.length ? '' : ' — 문제 없음'}   (사진 .tmp/screens/${png})`);
      for (const [k, v] of probs) console.log(`    [${k}] ${v}`);
      if (r.small.length) console.log(`    (알림) 13px 보다 작은 글자 ${r.small.length}곳: ${r.small.slice(0, 4).join(', ')}${r.small.length > 4 ? ' …' : ''}`);
    }
  }
  if (heads.종합 && heads.재해) {
    const diff = HEAD.filter((s, i) => JSON.stringify(heads.종합[i]) !== JSON.stringify(heads.재해[i]));
    if (diff.length) { bad += diff.length; console.log(`✗ 윗줄 자리 — 종합과 재해가 다름: ${diff.join(', ')} (오른쪽 끝·세로 가운데 ${diff.map(s => JSON.stringify(heads.종합[HEAD.indexOf(s)]) + ' vs ' + JSON.stringify(heads.재해[HEAD.indexOf(s)])).join(' / ')})`); }
    else console.log('✓ 윗줄 자리 — 종합·재해 같음');
  }
  console.log(bad ? `\n문제 ${bad}건` : '\n모두 정상');
  ws.close(); br.kill();
  try { fs.rmSync(prof, { recursive: true, force: true }); } catch {}
  process.exit(bad ? 1 : 0);
}
main().catch(e => { console.log('점검 중 오류:', e.message); process.exit(2); });
