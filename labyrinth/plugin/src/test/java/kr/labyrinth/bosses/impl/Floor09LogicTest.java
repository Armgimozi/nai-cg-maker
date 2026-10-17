package kr.labyrinth.bosses.impl;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import kr.labyrinth.bosses.BossMath;
import kr.labyrinth.bosses.MechanicScaling;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.Test;

/** 지하 9층 시계탑의 간수 테오라 (GDD §7.9) — 봉인석 배치·각도 창·종말 시계·진자·톱니 현·위치 기록·YAML 키. */
class Floor09LogicTest {

    private static final double EPS = 1e-9;

    @Test
    void sealCountAndClockPositions() {
        assertEquals(4, ClockLogic.sealCount(1, 4, 6));
        assertEquals(4, ClockLogic.sealCount(5, 4, 6));
        assertEquals(6, ClockLogic.sealCount(6, 4, 6), "6명 이상 = 6개");
        assertEquals(6, ClockLogic.sealCount(10, 4, 6));
        // 12·3·6·9시 = 북(−Z) · 동(+X) · 남(+Z) · 서(−X)
        assertArrayEquals(new double[]{270, 0, 90, 180}, ClockLogic.sealAngles(4), EPS);
        double[] six = ClockLogic.sealAngles(6);
        assertEquals(6, six.length);
        for (int i = 0; i < 6; i++) assertEquals(BossMath.norm(270 + 60 * i), six[i], EPS, "2시간 간격");
        // 12시 방향 = −Z (북쪽)
        assertEquals(0, BossMath.ax(ClockLogic.TWELVE), 1e-9);
        assertEquals(-1, BossMath.az(ClockLogic.TWELVE), 1e-9);
    }

    @Test
    void handSpeedAndWindow() {
        // 24초 한 바퀴 = 0.75°/틱, 16초 = 1.125°/틱, 반대 방향은 음수
        assertEquals(0.75, ClockLogic.degPerTick(24, 1), EPS);
        assertEquals(1.125, ClockLogic.degPerTick(16, 1), EPS);
        assertEquals(-1.125, ClockLogic.degPerTick(16, -1), EPS);
        assertEquals(0, ClockLogic.degPerTick(0, 1), EPS);
        // ±1.5초 창 = 24초 주기에서 ±22.5°, 16초에서 ±33.75°
        assertEquals(22.5, ClockLogic.windowDeg(1.5, 24), EPS);
        assertEquals(33.75, ClockLogic.windowDeg(1.5, 16), EPS);
        assertTrue(ClockLogic.isOpen(270, 270, 22.5));
        assertTrue(ClockLogic.isOpen(250, 270, 22.5));
        assertTrue(ClockLogic.isOpen(292.5, 270, 22.5), "경계 포함");
        assertFalse(ClockLogic.isOpen(293, 270, 22.5));
        assertTrue(ClockLogic.isOpen(355, 10, 22.5), "0° 넘어가는 경우");
        assertFalse(ClockLogic.isOpen(90, 270, 22.5));
    }

    @Test
    void windowLastsTwiceTheHalfWindowInTicks() {
        // 바늘을 틱마다 돌려서 한 봉인석이 열려 있는 틱 수 = 2 × 1.5초 = 60틱 (±1)
        for (double period : new double[]{24, 16}) {
            for (int dir : new int[]{1, -1}) {
                double win = ClockLogic.windowDeg(1.5, period);
                double hand = 0;
                int open = 0;
                for (int t = 0; t < period * 20; t++) {
                    if (ClockLogic.isOpen(hand, 90, win)) open++;
                    hand = BossMath.norm(hand + ClockLogic.degPerTick(period, dir));
                }
                assertTrue(Math.abs(open - 60) <= 1, "period " + period + " dir " + dir + " open " + open);
            }
        }
    }

    @Test
    void secondsUntilHandReachesSeal() {
        // 12시(270°)에서 시계 방향으로 3시(0°)까지 = 90° = 24초 주기의 6초
        assertEquals(6.0, ClockLogic.secondsUntil(270, 0, 1, 24), EPS);
        // 반대 방향이면 9시(180°)가 6초 뒤, 3시는 18초 뒤
        assertEquals(6.0, ClockLogic.secondsUntil(270, 180, -1, 24), EPS);
        assertEquals(18.0, ClockLogic.secondsUntil(270, 0, -1, 24), EPS);
        assertEquals(Double.POSITIVE_INFINITY, ClockLogic.secondsUntil(0, 90, 1, 0));
    }

    @Test
    void standProgressResetsOffSealOrClosed() {
        int p = 0;
        for (int i = 0; i < 29; i++) p = ClockLogic.standProgress(p, true, true);
        assertEquals(29, p);
        assertEquals(0, ClockLogic.standProgress(p, false, true), "벗어나면 처음부터");
        assertEquals(0, ClockLogic.standProgress(p, true, false), "닫히면 처음부터");
    }

    @Test
    void doomClock() {
        assertEquals(4800, ClockLogic.doomStartTicks(240, 1.0));
        assertEquals(6000, ClockLogic.doomStartTicks(240, 1.25), "쉬움 = 여유");
        assertEquals(3840, ClockLogic.doomStartTicks(240, 0.8), "악몽 = 빡빡");
        assertEquals(600, ClockLogic.doomStartTicks(5, 1.0), "최소 30초");
        assertEquals(1400, ClockLogic.adjust(1000, 20));
        assertEquals(800, ClockLogic.adjust(1000, -10));
        assertEquals(0, ClockLogic.adjust(100, -10), "0 아래로는 안 감");
        // 1분마다 +10%
        assertEquals(1.0, ClockLogic.rampMult(0, 0.1), EPS);
        assertEquals(1.0, ClockLogic.rampMult(1199, 0.1), EPS);
        assertEquals(1.1, ClockLogic.rampMult(1200, 0.1), EPS);
        assertEquals(1.3, ClockLogic.rampMult(3 * 1200 + 5, 0.1), EPS);
        assertEquals(1.0, ClockLogic.rampMult(-50, 0.1), EPS);
        // 표기
        assertEquals("4:00", ClockLogic.clock(4800));
        assertEquals("3:59", ClockLogic.clock(4780));
        assertEquals("0:01", ClockLogic.clock(1), "올림");
        assertEquals("0:00", ClockLogic.clock(0));
        assertEquals("1:05", ClockLogic.clock(1300));
    }

    @Test
    void pendulumPassesAlternateAndCoverLane() {
        int pt = 24, passes = 4;
        double half = 9;
        assertEquals(-9, ClockLogic.pendulumAlong(0, pt, passes, half), EPS);
        assertEquals(0, ClockLogic.pendulumAlong(12, pt, passes, half), 1e-9);
        assertEquals(9, ClockLogic.pendulumAlong(24, pt, passes, half), EPS, "1회 통과 끝 = 반대쪽 끝");
        assertEquals(0, ClockLogic.pendulumAlong(36, pt, passes, half), 1e-9);
        assertEquals(-9, ClockLogic.pendulumAlong(48, pt, passes, half), EPS, "되돌아옴");
        assertEquals(-9, ClockLogic.pendulumAlong(200, pt, passes, half), EPS, "끝나면 마지막 끝(4회 = 원위치)");
        assertEquals(0, ClockLogic.pendulumPass(0, pt, passes));
        assertEquals(1, ClockLogic.pendulumPass(30, pt, passes));
        assertEquals(3, ClockLogic.pendulumPass(999, pt, passes));
        // 한 번 지날 때 차선 위 모든 점을 쓸고 지나간다 (틱 사이 구간 + 여유)
        for (double x = -9; x <= 9; x += 0.5) {
            boolean hit = false;
            double prev = ClockLogic.pendulumAlong(0, pt, passes, half);
            for (int t = 1; t <= pt; t++) {
                double cur = ClockLogic.pendulumAlong(t, pt, passes, half);
                if (ClockLogic.swept(prev, cur, x, 0.9)) hit = true;
                prev = cur;
            }
            assertTrue(hit, "x=" + x);
        }
        assertFalse(ClockLogic.swept(0, 1, 3, 0.9));
        // 흔들림 각: 추가 줄 길이만큼 옆이면 거의 90° (±80° 근처로 자름), 가운데 0
        assertEquals(0, ClockLogic.pendulumAngle(0, 12), EPS);
        assertEquals(30, ClockLogic.pendulumAngle(6, 12), 1e-9);
        assertTrue(ClockLogic.pendulumAngle(50, 12) < 81);
        assertEquals(-30, ClockLogic.pendulumAngle(-6, 12), 1e-9);
    }

    @Test
    void laneStaysInsideChord() {
        assertEquals(9, ClockLogic.laneCenter(2, 26, 9), EPS, "끝 쪽 대상 = 차선을 안쪽으로");
        assertEquals(17, ClockLogic.laneCenter(25, 26, 9), EPS);
        assertEquals(13, ClockLogic.laneCenter(13, 26, 9), EPS);
        assertEquals(5, ClockLogic.laneCenter(1, 10, 9), EPS, "현이 짧으면 가운데");
    }

    @Test
    void chordThroughArena() {
        // 중심을 지나는 동서 방향 = 지름
        double[] c = ClockLogic.chord(0, 0, 1, 0, 0, 0, 14);
        assertNotNull(c);
        assertEquals(-14, c[0], 1e-9);
        assertEquals(0, c[1], 1e-9);
        assertEquals(28, c[2], 1e-9);
        // 중심에서 8 떨어진 평행선: 길이 2√(14²−8²)
        double[] d = ClockLogic.chord(3, 8, 1, 0, 0, 0, 14);
        assertNotNull(d);
        assertEquals(2 * Math.sqrt(14 * 14 - 64), d[2], 1e-9);
        assertEquals(14, Math.hypot(d[0], d[1]), 1e-9, "시작점은 원 위");
        // 원 밖으로 지나가면 null
        assertNull(ClockLogic.chord(0, 20, 1, 0, 0, 0, 14));
        assertNull(ClockLogic.chord(0, 0, 0, 0, 0, 0, 14));
        // 굴러간 거리 = 반지름 × |각|
        assertEquals(-Math.PI, ClockLogic.rollAngle(Math.PI, 1), EPS);
        assertEquals(0, ClockLogic.rollAngle(5, 0), EPS);
    }

    @Test
    void positionHistoryRingBuffer() {
        int cap = PositionHistory.capacityFor(8, 0.5);
        assertEquals(18, cap);
        PositionHistory h = new PositionHistory(cap);
        assertNull(h.latest());
        assertNull(h.ago(100, 10));
        // 0.5초(10틱)마다 x = 틱 기록, 30초치 → 오래된 건 덮어씀
        for (long t = 0; t <= 600; t += 10) h.record(t, t, 64, 0, 0, 0);
        assertEquals(cap, h.size());
        assertEquals(600, h.latest()[0], EPS);
        assertEquals(500, h.ago(600, 100)[0], EPS, "5초 전");
        assertEquals(480, h.ago(600, 120)[0], EPS, "6초 전");
        assertEquals(490, h.ago(605, 110)[0], EPS, "그 시점 이전의 가장 최근");
        assertEquals(430, h.ago(600, 10_000)[0], EPS, "그만큼 오래된 기록이 없으면 가장 오래된 것");
        double[] copy = h.latest();
        copy[0] = -1;
        assertEquals(600, h.latest()[0], EPS, "복사본을 돌려준다");
        h.clear();
        assertEquals(0, h.size());
    }

    @Test
    void yamlKeysMatchGdd() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        BossDef d = c.bosses().get("floor09_clock_warden");
        assertEquals(9, d.floor());
        assertEquals("timed_seals", d.core());
        assertEquals(68000, d.hp(), EPS);
        assertEquals(List.of(1.0, 0.6, 0.25), d.phases());
        assertEquals(14, d.arena().dbl("radius", 0), EPS);
        assertEquals(12, d.arena().dbl("seal_ring_radius", 0), EPS);
        Params ts = d.pattern("timed_seals");
        assertEquals(24, ts.phased("hand_period", 1, 0), EPS);
        assertEquals(16, ts.phased("hand_period", 2, 0), EPS);
        assertEquals(16, ts.phased("hand_period", 3, 0), EPS, "3페이즈도 16초(반대 방향)");
        assertTrue(ts.bool("p3_reverse", false));
        assertEquals(1.5, ts.scaled("window", 4, 0), EPS);
        assertEquals(2.0, ts.scaled("window", 1, 0), EPS, "솔로 창 완화");
        assertEquals(1.5, ts.scaled("stand_time", 3, 0), EPS);
        assertEquals(0.03, ts.dbl("seal_damage_pct", 0), EPS);
        assertEquals(2.0, ts.dbl("seal_stun", 0), EPS);
        assertEquals(5, ts.dbl("rewind_seconds", 0), EPS);
        Params dc = d.pattern("doom_clock");
        assertEquals(240, dc.scaled("start_seconds", 4, 0), EPS);
        assertEquals(270, dc.scaled("start_seconds", 1, 0), EPS);
        assertEquals(20, dc.dbl("seal_bonus", 0), EPS);
        assertEquals(10, dc.dbl("wrong_penalty", 0), EPS);
        assertEquals(0.10, dc.dbl("damage_ramp_per_minute", 0), EPS);
        assertEquals(1.4, d.pattern("hand_strike").dbl("damage", 0), EPS);
        assertEquals(90, d.pattern("hand_strike").dbl("angle", 0), EPS);
        assertEquals(1.8, d.pattern("pendulum_sweep").dbl("damage", 0), EPS);
        assertEquals(3, d.pattern("pendulum_sweep").dbl("width", 0), EPS);
        assertEquals(6, d.pattern("rewind_echo").dbl("delay", 0), EPS);
        assertEquals(2.5, d.pattern("rewind_echo").dbl("radius", 0), EPS);
        // 톱니 줄 수 = 3 + ⌊(n−1)×0.34⌋
        Params g = d.pattern("gear_storm");
        assertEquals(3, new MechanicScaling(1, "normal", 2, false).count(g, "lines", 3, 8));
        assertEquals(3, new MechanicScaling(3, "normal", 2, false).count(g, "lines", 3, 8));
        assertEquals(4, new MechanicScaling(4, "normal", 2, false).count(g, "lines", 3, 8));
        assertEquals(6, new MechanicScaling(10, "normal", 2, false).count(g, "lines", 3, 8));
        // rotation: 톱니 폭풍은 2페이즈부터, 시간 봉인·종말 시계는 rotation 밖(상시)
        assertFalse(d.rotation().get(1).contains("gear_storm"));
        assertTrue(d.rotation().get(2).contains("gear_storm"));
        assertFalse(d.rotation().get(3).contains("timed_seals"));
        assertFalse(d.rotation().get(3).contains("doom_clock"));
        // 대사·점진 힌트 3단계
        assertNotNull(d.line("doom"));
        assertEquals(3, d.raw().strings("hints").size());
        // fx 모델이 전부 있다
        for (String m : List.of(ts.str("fx_seal", ""), ts.str("fx_seal_open", ""), ts.str("fx_hand", ""), ts.str("fx_hand_reverse", ""),
                d.pattern("pendulum_sweep").str("fx", ""), g.str("fx", ""), "telegraph_line", "telegraph_circle", "telegraph_cone")) {
            assertTrue(c.fxModels().containsKey(m), "fx.yml 에 없음: " + m);
        }
    }

    // ── 대응: 벽을 따라가는 진자 (bs363, GDD §8.6) ───────────────────────

    /** 차선 가운데 위치 (보스 코드와 같은 식) 에서 대상까지 차선 방향 거리 ≤ 반 길이 → 차선이 대상을 지난다. */
    private static boolean laneCoversTarget(double[] lane, double tx, double tz, double length) {
        double half = Math.min(lane[4] / 2, length / 2);
        double st = (tx - lane[2]) * lane[0] + (tz - lane[3]) * lane[1];
        double mid = ClockLogic.laneCenter(st, lane[4], half);
        double lat = Math.abs((tx - lane[2]) * lane[1] - (tz - lane[3]) * lane[0]);
        return Math.abs(st - mid) <= half + 1e-9 && lat < 1e-6;
    }

    @Test
    void answerLaneFollowsTheWallNearTheEdge() {
        // 아레나 반경 14, 대상이 벽 3칸 안 (중심에서 12.5) 동쪽, 보스는 안쪽
        double r = 14, tx = 12.5, tz = 0;
        double[] lane = ClockLogic.answerLane(tx, tz, 9, 0, 0, 0, r, 3.0, 0.5);
        assertNotNull(lane);
        // 방향 = 접선 (중심 → 대상에 수직)
        assertEquals(0, lane[0] * tx + lane[1] * tz, 1e-9, "접선");
        assertEquals(1, Math.hypot(lane[0], lane[1]), 1e-9);
        // 현 반경 = r + 0.5: 길이 2√(14.5² − 12.5²)
        assertEquals(2 * Math.sqrt(14.5 * 14.5 - 12.5 * 12.5), lane[4], 1e-9);
        assertTrue(laneCoversTarget(lane, tx, tz, 18), "차선이 대상을 지남");
        // 벽 바로 앞 (13.6) 도 벽을 따라간다
        double[] edge = ClockLogic.answerLane(0, -13.6, 0, -9, 0, 0, r, 3.0, 0.5);
        assertNotNull(edge);
        assertEquals(0, edge[0] * 0 + edge[1] * -13.6, 1e-9);
        assertTrue(laneCoversTarget(edge, 0, -13.6, 18));
    }

    @Test
    void answerLaneInsideRunsFromBossToTarget() {
        // 안쪽 (중심에서 6): 방향 = 보스 → 대상, 현 반경 r − 1 (로테이션과 같음)
        double r = 14;
        double[] lane = ClockLogic.answerLane(6, 0, 2, 3, 0, 0, r, 3.0, 0.5);
        assertNotNull(lane);
        double dx = 4 / 5.0, dz = -3 / 5.0;
        assertEquals(dx, lane[0], 1e-9);
        assertEquals(dz, lane[1], 1e-9);
        double[] ch = ClockLogic.chord(6, 0, dx, dz, 0, 0, r - 1);
        assertEquals(ch[2], lane[4], 1e-9);
        assertTrue(laneCoversTarget(lane, 6, 0, 18));
    }

    @Test
    void answerLaneFallsBackOnShortChords() {
        // 벽 밖까지 밀려난 대상 (중심에서 14.6 > r + 0.5): 접선 현 없음 → 보스 → 대상 · r − 1
        double[] lane = ClockLogic.answerLane(14.6, 0, 10, 0, 0, 0, 14, 3.0, 0.5);
        assertNotNull(lane);
        assertEquals(1, lane[0], 1e-9);
        assertEquals(0, lane[1], 1e-9);
        // 접선 현이 4칸보다 짧은 자리 (14.4: 2√(14.5² − 14.4²) ≈ 3.4) → 되돌림
        double[] short4 = ClockLogic.answerLane(14.4, 0, 10, 0, 0, 0, 14, 3.0, 0.5);
        assertNotNull(short4);
        assertEquals(1, short4[0], 1e-9, "보스 → 대상");
        // 그래도 현이 없으면 null (아주 작은 원)
        assertNull(ClockLogic.answerLane(30, 0, 29, 1, 0, 0, 3, 3.0, 0.5));
        // 보스가 대상 위에 서 있어도 (방향 없음) 결정적 방향
        assertNotNull(ClockLogic.answerLane(2, 0, 2, 0, 0, 0, 14, 3.0, 0.5));
    }
}
