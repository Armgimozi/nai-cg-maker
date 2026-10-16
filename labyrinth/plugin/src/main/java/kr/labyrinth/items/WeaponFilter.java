package kr.labyrinth.items;

import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.ItemDef;

/**
 * 도감·대장간 무기 거르개 (0.3.5, 순수) — 무기 종류(분류) 대신 공격 방식과 피해 종류로 거른다.
 */
public enum WeaponFilter {
    ALL("전체"), MELEE("근접"), RANGED("원거리"), CASTER("시전"), PHYSICAL("물리 피해"), MAGIC("마법 피해");

    private final String label;

    WeaponFilter(String label) { this.label = label; }

    public String label() { return label; }

    /** 다음 거르개 (끝이면 전체). */
    public WeaponFilter next() { return values()[(ordinal() + 1) % values().length]; }

    public boolean test(ItemDef d) {
        if (d == null || !d.isWeapon()) return this == ALL;
        WeaponAttack a = WeaponAttack.of(d);
        return switch (this) {
            case ALL -> true;
            case MELEE -> a.style() == WeaponAttack.Style.MELEE;
            case RANGED -> a.style() == WeaponAttack.Style.RANGED;
            case CASTER -> a.style() == WeaponAttack.Style.CASTER;
            case PHYSICAL -> a.kind() == DamageKind.PHYSICAL;
            case MAGIC -> a.kind() == DamageKind.MAGIC;
        };
    }
}
