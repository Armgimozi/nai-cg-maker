package kr.labyrinth.combat;

import io.papermc.paper.event.player.PlayerInventorySlotChangeEvent;
import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Text;
import kr.labyrinth.stats.DerivedStats;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.SoundCategory;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.EntityShootBowEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Vector;

/**
 * 게이지 없는 기본 공격 (0.3.5, combat_spec §2) — 플레이어마다 {@link AttackTiming} 시계 하나.
 * <ul>
 *   <li>미궁 무기·맨손을 들면 바닐라 공격 속도가 1024 라 게이지가 늘 꽉 차 있다 ({@code StatService}). 대신 여기서
 *       {@link PrePlayerAttackEntityEvent}(대상이 살아 있는 적) 를 무기 간격대로만 통과시킨다 — 통과한 공격은 언제나 온전한 피해.</li>
 *   <li>너무 이른 클릭은 취소. 간격 끝 0.35초 안이면 한 번 기억했다가 시각이 되면 넣는다(휘두름 + 같은 공격 경로).
 *       대상이 죽었거나 멀어졌거나(눈 → 히트박스 ≤ 사거리 + 0.3) 시야(50°·가림) 밖이거나 무기를 바꿨으면 조용히 버린다.
 *       더 이르면 본인에게만 작은 '휙' 소리.</li>
 *   <li>무기를 바꾸면 새 무기의 첫 공격은 지금 + 새 주기 × 0.5 뒤부터 (활은 그 안에 당김이 들어간다 — {@link AttackTiming#swap}).</li>
 *   <li>활: 끝까지 당겨지면 본인에게만 작은 '탁' 소리 (바닐라 활 그림은 늘 1초라서).</li>
 *   <li>활 쏘기와 근접 치기는 같은 시계 (0.3.6.1) — 공격마다 제 시간을 쓴다: 근접 한 대 = 그 뒤 간격, 화살 한 발 = 그 앞 당김 + 그 뒤
 *       다시 메기기 0.15초. 쏜 직후 단도로 바꾸면 약 0.2초 뒤에 찌르고, 근접 한 대 뒤의 당김은 그 간격이 끝난 뒤부터 센다
 *       ({@link AttackTiming#bowDrawnMs} · {@link AttackTiming#shot}). 번갈아 써도 두 무기 중 센 쪽보다 빨라지지 않는다.
 *       그 기다림은 활의 바닐라 재사용 대기(하얀 막대)로 보여 주고 그동안 당기지 못하게 한다 — 화면에 끝까지 당겨진 활 = 서버가 센 끝까지 당김
 *       ({@link #gateBow}). 주손에 미궁 근접·시전 무기를 든 채 보조손 활은 당기지 않는다 ({@link #onUseBow}).</li>
 * </ul>
 * 바닐라 무기(칼·도끼·삼지창 등 아이템에 공격 속도가 있는 것)는 바닐라 게이지 그대로라 여기서 막지 않는다.
 */
final class AttackClock implements Listener {

    /** 기억한 클릭의 유효 시간 (ms). */
    static final long BUFFER_MAX_AGE_MS = 600;
    /** 기억한 클릭을 넣을 때 허용 각도 (도). */
    static final double BUFFER_VIEW_DEG = 50;
    /** 기억한 클릭 사거리 여유 (블록). */
    static final double BUFFER_REACH_SLACK = 0.3;
    /** 무기를 바꾸면 새 간격의 이만큼을 기다린다. */
    static final double SWAP_DELAY_FRACTION = 0.5;
    /** 너무 이른 클릭 소리 간격 (ms). */
    static final long WHOOSH_GAP_MS = 150;
    /** 활: 놓고 다시 메기는 시간 (ms) — 한 발 주기 = 당김 + 이것. */
    static final long NOCK_MS = Math.round(CombatMath.BOW_NOCK * 1000.0);

    private final Services services;
    private final Map<UUID, AttackTiming> clocks = new ConcurrentHashMap<>();
    /** 활을 당기는 중 이미 '탁' 소리를 낸 플레이어. */
    private final Map<UUID, Boolean> drawCued = new ConcurrentHashMap<>();
    private BukkitTask task;
    /** 기억한 클릭을 넣는 중 (그 공격의 PrePlayerAttackEntityEvent 는 그대로 통과). */
    private UUID releasing;

    AttackClock(Services services) { this.services = services; }

    void start() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tick, 1L, 1L);
    }

    void stop() {
        if (task != null) task.cancel();
        HandlerList.unregisterAll(this);
        clocks.clear();
        drawCued.clear();
    }

    private AttackTiming clock(Player p) { return clocks.computeIfAbsent(p.getUniqueId(), u -> new AttackTiming()); }

    private Settings.Combat cfg() { return services.settings().combat(); }

    private static long ms(double seconds) { return Math.max(1, Math.round(seconds * 1000.0)); }

    /** 손에 든 것의 표시 (칸 + 아이템 id) — 기억한 클릭을 넣을 때 같은 무기인지. */
    private String weaponKey(Player p) {
        ItemStack main = p.getInventory().getItemInMainHand();
        String id = services.items().defOf(main).map(ItemDef::id).orElse(main.getType().name());
        return p.getInventory().getHeldItemSlot() + ":" + id;
    }

    // ── 클릭 ──────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onPreAttack(PrePlayerAttackEntityEvent e) {
        Player p = e.getPlayer();
        if (p.getUniqueId().equals(releasing)) return;
        if (!(e.getAttacked() instanceof LivingEntity target) || target.isDead() || !e.willAttack()) return;
        if (p.getGameMode() == GameMode.SPECTATOR || !services.stats().attackClocked(p)) return;
        if (!services.targets().isEnemy(p, target)) return;
        DerivedStats s = services.stats().get(p);
        Settings.Combat c = cfg();
        long now = System.currentTimeMillis();
        AttackTiming t = clock(p);
        AttackTiming.Result r = t.click(now, ms(s.attackInterval()), c.clickToleranceMs(), ms(c.earlyClickBuffer()),
                target.getUniqueId(), weaponKey(p));
        if (r == AttackTiming.Result.ACCEPT) return;
        e.setCancelled(true);
        if (r == AttackTiming.Result.EARLY && c.earlyClickSound() && t.whoosh(now, WHOOSH_GAP_MS)) {
            float pitch = (float) Math.max(0.5, Math.min(2.0, 1.6 - 0.6 * s.attackInterval()));
            p.playSound(p, Sound.ENTITY_PLAYER_ATTACK_NODAMAGE, SoundCategory.PLAYERS, 0.25f, pitch);
        }
    }

    // ── 무기 바꿈 ─────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHeld(PlayerItemHeldEvent e) {
        swapped(e.getPlayer(), e.getPlayer().getInventory().getItem(e.getNewSlot()));
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSwapHands(PlayerSwapHandItemsEvent e) {
        swapped(e.getPlayer(), e.getMainHandItem());
    }

    /** 칸은 그대로인데 손의 무기가 바뀜 (줍기·명령 지급 등). 같은 무기(설명만 다시 그림)면 무시. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onSlot(PlayerInventorySlotChangeEvent e) {
        Player p = e.getPlayer();
        if (e.getSlot() != p.getInventory().getHeldItemSlot()) return;
        String before = services.items().defOf(e.getOldItemStack()).map(ItemDef::id).orElse(e.getOldItemStack().getType().name());
        String after = services.items().defOf(e.getNewItemStack()).map(ItemDef::id).orElse(e.getNewItemStack().getType().name());
        if (!Objects.equals(before, after)) swapped(p, e.getNewItemStack());
    }

    private void swapped(Player p, ItemStack newMain) {
        AttackTiming t = clocks.get(p.getUniqueId());
        if (t == null) return;
        ItemDef def = services.items().defOf(newMain).filter(ItemDef::isWeapon).orElse(null);
        WeaponAttack a = def != null ? WeaponAttack.of(def) : WeaponAttack.UNARMED;
        double as = services.stats().get(p).attackSpeed();
        double min = cfg().attackIntervalMin();
        // 활의 첫 공격(화살)은 당김을 세기 시작하고 끝까지 당긴 뒤에 나간다 — 바꿈 대기에서 당김만큼 빼 준다 (0.3.6.1)
        long lead = a.ranged() ? ms(CombatMath.bowDraw(a.interval(), as, min)) : 0;
        t.swap(System.currentTimeMillis(), ms(CombatMath.cycle(a, as, min)), SWAP_DELAY_FRACTION, lead);
        drawCued.remove(p.getUniqueId());
        gateBow(p, t, newMain); // 근접 간격이 남았으면 그동안 활을 못 당기게 (손맛 검토 1)
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        clocks.remove(e.getPlayer().getUniqueId());
        drawCued.remove(e.getPlayer().getUniqueId());
        offHandHinted.remove(e.getPlayer().getUniqueId());
    }

    // ── 1틱: 기억한 클릭 넣기 · 활 끝까지 당김 소리 ─────────────────────────

    private void tick() {
        long now = System.currentTimeMillis();
        for (Map.Entry<UUID, AttackTiming> en : clocks.entrySet()) {
            AttackTiming t = en.getValue();
            if (!t.hasBuffer()) continue;
            if (t.bufferExpired(now, BUFFER_MAX_AGE_MS)) {
                t.clearBuffer();
                continue;
            }
            if (!t.bufferReady(now)) continue;
            Player p = Bukkit.getPlayer(en.getKey());
            LivingEntity target = p == null ? null : Bukkit.getEntity(t.bufferedTarget()) instanceof LivingEntity le ? le : null;
            if (p == null || target == null || !canRelease(p, target, t)) {
                t.clearBuffer();
                continue;
            }
            t.fireBuffered(now, ms(services.stats().get(p).attackInterval()), cfg().clickToleranceMs());
            release(p, target);
        }
        if (cfg().bowFullDrawCue()) drawCue();
    }

    private boolean canRelease(Player p, LivingEntity target, AttackTiming t) {
        if (!p.isOnline() || p.isDead() || p.getGameMode() == GameMode.SPECTATOR) return false;
        if (!target.isValid() || target.isDead() || !target.getWorld().equals(p.getWorld())) return false;
        if (!weaponKey(p).equals(t.bufferedWeapon()) || !services.stats().attackClocked(p)) return false;
        if (services.effects().isStunned(p) || !services.targets().isEnemy(p, target)) return false;
        Location eye = p.getEyeLocation();
        AttributeInstance reachAttr = p.getAttribute(Attribute.ENTITY_INTERACTION_RANGE);
        double reach = (reachAttr == null ? 3.0 : reachAttr.getValue()) + BUFFER_REACH_SLACK;
        if (distanceToBox(eye.toVector(), target.getBoundingBox()) > reach) return false;
        Vector look = eye.getDirection();
        Vector to = target.getBoundingBox().getCenter().subtract(eye.toVector());
        if (to.lengthSquared() > 1e-6 && look.angle(to) > Math.toRadians(BUFFER_VIEW_DEG)) return false;
        return p.hasLineOfSight(target);
    }

    /** 점 → 상자 가장 가까운 점 거리. */
    static double distanceToBox(Vector point, BoundingBox box) {
        double dx = Math.max(Math.max(box.getMinX() - point.getX(), 0), point.getX() - box.getMaxX());
        double dy = Math.max(Math.max(box.getMinY() - point.getY(), 0), point.getY() - box.getMaxY());
        double dz = Math.max(Math.max(box.getMinZ() - point.getZ(), 0), point.getZ() - box.getMaxZ());
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    /** 기억한 클릭 넣기: 휘두르는 모습 + 바닐라 공격 (같은 피해 경로 — 점프 치명·PvP 넉백·발화·타격 소리 포함). */
    private void release(Player p, LivingEntity target) {
        releasing = p.getUniqueId();
        try {
            p.swingMainHand();
            p.attack(target);
        } catch (Throwable ex) {
            kr.labyrinth.core.Log.error("기억한 공격 넣기 오류", ex);
        } finally {
            releasing = null;
        }
    }

    private void drawCue() {
        long now = System.currentTimeMillis();
        for (Player p : Bukkit.getOnlinePlayers()) {
            UUID u = p.getUniqueId();
            ItemStack active = p.hasActiveItem() ? p.getActiveItem() : null;
            if (active == null || active.getType() != Material.BOW) {
                drawCued.remove(u);
                continue;
            }
            if (drawCued.containsKey(u)) continue;
            DerivedStats s = services.stats().get(p);
            if (s.weapon() == null || !s.weapon().ranged()) continue;
            Draw d = draw(p, 0, now); // 당긴 시간을 못 읽으면 0 (소리 없음)
            if (d.force() >= 0.999) {
                drawCued.put(u, Boolean.TRUE);
                p.playSound(p, Sound.ITEM_CROSSBOW_LOADING_END, SoundCategory.PLAYERS, 0.3f, 1.2f);
            }
        }
    }

    /** 활 한 발의 당김: 바닐라가 잰 당긴 시간(ms), 끝까지 당기는 시간(초), 서버가 인정한 당긴 시간(ms), 세기. */
    private record Draw(long usedMs, double fullDraw, long drawnMs, double force) {}

    /**
     * 당김 재기 (상태는 바꾸지 않음). 당긴 시간을 못 읽으면 바닐라 세기에서 되돌린다. 당김은 공유 시계의 다음 시각부터 센다
     * (앞 화살 뒤에는 다시 메기기 0.15초 뒤부터, 근접 한 대 뒤에는 그 간격이 끝난 뒤부터).
     */
    private Draw draw(Player p, double vanillaForce, long now) {
        DerivedStats s = services.stats().get(p);
        double full = CombatMath.bowDraw(s.weapon() != null && s.weapon().ranged() ? s.weaponInterval() : 1.15,
                s.attackSpeed(), cfg().attackIntervalMin());
        int used = 0;
        try {
            used = p.getActiveItemUsedTime();
        } catch (Throwable ignored) {
            // 없는 판
        }
        double ticks = used > 0 ? used : CombatMath.ticksFromVanillaForce(vanillaForce);
        long usedMs = Math.round(ticks * 50.0);
        AttackTiming t = clocks.get(p.getUniqueId());
        long drawnMs = t == null ? usedMs : t.bowDrawnMs(now, usedMs, cfg().clickToleranceMs());
        return new Draw(usedMs, full, drawnMs, CombatMath.bowForce(drawnMs / 1000.0, full));
    }

    /** 활 한 발: 서버가 잰 당김 세기 (0~1) — 무기 스킬 '웅크리고 당겨 쏘기' 위력도 같은 값. 시계는 바꾸지 않는다. */
    double bowForce(Player p, double vanillaForce) {
        drawCued.remove(p.getUniqueId());
        return draw(p, vanillaForce, System.currentTimeMillis()).force();
    }

    /**
     * 화살이 나갔다 (활 — 쇠뇌 말고): 세기를 재고 근접과 같은 시계에 남긴다. 다음 근접·다음 당김 = 다시 메기기 0.15초 뒤부터
     * (다른 무기로 바꾸면 그 무기 간격 × 0.5 와 더 긴 쪽). @return 서버가 잰 세기 (0~1)
     */
    double shoot(Player p, double vanillaForce) {
        long now = System.currentTimeMillis();
        Draw d = draw(p, vanillaForce, now);
        long fullMs = Math.round(d.fullDraw() * 1000.0);
        clock(p).shot(now, d.usedMs(), fullMs, cfg().clickToleranceMs(), NOCK_MS);
        drawCued.remove(p.getUniqueId());
        return d.force();
    }

    /** 엔티티가 시계를 쓰는 플레이어인가 (디버그·자가 진단용). */
    boolean tracking(Entity e) { return e instanceof Player p && clocks.containsKey(p.getUniqueId()); }

    // ── 활 당김 막기 (0.3.6.1 손맛 검토 1) · 보조손 활 ──────────────────────

    /** 재사용 대기를 걸 만큼 남았는가 (ms) — 한 틱(50ms) 이하는 당김을 거의 잃지 않아 걸지 않는다. */
    static final long GATE_MIN_MS = 50;
    /** 보조손 활 안내를 다시 띄우기까지 (ms). */
    static final long OFFHAND_HINT_GAP_MS = 3000;

    /** 보조손 활 안내를 마지막으로 띄운 때. */
    private final Map<UUID, Long> offHandHinted = new ConcurrentHashMap<>();

    /** 막아 둘 시간(ms) → 바닐라 재사용 대기 틱 (올림 — 대기가 끝난 뒤 당기기 시작하면 서버가 다 센다). 0 = 걸지 않음. */
    static int gateTicks(long blockedMs) {
        return blockedMs <= GATE_MIN_MS ? 0 : (int) Math.min(Integer.MAX_VALUE, (blockedMs + 49) / 50);
    }

    /**
     * 당김을 세기 시작할 때까지 손(주손·보조손)의 활에 바닐라 재사용 대기를 건다 ({@link AttackTiming#drawBlockedMs}): 근접 한 대 뒤·활로 바꾼 뒤
     * 그 무기 간격이 남았을 때. 단축 칸에 하얀 막대가 보이고 그동안 당겨지지 않으므로 화면에 끝까지 당겨진 활 = 서버가 센 끝까지 당김.
     * 예전에는 그사이 당긴 것을 조용히 세지 않아, 활로 친 직후 평소처럼 1초 당겨 놓으면 화살이 과녁까지 못 갔다. 더 긴 대기가 있으면 그대로.
     */
    private void gateBow(Player p, AttackTiming t, ItemStack main) {
        int ticks = gateTicks(t.drawBlockedMs(System.currentTimeMillis(), cfg().clickToleranceMs()));
        if (ticks <= 0) return;
        for (ItemStack it : new ItemStack[] {main, p.getInventory().getItemInOffHand()}) {
            if (it == null || it.getType() != Material.BOW) continue;
            if (p.getCooldown(it) < ticks) p.setCooldown(it, ticks);
        }
    }

    /** 근접 한 대가 통과함 (기억한 클릭을 넣은 것 포함 — 시계는 이미 그 간격만큼 갔다): 손에 활이 있으면 그동안 당김을 막는다. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onAttackPassed(PrePlayerAttackEntityEvent e) {
        Player p = e.getPlayer();
        AttackTiming t = clocks.get(p.getUniqueId());
        if (t != null) gateBow(p, t, p.getInventory().getItemInMainHand());
    }

    /**
     * 활 당기기 (우클릭):
     * <ul>
     *   <li>재사용 대기 중이면 서버가 거절하면서 손님 쪽 당김도 되돌린다. 대기 패킷이 닿기 전에 누른 우클릭은 손님 화면에서 먼저 당겨지는데,
     *       바닐라는 조용히 무시만 해서 놓아도 화살이 안 나가는 빈 당김이 된다 (Paper 는 플러그인이 거절한 사용이면 '쓰는 중' 상태를 다시 보낸다).
     *       우클릭을 누르고 있으면 대기가 끝나는 대로 손님이 다시 당긴다.</li>
     *   <li>주손에 미궁 근접·시전 무기를 든 채 보조손 활은 당기지 않는다. 그 화살은 주손 무기의 한 방·피해 종류·고유 효과로 나가서
     *       (0.3.5 부터) 큰 도끼를 들고 보조손 활을 쏘면 가장 좋은 활만큼 셌다. 활은 주손에 들고 쏜다.</li>
     * </ul>
     */
    @EventHandler(priority = EventPriority.LOW)
    public void onUseBow(PlayerInteractEvent e) {
        if (e.getAction() != Action.RIGHT_CLICK_AIR && e.getAction() != Action.RIGHT_CLICK_BLOCK) return;
        ItemStack it = e.getItem();
        if (it == null || it.getType() != Material.BOW) return;
        Player p = e.getPlayer();
        if (offHandBowWithWeapon(p, e.getHand())) {
            e.setUseItemInHand(Event.Result.DENY);
            offHandHint(p);
        } else if (p.hasCooldown(it)) {
            e.setUseItemInHand(Event.Result.DENY);
        }
    }

    /** 보조손 활을 당기는 사이 주손을 미궁 근접·시전 무기로 바꿨으면 그 화살은 내보내지 않는다 ({@link #onUseBow} 와 같은 규칙). */
    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onShootOffHand(EntityShootBowEvent e) {
        if (e.getEntity() instanceof Player p && offHandBowWithWeapon(p, e.getHand())) {
            e.setCancelled(true);
            offHandHint(p);
        }
    }

    /** 보조손으로 쓰는 활인데 주손에 미궁 근접·시전 무기가 있는가. */
    private boolean offHandBowWithWeapon(Player p, EquipmentSlot hand) {
        if (hand != EquipmentSlot.OFF_HAND) return false;
        ItemDef main = services.items().heldWeapon(p);
        return main != null && !WeaponAttack.of(main).ranged();
    }

    private void offHandHint(Player p) {
        long now = System.currentTimeMillis();
        Long last = offHandHinted.get(p.getUniqueId());
        if (last != null && now - last < OFFHAND_HINT_GAP_MS) return;
        offHandHinted.put(p.getUniqueId(), now);
        services.hud().actionBar(p, Text.mm("<#ff6b6b>⚠ 활은 주손에 들고 쏘세요 <gray>— 주손에 무기를 들면 보조손 활은 당겨지지 않습니다"), 60);
    }
}
