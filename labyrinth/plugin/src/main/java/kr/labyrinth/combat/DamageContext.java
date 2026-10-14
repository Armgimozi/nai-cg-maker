package kr.labyrinth.combat;

import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/**
 * 피해 한 건의 입력 + 결과. 모든 피해는 {@link DamageService#deal(DamageContext)} 한 곳을 지난다.
 * <pre>
 * // 플레이어 스킬: 공격력 × 1.2 배율의 마법 피해
 * services.damage().deal(DamageContext.attack(player, target, 1.2, DamageType.MAGIC).skill("arcane_bolt"));
 * // 몹/보스 → 플레이어: 이미 배율이 적용된 원피해
 * services.damage().deal(DamageContext.raw(bossEntity, player, boss.damage() * 1.3, DamageType.MELEE).pattern("vine_lash"));
 * // 최대 HP 비율 피해(방어·회피·막기 무시)
 * services.damage().deal(DamageContext.percent(source, player, 0.15).pattern("erasure"));
 * </pre>
 */
public final class DamageContext {

    private final LivingEntity attacker;
    private final LivingEntity target;
    private double amount;
    private double attackMultiplier = Double.NaN;
    private double percent = Double.NaN;
    private DamageType type;
    private boolean skill;
    private boolean pattern;
    private boolean canCrit = true;
    private boolean canEvade = true;
    private boolean canBlock = true;
    private boolean ignoreDefense;
    private boolean showNumber = true;
    private boolean applyLifesteal = true;
    private double knockback;
    private double threatMultiplier = 1.0;
    private String sourceId;

    // 결과
    private double finalDamage;
    private double dealt;
    private boolean crit;
    private boolean evaded;
    private boolean blocked;
    private boolean killed;
    private boolean cancelled;

    private DamageContext(LivingEntity attacker, LivingEntity target, DamageType type) {
        this.attacker = attacker;
        this.target = target;
        this.type = type;
    }

    /** 원피해 그대로 (몹·보스 → 대상, 고정 피해). */
    public static DamageContext raw(LivingEntity attacker, LivingEntity target, double amount, DamageType type) {
        DamageContext c = new DamageContext(attacker, target, type);
        c.amount = amount;
        return c;
    }

    /** 플레이어 공격력 × multiplier (DamageService 가 공격자의 파생 능력치로 계산). */
    public static DamageContext attack(Player attacker, LivingEntity target, double multiplier, DamageType type) {
        DamageContext c = new DamageContext(attacker, target, type);
        c.attackMultiplier = multiplier;
        return c;
    }

    /** 대상 최대 HP × pct 의 TRUE 피해 (방어·회피·치명타·막기 무시, GDD §8.4 *_pct). */
    public static DamageContext percent(LivingEntity attacker, LivingEntity target, double pct) {
        DamageContext c = new DamageContext(attacker, target, DamageType.TRUE);
        c.percent = pct;
        c.canCrit = false;
        c.canEvade = false;
        c.canBlock = false;
        c.ignoreDefense = true;
        return c;
    }

    // ── 옵션 (체이닝) ─────────────────────────────────────────────────────
    /** 직업·무기 스킬 피해 (skill_damage 적용). */
    public DamageContext skill(String id) { this.skill = true; this.sourceId = id; return this; }
    /** 보스 패턴/장판 피해: 회피 불가. */
    public DamageContext pattern(String id) { this.pattern = true; this.canEvade = false; this.sourceId = id; return this; }
    public DamageContext source(String id) { this.sourceId = id; return this; }
    public DamageContext noCrit() { this.canCrit = false; return this; }
    public DamageContext noEvade() { this.canEvade = false; return this; }
    public DamageContext noBlock() { this.canBlock = false; return this; }
    public DamageContext ignoreDefense() { this.ignoreDefense = true; return this; }
    public DamageContext hideNumber() { this.showNumber = false; return this; }
    public DamageContext noLifesteal() { this.applyLifesteal = false; return this; }
    public DamageContext knockback(double strength) { this.knockback = strength; return this; }
    public DamageContext threat(double mult) { this.threatMultiplier = mult; return this; }
    public DamageContext type(DamageType t) { this.type = t; return this; }

    // ── 입력 접근 ─────────────────────────────────────────────────────────
    public LivingEntity attacker() { return attacker; }
    public Player attackerPlayer() { return attacker instanceof Player p ? p : null; }
    public LivingEntity target() { return target; }
    public double amount() { return amount; }
    /** DamageService 가 공격력/비율을 원피해로 바꿀 때 사용. */
    public void amount(double a) { this.amount = a; }
    public boolean usesAttackPower() { return !Double.isNaN(attackMultiplier); }
    public double attackMultiplier() { return attackMultiplier; }
    public boolean isPercent() { return !Double.isNaN(percent); }
    public double percent() { return percent; }
    public DamageType type() { return type; }
    public boolean isSkill() { return skill; }
    public boolean isPattern() { return pattern; }
    public boolean canCrit() { return canCrit; }
    public boolean canEvade() { return canEvade; }
    public boolean canBlock() { return canBlock; }
    public boolean ignoresDefense() { return ignoreDefense || type == DamageType.TRUE; }
    public boolean showNumber() { return showNumber; }
    public boolean applyLifesteal() { return applyLifesteal; }
    public double knockbackStrength() { return knockback; }
    public double threatMultiplier() { return threatMultiplier; }
    public String sourceId() { return sourceId; }

    // ── 결과 ──────────────────────────────────────────────────────────────
    /** 계산된 최종 피해 (적용 전). */
    public double finalDamage() { return finalDamage; }
    /** 실제로 깎인 HP. */
    public double dealt() { return dealt; }
    public boolean crit() { return crit; }
    public boolean evaded() { return evaded; }
    public boolean blocked() { return blocked; }
    public boolean killed() { return killed; }
    /** 무적·대상 없음 등으로 적용되지 않음. */
    public boolean cancelled() { return cancelled; }

    void result(double finalDamage, boolean crit, boolean evaded, boolean blocked) {
        this.finalDamage = finalDamage;
        this.crit = crit;
        this.evaded = evaded;
        this.blocked = blocked;
    }

    void applied(double dealt, boolean killed) {
        this.dealt = dealt;
        this.killed = killed;
    }

    void cancel() { this.cancelled = true; }
}
