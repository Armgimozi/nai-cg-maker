package kr.labyrinth.content;

import java.util.List;
import java.util.Map;
import kr.labyrinth.stats.Stat;

/** classes.yml 의 직업 하나. */
public record ClassDef(
        String id,
        String name,
        String role,
        String color,
        String description,
        String iconItem,
        List<String> weaponTypes,
        Stat primaryStat,
        Map<Stat, Integer> baseStats,
        double baseHp,
        double baseMp,
        double hpPerLevel,
        double mpPerLevel,
        double manaRegen,
        PassiveDef passive,
        List<SkillDef> skills,
        Params raw) {

    public record PassiveDef(String id, String name, String description, Params params) {}

    /** 직업 스킬. input = SWAP | SNEAK_SWAP | DROP | SNEAK_DROP. */
    public record SkillDef(String id, String name, String input, int unlockLevel, double mana, double cooldown,
                           Params params, String description) {}

    public int baseStat(Stat s) { return baseStats.getOrDefault(s, 0); }

    public SkillDef skillByInput(String input) {
        for (SkillDef s : skills) if (s.input().equalsIgnoreCase(input)) return s;
        return null;
    }

    public boolean canUseWeaponType(String weaponType) {
        return weaponType != null && weaponTypes.contains(weaponType);
    }
}
