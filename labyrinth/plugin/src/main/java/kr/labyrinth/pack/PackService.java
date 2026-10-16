package kr.labyrinth.pack;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import kr.labyrinth.Services;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Text;
import net.kyori.adventure.resource.ResourcePackInfo;
import net.kyori.adventure.resource.ResourcePackRequest;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.player.AsyncPlayerPreLoginEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerResourcePackStatusEvent;

/**
 * 리소스팩 배포 (ARCHITECTURE §3). plugins/Labyrinth/pack/labyrinth-pack.zip 을 내장 HTTP 서버로 서빙하고
 * 접속 시 SHA-1 과 함께 전송. jar 에 팩이 들어 있으면(빌드 시 포함) 자동으로 꺼내 쓴다.
 * zip 이 없으면 경고만 하고 플러그인은 정상 동작 (팩 없이도 접속 가능).
 */
public final class PackService implements Module, Listener {

    public static final String FILE_NAME = "labyrinth-pack.zip";
    private static final String BUNDLED = "pack/" + FILE_NAME;

    private final Services services;
    private final Path packFile;
    private final Map<UUID, String> joinHosts = new ConcurrentHashMap<>();
    private final Map<UUID, Integer> joinPorts = new ConcurrentHashMap<>();
    private final GamePortPackServer gamePort = new GamePortPackServer(() -> this.packBytes, FILE_NAME);
    private HttpServer server;
    private volatile byte[] packBytes;
    private volatile String sha1 = "";
    private volatile UUID packId;
    private volatile String externalUrl;
    /** 0.3.6.1 주소 고르기 결과 ({@link PackUrlChoice}). */
    private volatile PackUrlChoice.Plan plan;
    /** 공개 사본을 받아 SHA-1 이 맞았나 (null = 확인 중 · 안 함). */
    private volatile Boolean copyOk;
    private volatile String copyState = "확인 안 함";
    /** 지금 보내는 방식 ((b) 사본을 못 받으면 내장으로 돌아감). */
    private volatile PackUrlChoice.Mode activeMode = PackUrlChoice.Mode.BUILTIN;
    private volatile int generation;
    /** 내장 주소를 받지 못해 공개 사본으로 한 번 더 보낸 사람 (접속마다 한 번). */
    private final java.util.Set<UUID> fallbackSent = ConcurrentHashMap.newKeySet();
    private volatile UUID fallbackId;

    public PackService(Services services) {
        this.services = services;
        this.packFile = services.plugin().getDataFolder().toPath().resolve("pack").resolve(FILE_NAME);
    }

    @Override
    public String name() { return "pack"; }

    @Override
    public void enable() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        start();
    }

    @Override
    public void reload() {
        stopServer();
        start();
    }

    @Override
    public void disable() {
        HandlerList.unregisterAll(this);
        stopServer();
        gamePort.uninstall();
    }

    /** 게임 포트로도 팩을 보내는 중인가 (playit 같은 터널에서 8163 없이 받기). */
    public boolean gamePortActive() { return gamePort.installed() && packBytes != null; }

    private void start() {
        Settings.Pack cfg = services.settings().pack();
        packBytes = null;
        sha1 = "";
        externalUrl = null;
        plan = null;
        copyOk = null;
        copyState = "확인 안 함";
        activeMode = PackUrlChoice.Mode.BUILTIN;
        fallbackSent.clear();
        int gen = ++generation;
        if (!cfg.enabled()) {
            Log.info("리소스팩 전송 꺼짐 (pack.enabled: false)");
            return;
        }
        // 0.3.6.1: jar 팩을 늘 꺼내 SHA-1 을 안다 (외부 주소를 쓸 때도 — 옛 사본을 가리키는 pack.url 을 바로잡으려고)
        String jarSha = "";
        try {
            extractBundled(cfg.updateFromJar());
            if (Files.exists(packFile)) jarSha = sha1Hex(Files.readAllBytes(packFile));
        } catch (IOException e) {
            Log.warn("로컬 팩 해시 계산 실패: " + e.getMessage());
        }
        PackUrlChoice.Plan pl = PackUrlChoice.decide(cfg.url(), cfg.sha1(), cfg.publicHost(), cfg.publicCopy(), jarSha);
        plan = pl;
        fallbackId = UUID.nameUUIDFromBytes(("labyrinth:copy:" + jarSha).getBytes(StandardCharsets.UTF_8));
        if (pl.notice() != null) Log.info(pl.notice());
        if (pl.mode() != PackUrlChoice.Mode.BUILTIN) {
            externalUrl = pl.url();
            sha1 = pl.sha1() == null ? "" : pl.sha1();
            activeMode = pl.mode();
            packId = UUID.nameUUIDFromBytes(("labyrinth:" + externalUrl + sha1).getBytes(StandardCharsets.UTF_8));
            Log.info("리소스팩: " + PackUrlChoice.label(pl.mode()) + " " + externalUrl + (sha1.isEmpty() ? " (SHA-1 없음)" : ""));
            if (pl.checkUrl() != null) {
                checkCopy(gen, pl.checkUrl(), sha1, ok -> {
                    if (ok || externalUrl == null) return;
                    Log.warn("[리소스팩] 공개 사본을 받을 수 없어(" + copyState + ") 내장 서버로 보냅니다 — 사본이 올라오면 다음 시작부터 사본을 씁니다.");
                    externalUrl = null;
                    activeMode = PackUrlChoice.Mode.BUILTIN;
                    startBuiltin(cfg);
                    for (Player p : Bukkit.getOnlinePlayers()) send(p);
                });
            }
            return;
        }
        startBuiltin(cfg);
        if (pl.checkUrl() != null && packBytes != null) checkCopy(gen, pl.checkUrl(), sha1, ok -> { });
    }

    /** 내장 HTTP 서버 (+ 게임 포트) 로 plugins/Labyrinth/pack/labyrinth-pack.zip 을 보낸다. */
    private void startBuiltin(Settings.Pack cfg) {
        stopServer();
        try {
            if (!Files.exists(packFile)) {
                Log.warn("리소스팩 파일이 없습니다: " + packFile + " — 팩 없이 동작합니다 (resourcepack/generate.py 로 만든 zip 을 넣으세요).");
                return;
            }
            packBytes = Files.readAllBytes(packFile);
            sha1 = sha1Hex(packBytes);
            packId = UUID.nameUUIDFromBytes(("labyrinth:" + sha1).getBytes(StandardCharsets.UTF_8));
            if (cfg.samePort()) {
                if (gamePort.install()) Log.info("리소스팩을 게임 포트로도 보냅니다 (터널·포트포워딩에 8163 을 따로 열지 않아도 됨)");
            } else {
                gamePort.uninstall();
            }
            server = HttpServer.create(new InetSocketAddress(cfg.bind(), cfg.port()), 16);
            server.createContext("/", this::handle);
            server.setExecutor(Executors.newFixedThreadPool(2, r -> {
                Thread t = new Thread(r, "Labyrinth-PackHTTP");
                t.setDaemon(true);
                return t;
            }));
            server.start();
            Log.info("리소스팩 HTTP 서버 시작: 포트 " + cfg.port() + " (" + packBytes.length / 1024 + " KB, sha1 " + sha1 + ")");
        } catch (IOException e) {
            stopServer();
            if (gamePortActive()) {
                Log.warn("리소스팩 8163 서버 시작 실패 (포트 " + cfg.port() + " 사용 중?) — 게임 포트로만 보냅니다: " + e.getMessage());
            } else {
                Log.error("리소스팩 서버 시작 실패 (포트 " + cfg.port() + " 사용 중?) — 팩 없이 동작합니다", e);
                packBytes = null;
            }
        }
    }

    private void extractBundled(boolean update) throws IOException {
        try (InputStream in = services.plugin().getResource(BUNDLED)) {
            if (in == null) return;
            byte[] bundled = in.readAllBytes();
            if (Files.exists(packFile)) {
                if (!update) return;
                if (sha1Hex(Files.readAllBytes(packFile)).equals(sha1Hex(bundled))) return;
            }
            Files.createDirectories(packFile.getParent());
            Path tmp = packFile.resolveSibling(FILE_NAME + ".tmp");
            Files.write(tmp, bundled);
            Files.move(tmp, packFile, StandardCopyOption.REPLACE_EXISTING);
            Log.info("jar 에 포함된 리소스팩을 꺼냈습니다: " + packFile);
        }
    }

    private void stopServer() {
        if (server != null) {
            server.stop(0);
            server = null;
        }
    }

    private void handle(HttpExchange ex) throws IOException {
        try (ex) {
            byte[] data = packBytes;
            if (data == null || !"GET".equalsIgnoreCase(ex.getRequestMethod()) && !"HEAD".equalsIgnoreCase(ex.getRequestMethod())) {
                ex.sendResponseHeaders(404, -1);
                return;
            }
            ex.getResponseHeaders().set("Content-Type", "application/zip");
            ex.getResponseHeaders().set("Cache-Control", "no-cache");
            if ("HEAD".equalsIgnoreCase(ex.getRequestMethod())) {
                ex.sendResponseHeaders(200, -1);
                return;
            }
            ex.sendResponseHeaders(200, data.length);
            try (OutputStream os = ex.getResponseBody()) {
                os.write(data);
            }
        }
    }

    public boolean isAvailable() { return externalUrl != null || packBytes != null; }

    public String sha1() { return sha1; }

    /** 플레이어가 받을 팩 URL (외부 주소가 있으면 그것, 없으면 접속한 호스트 이름 기준 내장 주소). */
    public String urlFor(Player p) {
        if (externalUrl != null) return externalUrl;
        return builtinUrlFor(p);
    }

    /** 내장 서버 주소 (접속한 호스트 이름 기준). */
    public String builtinUrlFor(Player p) {
        Settings.Pack cfg = services.settings().pack();
        String joined = p == null ? null : joinHosts.get(p.getUniqueId());
        String host;
        int port = cfg.port();
        boolean hasPublic = cfg.publicHost() != null && !cfg.publicHost().isBlank();
        Integer joinedPort = p == null ? null : joinPorts.get(p.getUniqueId());
        if (!hasPublic && gamePortActive() && joined != null && !joined.isBlank()) {
            host = joined;                       // 접속한 주소·포트 그대로 (게임 포트로 팩을 받음 — 터널 하나로 충분)
            port = joinedPort != null && joinedPort > 0 ? joinedPort : Bukkit.getPort();
        } else if (joined != null && isLocalHost(joined)) {
            host = joined;                       // 같은 PC·같은 와이파이 → 내장 서버에 바로
        } else if (hasPublic) {
            host = cfg.publicHost().trim();      // 터널(playit.gg 등)·외부 → 설정한 공개 주소:포트
            if (cfg.publicPort() > 0) port = cfg.publicPort();
        } else {
            host = joined;
        }
        if (host == null || host.isBlank()) host = Bukkit.getIp();
        if (host == null || host.isBlank() || host.equals("0.0.0.0")) host = "127.0.0.1";
        if (host.contains(":") && !host.startsWith("[")) host = "[" + host + "]"; // IPv6
        return "http://" + host + ":" + port + "/" + FILE_NAME + "?v=" + (sha1.length() >= 8 ? sha1.substring(0, 8) : "0");
    }

    /** localhost · 사설망(LAN) 주소인가. */
    static boolean isLocalHost(String h) {
        String s = h.toLowerCase(java.util.Locale.ROOT);
        if (s.equals("localhost") || s.startsWith("127.") || s.equals("::1") || s.equals("[::1]")) return true;
        if (s.startsWith("10.") || s.startsWith("192.168.")) return true;
        if (s.startsWith("172.")) {
            String[] parts = s.split("\\.");
            try {
                int second = Integer.parseInt(parts[1]);
                return second >= 16 && second <= 31;
            } catch (RuntimeException e) {
                return false;
            }
        }
        return false;
    }

    /** 팩 전송 (접속 시 자동, /labadmin pack resend 등에서 수동). */
    public void send(Player p) {
        if (!isAvailable()) return;
        send(p, packId, urlFor(p));
    }

    private void send(Player p, UUID id, String url) {
        Settings.Pack cfg = services.settings().pack();
        try {
            ResourcePackInfo info = ResourcePackInfo.resourcePackInfo(id, URI.create(url), sha1);
            p.sendResourcePacks(ResourcePackRequest.resourcePackRequest()
                    .packs(info)
                    .required(cfg.required())
                    .replace(true)
                    .prompt(Text.mm(cfg.prompt()))
                    .build());
        } catch (IllegalArgumentException e) {
            Log.warn("리소스팩 URL 이 올바르지 않음: " + e.getMessage());
        }
    }

    static String sha1Hex(byte[] data) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-1").digest(data));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    // ── 이벤트 ────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onPreLogin(AsyncPlayerPreLoginEvent e) {
        String host = e.getHostname();
        if (host == null) return;
        int nul = host.indexOf('\0');
        if (nul >= 0) host = host.substring(0, nul);
        int port = -1;
        if (host.startsWith("[")) {
            int end = host.indexOf(']');
            if (end > 0 && host.length() > end + 2 && host.charAt(end + 1) == ':') port = parsePort(host.substring(end + 2));
            host = end > 0 ? host.substring(1, end) : host;
        } else if (host.chars().filter(c -> c == ':').count() == 1) {
            port = parsePort(host.substring(host.indexOf(':') + 1));
            host = host.substring(0, host.indexOf(':'));
        }
        if (host.endsWith(".")) host = host.substring(0, host.length() - 1);
        // 주소 뒤에 포트 없이 SRV 기록으로 들어온 경우(예: playit 의 joinmc.link) → SRV 가 가리키는 진짜 주소·포트로 받게
        if (gamePortActive() && (port <= 0 || port == 25565) && !isLocalHost(host) && host.contains(".") && !isIpLiteral(host)) {
            String[] srv = srvLookup(host);
            if (srv != null) {
                host = srv[0];
                port = parsePort(srv[1]);
            }
        }
        joinHosts.put(e.getUniqueId(), host);
        if (port > 0) joinPorts.put(e.getUniqueId(), port);
        else joinPorts.remove(e.getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (p.isOnline()) send(p);
        }, 20L);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        joinHosts.remove(e.getPlayer().getUniqueId());
        joinPorts.remove(e.getPlayer().getUniqueId());
        fallbackSent.remove(e.getPlayer().getUniqueId());
    }

    // ── 0.3.6.1 공개 사본 ────────────────────────────────────────────────

    /** (a) 내장 주소를 받지 못한 사람에게 공개 사본으로 한 번 더 (시작 때 받아 본 사본의 SHA-1 이 맞을 때만, 접속마다 한 번). */
    private boolean sendCopyOnce(Player p) {
        PackUrlChoice.Plan pl = plan;
        if (externalUrl != null || pl == null || pl.fallbackUrl() == null || !Boolean.TRUE.equals(copyOk)) return false;
        if (!fallbackSent.add(p.getUniqueId())) return false;
        Text.send(p, "<gray>리소스팩을 다른 주소에서 한 번 더 받습니다…");
        Log.info("[리소스팩] " + p.getName() + " 님이 내장 주소를 받지 못해 공개 사본으로 다시 보냅니다.");
        send(p, fallbackId, pl.fallbackUrl());
        return true;
    }

    /** 공개 사본을 받아 SHA-1 을 맞춰 본다 (비동기, 20초 제한). 끝나면 주 스레드에서 then(맞음). */
    private void checkCopy(int gen, String url, String wantSha, java.util.function.Consumer<Boolean> then) {
        copyState = "확인 중";
        var plugin = services.plugin();
        Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
            boolean ok;
            String state;
            try {
                java.net.http.HttpClient http = java.net.http.HttpClient.newBuilder()
                        .connectTimeout(java.time.Duration.ofSeconds(6))
                        .followRedirects(java.net.http.HttpClient.Redirect.NORMAL)
                        .proxy(java.net.ProxySelector.getDefault())
                        .build();
                java.net.http.HttpResponse<byte[]> r = http.send(java.net.http.HttpRequest.newBuilder(URI.create(url))
                        .timeout(java.time.Duration.ofSeconds(20)).GET().build(), java.net.http.HttpResponse.BodyHandlers.ofByteArray());
                if (r.statusCode() != 200) {
                    ok = false;
                    state = "HTTP " + r.statusCode();
                } else {
                    ok = PackUrlChoice.matches(r.body(), wantSha);
                    state = ok ? "받음 (sha1 맞음)" : "받았지만 sha1 다름";
                }
            } catch (Exception ex) {
                ok = false;
                state = "받지 못함 (" + ex.getClass().getSimpleName() + ")";
            }
            boolean fok = ok;
            String fstate = state;
            Bukkit.getScheduler().runTask(plugin, () -> {
                if (gen != generation) return;          // 그 사이 다시 읽음
                copyOk = fok;
                copyState = fstate;
                Log.info("[리소스팩] 공개 사본 " + (fok ? "확인: " : "확인 실패: ") + fstate + " — " + url);
                then.accept(fok);
            });
        });
    }

    /** /labadmin pack: 방식마다 쓰는 주소 (viewer 기준 내장 주소). */
    public java.util.List<String> describe(Player viewer) {
        java.util.List<String> out = new java.util.ArrayList<>();
        Settings.Pack cfg = services.settings().pack();
        if (!cfg.enabled()) {
            out.add("<gray>리소스팩 전송 꺼짐 (pack.enabled: false)");
            return out;
        }
        out.add(isAvailable() ? "<green>리소스팩 사용 가능</green> <gray>sha1 " + (sha1.length() >= 8 ? sha1.substring(0, 8) : "?")
                + " · 지금 방식: <white>" + PackUrlChoice.label(activeMode)
                : "<red>리소스팩 없음</red> <gray>(plugins/Labyrinth/pack/labyrinth-pack.zip)");
        PackUrlChoice.Plan pl = plan;
        String cfgUrl = cfg.url() == null || cfg.url().isBlank() ? "(비어 있음)" : cfg.url().trim();
        out.add("<gray>config pack.url: <white>" + Text.escape(cfgUrl));
        if (externalUrl != null) out.add("<gray>보내는 주소: <white>" + Text.escape(externalUrl));
        if (packBytes != null) {
            out.add("<gray>내장 주소" + (viewer == null ? "" : " (당신 기준)") + ": <white>" + Text.escape(builtinUrlFor(viewer))
                    + (gamePortActive() ? " <gray>· 게임 포트로도 보냄" : " <gray>· 8163 · public_host 로만"));
        }
        String copy = pl == null ? null : pl.mode() == PackUrlChoice.Mode.BUILTIN ? pl.fallbackUrl() : pl.mode() == PackUrlChoice.Mode.PUBLIC_COPY ? pl.url() : null;
        if (cfg.publicCopy() == null || cfg.publicCopy().isBlank()) out.add("<gray>공개 사본: 꺼짐 (pack.public_copy: \"\")");
        else if (copy != null) out.add("<gray>공개 사본: <white>" + Text.escape(copy) + " <gray>(" + Text.escape(copyState) + ")");
        else out.add("<gray>공개 사본: 안 씀 (" + (pl != null && pl.mode() == PackUrlChoice.Mode.CUSTOM_URL ? "직접 적은 pack.url 을 그대로 씀" : "public_host 를 씀") + ")");
        if (activeMode == PackUrlChoice.Mode.BUILTIN) {
            out.add("<gray>내장 주소를 받지 못하면: " + (pl != null && pl.fallbackUrl() != null
                    ? (Boolean.TRUE.equals(copyOk) ? "<white>공개 사본으로 한 번 더 보냄" : "<white>공개 사본으로 한 번 더 (사본 확인 뒤)")
                    : "<white>다시 보내지 않음"));
        }
        return out;
    }

    static boolean isIpLiteral(String h) {
        return h.contains(":") || h.chars().allMatch(c -> c == '.' || (c >= '0' && c <= '9'));
    }

    /** _minecraft._tcp.&lt;host&gt; SRV 기록 → {대상 주소, 포트}. 없거나 실패하면 null (접속 전 비동기 이벤트라 기다려도 됨, 2초 제한). */
    static String[] srvLookup(String host) {
        try {
            java.util.Hashtable<String, String> env = new java.util.Hashtable<>();
            env.put("java.naming.factory.initial", "com.sun.jndi.dns.DnsContextFactory");
            env.put("com.sun.jndi.dns.timeout.initial", "1000");
            env.put("com.sun.jndi.dns.timeout.retries", "1");
            javax.naming.directory.DirContext ctx = new javax.naming.directory.InitialDirContext(env);
            try {
                javax.naming.directory.Attribute a = ctx.getAttributes("_minecraft._tcp." + host, new String[] {"SRV"}).get("SRV");
                if (a == null || a.size() == 0) return null;
                String[] parts = String.valueOf(a.get(0)).trim().split("\\s+"); // 우선순위 무게 포트 대상
                if (parts.length < 4) return null;
                String target = parts[3].endsWith(".") ? parts[3].substring(0, parts[3].length() - 1) : parts[3];
                if (target.isBlank() || parsePort(parts[2]) <= 0) return null;
                return new String[] {target, parts[2]};
            } finally {
                ctx.close();
            }
        } catch (javax.naming.NamingException | RuntimeException e) {
            return null;
        }
    }

    static int parsePort(String s) {
        try {
            int v = Integer.parseInt(s.trim());
            return v > 0 && v <= 65535 ? v : -1;
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    @EventHandler
    public void onStatus(PlayerResourcePackStatusEvent e) {
        Player p = e.getPlayer();
        switch (e.getStatus()) {
            case SUCCESSFULLY_LOADED -> Text.send(p, "<green>리소스팩 적용 완료!</green> <gray>미궁에 오신 것을 환영합니다.");
            case DECLINED -> {
                if (services.settings().pack().kickOnDecline()) {
                    p.kick(Text.mm("<red>미궁 라비린스는 전용 리소스팩이 필요합니다.\n<gray>서버 목록 → 편집 → 서버 리소스팩: 사용"));
                } else {
                    Text.error(p, "리소스팩을 거절했습니다. 무기·몬스터가 제대로 보이지 않습니다. <gray>(서버 목록 → 편집 → 리소스팩: 사용)");
                }
            }
            case FAILED_DOWNLOAD, INVALID_URL, FAILED_RELOAD -> {
                if (e.getStatus() != PlayerResourcePackStatusEvent.Status.FAILED_RELOAD && sendCopyOnce(p)) return;
                Text.error(p,
                    "리소스팩을 받지 못했습니다. <gray>서버 관리자에게 pack.port(" + services.settings().pack().port()
                            + ") 포트 개방 또는 pack.public_host 설정을 요청하세요.");
            }
            default -> { }
        }
    }
}
