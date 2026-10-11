package kr.souls.input;

/**
 * 가짜 휘두르기 거르기 (2.3 의 1, R2, PS 의 S3). 순수 (13.1 의 FakeSwingFilterTest). 틱은 모두 Ticker.now 로 적은 값이다.
 * <ul>
 *   <li>mark: 클라이언트는 Q (버리기), 우클릭 사용, 물체 우클릭 뒤에도 팔을 휘두른다 (skyblock WeaponListener.isFakeSwing). 그 표시
 *       (PlayerDropItemEvent, PlayerInteractEvent RIGHT_*, PlayerInteractEntityEvent) 를 받은 틱 m 에서 window 틱 안 (m ≤ s ≤ m + window)
 *       의 휘두르기 s 는 가짜다. 같은 틱이면 두 패킷의 차례와 상관없다 (둘 다 그 틱으로 적힌다. 판정은 다음 틱의 input 자리에서 한다).
 *       클라이언트는 늘 표시 패킷을 먼저 보내므로 휘두르기보다 늦은 틱의 표시는 보지 않는다.</li>
 *   <li>echo (2026-10-11 장부, {@link Ledger}): 서버가 휘두르면 (combat/Swings) 진짜 클라이언트가 같은 손의 휘두르기 하나를 왕복 시간 +
 *       0~1틱 뒤에 되돌려 보낸다 (S3). 서버 휘두름 하나에 그 손의 휘두르기 하나만 되돌아온 것으로 버린다. 예전의 창 규칙 (서버 휘두름 뒤
 *       창 안의 휘두르기를 모두 버림) 은 진짜 클릭까지 버렸고, 서버 휘두름이 막혀 되돌림이 오지 않을 때도 버렸다.</li>
 * </ul>
 */
public final class FakeSwingFilter {
    /** "없음" 틱 (CombatState.NEVER 와 같다) */
    public static final long NEVER = Long.MIN_VALUE / 2;

    /**
     * 장부의 판정. REAL: 진짜 클릭. ECHO: 되돌아온 것 (공격이 아니다). EARLY: 되돌림이 아직 올 수 없는 이른 휘두르기 (진짜로 친다. 주손은
     * InputRouter 가 장부가 정할 때까지 묶어 둔다: {@link Ledger#settle}).
     */
    public enum Verdict { REAL, ECHO, EARLY }

    private FakeSwingFilter() {}

    /**
     * 표시 뒤의 휘두르기인가 (mark 규칙).
     * @param mark 마지막 표시의 틱 (없으면 NEVER)
     * @param window 표시 뒤 가짜로 보는 틱 (combat.input.fake-swing-window)
     */
    public static boolean mark(long swing, long mark, int window) {
        return mark > NEVER && swing >= mark && swing - mark <= Math.max(0, window);
    }

    /** 휘두르기 swing 이 표시 뒤의 가짜면 "mark", 아니면 null (되돌림은 {@link Ledger#take} 가 휘두르기를 받은 그때 정한다). */
    public static String why(long swing, long mark, int window) {
        return mark(swing, mark, window) ? "mark" : null;
    }

    /** 핑 (ms) 의 왕복 틱 (올림). */
    public static int pingTicks(int pingMs) {
        return pingMs <= 0 ? 0 : (int) Math.ceil(pingMs / 50.0);
    }

    /**
     * 한 손의 되돌림 장부 (2026-10-11, CombatState 가 손마다 하나 둔다). 서버 휘두름 하나에 그 손의 휘두르기 하나가 되돌아온다.
     * <ul>
     *   <li>{@link #sent}: 서버가 휘둘렀다. 남은 되돌림 due + 1, 받는 끝 틱 until = max(until, now + 핑 틱 + window).
     *       받는 첫 틱 from = now + max(0, 핑 틱 − 2): 되돌림은 한 왕복이 지나야 온다 (Paper 의 핑은 5초 평균이라 두 틱을 덜 본다).
     *       앞의 되돌림이 아직 남았으면 from 은 그것의 것을 둔다.</li>
     *   <li>{@link #take}: 그 손의 휘두르기 하나. from 이 지나 온 것은 되돌림이다 (due − 1). from 전에 온 것 (EARLY) 은 되돌림이 닿기 전에
     *       클라이언트가 보낸 진짜 클릭이다: 핑이 큰 클라이언트에서 공격 시작 바로 뒤의 클릭이 되돌림보다 먼저 와 장부를 쓰고, 늦게 온
     *       되돌림이 그 클릭의 웅크리기·달리기로 공격이 되던 것 (강공격이 약공격으로, 웅크리기 짧은 누름이 구르기로) 을 막는다.</li>
     *   <li>{@link #settle}: 묶어 둔 이른 휘두르기의 판정. 그 뒤 되돌림이 오면 (take 가 ECHO) 진짜로 풀고, 끝 틱이 지나도록 오지 않으면 핑을
     *       크게 본 것이라 그 이른 휘두르기가 되돌림이었다 (버린다). 그래서 핑을 잘못 보아도 저절로 생긴 공격은 없다 (수는 늘 같다).</li>
     * </ul>
     */
    public static final class Ledger {
        /** 아직 오지 않은 되돌림 */
        private int due;
        /** 이 틱부터 온 휘두르기가 되돌림일 수 있다 */
        private long from = NEVER;
        /** 받는 끝 틱 */
        private long until = NEVER;
        /** 묶어 둔 (아직 정하지 않은) 이른 휘두르기 */
        private int held;
        /** 진짜로 풀린 이른 휘두르기 (settle 이 오래된 것부터 꺼낸다) */
        private int confirmed;

        /** 서버가 이 손을 휘둘렀다 (now 틱, 핑 틱, combat.input.echo-window). */
        public void sent(long now, int pingTicks, int window) {
            int ping = Math.max(0, pingTicks);
            if (due <= 0 || now > until) {
                due = 0;
                from = now + Math.max(0, ping - 2);
            }
            due++;
            until = Math.max(until, now + ping + Math.max(0, window));
        }

        /**
         * 그 손의 휘두르기 하나가 now 에 왔다. hold 면 이른 휘두르기를 묶는다 (주손: InputRouter 가 settle 로 정한다). 아니면 이른 것은
         * 진짜로만 치고 장부는 그대로 둔다 (왼손: 입력이 아니다).
         */
        public Verdict take(long now, boolean hold) {
            if (now > until) due = 0;
            if (due <= 0) return Verdict.REAL;
            if (now < from) {
                if (!hold) return Verdict.EARLY;
                // 남은 되돌림마다 이른 휘두르기 하나만 묶는다 (그보다 많으면 모두 되돌림일 수는 없다)
                if (due - held <= 0) return Verdict.REAL;
                held++;
                return Verdict.EARLY;
            }
            due--;
            // 되돌림이 왔다: 먼저 묶어 둔 이른 휘두르기는 진짜다
            if (held > 0) {
                held--;
                confirmed++;
            }
            return Verdict.ECHO;
        }

        /**
         * 묶어 둔 이른 휘두르기 (오래된 것부터, 받은 때의 끝 틱 deadline) 의 판정: 그 뒤 되돌림이 왔으면 REAL, deadline 이 지나도록 오지
         * 않았으면 ECHO (그것이 되돌림이었다), 아직이면 null.
         */
        public Verdict settle(long now, long deadline) {
            if (confirmed > 0) {
                confirmed--;
                return Verdict.REAL;
            }
            if (now <= deadline) return null;
            held = Math.max(0, held - 1);
            due = Math.max(0, due - 1);
            return Verdict.ECHO;
        }

        /** 지금 남은 되돌림 (시험 줄 MOVE_STATE echo=). */
        public int due(long now) {
            return now <= until ? due : 0;
        }

        /** 받는 끝 틱 (묶은 휘두르기의 deadline). */
        public long until() {
            return until;
        }

        /** 받는 첫 틱. */
        public long from() {
            return from;
        }
    }
}
