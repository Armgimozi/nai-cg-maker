package kr.labyrinth.combat;

import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/**
 * 피해 한 건의 입력 + 결과. 모든 피해는 {@link DamageService#deal(DamageContext)} 한 곳을 지난다.
 * <p>
 * 0.3.5 원피해 (플레이어 공격자, {@link #attack}): 기준 × 피해 종류의 스탯 배율 × multiplier.
 * 기준 = {@link Base#PER_HIT}(기본 공격 — 무기 한 방 W) 또는 {@link Base#SKILL}(스킬 — 스킬 위력 SP, {@link #skill} 을 부르면 이것).
 * 피해 종류 = {@link #kind(DamageKind)} 로 정한 값, 없으면 기본 공격은 손에 든 무기의 종류, 그 밖은 유형에서
 * ({@link DamageKind#of}: 근접·원거리 물리 · 마법 마법 · 고정 고정).
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
    private DamageKind kind;
    private Base base = Base.PER_HIT;
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
    private double critBonus;
    private double defenseScale = 1.0;
    private double critDamageScale = 1.0;
    private double critDamageAdd;
    private String sourceId;
    private double weaponHit = Double.NaN;
    /** 화살을 쏜 활·마법탄을 쏜 시전 무기의 아이템 id (null = 지금 든 무기의 고유 효과, "" = 고유 효과 없음). */
    private String firedWith;
    private boolean casterBolt;

    // 결과
    private double finalDamage;
    private double dealt;
    private boolean crit;
    private boolean evaded;
    private boolean blocked;
    private boolean killed;
    private boolean cancelled;

    /** 원피해 기준: 무기 한 방 W(기본 공격) · 스킬 위력 SP(직업·무기 스킬). */
    public enum Base { PER_HIT, SKILL }

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

    /** 기본 공격: 무기 한 방 W × 손에 든 무기 피해 종류의 배율 × multiplier. */
    public static DamageContext basic(Player attacker, LivingEntity target, double multiplier, DamageType type) {
        return attack(attacker, target, multiplier, type);
    }

    /** 스킬 피해: 스킬 위력 SP × 피해 종류의 배율 × multiplier (skill_damage 적용). */
    public static DamageContext skill(Player attacker, LivingEntity target, double multiplier, DamageType type, DamageKind kind,
                                      String id) {
        return attack(attacker, target, multiplier, type).kind(kind).skill(id);
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
    /** 직업·무기 스킬 피해 (skill_damage 적용, 원피해 기준 = 스킬 위력). */
    public DamageContext skill(String id) { this.skill = true; this.base = Base.SKILL; this.sourceId = id; return this; }
    /** 피해 종류 (null = 기본값). */
    public DamageContext kind(DamageKind k) { this.kind = k; return this; }
    /** 원피해 기준을 직접 정한다 (스킬이 한 방 기준을 쓰고 싶을 때 등). */
    public DamageContext base(Base b) { this.base = b == null ? Base.PER_HIT : b; return this; }
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
    /** 이 피해 한 건의 치명타 확률 가산 (1.0 이상 = 확정 치명타, 플레이어 공격자만). 누적된다. */
    public DamageContext critBonus(double add) { this.critBonus += add; return this; }
    /** 대상 방어를 얼마나 셀지 (1 = 그대로, 0 = 방어 무시). PvP 훅이 before() 에서 바꾼다 (pvp.defense_weight). */
    public DamageContext defenseScale(double s) { this.defenseScale = Math.max(0, s); return this; }
    /** 치명 '추가' 피해 배율 (1 = 그대로, 0.6 = 치명 피해 2.5 → 1.9). PvP 훅이 before() 에서 바꾼다 (pvp.crit_damage_scale). */
    public DamageContext critDamageScale(double s) { this.critDamageScale = Math.max(0, s); return this; }
    /** 이 피해 한 건의 치명 피해 가산 (0.45 = 치명 피해 +45%p, 고유 효과 피 냄새). 누적된다. PvP 의 critDamageScale 은 그 뒤에 곱한다. */
    public DamageContext critDamageAdd(double add) { this.critDamageAdd += add; return this; }
    /**
     * 기본 공격 한 방 W 를 지금 든 무기 대신 이 값으로 (0.3.6.1 화살 — 쏜 순간의 활 W · 마법탄 — 쏜 순간의 시전 무기 W.
     * 날아가는 동안 무기를 바꿔도 그대로). 기준이 {@link Base#PER_HIT} 일 때만 쓴다. 0 이하·NaN 은 '없음'(지금 든 무기 — {@link #hasWeaponHit()} 거짓).
     */
    public DamageContext weaponHit(double w) { this.weaponHit = w > 0 ? w : Double.NaN; return this; }
    /**
     * 쏜 무기의 아이템 id — 고유 효과도 맞는 순간 든 무기가 아니라 쏜 무기로 (0.3.6.1 화살 = 쏜 활, 마법탄 = 쏜 시전 무기).
     * null 은 "" (고유 효과 없음 — 미궁 활이 아닌 것으로 쐈거나 덜 당긴 화살).
     */
    public DamageContext firedWith(String weaponId) { this.firedWith = weaponId == null ? "" : weaponId; return this; }
    /** 시전 무기 마법탄 (0.3.6.1) — 기본 공격 (유형은 마법). '기본 공격 적중' 효과(광전사 피의 분노 MP 등)가 근접처럼 붙는다. */
    public DamageContext casterBolt() { this.casterBolt = true; return this; }

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
    /** 정해 둔 피해 종류 (없으면 null — DamageService 가 기본값으로 채운다). */
    public DamageKind kind() { return kind; }
    /** 실제 피해 종류 (정해 둔 값 → 유형의 기본값). DamageService 가 원피해를 정한 뒤에는 늘 채워져 있다. */
    public DamageKind effectiveKind() { return kind != null ? kind : DamageKind.of(type); }
    public Base base() { return base; }
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
    public double critBonus() { return critBonus; }
    public double defenseScale() { return defenseScale; }
    public double critDamageScale() { return critDamageScale; }
    public double critDamageAdd() { return critDamageAdd; }
    /** 정해 둔 기본 공격 한 방 (없으면 NaN — 지금 든 무기의 W). */
    public double weaponHit() { return weaponHit; }
    public boolean hasWeaponHit() { return !Double.isNaN(weaponHit); }
    /** 쏜 무기의 id ({@link #firedWith(String)}) — 화살·마법탄, 그 밖은 null (= 지금 든 무기). */
    public String firedWith() { return firedWith; }
    /** 시전 무기 마법탄인가 (기본 공격, 유형 마법). */
    public boolean isCasterBolt() { return casterBolt; }
    /** 기본 공격인가 — 플레이어가 무기로 친 한 대 (스킬·보스 패턴·지속 피해·고유 효과 피해·출처 붙은 피해가 아님). */
    public boolean isBasicAttack() {
        return attacker instanceof Player && !skill && !pattern && sourceId == null && usesAttackPower() && base == Base.PER_HIT;
    }
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
