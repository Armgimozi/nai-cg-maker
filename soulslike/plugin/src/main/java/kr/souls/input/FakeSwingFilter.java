package kr.souls.input;

/**
 * 가짜 휘두르기 거르기 (2.3 의 1, R2, PS 의 S3). 순수 함수 (13.1 의 FakeSwingFilterTest). 틱은 모두 Ticker.now 로 적은 값이다.
 * <ul>
 *   <li>mark: 클라이언트는 Q (버리기), 우클릭 사용, 물체 우클릭 뒤에도 팔을 휘두른다 (skyblock WeaponListener.isFakeSwing). 그 표시
 *       (PlayerDropItemEvent, PlayerInteractEvent RIGHT_*, PlayerInteractEntityEvent) 를 받은 틱 m 에서 window 틱 안 (m ≤ s ≤ m + window)
 *       의 휘두르기 s 는 가짜다. 같은 틱이면 두 패킷의 차례와 상관없다 (둘 다 그 틱으로 적힌다. 판정은 다음 틱의 input 자리에서 한다).
 *       클라이언트는 늘 표시 패킷을 먼저 보내므로 휘두르기보다 늦은 틱의 표시는 보지 않는다.</li>
 *   <li>echo: 서버가 휘두르면 (combat/Swings) 진짜 클라이언트가 같은 손의 휘두르기를 왕복 시간 + 0~1틱 뒤에 되돌려 보낸다 (S3). 서버의
 *       주손 휘두르기 틱 e 에서 echoWindow (핑 틱 + combat.input.echo-window) 안의 주손 휘두르기는 되돌아온 것이다.</li>
 * </ul>
 */
public final class FakeSwingFilter {
    /** "없음" 틱 (CombatState.NEVER 와 같다) */
    public static final long NEVER = Long.MIN_VALUE / 2;

    private FakeSwingFilter() {}

    /**
     * 휘두르기 swing 이 가짜면 까닭 ("mark" | "echo"), 진짜면 null.
     * @param mark 마지막 표시의 틱 (없으면 NEVER)
     * @param window 표시 뒤 가짜로 보는 틱 (combat.input.fake-swing-window)
     * @param serverSwing 서버가 이 사람의 주손을 마지막으로 휘두른 틱 (없으면 NEVER)
     * @param echoWindow 서버 휘두르기 뒤 되돌아온 것으로 보는 틱 (핑 틱 + echo-window)
     */
    public static String why(long swing, long mark, int window, long serverSwing, int echoWindow) {
        if (mark > NEVER && swing >= mark && swing - mark <= Math.max(0, window)) return "mark";
        if (serverSwing > NEVER && swing >= serverSwing && swing - serverSwing <= Math.max(0, echoWindow)) return "echo";
        return null;
    }

    /** 핑 (ms) 의 왕복 틱 (올림). */
    public static int pingTicks(int pingMs) {
        return pingMs <= 0 ? 0 : (int) Math.ceil(pingMs / 50.0);
    }
}
