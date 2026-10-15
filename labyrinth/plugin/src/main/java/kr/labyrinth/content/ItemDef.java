package kr.labyrinth.content;

import java.util.List;
import java.util.Map;

/**
 * items.yml 의 아이템 하나. stats 는 [최소, 최대] 굴림 범위(GDD §11.7 키).
 * <p>
 * {@code levelReq} (items.yml level_req): 장비는 <b>숨은 내부 레벨</b> — 정렬·강화 골드·드롭 단계에만 쓰고 표시·착용 제한은 없다.
 * 소모품은 그대로 사용 레벨. 장비 착용 조건은 {@code requires}(요구 능력치, {@link #requirement()}).
 */
public record ItemDef(
        String id,
        String name,
        ItemType type,
        String weaponType,
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
        Params raw) {

    /** 무기 스킬. input = LEFT | RIGHT | SNEAK_LEFT | SNEAK_RIGHT. */
    public record WeaponSkillDef(String id, String name, String input, double cooldown, double mana, Params params,
                                 String description) {}

    public boolean isWeapon() { return type == ItemType.WEAPON; }
    public boolean isGear() { return type.isGear(); }
    public boolean isShield() { return "offhand".equals(armorSlot); }

    /**
     * 착용 요구 능력치 — 무기·방어구(방패 포함)만. 장신구·재료·소모품은 언제나 요구 없음
     * (items.yml 에 적혀 있어도 무시 — ContentValidator 가 경고).
     */
    public StatRequirement requirement() {
        return (type == ItemType.WEAPON || type == ItemType.ARMOR) && requires != null ? requires : StatRequirement.NONE;
    }

    /** 요구 능력치만 바꾼 사본 (시험·도구용). */
    public ItemDef withRequires(StatRequirement r) {
        return new ItemDef(id, name, type, weaponType, armorSlot, armorSet, rarity, levelReq, r == null ? StatRequirement.NONE : r,
                classes, stats, setBonus, aura, weaponSkills, floor, pool, sources, use, model, texture, lore, raw);
    }

    /** 직업 제한 없음 — 어느 직업이든(직업 없음 포함) 모든 장비를 쓴다 (GDD §4.4). */
    public boolean usableBy(String classId) { return true; }

    /**
     * 그 직업에 어울리는 장비인가 ({@code classes} = 추천 직업, 비우면 모두). 착용 제한이 아니고 대장간 필터도 없다(없어짐) —
     * 드롭 직업 편향(loot.yml settings.own_class_bias)에만 쓴다 (+ 처음 전직할 때 줄 시작 무기 고르기 {@link WeaponTypes#starterWeapon}).
     * 툴팁·대장간에는 표시하지 않는다.
     */
    public boolean suitedFor(String classId) {
        return classes.isEmpty() || (classId != null && classes.contains(classId));
    }

    public WeaponSkillDef weaponSkill(String input) {
        for (WeaponSkillDef s : weaponSkills) if (s.input().equalsIgnoreCase(input)) return s;
        return null;
    }
}
