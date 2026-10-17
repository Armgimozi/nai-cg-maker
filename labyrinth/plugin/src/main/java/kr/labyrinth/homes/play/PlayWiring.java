package kr.labyrinth.homes.play;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.NoopHomesUi;
import org.bukkit.Bukkit;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;

/**
 * 묶음 C 연결 (0.3.7): 메뉴 ({@link kr.labyrinth.homes.HomesUi} 구현) · 회복·표지판·들어설 때 글 리스너. 소유: 묶음 C.
 * 뼈대: 메뉴 = 안내 글 ({@link NoopHomesUi}), 리스너 = 빈 {@link HomeCareListener}.
 */
public final class PlayWiring {

    private final Services services;
    private final HomesService service;
    private final List<Listener> listeners = new ArrayList<>();

    public PlayWiring(Services services, HomesService service) {
        this.services = services;
        this.service = service;
    }

    public void enable() {
        disable();
        service.setUi(new NoopHomesUi());
        listeners.add(new HomeCareListener(service));
        for (Listener l : listeners) Bukkit.getPluginManager().registerEvents(l, services.plugin());
    }

    public void disable() {
        for (Listener l : listeners) HandlerList.unregisterAll(l);
        listeners.clear();
    }
}
