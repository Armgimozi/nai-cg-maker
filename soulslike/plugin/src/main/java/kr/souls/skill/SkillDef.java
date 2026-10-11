package kr.souls.skill;

import kr.souls.Lang;
import net.kyori.adventure.text.Component;

import java.util.List;

/**
 * skills.yml 한 항목. cooldown 은 초 단위. 이름과 설명은 콘텐츠에 쓰지 않고 lang 열쇠 skill.&lt;id&gt;.name, skill.&lt;id&gt;.desc
 * 에 둔다 (10.3, 12.5: 영어판도 같은 열쇠).
 */
public record SkillDef(String id, double cooldown, List<Mechanic> mechanics) {
    public void cast(SkillContext ctx) {
        Mechanics.runAll(mechanics, ctx);
    }

    public Component name() {
        return Lang.c("skill." + id + ".name"); // lang-dyn: skill.*.name
    }

    public List<Component> description() {
        return Lang.lines("skill." + id + ".desc"); // lang-dyn: skill.*.desc
    }
}
