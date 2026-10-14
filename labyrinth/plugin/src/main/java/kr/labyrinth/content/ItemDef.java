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

    /** classes 가 비어 있으면 모두 사용 가능. */
    public boolean usableBy(String classId) {
        return classes.isEmpty() || (classId != null && classes.contains(classId));
    }

    public WeaponSkillDef weaponSkill(String input) {
        for (WeaponSkillDef s : weaponSkills) if (s.input().equalsIgnoreCase(input)) return s;
        return null;
    }
}
