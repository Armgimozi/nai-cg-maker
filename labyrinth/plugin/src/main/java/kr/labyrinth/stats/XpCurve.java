package kr.labyrinth.stats;

import kr.labyrinth.core.Settings;

/** 경험치 곡선 (GDD §16.1): 다음 레벨까지 필요 경험치(L) = round(a × L^exp + b). */
public record XpCurve(int maxLevel, double a, double exp, double b) {

    public static final XpCurve DEFAULT = new XpCurve(50, 40, 1.6, 60);

    public static XpCurve of(Settings.Level l) {
        return new XpCurve(l.max(), l.xpA(), l.xpExp(), l.xpB());
    }

    /** level → level+1 필요량. 최대 레벨이면 0. */
    public long xpToNext(int level) {
        if (level >= maxLevel || level < 1) return 0;
        return Math.round(a * Math.pow(level, exp) + b);
    }

    /** 1레벨 0xp 부터 level 레벨 0xp 까지 누적 필요량. */
    public long totalTo(int level) {
        long sum = 0;
        for (int l = 1; l < Math.min(level, maxLevel); l++) sum += xpToNext(l);
        if (level > maxLevel) return totalTo(maxLevel);
        return sum;
    }

    /** 현재 레벨/경험치에 xp 를 더한 결과 [newLevel, newXp]. 최대 레벨에서는 xp 0. */
    public long[] apply(int level, long xp, long gained) {
        int lv = Math.max(1, Math.min(level, maxLevel));
        long cur = Math.max(0, xp) + Math.max(0, gained);
        while (lv < maxLevel) {
            long need = xpToNext(lv);
            if (cur < need) break;
            cur -= need;
            lv++;
        }
        if (lv >= maxLevel) cur = 0;
        return new long[] {lv, cur};
    }
}
