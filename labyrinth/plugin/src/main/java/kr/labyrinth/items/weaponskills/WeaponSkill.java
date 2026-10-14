package kr.labyrinth.items.weaponskills;

/**
 * 무기 스킬 구현 하나 (GDD §17.2 의 17개 id 중 하나). 무기마다 params·fx·이름만 바꿔 재사용한다.
 * 마나·쿨다운·침묵 확인은 서비스가 끝낸 뒤 호출된다. 지속형은 {@link SkillCast#repeat} 로 틱 작업을 건다.
 */
@FunctionalInterface
public interface WeaponSkill {
    void cast(SkillCast c);
}
