package kr.labyrinth.core;

import kr.labyrinth.Services;
import org.bukkit.Bukkit;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;

/**
 * 인벤세이브 (config.yml death) — 야생·마을·네더·엔드 어디서 죽든(PvP 포함) 소지품과 바닐라 경험치 레벨을 지키고
 * 아무것도 떨구지 않는다. 미궁 월드 안의 죽음은 {@code dungeon.DungeonManager} 가 먼저 처리한다
 * (공략 중이면 죽음을 취소하고 쓰러짐·관전, 그 밖에는 이 설정과 상관없이 {@link #apply} 로 언제나 보존).
 * pvp 모듈은 죽음 메시지만 바꾸므로 PvP 로 죽어도 같은 규칙이다.
 */
public final class DeathKeep implements Module, Listener {

    private final Services services;

    public DeathKeep(Services services) { this.services = services; }

    @Override
    public String name() { return "death"; }

    @Override
    public void enable() { Bukkit.getPluginManager().registerEvents(this, services.plugin()); }

    @Override
    public void disable() { HandlerList.unregisterAll(this); }

    /** 다른 플러그인·모듈이 드롭을 정한 뒤 마지막에 (취소된 죽음 = 미궁 쓰러짐은 건너뜀). */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onDeath(PlayerDeathEvent e) {
        if (services.dungeon().isLabyrinthWorld(e.getPlayer().getWorld())) return; // 미궁 월드 = DungeonManager (언제나 보존)
        Settings.Death d = services.settings().death();
        apply(e, d.keepInventory(), d.keepLevel());
    }

    /**
     * 죽음 이벤트에 보존 규칙을 적용한다 (DungeonManager 도 같은 함수). keepInventory 를 켜도 드롭 목록은 그대로 떨어지므로
     * 비워야 복제가 생기지 않는다. false 인 부분은 건드리지 않는다(바닐라 게임 규칙대로).
     */
    public static void apply(PlayerDeathEvent e, boolean keepInventory, boolean keepLevel) {
        if (keepInventory) {
            e.setKeepInventory(true);
            e.getDrops().clear();
        }
        if (keepLevel) {
            e.setKeepLevel(true);
            e.setDroppedExp(0);
        }
    }
}
