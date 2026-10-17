package kr.labyrinth.homes.play;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.core.Log;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.NoopHomesUi;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;

/**
 * 묶음 C 연결 (0.3.7): 메뉴 ({@link PlayUi} = {@link kr.labyrinth.homes.HomesUi} 구현) · 자재 목록 ({@link HousingCatalog}) ·
 * 회복·침대·들어설 때 글 ({@link HomeCareListener}) · 켤 때 표지판 다시 쓰기. {@code homes.enabled} 일 때만 켠다 ({@link kr.labyrinth.homes.HomesModule}).
 */
public final class PlayWiring {

    private final Services services;
    private final HomesService service;
    private final List<Listener> listeners = new ArrayList<>();
    private volatile HousingCatalog catalog = HousingCatalog.EMPTY;
    private PlayUi ui;
    private HomeCareListener care;

    public PlayWiring(Services services, HomesService service) {
        this.services = services;
        this.service = service;
    }

    public HomesService service() { return service; }

    /** 켜져 있으면 메뉴 (꺼져 있으면 null). */
    public PlayUi ui() { return ui; }

    public HousingCatalog catalog() { return catalog; }

    public void enable() {
        disable();
        reloadCatalog();
        ui = new PlayUi(services, service, this);
        service.setUi(ui);
        care = new HomeCareListener(services, service);
        listeners.add(care);
        for (Listener l : listeners) Bukkit.getPluginManager().registerEvents(l, services.plugin());
        care.start(services.plugin());
        // 꺼져 있는 동안 바뀐 소유를 표지판에 (구역 기록·소유 파일을 다 읽은 뒤)
        PlayUi u = ui;
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (u == ui) u.refreshAllSigns();
        }, 100L);
    }

    public void disable() {
        for (Listener l : listeners) HandlerList.unregisterAll(l);
        listeners.clear();
        if (care != null) care.stop();
        care = null;
        if (ui != null) service.setUi(new NoopHomesUi());
        ui = null;
    }

    /** content/housing.yml 다시 읽기 (켤 때 · /labadmin reload). */
    public void reloadCatalog() {
        HousingCatalog c = HousingCatalog.load(services.plugin().getDataFolder(), services.plugin()::getResource, PlayWiring::knownItem);
        int shown = 0;
        for (String prob : c.problems()) {
            if (shown++ >= 10) break;
            Log.warn("[집] housing.yml " + prob);
        }
        if (c.problems().size() > 10) Log.warn("[집] housing.yml 건너뛴 줄 " + c.problems().size() + "개 (위는 앞 10개)");
        catalog = c;
        Log.info("[집] 자재 " + c.size() + "가지 · 탭 " + c.tabs().size());
    }

    static boolean knownItem(String id) {
        try {
            Material m = Material.matchMaterial(id);
            return m != null && m.isItem();
        } catch (Throwable t) {
            return false;
        }
    }
}
