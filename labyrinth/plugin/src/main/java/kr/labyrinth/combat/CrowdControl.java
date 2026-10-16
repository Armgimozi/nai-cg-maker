package kr.labyrinth.combat;

import java.util.Set;

/**
 * 플레이어가 받는 밀쳐내기·발 묶기 줄이기 (look_spec §1.3 판금 버팀, 순수 — 단위 테스트 대상).
 * 보스가 민 것·건 것은 그대로다 — 보스 싸움의 짜임을 깨지 않으려고 (툴팁 '(보스 제외)').
 */
public final class CrowdControl {

    /** 버팀이 줄이는 상태이상 (기절·속박·빙결). */
    public static final Set<String> HARD = Set.of("stun", "root", "frozen");

    private CrowdControl() {}

    /** 상태이상 시간: 보스가 건 것이면 그대로, 아니면 × (1 − ccResist). */
    public static double duration(double baseSeconds, double ccResist, boolean fromBoss) {
        if (fromBoss || !(ccResist > 0)) return baseSeconds;
        return baseSeconds * (1.0 - Math.min(0.95, ccResist));
    }

    /** 밀려나는 세기: 보스가 민 것이면 그대로, 아니면 × (1 − 저항). */
    public static double knockback(double strength, double resist, boolean fromBoss) {
        if (fromBoss || !(resist > 0)) return strength;
        return strength * (1.0 - Math.min(1.0, resist));
    }
}
