package kr.labyrinth.content;

import java.util.ArrayList;
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

    /**
     * 직업 스킬. input = SWAP | SNEAK_SWAP | DROP | SNEAK_DROP.
     * kind = 피해 종류 꼬리표 (classes.yml {@code kind}: physical | magic | hybrid | none, 0.3.5) — 물리는 힘, 마법은 지능이 키운다.
     * 비우면 구현이 쓰는 피해 유형에서 (근접·원거리 = 물리, 마법 = 마법).
     * pvpMult = 플레이어에게 주는 피해 배율 (classes.yml {@code pvp_mult}, 기본 1, 0.1~1.0 — pvp_spec §6: 광역·궁극기).
     */
    public record SkillDef(String id, String name, String input, int unlockLevel, double mana, double cooldown,
                           Params params, String description, String kind, double pvpMult) {

        public SkillDef(String id, String name, String input, int unlockLevel, double mana, double cooldown,
                        Params params, String description, String kind) {
            this(id, name, input, unlockLevel, mana, cooldown, params, description, kind, 1.0);
        }

        public SkillDef(String id, String name, String input, int unlockLevel, double mana, double cooldown,
                        Params params, String description) {
            this(id, name, input, unlockLevel, mana, cooldown, params, description, "", 1.0);
        }
    }

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

    /**
     * 처음 이 직업을 골랐을 때 한 번 주는 무기 (classes.yml {@code starter_weapon}, 0.3.5). 키가 없으면(직접 고친 예전 classes.yml)
     * 직업 id 의 기본값, 모르는 직업은 null (주지 않음).
     */
    public String starterWeapon() {
        String v = raw == null ? null : raw.str("starter_weapon");
        return v != null && !v.isBlank() ? v.trim() : DEFAULT_STARTER_WEAPON.get(id);
    }

    /** 0.3.5 기본 시작 무기 (= jar 의 classes.yml, 0.3.4 에 주던 것 그대로). */
    public static final Map<String, String> DEFAULT_STARTER_WEAPON = Map.of("guardian", "corridor_longsword",
            "berserker", "rootcutter_greatsword", "hunter", "corridor_longbow", "arcanist", "lantern_staff",
            "priest", "acolyte_scepter", "shadow", "moss_dirk");

    /**
     * 주로 쓰는 능력치 (classes.yml {@code main_stats}, 0.3.5) — 직업 메뉴 안내 한 줄에만 쓴다. 키가 없으면 직업 id 의 기본값,
     * 그것도 없으면 주 스탯 하나.
     */
    public List<Stat> mainStats() {
        List<Stat> out = new ArrayList<>();
        if (raw != null) for (String k : raw.strings("main_stats")) {
            Stat s = Stat.byKey(k);
            if (s != null && !out.contains(s)) out.add(s);
        }
        if (out.isEmpty()) out.addAll(DEFAULT_MAIN_STATS.getOrDefault(id, primaryStat == null ? List.of() : List.of(primaryStat)));
        return List.copyOf(out);
    }

    /** 0.3.5 기본 '주로 쓰는 능력치' (combat_spec §6.1 알맞은 분배의 앞 두 능력치). */
    public static final Map<String, List<Stat>> DEFAULT_MAIN_STATS = Map.of("guardian", List.of(Stat.VIT, Stat.STR),
            "berserker", List.of(Stat.STR, Stat.VIT), "hunter", List.of(Stat.DEX, Stat.STR), "arcanist", List.of(Stat.INT, Stat.VIT),
            "priest", List.of(Stat.WIS, Stat.INT), "shadow", List.of(Stat.DEX, Stat.STR));
}
