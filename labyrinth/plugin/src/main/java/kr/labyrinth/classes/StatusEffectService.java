package kr.labyrinth.classes;

import java.util.Map;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/**
 * 상태이상·버프 (GDD §9.2 의 14종 + §11.7 버프 키). 플레이어·커스텀 몹 공통. 소유: classes 담당.
 * 기본 구현 {@link NoopStatusEffectService}.
 * <p>
 * 구현 규칙: 플레이어 버프/디버프의 능력치 변화는 StatContributor 로 StatService 에 보탠다
 * (버프 키 "damage" → StatBlock "damage_mult", weaken → 음수 damage_mult, vulnerable → "damage_taken").
 * WIS 의 해로운 효과 지속시간 감소(DerivedStats.debuffReduction)는 stun 을 제외하고 적용.
 */
public interface StatusEffectService {

    /**
     * 상태이상 부여. effectId = poison | bleed | burn | slow | root | stun | weaken | vulnerable | blind | silence |
     * frost | infection | knockback | damage.
     * @param potency 효과별 amount (지속 피해 배율, 둔화 비율, 중첩 수 등)
     * @param source  시전자 (지속 피해의 기준 피해·위협 대상). null 가능
     */
    void apply(LivingEntity target, String effectId, double durationSeconds, double potency, LivingEntity source);

    boolean has(LivingEntity target, String effectId);

    /** 중첩 수 (frost/infection). 없으면 0. */
    int stacks(LivingEntity target, String effectId);

    void clear(LivingEntity target, String effectId);

    /** 정화: 정화 가능한 해로운 효과 전부 제거. */
    void cleanse(LivingEntity target);

    /** 버프 (키 = §11.7 버프 키 → 비율). sourceId 가 같으면 갱신. */
    void applyBuff(Player player, Map<String, Double> buff, double durationSeconds, String sourceId);

    /** 행동 불가 (stun/빙결). */
    default boolean isStunned(LivingEntity e) { return has(e, "stun"); }

    /** 스킬 사용 불가. */
    default boolean isSilenced(LivingEntity e) { return has(e, "silence") || isStunned(e); }

    default boolean isRooted(LivingEntity e) { return has(e, "root") || isStunned(e); }
}
