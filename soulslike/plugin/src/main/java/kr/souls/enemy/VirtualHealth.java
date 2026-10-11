package kr.souls.enemy;

/**
 * 가상 체력 (DESIGN 6.1, M1 P1b). 바닐라 피해는 모두 취소하고 (FoeBody) 플러그인이 이 값을 깎는다. 최대치는 생길 때 한 번
 * enemies.yml hp × 난이도 enemy-health 로 정한다 (그 뒤 난이도가 바뀌어도 이미 선 적은 그대로, 새로 서는 적부터 새 배율).
 * regenAfter (틱) 가 0 보다 크면 마지막으로 맞고 그만큼 지난 뒤 다 찬다 (허수아비. 읽을 때 셈하므로 틱마다 돌 일이 없다). 쓰러진 (0) 적은
 * 차지 않는다. 순수하다 (시계는 부르는 쪽이 넘긴다, VirtualHealthTest).
 */
public final class VirtualHealth {
    private final double max;
    private final int regenAfter;
    private double hp;
    private long lastHurt = Long.MIN_VALUE / 2;

    /** max: {@link #maxFor} 로 셈한 최대치 (1 밑이면 1). regenAfter: 틱, 0 이면 차지 않는다. */
    public VirtualHealth(double max, int regenAfter) {
        this.max = Double.isNaN(max) || max < 1 ? 1 : Math.min(max, 1e12);
        this.regenAfter = Math.max(0, regenAfter);
        this.hp = this.max;
    }

    /** 생길 때의 최대치 = 정의의 hp × 난이도 배율 (NaN·0 밑의 배율은 1). 1 밑으로 내려가지 않는다. */
    public static double maxFor(double base, double mult) {
        double b = Double.isNaN(base) || base < 1 ? 1 : base;
        double m = Double.isNaN(mult) || Double.isInfinite(mult) || mult <= 0 ? 1 : mult;
        return Math.max(1, b * m);
    }

    public double max() {
        return max;
    }

    public int regenAfter() {
        return regenAfter;
    }

    /** 마지막으로 깎인 틱 (없으면 아주 작은 값). */
    public long lastHurt() {
        return lastHurt;
    }

    /** now 의 남은 체력 (regenAfter 가 지났으면 다 찬다). */
    public double hp(long now) {
        settle(now);
        return hp;
    }

    /** 쓰러졌다 (0). */
    public boolean dead() {
        return hp <= 0;
    }

    /** amount 를 깎고 남은 체력을 돌려준다 (0 밑으로 내려가지 않는다). 0 이하·NaN 은 깎지 않고 시계도 그대로. */
    public double hurt(double amount, long now) {
        settle(now);
        if (!(amount > 0) || hp <= 0) return hp;
        hp = Math.max(0, hp - Math.min(amount, 1e15));
        lastHurt = now;
        return hp;
    }

    /** 다 채운다 (쓰러진 것도). */
    public void fill() {
        hp = max;
    }

    private void settle(long now) {
        if (regenAfter > 0 && hp > 0 && hp < max && now - lastHurt >= regenAfter) hp = max;
    }
}
