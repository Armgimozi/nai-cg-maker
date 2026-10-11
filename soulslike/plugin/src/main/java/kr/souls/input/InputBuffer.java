package kr.souls.input;

/**
 * 입력 기억 (3.1, 3.6). 순수 (13.1 의 InputBufferTest). 한 사람의 마지막 약공격·강공격·달리기 공격·구르기 입력 하나와 그 틱을 둔다
 * (나중 것이 앞의 것을 바꾼다).
 * <ul>
 *   <li>받기: 지금 동작이 끝나는 틱 E 에서 acceptBefore 틱 전부터 (t ≥ E − acceptBefore). 더 이른 입력은 버린다 (회복 − 6 은 받고 − 7 은
 *       버린다).</li>
 *   <li>꺼내기: 동작이 끝난 틱 (가능한 첫 틱) 에 꺼낸다. 받은 지 buffer 틱이 넘은 것은 버린다.</li>
 * </ul>
 * 구르기 (ROLL) 는 P1c 가 쓴다 (지금 구르기의 짧은 누름은 SneakTap 이 따로 기억한다).
 */
public final class InputBuffer {
    /** 입력 종류. 강공격 = 웅크리기 키 + 휘두르기, 달리기 공격 = 달리며 휘두르기 */
    public enum Kind { LIGHT, HEAVY, RUNNING, ROLL }

    /** 기억한 입력 하나. aim 은 겨눈 대상의 UUID 글 (없으면 null). */
    public record Entry(Kind kind, long at, java.util.UUID aim) {}

    private Entry last;

    /**
     * 동작 중에 들어온 입력. readyAt = 지금 동작이 끝나는 틱. 받았으면 true (앞에 기억한 것을 바꾼다).
     */
    public boolean offer(Kind kind, long now, long readyAt, int acceptBefore, java.util.UUID aim) {
        if (kind == null || now < readyAt - Math.max(0, acceptBefore)) return false;
        last = new Entry(kind, now, aim);
        return true;
    }

    /** 지금 (now) 쓸 수 있는 기억한 입력을 꺼낸다 (buffer 틱이 넘었으면 버리고 null). 꺼내면 비운다. */
    public Entry take(long now, int buffer) {
        Entry e = last;
        last = null;
        if (e == null || now - e.at() > Math.max(0, buffer)) return null;
        return e;
    }

    /** 기억한 입력 (꺼내지 않는다, 시험 줄). */
    public Entry peek() {
        return last;
    }

    public void clear() {
        last = null;
    }
}
