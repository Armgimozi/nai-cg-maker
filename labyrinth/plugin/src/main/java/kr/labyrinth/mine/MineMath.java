package kr.labyrinth.mine;

import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.ToolSpec;

/**
 * 캐는 시간 ↔ 곡괭이 Tool 규칙 speed (순수, 계약 §2.3 · mine.json rules.seconds).
 * <p>
 * 바닐라: 맞는 도구(correct_for_drops = TRUE)로 땅 위에서 캘 때 한 틱 진행 = speed ÷ 단단함 ÷ 30, 진행 1 이면 부서짐.
 * 그래서 초 s 를 원하면 speed = 30·단단함 ÷ (20·s). 블록을 바꿔도(단단함이 달라도) 초는 그대로다.
 * 초 = 광석(또는 보석 노드) base_seconds ÷ 곡괭이 speed[광석 tier]. 어떤 조합도 {@link #MIN_SECONDS} 보다 빠르지 않다.
 */
public final class MineMath {

    private MineMath() {}

    /** 가장 빠른 캐기 (계약 rules.min_seconds). */
    public static final double MIN_SECONDS = 1.0;

    /** 바닐라 진행 나눗수 (맞는 도구). */
    static final double CORRECT_DIVISOR = 30.0;

    /**
     * 캐는 초 → Tool 규칙 speed. 진행이 틱 경계에서 한 틱 늦어지지 않게 아주 조금(1e-4) 올린다 (float 오차).
     * 단단함이 0 이하(바로 부서지는 블록)면 0.
     */
    public static float toolSpeed(double hardness, double seconds) {
        if (!(hardness > 0) || !(seconds > 0)) return 0f;
        double s = Math.max(MIN_SECONDS, seconds);
        return (float) (CORRECT_DIVISOR * hardness / (20.0 * s) * 1.0001);
    }

    /** speed 로 그 블록을 캐는 틱 수 (바닐라와 같은 셈: 진행이 1 이 되는 첫 틱). */
    public static int ticks(double hardness, double speed) {
        if (!(hardness > 0)) return 0;
        if (!(speed > 0)) return Integer.MAX_VALUE;
        double perTick = speed / hardness / CORRECT_DIVISOR;
        int t = 0;
        float progress = 0f;
        while (progress < 1.0f && t < 100_000) {
            progress += (float) perTick;
            t++;
        }
        return t;
    }

    /** 곡괭이로 광석·보석 하나를 캐는 초 (못 캐면 +∞). 계약 표 §3.4. */
    public static double seconds(MineDef.Node node, ToolSpec tool) {
        if (node == null || tool == null) return Double.POSITIVE_INFINITY;
        return Math.max(MIN_SECONDS, tool.seconds(node.baseSeconds(), node.tier()));
    }

    /** 곡괭이 덤 굴림: 광석 1 + (덤 확률이면 +1) — 보석 노드는 덤 없음. */
    public static int baseYield(boolean gemNode, double bonusChance, double roll) {
        if (gemNode) return 1;
        return roll < bonusChance ? 2 : 1;
    }
}
