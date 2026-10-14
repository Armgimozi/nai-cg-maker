package kr.labyrinth.classes.skills;

/**
 * 직업 스킬 구현 하나 (classes.yml skills[].id 가 키). 수치는 전부 {@link SkillContext#params()} 에서 읽는다
 * (GDD §4.1 파라미터 규칙). 마나·쿨다운·침묵·레벨 검사는 ClassService 가 끝낸 뒤 호출된다.
 */
public interface Skill {

    /** classes.yml 의 스킬 id. */
    String id();

    /**
     * 시전. @return 성공(마나·쿨다운 소모)이면 true. 대상이 없는 등으로 실패하면 {@link SkillContext#fail} 로 이유를 남기고 false.
     */
    boolean cast(SkillContext ctx);
}
