/* C-PICK 참석·정산(번개게임·번개회식) 서비스 워커
   - 앱 화면(HTML·아이콘)은 캐시해서 카톡 인앱·지하주차장에서도 열리게
   - 구글 시트(Apps Script) 통신은 캐시하지 않고 그대로 보냄
   - 화면을 고칠 때는 아래 VERSION 을 올리면 기기에 새 화면이 내려간다 */
const VERSION = 'cpick-attendance-v6';
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;      // Apps Script 쪽은 손대지 않음

  const isDoc = req.mode === 'navigate' || (req.headers.get('accept') || '').indexOf('text/html') >= 0;
  if (isDoc) {
    /* 화면은 새 것을 먼저 시도하고, 실패하면 캐시본으로 */
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => caches.match(req).then((hit) => hit || caches.match('./index.html')))
    );
    return;
  }
  e.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
      return res;
    }).catch(() => hit))
  );
});
