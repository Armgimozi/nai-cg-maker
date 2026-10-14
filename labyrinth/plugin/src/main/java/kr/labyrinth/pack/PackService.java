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
    private HttpServer server;
    private volatile byte[] packBytes;
    private volatile String sha1 = "";
    private volatile UUID packId;
    private volatile String externalUrl;

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
    }

    private void start() {
        Settings.Pack cfg = services.settings().pack();
        packBytes = null;
        sha1 = "";
        externalUrl = null;
        if (!cfg.enabled()) {
            Log.info("리소스팩 전송 꺼짐 (pack.enabled: false)");
            return;
        }
        if (cfg.url() != null && !cfg.url().isBlank()) {
            externalUrl = cfg.url().trim();
            sha1 = cfg.sha1() == null ? "" : cfg.sha1().trim().toLowerCase();
            if (sha1.isEmpty() && Files.exists(packFile)) {
                try {
                    sha1 = sha1Hex(Files.readAllBytes(packFile));
                } catch (IOException e) {
                    Log.warn("로컬 팩 해시 계산 실패: " + e.getMessage());
                }
            }
            packId = UUID.nameUUIDFromBytes(("labyrinth:" + externalUrl + sha1).getBytes(StandardCharsets.UTF_8));
            Log.info("리소스팩: 외부 URL 사용 " + externalUrl + (sha1.isEmpty() ? " (SHA-1 없음)" : ""));
            return;
        }
        try {
            extractBundled(cfg.updateFromJar());
            if (!Files.exists(packFile)) {
                Log.warn("리소스팩 파일이 없습니다: " + packFile + " — 팩 없이 동작합니다 (resourcepack/generate.py 로 만든 zip 을 넣으세요).");
                return;
            }
            packBytes = Files.readAllBytes(packFile);
            sha1 = sha1Hex(packBytes);
            packId = UUID.nameUUIDFromBytes(("labyrinth:" + sha1).getBytes(StandardCharsets.UTF_8));
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
            Log.error("리소스팩 서버 시작 실패 (포트 " + cfg.port() + " 사용 중?) — 팩 없이 동작합니다", e);
            stopServer();
            packBytes = null;
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

    /** 플레이어가 받을 팩 URL (접속한 호스트 이름 기준). */
    public String urlFor(Player p) {
        if (externalUrl != null) return externalUrl;
        Settings.Pack cfg = services.settings().pack();
        String host = cfg.publicHost();
        if (host == null || host.isBlank()) host = joinHosts.get(p.getUniqueId());
        if (host == null || host.isBlank()) host = Bukkit.getIp();
        if (host == null || host.isBlank() || host.equals("0.0.0.0")) host = "127.0.0.1";
        if (host.contains(":") && !host.startsWith("[")) host = "[" + host + "]"; // IPv6
        return "http://" + host + ":" + cfg.port() + "/" + FILE_NAME + "?v=" + (sha1.length() >= 8 ? sha1.substring(0, 8) : "0");
    }

    /** 팩 전송 (접속 시 자동, /labadmin pack resend 등에서 수동). */
    public void send(Player p) {
        if (!isAvailable()) return;
        Settings.Pack cfg = services.settings().pack();
        try {
            ResourcePackInfo info = ResourcePackInfo.resourcePackInfo(packId, URI.create(urlFor(p)), sha1);
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
        if (host.startsWith("[")) {
            int end = host.indexOf(']');
            host = end > 0 ? host.substring(1, end) : host;
        } else if (host.chars().filter(c -> c == ':').count() == 1) {
            host = host.substring(0, host.indexOf(':'));
        }
        if (host.endsWith(".")) host = host.substring(0, host.length() - 1);
        joinHosts.put(e.getUniqueId(), host);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (p.isOnline()) send(p);
        }, 20L);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) { joinHosts.remove(e.getPlayer().getUniqueId()); }

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
            case FAILED_DOWNLOAD, INVALID_URL, FAILED_RELOAD -> Text.error(p,
                    "리소스팩을 받지 못했습니다. <gray>서버 관리자에게 pack.port(" + services.settings().pack().port()
                            + ") 포트 개방 또는 pack.public_host 설정을 요청하세요.");
            default -> { }
        }
    }
}
