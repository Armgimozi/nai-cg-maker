package kr.labyrinth.bosses;

import java.util.Objects;
import java.util.UUID;

/**
 * 추격 막힘 감시 (bs362 → bs363, Bukkit 무관 — 단위 테스트 대상).
 * <p>
 * 바닐라 큰 몹 길찾기는 벽·등불 받침 옆 1칸 틈 앞에서 길이 바로 끝나 보스가 그 자리에 서 버린다 (보스는 못 치고 플레이어만 치는 자리).
 * 이 감시는 {@link Boss} 의 추격이 매 틱(바쁘지 않을 때) 부른다:
 * <ol>
 *   <li><b>멈춤</b>: 대상이 기본 공격 밖인데 보스가 {@link #WINDOW} 틱 동안 {@link #STALL_MOVE} 칸도 못 움직였다.</li>
 *   <li><b>곧장 걷기</b>: 멈췄거나 땅 길찾기를 못 쓸 때(떠다니는 보스), 대상이 보이고 {@link #STEER_RANGE} 칸 안이면(떠다니는 보스는 거리 무관)
 *       길찾기 대신 곧장 걷는다 (보스는 대상 둘레 설 자리를 겨눈다) — 벽은 바닐라 충돌이 막는다. 안 보이는 채 {@link #BLIND_AFTER} 틱 더
 *       멈춰 있으면 {@link #BLIND_TICKS} 틱 동안은 안 보여도 다가간다 (기둥 뒤 — 몸이 기둥을 돌아 시야를 찾는다).</li>
 *   <li><b>자리 지키기</b>: 곧장 걷기·돌아가기로 기본 공격이 닿게 되면 그 자리를 지킨다({@link Move#HOLD}) — 대상이
 *       {@link #LATCH_MOVE} 칸 넘게 움직이거나 안 닿게 될 때까지. 지키지 않으면 0.85 × reach 다시 길찾기가 보스를 길 끝(못 닿는 자리)으로
 *       끌어낸다. 트인 곳 길찾기로 닿은 경우는 지키지 않는다 (0.3.6.1 그대로).</li>
 * </ol>
 * 보스가 움직이는 동안(트인 곳 추격·원거리 카이팅)은 멈춤이 아니라서 아무 일도 없다. 기본 공격이 닿으면 멈춤·걷기는 처음으로.
 * 시간은 부른 횟수로 센다 — 패턴으로 바쁜 동안은 멈춤 시간에 안 들어간다. 그래도 못 닿으면 보스별 대응은 {@link AnswerWatch} 가 맡는다.
 */
public final class ChaseGuard {

    /** 이동량을 재는 창 (부른 횟수 = 틱). */
    public static final int WINDOW = 10;
    /** 한 창에서 이만큼도 못 움직이면 멈춤 (걷기 0.12칸/틱 × 10 = 1.2칸). */
    public static final double STALL_MOVE = 0.25;
    /** 곧장 걷기를 시작하는 거리 (떠다니는 보스는 거리 무관). 끝은 + 2칸. */
    public static final double STEER_RANGE = 6.0;
    /** 안 보이는 채 이만큼(1초) 멈춰 있으면 안 보여도 다가가 본다 (기둥 뒤 — 몸이 기둥을 돌아 시야를 찾는다). */
    public static final int BLIND_AFTER = 20;
    /** 안 보여도 다가가기를 이어 가는 틱. */
    public static final int BLIND_TICKS = 60;
    /** 자리 지키기: 대상이 지킨 자리(대상 발)에서 이만큼 넘게 움직이면 풂. */
    public static final double LATCH_MOVE = 0.75;

    public enum Move {
        /** 옛 추격 (길찾기 · 0.85 × reach 안이면 멈춤). */
        PATH,
        /** 곧장 걷기 (설 자리 또는 대상 쪽). */
        STEER,
        /** 움직이지 않음 (길찾기 꺼짐·안 걷는 보스·자리 지키기). */
        HOLD
    }

    /**
     * 한 틱 입력.
     * @param target    대상 (null = 없음)
     * @param canMove   보스가 지금 걸을 수 있는가 (길찾기 켜짐 + 이동 속도 &gt; 0)
     * @param inReach   기본 공격이 지금 닿는가 (보스 자기 거리 + 시야)
     * @param dist      보스 중심 ↔ 대상 수평 거리
     * @param noPath    땅 길찾기를 못 쓰는 보스 (떠다니는 보스 = 늘 true). 땅 보스는 false — 길 끝에 서면 멈춤 감시가 잡는다
     * @param sees      보스와 대상 사이 시야
     * @param bx        보스 x
     * @param bz        보스 z
     * @param tx        대상 발 x
     * @param tz        대상 발 z
     * @param detouring 보스가 지금 설 자리로 돌아가는 중 (길찾기)
     */
    public record Input(UUID target, boolean canMove, boolean inReach, double dist, boolean noPath, boolean sees,
                        double bx, double bz, double tx, double tz, boolean detouring) {}

    /**
     * @param move    이번 틱 움직임
     * @param stalled 지금 멈춤 상태 (창 안에서 0.25칸도 못 움직임)
     * @param moved   이번 틱에 창이 0.25칸 넘는 움직임으로 다시 잡혔다 (걷기·패턴 이동·순간이동)
     */
    public record Output(Move move, boolean stalled, boolean moved) {}

    private UUID target;
    private boolean steering;
    private boolean stalled;
    private boolean latched;
    private double lx, lz;
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
            return new Output(Move.HOLD, false, false);
        }
        boolean moved = false;
        if (anchorClock < 0) anchor(in);
        if (Math.hypot(in.bx() - ax, in.bz() - az) >= STALL_MOVE) {
            // 움직였다 (걷기·패턴 이동·순간이동) — 창 끝을 기다리지 않고 바로 멈춤이 아니다.
            // 시간은 부른 횟수라, 긴 시전(바쁨) 뒤에는 시전 전 멈춤이 남아 시전이 끝나자마자 멀리 있는 대상에게 뛰었다.
            stalled = false;
            moved = true;
            anchor(in);
        } else if (clock - anchorClock >= WINDOW) {
            stalled = true;
            anchor(in);
        }
        if (in.inReach()) {
            if (latched) {
                if (Math.hypot(in.tx() - lx, in.tz() - lz) > LATCH_MOVE) latched = false;
            } else if (steering || in.detouring()) {
                latched = true;
                lx = in.tx();
                lz = in.tz();
            }
            steering = false;
            stalled = false;
            blocked = 0;
            blind = 0;
            anchor(in);
            return new Output(latched ? Move.HOLD : Move.PATH, false, moved);
        }
        latched = false;
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
        return new Output(steering ? Move.STEER : Move.PATH, stalled, moved);
    }

    /** 지금 멈춤으로 센 틱 수 (진단용). */
    public int blocked() { return blocked; }

    public boolean steering() { return steering; }

    public boolean stalled() { return stalled; }

    /** 자리를 지키는 중 (곧장 걷기·돌아가기로 닿은 뒤). */
    public boolean latched() { return latched; }

    private void anchor(Input in) {
        anchorClock = clock;
        ax = in.bx();
        az = in.bz();
    }

    /** 처음으로 (대상은 그대로) — 보스가 대응 패턴으로 움직인 뒤 등. */
    public void reset() {
        steering = false;
        stalled = false;
        latched = false;
        blocked = 0;
        blind = 0;
        blindNext = 0;
        anchorClock = -1;
    }
}
