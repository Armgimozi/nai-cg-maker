package kr.labyrinth.core;

/**
 * 서버 난이도 프리셋 (config.yml difficulties, GDD §2.4).
 * hp/damage = 몹·보스 배율, drop = 드롭 확률 배율, xp = 경험치 배율, telegraph = 경고 시간(windup) 배율.
 */
public record Difficulty(String id, String name, double hp, double damage, double drop, double xp, double telegraph) {

    public static final Difficulty EASY = new Difficulty("easy", "쉬움", 0.7, 0.6, 0.8, 0.8, 1.3);
    public static final Difficulty NORMAL = new Difficulty("normal", "보통", 1.0, 1.0, 1.0, 1.0, 1.0);
    public static final Difficulty HARD = new Difficulty("hard", "어려움", 1.5, 1.4, 1.3, 1.3, 0.85);
    public static final Difficulty NIGHTMARE = new Difficulty("nightmare", "악몽", 2.4, 2.0, 1.8, 1.7, 0.7);

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
