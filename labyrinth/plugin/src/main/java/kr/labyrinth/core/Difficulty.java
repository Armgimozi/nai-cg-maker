package kr.labyrinth.core;

/**
 * 서버 난이도 프리셋 (config.yml difficulties, GDD §2.4).
 * hp/damage = 몹·보스 배율, drop = 드롭 확률 배율, xp = 경험치 배율, telegraph = 경고 시간(windup) 배율.
 * <p>
 * 난이도마다 배율 한 벌 — 1층부터 마지막 층까지 같은 값이다(0.3.3, 층 램프 기본값 없음).
 * ramp = 관리자가 config 에 직접 적은 층 램프만 (null = 모든 층 같은 값). hp·damage·telegraph 만 낮은 층에서 완만하게
 * 시작해 {@link Ramp#fullFloor} 층부터 원래 값이 된다. drop·xp(보상)는 1층부터 원래 값. 층의 실제 값은 {@link #atFloor}.
 */
public record Difficulty(String id, String name, double hp, double damage, double drop, double xp, double telegraph, Ramp ramp) {

    // 기본 배율 (= jar 의 config.yml). 어려움·악몽은 밸런스 시뮬레이터로 고른 통합 값 — 악몽 1층 솔로 숙련 클리어율 ≈ 50%
    public static final Difficulty EASY = new Difficulty("easy", "쉬움", 0.7, 0.6, 0.8, 0.8, 1.3);
    public static final Difficulty NORMAL = new Difficulty("normal", "보통", 1.0, 1.0, 1.0, 1.0, 1.0);
    public static final Difficulty HARD = new Difficulty("hard", "어려움", 1.4, 1.3, 1.3, 1.3, 0.9);
    public static final Difficulty NIGHTMARE = new Difficulty("nightmare", "악몽", 1.8, 1.6, 1.8, 1.7, 0.85);

    /** 예전 판(0.3.2)이 config.yml 에 적어 둔 어려움·악몽 값 — 손대지 않은 값이므로 새 기본값으로 올린다 ({@code Settings}). */
    public static final Difficulty LEGACY_HARD_032 = new Difficulty("hard", "어려움", 1.5, 1.4, 1.3, 1.3, 0.85);
    public static final Difficulty LEGACY_NIGHTMARE_032 = new Difficulty("nightmare", "악몽", 2.4, 2.0, 1.8, 1.7, 0.7);

    /** 램프 없는 프리셋 (위 상수·대체 보스 배율·테스트). */
    public Difficulty(String id, String name, double hp, double damage, double drop, double xp, double telegraph) {
        this(id, name, hp, damage, drop, xp, telegraph, null);
    }

    /** 코드 기본 프리셋 (쉬움·보통·어려움·악몽, 그 밖의 id 는 null). */
    public static Difficulty defaultFor(String id) {
        if (id == null) return null;
        return switch (id) {
            case "easy" -> EASY;
            case "normal" -> NORMAL;
            case "hard" -> HARD;
            case "nightmare" -> NIGHTMARE;
            default -> null;
        };
    }

    /** 0.3.2 의 jar 기본 값 (어려움·악몽만, 나머지 null — 쉬움·보통은 그때와 같다). */
    public static Difficulty legacy032(String id) {
        if (id == null) return null;
        return switch (id) {
            case "hard" -> LEGACY_HARD_032;
            case "nightmare" -> LEGACY_NIGHTMARE_032;
            default -> null;
        };
    }

    /**
     * 층 램프: fromFloor 층에서 start* 값으로 시작해 fullFloor 층부터 그 난이도의 원래 값.
     * 층 f 의 값 = start + (원래 − start) × t, t = clamp((f − fromFloor)/(fullFloor − fromFloor), 0, 1).
     * 기본값은 없다 — config 에 직접 적은 램프만 쓴다 (0.3.2 의 기본 램프 그대로면 {@code Settings} 가 지운다).
     */
    public record Ramp(int fromFloor, int fullFloor, double startHp, double startDamage, double startTelegraph) {

        /** 0.3.2 의 jar 기본 램프 (어려움 1→4층 · 악몽 1→6층). 기존 서버 config.yml 에 그대로 남은 것을 알아보는 데만 쓴다. */
        public static final Ramp LEGACY_HARD_032 = new Ramp(1, 4, 1.2, 1.15, 0.95);
        public static final Ramp LEGACY_NIGHTMARE_032 = new Ramp(1, 6, 1.8, 1.6, 0.85);

        /** 난이도 id 의 0.3.2 기본 램프 (어려움·악몽만, 나머지 null). */
        public static Ramp legacy032(String id) {
            if (id == null) return null;
            return switch (id) {
                case "hard" -> LEGACY_HARD_032;
                case "nightmare" -> LEGACY_NIGHTMARE_032;
                default -> null;
            };
        }

        /** 진행도 0(시작 값) ~ 1(원래 값). fullFloor ≤ fromFloor 면 1. */
        public double progress(int floor) {
            if (fullFloor <= fromFloor) return 1.0;
            double t = (floor - fromFloor) / (double) (fullFloor - fromFloor);
            return Math.max(0.0, Math.min(1.0, t));
        }
    }

    /** 이 난이도에 램프를 붙인(바꾼) 것. null = 램프 없음. */
    public Difficulty withRamp(Ramp r) {
        return new Difficulty(id, name, hp, damage, drop, xp, telegraph, r);
    }

    /** 층 램프 진행도 (램프 없으면 1 = 기본). 보스 기믹 배율({@code MechanicScaling})도 이 값으로 보간한다. */
    public double rampProgress(int floor) {
        return ramp == null ? 1.0 : ramp.progress(floor);
    }

    /**
     * 그 층의 실효 난이도 — hp·damage·telegraph 를 램프로 보간하고 drop·xp·id·이름은 그대로.
     * 돌려주는 값은 램프가 없어(null) 두 번 적용되지 않는다.
     */
    public Difficulty atFloor(int floor) {
        if (ramp == null) return this;
        double t = ramp.progress(floor);
        return new Difficulty(id, name, lerp(ramp.startHp(), hp, t), lerp(ramp.startDamage(), damage, t), drop, xp,
                lerp(ramp.startTelegraph(), telegraph, t), null);
    }

    private static double lerp(double a, double b, double t) { return a + (b - a) * t; }

    /** 1층 값이 원래 값과 다른가 (램프가 실제로 숫자를 바꾸는가 — 표시용). */
    public boolean rampsAtFloor1() {
        Difficulty f = atFloor(1);
        return ramp != null && (Math.abs(f.hp - hp) > 1e-9 || Math.abs(f.damage - damage) > 1e-9 || Math.abs(f.telegraph - telegraph) > 1e-9);
    }

    /**
     * 몹 HP·피해 배율 안내 (초기 설정 창·난이도 변경 메시지). 기본은 모든 층 같은 값 한 벌: "HP ×1.8·피해 ×1.6".
     * 관리자가 층 램프를 직접 적었을 때만 1층 값과 원래 값을 함께: "1층 HP ×1.5·피해 ×1.3 → 5층부터 ×1.8·×1.6".
     */
    public String hpDamageText() {
        if (!rampsAtFloor1()) return "HP ×" + mult(hp) + "·피해 ×" + mult(damage);
        Difficulty f = atFloor(1);
        return "1층 HP ×" + mult(f.hp) + "·피해 ×" + mult(f.damage) + " → " + ramp.fullFloor() + "층부터 ×" + mult(hp) + "·×" + mult(damage);
    }

    /** 경고 시간 배율 안내 — "×0.85" (직접 적은 램프가 경고 시간을 바꾸면 "×0.95 → 5층부터 ×0.85"). */
    public String telegraphText() {
        Difficulty f = atFloor(1);
        if (ramp == null || Math.abs(f.telegraph - telegraph) <= 1e-9) return "×" + mult(telegraph);
        return "×" + mult(f.telegraph) + " → " + ramp.fullFloor() + "층부터 ×" + mult(telegraph);
    }

    /** 배율 표기 — 소수 둘째 자리까지, 정수도 한 자리 (2.0, 1.15, 0.7). */
    public static String mult(double v) {
        String s = java.math.BigDecimal.valueOf(Math.round(v * 100) / 100.0).stripTrailingZeros().toPlainString();
        return s.contains(".") ? s : s + ".0";
    }

    /** 경고 시간(windup) 에 배율을 적용하되 최소 0.5초 보장 (공정성). */
    public double windup(double seconds) {
        return Math.max(0.5, seconds * telegraph);
    }

    /** 난이도 순서 (min_difficulty 비교용). 알 수 없으면 1(보통). */
    public static int rank(String id) {
        if (id == null) return 1;
        return switch (id) {
            case "easy" -> 0;
            case "normal" -> 1;
            case "hard" -> 2;
            case "nightmare" -> 3;
            default -> 1;
        };
    }

    public boolean atLeast(String otherId) {
        return otherId == null || rank(id) >= rank(otherId);
    }
}
