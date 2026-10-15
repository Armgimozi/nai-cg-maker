package kr.labyrinth.dungeon.traps;

/** 함정 수치 공식 (순수 — 단위 테스트 대상, GDD §5.5). 파티 인원은 쓰지 않는다. */
public final class TrapMath {

    private TrapMath() {}

    /** 피해 상한 (최대 HP 비율). */
    public static final double MAX_PCT = 0.5;

    /** 층·난이도 피해 배율 = (1 + 3% × (층−1)) × 난이도 damage. */
    public static double damageScale(int floor, double difficultyDamage) {
        return (1 + 0.03 * (Math.max(1, floor) - 1)) * Math.max(0.1, difficultyDamage);
    }

    /** 한 번 맞을 때 최대 HP 비율 TRUE 피해. */
    public static double pct(TrapType t, int floor, double difficultyDamage) {
        return Math.min(MAX_PCT, t.basePct() * damageScale(floor, difficultyDamage));
    }

    /** 경고 틱 = 기본 × 난이도 telegraph (쉬움 1.3 … 악몽 0.7), 최소 2. */
    public static int telegraphTicks(int base, double telegraphMult) {
        if (base <= 0) return 0;
        return Math.max(2, (int) Math.round(base * Math.max(0.3, telegraphMult)));
    }

    /** 해제에 웅크리고 있어야 하는 틱 (그림자는 shadowSeconds). */
    public static int disarmTicks(boolean shadow, double seconds, double shadowSeconds) {
        return Math.max(2, (int) Math.round((shadow ? shadowSeconds : seconds) * 20));
    }

    /** 해제 보상 골드 = 기준 × 층 × 골드 배율. */
    public static long disarmGold(int floor, int base, double goldMult) {
        return Math.max(1, Math.round(base * Math.max(1, floor) * Math.max(0, goldMult)));
    }

    /**
     * 물살이 밀어낼 쪽 (복도 방향 along 축 위 +1 / −1) = 들어온 쪽. entry = 들어오기 직전 자리를 함정 가운데 기준 along 축에
     * 투영한 값 (기록 없으면 NaN), facing = 바라보는 방향의 along 축 성분 — 기록이 없으면 바라보는 반대쪽에서 왔다고 본다. 둘 다 0 이면 +1.
     */
    public static int pushSide(double entry, double facing) {
        if (entry > 1e-3) return 1;
        if (entry < -1e-3) return -1;
        return facing > 1e-3 ? -1 : 1;
    }

    /** 주기 함정의 현재 박자: 0 = 쉼, 1 = 경고, 2 = 발동. cycle 틱 주기의 끝 burst 틱이 발동, 그 앞 warn 틱이 경고. */
    public static int beat(long t, int phase, int cycle, int warn, int burst) {
        int local = (int) Math.floorMod(t + phase, (long) cycle);
        if (local >= cycle - burst) return 2;
        if (local >= cycle - burst - warn) return 1;
        return 0;
    }
}
