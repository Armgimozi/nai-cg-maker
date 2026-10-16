package kr.labyrinth.classes;

import java.util.Map;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/**
 * 상태이상·버프 (GDD §9.2 의 14종 + §11.7 버프 키). 플레이어·커스텀 몹·보스 공통 (PvP 에서도 플레이어끼리 그대로 쓴다).
 * 소유: classes 담당. 기본 구현 {@link NoopStatusEffectService}, 실제 구현 {@link LabyrinthStatusEffectService}.
 * <p>
 * 구현 규칙: 플레이어 버프/디버프의 능력치 변화는 StatContributor 로 StatService 에 보탠다
 * (버프 키 "damage" → StatBlock "damage_mult", weaken → 음수 damage_mult, vulnerable·mark → "damage_taken").
 * 커스텀 몹·보스의 weaken/vulnerable/mark 는 구현이 {@code DamageService.Hook} 으로 피해에 직접 곱한다 —
 * mobs/bosses 의 {@code HealthPool.damageTaken()} 에 다시 더하지 말 것(이중 적용).
 * WIS 의 해로운 효과 지속시간 감소(DerivedStats.debuffReduction)는 stun 을 제외하고 적용.
 * <p>
 * 이동 제한(slow/root/stun/빙결)은 구현이 MOVEMENT_SPEED·JUMP_STRENGTH 속성 수정치로 직접 건다(바닐라 AI 도 멈춤).
 * <b>mobs/bosses 의 AI·스킬·패턴 시작 전에 {@link #isStunned}(행동 불가)를 확인</b>하고, 시전 끊기 가능한 패턴은
 * {@code has(entity, "interrupt")} 를 확인해 취소할 것. 은신한 플레이어({@link #isStealthed})는 대상으로 고르지 않는다.
 * 보스는 기본적으로 stun/root/frozen 면역 (스킬의 boss_* 대체 값 규칙, GDD §4.1).
 */
public interface StatusEffectService {

    /**
     * 상태이상 부여. effectId = poison | bleed | burn | slow | root | stun | weaken | vulnerable | blind | silence |
     * frost | infection | knockback | damage (GDD §9.2) + 확장: venom(중첩 독, 그림자 독날) | mark(사냥꾼 표식: 받는 피해 +)
     * | cooldown_slow(스킬 쿨다운 감속 비율) | interrupt(보스 시전 끊기 신호, 짧게).
     * @param potency 효과별 세기: slow/weaken/vulnerable/mark/cooldown_slow = 비율(0~1),
     *                poison/bleed/burn/venom = 초당 기준 피해 배율(0~1 — 시전자 공격력 또는 몹 damage 에 곱함,
     *                0 이하나 1 이상이면 효과별 기본값 poison/bleed 0.15·burn 0.2 사용), frost/infection = 추가 중첩 수,
     *                knockback = 세기, damage = 기준 피해 배율
     * @param source  시전자 (지속 피해의 기준 피해·위협 대상). null 가능
     */
    void apply(LivingEntity target, String effectId, double durationSeconds, double potency, LivingEntity source);

    boolean has(LivingEntity target, String effectId);

    /** 중첩 수 (frost/infection/venom). 없으면 0. */
    int stacks(LivingEntity target, String effectId);

    void clear(LivingEntity target, String effectId);

    /** 정화: 정화 가능한 해로운 효과 전부 제거 (stun 제외, 중첩 포함). */
    void cleanse(LivingEntity target);

    /** 버프 (키 = §11.7 버프 키 → 비율). sourceId 가 같으면 갱신, 다르면 합산. */
    void applyBuff(Player player, Map<String, Double> buff, double durationSeconds, String sourceId);

    /** 행동 불가 (stun/빙결). */
    default boolean isStunned(LivingEntity e) { return has(e, "stun") || has(e, "frozen"); }

    /** 스킬 사용 불가. */
    default boolean isSilenced(LivingEntity e) { return has(e, "silence") || isStunned(e); }

    default boolean isRooted(LivingEntity e) { return has(e, "root") || isStunned(e); }

    // ── 확장 (classes 담당 추가, 기본 구현은 효과 없음) ─────────────────────

    /** 버프 제거. */
    default void removeBuff(Player player, String sourceId) {}

    /** 해당 출처 버프가 걸려 있는가. */
    default boolean hasBuff(Player player, String sourceId) { return false; }

    /** 보호막 부여 (커스텀 HP 단위). 같은 sourceId 는 큰 값으로 갱신. 몹·보스에도 가능. */
    default void addShield(LivingEntity target, double amount, double durationSeconds, String sourceId) {}

    /** 현재 보호막 총량. */
    default double shield(LivingEntity target) { return 0; }

    /** 은신 (몹이 대상으로 고르지 않음, 첫 공격 피해 +firstHitBonus 후 해제). */
    default void stealth(Player player, double seconds, double firstHitBonus) {}

    default boolean isStealthed(LivingEntity e) { return false; }

    default void breakStealth(LivingEntity e) {}

    /** 넉백 면역 (수호기사 불굴의 성채 등). 보스 패턴의 밀쳐내기는 이걸 확인하거나 apply(…"knockback"…) 을 쓸 것. */
    default boolean isKnockbackImmune(LivingEntity e) { return false; }

    /** 직업·무기 스킬 쿨다운이 흐르는 속도 (1 = 정상, cooldown_slow 0.3 이면 0.7). */
    default double cooldownRate(LivingEntity e) { return 1.0; }

    /**
     * 중첩 지속 피해 (고유 효과 찢는 치명의 출혈 · 원소 부여의 독, unique_spec): 중첩당 초당 perStack (커스텀 HP 단위, 부르는 쪽이 계산),
     * 중첩 += addStacks (상한 maxStacks). 일반 bleed/poison 과 따로 쌓이고 {@code has("bleed")}·{@code has("poison")} 에 함께 잡힌다.
     * 기본 구현은 일반 효과로 건다.
     */
    default void applyStacks(LivingEntity target, String effectId, double durationSeconds, double perStack, int addStacks,
                             int maxStacks, LivingEntity source) {
        apply(target, effectId, durationSeconds, 0, source);
    }

    /**
     * 서리 중첩 (고유 효과 원소 부여): 5중첩이면 빙결 freezeSeconds (무기 스킬·몹이 건 서리는 그대로 4초).
     * 보스는 빙결 대신 받는 피해 +bossVulnerable 3초 (0 이면 아무것도 안 함).
     */
    default void applyFrost(LivingEntity target, int stacks, double freezeSeconds, double bossVulnerable, LivingEntity source) {
        apply(target, "frost", 6, Math.max(1, stacks), source);
    }

    /** 사망·인스턴스 종료 등: 버프·디버프·보호막 전부 제거. */
    default void clearAll(LivingEntity e) { cleanse(e); }
}
