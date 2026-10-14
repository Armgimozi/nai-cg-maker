package kr.labyrinth.core;

import com.destroystokyo.paper.event.server.PaperServerListPingEvent;
import java.awt.image.BufferedImage;
import java.io.InputStream;
import javax.imageio.ImageIO;
import kr.labyrinth.Services;
import org.bukkit.Bukkit;
import org.bukkit.event.EventHandler;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.util.CachedServerIcon;

/**
 * 서버 목록 아이콘: jar 안 server-icon.png(tools/server_icon.py 로 생성, 미궁 석문)를 보낸다.
 * 설명 글은 server.properties motd 그대로 (사용자: 꾸민 글보다 원래 글이 낫다). 끄려면 server_list.icon: false.
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

    @EventHandler
    public void onPing(PaperServerListPingEvent e) {
        if (icon != null && services.plugin().getConfig().getBoolean("server_list.icon", true)) e.setServerIcon(icon);
    }
}
