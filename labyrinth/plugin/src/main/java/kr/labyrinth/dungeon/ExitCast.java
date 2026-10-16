package kr.labyrinth.dungeon;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageService;
import kr.labyrinth.core.DeathPenaltyRules;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.scheduler.BukkitTask;

/**
 * 0.3.6.1 죽음 페널티 보완: 공략 중 살아 있고 전투 중(10초 안에 피해)이면 /미궁 퇴장·귀환과 입구 메뉴 '귀환' 도
 * 귀환 주문서처럼 시전한다 (config {@code death.penalty.combat_exit_seconds}, 기본 5초, 0 = 바로). 그동안 피해를 받으면 끊긴다.
 * 벌칙이 아니라 "죽기 직전에 퇴장 한 번으로 페널티를 피하는" 틈만 막는다. 쓰러진 사람·전투 밖은 지금처럼 바로 나간다.
 * 규칙은 {@link DeathPenaltyRules#exitCastSeconds}. 귀환 주문서 시전(items.ConsumableListener)은 그대로 따로 돈다.
 */
final class ExitCast implements Listener {

    private final DungeonManager manager;
    private final Map<UUID, Long> lastHurt = new ConcurrentHashMap<>();
    private final Map<UUID, BukkitTask> casting = new ConcurrentHashMap<>();

    /** 커스텀 피해(스킬·몹 공격·함정)는 바닐라 피해 이벤트 없이 HP 만 줄이므로 피해 파이프라인에서 본다. */
    private final DamageService.Hook hurtHook = new DamageService.Hook() {
        @Override
        public void after(DamageContext ctx) {
            if (ctx.target() instanceof Player p && ctx.dealt() > 0) hurt(p);
        }
    };

    ExitCast(DungeonManager manager) { this.manager = manager; }

    void start() {
        Bukkit.getPluginManager().registerEvents(this, manager.services().plugin());
        manager.services().damage().addHook(hurtHook);
    }

    void stop() {
        HandlerList.unregisterAll(this);
        manager.services().damage().removeHook(hurtHook);
        for (UUID u : casting.keySet()) {
            Player p = Bukkit.getPlayer(u);
            if (p != null) cancel(p, null);
        }
        casting.values().forEach(BukkitTask::cancel);
        casting.clear();
        lastHurt.clear();
    }

    private void hurt(Player p) {
        if (manager.runOf(p) != null) lastHurt.put(p.getUniqueId(), System.currentTimeMillis());
    }

    /** 바닐라 피해 (낙하·불·용암·바닐라 몹 등). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHurt(EntityDamageEvent e) {
        if (e.getEntity() instanceof Player p && e.getFinalDamage() > 0) hurt(p);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        // 전투 기록(lastHurt)은 남긴다 — 끊고 바로 다시 들어와 곧장 나가는 길을 만들지 않게
        cancel(e.getPlayer(), null);
    }

    /**
     * 스스로 나가기 요청. 시전이 필요하면 시작하고 true (지금은 안 나감), 아니면 false (부른 쪽이 바로 내보냄).
     */
    boolean tryBegin(Player p, Run r) {
        UUID u = p.getUniqueId();
        if (casting.containsKey(u)) {
            Text.error(p, "이미 나가는 중입니다.");
            return true;
        }
        long last = lastHurt.getOrDefault(u, -1L);
        long since = last < 0 ? -1 : System.currentTimeMillis() - last;
        double secs = DeathPenaltyRules.exitCastSeconds(manager.services().settings().deathPenalty(), r.adminTest(),
                r.isAlive(p) && !r.ending(), since);
        if (secs <= 0) return false;
        begin(p, r, secs, last);
        return true;
    }

    private void begin(Player p, Run r, double secs, long startHurt) {
        UUID u = p.getUniqueId();
        int total = Math.max(1, (int) Math.round(secs * 20));
        int[] t = {0};
        Text.send(p, DeathPenaltyRules.exitCastText(secs));
        p.playSound(p.getLocation(), Sound.BLOCK_PORTAL_TRIGGER, 0.3f, 1.8f);
        BukkitTask task = Bukkit.getScheduler().runTaskTimer(manager.services().plugin(), () -> {
            t[0] += 2;
            if (!p.isOnline() || p.isDead() || manager.runOf(p) != r || !r.isAlive(p) || r.ending()) {
                cancel(p, null);
                return;
            }
            if (lastHurt.getOrDefault(u, -1L) > startHurt) {
                cancel(p, "피해를 받아 귀환이 끊겼습니다.");
                return;
            }
            double prog = Math.min(1.0, (double) t[0] / total);
            manager.services().hud().castBar(p, Text.mm("<#c9a2ff>귀환 중 <gray>"
                    + String.format("%.1f", Math.max(0, (total - t[0]) / 20.0)) + "초"), prog, 6);
            p.getWorld().spawnParticle(Particle.PORTAL, p.getLocation().add(0, 1, 0), 10, 0.4, 0.8, 0.4, 0.3);
            if (t[0] >= total) {
                cancel(p, null);
                manager.leave(p);
                p.playSound(p.getLocation(), Sound.ENTITY_ENDERMAN_TELEPORT, 0.8f, 1.2f);
            }
        }, 2L, 2L);
        casting.put(u, task);
    }

    private void cancel(Player p, String msg) {
        BukkitTask task = casting.remove(p.getUniqueId());
        if (task == null) return;
        task.cancel();
        manager.services().hud().clearCast(p);
        if (msg != null) {
            manager.services().hud().actionBar(p, Text.mm("<#ff6b6b>" + msg), 30);
            p.playSound(p.getLocation(), Sound.BLOCK_FIRE_EXTINGUISH, 0.4f, 1.6f);
        }
    }
}
