package kr.souls.skill;

import java.util.List;

/** skills.yml 한 항목. cooldown 은 초 단위. */
public record SkillDef(String id, String name, List<String> description, double cooldown, List<Mechanic> mechanics) {
    public void cast(SkillContext ctx) {
        Mechanics.runAll(mechanics, ctx);
    }
}
