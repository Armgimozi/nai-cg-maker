package kr.labyrinth.combat;

import java.util.Locale;
import java.util.Map;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Params;

/**
 * 무기 한 자루의 공격 방식 (0.3.5, 순수) — 무기 종류(대검·활 …) 대신 무기마다 공격 간격·방식·피해 종류를 가진다.
 * <ul>
 *   <li>{@code style}: MELEE(근접 휘두르기) · RANGED(활 — 당겨 쏘기) · CASTER(시전 — 지금은 근접 휘두르기, 피해는 마법)</li>
 *   <li>{@code interval}: 툴팁 간격(초, 민첩 전). 활은 한 발 주기 = 끝까지 당기는 시간 + 0.15초</li>
 *   <li>{@code kind}: 기본 공격·무기 스킬의 기본 피해 종류 (시전 = 마법, 그 밖 = 물리)</li>
 *   <li>{@code skillPowerMult}: 스킬 위력 배율 (시전 1.05, 그 밖 1.0)</li>
 * </ul>
 * items.yml 의 {@code attack: {style, interval, kind, skill_power_mult}} 를 읽는다 ({@code speed} 만 있으면 1 ÷ speed).
 * 블록이 없는 무기는 예전 weapon_type 의 0.3.4 주기로 대신한다 (데이터를 옮기는 동안만).
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

    /** attack 블록이 없을 때 쓰는 0.3.4 종류 주기 (초). 데이터 옮기기가 끝나면 쓰이지 않는다. */
    private static final Map<String, WeaponAttack> LEGACY_TYPE = Map.of(
            "sword_shield", new WeaponAttack(Style.MELEE, 0.67, DamageKind.PHYSICAL, 1.0),
            "greatsword", new WeaponAttack(Style.MELEE, 1.05, DamageKind.PHYSICAL, 1.0),
            "dagger", new WeaponAttack(Style.MELEE, 0.45, DamageKind.PHYSICAL, 1.0),
            "bow", new WeaponAttack(Style.RANGED, 1.15, DamageKind.PHYSICAL, 1.0),
            "staff", new WeaponAttack(Style.CASTER, 0.91, DamageKind.MAGIC, CASTER_SKILL_POWER_MULT),
            "scepter", new WeaponAttack(Style.CASTER, 0.77, DamageKind.MAGIC, CASTER_SKILL_POWER_MULT));

    public WeaponAttack {
        if (style == null) style = Style.MELEE;
        if (kind == null) kind = style == Style.CASTER ? DamageKind.MAGIC : DamageKind.PHYSICAL;
        if (!(interval > 0) || Double.isInfinite(interval)) interval = UNARMED_INTERVAL;
        interval = Math.max(0.2, Math.min(5.0, interval));
        if (!(skillPowerMult > 0)) skillPowerMult = 1.0;
    }

    /** 무기 정의의 공격 방식. 무기가 아니면 맨손. */
    public static WeaponAttack of(ItemDef def) {
        if (def == null || !def.isWeapon()) return UNARMED;
        WeaponAttack legacy = LEGACY_TYPE.getOrDefault(def.weaponType() == null ? "" : def.weaponType(),
                new WeaponAttack(Style.MELEE, 0.67, DamageKind.PHYSICAL, 1.0));
        Params a = def.raw() == null ? Params.EMPTY : def.raw().sub("attack");
        if (a.isEmpty()) return legacy;
        Style style = Style.byId(a.str("style"), legacy.style());
        double interval = a.dbl("interval", Double.NaN);
        if (Double.isNaN(interval) && a.has("speed")) {
            double speed = a.dbl("speed", 0);
            interval = speed > 0 ? 1.0 / speed : Double.NaN;
        }
        if (Double.isNaN(interval)) interval = legacy.interval();
        DamageKind defKind = style == Style.CASTER ? DamageKind.MAGIC : DamageKind.PHYSICAL;
        DamageKind kind = DamageKind.byId(a.str("kind"), defKind);
        double sp = a.dbl("skill_power_mult", style == Style.CASTER ? CASTER_SKILL_POWER_MULT : 1.0);
        return new WeaponAttack(style, interval, kind, sp);
    }

    /** 바닐라 무기 (칼·도끼·삼지창 …): 초당 횟수 그대로 근접 물리. 바닐라 활·쇠뇌는 원거리 1.15초. */
    public static WeaponAttack vanilla(double attacksPerSecond, boolean bow) {
        if (bow) return new WeaponAttack(Style.RANGED, 1.15, DamageKind.PHYSICAL, 1.0);
        return new WeaponAttack(Style.MELEE, attacksPerSecond > 0 ? 1.0 / attacksPerSecond : UNARMED_INTERVAL,
                DamageKind.PHYSICAL, 1.0);
    }

    public boolean ranged() { return style == Style.RANGED; }

    /** 툴팁 '공격 속도 초당 N회' (민첩 전) = 1 ÷ interval. */
    public double attacksPerSecond() { return 1.0 / interval; }
}
