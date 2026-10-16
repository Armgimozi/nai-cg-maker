package kr.labyrinth.mobs;

/**
 * 묶인 몹(미믹 — 상자 자리에 매인 몹)의 부드러운 줄 (순수). 대상이 줄 안이면 그냥 쫓고, 줄 밖이면 줄 끝까지만 가서 대상을 보고 버틴다
 * (순간이동 없이). 줄 밖으로 밀려났으면 걸어서 돌아온다. 도약 같은 돌진 스킬은 대상이 줄 끝에서 {@link #LUNGE_MARGIN} 칸 안일 때만.
 * 거리는 모두 줄 가운데에서 잰 수평 거리(블록).
 */
public final class Leash {

    private Leash() {}

    public enum Move { CHASE, HOLD, RETURN }

    /** 줄 끝에서 이만큼 안쪽부터는 멈춰 버틴다 (끝에서 들락날락하지 않게). */
    public static final double HOLD_BAND = 1.0;
    /** 줄 끝보다 이만큼 더 나가 있으면 걸어서 돌아온다. */
    public static final double RETURN_SLACK = 0.5;
    /** 돌진(도약·돌격·순간이동) 스킬은 대상이 줄 끝 + 이만큼 안일 때만 — 줄 끝에서 한 번 덮치고 돌아온다. */
    public static final double LUNGE_MARGIN = 3.0;

    /**
     * @param own    몹이 줄 가운데에서 떨어진 거리
     * @param target 대상이 줄 가운데에서 떨어진 거리
     * @param radius 줄 길이
     */
    public static Move decide(double own, double target, double radius) {
        if (target <= radius) return Move.CHASE;
        if (own > radius + RETURN_SLACK) return Move.RETURN;
        if (own >= radius - HOLD_BAND) return Move.HOLD;
        return Move.CHASE;
    }

    /** 돌진 스킬을 써도 되나 (대상이 줄 끝 + {@link #LUNGE_MARGIN} 안). */
    public static boolean canLunge(double target, double radius) {
        return target <= radius + LUNGE_MARGIN;
    }
}
