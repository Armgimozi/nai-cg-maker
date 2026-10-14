package kr.labyrinth.core;

import kr.labyrinth.Services;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.event.EventHandler;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.world.EntitiesLoadEvent;

/**
 * 이전 세션이 남긴 임시 엔티티(커스텀 몹·모델 파트·이펙트·피해 숫자) 청소 (ARCHITECTURE §7).
 * {@link Keys#tagTransient} 로 태그된 것만 지운다 — NPC·플레이어 소유물은 건드리지 않음.
 */
public final class EntityJanitor implements Module, Listener {

    private final Services services;

    public EntityJanitor(Services services) { this.services = services; }

    @Override
    public String name() { return "janitor"; }

    @Override
    public void enable() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        int n = 0;
        for (World w : Bukkit.getWorlds()) {
            for (Entity e : w.getEntities()) {
                if (Keys.isStaleTransient(e)) {
                    e.remove();
                    n++;
                }
            }
        }
        if (n > 0) Log.info("이전 세션의 임시 엔티티 " + n + "개 정리");
    }

    @Override
    public void disable() {
        HandlerList.unregisterAll(this);
        // 이번 세션 임시 엔티티도 종료 시 제거 (재시작 전에 깨끗하게)
        for (World w : Bukkit.getWorlds()) {
            for (Entity e : w.getEntities()) {
                for (var k : Keys.TRANSIENT_ENTITY_KEYS) {
                    if (e.getPersistentDataContainer().has(k)) {
                        e.remove();
                        break;
                    }
                }
            }
        }
    }

    @EventHandler
    public void onEntitiesLoad(EntitiesLoadEvent e) {
        for (Entity en : e.getEntities()) {
            if (Keys.isStaleTransient(en)) en.remove();
        }
    }
}
