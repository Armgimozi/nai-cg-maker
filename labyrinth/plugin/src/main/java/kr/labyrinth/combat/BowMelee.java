package kr.labyrinth.combat;

/**
 * 활로 직접 치기 (0.3.6.1, bowfeel '정할 것 2' · 주인 결정 2) — 순수 로직 (단위 테스트 대상).
 * <ul>
 *   <li>활(원거리 무기)을 든 채 왼쪽 클릭으로 친 근접 기본 공격은 피해 × {@code combat.bow_melee_mult} (기본 0.5 = 절반).
 *       예전에는 활 한 방이 그대로 들어가 단도보다 26% 셌다. 몹·바닐라 몹·PvP 모두 같다 ({@code CombatListener.meleeMult}).</li>
 *   <li>간격은 그대로 활 한 발 주기 (화살 한 발이나 근접 한 대 — {@link AttackTiming}). 화살·무기 스킬·직업 스킬은 바뀌지 않는다.</li>
 *   <li>툴팁: 활마다 '공격 속도' 줄 바로 아래 한 줄 ({@link #tooltipText}).</li>
 * </ul>
 */
public final class BowMelee {

    /** config 에 키가 없을 때 (= jar config.yml). */
    public static final double DEFAULT_MULT = 0.5;

    private BowMelee() {}

    /** 설정값을 0~1 로 (NaN = 기본값). 1 = 예전 그대로. */
    public static double clamp(double mult) {
        return Double.isNaN(mult) ? DEFAULT_MULT : Math.max(0, Math.min(1.0, mult));
    }

    /** 근접 기본 공격 피해 배율: 손 무기가 원거리(활)면 설정 배율, 아니면 1. */
    public static double mult(WeaponAttack held, double configured) {
        return held != null && held.ranged() ? clamp(configured) : 1.0;
    }

    /** 활 툴팁 한 줄 (색 없음): 0.5 = "활로 직접 치면 피해 절반", 1 = 없음(null), 그 밖 = "활로 직접 치면 피해 70%". */
    public static String tooltipText(double configured) {
        double m = clamp(configured);
        if (m >= 0.9995) return null;
        if (Math.abs(m - 0.5) < 0.0005) return "활로 직접 치면 피해 절반";
        if (m <= 0.0005) return "활로 직접 치면 피해 없음";
        return "활로 직접 치면 피해 " + Math.round(m * 100) + "%";
    }
}
