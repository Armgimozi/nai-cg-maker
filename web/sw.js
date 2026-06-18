/* 단부루 사전 PWA 서비스워커.
 * 정적 앱 셸(HTML/CSS/JS/아이콘)은 캐시 우선으로 오프라인에서도 열리게 하고,
 * /api/* 동적 요청과 비-GET 은 항상 네트워크로 보낸다(캐시하지 않음).
 * 셸 파일을 고치면 CACHE 버전을 올려 새로 받게 한다.
 */
const CACHE = "danbooru-dict-v1";
const SHELL = [
  "./", "./index.html", "./style.css", "./app.js",
  "./manifest.webmanifest", "./icon-192.png", "./icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;                    // API POST 등은 그대로 통과
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;          // 외부(폰트 등)는 브라우저에 맡김
  if (url.pathname.startsWith("/api/")) return;        // 동적 API 는 캐시 안 함

  // 정적: 캐시 우선 → 없으면 네트워크(받아서 캐시) → 실패 시 index 폴백
  e.respondWith(
    caches.match(req, { ignoreSearch: true }).then((hit) =>
      hit || fetch(req).then((res) => {
        if (res.ok && res.type === "basic") {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => { });
        }
        return res;
      }).catch(() => caches.match("./index.html", { ignoreSearch: true }))
    )
  );
});
