package kr.souls.combat;

/**
 * 차오르고 쓰는 자원 하나. 지금은 스태미나만 쓰지만, 마법을 넣기로 했으므로 마나(FP)도 같은 꼴로 더한다
 * (회복 규칙만 다르다: 마나는 저절로 차지 않고 화톳불·물약으로 찬다). 그래서 회복은 이 클래스가 아니라 각 체계가 정한다.
 *
 * 규칙 (3.2): 1 이상이면 어떤 행동이든 한다. 모자라면 0 에서 멈춘다.
 */
public final class Pool {
    private double cur, max;
    /** 회복이 시작되는 틱 (이 틱부터 찬다) */
    private long regenFrom;

    public Pool(double max) {
        this.max = Math.max(1, max);
        this.cur = this.max;
    }

    public double cur() { return cur; }

    public double max() { return max; }

    public double ratio() { return cur / max; }

    public boolean full() { return cur >= max; }

    public long regenFrom() { return regenFrom; }

    /** 최대치를 바꾼다. 가득 차 있었으면 가득 찬 채로. */
    public void setMax(double m) {
        boolean wasFull = full();
        max = Math.max(1, m);
        cur = wasFull ? max : Math.min(cur, max);
    }

    public void set(double v) {
        cur = Math.max(0, Math.min(max, v));
    }

    public void fill() {
        cur = max;
    }

    /** 행동을 시작할 수 있는가 (1 이상). */
    public boolean canAct() {
        return cur >= 1;
    }

    /** 쓴다. 0 아래로는 내려가지 않는다. 0 이 되었으면 true. */
    public boolean spend(double amount) {
        cur = Math.max(0, cur - amount);
        return cur <= 0;
    }

    /** 회복은 이 틱부터 (이미 더 늦게 잡혀 있으면 그대로). */
    public void holdUntil(long tick) {
        if (tick > regenFrom) regenFrom = tick;
    }

    public void resetHold() {
        regenFrom = 0;
    }

    /** now 가 회복 틱에 닿았으면 amount 만큼 찬다. 실제로 바뀌었으면 true. */
    public boolean regen(long now, double amount) {
        if (now < regenFrom || cur >= max || amount <= 0) return false;
        cur = Math.min(max, cur + amount);
        return true;
    }
}
