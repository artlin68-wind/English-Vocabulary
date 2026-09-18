/* ================= 背單字 App — vanilla JS ================= *
 * 資料:data/index.json (manifest) + data/<book>.json
 * 功能:卡片瀏覽 / 翻面 / 左右滑動 / 發音 / 單元篩選 / 搜尋 /
 *       進度標記 / 自動播放(MediaSession 鎖屏連播)/ 分單元離線下載
 * ============================================================ */
'use strict';

const AUDIO_CACHE = 'vocab-audio';
const $ = (id) => document.getElementById(id);

/* ---------- 全域狀態 ---------- */
const state = {
  manifest: null,
  book: null,          // 目前 book meta
  words: [],           // 目前 book 全部單字
  units: [],           // [{name, from, to, count}]
  view: [],            // 篩選後的單字陣列
  pos: 0,              // view 內目前索引
  flipped: false,
  filter: { unit: null, status: 'all' },
  progress: {},        // { id: 'known' | 'review' }
  downloaded: {},      // { unitName: true }
  settings: {
    font: 1, rate: 1, autoFlip: true, readZh: false, repeat: false, gap: 0.9
  },
  auto: { on: false, timer: null, step: null },
};

/* ---------- localStorage 小工具 ---------- */
const LS = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
const keyProgress = (b) => `vocab.progress.${b}`;
const keyDl = (b) => `vocab.dl.${b}`;
const keyPos = (b) => `vocab.pos.${b}`;

/* ================= 啟動 ================= */
init();

async function init() {
  loadSettings();
  applyFont();
  bindStaticUI();
  registerSW();
  try {
    state.manifest = await fetchJSON('data/index.json');
  } catch (e) {
    return fatal('無法載入單字本清單 (data/index.json)。');
  }
  buildBookSelect();
  const firstBook = state.manifest.books[0].book;
  await loadBook(firstBook);
}

async function fetchJSON(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(url + ' ' + r.status);
  return r.json();
}

async function loadBook(bookCode) {
  const entry = state.manifest.books.find((b) => b.book === bookCode) || state.manifest.books[0];
  const data = await fetchJSON(entry.file);
  state.book = data.meta;
  state.words = data.words;
  state.progress = LS.get(keyProgress(bookCode), {});
  state.downloaded = LS.get(keyDl(bookCode), {});
  buildUnits();
  state.filter = { unit: null, status: 'all' };
  rebuildView();
  state.pos = clamp(LS.get(keyPos(bookCode), 0), 0, state.view.length - 1);
  $('bookName').textContent = state.book.name || bookCode;
  renderUnitList();
  render();
  updateStorageLine();
}

/* ================= 單元 / 篩選 ================= */
function buildUnits() {
  const map = new Map();
  state.words.forEach((w) => {
    if (!map.has(w.unit)) map.set(w.unit, []);
    map.get(w.unit).push(w);
  });
  state.units = [...map.entries()].map(([name, ws]) => ({ name, count: ws.length, words: ws }));
}

function rebuildView() {
  const { unit, status } = state.filter;
  state.view = state.words.filter((w) => {
    if (unit && w.unit !== unit) return false;
    const st = state.progress[w.id];
    if (status === 'review') return st === 'review';
    if (status === 'unknown') return !st;
    return true;
  });
  if (state.view.length === 0) state.view = state.words.slice(); // 篩選為空時退回全部,避免卡死
  state.pos = clamp(state.pos, 0, state.view.length - 1);
  updateUnitName();
}

function updateUnitName() {
  const parts = [];
  parts.push(state.filter.unit ? state.filter.unit : '全部單元');
  if (state.filter.status === 'review') parts.push('待複習');
  else if (state.filter.status === 'unknown') parts.push('未標記');
  $('unitName').textContent = parts.join(' · ');
}

/* ================= 卡片渲染 ================= */
function current() { return state.view[state.pos]; }

function render() {
  const w = current();
  if (!w) return;
  // 正面
  const posRow = $('posRow');
  posRow.innerHTML = '';
  (w.pos || []).forEach((p) => {
    const s = document.createElement('span');
    s.className = 'pos-tag'; s.textContent = p; posRow.appendChild(s);
  });
  $('wordText').textContent = w.word;
  const ipa = $('ipaText');
  if (w.ipa) { ipa.textContent = w.ipa; ipa.hidden = false; }
  else { ipa.hidden = true; }
  $('playWordBtn').hidden = false;
  toggleImg($('imgWord'), w.imageWord);
  // 背面(來源無例句時以「—」表示,視為空)
  const hasEx = w.example && w.example.trim() && w.example.trim() !== '—';
  $('exampleText').textContent = hasEx ? w.example : '(此字無例句)';
  $('translationText').textContent = hasEx ? (w.translation || '') : '';
  $('playSentenceBtn').hidden = !w.audioSentence;
  toggleImg($('imgSentence'), w.imageSentence);
  // 來源標記
  const badge = $('srcBadge');
  if (w.audioWordSource === 'human') { badge.textContent = '🎙 真人'; badge.hidden = false; }
  else if (w.ipaSource === 'auto') { badge.textContent = '音標自動推定'; badge.hidden = false; }
  else badge.hidden = true;

  showFace(false);
  // 進度 / 計數 / 進度條
  updateMarkButtons();
  $('counter').textContent = `${state.pos + 1} / ${state.view.length}`;
  $('progressFill').style.width = ((state.pos + 1) / state.view.length * 100) + '%';
  LS.set(keyPos(state.book.book), state.pos);
  updateMediaMeta();
}

function toggleImg(el, src) {
  if (src) { el.src = src; el.hidden = false; el.onerror = () => (el.hidden = true); }
  else { el.hidden = true; el.removeAttribute('src'); }
}

function showFace(back) {
  state.flipped = back;
  $('cardFront').hidden = back;
  $('cardBack').hidden = !back;
}
function flip() { showFace(!state.flipped); if (state.flipped) beat(); }

function updateMarkButtons() {
  const st = state.progress[current().id];
  $('btnKnown').classList.toggle('marked-known', st === 'known');
  $('btnReview').classList.toggle('marked-review', st === 'review');
}

/* ================= 導覽 / 滑動 ================= */
function go(delta) {
  const n = state.view.length;
  if (!n) return;
  state.pos = (state.pos + delta + n) % n;
  const card = $('card');
  card.classList.remove('swipe-left', 'swipe-right');
  void card.offsetWidth;
  card.classList.add(delta > 0 ? 'swipe-left' : 'swipe-right');
  render();
}

function setupSwipe() {
  const card = $('card');
  let x0 = 0, y0 = 0, active = false;
  const EDGE = 28; // 避開 Safari 邊緣返回手勢
  card.addEventListener('touchstart', (e) => {
    const t = e.touches[0];
    if (t.clientX < EDGE || t.clientX > innerWidth - EDGE) { active = false; return; }
    x0 = t.clientX; y0 = t.clientY; active = true;
  }, { passive: true });
  card.addEventListener('touchend', (e) => {
    if (!active) return; active = false;
    const t = e.changedTouches[0];
    const dx = t.clientX - x0, dy = t.clientY - y0;
    if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.4) {
      stopAuto();
      go(dx < 0 ? 1 : -1);   // 左滑=下一個
    }
  }, { passive: true });
}

/* ================= 音訊 ================= */
const player = $('player');
let audioUnlocked = false;

function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  // 播一段極短無聲以解鎖 iOS 自動播放限制
  try {
    player.muted = true;
    player.play().catch(() => {});
    player.pause(); player.currentTime = 0; player.muted = false;
  } catch {}
}

function playSrc(src) {
  return new Promise((resolve) => {
    if (!src) return resolve(false);
    player.onended = null; player.onerror = null;
    player.src = src;
    player.playbackRate = state.settings.rate;
    const done = (ok) => { player.onended = null; player.onerror = null; resolve(ok); };
    player.onended = () => done(true);
    player.onerror = () => done(false);
    player.play().then(() => {}).catch(() => done(false));
  });
}

async function playWord(fromUser) {
  const w = current(); if (!w || !w.audioWord) { if (fromUser) toast('此單字尚無音檔'); return; }
  markPlaying($('playWordBtn'), true);
  await playSrc(w.audioWord);
  markPlaying($('playWordBtn'), false);
}
async function playSentence(fromUser) {
  const w = current(); if (!w || !w.audioSentence) { if (fromUser) toast('此例句尚無音檔'); return; }
  markPlaying($('playSentenceBtn'), true);
  await playSrc(w.audioSentence);
  markPlaying($('playSentenceBtn'), false);
}
function markPlaying(btn, on) { btn && btn.classList.toggle('playing', on); }

/* ================= 自動播放 ================= *
 * 以持久 <audio> 串接播放清單,'ended' 由 playSrc 的 Promise 接續。
 * readZh 用 speechSynthesis 唸中譯(次要、開螢幕時較可靠)。 */
async function startAuto() {
  unlockAudio();
  if (state.auto.on) return;
  state.auto.on = true;
  $('btnAuto').classList.add('on');
  $('btnAuto').textContent = '⏸ 停止';
  $('autobar').hidden = false;
  autoLoop();
}
function stopAuto() {
  if (!state.auto.on) return;
  state.auto.on = false;
  clearTimeout(state.auto.timer);
  try { player.pause(); } catch {}
  try { speechSynthesis.cancel(); } catch {}
  $('btnAuto').classList.remove('on');
  $('btnAuto').textContent = '▶ 自動';
  $('autobar').hidden = true;
}
function toggleAuto() { state.auto.on ? stopAuto() : startAuto(); }

function wait(sec) { return new Promise((r) => { state.auto.timer = setTimeout(r, sec * 1000); }); }

async function autoLoop() {
  while (state.auto.on) {
    const w = current();
    if (!w) break;
    setAutoNow(`${w.word}`);
    showFace(false);
    if (w.audioWord) { markPlaying($('playWordBtn'), true); await playSrc(w.audioWord); markPlaying($('playWordBtn'), false); }
    if (!state.auto.on) break;
    await wait(state.settings.gap * 0.6);
    if (state.settings.autoFlip) { showFace(true); beat(); }
    if (w.audioSentence) {
      setAutoNow(`${w.word} — 例句`);
      markPlaying($('playSentenceBtn'), true); await playSrc(w.audioSentence); markPlaying($('playSentenceBtn'), false);
    }
    if (!state.auto.on) break;
    if (state.settings.readZh && w.translation) { await speak(w.translation); }
    if (!state.auto.on) break;
    await wait(state.settings.gap);
    if (!state.auto.on) break;
    if (!state.settings.repeat) {
      if (state.pos >= state.view.length - 1) { stopAuto(); toast('已播完本組單字'); break; }
      state.pos += 1; render();
    } else { render(); }
  }
}

function setAutoNow(t) { $('autobarNow').textContent = t; }

function speak(text) {
  return new Promise((resolve) => {
    if (!('speechSynthesis' in window)) return resolve();
    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'zh-TW'; u.rate = state.settings.rate;
      let settled = false;
      const fin = () => { if (!settled) { settled = true; resolve(); } };
      u.onend = fin; u.onerror = fin;
      speechSynthesis.speak(u);
      setTimeout(fin, 4000); // 安全逾時(鎖屏可能不觸發)
    } catch { resolve(); }
  });
}

/* ================= MediaSession(鎖屏 / 控制中心) ================= */
function updateMediaMeta() {
  if (!('mediaSession' in navigator)) return;
  const w = current(); if (!w) return;
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: w.word,
      artist: w.example || '',
      album: `${state.book.name || ''} · ${w.unit}`,
      artwork: [
        { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
        { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
      ],
    });
  } catch {}
}
function setupMediaSession() {
  if (!('mediaSession' in navigator)) return;
  const ms = navigator.mediaSession;
  const set = (a, fn) => { try { ms.setActionHandler(a, fn); } catch {} };
  set('play', () => { if (!state.auto.on) startAuto(); else player.play().catch(() => {}); });
  set('pause', () => stopAuto());
  set('nexttrack', () => { stopAuto(); go(1); });
  set('previoustrack', () => { stopAuto(); go(-1); });
}

/* ================= 進度標記 ================= */
function mark(kind) {
  const w = current(); if (!w) return;
  if (state.progress[w.id] === kind) delete state.progress[w.id];
  else state.progress[w.id] = kind;
  LS.set(keyProgress(state.book.book), state.progress);
  updateMarkButtons();
  renderUnitList();
}

/* ================= 單元清單 / 下載 ================= */
function renderUnitList() {
  const ul = $('unitList'); ul.innerHTML = '';
  state.units.forEach((u) => {
    const li = document.createElement('li');
    li.className = 'unit-item' + (state.filter.unit === u.name ? ' current' : '');
    const known = u.words.filter((w) => state.progress[w.id] === 'known').length;
    const main = document.createElement('div');
    main.className = 'unit-main';
    main.innerHTML = `<div class="unit-title">${esc(u.name)}</div>
      <div class="unit-sub">${u.count} 字 · 已會 ${known}</div>`;
    main.onclick = () => { state.filter.unit = u.name; state.pos = 0; rebuildView(); render(); renderUnitList(); closePanels(); };
    const dl = document.createElement('button');
    dl.className = 'unit-dl' + (state.downloaded[u.name] ? ' done' : '');
    dl.textContent = state.downloaded[u.name] ? '已下載' : '下載';
    dl.onclick = (e) => { e.stopPropagation(); downloadUnit(u, dl); };
    li.appendChild(main); li.appendChild(dl); ul.appendChild(li);
  });
}

function unitMediaUrls(u) {
  const urls = [];
  u.words.forEach((w) => {
    if (w.audioWord) urls.push(w.audioWord);
    if (w.audioSentence) urls.push(w.audioSentence);
    if (w.imageWord) urls.push(w.imageWord);
    if (w.imageSentence) urls.push(w.imageSentence);
  });
  return urls;
}

async function downloadUnit(u, btn) {
  if (!('caches' in window)) return toast('此瀏覽器不支援離線快取');
  const urls = unitMediaUrls(u);
  if (!urls.length) return toast('此單元尚無音檔');
  btn.classList.add('busy'); btn.disabled = true;
  try {
    const cache = await caches.open(AUDIO_CACHE);
    let done = 0;
    for (const url of urls) {
      try {
        const res = await fetch(url, { cache: 'no-cache' });
        if (res.ok) await cache.put(url, res.clone());
      } catch {}
      done++;
      btn.textContent = `${Math.round(done / urls.length * 100)}%`;
    }
    state.downloaded[u.name] = true;
    LS.set(keyDl(state.book.book), state.downloaded);
    btn.classList.remove('busy'); btn.classList.add('done');
    btn.textContent = '已下載'; btn.disabled = false;
    toast(`已下載「${u.name}」音檔/圖片(${urls.length} 檔)`);
    updateStorageLine();
  } catch (e) {
    btn.classList.remove('busy'); btn.disabled = false; btn.textContent = '下載';
    toast('下載失敗,可能空間不足');
  }
}

async function clearAudio() {
  if (!('caches' in window)) return;
  await caches.delete(AUDIO_CACHE);
  state.downloaded = {};
  state.manifest.books.forEach((b) => LS.set(keyDl(b.book), {}));
  renderUnitList(); updateStorageLine();
  toast('已清除所有離線音檔/圖片');
}

async function updateStorageLine() {
  const el = $('storageLine'); if (!el) return;
  let txt = '';
  try {
    if (navigator.storage && navigator.storage.estimate) {
      const { usage } = await navigator.storage.estimate();
      txt = `App 已用約 ${(usage / 1048576).toFixed(1)} MB`;
    }
  } catch {}
  const n = Object.values(state.downloaded).filter(Boolean).length;
  el.textContent = `已下載單元:${n} 個${txt ? ' · ' + txt : ''}`;
}

/* ================= 搜尋 ================= */
function runSearch(q) {
  const box = $('searchResults'); box.innerHTML = '';
  q = q.trim().toLowerCase();
  if (!q) return;
  const hits = state.words.filter((w) =>
    w.word.toLowerCase().includes(q) ||
    (w.translation || '').toLowerCase().includes(q) ||
    (w.example || '').toLowerCase().includes(q)).slice(0, 40);
  if (!hits.length) { box.innerHTML = '<li class="search-empty">找不到符合的單字</li>'; return; }
  hits.forEach((w) => {
    const li = document.createElement('li');
    li.className = 'search-item';
    li.innerHTML = `<div class="sw">${esc(w.word)} <span class="st">${esc((w.pos || []).join(' '))}</span></div>
      <div class="st">${esc(w.translation || '')} · ${esc(w.unit)}</div>`;
    li.onclick = () => {
      state.filter = { unit: null, status: 'all' }; rebuildView();
      const idx = state.view.findIndex((x) => x.id === w.id);
      state.pos = idx < 0 ? 0 : idx; render(); renderUnitList(); closePanels();
    };
    box.appendChild(li);
  });
}

/* ================= UI 綁定 ================= */
function bindStaticUI() {
  // 卡片:點空白翻面;點字播音
  $('card').addEventListener('click', (e) => {
    if (e.target.closest('.word,.example,.play-word-btn,.play-sentence-btn,.card-img')) return;
    unlockAudio(); flip();
  });
  $('wordText').addEventListener('click', () => { unlockAudio(); playWord(true); });
  $('exampleText').addEventListener('click', () => { unlockAudio(); playSentence(true); });
  $('playWordBtn').addEventListener('click', (e) => { e.stopPropagation(); unlockAudio(); playWord(true); });
  $('playSentenceBtn').addEventListener('click', (e) => { e.stopPropagation(); unlockAudio(); playSentence(true); });

  $('btnPrev').onclick = () => { unlockAudio(); stopAuto(); go(-1); };
  $('btnNext').onclick = () => { unlockAudio(); stopAuto(); go(1); };
  $('btnKnown').onclick = () => mark('known');
  $('btnReview').onclick = () => mark('review');
  $('btnAuto').onclick = () => { unlockAudio(); toggleAuto(); };
  $('autobarStop').onclick = () => stopAuto();

  // 面板開關
  $('btnUnits').onclick = () => openPanel('panelUnits');
  $('btnSearch').onclick = () => { openPanel('panelSearch'); setTimeout(() => $('searchInput').focus(), 250); };
  $('btnSettings').onclick = () => { openPanel('panelSettings'); updateStorageLine(); };
  $('scrim').onclick = closePanels;
  document.querySelectorAll('[data-close]').forEach((b) => (b.onclick = closePanels));

  // 篩選 chips
  document.querySelectorAll('#filterChips .chip').forEach((c) => {
    c.onclick = () => {
      document.querySelectorAll('#filterChips .chip').forEach((x) => x.classList.remove('active'));
      c.classList.add('active');
      state.filter.status = c.dataset.filter; state.pos = 0; rebuildView(); render();
    };
  });

  $('bookSelect').onchange = (e) => loadBook(e.target.value);
  $('searchInput').addEventListener('input', (e) => runSearch(e.target.value));

  // 設定:字級 / 語速 / 間隔 segmented
  segBind('fontSeg', 'font', (v) => { state.settings.font = +v; applyFont(); saveSettings(); });
  segBind('rateSeg', 'rate', (v) => { state.settings.rate = +v; saveSettings(); });
  segBind('gapSeg', 'gap', (v) => { state.settings.gap = +v; saveSettings(); });
  bindSwitch('setFlip', 'autoFlip');
  bindSwitch('setReadZh', 'readZh');
  bindSwitch('setRepeat', 'repeat');
  $('btnClearAudio').onclick = clearAudio;

  setupSwipe();
  setupMediaSession();
  showInstallHint();

  // 鍵盤(桌機預覽方便)
  document.addEventListener('keydown', (e) => {
    if (document.querySelector('.panel:not([hidden])')) return;
    if (e.key === 'ArrowLeft') { stopAuto(); go(-1); }
    else if (e.key === 'ArrowRight') { stopAuto(); go(1); }
    else if (e.key === ' ') { e.preventDefault(); unlockAudio(); flip(); }
    else if (e.key === 'Enter') { unlockAudio(); playWord(true); }
  });
}

function segBind(id, keyName, cb) {
  const seg = $(id); if (!seg) return;
  seg.querySelectorAll('button').forEach((b) => {
    b.onclick = () => {
      seg.querySelectorAll('button').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      cb(b.dataset[keyName]);
    };
  });
}
function bindSwitch(id, key) {
  const el = $(id); if (!el) return;
  el.checked = !!state.settings[key];
  el.onchange = () => { state.settings[key] = el.checked; saveSettings(); };
}

function openPanel(id) {
  closePanels();
  $('scrim').hidden = false;
  $(id).hidden = false;
  if (id === 'panelUnits') { renderUnitList(); syncFilterChips(); }
}
function closePanels() {
  $('scrim').hidden = true;
  document.querySelectorAll('.panel').forEach((p) => (p.hidden = true));
}
function syncFilterChips() {
  document.querySelectorAll('#filterChips .chip').forEach((c) =>
    c.classList.toggle('active', c.dataset.filter === state.filter.status));
}

function buildBookSelect() {
  const sel = $('bookSelect'); sel.innerHTML = '';
  state.manifest.books.forEach((b) => {
    const o = document.createElement('option');
    o.value = b.book; o.textContent = `${b.name || b.book}(${b.count}字)`;
    sel.appendChild(o);
  });
}

/* ================= 設定 / 字級 ================= */
function loadSettings() {
  const s = LS.get('vocab.settings', null);
  if (s) Object.assign(state.settings, s);
  // 反映到 UI 的 active 狀態(於 DOM ready 後)
  document.addEventListener('DOMContentLoaded', reflectSettings);
  if (document.readyState !== 'loading') reflectSettings();
}
function reflectSettings() {
  markSeg('fontSeg', 'font', state.settings.font);
  markSeg('rateSeg', 'rate', state.settings.rate);
  markSeg('gapSeg', 'gap', state.settings.gap);
}
function markSeg(id, key, val) {
  const seg = $(id); if (!seg) return;
  seg.querySelectorAll('button').forEach((b) =>
    b.classList.toggle('active', +b.dataset[key] === +val));
}
function saveSettings() { LS.set('vocab.settings', state.settings); }
function applyFont() { document.documentElement.style.setProperty('--fs', state.settings.font); }

/* ================= Service Worker ================= */
function registerSW() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('sw.js').catch(() => {});
    });
  }
}

/* ================= 小工具 ================= */
function clamp(n, a, b) { return Math.max(a, Math.min(b, isNaN(n) ? a : n)); }
function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
function beat() { if ('vibrate' in navigator) try { navigator.vibrate(8); } catch {} }
let toastT;
function toast(msg) {
  let el = document.querySelector('.toast');
  if (el) el.remove();
  el = document.createElement('div'); el.className = 'toast'; el.textContent = msg;
  document.body.appendChild(el);
  clearTimeout(toastT);
  toastT = setTimeout(() => el.remove(), 2200);
}
function fatal(msg) {
  document.body.innerHTML = `<div style="padding:40px;color:#f0f4ff;font-size:18px;line-height:1.6">
    <h2>載入失敗</h2><p>${esc(msg)}</p>
    <p style="color:#9aa6c4">請用本機伺服器(非 file://)開啟,或確認已部署到 HTTPS。</p></div>`;
}
function showInstallHint() {
  const el = $('installHint'); if (!el) return;
  const standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  if (standalone) el.textContent = '✓ 已從主畫面開啟(standalone),離線音檔會可靠保留。';
  else if (isIOS) el.textContent = '提示:點 Safari 分享鈕 → 「加入主畫面」,再從主畫面開啟,離線最穩定。';
  else el.textContent = '提示:可將本頁「安裝 / 加入主畫面」當 App 用。';
}
