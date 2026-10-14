package kr.labyrinth.content;

import java.util.List;

/** mobs.yml 의 일반 몹/엘리트/소환물. */
public record MobDef(
        String id,
        String name,
        String description,
        int floor,
        String rank,
        String base,
        double scale,
        double hp,
        double damage,
        double defense,
        double speed,
        double xp,
        IntRange gold,
        String ai,
        List<MobSkillDef> skills,
        String drops,
        boolean flying,
        Params sounds,
        ModelDef model,
        Params raw) {

    /** type = GDD §9.1 닫힌 목록. cooldown 0 = 패시브. */
    public record MobSkillDef(String type, double cooldown, Params params) {}

    public boolean isElite() { return "elite".equals(rank); }
    public boolean isAdd() { return "add".equals(rank); }
}
