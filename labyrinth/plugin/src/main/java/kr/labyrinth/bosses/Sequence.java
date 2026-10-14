package kr.labyrinth.bosses;

import java.util.Random;

/**
 * 서열 기억 퍼즐 부품 (GDD §8.2 {@code Sequence} — 8층 금서 색인 {@code forbidden_index}).
 * 서열 생성 → 하나씩 공개(빛·소리) → 입력 검증 → 제한 시간. Bukkit 무관 — 단위 테스트 대상. 시간 단위는 틱, 기호는 0 ~ symbols−1.
 * <ul>
 *   <li>공개: {@code lead} 틱 뒤부터 {@code interval} 틱마다 하나씩, 각 기호는 {@code lit} 틱 동안 빛난다.</li>
 *   <li>입력: 공개가 끝난 틱부터 {@code timeLimit} 틱. 공개 중의 입력은 무시(벌칙 없음).</li>
 *   <li>맞으면 다음 칸, 서열을 끝까지 맞히면 {@link Result#COMPLETE}. 틀리면 처음부터 + 제한 시간 −{@code penalty} 틱.</li>
 *   <li>방금 맞힌 기호를 또 치는 것(연타·다단 히트)은 무시, 틀린 직후 {@link #WRONG_GRACE_TICKS} 동안의 입력도 무시
 *       (광역기 한 번에 벌칙이 겹치지 않게).</li>
 * </ul>
 */
public final class Sequence {

    /** 틀린 직후 입력을 무시하는 시간 (0.5초). */
    public static final int WRONG_GRACE_TICKS = 10;

    public enum State { REVEAL, INPUT, SUCCESS, FAILED }

    public enum Result { IGNORED, ADVANCE, COMPLETE, WRONG }

    private final int[] order;
    private final long revealStart;
    private final int interval;
    private final int lit;
    private final long inputStart;
    private final int timeLimit;
    private final int penalty;
    private long deadline;
    private int progress;
    private int lastAccepted = -1;
    private long graceUntil = Long.MIN_VALUE;
    private int wrongs;
    private State state = State.REVEAL;

    /**
     * @param order     공개·입력 순서 (기호 번호)
     * @param now       시작 틱
     * @param lead      첫 공개까지 대기 틱
     * @param interval  공개 간격 틱 (≥ 1)
     * @param lit       기호 하나가 빛나는 틱 (≤ interval)
     * @param timeLimit 입력 제한 시간 틱
     * @param penalty   틀렸을 때 줄어드는 제한 시간 틱
     */
    public Sequence(int[] order, long now, int lead, int interval, int lit, int timeLimit, int penalty) {
        if (order == null || order.length == 0) throw new IllegalArgumentException("빈 서열");
        this.order = order.clone();
        this.interval = Math.max(1, interval);
        this.lit = Math.max(1, Math.min(this.interval, lit));
        this.revealStart = now + Math.max(0, lead);
        this.inputStart = revealStart + (long) this.order.length * this.interval;
        this.timeLimit = Math.max(1, timeLimit);
        this.penalty = Math.max(0, penalty);
        this.deadline = inputStart + this.timeLimit;
    }

    /** 서열 길이 = base + floor((n−1) / perMembers), [1, max] (GDD §7.8: 4 + ⌊(n−1)/3⌋, 최대 7). */
    public static int length(double base, double perMembers, int max, int partySize) {
        int n = BossMath.countPerMembers(base, perMembers, partySize);
        return Math.max(1, max > 0 ? Math.min(max, n) : n);
    }

    /**
     * 무작위 서열. length ≤ symbols 이면 모두 다른 기호(같은 책장을 두 번 치는 일이 없다),
     * 더 길면 바로 앞과 같은 기호만 피한다.
     */
    public static int[] generate(int symbols, int length, Random rng) {
        int s = Math.max(1, symbols);
        int len = Math.max(1, length);
        int[] out = new int[len];
        if (len <= s) {
            int[] pool = new int[s];
            for (int i = 0; i < s; i++) pool[i] = i;
            for (int i = 0; i < len; i++) {
                int j = i + rng.nextInt(s - i);
                int t = pool[i];
                pool[i] = pool[j];
                pool[j] = t;
                out[i] = pool[i];
            }
            return out;
        }
        for (int i = 0; i < len; i++) {
            int v = rng.nextInt(s);
            if (i > 0 && s > 1 && v == out[i - 1]) v = (v + 1 + rng.nextInt(s - 1)) % s;
            out[i] = v;
        }
        return out;
    }

    /** 시간 진행 (공개 → 입력 → 시간 초과). */
    public State update(long now) {
        if (state == State.REVEAL && now >= inputStart) state = State.INPUT;
        if (state == State.INPUT && now >= deadline) state = State.FAILED;
        return state;
    }

    /** 지금 빛나는 기호의 공개 순번 (0부터, 없으면 −1). */
    public int litIndex(long now) {
        if (now < revealStart || now >= inputStart) return -1;
        long dt = now - revealStart;
        int k = (int) (dt / interval);
        return dt % interval < lit ? k : -1;
    }

    /** 이 틱에 새로 켜지는 공개 순번 (소리·연출 시작용, 없으면 −1). */
    public int revealStep(long now) {
        if (now < revealStart || now >= inputStart) return -1;
        long dt = now - revealStart;
        return dt % interval == 0 ? (int) (dt / interval) : -1;
    }

    /** 기호 하나 입력 (책장 피격). */
    public Result input(int symbol, long now) {
        update(now);
        if (state != State.INPUT) return Result.IGNORED;
        if (now < graceUntil) return Result.IGNORED;
        if (symbol == lastAccepted) return Result.IGNORED;
        if (symbol == order[progress]) {
            lastAccepted = symbol;
            progress++;
            if (progress >= order.length) {
                state = State.SUCCESS;
                return Result.COMPLETE;
            }
            return Result.ADVANCE;
        }
        wrongs++;
        progress = 0;
        lastAccepted = -1;
        graceUntil = now + WRONG_GRACE_TICKS;
        deadline -= penalty;
        if (now >= deadline) state = State.FAILED;
        return Result.WRONG;
    }

    /** 강제 종료 (페이즈 전환·보스 종료). */
    public void abort() {
        if (state == State.REVEAL || state == State.INPUT) state = State.FAILED;
    }

    public State state() { return state; }

    public boolean finished() { return state == State.SUCCESS || state == State.FAILED; }

    public int length() { return order.length; }

    public int symbol(int index) { return order[index]; }

    public int[] order() { return order.clone(); }

    /** 맞힌 개수. */
    public int progress() { return progress; }

    public int wrongs() { return wrongs; }

    public long revealStart() { return revealStart; }

    public long inputStart() { return inputStart; }

    public long deadline() { return deadline; }

    public int timeLimit() { return timeLimit; }

    /** 남은 입력 시간 틱 (입력 전이면 전체). */
    public long remaining(long now) {
        if (now < inputStart) return deadline - inputStart;
        return Math.max(0, deadline - now);
    }
}
