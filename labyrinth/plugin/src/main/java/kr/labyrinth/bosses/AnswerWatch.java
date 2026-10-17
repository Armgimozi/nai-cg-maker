package kr.labyrinth.bosses;

import java.util.Objects;
import java.util.UUID;

/**
 * 대응 감시 (bs363, Bukkit 무관 — 단위 테스트 대상, GDD §8.6).
 * <p>
 * 보스 기본 공격 거리는 보스마다 다르다 (0.3.6.1 그대로). 대신 보스가 틈 앞에서 막혀 못 닿는데 대상이 계속 보스를 때리면,
 * 보스는 <b>자기 패턴</b>으로 답한다 ({@link Boss#answer}). 이 클래스는 "언제 답하나" 만 정한다 — 무엇으로 답하는지는 보스마다.
 * <ul>
 *   <li><b>BAND</b> (걷는·떠다니는 보스): 대상이 칼끝 띠(플레이어 칼은 닿고 보스 기본 공격은 안 닿는 거리) 안에서 보스를 때리고,
 *       보스는 멈춰 있다(곧장 걷기·돌아가기로도 못 닫음) → 무장 {@link #ARM_BAND} 틱. 보조 셈: 대상이 가만히 선 채 {@link #STILL_FIRE} 빈 틱.</li>
 *   <li><b>PERCH</b>: 칼끝 띠 밖 높은 곳에서 가만히 서서 때림 + 보스 멈춤 + 걸어서 갈 설 자리 없음 → {@link #ARM_PERCH} 틱.</li>
 *   <li><b>STATIONARY</b> (걷지 않는 보스, 10층 심장): 칼끝 띠에서 때림 → {@link #ARM_STATIONARY} 틱.</li>
 * </ul>
 * 보스가 걷는 동안(트인 곳 거리 두기)과 원거리 카이팅(칼끝 띠 밖 + 대상이 움직임)은 셈이 쌓이지 않는다 — 대응 0번.
 * 대응 쿨은 보스 하나에 하나, 최소 {@link #MIN_COOLDOWN} 틱. 시간 단위는 틱.
 */
public final class AnswerWatch {

    /** 대상이 이 틱(3초) 안에 보스를 때렸으면 교전. */
    public static final int ENGAGE_TICKS = 60;
    /** 칼끝 띠 여유 (플레이어 손 닿음 + 이만큼). */
    public static final double BAND_SLACK = 0.5;
    /** 가만히: 기준점에서 {@link #STILL_MOVE} 칸 안으로 이만큼(2초). */
    public static final int STILL_TICKS = 40;
    public static final double STILL_MOVE = 1.0;
    /** 걷는 보스, 칼끝 띠 무장. */
    public static final int ARM_BAND = 40;
    /** 걷지 않는 보스 (10층). */
    public static final int ARM_STATIONARY = 30;
    /** 보조 셈: 가만히 선 대상에게 못 닿음 (빈 틱). */
    public static final int STILL_FIRE = 80;
    /** 칼끝 띠 밖, 정말 못 가는 높은 곳. */
    public static final int ARM_PERCH = 160;
    /** 띠·교전 밖으로 이만큼이면 무장 0. */
    public static final int OFF_RESET = 100;
    /** 걷는 보스가 걸어 창이 다시 잡히면 무장 −이만큼. */
    public static final int WALK_DRAIN = 10;
    /** 대응이 0(지금 못 함)을 돌려주면 이 틱 뒤 다시. */
    public static final int RETRY = 10;
    /** 0 이 이만큼 이어지면 쿨의 절반을 건다. */
    public static final int MAX_ZERO = 3;
    /** 대응 쿨 최소 (6초). */
    public static final int MIN_COOLDOWN = 120;
    /** 0 세 번 뒤 쉼의 최소 (3초). */
    public static final int MIN_HALF = 60;

    public enum Kind { BAND, PERCH, STATIONARY }

    /**
     * 한 틱 입력 (보스가 매 틱 만든다 — 바쁠 때도).
     * @param target       대상 (null = 없음)
     * @param tx           대상 발 x
     * @param ty           대상 발 y
     * @param tz           대상 발 z
     * @param free         보스가 지금 한가함 (안 바쁨·기절 아님) — 쏘기와 보조·PERCH 셈은 빈 틱만
     * @param stationary   걷지 않는 보스
     * @param reached      보스 기본 공격이 지금 닿음 (자기 거리 + 시야)
     * @param band         대상이 칼끝 띠 안 (판단 전용)
     * @param sees         보스 ↔ 대상 시야
     * @param targetHitAgo 대상이 보스를 마지막으로 때린 뒤 틱
     * @param anyHitAgo    파티 누구든 마지막으로 때린 뒤 틱
     * @param stalled      (빈 틱) 추격이 멈춤 상태
     * @param castStalled  (바쁜 틱) 지금 시전을 멈춘 채 시작했는가
     * @param moved        (빈 틱) 보스가 이번 틱 걸어 창이 다시 잡힘
     * @param noSpot       걸어서 갈 설 자리가 없음 (PERCH 조건)
     * @param allowed      지금 이 대상에게 대응해도 됨 (기절·무적·숨음·페이즈 전환 아님 + 보스별 조건)
     * @param gapOk        대응 패턴의 최소 간격이 지났음 (로테이션으로 쓴 직후 아님)
     * @param now          지금 틱
     */
    public record Input(UUID target, double tx, double ty, double tz, boolean free, boolean stationary, boolean reached, boolean band,
                        boolean sees, long targetHitAgo, long anyHitAgo, boolean stalled, boolean castStalled, boolean moved,
                        boolean noSpot, boolean allowed, boolean gapOk, long now) {}

    private UUID target;
    private int arm;
    private int off;
    private int su;
    private int ap;
    private boolean anchored;
    private double sx, sy, sz;
    private long stillSince;
    private long readyAt = Long.MIN_VALUE / 4;
    private long nextTry = Long.MIN_VALUE / 4;
    private int zeros;
    private boolean disabled;
    private int fired;

    /** @return 지금 쏠 대응 종류 (없으면 null). 쏘면 보스가 {@link #fired}/{@link #zero}/{@link #none} 중 하나를 부른다. */
    public Kind update(Input in) {
        if (disabled) return null;
        if (!Objects.equals(target, in.target())) {
            clearCounts();
            anchored = false;
            target = in.target();
        }
        if (in.target() == null) return null;
        // 가만히: 기준점에서 1칸 안으로 2초
        double dx = in.tx() - sx, dy = in.ty() - sy, dz = in.tz() - sz;
        if (!anchored || dx * dx + dy * dy + dz * dz > STILL_MOVE * STILL_MOVE) {
            anchored = true;
            sx = in.tx();
            sy = in.ty();
            sz = in.tz();
            stillSince = in.now();
        }
        boolean still = in.now() - stillSince >= STILL_TICKS;
        if (in.reached()) {
            clearCounts();
            return null;
        }
        boolean engaged = in.targetHitAgo() <= ENGAGE_TICKS || (in.anyHitAgo() <= ENGAGE_TICKS && still && in.band());
        boolean stuck = in.stationary() || (in.free() ? in.stalled() : in.castStalled());
        if (in.band() && engaged && in.sees() && in.allowed() && stuck) {
            arm++;
            off = 0;
        } else if (!in.band() || !engaged) {
            arm = Math.max(0, arm - 1);
            if (++off >= OFF_RESET) arm = 0;
        }
        if (!in.stationary() && in.moved()) arm = Math.max(0, arm - WALK_DRAIN);
        if (!in.stationary() && in.free()) {
            if (in.band() && engaged && still && in.sees() && in.allowed()) su++;
            else if (!still || !in.band()) su = 0;
            if (!in.band() && in.sees() && in.targetHitAgo() <= ENGAGE_TICKS && still && in.stalled() && in.noSpot() && in.allowed()) ap++;
            else ap = 0;
        }
        if (!in.free() || in.now() < readyAt || in.now() < nextTry || !in.gapOk() || !in.allowed() || !in.sees()) return null;
        if (in.stationary()) return in.band() && arm >= ARM_STATIONARY ? Kind.STATIONARY : null;
        if (in.band() && (arm >= ARM_BAND || su >= STILL_FIRE)) return Kind.BAND;
        if (!in.band() && ap >= ARM_PERCH) return Kind.PERCH;
        return null;
    }

    /** 보스 기본 공격이 대상에게 맞았다 → 셈 모두 0. */
    public void landed(UUID who) {
        if (Objects.equals(who, target)) clearCounts();
    }

    /** 대응을 썼다. @param cooldownTicks 대응 쿨 × 배율 (틱) */
    public void fired(long now, double cooldownTicks) {
        readyAt = now + Math.max(MIN_COOLDOWN, Math.round(cooldownTicks));
        zeros = 0;
        fired++;
        clearCounts();
    }

    /** 대응이 지금 못 함 (0) → 10틱 뒤 다시, 세 번이면 쿨의 절반. */
    public void zero(long now, double cooldownTicks) {
        nextTry = now + RETRY;
        if (++zeros >= MAX_ZERO) {
            zeros = 0;
            readyAt = now + Math.max(MIN_HALF, Math.round(cooldownTicks / 2));
            clearCounts();
        }
    }

    /** 이 보스는 대응이 없음 (−1) → 이번 싸움 동안 끔. */
    public void none() { disabled = true; }

    /** 패턴이 몸을 1칸 넘게 옮긴 시전이 끝났다 → 셈 모두 0. */
    public void bodyMoved() { clearCounts(); }

    private void clearCounts() {
        arm = 0;
        off = 0;
        su = 0;
        ap = 0;
    }

    public int arm() { return arm; }

    public int still() { return su; }

    public int perch() { return ap; }

    public long readyAt() { return readyAt; }

    public boolean disabled() { return disabled; }

    public int firedCount() { return fired; }
}
