package kr.augsky.skill;

import org.bukkit.Location;
import org.bukkit.entity.LivingEntity;

/** 스킬이 맞힌 대상 하나에게 적용하는 효과 (피해, 화상, 넉백 ...). origin 은 넉백 기준점. */
@FunctionalInterface
public interface HitEffect {
    void apply(SkillContext ctx, LivingEntity target, Location origin);
}
