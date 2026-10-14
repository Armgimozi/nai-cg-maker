package kr.labyrinth.classes;

import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.classes.skills.SkillFx;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageService;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.mobs.CustomMob;
import kr.labyrinth.stats.StatBlock;
import kr.labyrinth.stats.StatContributor;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityTargetLivingEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

/**
 * 상태이상·버프·보호막·은신 실제 구현 (GDD §9.2, §11.7). 플레이어·커스텀 몹·보스 공통, PvP 에서도 그대로.
 * <ul>
 *   <li>5틱(0.25초)마다: 만료 처리, 지속 피해(1초 간격, DamageService 경유 TRUE 피해), 이동 제한 속성 수정치, 파티클</li>
 *   <li>플레이어 버프·디버프 능력치 → {@link StatContributor} (damage_mult, damage_taken, evasion …)</li>
 *   <li>몹·보스의 weaken/vulnerable/mark, 모든 대상의 보호막 → {@link DamageService.Hook}</li>
 *   <li>frost 5중첩 → 4초 빙결(얼음 껍질 모델, 아군 4회 타격으로 해방), infection 5중첩 → 2초 속박 + 피해</li>
 * </ul>
 */
public final class LabyrinthStatusEffectService implements StatusEffectService, Listener, DamageService.Hook, StatContributor {

    private static final org.bukkit.NamespacedKey MOVE_KEY = Keys.key("fx_move");
    private static final org.bukkit.NamespacedKey JUMP_KEY = Keys.key("fx_jump");
    private static final org.bukkit.NamespacedKey KB_KEY = Keys.key("fx_knockback");
    private static final long TICK_MS = 250;

    /** 엔티티 하나의 상태. */
    private static final class State {
        final LivingEntity entity;
        final EffectStack effects = new EffectStack();
        final BuffSet buffs = new BuffSet();
        final ShieldPool shields = new ShieldPool();
        double appliedMove = 0;
        boolean appliedRoot;
        boolean appliedKbImmune;
        long stealthUntil;
        double stealthBonus;
        int freeHits;
        ItemDisplay iceShell;
        ItemDisplay markDisplay;
        long lastShieldFx;

        State(LivingEntity e) { this.entity = e; }

        boolean idle(long now) {
            return effects.isEmpty() && buffs.isEmpty() && shields.isEmpty() && stealthUntil <= now && appliedMove == 0
                    && !appliedRoot && !appliedKbImmune && iceShell == null && markDisplay == null;
        }
    }

    private final Services services;
    private final Map<UUID, State> states = new ConcurrentHashMap<>();
    private BukkitTask task;
    private long tickCount;

    public LabyrinthStatusEffectService(Services services) { this.services = services; }

    public void start() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        services.stats().addContributor(this);
        services.damage().addHook(this);
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tick, 5L, 5L);
    }

    public void stop() {
        if (task != null) task.cancel();
        HandlerList.unregisterAll(this);
        services.stats().removeContributor(this);
        services.damage().removeHook(this);
        for (State s : states.values()) resetPhysical(s);
        states.clear();
    }

    private State state(LivingEntity e) { return states.computeIfAbsent(e.getUniqueId(), u -> new State(e)); }

    private State peek(Entity e) { return e == null ? null : states.get(e.getUniqueId()); }

    private boolean isBoss(Entity e) { return services.bosses().byEntity(e).isPresent(); }

    // ── 부여 ──────────────────────────────────────────────────────────────

    @Override
    public void apply(LivingEntity target, String effectId, double durationSeconds, double potency, LivingEntity source) {
        if (target == null || target.isDead() || effectId == null) return;
        String id = effectId.toLowerCase(java.util.Locale.ROOT);
        long now = System.currentTimeMillis();
        if (target instanceof Player p && (p.getGameMode() == org.bukkit.GameMode.CREATIVE
                || p.getGameMode() == org.bukkit.GameMode.SPECTATOR)) return;
        if (isBoss(target) && (id.equals("stun") || id.equals("root") || id.equals("frozen"))) return;

        switch (id) {
            case "knockback" -> {
                knockback(target, source, potency <= 0 ? 1.0 : potency);
                return;
            }
            case "damage" -> {
                double base = baseDamage(source);
                services.damage().deal(DamageContext.raw(source, target, base * (potency <= 0 ? 1 : potency), DamageType.TRUE)
                        .source("effect:damage").noCrit().noEvade().noBlock().noLifesteal());
                return;
            }
            default -> { }
        }

        double dur = Math.max(0.05, durationSeconds);
        if (target instanceof Player p && EffectStack.harmful(id) && !id.equals("stun") && !id.equals("frozen")) {
            dur *= 1.0 - services.stats().get(p).debuffReduction();
        }
        State s = state(target);
        double value = potency;
        int addStacks = 1;
        if (EffectStack.DOT.contains(id)) {
            double ratio = potency > 0 && potency < 1 ? potency : switch (id) {
                case "burn" -> 0.2;
                case "venom" -> 0.1;
                default -> 0.15;
            };
            value = Math.max(0.5, ratio * baseDamage(source));
        } else if (id.equals("frost") || id.equals("infection")) {
            addStacks = Math.max(1, (int) Math.round(potency));
            value = 1;
            if (dur < 0.5) dur = id.equals("frost") ? 6 : 8;
        }
        int max = EffectStack.defaultMaxStacks(id);
        EffectStack.Applied a = s.effects.apply(id, value, addStacks, (long) (dur * 1000), source == null ? null : source.getUniqueId(),
                now, max);
        if (a.isNew()) announce(target, id);
        if (id.equals("stealth_reveal")) breakStealth(target);
        if (id.equals("mark")) {
            breakStealth(target);
            if (s.markDisplay == null || !s.markDisplay.isValid()) {
                s.markDisplay = SkillFx.attach("mark_hunter", target, target.getHeight() + 0.6, 0.9f, 0);
            }
        }
        if (id.equals("blind") && target instanceof Player p) {
            p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, (int) (dur * 20) + 10, 0, false, false, true));
        }
        if (id.equals("silence") && target instanceof Player p) {
            services.hud().actionBar(p, Text.mm("<#9a9aff>🔇 침묵 — 스킬을 쓸 수 없습니다"), (int) (dur * 20));
        }
        if (a.reachedMax()) onMaxStacks(target, s, id, source);
        if (target instanceof Player p) services.stats().markDirty(p);
        updatePhysical(s, now);
    }

    private void onMaxStacks(LivingEntity target, State s, String id, LivingEntity source) {
        switch (id) {
            case "frost" -> {
                s.effects.remove("frost");
                s.freeHits = 4;
                apply(target, "frozen", 4, 1, source);
                SkillFx.sound(target.getLocation(), Sound.BLOCK_GLASS_PLACE, 1f, 0.6f);
                SkillFx.burst(target.getLocation().add(0, 1, 0), Particle.SNOWFLAKE, 40, 0.5, 0.05, null);
                if (s.iceShell == null || !s.iceShell.isValid()) {
                    s.iceShell = SkillFx.attach("ice_shell", target, 0.0, (float) Math.max(1.0, target.getHeight() / 1.8), 0);
                }
                if (target instanceof Player p) {
                    services.hud().actionBar(p, Text.mm("<#bfe6ff>❄ 빙결! <gray>동료가 4번 때려 깨 줄 수 있습니다"), 80);
                }
            }
            case "infection" -> {
                s.effects.remove("infection");
                apply(target, "root", 2, 1, source);
                double base = baseDamage(source);
                services.damage().deal(DamageContext.raw(source, target, base * 0.8, DamageType.TRUE).source("effect:infection")
                        .noCrit().noEvade().noBlock().noLifesteal());
                SkillFx.burst(target.getLocation().add(0, 1, 0), Particle.CRIMSON_SPORE, 40, 0.6, 0.02, null);
                SkillFx.sound(target.getLocation(), Sound.ENTITY_SLIME_SQUISH, 1f, 0.5f);
            }
            case "venom" -> {
                apply(target, "weaken", 6, 0.10, source);
                SkillFx.burst(target.getLocation().add(0, 1, 0), Particle.ITEM_SLIME, 20, 0.4, 0.05, null);
            }
            default -> { }
        }
    }

    private void announce(LivingEntity target, String id) {
        Location at = target.getLocation().add(0, target.getHeight() + 0.3, 0);
        switch (id) {
            case "stun" -> SkillFx.sound(at, Sound.BLOCK_ANVIL_LAND, 0.4f, 1.8f);
            case "root" -> SkillFx.sound(at, Sound.BLOCK_CHAIN_PLACE, 0.8f, 0.7f);
            case "slow" -> SkillFx.burst(at, Particle.SNOWFLAKE, 6, 0.3, 0.01, null);
            case "vulnerable", "mark" -> SkillFx.sound(at, Sound.ENTITY_ELDER_GUARDIAN_CURSE, 0.25f, 1.8f);
            default -> { }
        }
    }

    /** 지속 피해 기준: 플레이어 = 공격력, 커스텀 몹 = damage, 그 외 = 10. */
    private double baseDamage(LivingEntity source) {
        if (source instanceof Player p) return services.stats().get(p).attackPower();
        if (source != null) {
            var m = services.mobs().byEntity(source);
            if (m.isPresent()) return m.get().damage();
            var b = services.bosses().byEntity(source);
            if (b.isPresent()) return b.get().damage();
        }
        return 10;
    }

    private void knockback(LivingEntity target, LivingEntity source, double strength) {
        if (isKnockbackImmune(target)) {
            SkillFx.burst(target.getLocation().add(0, 1, 0), Particle.ENCHANTED_HIT, 8, 0.3, 0.1, null);
            return;
        }
        Vector dir = source == null ? target.getLocation().getDirection().multiply(-1)
                : target.getLocation().toVector().subtract(source.getLocation().toVector());
        dir.setY(0);
        if (dir.lengthSquared() < 1e-6) dir = new Vector(0, 0, 1);
        dir.normalize().multiply(0.5 * strength).setY(Math.min(0.6, 0.2 + 0.1 * strength));
        target.setVelocity(target.getVelocity().add(dir));
    }

    @Override
    public boolean has(LivingEntity target, String effectId) {
        State s = peek(target);
        if (s == null) return false;
        if ("stealth".equals(effectId)) return isStealthed(target);
        return s.effects.has(effectId, System.currentTimeMillis());
    }

    @Override
    public int stacks(LivingEntity target, String effectId) {
        State s = peek(target);
        return s == null ? 0 : s.effects.stacks(effectId, System.currentTimeMillis());
    }

    @Override
    public void clear(LivingEntity target, String effectId) {
        State s = peek(target);
        if (s == null) return;
        EffectStack.Entry e = s.effects.remove(effectId);
        if (e != null) onRemoved(s, e.id);
        updatePhysical(s, System.currentTimeMillis());
        if (target instanceof Player p) services.stats().markDirty(p);
    }

    @Override
    public void cleanse(LivingEntity target) {
        State s = peek(target);
        if (s == null) return;
        List<String> removed = s.effects.cleanse();
        for (String id : removed) onRemoved(s, id);
        if (!removed.isEmpty()) {
            SkillFx.burst(target.getLocation().add(0, 1, 0), Particle.END_ROD, 12, 0.4, 0.05, null);
            if (target instanceof Player p) {
                p.removePotionEffect(PotionEffectType.BLINDNESS);
                services.stats().markDirty(p);
            }
        }
        updatePhysical(s, System.currentTimeMillis());
    }

    @Override
    public void clearAll(LivingEntity e) {
        State s = states.remove(e.getUniqueId());
        if (s == null) return;
        for (EffectStack.Entry x : List.copyOf(s.effects.all())) onRemoved(s, x.id);
        s.effects.clear();
        s.buffs.clear();
        s.shields.clear();
        s.stealthUntil = 0;
        resetPhysical(s);
        if (e instanceof Player p) {
            p.removePotionEffect(PotionEffectType.INVISIBILITY);
            services.stats().markDirty(p);
        }
    }

    private void onRemoved(State s, String id) {
        switch (id) {
            case "frozen" -> {
                SkillFx.remove(s.iceShell);
                s.iceShell = null;
                SkillFx.sound(s.entity.getLocation(), Sound.BLOCK_GLASS_BREAK, 1f, 1.2f);
                SkillFx.burst(s.entity.getLocation().add(0, 1, 0), Particle.ITEM_SNOWBALL, 25, 0.5, 0.1, null);
            }
            case "mark" -> {
                SkillFx.remove(s.markDisplay);
                s.markDisplay = null;
            }
            default -> { }
        }
    }

    // ── 버프·보호막·은신 ──────────────────────────────────────────────────

    @Override
    public void applyBuff(Player player, Map<String, Double> buff, double durationSeconds, String sourceId) {
        if (player == null || buff == null) return;
        State s = state(player);
        s.buffs.put(sourceId == null ? "buff" : sourceId, buff, System.currentTimeMillis() + (long) (durationSeconds * 1000));
        services.stats().markDirty(player);
        updatePhysical(s, System.currentTimeMillis());
    }

    @Override
    public void removeBuff(Player player, String sourceId) {
        State s = peek(player);
        if (s != null && s.buffs.remove(sourceId)) {
            services.stats().markDirty(player);
            updatePhysical(s, System.currentTimeMillis());
        }
    }

    @Override
    public boolean hasBuff(Player player, String sourceId) {
        State s = peek(player);
        return s != null && s.buffs.has(sourceId, System.currentTimeMillis());
    }

    @Override
    public void addShield(LivingEntity target, double amount, double durationSeconds, String sourceId) {
        if (target == null || amount <= 0) return;
        State s = state(target);
        long until = System.currentTimeMillis() + (long) (durationSeconds * 1000);
        if ("grace_overheal".equals(sourceId)) {
            double cap = services.damage().maxHp(target) * 0.10;
            s.shields.addStacking(sourceId, amount, Math.max(amount, cap), until);
        } else {
            s.shields.add(sourceId == null ? "shield" : sourceId, amount, until);
        }
        SkillFx.burst(target.getLocation().add(0, 1, 0), Particle.END_ROD, 10, 0.5, 0.02, null);
        if (target instanceof Player p) services.hud().refresh(p);
    }

    @Override
    public double shield(LivingEntity target) {
        State s = peek(target);
        return s == null ? 0 : s.shields.total(System.currentTimeMillis());
    }

    @Override
    public void stealth(Player player, double seconds, double firstHitBonus) {
        State s = state(player);
        s.stealthUntil = System.currentTimeMillis() + (long) (seconds * 1000);
        s.stealthBonus = firstHitBonus;
        player.addPotionEffect(new PotionEffect(PotionEffectType.INVISIBILITY, (int) (seconds * 20), 0, false, false, true));
        for (Entity e : player.getNearbyEntities(24, 12, 24)) {
            if (e instanceof Mob m && player.equals(m.getTarget())) m.setTarget(null);
        }
    }

    @Override
    public boolean isStealthed(LivingEntity e) {
        State s = peek(e);
        return s != null && s.stealthUntil > System.currentTimeMillis();
    }

    @Override
    public void breakStealth(LivingEntity e) {
        State s = peek(e);
        if (s == null || s.stealthUntil <= 0) return;
        boolean was = s.stealthUntil > System.currentTimeMillis();
        s.stealthUntil = 0;
        s.stealthBonus = 0;
        if (e instanceof Player p) p.removePotionEffect(PotionEffectType.INVISIBILITY);
        if (was) SkillFx.burst(e.getLocation().add(0, 1, 0), Particle.LARGE_SMOKE, 12, 0.3, 0.02, null);
    }

    @Override
    public boolean isKnockbackImmune(LivingEntity e) {
        State s = peek(e);
        return s != null && s.buffs.total("knockback_immune", System.currentTimeMillis()) > 0;
    }

    @Override
    public double cooldownRate(LivingEntity e) {
        State s = peek(e);
        if (s == null) return 1.0;
        return Math.max(0.1, 1.0 - s.effects.value("cooldown_slow", System.currentTimeMillis()));
    }

    // ── StatContributor: 플레이어 버프·디버프 ────────────────────────────

    @Override
    public void contribute(Player player, StatBlock block) {
        State s = peek(player);
        if (s == null) return;
        long now = System.currentTimeMillis();
        s.buffs.totals(now).forEach((k, v) -> {
            if (!k.equals("knockback_immune") && !k.equals("venom_blades")) block.add(k, v);
        });
        double weaken = s.effects.value("weaken", now);
        if (weaken > 0) block.add("damage_mult", -weaken);
        double taken = s.effects.value("vulnerable", now) + s.effects.value("mark", now);
        if (taken > 0) block.add("damage_taken", taken);
    }

    // ── DamageService.Hook ───────────────────────────────────────────────

    @Override
    public void before(DamageContext ctx) {
        long now = System.currentTimeMillis();
        LivingEntity atk = ctx.attacker();
        State as = peek(atk);
        if (as != null) {
            if (!(atk instanceof Player)) {
                double weaken = as.effects.value("weaken", now);
                if (weaken > 0) ctx.amount(ctx.amount() * Math.max(0.1, 1 - weaken));
            }
            if (atk instanceof Player p && as.stealthUntil > now && !isDot(ctx)) {
                ctx.amount(ctx.amount() * (1 + as.stealthBonus));
                breakStealth(p);
            }
        }
        State ts = peek(ctx.target());
        if (ts != null && !(ctx.target() instanceof Player) && !ctx.isPercent()) {
            double taken = ts.effects.value("vulnerable", now) + ts.effects.value("mark", now);
            if (taken > 0) ctx.amount(ctx.amount() * (1 + taken));
        }
    }

    @Override
    public double absorb(DamageContext ctx, double damage) {
        State ts = peek(ctx.target());
        if (ts == null || ts.shields.isEmpty()) return damage;
        long now = System.currentTimeMillis();
        double left = ts.shields.absorb(damage, now);
        if (left < damage) {
            LivingEntity t = ctx.target();
            if (now - ts.lastShieldFx > 300) {
                ts.lastShieldFx = now;
                SkillFx.burst(t.getLocation().add(0, t.getHeight() * 0.6, 0), Particle.DUST, 10, 0.4, 0,
                        SkillFx.dust(0xbfe6ff, 1.2f));
                SkillFx.sound(t.getLocation(), Sound.ITEM_SHIELD_BLOCK, 0.5f, 1.6f);
            }
            if (t instanceof Player p) services.hud().refresh(p);
        }
        return left;
    }

    private static boolean isDot(DamageContext ctx) {
        return ctx.sourceId() != null && ctx.sourceId().startsWith("effect:");
    }

    // ── 틱 ────────────────────────────────────────────────────────────────

    private void tick() {
        long now = System.currentTimeMillis();
        tickCount++;
        for (var it = states.entrySet().iterator(); it.hasNext(); ) {
            State s = it.next().getValue();
            LivingEntity e = s.entity;
            try {
                if (!e.isValid() || e.isDead()) {
                    resetPhysical(s);
                    it.remove();
                    continue;
                }
                for (EffectStack.Entry x : s.effects.expire(now)) onRemoved(s, x.id);
                boolean buffChanged = s.buffs.expire(now);
                s.shields.expire(now);
                if (s.stealthUntil > 0 && s.stealthUntil <= now) breakStealth(e);
                if (e instanceof Player p && buffChanged) services.stats().markDirty(p);
                dots(s, now);
                updatePhysical(s, now);
                particles(s, now);
                if (s.idle(now)) it.remove();
            } catch (Throwable t) {
                Log.error("상태이상 틱 오류 (" + e.getType() + ")", t);
                it.remove();
            }
        }
    }

    private void dots(State s, long now) {
        for (EffectStack.Entry x : List.copyOf(s.effects.all())) {
            if (!EffectStack.DOT.contains(x.id) || x.nextTickAt > now) continue;
            x.nextTickAt = now + 1000;
            double amount = x.value * (x.id.equals("venom") ? x.stacks : 1);
            if (x.id.equals("bleed") && s.entity.getVelocity().clone().setY(0).lengthSquared() > 0.003) amount *= 1.5;
            LivingEntity src = x.source == null ? null : Bukkit.getEntity(x.source) instanceof LivingEntity le && le.isValid() ? le : null;
            services.damage().deal(DamageContext.raw(src, s.entity, amount, DamageType.TRUE).source("effect:" + x.id)
                    .noCrit().noEvade().noBlock().noLifesteal());
            if (s.entity.isDead()) return;
        }
    }

    private void particles(State s, long now) {
        LivingEntity e = s.entity;
        Location feet = e.getLocation();
        Location mid = feet.clone().add(0, e.getHeight() * 0.55, 0);
        Location head = feet.clone().add(0, e.getHeight() + 0.25, 0);
        double w = Math.max(0.3, e.getWidth() * 0.5);
        if (s.effects.has("poison", now) || s.effects.has("venom", now)) {
            SkillFx.burst(mid, Particle.DUST, 3, w, 0, SkillFx.dust(0x6ad13a, 1.0f));
        }
        if (s.effects.has("bleed", now)) SkillFx.burst(mid, Particle.DUST, 3, w * 0.7, 0, SkillFx.dust(0xa01818, 1.1f));
        if (s.effects.has("burn", now)) SkillFx.burst(mid, Particle.FLAME, 2, w * 0.7, 0.01, null);
        if (s.effects.has("stun", now)) {
            double a = (tickCount % 8) / 8.0 * Math.PI * 2;
            for (int i = 0; i < 3; i++) {
                double b = a + i * Math.PI * 2 / 3;
                SkillFx.burst(head.clone().add(Math.cos(b) * 0.45, 0, Math.sin(b) * 0.45), Particle.DUST, 1, 0, 0,
                        SkillFx.dust(0xffe14a, 1.1f));
            }
        }
        if (s.effects.has("root", now)) SkillFx.circle(feet.clone().add(0, 0.1, 0), w + 0.2, 8, Particle.DUST, SkillFx.dust(0x5a7a2a, 1.0f));
        if (s.effects.has("slow", now) && tickCount % 2 == 0) SkillFx.burst(feet.clone().add(0, 0.2, 0), Particle.SNOWFLAKE, 2, w, 0, null);
        if (s.effects.has("weaken", now) && tickCount % 2 == 0) SkillFx.burst(mid, Particle.SMOKE, 2, w * 0.6, 0.01, null);
        if (s.effects.has("vulnerable", now)) SkillFx.burst(head, Particle.DUST, 2, w * 0.5, 0, SkillFx.dust(0xc77dff, 1.0f));
        if (s.effects.has("silence", now) && tickCount % 2 == 0) SkillFx.burst(head, Particle.NOTE, 1, 0.2, 0, null);
        if (s.effects.has("frost", now)) {
            SkillFx.burst(mid, Particle.SNOWFLAKE, s.effects.stacks("frost", now), w, 0.01, null);
        }
        if (s.effects.has("infection", now)) {
            SkillFx.burst(mid, Particle.CRIMSON_SPORE, s.effects.stacks("infection", now) * 2, w, 0.01, null);
        }
        if (s.effects.has("frozen", now)) SkillFx.burst(mid, Particle.SNOWFLAKE, 4, w, 0.01, null);
        if (tickCount % 4 == 0 && s.shields.total(now) > 0) {
            SkillFx.circle(mid, w + 0.35, 10, Particle.DUST, SkillFx.dust(0xbfe6ff, 0.8f));
        }
        if (s.stealthUntil > now && tickCount % 2 == 0) SkillFx.burst(feet.clone().add(0, 0.3, 0), Particle.SMOKE, 2, 0.25, 0.0, null);
    }

    // ── 이동 제한 (속성 수정치) ───────────────────────────────────────────

    private void updatePhysical(State s, long now) {
        LivingEntity e = s.entity;
        if (!e.isValid()) return;
        boolean root = s.effects.has("root", now) || s.effects.has("stun", now) || s.effects.has("frozen", now);
        double slow = root ? 1.0 : Math.min(0.85, s.effects.value("slow", now));
        if (Math.abs(slow - s.appliedMove) > 1e-4) {
            setModifier(e, Attribute.MOVEMENT_SPEED, MOVE_KEY, slow <= 0 ? 0 : -slow);
            s.appliedMove = slow;
        }
        if (root != s.appliedRoot) {
            setModifier(e, Attribute.JUMP_STRENGTH, JUMP_KEY, root ? -1.0 : 0);
            s.appliedRoot = root;
            if (root) e.setVelocity(new Vector(0, Math.min(0, e.getVelocity().getY()), 0));
        }
        boolean kb = s.buffs.total("knockback_immune", now) > 0;
        if (kb != s.appliedKbImmune) {
            setModifier(e, Attribute.KNOCKBACK_RESISTANCE, KB_KEY, kb ? 1.0 : 0);
            s.appliedKbImmune = kb;
        }
        if (s.iceShell != null && !s.effects.has("frozen", now)) {
            SkillFx.remove(s.iceShell);
            s.iceShell = null;
        }
        if (s.markDisplay != null && !s.effects.has("mark", now)) {
            SkillFx.remove(s.markDisplay);
            s.markDisplay = null;
        }
    }

    private static void setModifier(LivingEntity e, Attribute attr, org.bukkit.NamespacedKey key, double value) {
        AttributeInstance inst = e.getAttribute(attr);
        if (inst == null) return;
        if (inst.getModifier(key) != null) inst.removeModifier(key);
        if (value != 0) {
            AttributeModifier.Operation op = attr == Attribute.KNOCKBACK_RESISTANCE ? AttributeModifier.Operation.ADD_NUMBER
                    : AttributeModifier.Operation.MULTIPLY_SCALAR_1;
            inst.addTransientModifier(new AttributeModifier(key, value, op));
        }
    }

    private void resetPhysical(State s) {
        LivingEntity e = s.entity;
        if (e.isValid()) {
            setModifier(e, Attribute.MOVEMENT_SPEED, MOVE_KEY, 0);
            setModifier(e, Attribute.JUMP_STRENGTH, JUMP_KEY, 0);
            setModifier(e, Attribute.KNOCKBACK_RESISTANCE, KB_KEY, 0);
        }
        s.appliedMove = 0;
        s.appliedRoot = false;
        s.appliedKbImmune = false;
        SkillFx.remove(s.iceShell);
        SkillFx.remove(s.markDisplay);
        s.iceShell = null;
        s.markDisplay = null;
    }

    // ── 리스너 ────────────────────────────────────────────────────────────

    /** 행동 불가 상태의 바닐라 공격 취소 (CombatListener 보다 먼저). */
    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onAttack(EntityDamageByEntityEvent e) {
        Entity d = e.getDamager();
        LivingEntity src = d instanceof org.bukkit.entity.Projectile pr && pr.getShooter() instanceof LivingEntity sh ? sh
                : d instanceof LivingEntity le ? le : null;
        if (src != null && !(d instanceof org.bukkit.entity.Projectile) && isStunned(src)) e.setCancelled(true);
    }

    /** 빙결된 동료를 때리면 해방 카운트 (PvP 꺼진 상태에서도). 행동 불가면 공격 시도 자체를 막는다. */
    @EventHandler(priority = EventPriority.LOW)
    public void onPreAttack(PrePlayerAttackEntityEvent e) {
        Player p = e.getPlayer();
        if (isStunned(p)) {
            e.setCancelled(true);
            return;
        }
        if (e.getAttacked() instanceof LivingEntity target && services.targets().isAlly(p, target) && !p.equals(target)) {
            State s = peek(target);
            if (s != null && s.effects.has("frozen", System.currentTimeMillis())) {
                e.setCancelled(true);
                s.freeHits--;
                SkillFx.sound(target.getLocation(), Sound.BLOCK_GLASS_HIT, 1f, 1.0f + (4 - s.freeHits) * 0.15f);
                SkillFx.burst(target.getLocation().add(0, 1, 0), Particle.ITEM_SNOWBALL, 10, 0.4, 0.1, null);
                if (s.freeHits <= 0) clear(target, "frozen");
            }
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onInteract(PlayerInteractEvent e) {
        if (isStunned(e.getPlayer())) e.setCancelled(true);
    }

    /** 은신한 플레이어를 바닐라 AI 가 노리지 못하게. */
    @EventHandler(ignoreCancelled = true)
    public void onTarget(EntityTargetLivingEntityEvent e) {
        if (e.getTarget() != null && isStealthed(e.getTarget())) e.setCancelled(true);
        if (e.getEntity() instanceof LivingEntity le && isStunned(le)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(EntityDeathEvent e) { clearAll(e.getEntity()); }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) { clearAll(e.getPlayer()); }

    /** 디버그·관리자 정보용: 현재 효과 요약. */
    public Map<String, Integer> summary(LivingEntity e) {
        State s = peek(e);
        Map<String, Integer> out = new HashMap<>();
        if (s == null) return out;
        long now = System.currentTimeMillis();
        for (EffectStack.Entry x : s.effects.all()) if (x.expiresAt > now) out.put(x.id, x.stacks);
        return out;
    }

    /** 몹 판별 (스킬에서 도발 등). */
    public java.util.Optional<CustomMob> mobOf(Entity e) {
        var m = services.mobs().byEntity(e);
        if (m.isPresent()) return m;
        return services.bosses().byEntity(e).map(b -> (CustomMob) b);
    }
}
