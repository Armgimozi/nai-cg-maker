package kr.labyrinth.core;

/**
 * 서버 난이도 프리셋 (config.yml difficulties, GDD §2.4).
 * hp/damage = 몹·보스 배율, drop = 드롭 확률 배율, xp = 경험치 배율, telegraph = 경고 시간(windup) 배율.
 * <p>
 * ramp = 층 램프 (null = 모든 층 같은 값). hp·damage·telegraph 만 낮은 층에서 완만하게 시작해
 * {@link Ramp#fullFloor} 층부터 원래 값이 된다. drop·xp(보상)는 1층부터 원래 값. 층의 실제 값은 {@link #atFloor}.
 */
public record Difficulty(String id, String name, double hp, double damage, double drop, double xp, double telegraph, Ramp ramp) {

    public static final Difficulty EASY = new Difficulty("easy", "쉬움", 0.7, 0.6, 0.8, 0.8, 1.3);
    public static final Difficulty NORMAL = new Difficulty("normal", "보통", 1.0, 1.0, 1.0, 1.0, 1.0);
    public static final Difficulty HARD = new Difficulty("hard", "어려움", 1.5, 1.4, 1.3, 1.3, 0.85);
    public static final Difficulty NIGHTMARE = new Difficulty("nightmare", "악몽", 2.4, 2.0, 1.8, 1.7, 0.7);

    /** 램프 없는 프리셋 (위 상수·대체 보스 배율·테스트). */
    public Difficulty(String id, String name, double hp, double damage, double drop, double xp, double telegraph) {
        this(id, name, hp, damage, drop, xp, telegraph, null);
    }

    /**
     * 층 램프: fromFloor 층에서 start* 값으로 시작해 fullFloor 층부터 그 난이도의 원래 값.
     * 층 f 의 값 = start + (원래 − start) × t, t = clamp((f − fromFloor)/(fullFloor − fromFloor), 0, 1).
     */
    public record Ramp(int fromFloor, int fullFloor, double startHp, double startDamage, double startTelegraph) {

        /** 코드 기본값 (= jar 의 config.yml). 기존 서버 config.yml 에 ramp 키가 없어도 이 값으로 켜진다. */
        public static final Ramp HARD = new Ramp(1, 4, 1.2, 1.15, 0.95);
        public static final Ramp NIGHTMARE = new Ramp(1, 6, 1.8, 1.6, 0.85);

        /** 난이도 id 의 기본 램프 (어려움·악몽만, 나머지 null). */
        public static Ramp defaultFor(String id) {
            if (id == null) return null;
            return switch (id) {
                case "hard" -> HARD;
                case "nightmare" -> NIGHTMARE;
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

    /** 층 램프 진행도 (램프 없으면 1). 보스 기믹 배율({@code MechanicScaling})도 이 값으로 보간한다. */
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
     * 몹 HP·피해 배율 안내 (초기 설정 창·난이도 변경 메시지). 램프가 있으면 1층 값과 원래 값을 함께:
     * "1층 HP ×1.8·피해 ×1.6 → 6층부터 ×2.4·×2.0", 없으면 "HP ×1.5·피해 ×1.4".
     */
    public String hpDamageText() {
        if (!rampsAtFloor1()) return "HP ×" + mult(hp) + "·피해 ×" + mult(damage);
        Difficulty f = atFloor(1);
        return "1층 HP ×" + mult(f.hp) + "·피해 ×" + mult(f.damage) + " → " + ramp.fullFloor() + "층부터 ×" + mult(hp) + "·×" + mult(damage);
    }

    /** 경고 시간 배율 안내 — "×0.85 → 6층부터 ×0.7" (램프가 없거나 같으면 "×0.7"). */
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
