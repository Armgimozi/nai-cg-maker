/* 단부루 사전 PWA 서비스워커 — 네트워크 우선(network-first).
 *
 * 이 앱은 검색이 전부 서버(/api/dict/*)를 거치므로 '오프라인 캐시'의 실익이 적고,
 * 캐시 우선이면 새 배포가 폰에 안 들어오는 문제가 생긴다. 그래서:
 *   - 온라인이면 항상 네트워크에서 최신을 받아 보여주고(=배포 즉시 반영), 사본만 캐시.
 *   - 네트워크 실패(오프라인)일 때만 마지막 캐시로 폴백.
 *   - /api/* 와 비-GET·외부 도메인은 건드리지 않는다.
 * 새 워커는 즉시 활성(skipWaiting+claim)되고, 페이지가 controllerchange 로 새로고침한다.
 */
const CACHE = "danbooru-dict-v2";

self.addEventListener("install", () => self.skipWaiting());

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
  if (url.pathname.startsWith("/api/")) return;        // 동적 API 는 캐시/가로채기 안 함

  e.respondWith(
    fetch(req).then((res) => {
      if (res && res.ok && res.type === "basic") {     // 받은 최신본을 캐시에 갱신
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => { });
      }
      return res;
    }).catch(() =>                                      // 오프라인: 마지막 캐시 → index 폴백
      caches.match(req, { ignoreSearch: true })
        .then((hit) => hit || caches.match("./index.html", { ignoreSearch: true }))
    )
  );
});
