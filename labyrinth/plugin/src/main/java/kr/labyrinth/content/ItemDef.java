package kr.labyrinth.content;

import java.util.List;
import java.util.Map;

/** items.yml 의 아이템 하나. stats 는 [최소, 최대] 굴림 범위(GDD §11.7 키). */
public record ItemDef(
        String id,
        String name,
        ItemType type,
        String weaponType,
        String armorSlot,
        String armorSet,
        Rarity rarity,
        int levelReq,
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

    /** 직업 제한 없음 — 어느 직업이든(직업 없음 포함) 모든 장비를 쓴다 (GDD §4.4). */
    public boolean usableBy(String classId) { return true; }

    /**
     * 그 직업에 어울리는 장비인가 ({@code classes} = 추천 직업, 비우면 모두). 착용 제한이 아니라
     * 드롭 직업 편향·대장간 '추천 장비만' 필터·툴팁 "추천 직업" 표시에만 쓴다.
     */
    public boolean suitedFor(String classId) {
        return classes.isEmpty() || (classId != null && classes.contains(classId));
    }

    public WeaponSkillDef weaponSkill(String input) {
        for (WeaponSkillDef s : weaponSkills) if (s.input().equalsIgnoreCase(input)) return s;
        return null;
    }
}
