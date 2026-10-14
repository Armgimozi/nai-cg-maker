package kr.labyrinth.core;

import com.destroystokyo.paper.event.server.PaperServerListPingEvent;
import java.awt.image.BufferedImage;
import java.io.InputStream;
import javax.imageio.ImageIO;
import kr.labyrinth.Services;
import net.kyori.adventure.text.minimessage.tag.resolver.Placeholder;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.util.CachedServerIcon;

/**
 * 서버 목록 화면: 그라데이션 두 줄 설명(MiniMessage, config server_list) + 미궁 석문 아이콘(jar 안 server-icon.png,
 * tools/server_icon.py 로 생성). 둘째 줄은 상황에 따라 바뀐다 — 서버 최고 돌파 층, 지금 미궁 탐험 중인 인원.
 * server.properties 의 motd·server-icon.png 보다 우선한다 (끄려면 server_list.enabled: false).
 */
public final class ServerListListener implements Module, Listener {

    private final Services services;
    private CachedServerIcon icon;

    public ServerListListener(Services services) { this.services = services; }

    @Override
    public String name() { return "server-list"; }

    @Override
    public void enable() {
        try (InputStream in = services.plugin().getResource("server-icon.png")) {
            BufferedImage img = in == null ? null : ImageIO.read(in);
            if (img != null) icon = Bukkit.loadServerIcon(img);
        } catch (Exception e) {
            Log.warn("서버 아이콘을 불러오지 못했습니다: " + e.getMessage());
        }
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
    }

    @Override
    public void disable() { HandlerList.unregisterAll(this); }

    private static String str(String s) { return s == null ? "" : s; }

    @EventHandler
    public void onPing(PaperServerListPingEvent e) {
        var c = services.plugin().getConfig();
        if (!c.getBoolean("server_list.enabled", true)) return;
        if (icon != null && c.getBoolean("server_list.icon", true)) e.setServerIcon(icon);
        int deepest = 0;
        for (int n = 1; n <= services.content().maxFloor(); n++) {
            if (services.records().isClaimed("first_clear.floor_" + n)) deepest = n;
        }
        int exploring = 0;
        for (Player p : Bukkit.getOnlinePlayers()) if (services.dungeon().isInLabyrinth(p)) exploring++;
        // 기본값 없이 읽어야 jar 안 config.yml 기본값이 쓰인다 (예전 config.yml 에 server_list 가 없어도 동작)
        String line1 = str(c.getString("server_list.line1"));
        String line2 = str(c.getString(deepest >= services.content().maxFloor() ? "server_list.line2_cleared"
                : deepest > 0 ? "server_list.line2_record" : "server_list.line2_new"));
        String tail = exploring > 0 ? str(c.getString("server_list.exploring")) : "";
        var resolvers = new net.kyori.adventure.text.minimessage.tag.resolver.TagResolver[] {
                Placeholder.unparsed("deepest", String.valueOf(deepest)),
                Placeholder.unparsed("exploring", String.valueOf(exploring)),
                Placeholder.unparsed("difficulty", services.settings().isDifficultySet() ? services.settings().difficulty().name() : "미정"),
        };
        try {
            e.motd(Text.mm(line1 + "\n" + line2 + tail, resolvers));
        } catch (Exception ex) {
            Log.warn("server_list 문구 오류: " + ex.getMessage());
        }
    }
}
