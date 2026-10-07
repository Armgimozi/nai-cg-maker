package kr.souls.pack;

import com.sun.net.httpserver.HttpServer;
import io.papermc.paper.connection.PlayerConfigurationConnection;
import io.papermc.paper.event.connection.configuration.AsyncPlayerConnectionConfigureEvent;
import kr.souls.Config;
import kr.souls.Lang;
import kr.souls.Souls;
import net.kyori.adventure.resource.ResourcePackInfo;
import net.kyori.adventure.resource.ResourcePackRequest;
import net.kyori.adventure.resource.ResourcePackStatus;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerResourcePackStatusEvent;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * 리소스팩 배포 (10.10). jar 안 pack.zip 의 SHA-1 로 주소 틀의 {sha1} 을 채운다 (파일 이름이 내용으로 정해져
 * raw.githubusercontent.com 의 캐시·커밋 고정 문제가 없다). 올리기(커밋·푸시)는 사용자가 한다.
 * 켤 때 그 주소에서 팩을 받아 SHA-1 을 견주고, 다르거나 못 받으면 크게 알린 뒤 팩을 선택(optional)으로 보낸다.
 * 보내는 때: 접속 + join-delay 틱 (skyblock 에서 검증), 또는 설정 단계(AsyncPlayerConnectionConfigureEvent, 아직 확인 전).
 * playit 은 25565 만 통하므로 실제 서버에서는 자체 HTTP 서버를 쓰지 않는다. serve-port 는 로컬 시험용이다.
 */
public final class PackService implements Listener {
    /** 고정 팩 UUID (바뀌면 클라이언트가 같은 팩을 두 번 쌓는다) */
    public static final UUID PACK_ID = UUID.fromString("3b1d7c40-8a2e-4f6b-9c15-5e0a7d2c4b91");

    public enum Check { OFF, PENDING, OK, MISMATCH, FAILED }

    private final Souls plugin;
    private HttpServer http;
    private byte[] data;
    private String sha1;
    private String url;
    private volatile Check check = Check.OFF;
    private volatile String checkNote = "";

    public PackService(Souls plugin) {
        this.plugin = plugin;
    }

    private Config.PackCfg cfg() {
        return plugin.cfg().pack;
    }

    public String sha1() { return sha1; }

    public String url() { return url; }

    public Check check() { return check; }

    public String checkNote() { return checkNote; }

    public boolean ready() { return data != null && url != null && !url.isBlank(); }

    /**
     * jar 안 팩의 언어 문자열 하나 (assets/minecraft/lang/&lt;code&gt;.json). 팩이 없거나 키가 없으면 null.
     * /souls check 가 사망 화면 제목과 death.title 이 겹치지 않는지 볼 때 쓴다 (5.6).
     */
    public String packLang(String code, String key) {
        if (data == null) return null;
        try (ZipInputStream z = new ZipInputStream(new ByteArrayInputStream(data), StandardCharsets.UTF_8)) {
            for (ZipEntry e; (e = z.getNextEntry()) != null; ) {
                if (!e.getName().equals("assets/minecraft/lang/" + code + ".json")) continue;
                JsonObject o = JsonParser.parseString(new String(z.readAllBytes(), StandardCharsets.UTF_8)).getAsJsonObject();
                return o.has(key) ? o.get(key).getAsString() : null;
            }
        } catch (Exception ex) {
            plugin.getLogger().warning("팩 언어 파일을 읽지 못했습니다: " + ex.getMessage());
        }
        return null;
    }

    /** 자체 확인에 실패하면 선택으로 보낸다. */
    public boolean required() {
        return cfg().required() && (check == Check.OK || check == Check.OFF || check == Check.PENDING);
    }

    public void start() {
        Config.PackCfg c = cfg();
        if (!c.enabled()) return;
        try (InputStream in = plugin.getResource("pack.zip")) {
            if (in == null) {
                plugin.getLogger().warning("jar 안에 pack.zip 이 없습니다 (pack/gen_pack.py 를 gradle 보다 먼저 돌리세요). 리소스팩 없이 켭니다.");
                return;
            }
            data = in.readAllBytes();
            sha1 = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-1").digest(data));
        } catch (Exception e) {
            plugin.getLogger().warning("리소스팩 준비 실패: " + e.getMessage());
            return;
        }
        url = c.url().replace("{sha1}", sha1);
        plugin.getLogger().info("리소스팩 SHA-1 " + sha1 + " (" + data.length / 1024 + " KB), 주소 " + url);
        if (data.length > 8 * 1024 * 1024) plugin.getLogger().warning("리소스팩이 8MB 를 넘습니다 (10.10).");
        if (c.servePort() > 0) serve(c.servePort());
        if (url.isBlank()) {
            plugin.getLogger().warning("pack.url 이 비어 있어 리소스팩을 보내지 않습니다.");
            return;
        }
        if (c.selfCheck()) selfCheck();
    }

    private void serve(int port) {
        try {
            http = HttpServer.create(new InetSocketAddress(port), 0);
            http.createContext("/", ex -> {
                try (ex) {
                    ex.getResponseHeaders().add("Content-Type", "application/zip");
                    ex.sendResponseHeaders(200, data.length);
                    try (OutputStream os = ex.getResponseBody()) {
                        os.write(data);
                    }
                }
            });
            http.setExecutor(Executors.newFixedThreadPool(2));
            http.start();
            plugin.getLogger().info("리소스팩을 포트 " + port + " 에서 내보냅니다 (로컬 시험용).");
        } catch (Exception e) {
            plugin.getLogger().warning("리소스팩 HTTP 서버를 열지 못했습니다 (포트 " + port + "): " + e.getMessage());
        }
    }

    public void stop() {
        if (http != null) http.stop(0);
        http = null;
    }

    /** 주소에서 받아 SHA-1 을 견준다 (비동기). */
    private void selfCheck() {
        check = Check.PENDING;
        String u = url;
        HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10))
                .followRedirects(HttpClient.Redirect.NORMAL).build();
        HttpRequest req;
        try {
            req = HttpRequest.newBuilder(URI.create(u)).timeout(Duration.ofSeconds(30)).GET().build();
        } catch (IllegalArgumentException ex) {
            fail(Check.FAILED, "주소가 틀렸습니다: " + ex.getMessage());
            return;
        }
        client.sendAsync(req, HttpResponse.BodyHandlers.ofByteArray()).whenComplete((res, err) -> {
            if (err != null) {
                fail(Check.FAILED, "받지 못했습니다: " + err);
                return;
            }
            if (res.statusCode() != 200) {
                fail(Check.FAILED, "HTTP " + res.statusCode());
                return;
            }
            try {
                String got = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-1").digest(res.body()));
                if (got.equals(sha1)) {
                    check = Check.OK;
                    checkNote = "주소의 팩이 jar 안 팩과 같다";
                    plugin.getLogger().info("리소스팩 자체 확인 통과 (" + u + ")");
                } else {
                    fail(Check.MISMATCH, "주소의 팩 SHA-1 " + got + " 이 jar 안 팩 " + sha1 + " 과 다릅니다");
                }
            } catch (Exception ex) {
                fail(Check.FAILED, ex.toString());
            }
        });
    }

    private void fail(Check c, String why) {
        check = c;
        checkNote = why;
        Bukkit.getScheduler().runTask(plugin, () -> {
            var log = plugin.getLogger();
            log.severe("=================================================================");
            log.severe("리소스팩 자체 확인 실패: " + why);
            log.severe("주소: " + url);
            log.severe("dist/packs/" + sha1 + ".zip 을 올렸는지 (커밋·푸시) 확인하세요. 그때까지 팩을 선택으로 보냅니다.");
            log.severe("=================================================================");
        });
    }

    private ResourcePackRequest request(net.kyori.adventure.resource.ResourcePackCallback cb) {
        return ResourcePackRequest.resourcePackRequest()
                .packs(ResourcePackInfo.resourcePackInfo(PACK_ID, URI.create(url), sha1))
                .required(required())
                .replace(true)
                .prompt(Lang.c("pack.prompt"))
                .callback(cb)
                .build();
    }

    // ------------------------------------------------------------------ 보내기

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        if (!ready() || !"join".equals(cfg().sendAt())) return;
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(plugin, () -> send(p), cfg().joinDelay());
    }

    public void send(Player p) {
        if (!ready() || !p.isOnline()) return;
        p.sendResourcePacks(request(net.kyori.adventure.resource.ResourcePackCallback.noOp()));
        plugin.test(p, "PACK sent sha1=" + sha1 + " required=" + required());
    }

    /**
     * 설정 단계에서 보내고 끝 상태(받음·거절·실패)가 올 때까지 기다린다. 이 이벤트는 비동기라 기다려도 서버가 멈추지 않는다.
     * 실제 클라이언트에서 아직 확인하지 못했다 (13.4 의 13). 안 되면 send-at: join 으로.
     */
    @EventHandler
    public void onConfigure(AsyncPlayerConnectionConfigureEvent e) {
        if (!ready() || !"configure".equals(cfg().sendAt())) return;
        PlayerConfigurationConnection conn = e.getConnection();
        CompletableFuture<ResourcePackStatus> done = new CompletableFuture<>();
        conn.getAudience().sendResourcePacks(request((id, status, audience) -> {
            if (!status.intermediate()) done.complete(status);
        }));
        try {
            ResourcePackStatus s = done.get(cfg().configureTimeout(), TimeUnit.SECONDS);
            if (required() && s == ResourcePackStatus.DECLINED) {
                conn.disconnect(Lang.c("pack.declined"));
            } else if (required() && s != ResourcePackStatus.SUCCESSFULLY_LOADED && s != ResourcePackStatus.DISCARDED) {
                conn.disconnect(Lang.c("pack.failed"));
            }
        } catch (Exception ex) {
            plugin.getLogger().warning(conn.getProfile().getName() + " 의 리소스팩 답을 기다리다 그만뒀습니다: " + ex);
        }
    }

    /** 접속 뒤에 보낸 팩: 필수인데 거절하거나 못 받으면 내보낸다. */
    @EventHandler
    public void onStatus(PlayerResourcePackStatusEvent e) {
        Player p = e.getPlayer();
        plugin.test(p, "PACK status=" + e.getStatus());
        if (!PACK_ID.equals(e.getID()) || !required()) return;
        switch (e.getStatus()) {
            case DECLINED -> p.kick(Lang.c("pack.declined"));
            case FAILED_DOWNLOAD, INVALID_URL, FAILED_RELOAD -> p.kick(Lang.c("pack.failed"));
            default -> {
            }
        }
    }
}
