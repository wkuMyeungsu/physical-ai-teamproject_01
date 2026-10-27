// ===== API 연결부 =====
// 실제 API가 나오면 USE_MOCK을 false로 바꾸고, real의 주소·응답 형식만 맞춘다.
// 화면 코드(아래 render*)는 이 세 함수의 반환 형식만 보고 그린다.
//   session() → { capture_url: string, connected: boolean }
//   stats()   → { saved: number, per_minute: number, latest: [{ id, title, text, saved_at }] }  (latest는 최신순)
//   ask(q)    → { answer: string, sources: [{ id, title }] }
const USE_MOCK = true;

const real = {
  session: () => getJSON('/api/session'),
  stats: () => getJSON('/api/stats'),
  ask: (question) => getJSON('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) }),
};

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json();
}

// ===== 임시 데이터 (USE_MOCK = true일 때만 사용) =====
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
  const started = Date.now();
  const saved = [];
  let next = 0;
  return {
    async session() {
      return { capture_url: 'https://example-tunnel.app/capture?session=demo-001', connected: Date.now() - started > 4000 };
    },
    async stats() {
      if (Date.now() - started > 4000) {  // 카메라 연결 후부터 2초마다 1건씩 쌓인다
        const p = PASSAGES[next % PASSAGES.length];
        saved.unshift({ id: next + 1, title: p.title, text: p.text, saved_at: new Date().toISOString() });
        next++;
      }
      const minuteAgo = Date.now() - 60000;
      return { saved: saved.length, per_minute: saved.filter(s => Date.parse(s.saved_at) > minuteAgo).length, latest: saved.slice(0, 20) };
    },
    async ask(question) {
      await new Promise(r => setTimeout(r, 700));
      const words = question.toLowerCase().match(/[a-z0-9]+/g) || [];
      const scored = PASSAGES.map((p, i) => ({ i, p, s: words.filter(w => w.length > 2 && p.text.toLowerCase().includes(w)).length }))
        .filter(x => x.s > 0).sort((a, b) => b.s - a.s);
      if (!scored.length) return { answer: '저장된 원문에서 관련 내용을 찾지 못했습니다.', sources: [] };
      const top = scored[0];
      return { answer: `[임시 답변] ${top.p.text}`, sources: scored.slice(0, 2).map(x => ({ id: x.i + 1, title: x.p.title })) };
    },
  };
})();

const api = USE_MOCK ? mock : real;

// ===== 화면 =====
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const hhmmss = (iso) => new Date(iso).toLocaleTimeString('ko-KR', { hour12: false });

$('mock-badge').hidden = !USE_MOCK;

fetch('/api/health').then(r => r.json())
  .then(d => $('health').textContent = d.ok ? '서버 정상' : '서버 오류')
  .catch(() => $('health').textContent = '서버 연결 실패');

// 1. QR 카메라 연동
let qrText = null;
function renderSession(s) {
  if (s.capture_url !== qrText) {
    qrText = s.capture_url;
    $('capture-url').textContent = qrText;
    $('qr').innerHTML = '';
    // qrcodejs는 한글 등 비ASCII 주소에서 실패한다. 캡처 주소는 ASCII로 만든다.
    try { new QRCode($('qr'), { text: qrText, width: 200, height: 200 }); }
    catch (err) { $('qr').textContent = `QR 생성 실패: ${err.message || err}`; }
  }
  const st = $('cam-status');
  st.textContent = s.connected ? '연결됨' : '대기 중';
  st.classList.toggle('on', s.connected);
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
  if (!s.latest.length || s.latest[0].id === lastTopId) return;
  lastTopId = s.latest[0].id;
  const first = seen.size === 0;  // 처음 그릴 때는 강조하지 않는다
  $('feed').innerHTML = s.latest.map(r => `
    <li class="${!first && !seen.has(r.id) ? 'new' : ''}">
      <div class="top"><span class="id">#${String(r.id).padStart(3, '0')}</span><span class="title">${esc(r.title)}</span><span class="time">${hhmmss(r.saved_at)}</span></div>
      <p class="text">${esc(r.text)}</p>
    </li>`).join('');
  seen = new Set(s.latest.map(r => r.id));
}

// 3. RAG 검색
const EXAMPLES = ['What water temperature kills yeast?', 'How fast does an adult read?', 'When was paper first made?'];
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
      (r.sources.length ? `<div class="sources">${r.sources.map(s => `<span>출처 #${String(s.id).padStart(3, '0')} ${esc(s.title)}</span>`).join('')}</div>` : '');
  } catch (err) {
    $('result').innerHTML = `<p class="muted">검색 실패: ${esc(err.message)}</p>`;
  } finally {
    $('ask-btn').disabled = false;
  }
});

// 2초마다 갱신 (실제 API에서 WebSocket·SSE를 주면 여기만 바꾼다)
async function tick() {
  try { renderSession(await api.session()); } catch { $('cam-status').textContent = '연결 실패'; }
  try { renderStats(await api.stats()); } catch { $('live-status').textContent = '연결 실패'; }
}
tick();
setInterval(tick, 2000);
