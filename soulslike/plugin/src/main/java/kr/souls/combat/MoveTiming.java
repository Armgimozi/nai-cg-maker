package kr.souls.combat;

import java.util.List;

/**
 * 공격 속도 (민첩, 3.6) 의 틱 셈. 순수 함수만 둔다 (13.1 의 MoveTimingTest, 가짜 시계 없이).
 * <ul>
 *   <li>a = 1 + 민첩 속도 (DamageCalc.attackSpeed). 모든 무기에 같다 (DECISIONS 2026-10-10).</li>
 *   <li>준비 = max(min-startup, round(준비 / a)). 0.5 는 올린다 (민첩 36 의 단도 3 / 1.2 = 2.5 → 3, 민첩 37 부터 2).</li>
 *   <li>판정 틱은 그대로.</li>
 *   <li>회복 = max(min-recovery, 회복 / a). 소수 몫은 사람마다 모아 둔다: 늘 올린 틱으로 하고, 올려서 더 쓴 몫이 1틱 차면 그 동작에서
 *       한 틱 줄인다 (짧은 동작에서도 평균이 맞는다. 직검 7 / 1.22 = 5.74 → 6, 6, 6, 5, …).</li>
 *   <li>한 동작 (준비 + 판정 + 회복) 은 min-cycle (10) 밑으로 가지 않는다 (허공 휘두르기는 10틱에 한 번만 온다, 2.3 의 2): 모자란 몫은
 *       회복에 되돌린다. 그래서 단도 약공격은 준비만 짧아진다 (3/1/6 → 2/1/7).</li>
 *   <li>최소값에 걸려 늘린 동작은 모아 둔 몫을 쓰지 않고 비운다 (다음 동작이 그만큼 빨라지지 않게).</li>
 * </ul>
 * 아이템의 휘두르는 길이 (swing_animation, R13) 는 {@link #lockTicks}: 민첩 단계 (combat.moves.swing-tiers) 의 가장 빠른 민첩으로 셈한
 * 가장 짧은 약공격 한 주기의 두 배 − swing-margin (2026-10-11 휘두름 잠금. 그 전에는 준비 + 판정, 다음에는 약공격 1단 한 주기였다).
 */
public final class MoveTiming {
    /** moves.yml 의 바탕 틱 (민첩 10). */
    public record Base(int s, int a, int r) {
        public int cycle() {
            return s + a + r;
        }
    }

    /** 민첩으로 나눈 틱과 남은 몫 (다음 동작에 넘긴다). */
    public record Timed(int s, int a, int r, double carry) {
        public int cycle() {
            return s + a + r;
        }
    }

    /** 최소값 (combat.moves.min-startup, min-recovery, min-light-cycle). */
    public record Rules(int minStartup, int minRecovery, int minCycle) {
        public static final Rules DEFAULT = new Rules(2, 4, 10);
    }

    private static final double EPS = 1e-9;

    private MoveTiming() {}

    /** 준비 틱: max(min, round(s / a)). */
    public static int startup(int s, double a, int min) {
        double v = s / safe(a);
        return Math.max(min, (int) Math.floor(v + 0.5 + EPS));
    }

    /**
     * 한 동작의 틱. carry 는 그 사람이 모아 둔 몫 (0 이상 1 미만, 처음은 0), 돌려준 Timed.carry 를 다음 동작에 넘긴다.
     */
    public static Timed time(Base b, double a, double carry, Rules rules) {
        a = safe(a);
        int s = startup(b.s(), a, rules.minStartup());
        int act = Math.max(0, b.a());
        double raw = b.r() / a;
        int r = (int) Math.ceil(raw - EPS);
        double saved = Math.max(0, carry) + (r - raw);
        if (saved >= 1 - EPS && r - 1 >= rules.minRecovery()) {
            r -= 1;
            saved -= 1;
        }
        if (r < rules.minRecovery()) {
            r = rules.minRecovery();
            saved = 0;
        }
        if (s + act + r < rules.minCycle()) {
            r = rules.minCycle() - s - act;
            saved = 0;
        }
        return new Timed(s, act, r, Math.max(0, Math.min(1 - EPS, saved)));
    }

    /** 민첩으로 나눈 준비 + 판정 (1 이상). 2026-10-11 부터 아이템의 휘두르는 길이는 {@link #lockTicks} 다. */
    public static int swingTicks(int s, int act, double a, int minStartup) {
        return Math.max(1, startup(s, a, minStartup) + Math.max(0, act));
    }

    /**
     * 아이템의 휘두르는 길이 D (틱, 2026-10-11 "휘두름 잠금"): D = 2 × Cmin − margin (2 이상).
     * Cmin 은 약공격 단들 (lights) 의 가장 짧은 한 주기를 배율 aFast (그 민첩 단계의 가장 빠른 민첩) 로 셈한 것:
     * max(min-cycle, min_i(준비_i + 판정_i + max(min-recovery, floor(회복_i / aFast)))). 회복은 모아 둔 몫 ({@link #time}) 으로 한 틱
     * 짧아질 수 있어 내림으로 본다.
     * 바닐라 클라이언트는 휘두름이 반 (D/2, 내림: margin 3 이면 Cmin − 2) 지나야 클릭으로 팔을 다시 휘두른다. 그래서 공격 한 주기 안에
     * 더 누른 클릭은 팔을 다시 휘두르지 않고 (입력 기억에만 든다), 서버가 다음 동작의 시작에 휘두른 것 (Swings.main) 은 받아들여진다.
     * margin 2 면 서버의 같은 규칙 (now − last ≥ D/2 + 1 = Cmin) 이 가장 짧은 주기에서도 맞는다. 기본 3 (combat.moves.swing-margin,
     * 2026-10-11 검토): D/2 + 1 = Cmin − 1 이라 가장 짧은 주기에서도 서버와 클라이언트 (서버 휘두름 패킷이 닿은 클라이언트 틱으로 센다)
     * 모두 한 틱이 남는다. 2 면 패킷이 몇 ms 만 일찍 닿아도 클라이언트가 그 내려치기를 버린다 (다른 사람에게는 팔이 보이지 않는다).
     */
    public static int lockTicks(List<Base> lights, double aFast, Rules r, int margin) {
        double a = safe(aFast);
        int c = Integer.MAX_VALUE;
        if (lights != null) {
            for (Base b : lights) {
                int rec = Math.max(r.minRecovery(), (int) Math.floor(b.r() / a + EPS));
                c = Math.min(c, startup(b.s(), a, r.minStartup()) + Math.max(0, b.a()) + rec);
            }
        }
        if (c == Integer.MAX_VALUE) c = r.minCycle();
        c = Math.max(r.minCycle(), c);
        return Math.max(2, 2 * c - margin);
    }

    /** 단계 tier 의 가장 빠른 민첩: 다음 단계의 첫 값 − 1, 끝 단계면 99 (휘두름 잠금 {@link #lockTicks} 의 aFast). */
    public static int fastestDex(int tier, List<Integer> steps) {
        if (steps == null || steps.isEmpty()) return 99;
        int t = Math.max(0, Math.min(steps.size() - 1, tier));
        return t + 1 < steps.size() ? Math.max(steps.get(t), steps.get(t + 1) - 1) : 99;
    }

    /** 민첩 dex 의 단계: steps 가운데 dex 이하인 마지막 것의 번호 (첫 값보다 작으면 0). */
    public static int tier(int dex, List<Integer> steps) {
        int t = 0;
        if (steps == null) return 0;
        for (int i = 0; i < steps.size(); i++) if (dex >= steps.get(i)) t = i;
        return t;
    }

    /** 단계 tier 의 첫 민첩 값 (그 단계의 길이를 이 값으로 셈한다). */
    public static int tierDex(int tier, List<Integer> steps) {
        if (steps == null || steps.isEmpty()) return 10;
        return steps.get(Math.max(0, Math.min(steps.size() - 1, tier)));
    }

    private static double safe(double a) {
        return a > 0 && !Double.isInfinite(a) && !Double.isNaN(a) ? a : 1;
    }
}
