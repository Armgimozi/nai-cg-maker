package kr.labyrinth.bosses;

import java.util.Objects;
import java.util.UUID;

/**
 * 추격 막힘 감시 (bs362, Bukkit 무관 — 단위 테스트 대상).
 * <p>
 * 바닐라 큰 몹 길찾기는 벽·등불 받침 옆 1칸 틈 앞에서 길이 바로 끝나 보스가 그 자리에 서 버린다 (보스는 못 치고 플레이어만 치는 자리).
 * 이 감시는 {@link Boss} 의 추격이 매 틱(바쁘지 않을 때) 부른다:
 * <ol>
 *   <li><b>멈춤</b>: 대상이 기본 공격 밖인데 보스가 {@link #WINDOW} 틱 동안 {@link #STALL_MOVE} 칸도 못 움직였다.</li>
 *   <li><b>직접 다가가기</b>: 멈췄거나 길이 아예 없을 때(떠다니는 보스), 대상이 보이고 {@link #STEER_RANGE} 칸 안이면(길이 없으면 거리 무관)
 *       길찾기 대신 대상 쪽으로 곧장 걷는다 — 벽은 바닐라 충돌이 막는다. 안 보이는 채 {@link #BLIND_AFTER} 틱 더 멈춰 있으면
 *       {@link #BLIND_TICKS} 틱 동안은 안 보여도 다가간다 (기둥 뒤 — 몸이 기둥을 돌아 시야를 찾는다).</li>
 *   <li><b>거리 좁히기</b>: 그래도 {@link #GAP_AFTER} 틱 동안 멈춘 채이고 대상이 교전 중(최근 {@link #ENGAGE_TICKS} 틱 안에 보스를 때렸거나
 *       {@link #ENGAGE_RANGE} 칸 안)이면 한 번 알린다 → 보스가 경고 장판 뒤 도약(설 자리 없으면 땅 울림).</li>
 * </ol>
 * 보스가 움직이는 동안(트인 곳 추격·원거리 카이팅)은 멈춤이 아니라서 아무 일도 없다. 기본 공격이 닿으면 전부 처음으로.
 * 시간은 부른 횟수로 센다 — 패턴으로 바쁜 동안은 멈춤 시간에 안 들어간다.
 */
public final class ChaseGuard {

    /** 이동량을 재는 창 (부른 횟수 = 틱). */
    public static final int WINDOW = 10;
    /** 한 창에서 이만큼도 못 움직이면 멈춤 (걷기 0.12칸/틱 × 10 = 1.2칸). */
    public static final double STALL_MOVE = 0.25;
    /** 멈춘 채 이만큼(2초) 지나면 거리 좁히기. */
    public static final int GAP_AFTER = 40;
    /** 대상이 이 틱(4초) 안에 보스를 때렸으면 교전 중. */
    public static final int ENGAGE_TICKS = 80;
    /** 또는 이 거리(수평) 안이면 교전 중. */
    public static final double ENGAGE_RANGE = 6.0;
    /** 직접 다가가기를 시작하는 거리 (길이 아예 없으면 거리 무관). 끝은 + 2칸. */
    public static final double STEER_RANGE = 6.0;
    /** 안 보이는 채 이만큼(1초) 멈춰 있으면 안 보여도 다가가 본다 (기둥 뒤 — 몸이 기둥을 돌아 시야를 찾는다). */
    public static final int BLIND_AFTER = 20;
    /** 안 보여도 다가가기를 이어 가는 틱. */
    public static final int BLIND_TICKS = 60;

    public enum Move {
        /** 옛 추격 (길찾기 · 0.85 × reach 안이면 멈춤). */
        PATH,
        /** 대상 쪽으로 곧장 걷기. */
        STEER,
        /** 움직이지 않음 (길찾기 꺼짐·안 걷는 보스). */
        HOLD
    }

    /**
     * 한 틱 입력.
     * @param target   대상 (null = 없음)
     * @param canMove  보스가 지금 걸을 수 있는가 (길찾기 켜짐 + 이동 속도 &gt; 0)
     * @param inReach  기본 공격이 지금 닿는가 (기하 + 시야)
     * @param dist     보스 중심 ↔ 대상 수평 거리
     * @param noPath   길찾기가 길을 못 만든다 (떠다니는 보스는 늘 true)
     * @param sees     보스와 대상 사이 시야
     * @param sinceHit 대상이 보스를 마지막으로 때린 뒤 지난 틱 (없으면 아주 큰 값)
     * @param bx       보스 x
     * @param bz       보스 z
     */
    public record Input(UUID target, boolean canMove, boolean inReach, double dist, boolean noPath, boolean sees,
                        long sinceHit, double bx, double bz) {}

    /** @param closeGap true = 지금 거리 좁히기 (이번 한 틱만) */
    public record Output(Move move, boolean closeGap) {}

    private UUID target;
    private boolean steering;
    private boolean stalled;
    private int blocked;
    private int blind;
    private long blindNext;
    private long clock;
    private long anchorClock = -1;
    private double ax, az;

    public Output update(Input in) {
        clock++;
        if (!Objects.equals(target, in.target())) {
            reset();
            target = in.target();
        }
        if (in.target() == null || !in.canMove()) {
            reset();
            target = in.target();
            return new Output(Move.HOLD, false);
        }
        if (anchorClock < 0) anchor(in);
        if (clock - anchorClock >= WINDOW) {
            stalled = Math.hypot(in.bx() - ax, in.bz() - az) < STALL_MOVE;
            anchor(in);
        }
        if (in.inReach()) {
            steering = false;
            stalled = false;
            blocked = 0;
            blind = 0;
            anchor(in);
            return new Output(Move.PATH, false);
        }
        blocked = stalled ? blocked + 1 : 0;
        if (blind > 0) {
            blind--;
        } else if (!in.sees() && stalled && blocked >= BLIND_AFTER && clock >= blindNext) {
            blind = BLIND_TICKS;
            blindNext = clock + BLIND_TICKS + 2L * BLIND_AFTER; // 다시 해 보기까지 쉼
        }
        boolean looks = in.sees() || blind > 0; // 안 보이면 잠깐만 (충돌이 벽을 막으니 벽 너머로 가지는 않는다)
        boolean steerOk = looks && (in.noPath() || in.dist() <= STEER_RANGE);
        if (!steering) {
            if (steerOk && (in.noPath() || stalled || blind > 0)) steering = true;
        } else if (!looks || (!in.noPath() && in.dist() > STEER_RANGE + 2)) {
            steering = false;
        }
        boolean engaged = in.sinceHit() <= ENGAGE_TICKS || in.dist() <= ENGAGE_RANGE;
        boolean gap = false;
        if (blocked >= GAP_AFTER && engaged) {
            gap = true;
            blocked = 0;
            stalled = false;
            anchor(in);
        }
        return new Output(steering ? Move.STEER : Move.PATH, gap);
    }

    /** 지금 멈춤으로 센 틱 수 (진단용). */
    public int blocked() { return blocked; }

    public boolean steering() { return steering; }

    public boolean stalled() { return stalled; }

    private void anchor(Input in) {
        anchorClock = clock;
        ax = in.bx();
        az = in.bz();
    }

    private void reset() {
        steering = false;
        stalled = false;
        blocked = 0;
        blind = 0;
        blindNext = 0;
        anchorClock = -1;
    }
}
