package kr.labyrinth.items.weaponskills;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.IntPredicate;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.mobs.CustomMob;
import org.bukkit.Color;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/**
 * 무기 스킬 시전 한 번의 문맥 + 공용 헬퍼 (GDD §17.1 공통 규칙):
 * 피해 = params.damage × 스킬 위력 × 피해 종류 배율 × (1 + skill_damage) → {@code DamageContext.skill(...)} (DamageService 단일 경로),
 * 피해 유형 = params.damage_type, 피해 종류 = {@link SkillKinds#hitKind} (없으면 무기 attack.kind),
 * 상태이상 effect/amount/effect_duration(+dot_ratio), taunt, boss_* 대체값, fx, sound.
 */
public final class SkillCast {

    private static final Set<String> DOTS = Set.of("poison", "bleed", "burn");

    public final Services services;
    public final LabWeaponSkillService service;
    public final Player player;
    public final ItemDef weapon;
    public final ItemDef.WeaponSkillDef skill;
    public final Params p;
    private final DamageType defaultType;
    private double charge = -1;

    SkillCast(Services services, LabWeaponSkillService service, Player player, ItemDef weapon, ItemDef.WeaponSkillDef skill,
              DamageType defaultType) {
        this.services = services;
        this.service = service;
        this.player = player;
        this.weapon = weapon;
        this.skill = skill;
        this.p = skill.params() == null ? Params.EMPTY : skill.params();
        this.defaultType = defaultType;
    }

    /** 활 "웅크리고 당겨 쏘기"(SNEAK_RIGHT) 의 당김 세기 0~1. 그 외 입력은 -1. */
    public double charge() { return charge; }

    SkillCast charge(double v) {
        this.charge = v;
        return this;
    }

    // ── 파라미터 ──────────────────────────────────────────────────────────

    public double num(String key, double def) { return p.dbl(key, def); }

    /** bool 또는 숫자(>0 = true). */
    public boolean flag(String key, boolean def) {
        Object v = p.get(key);
        if (v instanceof Boolean b) return b;
        if (v instanceof Number n) return n.doubleValue() > 0;
        if (v instanceof String s) return Boolean.parseBoolean(s);
        return def;
    }

    /** bool(true = 무한) 또는 정수(관통 가능한 추가 대상 수). */
    public int pierce() {
        Object v = p.get("pierce");
        if (v instanceof Boolean b) return b ? Integer.MAX_VALUE : 0;
        if (v instanceof Number n) return Math.max(0, n.intValue());
        return 0;
    }

    /** 숫자 또는 bool(true = def). */
    public double amountOrFlag(String key, double trueValue) {
        Object v = p.get(key);
        if (v instanceof Number n) return n.doubleValue();
        if (v instanceof Boolean b) return b ? trueValue : 0;
        return 0;
    }

    public double damage() { return num("damage", 1.0); }

    public DamageType type() { return DamageType.byId(p.str("damage_type"), defaultType); }

    /** 이 스킬 피해의 종류 (물리 = 힘, 마법 = 지능) — damage_type → 구현 기본 → 무기 attack.kind. */
    public DamageKind kind() { return SkillKinds.hitKind(skill.id(), p, weaponKind()); }

    /** 무기의 기본 피해 종류 (attack.kind). */
    public DamageKind weaponKind() { return SkillKinds.weaponKind(weapon); }

    public String fx(String fallback) {
        String f = p.str("fx");
        return f != null && Fx.exists(services, f) ? f : (fallback != null && Fx.exists(services, fallback) ? fallback : null);
    }

    public Color color() { return Fx.color(services, p.str("fx")); }

    /** 버프 맵 (params.buff / ally_buff). */
    public Map<String, Double> buffMap(String key) {
        Map<String, Double> out = new LinkedHashMap<>();
        Params b = p.sub(key);
        for (String k : b.keys()) out.put(k, b.dbl(k, 0));
        return out;
    }

    public String sourceId() { return "ws:" + weapon.id() + ":" + skill.input(); }

    // ── 대상 ──────────────────────────────────────────────────────────────

    public WeaponTargeting targets() { return service.targeting(); }

    public List<LivingEntity> enemies(Location center, double radius) {
        return targets().enemiesInRadius(player, center, radius);
    }

    public List<Player> allies(Location center, double radius) {
        return targets().alliesInRadius(player, center, radius);
    }

    public boolean isBoss(Entity e) { return services.bosses().byEntity(e).isPresent(); }

    // ── 피해 ──────────────────────────────────────────────────────────────

    /** 스킬 위력 × mult 의 스킬 피해 + 상태이상·도발. 적이 아니면 null. */
    public DamageContext hit(LivingEntity target, double mult) { return hit(target, mult, 0); }

    public DamageContext hit(LivingEntity target, double mult, double knockback) {
        if (target == null || !targets().isEnemy(player, target) || mult <= 0) return null;
        DamageContext ctx = DamageContext.skill(player, target, mult, type(), kind(), sourceId());
        if (knockback > 0 && !isBoss(target)) ctx.knockback(knockback);
        services.damage().deal(ctx);
        if (!ctx.cancelled() && !ctx.evaded()) afterHit(target);
        return ctx;
    }

    /** 공통 키: effect/amount/effect_duration(+dot_ratio), taunt. */
    public void afterHit(LivingEntity target) {
        if (target.isDead()) return;
        String effect = p.str("effect");
        if (effect != null && !effect.isBlank()) {
            double dur = num("effect_duration", 2.0);
            double potency = p.has("amount") ? num("amount", 0) : DOTS.contains(effect) ? num("dot_ratio", 0.15) : 0;
            if (!(isBoss(target) && "stun".equals(effect))) services.effects().apply(target, effect, dur, potency, player);
        }
        double taunt = num("taunt", 0);
        if (taunt > 0) taunt(target, taunt);
    }

    public void taunt(LivingEntity target, double seconds) {
        services.mobs().byEntity(target).ifPresentOrElse(m -> m.taunt(player, seconds),
                () -> services.bosses().byEntity(target).ifPresent(b -> ((CustomMob) b).taunt(player, seconds)));
    }

    public void stun(LivingEntity target, double seconds) {
        if (seconds > 0) services.effects().apply(target, "stun", seconds, 0, player);
    }

    /** 위로 띄우기 (보스는 boss_launch, 기본 0). */
    public void launch(LivingEntity target, double normal, double boss) {
        double v = isBoss(target) ? boss : normal;
        if (v <= 0) return;
        target.setVelocity(target.getVelocity().setY(Math.min(1.5, v)));
    }

    /** center 쪽으로 끌기 (보스는 boss 값, 기본 0). */
    public void pull(LivingEntity target, Location center, double strength, double bossStrength) {
        double s = isBoss(target) ? bossStrength : strength;
        if (s <= 0) return;
        Vector d = center.toVector().subtract(target.getLocation().toVector());
        double len = d.length();
        if (len < 0.6) return;
        d.multiply(1.0 / len).multiply(Math.min(1.2, s));
        d.setY(Math.max(-0.1, Math.min(0.25, d.getY() + 0.05)));
        target.setVelocity(target.getVelocity().multiply(0.4).add(d));
    }

    // ── 치유 ──────────────────────────────────────────────────────────────

    /** 최대 HP × ratio + 치유력 × scale (PvP 배율 전). */
    public double healAmount(Player target, double ratio, double healPowerScale) {
        return services.stats().maxHp(target) * ratio + services.stats().get(player).healPower() * healPowerScale;
    }

    /** 최대 HP × ratio(비율 몫) + 치유력 × scale(고정 몫) — PvP 전투 중인 대상이면 회복 배율 (pvp_spec §8). */
    public void heal(Player target, double ratio, double healPowerScale) {
        double pct = services.stats().maxHp(target) * ratio;
        double flat = services.stats().get(player).healPower() * healPowerScale;
        if (pct + flat > 0) services.damage().heal(target, pct, flat, kr.labyrinth.combat.HealKind.SKILL, true);
    }

    // ── 위치 ──────────────────────────────────────────────────────────────

    public Vector look() { return player.getEyeLocation().getDirection(); }

    public Vector flatLook() {
        Vector v = look().setY(0);
        if (v.lengthSquared() < 1e-6) v = new Vector(-Math.sin(Math.toRadians(player.getYaw())), 0, Math.cos(Math.toRadians(player.getYaw())));
        return v.normalize();
    }

    /** 바라보는 지점(최대 range) 의 바닥 위치. 블록에 닿으면 그 앞. */
    public Location targetPoint(double range) {
        Location eye = player.getEyeLocation();
        RayTraceResult r = player.getWorld().rayTraceBlocks(eye, eye.getDirection(), range, FluidCollisionMode.NEVER, true);
        Location at = r == null ? eye.clone().add(eye.getDirection().multiply(range))
                : r.getHitPosition().toLocation(player.getWorld()).subtract(eye.getDirection().multiply(0.4));
        return ground(at, 8);
    }

    /** 아래로 maxDown 블록 안의 바닥 위 (없으면 그대로). */
    public static Location ground(Location at, int maxDown) {
        Location l = at.clone();
        for (int i = 0; i <= maxDown; i++) {
            Block below = l.getBlock().getRelative(org.bukkit.block.BlockFace.DOWN);
            if (!below.isPassable()) {
                l.setY(below.getY() + 1.0);
                return l;
            }
            l.subtract(0, 1, 0);
        }
        return at;
    }

    /** 플레이어가 서 있을 수 있는 위치인가 (발·머리 통과 가능). */
    public static boolean standable(Location l) {
        return l.getBlock().isPassable() && l.clone().add(0, 1, 0).getBlock().isPassable();
    }

    // ── 연출 ──────────────────────────────────────────────────────────────

    public ItemDisplay display(Location at, String fallbackFx, float scale, int lifetime) {
        String f = fx(fallbackFx);
        return f == null ? null : Fx.spawn(services, at, f, scale, lifetime);
    }

    public void sound(Sound fallback, float volume, float pitch) {
        String key = p.str("sound");
        if (key != null && !key.isBlank()) player.getWorld().playSound(player.getLocation(), key, volume, pitch);
        else player.getWorld().playSound(player.getLocation(), fallback, volume, pitch);
    }

    public void soundAt(Location at, Sound s, float volume, float pitch) {
        at.getWorld().playSound(at, s, volume, pitch);
    }

    public void particles(Particle type, Location at, int count, double spread, double speed) {
        at.getWorld().spawnParticle(type, at, count, spread, spread, spread, speed);
    }

    /** 색 입자 원 (장판 테두리 표시). */
    public void ring(Location center, double radius, int points) {
        Color c = color();
        for (int i = 0; i < points; i++) {
            double a = Math.PI * 2 * i / points;
            Fx.dust(center.clone().add(Math.cos(a) * radius, 0.15, Math.sin(a) * radius), c, 1.1f, 1, 0.02);
        }
    }

    /**
     * 반복 작업: periodTicks 마다 fn(경과 틱) 호출, totalTicks 가 지나거나 fn 이 false 를 돌려주면 끝.
     * 플레이어가 나가거나 죽으면 자동 종료(onEnd 호출).
     */
    public void repeat(int periodTicks, int totalTicks, IntPredicate fn, Runnable onEnd) {
        service.schedule(player, Math.max(1, periodTicks), totalTicks, fn, onEnd);
    }

    public void later(int ticks, Runnable r) {
        service.schedule(player, Math.max(1, ticks), Math.max(1, ticks), t -> false, r);
    }

    static int ticks(double seconds) { return (int) Math.max(1, Math.round(seconds * 20.0)); }
}
