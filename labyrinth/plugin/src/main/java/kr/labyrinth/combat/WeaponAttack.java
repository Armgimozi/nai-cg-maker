package kr.labyrinth.combat;

import java.util.Locale;
import java.util.Map;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Params;

/**
 * 무기 한 자루의 공격 방식 (0.3.5, 순수) — 무기 종류(분류) 없이 무기마다 공격 간격·방식·피해 종류를 가진다.
 * <ul>
 *   <li>{@code style}: MELEE(근접 휘두르기) · RANGED(활 — 당겨 쏘기) · CASTER(시전 — 0.3.6.1 부터 좌클릭 = 마법탄, 피해는 마법.
 *       한 방·간격은 예전 휘두르기와 같고 공격 시계를 함께 쓴다 — {@code CasterBolts}. config combat.caster_bolt.enabled: false 면 예전처럼 휘두르기)</li>
 *   <li>{@code interval}: 툴팁 간격(초, 민첩 전). 활은 한 발 주기 = 끝까지 당기는 시간 + 0.15초</li>
 *   <li>{@code kind}: 기본 공격·무기 스킬의 기본 피해 종류 (시전 = 마법, 그 밖 = 물리)</li>
 *   <li>{@code skillPowerMult}: 스킬 위력 배율 (시전 1.05, 그 밖 1.0)</li>
 * </ul>
 * items.yml 의 {@code attack: {style, interval, kind, skill_power_mult}} 를 읽는다 ({@code speed} 만 있으면 1 ÷ speed).
 * 콘텐츠를 읽을 때 한 번 만들어 {@link ItemDef#attack()} 에 둔다 ({@link #parse}).
 * 블록이 없는 무기(0.3.4 때 손대 jar 의 새 items.yml 로 바뀌지 않은 파일)는 예전 키의 0.3.4 주기로 대신하고, 검사기가 경고한다.
 */
public record WeaponAttack(Style style, double interval, DamageKind kind, double skillPowerMult) {

    public enum Style {
        MELEE, RANGED, CASTER;

        public static Style byId(String id, Style def) {
            if (id == null || id.isBlank()) return def;
            try {
                return valueOf(id.trim().toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                return def;
            }
        }
    }

    private static final double UNARMED_INTERVAL = 0.625;
    /** 시전 무기의 스킬 위력 배율 기본값 (설계상 기본 공격이 약한 몫). */
    public static final double CASTER_SKILL_POWER_MULT = 1.05;
    /** 맨손 = 한 방 3 · 간격 0.625초 (config weapon_attack_speed.none 1.6 의 역수) · 근접 · 물리. */
    public static final WeaponAttack UNARMED = new WeaponAttack(Style.MELEE, 0.625, DamageKind.PHYSICAL, 1.0);

    /**
     * attack 블록이 없는 예전(0.3.4) items.yml 을 읽을 때만 쓰는 옛 키 → 그때의 주기 (초). 0.3.5 jar 의 items.yml 은 무기마다
     * attack 블록이 있어 쓰이지 않는다. 화면에는 어떤 분류 이름도 나오지 않는다.
     */
    private static final Map<String, WeaponAttack> LEGACY_034 = Map.of(
            "sword_shield", new WeaponAttack(Style.MELEE, 0.67, DamageKind.PHYSICAL, 1.0),
            "greatsword", new WeaponAttack(Style.MELEE, 1.05, DamageKind.PHYSICAL, 1.0),
            "dagger", new WeaponAttack(Style.MELEE, 0.45, DamageKind.PHYSICAL, 1.0),
            "bow", new WeaponAttack(Style.RANGED, 1.15, DamageKind.PHYSICAL, 1.0),
            "staff", new WeaponAttack(Style.CASTER, 0.91, DamageKind.MAGIC, CASTER_SKILL_POWER_MULT),
            "scepter", new WeaponAttack(Style.CASTER, 0.77, DamageKind.MAGIC, CASTER_SKILL_POWER_MULT));
    /** attack 블록도 옛 키도 없는 무기 = 근접 0.67초 물리. */
    public static final WeaponAttack DEFAULT = new WeaponAttack(Style.MELEE, 0.67, DamageKind.PHYSICAL, 1.0);

    public WeaponAttack {
        if (style == null) style = Style.MELEE;
        if (kind == null) kind = style == Style.CASTER ? DamageKind.MAGIC : DamageKind.PHYSICAL;
        if (!(interval > 0) || Double.isInfinite(interval)) interval = UNARMED_INTERVAL;
        interval = Math.max(0.2, Math.min(5.0, interval));
        if (!(skillPowerMult > 0)) skillPowerMult = 1.0;
    }

    /** 무기 정의의 공격 방식 (읽을 때 정한 {@link ItemDef#attack()}). 무기가 아니면 맨손. */
    public static WeaponAttack of(ItemDef def) {
        if (def == null || !def.isWeapon()) return UNARMED;
        return def.attack() != null ? def.attack() : DEFAULT;
    }

    /** items.yml 무기 항목(raw) 의 attack 블록 → 공격 방식. 블록이 없으면 {@link #legacy}. */
    public static WeaponAttack parse(Params raw) {
        Params item = raw == null ? Params.EMPTY : raw;
        WeaponAttack fallback = legacy(item);
        Params a = item.sub("attack");
        if (a.isEmpty()) return fallback;
        Style style = Style.byId(a.str("style"), fallback.style());
        double interval = a.dbl("interval", Double.NaN);
        if (Double.isNaN(interval) && a.has("speed")) {
            double speed = a.dbl("speed", 0);
            interval = speed > 0 ? 1.0 / speed : Double.NaN;
        }
        if (Double.isNaN(interval)) interval = style == fallback.style() ? fallback.interval() : DEFAULT.interval();
        DamageKind defKind = style == Style.CASTER ? DamageKind.MAGIC : DamageKind.PHYSICAL;
        DamageKind kind = DamageKind.byId(a.str("kind"), defKind);
        double sp = a.dbl("skill_power_mult", style == Style.CASTER ? CASTER_SKILL_POWER_MULT : 1.0);
        return new WeaponAttack(style, interval, kind, sp);
    }

    /** attack 블록이 없을 때: 예전 키(weapon_type)가 남아 있으면 그때의 주기, 없으면 {@link #DEFAULT}. */
    public static WeaponAttack legacy(Params raw) {
        String old = raw == null ? null : raw.str("weapon_type");
        return old == null ? DEFAULT : LEGACY_034.getOrDefault(old.trim(), DEFAULT);
    }

    /** 바닐라 무기 (칼·도끼·삼지창 …): 초당 횟수 그대로 근접 물리. 바닐라 활·쇠뇌는 원거리 1.15초. */
    public static WeaponAttack vanilla(double attacksPerSecond, boolean bow) {
        if (bow) return new WeaponAttack(Style.RANGED, 1.15, DamageKind.PHYSICAL, 1.0);
        return new WeaponAttack(Style.MELEE, attacksPerSecond > 0 ? 1.0 / attacksPerSecond : UNARMED_INTERVAL,
                DamageKind.PHYSICAL, 1.0);
    }

    public boolean ranged() { return style == Style.RANGED; }

    public boolean caster() { return style == Style.CASTER; }

    /** 시전 무기 좌클릭이 마법탄인가 (config combat.caster_bolt.enabled — 전투 모듈이 켤 때·다시 읽을 때 정한다. 툴팁·도감 글이 따른다). */
    private static volatile boolean casterBolt = true;

    public static boolean casterBolt() { return casterBolt; }

    public static void casterBolt(boolean on) { casterBolt = on; }

    /** 기본 공격이 마법탄인가 (시전 무기 + 켜짐). */
    public boolean firesBolt() { return style == Style.CASTER && casterBolt; }

    /** 툴팁 '공격 속도 초당 N회' (민첩 전) = 1 ÷ interval. */
    public double attacksPerSecond() { return 1.0 / interval; }
}
