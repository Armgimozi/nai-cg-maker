package kr.labyrinth.content;

import java.util.List;
import java.util.Map;
import kr.labyrinth.combat.WeaponAttack;

/**
 * items.yml 의 아이템 하나. stats 는 [최소, 최대] 굴림 범위(GDD §11.7 키).
 * <p>
 * {@code levelReq} (items.yml level_req): 장비는 <b>숨은 내부 레벨</b> — 정렬·강화 골드·드롭 단계에만 쓰고 표시·착용 제한은 없다.
 * 소모품은 그대로 사용 레벨. 장비 착용 조건은 {@code requires}(요구 능력치, {@link #requirement()}).
 * <p>
 * {@code attack} (0.3.5): 무기마다 공격 방식 — 간격·근접/원거리/시전·피해 종류 ({@link WeaponAttack}). 무기 종류(분류)는 없다.
 * 무기가 아니면 null. 무기인데 null 로 만들면 raw 의 attack 블록을 읽는다.
 * <p>
 * {@code unique} (0.3.5, unique_spec): 무기 고유 효과 하나 ({@link UniqueDef}). 무기가 아니면 null. 무기인데 null 로 만들면
 * raw 의 unique 블록을 읽는다 (없으면 null — 효과 없음).
 */
public record ItemDef(
        String id,
        String name,
        ItemType type,
        WeaponAttack attack,
        String armorSlot,
        String armorSet,
        Rarity rarity,
        int levelReq,
        StatRequirement requires,
        List<String> classes,
        Map<String, Range> stats,
        String setBonus,
        String aura,
        List<WeaponSkillDef> weaponSkills,
        int floor,
        boolean pool,
        List<String> sources,
        Params use,
        Params model,
        Params texture,
        String lore,
        Params raw,
        UniqueDef unique) {

    /**
     * 무기 스킬. input = LEFT | RIGHT | SNEAK_LEFT | SNEAK_RIGHT.
     * pvpMult = 플레이어에게 주는 피해 배율 (items.yml {@code weapon_skills[].pvp_mult}, 기본 1, 0.1~1.0 — pvp_spec §6).
     */
    public record WeaponSkillDef(String id, String name, String input, double cooldown, double mana, Params params,
                                 String description, double pvpMult) {

        public WeaponSkillDef(String id, String name, String input, double cooldown, double mana, Params params,
                              String description) {
            this(id, name, input, cooldown, mana, params, description, 1.0);
        }
    }

    public ItemDef {
        if (type != ItemType.WEAPON) {
            attack = null;
            unique = null;
        } else {
            if (attack == null) attack = WeaponAttack.parse(raw);
            if (unique == null) unique = UniqueDef.parse(raw);
        }
    }

    /** 고유 효과를 raw 에서 읽는다 (0.3.4 까지의 꼴 — 시험·도구용). */
    public ItemDef(String id, String name, ItemType type, WeaponAttack attack, String armorSlot, String armorSet,
                   Rarity rarity, int levelReq, StatRequirement requires, List<String> classes, Map<String, Range> stats,
                   String setBonus, String aura, List<WeaponSkillDef> weaponSkills, int floor, boolean pool,
                   List<String> sources, Params use, Params model, Params texture, String lore, Params raw) {
        this(id, name, type, attack, armorSlot, armorSet, rarity, levelReq, requires, classes, stats, setBonus, aura,
                weaponSkills, floor, pool, sources, use, model, texture, lore, raw, null);
    }

    /**
     * 요구 능력치 없이 만든다 ({@link StatRequirement#NONE}) — 시험·도구용. 요구치가 필요하면 {@link #withRequires}.
     * attack 이 null 인 무기는 raw 의 attack 블록을 읽는다.
     */
    public ItemDef(String id, String name, ItemType type, WeaponAttack attack, String armorSlot, String armorSet,
                   Rarity rarity, int levelReq, List<String> classes, Map<String, Range> stats, String setBonus,
                   String aura, List<WeaponSkillDef> weaponSkills, int floor, boolean pool, List<String> sources,
                   Params use, Params model, Params texture, String lore, Params raw) {
        this(id, name, type, attack, armorSlot, armorSet, rarity, levelReq, StatRequirement.NONE, classes, stats,
                setBonus, aura, weaponSkills, floor, pool, sources, use, model, texture, lore, raw);
    }

    public boolean isWeapon() { return type == ItemType.WEAPON; }
    public boolean isGear() { return type.isGear(); }
    public boolean isShield() { return "offhand".equals(armorSlot); }

    /** 활처럼 당겨 쏘는 무기 ({@code attack.style: ranged}). */
    public boolean isRanged() { return attack != null && attack.ranged(); }

    /**
     * 착용 요구 능력치 — 무기·방어구(방패 포함)만. 장신구·재료·소모품은 언제나 요구 없음
     * (items.yml 에 적혀 있어도 무시 — ContentValidator 가 경고).
     */
    public StatRequirement requirement() {
        return (type == ItemType.WEAPON || type == ItemType.ARMOR) && requires != null ? requires : StatRequirement.NONE;
    }

    /** 요구 능력치만 바꾼 사본 (시험·도구용). */
    public ItemDef withRequires(StatRequirement r) {
        return new ItemDef(id, name, type, attack, armorSlot, armorSet, rarity, levelReq, r == null ? StatRequirement.NONE : r,
                classes, stats, setBonus, aura, weaponSkills, floor, pool, sources, use, model, texture, lore, raw, unique);
    }

    /** 직업 제한 없음 — 어느 직업이든(직업 없음 포함) 모든 장비를 쓴다 (GDD §4.4). */
    public boolean usableBy(String classId) { return true; }

    /**
     * 그 직업에 어울리는 장비인가 ({@code classes} = 추천 직업, 비우면 모두). 착용 제한이 아니고 대장간 필터도 없다(없어짐) —
     * 드롭 직업 편향(loot.yml settings.own_class_bias)에만 쓴다.
     * 툴팁·대장간에는 표시하지 않는다.
     */
    public boolean suitedFor(String classId) {
        return classes.isEmpty() || (classId != null && classes.contains(classId));
    }

    /** 고유 효과가 있는 무기인가. */
    public boolean hasUnique() { return unique != null; }

    public WeaponSkillDef weaponSkill(String input) {
        for (WeaponSkillDef s : weaponSkills) if (s.input().equalsIgnoreCase(input)) return s;
        return null;
    }
}
