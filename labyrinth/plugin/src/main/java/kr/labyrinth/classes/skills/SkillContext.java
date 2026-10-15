package kr.labyrinth.classes.skills;

import java.util.Optional;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.mobs.CustomMob;
import kr.labyrinth.stats.DerivedStats;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/**
 * 스킬 한 번 시전의 문맥: 시전자, 직업·스킬 정의, 파라미터, 공용 동작(피해·치유·대상 고르기·연출).
 * 모든 피해는 {@link #damage} → {@code DamageService}, 모든 치유는 {@link #heal} → {@code DamageService.heal}.
 * 적/아군 판정은 전부 {@link Targeting}(→ {@code TargetFilter}) 을 지난다 — 다른 파티 플레이어도 같은 규칙으로 적(PvP, GDD §18).
 */
public final class SkillContext {

    /** ClassService 가 제공하는 콜백 (지연 효과에서 마나 환급·쿨다운 조정·채널링). */
    public interface Host {
        void refundMana(Player player, double amount);

        void setCooldown(Player player, String skillId, double seconds);

        void setChannel(Player player, long untilMs);
    }

    private final Services services;
    private final Player caster;
    private final ClassDef classDef;
    private final ClassDef.SkillDef skill;
    private final Host host;
    private final Targeting targeting;
    private final double manaCost;
    private String failReason;
    private boolean refunded;

    public SkillContext(Services services, Player caster, ClassDef classDef, ClassDef.SkillDef skill, Host host, double manaCost) {
        this.services = services;
        this.caster = caster;
        this.classDef = classDef;
        this.skill = skill;
        this.host = host;
        this.manaCost = manaCost;
        this.targeting = new Targeting(services, caster);
    }

    public Services services() { return services; }
    public Player caster() { return caster; }
    public ClassDef classDef() { return classDef; }
    public ClassDef.SkillDef skill() { return skill; }
    public String id() { return skill.id(); }
    public Params params() { return skill.params(); }
    public Targeting targets() { return targeting; }
    public DerivedStats stats() { return services.stats().get(caster); }
    public double manaCost() { return manaCost; }

    public double p(String key, double def) { return skill.params().dbl(key, def); }

    public int pi(String key, int def) { return skill.params().integer(key, def); }

    public boolean flag(String key, boolean def) { return skill.params().bool(key, def); }

    public String fx(String key, String def) { return skill.params().str(key, def); }

    /** 직업 색 (MiniMessage 색 태그 안에 쓰는 #rrggbb). */
    public String color() { return classDef.color() == null ? "#ffffff" : classDef.color(); }

    /** 직업 색 RGB 정수 (파티클 DUST 용). */
    public int rgb() {
        try {
            return Integer.parseInt(color().replace("#", ""), 16);
        } catch (NumberFormatException e) {
            return 0xffffff;
        }
    }

    // ── 실패·환급 ─────────────────────────────────────────────────────────

    /** 실패 이유 (액션바에 표시). 항상 false 를 돌려줘 {@code return ctx.fail("...")} 로 쓴다. */
    public boolean fail(String reasonMiniMessage) {
        this.failReason = reasonMiniMessage;
        return false;
    }

    public String failReason() { return failReason; }

    /**
     * 적중 수 보고 (지연 적중 포함). 비전술사 패시브 '비전 공명': 한 스킬로 multi_hit 명 이상 맞히면 소모 MP 의 refund 비율 환급.
     */
    public void reportHits(int hits) {
        if (refunded || classDef.passive() == null || !"arcane_resonance".equals(classDef.passive().id())) return;
        Params pp = classDef.passive().params();
        if (hits >= pp.integer("multi_hit", 3) && manaCost > 0) {
            refunded = true;
            host.refundMana(caster, manaCost * pp.dbl("refund", 0.5));
            SkillFx.burst(caster.getLocation().add(0, 1.2, 0), org.bukkit.Particle.ENCHANT, 18, 0.4, 0.6, null);
            if (services.hud().skillMessages()) services.hud().actionBar(caster, kr.labyrinth.core.Text.mm("<#b07cff>✦ 비전 공명 <gray>— MP "
                    + kr.labyrinth.core.Text.num(manaCost * pp.dbl("refund", 0.5)) + " 환급"), 30);
        }
    }

    /** 시전 취소(채널링 중단): 마나 환급 + 쿨다운을 seconds 로. */
    public void cancelCast(boolean refundMana, double cooldownSeconds) {
        if (refundMana && manaCost > 0) host.refundMana(caster, manaCost);
        host.setCooldown(caster, skill.id(), cooldownSeconds);
        host.setChannel(caster, 0);
    }

    public void channel(double seconds) { host.setChannel(caster, System.currentTimeMillis() + (long) (seconds * 1000)); }

    public void endChannel() { host.setChannel(caster, 0); }

    // ── 피해·치유 ─────────────────────────────────────────────────────────

    /**
     * 직업 스킬 배율 (0.3.5) = classes.yml {@code skill_scale}. 직업 스킬 피해 = 스킬 위력 × 이 값 × 스킬 배율 — 스킬 위력이
     * 무기 무게와 상관없으므로 무엇을 들든 같은 단계면 같다 (예전 '추천 무기 환산'을 대신함).
     */
    public double weaponScale() { return weaponScale(services, caster, classDef); }

    /** {@link #weaponScale()} 의 정적 판 — 스킬 문맥 밖(독날 적중 등)에서 쓴다. */
    public static double weaponScale(Services services, Player player, ClassDef cls) {
        return cls == null ? 1.0 : cls.skillScale();
    }

    /**
     * 지속 피해 비율(초당 공격력 배율 — 출혈·독·화상 potency)에 무기 환산을 곱한다. 부여 순간 공격력으로 굳으므로 부여할 때마다 부른다.
     * 상태이상 potency 는 0~1 사이만 비율로 읽히므로 0.95 에서 자른다.
     */
    public double dotRatio(double ratio) { return dotRatio(ratio, weaponScale()); }

    public static double dotRatio(double ratio, double scale) { return Math.min(0.95, ratio * scale); }

    /** 스킬 위력 × mult × 직업 스킬 배율의 스킬 피해. TargetFilter 로 적인지 다시 확인한다. @return 결과 (적이 아니면 null) */
    public DamageContext damage(LivingEntity target, double mult, DamageType type) {
        return damage(target, mult, type, 1.0, 0);
    }

    public DamageContext damage(LivingEntity target, double mult, DamageType type, double threat, double knockback) {
        if (target == null || !services.targets().isEnemy(caster, target)) return null;
        DamageContext c = DamageContext.attack(caster, target, mult * weaponScale(), type).skill(skill.id());
        if (threat != 1.0) c.threat(threat);
        if (knockback > 0 && !services.effects().isKnockbackImmune(target)) c.knockback(knockback);
        return services.damage().deal(c);
    }

    /**
     * 대상 최대 HP × ratio + heal_power_scale × 치유력 만큼 치유 (GDD §4.1). 사제 패시브 '은총'(넘친 치유 → 보호막, MP 회복) 적용.
     * @return 실제 회복량
     */
    public double heal(LivingEntity target, double ratio) {
        if (target == null || target.isDead()) return 0;
        double amount = services.damage().maxHp(target) * ratio + p("heal_power_scale", 1.0) * stats().healPower();
        return healFlat(target, amount);
    }

    public double healFlat(LivingEntity target, double amount) {
        if (amount <= 0 || target == null || target.isDead()) return 0;
        double healed = services.damage().heal(target, amount, true);
        if (classDef.passive() != null && "grace".equals(classDef.passive().id()) && target instanceof Player tp) {
            Params pp = classDef.passive().params();
            double over = amount - healed;
            if (over > 0.5) {
                double cap = services.stats().maxHp(tp) * pp.dbl("overheal_shield_cap", 0.10);
                services.effects().addShield(tp, Math.min(cap, over), pp.dbl("overheal_duration", 5), "grace_overheal");
            }
            if (!tp.equals(caster) || healed > 0) host.refundMana(caster, pp.dbl("mana_on_heal", 2));
        }
        return healed;
    }

    // ── 대상 정보 ─────────────────────────────────────────────────────────

    public boolean isBoss(Entity e) { return services.bosses().byEntity(e).isPresent(); }

    public Optional<CustomMob> mob(Entity e) {
        Optional<CustomMob> m = services.mobs().byEntity(e);
        if (m.isPresent()) return m;
        return services.bosses().byEntity(e).map(b -> (CustomMob) b);
    }

    /** 대상 HP 비율 (0~1). */
    public double hpRatio(LivingEntity e) {
        if (e instanceof Player p) return services.stats().currentHp(p) / Math.max(1, services.stats().maxHp(p));
        var pool = services.damage().poolOf(e);
        if (pool.isPresent()) return pool.get().health() / Math.max(1, pool.get().maxHealth());
        var a = e.getAttribute(org.bukkit.attribute.Attribute.MAX_HEALTH);
        return e.getHealth() / Math.max(1, a == null ? 20 : a.getValue());
    }
}
