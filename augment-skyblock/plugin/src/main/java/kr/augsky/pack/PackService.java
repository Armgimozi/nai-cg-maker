package kr.augsky.pack;

import com.sun.net.httpserver.HttpServer;
import kr.augsky.AugSky;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerLoginEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerResourcePackStatusEvent;

import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Executors;

/**
 * 리소스팩 배포. 플러그인 jar 안의 pack.zip 을 꺼내 작은 HTTP 서버로 내보내고, 접속한 플레이어에게 보낸다.
 * config 의 resource-pack.url 을 채우면 그 주소(예: GitHub raw)를 대신 쓴다.
 */
public final class PackService implements Listener {
    private static final UUID PACK_ID = UUID.fromString("6a0f3c62-5d7e-4f0e-9a51-0c1d7a2b9e11");

    private final AugSky plugin;
    private HttpServer http;
    private byte[] data;
    private byte[] sha1;
    private final Map<UUID, String> hostOf = new HashMap<>();

    public PackService(AugSky plugin) {
        this.plugin = plugin;
    }

    public void start() {
        if (!plugin.getConfig().getBoolean("resource-pack.enabled", true)) return;
        File out = new File(plugin.getDataFolder(), "pack.zip");
        try (InputStream in = plugin.getResource("pack.zip")) {
            if (in == null) {
                plugin.getLogger().warning("jar 안에 pack.zip 이 없습니다. 리소스팩 없이 실행합니다.");
                return;
            }
            Files.copy(in, out.toPath(), StandardCopyOption.REPLACE_EXISTING);
            data = Files.readAllBytes(out.toPath());
            sha1 = MessageDigest.getInstance("SHA-1").digest(data);
        } catch (Exception e) {
            plugin.getLogger().warning("리소스팩 준비 실패: " + e.getMessage());
            return;
        }
        plugin.getLogger().info("리소스팩 SHA-1: " + HexFormat.of().formatHex(sha1));
        if (!plugin.getConfig().getString("resource-pack.url", "").isBlank()) return;
        int port = plugin.getConfig().getInt("resource-pack.port", 8163);
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
            plugin.getLogger().info("리소스팩을 포트 " + port + " 에서 내보내는 중");
        } catch (Exception e) {
            plugin.getLogger().warning("리소스팩 HTTP 서버를 열지 못했습니다(포트 " + port + "): " + e.getMessage());
        }
    }

    public void stop() {
        if (http != null) http.stop(0);
    }

    @EventHandler
    public void onLogin(PlayerLoginEvent e) {
        String host = e.getHostname();
        if (host != null) {
            int c = host.lastIndexOf(':');
            if (c > 0) host = host.substring(0, c);
            // 일부 런처가 붙이는 FML 표식 등 \0 뒤 문자열 제거
            int z = host.indexOf('\0');
            if (z >= 0) host = host.substring(0, z);
            hostOf.put(e.getPlayer().getUniqueId(), host);
        }
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        hostOf.remove(e.getPlayer().getUniqueId());
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        if (data == null) return;
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(plugin, () -> send(p), 20);
    }

    public void send(Player p) {
        if (data == null || !p.isOnline()) return;
        String url = url(p);
        if (url == null) return;
        boolean required = plugin.getConfig().getBoolean("resource-pack.required", false);
        p.setResourcePack(PACK_ID, url, sha1, Text.mm("<#ffcc55>증강 스카이블럭<gray> 무기와 아이템 모양을 보려면 리소스팩이 필요합니다."), required);
    }

    private String url(Player p) {
        String fixed = plugin.getConfig().getString("resource-pack.url", "");
        if (!fixed.isBlank()) return fixed;
        if (http == null) return null;
        String host = plugin.getConfig().getString("resource-pack.public-host", "");
        if (host.isBlank()) host = hostOf.getOrDefault(p.getUniqueId(), "localhost");
        if (host.isBlank()) host = "localhost";
        return "http://" + host + ":" + plugin.getConfig().getInt("resource-pack.port", 8163) + "/pack.zip?v="
                + HexFormat.of().formatHex(sha1).substring(0, 8);
    }

    @EventHandler
    public void onStatus(PlayerResourcePackStatusEvent e) {
        switch (e.getStatus()) {
            case FAILED_DOWNLOAD, INVALID_URL, FAILED_RELOAD -> e.getPlayer().sendMessage(Text.mm(
                    "<#ff7070>리소스팩을 받지 못했습니다. <gray>무기 모양이 보라색 상자로 보일 수 있어요. 서버 관리자에게 config.yml 의 resource-pack 설정을 확인해 달라고 하세요."));
            case DECLINED -> e.getPlayer().sendMessage(Text.mm(
                    "<gray>리소스팩을 거절했습니다. 무기 모양이 깨져 보일 수 있습니다. <white>멀티플레이 → 서버 편집 → 서버 리소스팩: 사용<gray>으로 바꿔 주세요."));
            default -> {
            }
        }
    }
}
