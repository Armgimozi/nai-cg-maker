package kr.souls.progression;

/**
 * 레벨 비용 (5.3). 레벨 L 에서 L+1 로 가는 비용: L 이 flat-until (11) 이하면 flat-base + flat-per-level × L (300 + 20L),
 * 그 위는 다크 소울 1 의 식 × scale: round(scale × (a x³ + b x² + c x + d)), x = L + 1. 비용은 지금 레벨만 본다 (어느 능력치든 같다).
 * 순수 클래스 (13.1 의 LevelCostTest 가 5.3 의 표를 본다). 값은 config.yml 의 level.cost.*.
 */
public final class LevelCost {
    private final int flatUntil;
    private final double flatBase, flatPerLevel, a, b, c, d, scale;

    public LevelCost(int flatUntil, double flatBase, double flatPerLevel, double[] cubic, double scale) {
        this.flatUntil = flatUntil;
        this.flatBase = flatBase;
        this.flatPerLevel = flatPerLevel;
        this.a = cubic.length > 0 ? cubic[0] : 0;
        this.b = cubic.length > 1 ? cubic[1] : 0;
        this.c = cubic.length > 2 ? cubic[2] : 0;
        this.d = cubic.length > 3 ? cubic[3] : 0;
        this.scale = scale;
    }

    public static LevelCost defaults() {
        return new LevelCost(11, 300, 20, new double[] {0.02, 3.06, 105.6, -895}, 0.6);
    }

    /** 레벨 level 에서 한 레벨 올리는 비용 (0 이상). */
    public long next(int level) {
        int lv = Math.max(1, level);
        if (lv <= flatUntil) return Math.max(0, Math.round(flatBase + flatPerLevel * lv));
        double x = lv + 1;
        return Math.max(0, Math.round(scale * (a * x * x * x + b * x * x + c * x + d)));
    }

    /** 레벨 from 에서 n 레벨을 차례로 올리는 비용의 합 (5.3: 레벨 9 에서 셋 = 480 + 500 + 520). */
    public long sum(int from, int n) {
        long s = 0;
        for (int i = 0; i < n; i++) s += next(from + i);
        return s;
    }
}
