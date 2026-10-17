package kr.labyrinth.mine;

import java.time.Duration;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageService;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.DeathPenalty;
import kr.labyrinth.core.DeathPenaltyRules;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Teleports;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.pvp.PvpSources;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.damage.DamageSource;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerKickEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;

/**
 * 광산 PvP (0.3.7 주인 결정 "광산 PVP 키자" → PvP 쓰러짐 비용 "던전과 같게"). 규칙은 {@link MinePvpRules} · {@link MineSafeZones}.
 * <ul>
 *   <li>피해 문: {@link #allowVanilla} (MineListener LOWEST·HIGHEST 가 묻는다) — 다른 파티 플레이어가 PvP 구역의 플레이어에게 준 것만.
 *       미궁 피해 처리(DamageService)는 {@link MineSafety#protects(MineApi, org.bukkit.entity.Entity, org.bukkit.entity.Entity)} 로 같은 판정.</li>
 *   <li>싸우는 중 시계 {@link MineCombat}: DamageService 훅(맞힘·피함) + 바닐라 PvP 피해(MONITOR).</li>
 *   <li>쓰러짐: PlayerDeathEvent HIGH (ignoreCancelled — DungeonManager 와 같은 자리) 에서 범인이 다른 플레이어면 죽음을 취소하고
 *       다음 틱 {@link DeathPenalty#onMineDown} (미궁과 같은 길) → 얕은 갱도 승강장에서 체력 가득. 죽음 줄은 PvpListener 가 당사자 둘에게.</li>
 *   <li>PvP 가 아닌 죽음(다른 플러그인 등): 취소하지 않고 부활 자리만 얕은 갱도 승강장.</li>
 *   <li>나가기 5초: {@link #holdExit} (/미궁 마을 · 메인 메뉴 "마을") · 승강기({@code MineLift}) · 다른 플러그인/명령 순간이동은 막음.</li>
 *   <li>싸우는 중 끊김: PlayerQuitEvent LOW → {@link MinePvpRules#combatQuit} → {@link DeathPenalty#onMineCombatQuit}, 다시 들어오면 승강장으로.</li>
 *   <li>보여 주기: 구역 경계를 넘으면 액션바 · 광산에 처음 들어올 때 채팅 한 번.</li>
 * </ul>
 */
final class MinePvp implements Listener {

    private final MineModule module;
    private final MineCombat combat = new MineCombat();
    /** 막타를 맞고 다음 틱 쓰러짐 처리를 기다리는 사람 (그동안 더 맞지 않음). */
    private final Set<UUID> downing = ConcurrentHashMap.newKeySet();
    /** 우리가 허락한 광산 밖 순간이동 (시전을 마친 /미궁 마을 · 승강기 도착). */
    private final Set<UUID> bypass = ConcurrentHashMap.newKeySet();
    /** 광산에서 진짜로 죽음 (PvP 가 아님) — 부활 자리를 승강장으로. */
    private final Set<UUID> diedInMine = ConcurrentHashMap.newKeySet();
    /** 서버 쪽에서 내보냄 (/restart · /kick · /ban · 화이트리스트) — 이어지는 PlayerQuitEvent 에서 벌하지 않게. */
    private final Set<UUID> serverKicked = ConcurrentHashMap.newKeySet();
    private final Map<UUID, BukkitTask> exits = new ConcurrentHashMap<>();
    /** 마지막으로 보여 준 구역 (true = PvP 구역). */
    private final Map<UUID, Boolean> zone = new ConcurrentHashMap<>();
    private final Set<UUID> noticed = ConcurrentHashMap.newKeySet();
    private final Map<UUID, Long> lastBlockedNote = new ConcurrentHashMap<>();
    private volatile boolean stopping;

    /** 미궁 피해(근접·화살·스킬·지속 피해)는 바닐라 피해 이벤트 없이 들어오므로 피해 파이프라인에서 본다. */
    private final DamageService.Hook hook = new DamageService.Hook() {
        @Override
        public void after(DamageContext ctx) {
            if (!ctx.cancelled()) mark(ctx, ctx.dealt() > 0);
        }

        @Override
        public void evaded(DamageContext ctx) { mark(ctx, false); }
    };

    MinePvp(MineModule module) { this.module = module; }

    private Services services() { return module.services(); }

    void start() {
        stopping = false;
        Bukkit.getPluginManager().registerEvents(this, services().plugin());
        services().damage().addHook(hook);
    }

    void stop() {
        stopping = true;
        HandlerList.unregisterAll(this);
        services().damage().removeHook(hook);
        for (UUID u : exits.keySet()) {
            Player p = Bukkit.getPlayer(u);
            if (p != null) cancelExit(p, null);
        }
        exits.values().forEach(BukkitTask::cancel);
        exits.clear();
        downing.clear();
        bypass.clear();
        diedInMine.clear();
        serverKicked.clear();
        zone.clear();
        noticed.clear();
        combat.clear();
    }

    MineCombat combat() { return combat; }

    boolean downing(Player p) { return p != null && downing.contains(p.getUniqueId()); }

    private static boolean alive(Player p) {
        return !p.isDead() && (p.getGameMode() == GameMode.SURVIVAL || p.getGameMode() == GameMode.ADVENTURE);
    }

    private boolean onGround(Player p) { return !module.pvpSafeAt(p.getLocation()); }

    // ── 싸우는 중 ───────────────────────────────────────────────────────

    private void mark(DamageContext ctx, boolean hurt) {
        Player a = ctx.attackerPlayer();
        if (a == null || !(ctx.target() instanceof Player v) || a.equals(v) || !module.isMineWorld(v.getWorld())) return;
        long now = System.currentTimeMillis();
        combat.mark(a.getUniqueId(), v.getUniqueId(), now);
        if (hurt) combat.hurt(v.getUniqueId(), now);
    }

    /** 바닐라 PvP 피해 (피해 물약 · 가시 · 쇠뇌 폭죽 — 근접·화살은 CombatListener 가 취소하고 위 훅으로 간다). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onVanillaHit(EntityDamageByEntityEvent e) {
        if (!(e.getEntity() instanceof Player v) || !module.isMineWorld(v.getWorld())) return;
        if (services().damage().isApplyingVanilla()) return; // 미궁 막타 — 훅이 이미 적음
        Player a = PvpSources.playerBehind(e.getDamager(), e.getDamageSource());
        if (a == null || a.equals(v)) return;
        long now = System.currentTimeMillis();
        combat.mark(a.getUniqueId(), v.getUniqueId(), now);
        if (e.getFinalDamage() > 0) combat.hurt(v.getUniqueId(), now);
    }

    /**
     * 광산 PvP 구역에서 나갈 때 기다릴 초 (0 = 바로) — 광산 PvP 켜짐 · 광산 월드 · PvP 구역 · 살아 있음 · 10초 안에 때리거나 맞음 ·
     * 잃을 것이 있음 · {@code combat_exit_seconds}.
     */
    double exitCastSeconds(Player p) {
        if (p == null || !module.pvpEnabled() || !module.isMineWorld(p.getWorld())) return 0;
        return MinePvpRules.exitCastSeconds(services().settings().deathPenalty(), module.config().pvp().penalty(), true, onGround(p), alive(p),
                combat.since(p.getUniqueId(), System.currentTimeMillis()));
    }

    // ── 바닐라 피해 문 ──────────────────────────────────────────────────

    /**
     * 광산 월드의 바닐라 피해를 통과시킬지 (MineListener 가 나머지는 모두 취소). 맞는 쪽이 플레이어 · 광산 PvP 켜짐이고,
     * (1) 미궁 피해 처리가 이미 판정을 통과시킨 막타(바닐라 길로 죽임) 이거나 (2) 다른 플레이어가 준 근접·투사체·피해 물약·가시·폭죽이고
     * PvP 규칙상 적일 때만. 떨어짐·불·독·시듦·몹·{@code /kill} 은 거짓.
     */
    boolean allowVanilla(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof Player v)) return false;
        boolean on = module.pvpEnabled();
        boolean applying = on && services().damage().isApplyingVanilla();
        boolean enemy = false;
        if (on && !applying && e instanceof EntityDamageByEntityEvent be && MinePvpRules.vanillaPvpCause(e.getCause())) {
            Player a = PvpSources.playerBehind(be.getDamager(), e.getDamageSource());
            enemy = a != null && module.pvpAllows(a, v);
        }
        return MinePvpRules.vanillaGate(on, true, applying, e.getCause(), enemy);
    }

    // ── 쓰러짐 ──────────────────────────────────────────────────────────

    private static Player culprit(PlayerDeathEvent e) {
        Player v = e.getPlayer();
        Player k = null;
        try {
            DamageSource ds = e.getDamageSource();
            k = PvpSources.playerBehind(ds.getDirectEntity(), ds);
        } catch (Throwable ignored) {
            // 피해 원인 API 가 없는 죽음 — getKiller 로
        }
        if (k == null) k = v.getKiller();
        return k == null || k.equals(v) ? null : k;
    }

    /** 다른 플레이어에게 쓰러짐: 죽음 취소 (미궁 공략 쓰러짐과 같은 자리 — DeathKeep HIGHEST·MONITOR 는 ignoreCancelled 라 건너뜀). */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDeath(PlayerDeathEvent e) {
        Player p = e.getPlayer();
        if (!module.isMineWorld(p.getWorld()) || !module.pvpEnabled()) return;
        Player killer = culprit(e);
        if (killer == null) return;
        e.setCancelled(true);
        var s = services();
        s.stats().setHp(p, s.stats().maxHp(p));
        p.setFireTicks(0);
        p.setFallDistance(0);
        if (!downing.add(p.getUniqueId())) return; // 같은 틱 두 번째 막타
        String name = killer.getName();
        Bukkit.getScheduler().runTask(s.plugin(), () -> knockDown(p, name));
    }

    /** 다음 틱 (DungeonManager 와 같은 차례): 미궁과 같은 페널티 → 얕은 갱도 승강장에서 체력 가득. */
    void knockDown(Player p, String killer) {
        UUID u = p.getUniqueId();
        if (!downing.contains(u)) return; // 그사이 접속을 끊어 onQuit 이 처리함
        var s = services();
        try {
            if (!p.isOnline()) return;
            module.lift().cancel(p);
            cancelExit(p, null);
            combat.forget(u);
            DeathPenalty.onMineDown(s, p, MinePvpRules.where(module.config().pvp().penalty()));
            try {
                s.effects().cleanse(p);
                for (PotionEffect pe : p.getActivePotionEffects()) {
                    if (pe.getType().getEffectCategory() == PotionEffectType.Category.HARMFUL) p.removePotionEffect(pe.getType());
                }
            } catch (Throwable t) {
                Log.warnOnce("mine-pvp-cleanse", "[광산 PvP] 쓰러짐 효과 지우기 오류: " + t);
            }
            p.setFireTicks(0);
            p.setFallDistance(0);
            Location to = module.entrance();
            if (to != null) Teleports.to(p, to);
            s.stats().setHp(p, s.stats().maxHp(p));
            module.applyRules(p);
            zone.remove(u);
            String at = module.entranceName();
            p.showTitle(Title.title(Text.mm(MinePvpRules.DOWN_TITLE), Text.mm(DeathPenaltyRules.mineRestartText(at)),
                    Title.Times.times(Duration.ofMillis(200), Duration.ofMillis(2500), Duration.ofMillis(700))));
            p.playSound(p.getLocation(), Sound.ENTITY_WITHER_SPAWN, 0.4f, 1.6f);
            for (Player o : s.party().onlineMembers(p)) {
                if (!o.equals(p) && module.isMineWorld(o.getWorld())) Text.send(o, MinePvpRules.partyDownText(Text.escape(p.getName())));
            }
            Log.info("[광산 PvP] " + p.getName() + " 쓰러짐 (" + killer + ") → " + at);
        } catch (Throwable t) {
            Log.error("[광산 PvP] 쓰러짐 처리 실패 (" + p.getName() + ")", t);
        } finally {
            downing.remove(u);
        }
    }

    /** PvP 가 아닌 진짜 죽음 (다른 플러그인 등 — 광산의 떨어짐·/kill 은 이미 막힘): 부활 자리만 얕은 갱도 승강장으로. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onRealDeath(PlayerDeathEvent e) {
        if (module.isMineWorld(e.getPlayer().getWorld())) diedInMine.add(e.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onRespawn(PlayerRespawnEvent e) {
        if (!diedInMine.remove(e.getPlayer().getUniqueId())) return;
        Location to = module.entrance();
        if (to != null) e.setRespawnLocation(to);
    }

    // ── 나가기 시전 ─────────────────────────────────────────────────────

    /** {@link MineApi#holdExit}: PvP 구역에서 싸우는 중이면 5초 시전 (맞으면 끊김, 움직여도 됨) 뒤 go. */
    boolean holdExit(Player p, Runnable go) {
        if (p == null || go == null) return false;
        UUID u = p.getUniqueId();
        if (bypass.contains(u)) return false;
        if (exits.containsKey(u)) {
            Text.error(p, "이미 나가는 중입니다.");
            return true;
        }
        double secs = exitCastSeconds(p);
        if (secs <= 0) return false;
        long startHurt = combat.lastHurt(u);
        int total = Math.max(1, (int) Math.round(secs * 20));
        int[] t = {0};
        Text.send(p, DeathPenaltyRules.exitCastText(secs));
        p.playSound(p.getLocation(), Sound.BLOCK_PORTAL_TRIGGER, 0.3f, 1.8f);
        BukkitTask task = Bukkit.getScheduler().runTaskTimer(services().plugin(), () -> {
            t[0] += 2;
            if (!p.isOnline() || p.isDead() || !module.isMineWorld(p.getWorld()) || downing.contains(u)) {
                cancelExit(p, null);
                return;
            }
            if (combat.lastHurt(u) > startHurt) {
                cancelExit(p, MinePvpRules.EXIT_HIT);
                return;
            }
            double prog = Math.min(1.0, (double) t[0] / total);
            services().hud().castBar(p, Text.mm("<#c9a2ff>귀환 중 <gray>"
                    + String.format(java.util.Locale.ROOT, "%.1f", Math.max(0, (total - t[0]) / 20.0)) + "초"), prog, 6);
            p.getWorld().spawnParticle(Particle.PORTAL, p.getLocation().add(0, 1, 0), 10, 0.4, 0.8, 0.4, 0.3);
            if (t[0] >= total) {
                cancelExit(p, null);
                runBypassed(p, go);
            }
        }, 2L, 2L);
        exits.put(u, task);
        return true;
    }

    boolean exiting(Player p) { return p != null && exits.containsKey(p.getUniqueId()); }

    private void cancelExit(Player p, String msg) {
        BukkitTask task = exits.remove(p.getUniqueId());
        if (task == null) return;
        task.cancel();
        services().hud().clearCast(p);
        if (msg != null && p.isOnline()) {
            services().hud().actionBar(p, Text.mm("<#ff6b6b>" + msg), 30);
            p.playSound(p.getLocation(), Sound.BLOCK_FIRE_EXTINGUISH, 0.4f, 1.6f);
        }
    }

    /** 우리가 허락한 광산 밖 순간이동 (시전을 마친 나가기 · 승강기 도착) — {@link #onTeleport} 가 막지 않게. */
    void runBypassed(Player p, Runnable r) {
        UUID u = p.getUniqueId();
        bypass.add(u);
        try {
            r.run();
        } finally {
            bypass.remove(u);
        }
    }

    /**
     * 다른 플러그인·{@code /tp} 등으로 광산 밖으로 가는 순간이동: PvP 구역에서 싸우는 중이면 막는다 (미룰 수 없으므로).
     * 관리자 · 우리가 허락한 것 · 미궁 입장(공략 시작)은 통과.
     */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        PlayerTeleportEvent.TeleportCause c = e.getCause();
        if (c != PlayerTeleportEvent.TeleportCause.COMMAND && c != PlayerTeleportEvent.TeleportCause.PLUGIN
                && c != PlayerTeleportEvent.TeleportCause.UNKNOWN) return;
        Location to = e.getTo();
        if (to == null || to.getWorld() == null || !module.isMineWorld(e.getFrom().getWorld()) || module.isMineWorld(to.getWorld())) return;
        Player p = e.getPlayer();
        if (bypass.contains(p.getUniqueId()) || p.hasPermission(CommandService.PERM_ADMIN)) return;
        if (services().dungeon().isLabyrinthWorld(to.getWorld())) return;
        if (exitCastSeconds(p) <= 0) return;
        e.setCancelled(true);
        long now = System.currentTimeMillis();
        Long last = lastBlockedNote.put(p.getUniqueId(), now);
        if (last == null || now - last > 1000) Text.send(p, MinePvpRules.TELEPORT_BLOCKED);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorld(PlayerChangedWorldEvent e) {
        if (!module.isMineWorld(e.getFrom())) return;
        Player p = e.getPlayer();
        cancelExit(p, null);
        combat.forget(p.getUniqueId());
        zone.remove(p.getUniqueId());
    }

    // ── 싸우는 중 접속 끊김 ─────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onKick(PlayerKickEvent e) {
        if (DeathPenaltyRules.serverKick(e.getCause().name())) serverKicked.add(e.getPlayer().getUniqueId());
    }

    /**
     * PvP 구역에서 싸우는 중(10초 안에 때리거나 맞음 · 싸우는 중 나가기 시전 · 막타 뒤)에 끊으면 쓰러진 것으로 친다.
     * LOW = 시전 취소·스탯 정리(NORMAL)와 데이터 저장(MONITOR)보다 먼저 (DungeonManager.onQuitInCombat 과 같은 자리).
     * 순간이동은 하지 않는다 (나가는 중이라 믿을 수 없음) — 표시만 남기고 다시 들어올 때 옮긴다.
     */
    @EventHandler(priority = EventPriority.LOW)
    public void onQuit(PlayerQuitEvent e) {
        Player p = e.getPlayer();
        UUID u = p.getUniqueId();
        boolean inMine = module.isMineWorld(p.getWorld());
        boolean wasDowning = downing.contains(u);
        if (!inMine && !wasDowning) return;
        var s = services();
        try {
            boolean serverSide = stopping || Bukkit.isStopping() || serverKicked.contains(u);
            long since = combat.since(u, System.currentTimeMillis());
            boolean casting = exits.containsKey(u) || module.lift().combatRiding(p);
            var q = new MinePvpRules.MineQuit(module.pvpEnabled(), inMine, onGround(p), alive(p), since, casting, serverSide, wasDowning);
            boolean penalty = module.config().pvp().penalty();
            if (MinePvpRules.combatQuit(s.settings().deathPenalty(), penalty, q) != DeathPenaltyRules.QuitVerdict.APPLY) return;
            String why = wasDowning ? "막타를 맞은 뒤" : casting ? "나가기 시전 중"
                    : "마지막 PvP " + String.format(java.util.Locale.ROOT, "%.1f", since / 1000.0) + "초 전";
            Log.info("[죽음 페널티] " + p.getName() + " 싸우는 중 접속 끊김 → 쓰러진 것으로 침 (" + why + ", 광산)");
            downing.remove(u);
            cancelExit(p, null);
            module.lift().cancel(p);
            DeathPenalty.onMineCombatQuit(s, p, MinePvpRules.where(penalty), DeathPenaltyRules.mineRestartText(module.entranceName()));
            PlayerData d = s.data().get(p);
            d.ext().put(MineNames.EXT_PVP_DOWN, true);
            d.markDirty();
            try {
                s.stats().setHp(p, s.stats().maxHp(p));
                p.setFireTicks(0);
            } catch (Throwable t) {
                Log.error("[광산 PvP] 접속 끊김 쓰러짐 상태 정리 실패 (" + p.getName() + ")", t);
            }
            combat.forget(u);
            for (Player o : s.party().onlineMembers(p)) {
                if (!o.equals(p) && module.isMineWorld(o.getWorld())) Text.send(o, DeathPenaltyRules.quitDownPartyText(Text.escape(p.getName())));
            }
        } catch (Throwable t) {
            Log.error("[광산 PvP] 싸우는 중 접속 끊김 처리 실패 (" + p.getName() + ")", t);
        }
    }

    @EventHandler(priority = EventPriority.NORMAL)
    public void onQuitCleanup(PlayerQuitEvent e) {
        Player p = e.getPlayer();
        cancelExit(p, null); // 전투 기록은 남긴다 — 끊고 바로 들어와 곧장 나가는 길을 만들지 않게
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuitDone(PlayerQuitEvent e) {
        UUID u = e.getPlayer().getUniqueId();
        serverKicked.remove(u);
        zone.remove(u);
        noticed.remove(u);
        lastBlockedNote.remove(u);
        diedInMine.remove(u);
    }

    /** 싸우다 끊어 쓰러진 사람: 다시 들어오면 그 자리에서 얕은 갱도 승강장으로 (안내는 DungeonManager.onJoin 8틱 뒤 showQuitNotice). */
    @EventHandler(priority = EventPriority.NORMAL)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        UUID u = p.getUniqueId();
        serverKicked.remove(u);
        downing.remove(u);
        try {
            PlayerData d = services().data().get(p);
            Object flag = d.ext().remove(MineNames.EXT_PVP_DOWN);
            if (flag == null) return;
            d.markDirty();
            if (!Boolean.TRUE.equals(flag) && !"true".equals(String.valueOf(flag))) return;
            if (!module.active() || !module.isMineWorld(p.getWorld())) return;
            Location to = module.entrance();
            p.setFallDistance(0);
            if (to != null) Teleports.to(p, to);
            module.applyRules(p);
        } catch (Throwable t) {
            Log.error("[광산 PvP] 다시 접속 처리 실패 (" + p.getName() + ")", t);
        }
    }

    // ── 보여 주기 (MineModule.sweepPlayers 가 0.5초마다) ─────────────────

    /** 광산 사람 하나: 처음 안내 · 구역이 바뀌면 액션바 (광산에 들어와 첫 검사 때도 지금 구역 한 번). */
    void sweep(Player p) {
        UUID u = p.getUniqueId();
        if (!module.pvpEnabled() || !alive(p)) {
            zone.remove(u);
            return;
        }
        noticeOnce(p);
        boolean ground = onGround(p);
        Boolean last = zone.put(u, ground);
        if (last != null && last == ground) return;
        services().hud().actionBar(p, Text.mm(ground ? MinePvpRules.TO_PVP : MinePvpRules.TO_SAFE), 50);
    }

    /** 광산을 떠난 사람의 구역 기억 지우기. */
    void prune() {
        zone.keySet().removeIf(u -> {
            Player q = Bukkit.getPlayer(u);
            return q == null || !module.isMineWorld(q.getWorld());
        });
    }

    private void noticeOnce(Player p) {
        UUID u = p.getUniqueId();
        if (noticed.contains(u)) return;
        try {
            PlayerData d = services().data().get(p);
            noticed.add(u);
            Object seen = d.ext().get(MineNames.EXT_PVP_NOTICE);
            if (seen instanceof Number n && n.intValue() >= MineNames.PVP_NOTICE_VERSION) return;
            d.ext().put(MineNames.EXT_PVP_NOTICE, MineNames.PVP_NOTICE_VERSION);
            d.markDirty();
            Text.send(p, DeathPenaltyRules.mineNotice(services().settings().deathPenalty(), module.config().pvp().penalty(),
                    module.entranceName()));
        } catch (Throwable t) {
            Log.warnOnce("mine-pvp-notice", "[광산 PvP] 안내 오류: " + t);
        }
    }
}
