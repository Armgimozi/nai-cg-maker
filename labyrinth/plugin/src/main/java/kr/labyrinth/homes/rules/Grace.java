package kr.labyrinth.homes.rules;

/**
 * 이사 기간 (0.3.7, plan §10) — 순수. 소유: 묶음 B.
 * <p>
 * 지형 잠금이 <b>처음</b> 켜진 때 ({@code labyrinth-plots.yml grace.started_at}) 부터 days 일. 다시 켜도 다시 세지 않는다.
 * days 는 {@code /labadmin plot grace <일>} 로 바꾼 값, 없으면 config {@code homes.legacy_grace_days}. 0 = 이사 기간 없음.
 *
 * @param days      기간 (일)
 * @param startedAt 시작 (epoch ms, 0 = 아직 잠금이 켜진 적 없음)
 */
public record Grace(int days, long startedAt) {

    public static final long DAY_MS = 86_400_000L;

    public Grace {
        days = Math.max(0, Math.min(365, days));
        startedAt = Math.max(0, startedAt);
    }

    /** 관리자가 바꾼 값 (null·음수 = 없음) 이 있으면 그것, 아니면 config. */
    public static int effectiveDays(Integer override, int configDays) {
        return override != null && override >= 0 ? override : Math.max(0, configDays);
    }

    public long endsAt() { return startedAt <= 0 ? 0 : startedAt + days * DAY_MS; }

    /** 지금 이사 기간인가. */
    public boolean active(long now) { return days > 0 && startedAt > 0 && now < endsAt(); }

    /** 남은 날 (올림, 기간이 아니면 0). */
    public int daysLeft(long now) {
        if (!active(now)) return 0;
        long left = endsAt() - now;
        return (int) Math.max(1, (left + DAY_MS - 1) / DAY_MS);
    }

    /** 잠금이 켜졌고 아직 시작 시각이 없으면 지금 시작한다. */
    public static boolean shouldStart(boolean locked, long startedAt) { return locked && startedAt <= 0; }

    /** 접속 안내를 보낼까 (하루 한 번 — lastDay 는 마지막으로 보낸 날의 epoch day, 없으면 −1). */
    public static boolean noticeDue(long lastDay, long today) { return today != lastDay; }

    /** epoch ms → 서버 시간대의 날 번호. */
    public static long day(long epochMs) {
        return java.time.Instant.ofEpochMilli(epochMs).atZone(java.time.ZoneId.systemDefault()).toLocalDate().toEpochDay();
    }
}
