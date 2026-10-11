package kr.augsky.vfx;

import kr.augsky.skill.SkillContext;

/** 맞을 자리를 미리 알려 줄 수 있는 기술 부품. 판정과 같은 기준점으로 계산해야 한다 (부수효과 없이) */
public interface Telegraphable {
    Footprint footprint(SkillContext ctx);
}
