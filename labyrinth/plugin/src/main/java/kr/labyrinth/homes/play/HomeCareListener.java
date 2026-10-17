package kr.labyrinth.homes.play;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.combat.HealKind;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.homes.HomesConfig;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotRole;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Sound;
import org.bukkit.Tag;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.plugin.Plugin;
import org.bukkit.scheduler.BukkitTask;

/**
 * 집 안 회복 · 침대 쉬기 · 들어설 때 글 (0.3.7, plan §0·§8, 설계 §8). 소유: 묶음 C.
 * {@code PlayerMoveEvent} 는 쓰지 않는다 — 2틱 작업이 주 월드 접속자(≤ 10명)만 본다.
 * <ul>
 *   <li>회복 (1초마다): 내 집·초대받은 집 높이 창 안 + {@code home_regen.calm_seconds} 동안 안 맞음 + PvP 전투 아님 →
 *       최대 HP·MP 의 {@code home_regen.hp/mp} ({@code DamageService.heal REGEN} · {@code ClassService.restoreMana}). 미궁에는 안 넘어감.</li>
 *   <li>침대 쉬기: 내 집 안 침대 우클릭 → {@code bed_rest.seconds} 초 (움직이거나 맞으면 끊김) → 가득 (cooldown_seconds 에 한 번, ext {@code homes.rest_at}).
 *       바닐라 침대 동작(리스폰·잠)은 그대로.</li>
 *   <li>들어설 때 (0.5초마다): 다른 집터에 들어서면 액션바 "◆ 3번지 · 하린의 집" ({@code enter_actionbar}).</li>
 * </ul>
 */
public final class HomeCareListener implements Listener {

    private final Services services;
    private final HomesService service;
    private final Map<UUID, Long> lastHurt = new ConcurrentHashMap<>();
    private final Map<UUID, String> lastPlot = new HashMap<>();
    private final Map<UUID, BedRest.Session> rests = new HashMap<>();
    private BukkitTask task;
    private long tick;

    public HomeCareListener(Services services, HomesService service) {
        this.services = services;
        this.service = service;
    }

    HomesService service() { return service; }

    void start(Plugin plugin) {
        stop();
        task = Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 20L, 2L);
    }

    void stop() {
        if (task != null) task.cancel();
        task = null;
        for (UUID u : rests.keySet()) {
            Player p = Bukkit.getPlayer(u);
            if (p != null) services.hud().clearCast(p);
        }
        rests.clear();
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (e.getEntity() instanceof Player p) lastHurt.put(p.getUniqueId(), System.currentTimeMillis());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        UUID u = e.getPlayer().getUniqueId();
        lastHurt.remove(u);
        lastPlot.remove(u);
        rests.remove(u);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onBed(PlayerInteractEvent e) {
        if (e.getAction() != Action.RIGHT_CLICK_BLOCK || e.getHand() != EquipmentSlot.HAND) return;
        Block b = e.getClickedBlock();
        if (b == null || !Tag.BEDS.isTagged(b.getType())) return;
        if (e.useInteractedBlock() == Event.Result.DENY || !service.active()) return;
        Player p = e.getPlayer();
        PlotGeom plot = service.plotAt(b.getLocation());
        if (plot == null || !service.roleIn(p, plot).builds() || rests.containsKey(p.getUniqueId())) return;
        try {
            startRest(p);
        } catch (Throwable t) {
            Log.error("[집] 침대 쉬기 오류", t);
        }
    }

    private void startRest(Player p) {
        HomesConfig.BedRest cfg = service.config().bedRest();
        long now = System.currentTimeMillis();
        long left = BedRest.cooldownLeftMs(restAt(p), now, cfg.cooldownSeconds());
        if (left > 0) {
            bar(p, "<gray>조금 전에 쉬었습니다. <white>" + ((left + 999) / 1000) + "초</white> 뒤 다시", 40);
            return;
        }
        if (inCombat(p)) {
            bar(p, "<#ff8a8a>싸우는 중에는 쉴 수 없습니다.", 40);
            return;
        }
        if (full(p)) {
            bar(p, "<gray>HP·MP 가 이미 가득합니다.", 40);
            return;
        }
        if (cfg.seconds() <= 0) {
            finishRest(p);
            return;
        }
        Location l = p.getLocation();
        rests.put(p.getUniqueId(), new BedRest.Session(now, l.getX(), l.getY(), l.getZ()));
    }

    private void tick() {
        tick++;
        long now = System.currentTimeMillis();
        try {
            restTick(now);
        } catch (Throwable t) {
            Log.error("[집] 침대 쉬기 틱 오류", t);
        }
        boolean enter = tick % 5 == 0, regen = tick % 10 == 0;
        if ((!enter && !regen) || !service.active()) return;
        World main = Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0);
        if (main == null) return;
        HomesConfig c = service.config();
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (!main.equals(p.getWorld())) {
                lastPlot.remove(p.getUniqueId());
                continue;
            }
            try {
                PlotGeom plot = service.plotAt(p.getLocation());
                if (enter) enterCheck(p, plot, c);
                if (regen && plot != null) regen(p, plot, c, now);
            } catch (Throwable t) {
                Log.error("[집] 회복 틱 오류 (" + p.getName() + ")", t);
            }
        }
    }

    private void enterCheck(Player p, PlotGeom plot, HomesConfig c) {
        String id = plot == null ? "" : plot.id();
        String prev = lastPlot.put(p.getUniqueId(), id);
        if (plot == null || id.equals(prev) || !c.enterActionbar()) return;
        bar(p, PlotSigns.enterLine(plot, service.info(plot)), 50);
    }

    private void regen(Player p, PlotGeom plot, HomesConfig c, long now) {
        if (rests.containsKey(p.getUniqueId())) return;
        PlotRole role = service.roleIn(p, plot);
        HomesConfig.Regen r = c.regen();
        if (!HomeRegen.eligible(role, p.isDead(), inCombat(p), now, lastHurt.getOrDefault(p.getUniqueId(), 0L), r.calmSeconds())) return;
        double maxHp = services.stats().maxHp(p), hp = HomeRegen.amount(services.stats().currentHp(p), maxHp, r.hp());
        double maxMp = services.classes().maxMana(p), mp = HomeRegen.amount(services.classes().mana(p), maxMp, r.mp());
        if (hp > 0) services.damage().heal(p, hp, 0, HealKind.REGEN, false);
        if (mp > 0) services.classes().restoreMana(p, mp);
        if (hp >= 0.5 || mp >= 0.5) bar(p, "<#7fe07f>집 — 쉬는 중", 25);
    }

    private void restTick(long now) {
        if (rests.isEmpty()) return;
        int seconds = service.config().bedRest().seconds();
        Iterator<Map.Entry<UUID, BedRest.Session>> it = rests.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<UUID, BedRest.Session> e = it.next();
            Player p = Bukkit.getPlayer(e.getKey());
            if (p == null) {
                it.remove();
                continue;
            }
            Location l = p.getLocation();
            BedRest.Step st = BedRest.tick(e.getValue(), now, l.getX(), l.getY(), l.getZ(), p.isSleeping(),
                    lastHurt.getOrDefault(p.getUniqueId(), 0L), seconds);
            switch (st) {
                case WAIT -> services.hud().castBar(p, Text.mm("<#ffd36b>침대에서 쉬는 중"), BedRest.progress(e.getValue(), now, seconds), 10);
                case DONE -> {
                    it.remove();
                    services.hud().clearCast(p);
                    finishRest(p);
                }
                case CANCELLED -> {
                    it.remove();
                    services.hud().clearCast(p);
                    bar(p, "<gray>쉬기가 끊겼습니다.", 30);
                }
            }
        }
    }

    private void finishRest(Player p) {
        services.stats().heal(p, services.stats().maxHp(p));
        services.classes().restoreMana(p, services.classes().maxMana(p));
        services.hud().refresh(p);
        PlayerData d = services.data().get(p);
        d.ext().put(HomesNames.EXT_REST_AT, System.currentTimeMillis());
        d.markDirty();
        p.playSound(p.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_CHIME, 0.6f, 1.2f);
        bar(p, "<#7fe07f>푹 쉬었습니다. HP·MP 가득", 40);
    }

    private long restAt(Player p) {
        Object v = services.data().get(p).ext().get(HomesNames.EXT_REST_AT);
        return v instanceof Number n ? n.longValue() : 0L;
    }

    private boolean full(Player p) {
        double hp = services.stats().currentHp(p), maxHp = services.stats().maxHp(p);
        double mp = services.classes().mana(p), maxMp = services.classes().maxMana(p);
        return hp >= maxHp - 0.5 && mp >= maxMp - 0.5;
    }

    private boolean inCombat(Player p) {
        try {
            return services.targets().pvp().inCombat(p);
        } catch (Throwable t) {
            return false;
        }
    }

    private void bar(Player p, String mini, int ticks) { services.hud().actionBar(p, Text.mm(mini), ticks); }
}
