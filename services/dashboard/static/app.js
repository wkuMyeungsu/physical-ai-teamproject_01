// ===== API 연결부 =====
// ① QR 카메라 연동은 frame-capture, ② 저장 현황은 vector-store, ③ RAG 검색은 rag-chat에 연결됨.
// 서비스가 없을 때 화면만 보려면 MOCK 값을 true로 바꾼다.
// 화면 코드(아래 render*)는 이 함수들의 반환 형식만 보고 그린다.
//   session() → { session_id, capture_url, qr_png }   (qr_png: PNG base64)
//   stats()   → { saved, per_minute, latest: [{ id, no, title, text, saved_at }] }  (latest는 최신순, no는 저장 순번)
//   ask(q)    → { answer, sources: [{ n, id, title }] }  (n은 답변 안의 [1], [2] 번호)
const MOCK = { stats: false, ask: false };

const real = {
  session: () => getJSON('/api/session', { method: 'POST' }),
  stats: () => getJSON('/api/stats'),
  ask: (question) => getJSON('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) }),
};

// 연결 상태·실시간 영상은 브라우저가 frame-capture WebSocket에 붙는다.
// localhost:8000으로 직접 열면 frame-capture 포트(8001)로, 프록시·터널 주소로 열면 같은 주소의 /ws/로 붙는다 (프록시가 frame-capture로 넘김).
const captureWsUrl = (sid) => {
  const host = location.port === '8000' ? `${location.hostname}:8001` : location.host;
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${host}/ws/dashboard/${sid}`;
};

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json();
}

// ===== 임시 데이터 (MOCK 값이 true인 API만 사용) =====
const PASSAGES = [
  { title: 'The Quiet Machinery of Cities', text: 'Beneath every pavement there is a second city that almost no one sees. Water moves through cast-iron veins laid down in 1897.' },
  { title: 'Notes on Reading Speed', text: 'An average adult reads roughly 240 words per minute on paper and about 180 on a backlit screen.' },
  { title: 'A Letter from the Coast', text: 'Dear Miriam, the fog arrived on Tuesday and has not left since. The lighthouse keeper says this is ordinary for October.' },
  { title: 'Quarterly Operations Summary', text: 'Total throughput for Q3 reached 1,482,600 units, an increase of 8.4% over Q2 and 21.7% year over year.' },
  { title: 'On the Habit of Walking', text: 'Walking is the only exercise that doubles as thinking. The pace is slow enough to notice a doorway.' },
  { title: 'A Short History of Paper', text: 'Paper was first made in China around 105 AD from mulberry bark, hemp and rags.' },
  { title: 'How Bread Fails', text: 'Yeast dies when the water is hotter than 46 °C. Dough that never rises usually met water that was too hot.' },
  { title: 'Service Bulletin SB-4471', text: 'Inspect the fuel pump coupling every 400 operating hours and replace it if wear exceeds 0.8 mm.' },
];

const mock = (() => {
  const saved = [];
  let next = 0;
  return {
    async stats() {
      const p = PASSAGES[next % PASSAGES.length];  // 2초마다 1건씩 쌓인다
      saved.unshift({ id: next + 1, no: next + 1, title: p.title, text: p.text, saved_at: new Date().toISOString() });
      next++;
      const minuteAgo = Date.now() - 60000;
      return { saved: saved.length, per_minute: saved.filter(s => Date.parse(s.saved_at) > minuteAgo).length, latest: saved.slice(0, 20) };
    },
    async ask(question) {
      await new Promise(r => setTimeout(r, 700));
      const words = question.toLowerCase().match(/[a-z0-9]+/g) || [];
      const scored = PASSAGES.map((p, i) => ({ i, p, s: words.filter(w => w.length > 2 && p.text.toLowerCase().includes(w)).length }))
        .filter(x => x.s > 0).sort((a, b) => b.s - a.s);
      if (!scored.length) return { answer: '저장된 원문에서 관련 내용을 찾지 못했습니다.', sources: [] };
      return { answer: `[임시 답변] ${scored[0].p.text}`, sources: scored.slice(0, 2).map((x, k) => ({ n: k + 1, id: x.i + 1, title: x.p.title })) };
    },
  };
})();

const api = {
  session: real.session,
  stats: MOCK.stats ? mock.stats : real.stats,
  ask: MOCK.ask ? mock.ask : real.ask,
};

// ===== 화면 =====
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const hhmmss = (iso) => new Date(iso).toLocaleTimeString('ko-KR', { hour12: false });

const mocked = [MOCK.stats && '②', MOCK.ask && '③'].filter(Boolean);
$('mock-badge').hidden = !mocked.length;
$('mock-badge').textContent = `${mocked.join('')} 임시 데이터`;

fetch('/api/health').then(r => r.json())
  .then(d => $('health').textContent = d.ok ? '서버 정상' : '서버 오류')
  .catch(() => $('health').textContent = '서버 연결 실패');

// 1. QR 카메라 연동 (frame-capture)
function setCam(text, on) {
  $('cam-status').textContent = text;
  $('cam-status').classList.toggle('on', !!on);
}
function showLive(live) {  // 영상이 오면 QR 대신 영상을 보여 준다
  $('viewer').hidden = !live;
  $('qr-box').hidden = live;
}

let frames = 0, recent = 0, lastFrameUrl = null;
setInterval(() => { $('fps').textContent = recent; recent = 0; }, 1000);

async function startSession() {
  setCam('세션 생성 중');
  showLive(false);
  try {
    const s = await api.session();
    $('sid').textContent = s.session_id;
    $('capture-url').textContent = s.capture_url;
    $('qr-img').src = `data:image/png;base64,${s.qr_png}`;
    $('qr-img').hidden = false;
    $('qr-msg').hidden = true;
    connectCapture(s.session_id);
  } catch (err) {
    setCam('frame-capture 연결 실패');
    $('qr-msg').textContent = `세션을 만들지 못했습니다 (${err.message}). 5초 뒤 다시 시도합니다.`;
    $('qr-msg').hidden = false;
    $('qr-img').hidden = true;
    setTimeout(startSession, 5000);
  }
}

function connectCapture(sid) {
  const ws = new WebSocket(captureWsUrl(sid));
  ws.binaryType = 'blob';
  const ping = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send('ping'), 20000);

  ws.onmessage = (ev) => {
    if (typeof ev.data !== 'string') {  // 바이너리 = 휴대폰이 보낸 JPEG 한 장
      const url = URL.createObjectURL(ev.data);
      $('live').src = url;
      if (lastFrameUrl) URL.revokeObjectURL(lastFrameUrl);
      lastFrameUrl = url;
      frames++; recent++;
      $('frames').textContent = frames;
      showLive(true);
      return;
    }
    const msg = JSON.parse(ev.data);
    if (msg.type === 'waiting') setCam('대기 중');
    else if (msg.type === 'paired') setCam('연결됨', true);
    else if (msg.type === 'phone_disconnected') { setCam('연결 끊김 — QR 다시 스캔'); showLive(false); }
  };
  ws.onclose = (ev) => {
    clearInterval(ping);
    if (ev.code === 4404) { startSession(); return; }  // frame-capture가 세션을 모름(재시작 등) → 새 세션
    setCam('frame-capture 재연결 중');
    setTimeout(() => connectCapture(sid), 2000);
  };
}

// 2. 실시간 저장 현황
let lastTopId = null;
let seen = new Set();
function renderStats(s) {
  $('saved').textContent = s.saved.toLocaleString();
  $('per-min').textContent = s.per_minute;
  $('last-at').textContent = s.latest.length ? hhmmss(s.latest[0].saved_at) : '—';
  const live = $('live-status');
  live.textContent = s.per_minute > 0 ? 'LIVE' : '대기 중';
  live.classList.toggle('on', s.per_minute > 0);
  if (!s.latest.length) {  // DB를 비우면 목록도 비운다
    $('feed').innerHTML = '';
    lastTopId = null;
    seen = new Set();
    return;
  }
  if (s.latest[0].id === lastTopId) return;
  lastTopId = s.latest[0].id;
  const first = seen.size === 0;  // 처음 그릴 때는 강조하지 않는다
  $('feed').innerHTML = s.latest.map(r => `
    <li class="${!first && !seen.has(r.id) ? 'new' : ''}${openIds.has(String(r.id)) ? ' open' : ''}" data-id="${esc(r.id)}" tabindex="0" aria-expanded="${openIds.has(String(r.id))}">
      <div class="top"><span class="id">#${String(r.no).padStart(3, '0')}</span><span class="title">${esc(r.title)}</span><span class="time">${hhmmss(r.saved_at)}</span></div>
      <p class="text">${esc(r.text)}</p>
    </li>`).join('');
  seen = new Set(s.latest.map(r => r.id));
}

// 항목을 누르면 그 항목만 원문 전체를 펼친다 (2초마다 다시 그려도 펼친 상태 유지)
const openIds = new Set();
function toggleItem(li) {
  const open = li.classList.toggle('open');
  li.setAttribute('aria-expanded', open);
  if (open) openIds.add(li.dataset.id); else openIds.delete(li.dataset.id);
}
$('feed').addEventListener('click', e => {
  const li = e.target.closest('li');
  if (li) toggleItem(li);
});
$('feed').addEventListener('keydown', e => {
  if ((e.key === 'Enter' || e.key === ' ') && e.target.tagName === 'LI') {
    e.preventDefault();
    toggleItem(e.target);
  }
});

// 3. RAG 검색
// 컨베이어 앞쪽 카드(001~003) 내용으로 만든 예시 질문
const EXAMPLES = ['How fast does an adult read on paper?', 'When were the water pipes laid?', 'What did the lighthouse keeper say about the fog?'];
$('examples').innerHTML = EXAMPLES.map(q => `<button type="button">${esc(q)}</button>`).join('');
$('examples').addEventListener('click', e => {
  if (e.target.tagName !== 'BUTTON') return;
  $('q').value = e.target.textContent;
  $('ask-form').requestSubmit();
});

$('ask-form').addEventListener('submit', async e => {
  e.preventDefault();
  const q = $('q').value.trim();
  if (!q) return;
  $('ask-btn').disabled = true;
  $('result').innerHTML = '<p class="muted">검색 중…</p>';
  try {
    const r = await api.ask(q);
    $('result').innerHTML = `<div class="answer">${esc(r.answer)}</div>` +
      (r.sources.length ? `<div class="sources">${r.sources.map(s => `<span>출처 [${s.n}] ${esc(s.title)}</span>`).join('')}</div>` : '');
  } catch (err) {
    $('result').innerHTML = `<p class="muted">검색 실패: ${esc(err.message)}</p>`;
  } finally {
    $('ask-btn').disabled = false;
  }
});

// 시작
startSession();
async function tickStats() {
  try { renderStats(await api.stats()); } catch { $('live-status').textContent = '연결 실패'; }
}
tickStats();
setInterval(tickStats, 2000);  // 실제 API에서 WebSocket·SSE를 주면 여기만 바꾼다
