package kr.augsky.skill;

import java.util.List;

/** skills.yml 한 항목. cooldown 은 초 단위. */
public record SkillDef(String id, String name, List<String> description, double cooldown, List<Mechanic> mechanics) {
    public void cast(SkillContext ctx) {
        // 무기 등급·속성(몬스터면 몬스터 종류)에 맞춘 연출을 고른다. 피해·타이밍은 건드리지 않는다
        if (ctx.fx == null && ctx.plugin.vfx() != null) ctx.fx = ctx.plugin.vfx().begin(ctx, this);
        Mechanics.runAll(mechanics, ctx);
    }
}
