/* ================= 背單字 App — Service Worker =================
 * 策略:
 *  - App 殼與文字資料(html/css/js/manifest/icons/data/*.json):安裝時 precache,
 *    離線一律可瀏覽(cache-first)。
 *  - 音檔(audio/*.mp3):不自動全部 precache(iOS 配額有限);改由 App 端
 *    「分單元下載」寫入 AUDIO_CACHE。此處對音檔採 cache-first,快取沒有才走網路。
 * 版本升級:改 SHELL_VERSION 觸發 precache 更新,舊殼快取自動清除;音檔快取保留。
 * ============================================================ */
const SHELL_VERSION = 'vocab-shell-v1';
const AUDIO_CACHE = 'vocab-audio';

const SHELL_ASSETS = [
  './',
  'index.html',
  'css/styles.css',
  'js/app.js',
  'manifest.json',
  'data/index.json',
  'data/G1-S1.json',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/icon-512-maskable.png',
  'icons/apple-touch-icon-180.png',
  'icons/favicon-32.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_VERSION);
    // 個別加入,單一資源失敗不整批中斷
    await Promise.all(SHELL_ASSETS.map(async (url) => {
      try { await cache.add(new Request(url, { cache: 'reload' })); } catch (e) {}
    }));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => {
      if (k !== SHELL_VERSION && k !== AUDIO_CACHE) return caches.delete(k);
    }));
    await self.clients.claim();
  })());
});

function isAudio(url) {
  return url.pathname.includes('/audio/') && url.pathname.endsWith('.mp3');
}
function isImage(url) {
  return url.pathname.includes('/images/');
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // 只管同源

  // 音檔:先看 AUDIO_CACHE(分單元下載寫入),沒有再走網路(線上可播,不自動快取)
  if (isAudio(url)) {
    event.respondWith((async () => {
      const cached = await caches.match(req, { cacheName: AUDIO_CACHE });
      if (cached) return cached;
      try { return await fetch(req); }
      catch { return new Response('', { status: 504, statusText: 'offline-audio-not-downloaded' }); }
    })());
    return;
  }

  // 圖片(Phase 2):與音檔同策略——先看 AUDIO_CACHE(分單元下載寫入),
  // 沒有再走網路(線上可顯示,不自動快取,配額由「分單元下載」控管)
  if (isImage(url)) {
    event.respondWith((async () => {
      const cached = await caches.match(req, { cacheName: AUDIO_CACHE });
      if (cached) return cached;
      try { return await fetch(req); }
      catch { return new Response('', { status: 504, statusText: 'offline-image-not-downloaded' }); }
    })());
    return;
  }

  // App 殼與資料:cache-first,背景更新(stale-while-revalidate)
  event.respondWith((async () => {
    const cached = await caches.match(req);
    const network = fetch(req).then((res) => {
      if (res && res.ok) caches.open(SHELL_VERSION).then((c) => c.put(req, res.clone()));
      return res;
    }).catch(() => null);
    if (cached) { network; return cached; }
    const res = await network;
    if (res) return res;
    // 導覽請求離線且未快取 → 回首頁殼
    if (req.mode === 'navigate') {
      const shell = await caches.match('index.html');
      if (shell) return shell;
    }
    return new Response('offline', { status: 504 });
  })());
});
