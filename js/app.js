/* ================= 背單字 App — vanilla JS (v2 schema) ================= *
 * 資料:data/index.json (manifest) + data/<book>.json
 * 單字 schema(v2):word / ipa / ipaRaw / pos[] / gloss / verbForms /
 *   examples[{en,zh,audio,image}] / notes[] / audioWord / imageWord /
 *   page / unit(「第 N 頁」);頂層另含 meta 與 pageNotes{頁碼:[...]}。
 * 功能:卡片瀏覽 / 翻面(多例句)/ 左右滑動 / 單字+逐句發音 / 頁篩選 /
 *       搜尋 / 進度標記 / 自動播放(MediaSession 鎖屏連播)/ 分頁離線下載
 * ============================================================ */
'use strict';

const AUDIO_CACHE = 'vocab-audio';
const $ = (id) => document.getElementById(id);

/* ---------- 全域狀態 ---------- */
const state = {
  manifest: null,
  book: null,          // 目前 book meta
  words: [],           // 目前 book 全部單字
  pageNotes: {},       // { 頁碼字串: [補充字串...] }
  units: [],           // [{name, count, words}]
  view: [],            // 篩選後的單字陣列
  pos: 0,              // view 內目前索引
  flipped: false,
  filter: { unit: null, status: 'all' },
  progress: {},        // { id: 'known' | 'review' }
  downloaded: {},      // { unitName: true }
  settings: {
    font: 1, rate: 1, autoFlip: true, readZh: false, repeat: false, gap: 0.9
  },
  auto: { on: false, timer: null },
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
  await reconcileDataVersion();   // 資料改版 → 自動清掉舊的離線音檔/圖片快取
  const firstBook = state.manifest.books[0].book;
  await loadBook(firstBook);
}

/* 偵測資料版本:與上次不同時,清除 AUDIO_CACHE(舊音檔/圖片可能對不上新內容)
 * 並重設各書的「已下載」狀態,提示使用者重新下載。首次安裝不提示。 */
async function reconcileDataVersion() {
  const cur = state.manifest.version;
  if (cur == null) return;                       // 無版本欄位則不處理
  const prev = LS.get('vocab.dataVersion', null);
  if (prev === cur) return;                       // 版本相同,不動作
  try { if ('caches' in window) await caches.delete(AUDIO_CACHE); } catch {}
  try { (state.manifest.books || []).forEach((b) => LS.set(keyDl(b.book), {})); } catch {}
  state.downloaded = {};
  LS.set('vocab.dataVersion', cur);
  if (prev != null) {                             // 曾有舊版才提示(非首次安裝)
    setTimeout(() => toast('資料已更新,已清除舊離線音檔,請於設定重新下載'), 900);
  }
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
  const isSup = entry.type === 'supplement' || Array.isArray(data.phrases);
  if (isSup) {
    // 直接載入某補充本(words + phrases 合併,各自帶 kind)
    state.bookType = 'supplement';
    state.words = [...(data.words || []), ...(data.phrases || [])];
    state.pageNotes = {};
  } else {
    // 主本:把所有「補充本」的單元一併併入(接在頁數之後,同一個單元清單)
    state.bookType = 'vocab';
    state.words = [...(data.words || [])];
    state.pageNotes = data.pageNotes || {};
    for (const b of state.manifest.books) {
      if (b.type === 'supplement') {
        try {
          const sd = await fetchJSON(b.file);
          state.words.push(...(sd.words || []), ...(sd.phrases || []));
        } catch (e) { /* 補充本載入失敗不影響主本 */ }
      }
    }
  }
  // 每頁第一個字的 id(頁筆記只在該字顯示一次,避免同頁每張卡重複)
  state.pageFirstId = {};
  state.words.forEach((w) => {
    if (w.page != null && state.pageFirstId[w.page] === undefined) state.pageFirstId[w.page] = w.id;
  });
  state.progress = LS.get(keyProgress(bookCode), {});
  state.downloaded = LS.get(keyDl(bookCode), {});
  buildUnits();
  state.filter = { unit: null, status: 'all' };
  rebuildView();
  state.pos = clamp(LS.get(keyPos(bookCode), 0), 0, state.view.length - 1);
  $('bookName').textContent = state.book.name || bookCode;
  const sel = $('bookSelect'); if (sel) sel.value = bookCode;
  renderUnitList();
  render();
  updateStorageLine();
}

/* ================= 單元(頁)/ 篩選 ================= */
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
  parts.push(state.filter.unit ? state.filter.unit : '全部');
  if (state.filter.status === 'review') parts.push('待複習');
  else if (state.filter.status === 'unknown') parts.push('未標記');
  $('unitName').textContent = parts.join(' · ');
}

/* ================= 卡片渲染 ================= */
function current() { return state.view[state.pos]; }

// 例句音檔路徑:優先用資料內 examples[i].audio;無則回退慣例路徑(供已下載舊檔)
function exampleAudio(w, i) {
  const ex = (w.examples || [])[i];
  if (ex && ex.audio) return ex.audio;
  return null;
}

function render() {
  const w = current();
  if (!w) return;

  // 依卡片類型填入正反面內容
  if (w.kind === 'word') fillSupWordCard(w);
  else if (w.kind === 'phrase') fillSupPhraseCard(w);
  else fillMainCard(w);

  /* ---- 來源標記 ---- */
  const badge = $('srcBadge');
  if (w.audioWordSource === 'human') { badge.textContent = '🎙 真人'; badge.hidden = false; }
  else badge.hidden = true;

  showFace(false);
  // 進度 / 計數 / 進度條
  updateMarkButtons();
  $('counter').textContent = `${state.pos + 1} / ${state.view.length}`;
  $('progressFill').style.width = ((state.pos + 1) / state.view.length * 100) + '%';
  LS.set(keyPos(state.book.book), state.pos);
  updateMediaMeta();
}

/* ---- 主本卡片(單字:音標 / 多詞性 / 多例句 / 三態 / 筆記)---- */
function fillMainCard(w) {
  // 頁級補充(📝):只在該頁「第一個字」顯示一次,避免同頁每張卡重複
  const pn = state.pageNotes[String(w.page)];
  const pnEl = $('pageNote');
  if (pn && pn.length && state.pageFirstId[w.page] === w.id) {
    pnEl.innerHTML = `<span class="page-note-tag">本頁補充</span>` +
      pn.map((t) => `📝 ${esc(t)}`).join('<br>');
    pnEl.hidden = false;
  } else { pnEl.hidden = true; pnEl.innerHTML = ''; }

  setPosTags(w.pos || []);
  $('wordText').textContent = w.word;
  const ipa = $('ipaText');
  const ipaStr = w.ipaRaw || (w.ipa ? `/${w.ipa}/` : '');
  if (ipaStr) { ipa.textContent = ipaStr; ipa.hidden = false; }
  else { ipa.hidden = true; }
  $('playWordBtn').hidden = !w.audioWord;
  toggleImg($('imgWord'), w.imageWord);

  // 多詞性:gloss 以 ' / ' 分段,每個詞性分行顯示
  $('glossText').innerHTML = formatGloss(w.gloss);
  const vf = $('verbForms');
  if (w.verbForms) { vf.textContent = `動詞三態:${w.verbForms}`; vf.hidden = false; }
  else { vf.hidden = true; }
  renderExamples(w);
  const notesEl = $('wordNotes');
  if (w.notes && w.notes.length) {
    notesEl.innerHTML = w.notes.map((n) => `📝 ${esc(n)}`).join('<br>');
    notesEl.hidden = false;
  } else { notesEl.hidden = true; notesEl.innerHTML = ''; }
}

/* ---- 補充本:詞類變化(word)---- 正面 word/pos;背面 意思 + 衍生詞 ---- */
function fillSupWordCard(w) {
  $('pageNote').hidden = true;
  setPosTags(w.pos ? [w.pos] : []);
  $('wordText').textContent = w.word;
  $('ipaText').hidden = true;
  $('playWordBtn').hidden = !w.audioWord;
  toggleImg($('imgWord'), w.imageWord);

  $('glossText').innerHTML = w.meaning
    ? `<span class="gloss-line">${esc(w.meaning)}</span>` : '';
  // 搭配詞(Unit 4–6 單字補充才有)重用 verbForms 那一行顯示
  const vf = $('verbForms');
  if (w.collocations && w.collocations.length) {
    vf.textContent = `搭配詞:${w.collocations.join(' / ')}`; vf.hidden = false;
  } else { vf.hidden = true; }
  $('wordNotes').hidden = true;
  // 衍生詞列到 examplesList(重用結構)
  const ul = $('examplesList'); ul.innerHTML = '';
  (w.derivatives || []).forEach((d) => {
    const li = document.createElement('li');
    li.className = 'ex-item deriv-item';
    const head = document.createElement('div');
    head.className = 'deriv-form';
    head.innerHTML = `${d.audio ? '🔊 ' : ''}${esc(d.form || '')}`;
    if (d.audio) {
      head.classList.add('playable');
      head.addEventListener('click', (e) => { e.stopPropagation(); unlockAudio(); playSrc(d.audio); });
    }
    li.appendChild(head);
    if (d.detail) {
      const det = document.createElement('div');
      det.className = 'ex-zh'; det.textContent = d.detail;
      li.appendChild(det);
    }
    ul.appendChild(li);
  });
}

/* ---- 補充本:片語(phrase)---- 正面 phrase;背面 中文 + 英定義 + 例句 ---- */
function fillSupPhraseCard(w) {
  $('pageNote').hidden = true;
  setPosTags(w.lesson ? [`Lesson ${w.lesson}`] : []);
  $('wordText').textContent = w.phrase;
  $('ipaText').hidden = true;
  $('playWordBtn').hidden = !w.audioPhrase;
  toggleImg($('imgWord'), null);

  $('glossText').innerHTML = w.meaning
    ? `<span class="gloss-line">${esc(w.meaning)}</span>` : '';
  $('verbForms').hidden = true;
  $('wordNotes').hidden = true;
  const ul = $('examplesList'); ul.innerHTML = '';
  if (w.definition) {
    const li = document.createElement('li');
    li.className = 'ex-item';
    li.innerHTML = `<div class="def-label">英文定義</div><div class="ex-def" lang="en">${esc(w.definition)}</div>`;
    ul.appendChild(li);
  }
  if (w.example) {
    const li = document.createElement('li');
    li.className = 'ex-item';
    const en = document.createElement('button');
    en.className = 'ex-en'; en.lang = 'en';
    en.innerHTML = `${w.audioExample ? '🔊 ' : ''}${esc(w.example)}`;
    en.addEventListener('click', (e) => {
      e.stopPropagation(); unlockAudio();
      if (w.audioExample) { if (!state.flipped) showFace(true); markPlaying(en, true); playSrc(w.audioExample).then(() => markPlaying(en, false)); }
      else toast('此例句尚無音檔');
    });
    li.appendChild(en);
    if (w.exampleZh) {
      const zh = document.createElement('div');
      zh.className = 'ex-zh'; zh.textContent = w.exampleZh;
      li.appendChild(zh);
    }
    ul.appendChild(li);
  }
}

function setPosTags(tags) {
  const posRow = $('posRow');
  posRow.innerHTML = '';
  tags.forEach((p) => {
    const s = document.createElement('span');
    s.className = 'pos-tag'; s.textContent = p; posRow.appendChild(s);
  });
}

function formatGloss(gloss) {
  const segs = (gloss || '').split(' / ').filter((s) => s.trim());
  return segs.map((seg) => {
    const m = seg.trim().match(/^([A-Za-z]+\.)\s*(.*)$/);
    return m
      ? `<span class="gloss-line"><span class="gloss-pos">${esc(m[1])}</span>${esc(m[2])}</span>`
      : `<span class="gloss-line">${esc(seg.trim())}</span>`;
  }).join('');
}

function renderExamples(w) {
  const ul = $('examplesList');
  ul.innerHTML = '';
  const exs = w.examples || [];
  if (!exs.length) {
    const li = document.createElement('li');
    li.className = 'ex-empty';
    li.textContent = '(此字無例句)';
    ul.appendChild(li);
    return;
  }
  exs.forEach((ex, i) => {
    const li = document.createElement('li');
    li.className = 'ex-item';
    const hasAudio = !!exampleAudio(w, i);
    const en = document.createElement('button');
    en.className = 'ex-en';
    en.lang = 'en';
    en.dataset.i = i;
    en.innerHTML = `${hasAudio ? '🔊 ' : ''}${esc(ex.en || '')}`;
    en.setAttribute('aria-label', '播放例句發音');
    en.addEventListener('click', (e) => { e.stopPropagation(); unlockAudio(); playExample(i, true); });
    li.appendChild(en);
    if (ex.zh) {
      const zh = document.createElement('div');
      zh.className = 'ex-zh'; zh.textContent = ex.zh;
      li.appendChild(zh);
    }
    if (ex.image) {
      const img = document.createElement('img');
      img.className = 'card-img ex-img'; img.alt = '';
      img.src = ex.image; img.onerror = () => (img.hidden = true);
      li.appendChild(img);
    }
    ul.appendChild(li);
  });
}

function toggleImg(el, src) {
  if (src) { el.src = src; el.hidden = false; el.onerror = () => (el.hidden = true); }
  else { el.hidden = true; el.removeAttribute('src'); }
}

function showFace(back) {
  state.flipped = back;
  $('cardFront').hidden = back;
  $('cardBack').hidden = !back;
  if (back) $('backScroll').scrollTop = 0;
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

function headwordAudio(w) { return w ? (w.audioWord || w.audioPhrase || null) : null; }
function headwordText(w) { return w ? (w.word || w.phrase || '') : ''; }

async function playWord(fromUser) {
  const w = current(); const src = headwordAudio(w);
  if (!src) { if (fromUser) toast('尚無音檔'); return; }
  markPlaying($('playWordBtn'), true);
  await playSrc(src);
  markPlaying($('playWordBtn'), false);
}
async function playExample(i, fromUser) {
  const w = current(); if (!w) return;
  const src = exampleAudio(w, i);
  if (!src) { if (fromUser) toast('此例句尚無音檔'); return; }
  if (!state.flipped) showFace(true);
  const btn = $('examplesList').querySelector(`.ex-en[data-i="${i}"]`);
  markPlaying(btn, true);
  await playSrc(src);
  markPlaying(btn, false);
}
function markPlaying(btn, on) { btn && btn.classList.toggle('playing', on); }

/* ================= 自動播放 ================= *
 * 以持久 <audio> 串接:單字 → 逐例句。readZh 用 speechSynthesis 唸中譯。 */
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

// 一張卡在「主字發音」後要連播的段落:主本=各例句;片語=例句;詞類變化=有音檔的衍生詞
function autoSegments(w) {
  if (w.kind === 'phrase') return w.audioExample ? [{ src: w.audioExample, zh: w.exampleZh }] : [];
  if (w.kind === 'word') return (w.derivatives || []).filter((d) => d.audio).map((d) => ({ src: d.audio }));
  return (w.examples || []).map((e) => ({ src: e.audio, zh: e.zh })).filter((s) => s.src);
}

async function autoLoop() {
  while (state.auto.on) {
    const w = current();
    if (!w) break;
    setAutoNow(headwordText(w));
    showFace(false);
    const head = headwordAudio(w);
    if (head) { markPlaying($('playWordBtn'), true); await playSrc(head); markPlaying($('playWordBtn'), false); }
    if (!state.auto.on) break;
    await wait(state.settings.gap * 0.6);
    if (state.settings.autoFlip) { showFace(true); beat(); }

    // 逐段朗讀(例句/片語例句;含中譯選項)
    const segs = autoSegments(w);
    for (let i = 0; i < segs.length; i++) {
      if (!state.auto.on) break;
      setAutoNow(`${headwordText(w)} — ${i + 1}/${segs.length}`);
      await playSrc(segs[i].src);
      if (!state.auto.on) break;
      if (state.settings.readZh && segs[i].zh) { await speak(segs[i].zh); }
      if (i < segs.length - 1) await wait(state.settings.gap * 0.5);
    }
    if (!state.auto.on) break;
    await wait(state.settings.gap);
    if (!state.auto.on) break;
    if (!state.settings.repeat) {
      if (state.pos >= state.view.length - 1) { stopAuto(); toast('已播完本組'); break; }
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
  const firstEx = (w.examples || [])[0];
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: headwordText(w),
      artist: (firstEx && firstEx.en) || w.example || w.gloss || w.meaning || '',
      album: `${state.book.name || ''} · ${w.unit || ''}`,
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

/* ================= 單元(頁)清單 / 下載 ================= */
function renderUnitList() {
  const ul = $('unitList'); ul.innerHTML = '';
  let supHeaderDone = false;
  state.units.forEach((u) => {
    // 補充教材(含 kind 的項目)前插一條分隔標題
    const isSup = !!(u.words[0] && u.words[0].kind);
    if (isSup && !supHeaderDone) {
      const h = document.createElement('li');
      h.className = 'unit-section'; h.textContent = '補充教材';
      ul.appendChild(h); supHeaderDone = true;
    }
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
    if (w.imageWord) urls.push(w.imageWord);
    (w.examples || []).forEach((ex) => {
      if (ex.audio) urls.push(ex.audio);
      if (ex.image) urls.push(ex.image);
    });
  });
  return urls;
}

async function downloadUnit(u, btn) {
  if (!('caches' in window)) return toast('此瀏覽器不支援離線快取');
  const urls = unitMediaUrls(u);
  if (!urls.length) return toast('此頁尚無音檔');
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
  el.textContent = `已下載頁數:${n} 頁${txt ? ' · ' + txt : ''}`;
}

/* ================= 搜尋 ================= */
function runSearch(q) {
  const box = $('searchResults'); box.innerHTML = '';
  q = q.trim().toLowerCase();
  if (!q) return;
  const hits = state.words.filter((w) => {
    const head = headwordText(w).toLowerCase();
    if (head.includes(q)) return true;
    if ((w.gloss || '').toLowerCase().includes(q)) return true;
    if ((w.meaning || '').toLowerCase().includes(q)) return true;
    if ((w.definition || '').toLowerCase().includes(q)) return true;
    if ((w.example || '').toLowerCase().includes(q)) return true;
    if ((w.derivatives || []).some((d) => (d.form || '').toLowerCase().includes(q))) return true;
    return (w.examples || []).some((ex) =>
      (ex.en || '').toLowerCase().includes(q) || (ex.zh || '').toLowerCase().includes(q));
  }).slice(0, 40);
  if (!hits.length) { box.innerHTML = '<li class="search-empty">找不到符合的項目</li>'; return; }
  hits.forEach((w) => {
    const li = document.createElement('li');
    li.className = 'search-item';
    const posStr = Array.isArray(w.pos) ? w.pos.join(' ') : (w.pos || '');
    const sub = w.gloss || w.meaning || '';
    li.innerHTML = `<div class="sw">${esc(headwordText(w))} <span class="st">${esc(posStr)}</span></div>
      <div class="st">${esc(sub)} · ${esc(w.unit || '')}</div>`;
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
  // 卡片:點空白翻面;例句的點擊在 renderExamples 內各自綁定
  $('card').addEventListener('click', (e) => {
    if (e.target.closest('.word,.ex-en,.play-word-btn,.card-img')) return;
    unlockAudio(); flip();
  });
  $('wordText').addEventListener('click', () => { unlockAudio(); playWord(true); });
  $('playWordBtn').addEventListener('click', (e) => { e.stopPropagation(); unlockAudio(); playWord(true); });

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
  // 補充本已併入主本單元清單,選單只列出主(vocab)本
  const vocabBooks = state.manifest.books.filter((b) => b.type !== 'supplement');
  vocabBooks.forEach((b) => {
    const o = document.createElement('option');
    const total = b.count != null ? `${b.count}字` : '';
    o.value = b.book; o.textContent = `${b.name || b.book}${total ? '(' + total + ')' : ''}`;
    sel.appendChild(o);
  });
  // 只有一本可選時,隱藏整列選單(避免無意義的下拉)
  const row = sel.closest('.book-select-row');
  if (row) row.hidden = vocabBooks.length <= 1;
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
