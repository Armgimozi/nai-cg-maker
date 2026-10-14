package kr.labyrinth.items.weaponskills;

import io.papermc.paper.event.player.PlayerArmSwingEvent;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.IntPredicate;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageInterceptor;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.items.EquipRules;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.items.WeaponSkillService;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

/**
 * 무기 스킬 서비스 (GDD §17). 입력 감지 → 조건(착용 조건·침묵·쿨다운·마나) → 구현 실행.
 * <ul>
 *   <li>LEFT/SNEAK_LEFT = {@link PlayerArmSwingEvent}(주손) — 엔티티를 맞히든 허공이든 휘두를 때 한 번.
 *       버리기(Q)·블록/엔티티 상호작용이 만드는 팔 휘두름은 같은 틱 표시로 걸러 이중 발동을 막는다.</li>
 *   <li>RIGHT/SNEAK_RIGHT = 우클릭(허공·블록·적 엔티티). 상자·문 같은 상호작용 블록, NPC 는 그대로 둔다.
 *       활은 우클릭(당기기)을 건드리지 않는다.</li>
 *   <li>쿨다운은 플레이어 × 무기 id × 입력마다 따로(무기를 바꿔 들어도 유지), cooldown_reduction 적용.
 *       쿨다운 중이면 평범한 공격 + 액션바 남은 시간, 끝나면 "준비" 알림.</li>
 *   <li>런타임 상태(무적·보호막·방어 자세·낙하 피해 면제)는 {@link DamageInterceptor} 로 DamageService 에 연결.</li>
 * </ul>
 */
public final class LabWeaponSkillService implements WeaponSkillService, Listener, DamageInterceptor {

    private final Services services;
    private final WeaponTargeting targeting;
    private final Map<String, WeaponSkill> registry = new HashMap<>();
    /** uuid → (무기id:입력 → 끝나는 시각 ms). */
    private final Map<UUID, Map<String, Long>> cooldowns = new ConcurrentHashMap<>();
    private final List<Ready> pendingReady = new CopyOnWriteArrayList<>();
    private final Map<UUID, Integer> suppressSwingTick = new HashMap<>();
    private final Map<UUID, Integer> lastLeftTick = new HashMap<>();
    private final Map<UUID, Integer> lastRightTick = new HashMap<>();
    private final Map<UUID, Integer> interactTick = new HashMap<>();
    // 런타임 상태 (틱 = Bukkit.getCurrentTick)
    private final Map<UUID, Integer> invulnerableUntil = new ConcurrentHashMap<>();
    private final Map<UUID, Integer> noFallUntil = new ConcurrentHashMap<>();
    private final Map<UUID, Shield> shields = new ConcurrentHashMap<>();
    private final Map<UUID, Riposte> ripostes = new ConcurrentHashMap<>();
    private final Map<BukkitTask, Runnable> tasks = new ConcurrentHashMap<>();
    private BukkitTask readyTask;
    private boolean reflecting;

    private record Ready(UUID player, String itemId, String input, String name, long at) {}

    /** 보호막 (커스텀 HP 단위). */
    static final class Shield {
        double amount;
        int until;
        Shield(double amount, int until) { this.amount = amount; this.until = until; }
    }

    /** 방어 자세 (riposte). */
    static final class Riposte {
        final int until;
        final double reduction;
        final double angle;
        final double reflect;
        int blocks;
        Riposte(int until, double reduction, double angle, double reflect) {
            this.until = until;
            this.reduction = reduction;
            this.angle = angle;
            this.reflect = reflect;
        }
    }

    public LabWeaponSkillService(Services services) {
        this.services = services;
        this.targeting = new WeaponTargeting(services);
        ProjectileSkills.register(registry);
        MovementSkills.register(registry);
        AreaSkills.register(registry);
        SupportSkills.register(registry);
        MechanicsEngine.register(registry);
    }

    public void start() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        services.damage().addInterceptor(this);
        readyTask = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tickReady, 5L, 5L);
    }

    public void stop() {
        HandlerList.unregisterAll(this);
        services.damage().removeInterceptor(this);
        if (readyTask != null) readyTask.cancel();
        for (Map.Entry<BukkitTask, Runnable> e : Map.copyOf(tasks).entrySet()) {
            e.getKey().cancel();
            try {
                if (e.getValue() != null) e.getValue().run();
            } catch (Throwable t) {
                Log.error("무기 스킬 정리 오류", t);
            }
        }
        tasks.clear();
        shields.clear();
        ripostes.clear();
        invulnerableUntil.clear();
    }

    /** 구현된 무기 스킬 id (GDD §17.2 17종). */
    public java.util.Set<String> implementedIds() { return java.util.Set.copyOf(registry.keySet()); }

    WeaponTargeting targeting() { return targeting; }

    // ── WeaponSkillService ───────────────────────────────────────────────

    private static String key(String itemId, Input input) { return itemId + ":" + input.name(); }

    @Override
    public double cooldownRemaining(Player player, String itemId, Input input) {
        Map<String, Long> m = cooldowns.get(player.getUniqueId());
        if (m == null) return 0;
        Long end = m.get(key(itemId, input));
        if (end == null) return 0;
        long left = end - System.currentTimeMillis();
        return left <= 0 ? 0 : left / 1000.0;
    }

    @Override
    public boolean handle(Player player, Input input) { return handle(player, input, -1); }

    /**
     * @param charge 활의 SNEAK_RIGHT(웅크리고 당겨 쏘기)만 0~1 — 활 쏘기 이벤트에서 온 경우. 그 외 -1.
     */
    boolean handle(Player player, Input input, double charge) {
        if (player.getGameMode() == GameMode.SPECTATOR || player.isDead()) return false;
        ItemDef def = services.items().heldWeapon(player);
        if (def == null) return false;
        ItemDef.WeaponSkillDef s = def.weaponSkill(input.name());
        if (s == null) return false;
        boolean bow = "bow".equals(def.weaponType());
        if (bow && input == Input.RIGHT) return false;
        if (bow && input == Input.SNEAK_RIGHT && charge < 0) return false; // 활은 당겨 쏠 때(onShoot) 발동
        WeaponSkill impl = registry.get(s.id());
        if (impl == null) {
            Log.warnOnce("ws-missing-" + s.id(), "[무기 스킬] 구현이 없는 id: " + s.id() + " (" + def.id() + ")");
            return false;
        }
        PlayerData d = services.data().get(player);
        if (!EquipRules.usable(def, d.level(), d.classId())) {
            if (s.cooldown() > 1.0) bar(player, "<#ff6b6b>⚠ 착용 조건이 맞지 않아 무기 스킬을 쓸 수 없습니다.", 30);
            return false;
        }
        if (services.effects().isSilenced(player)) {
            if (s.cooldown() > 1.0) bar(player, "<#b06cff>침묵 상태 — 무기 스킬을 쓸 수 없습니다.", 30);
            return false;
        }
        double rem = cooldownRemaining(player, def.id(), input);
        if (rem > 0) {
            if (s.cooldown() > 1.0) {
                bar(player, "<gray>" + Text.escape(s.name()) + " <dark_gray>— <#ff9a6b>" + String.format("%.1f", rem) + "초</#ff9a6b> 후 사용 가능", 25);
            }
            return false;
        }
        if (s.mana() > 0 && !services.classes().useMana(player, s.mana())) {
            bar(player, "<#7fb2ff>MP 부족 <gray>(" + Math.round(services.classes().mana(player)) + " / " + Math.round(s.mana()) + ")", 30);
            player.playSound(player.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.5f, 0.6f);
            return false;
        }
        double cdr = services.stats().get(player).cooldownReduction();
        double cd = s.cooldown() * (1.0 - cdr);
        if (services.effects().has(player, "cooldown_slow")) cd *= 1.3;
        long end = System.currentTimeMillis() + Math.round(cd * 1000);
        cooldowns.computeIfAbsent(player.getUniqueId(), u -> new ConcurrentHashMap<>()).put(key(def.id(), input), end);
        try {
            impl.cast(new SkillCast(services, this, player, def, s, defaultType(s.id(), def)).charge(charge));
        } catch (Throwable t) {
            Log.error("무기 스킬 실행 오류: " + s.id() + " (" + def.id() + ")", t);
        }
        if (s.cooldown() >= 2.0) {
            bar(player, "<#ffd27a>◆ " + Text.escape(s.name()) + " <dark_gray>· " + ItemTooltip.inputName(def, input.name())
                    + " · 재사용 " + String.format("%.1f", cd) + "초", 30);
            pendingReady.add(new Ready(player.getUniqueId(), def.id(), input.name(), s.name(), end));
        }
        if (s.mana() > 0) services.hud().refresh(player);
        return true;
    }

    private static DamageType defaultType(String id, ItemDef weapon) {
        return switch (id) {
            case "slash_wave" -> DamageType.RANGED;
            case "beam", "chain_bolt", "sanctuary", "vortex" -> DamageType.MAGIC;
            case "missile", "rain_zone", "blade_orbit", "mechanics" -> switch (weapon.weaponType() == null ? "" : weapon.weaponType()) {
                case "bow" -> DamageType.RANGED;
                case "staff", "scepter" -> DamageType.MAGIC;
                default -> DamageType.MELEE;
            };
            default -> DamageType.MELEE;
        };
    }

    void bar(Player p, String mm, int ticks) { services.hud().actionBar(p, Text.mm(mm), ticks); }

    private void tickReady() {
        long now = System.currentTimeMillis();
        if (Bukkit.getCurrentTick() % 1200 < 5) cleanupCooldowns();
        for (Ready r : pendingReady) {
            if (r.at() > now) continue;
            pendingReady.remove(r);
            Player p = Bukkit.getPlayer(r.player());
            if (p == null || !p.isOnline()) continue;
            ItemDef held = services.items().heldWeapon(p);
            if (held == null || !held.id().equals(r.itemId())) continue;
            bar(p, "<#9be89b>✔ " + Text.escape(r.name()) + " <gray>준비 완료 <dark_gray>(" + ItemTooltip.inputName(r.input()) + ")", 25);
            p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_CHIME, 0.35f, 1.8f);
        }
    }

    // ── 입력 ──────────────────────────────────────────────────────────────

    private static int now() { return Bukkit.getCurrentTick(); }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onDrop(PlayerDropItemEvent e) { suppressSwingTick.put(e.getPlayer().getUniqueId(), now()); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSwing(PlayerArmSwingEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Player p = e.getPlayer();
        UUID u = p.getUniqueId();
        int t = now();
        if (suppressSwingTick.getOrDefault(u, -100) >= t - 1) return;
        if (lastLeftTick.getOrDefault(u, -100) == t) return;
        lastLeftTick.put(u, t);
        handle(p, p.isSneaking() ? Input.SNEAK_LEFT : Input.LEFT);
    }

    @SuppressWarnings("deprecation") // Material#isInteractable: 상자·문 등은 그대로 쓰게 둔다
    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Action a = e.getAction();
        if (a != Action.RIGHT_CLICK_AIR && a != Action.RIGHT_CLICK_BLOCK) return;
        Player p = e.getPlayer();
        UUID u = p.getUniqueId();
        int t = now();
        if (a == Action.RIGHT_CLICK_BLOCK && e.getClickedBlock() != null && e.getClickedBlock().getType().isInteractable()
                && !p.isSneaking()) {
            suppressSwingTick.put(u, t);
            return;
        }
        if (interactTick.getOrDefault(u, -100) == t) return;
        if (p.isSneaking() && isBowWithSneakShot(p)) return; // 웅크리고 당기기 → onShoot 에서 발동
        if (lastRightTick.getOrDefault(u, -100) == t) {
            e.setUseItemInHand(org.bukkit.event.Event.Result.DENY);
            return;
        }
        if (handle(p, p.isSneaking() ? Input.SNEAK_RIGHT : Input.RIGHT)) {
            lastRightTick.put(u, t);
            suppressSwingTick.put(u, t);
            e.setUseItemInHand(org.bukkit.event.Event.Result.DENY);
            e.setUseInteractedBlock(org.bukkit.event.Event.Result.DENY);
        }
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteractEntity(PlayerInteractEntityEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Player p = e.getPlayer();
        UUID u = p.getUniqueId();
        int t = now();
        suppressSwingTick.put(u, t);
        if (!targeting.isEnemy(p, e.getRightClicked())) {
            interactTick.put(u, t);
            return;
        }
        if (lastRightTick.getOrDefault(u, -100) == t) return;
        if (p.isSneaking() && isBowWithSneakShot(p)) return;
        if (handle(p, p.isSneaking() ? Input.SNEAK_RIGHT : Input.RIGHT)) {
            lastRightTick.put(u, t);
            e.setCancelled(true);
        }
    }

    private boolean isBowWithSneakShot(Player p) {
        ItemDef def = services.items().heldWeapon(p);
        return def != null && "bow".equals(def.weaponType()) && def.weaponSkill(Input.SNEAK_RIGHT.name()) != null;
    }

    /**
     * 활 "웅크리고 당겨 쏘기" (SNEAK_RIGHT): 웅크린 채 시위를 놓으면 화살 대신 무기 스킬이 나간다(당김 세기 = 위력).
     * 쿨다운·마나 부족이면 평범한 화살이 나간다.
     */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onShoot(org.bukkit.event.entity.EntityShootBowEvent e) {
        if (!(e.getEntity() instanceof Player p) || !p.isSneaking()) return;
        if (!isBowWithSneakShot(p)) return;
        if (handle(p, Input.SNEAK_RIGHT, Math.max(0, Math.min(1, e.getForce())))) {
            e.setCancelled(true); // 취소하면 화살도 소모되지 않는다 (미궁 활은 무한)
        }
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        UUID u = e.getPlayer().getUniqueId();
        suppressSwingTick.remove(u);
        lastLeftTick.remove(u);
        lastRightTick.remove(u);
        interactTick.remove(u);
        shields.remove(u);
        ripostes.remove(u);
        invulnerableUntil.remove(u);
        noFallUntil.remove(u);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(PlayerDeathEvent e) {
        UUID u = e.getPlayer().getUniqueId();
        shields.remove(u);
        ripostes.remove(u);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onFall(EntityDamageEvent e) {
        if (e.getCause() != EntityDamageEvent.DamageCause.FALL || !(e.getEntity() instanceof Player p)) return;
        Integer until = noFallUntil.get(p.getUniqueId());
        if (until != null && until >= now()) e.setCancelled(true);
    }

    // ── 런타임 상태 API (스킬·소모품이 사용) ──────────────────────────────

    /** ticks 동안 모든 피해 무시 (돌진 무적·부활 무적). */
    public void invulnerable(Player p, int ticks) {
        invulnerableUntil.merge(p.getUniqueId(), now() + ticks, Math::max);
    }

    public boolean isInvulnerable(Player p) {
        Integer u = invulnerableUntil.get(p.getUniqueId());
        return u != null && u >= now();
    }

    /** 낙하 피해 면제 (도약). */
    public void noFall(Player p, int ticks) { noFallUntil.merge(p.getUniqueId(), now() + ticks, Math::max); }

    /** 보호막 (커스텀 HP 단위). 기존 보호막보다 크면 교체. */
    public void shield(Player p, double amount, double seconds) {
        if (amount <= 0) return;
        int until = now() + SkillCast.ticks(seconds);
        shields.compute(p.getUniqueId(), (u, old) -> old == null || old.until < now() || old.amount < amount
                ? new Shield(amount, until) : old);
        p.getWorld().spawnParticle(Particle.END_ROD, p.getLocation().add(0, 1, 0), 10, 0.4, 0.6, 0.4, 0.02);
        bar(p, "<#c8f0ff>◈ 보호막 +" + Math.round(amount), 25);
    }

    void riposte(Player p, double seconds, double reduction, double angle, double reflect) {
        ripostes.put(p.getUniqueId(), new Riposte(now() + SkillCast.ticks(seconds), reduction, angle, reflect));
    }

    /** 방어 자세 종료 → 막은 횟수. */
    int endRiposte(Player p) {
        Riposte r = ripostes.remove(p.getUniqueId());
        return r == null ? 0 : r.blocks;
    }

    @Override
    public double intercept(DamageContext ctx, double damage) {
        if (!(ctx.target() instanceof Player p)) return damage;
        UUID u = p.getUniqueId();
        int t = now();
        Integer inv = invulnerableUntil.get(u);
        if (inv != null) {
            if (inv >= t) return 0;
            invulnerableUntil.remove(u);
        }
        Riposte r = ripostes.get(u);
        LivingEntity attacker = ctx.attacker();
        if (r != null && r.until >= t && attacker != null && attacker != p && facing(p, attacker, r.angle)) {
            double original = damage;
            damage *= Math.max(0, 1.0 - r.reduction);
            r.blocks++;
            p.getWorld().playSound(p.getLocation(), Sound.ITEM_SHIELD_BLOCK, 0.8f, 1.1f);
            p.getWorld().spawnParticle(Particle.CRIT, p.getEyeLocation().add(p.getLocation().getDirection().multiply(0.8)), 8, 0.2, 0.2, 0.2, 0.1);
            if (r.reflect > 0 && !reflecting && targeting.isEnemy(p, attacker)) {
                reflecting = true;
                try {
                    services.damage().deal(DamageContext.raw(p, attacker, original * r.reflect, DamageType.TRUE)
                            .skill("riposte").noCrit().noLifesteal());
                } finally {
                    reflecting = false;
                }
            }
        }
        Shield s = shields.get(u);
        if (s != null && damage > 0) {
            if (s.until < t) {
                shields.remove(u);
            } else {
                double absorb = Math.min(s.amount, damage);
                s.amount -= absorb;
                damage -= absorb;
                if (s.amount <= 0.01) {
                    shields.remove(u);
                    p.getWorld().playSound(p.getLocation(), Sound.BLOCK_GLASS_BREAK, 0.6f, 1.5f);
                }
            }
        }
        return damage;
    }

    static boolean facing(Player p, Entity attacker, double angleDeg) {
        if (angleDeg >= 359) return true;
        Vector look = p.getLocation().getDirection().setY(0);
        Vector to = attacker.getLocation().toVector().subtract(p.getLocation().toVector()).setY(0);
        if (look.lengthSquared() < 1e-6 || to.lengthSquared() < 1e-6) return true;
        return look.normalize().dot(to.normalize()) >= Math.cos(Math.toRadians(angleDeg / 2.0));
    }

    // ── 스케줄 ────────────────────────────────────────────────────────────

    void schedule(Player owner, int period, int total, IntPredicate fn, Runnable onEnd) {
        final int[] elapsed = {0};
        final BukkitTask[] ref = new BukkitTask[1];
        final boolean[] ended = {false};
        Runnable end = () -> {
            if (ended[0]) return;
            ended[0] = true;
            if (ref[0] != null) {
                ref[0].cancel();
                tasks.remove(ref[0]);
            }
            if (onEnd != null) {
                try {
                    onEnd.run();
                } catch (Throwable t) {
                    Log.error("무기 스킬 종료 처리 오류", t);
                }
            }
        };
        ref[0] = Bukkit.getScheduler().runTaskTimer(services.plugin(), () -> {
            elapsed[0] += period;
            if (!owner.isOnline()) {
                end.run();
                return;
            }
            boolean cont;
            try {
                cont = fn.test(elapsed[0]);
            } catch (Throwable t) {
                Log.error("무기 스킬 틱 오류", t);
                cont = false;
            }
            if (!cont || elapsed[0] >= total) end.run();
        }, period, period);
        tasks.put(ref[0], end);
    }

    /** 오래된 쿨다운 정리 (메모리). */
    void cleanupCooldowns() {
        long now = System.currentTimeMillis();
        for (Iterator<Map<String, Long>> it = cooldowns.values().iterator(); it.hasNext(); ) {
            Map<String, Long> m = it.next();
            m.values().removeIf(v -> v < now);
            if (m.isEmpty()) it.remove();
        }
    }
}
