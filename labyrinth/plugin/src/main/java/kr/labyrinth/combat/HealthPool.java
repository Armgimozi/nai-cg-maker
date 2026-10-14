package kr.labyrinth.combat;

import org.bukkit.entity.LivingEntity;

/**
 * 자체 HP 풀 계약 (ARCHITECTURE §4 combat). 커스텀 몹·보스는 바닐라 체력 대신 이 풀을 쓰고,
 * {@link DamageService} 가 계산을 끝낸 최종 피해를 {@link #applyDamage} 로 넘긴다.
 * 구현(mobs/bosses)은 HP 가 0 이 되면 스스로 사망 처리(보상·이벤트·remove)한다.
 */
public interface HealthPool {

    /** 판정용 바닐라 엔티티 (히트박스). */
    LivingEntity entity();

    double health();

    double maxHealth();

    /** 방어 (받는 피해 ×100/(100+방어)). */
    double defense();

    /** 받는 피해 감소 0~1 (보호막·패턴 중 경직 해제 등 일시 효과 포함). 기본 0. */
    default double damageReduction() { return 0; }

    /** 회피 0~1. 기본 0. */
    default double evasion() { return 0; }

    /** 받는 피해 증가 0~ (vulnerable). 기본 0. */
    default double damageTaken() { return 0; }

    /** 무적(페이즈 전환 연출 등)이면 피해를 받지 않는다. */
    default boolean invulnerable() { return false; }

    /**
     * 최종 피해 적용. ctx 에는 공격자·유형·치명타 여부가 들어 있다(위협 계산·반사 등에 사용).
     * @return 실제로 깎인 HP
     */
    double applyDamage(double amount, DamageContext ctx);

    /** HP 회복. @return 실제 회복량 */
    double heal(double amount);

    boolean isAlive();
}
