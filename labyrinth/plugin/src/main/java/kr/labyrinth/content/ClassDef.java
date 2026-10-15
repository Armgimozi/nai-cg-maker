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
        List<String> weaponTypes,   // 추천 무기 종류 (착용·스킬 제한 아님)
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

    /**
     * 직업 스킬 배율 (classes.yml {@code skill_scale}, 0.3.5) — 직업 스킬 피해 = 스킬 위력 × skill_scale × 스킬 배율.
     * 무기가 무엇이든 같다 (스킬 위력이 무기 무게와 상관없음). 키가 없으면(직접 고친 예전 classes.yml) 직업 id 의 0.3.5 기본값,
     * 모르는 직업은 1.
     */
    public double skillScale() {
        double def = DEFAULT_SKILL_SCALE.getOrDefault(id, 1.0);
        double v = raw == null ? def : raw.dbl("skill_scale", def);
        return v > 0 ? v : def;
    }

    /** 0.3.5 기본 직업 스킬 배율 (= jar 의 classes.yml). 옛 추천 무기 배율을 직업으로 옮김 (시전 ÷1.05), 그림자 0.62 → 0.70. */
    public static final Map<String, Double> DEFAULT_SKILL_SCALE = Map.of("guardian", 1.00, "berserker", 1.55, "hunter", 1.55,
            "arcanist", 1.05, "priest", 0.90, "shadow", 0.70);

    public SkillDef skillByInput(String input) {
        for (SkillDef s : skills) if (s.input().equalsIgnoreCase(input)) return s;
        return null;
    }

    /** 추천 무기 종류인가 ({@code weapon_types}). 직업 스킬은 아무 미궁 무기로나 나가고, 추천 무기면 재사용 대기 −10% ({@link WeaponTypes}). */
    public boolean recommendsWeapon(String weaponType) {
        return weaponType != null && weaponTypes.contains(weaponType);
    }
}
