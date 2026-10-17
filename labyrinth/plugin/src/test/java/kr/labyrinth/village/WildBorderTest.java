package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.village.WildBorder.Action;
import kr.labyrinth.village.WildBorder.Decision;
import kr.labyrinth.village.WildBorder.Record;
import kr.labyrinth.village.WildBorder.Square;
import org.junit.jupiter.api.Test;

/** 마을 둘레 월드 경계 (config wild.border · border_margin, 0.3.5.1): 계산 · 켬/끔 판정 (관리자 경계 지키기). */
class WildBorderTest {

    /** 배포 마을 '등불 어귀 마을'과 같은 중심·반경. */
    static final int[] CENTER = {-136, 64, 16};

    @Test
    void squareCoversVillagePlusMargin() {
        Square s = WildBorder.compute(CENTER, 37, List.of(), 30);
        // 블록 -173..-99 = 땅 -173 ~ -98 (75칸), 가운데 -135.5 · 한 변 75 + 30 × 2
        assertEquals(-135.5, s.x(), 1e-9);
        assertEquals(16.5, s.z(), 1e-9);
        assertEquals(135, s.size(), 1e-9);
        assertEquals(WildBorder.WARNING_DISTANCE, s.warning());
        assertTrue(s.containsBlocks(-173, -21, -99, 53), "마을 상자 전체");
        assertTrue(s.contains(-173 - 30, 16), "가장자리 + 30칸까지");
        assertFalse(s.contains(-173 - 31, 16), "그 너머는 밖");
        assertEquals("중심 (-135.5, 16.5) · 한 변 135칸", WildBorder.describe(s));
    }

    @Test
    void protectBoxesWidenTheSquare() {
        // 보호 상자 하나가 마을 반경 밖 동쪽으로 길게 (0.3.6 광산 구역 같은) → 경계가 넓어지고 상자를 덮는다
        VillageMeta.Box mine = new VillageMeta.Box(-90, 10, -10, -20, 70, 30);
        Square before = WildBorder.compute(CENTER, 37, List.of(), 30);
        Square after = WildBorder.compute(CENTER, 37, List.of(mine), 30);
        assertTrue(after.size() > before.size());
        assertTrue(after.containsBlocks(mine.x0(), mine.z0(), mine.x1(), mine.z1()));
        assertTrue(after.containsBlocks(-173, -21, -99, 53), "마을도 그대로 안");
        // 정사각형 = 긴 쪽(x: -173 ~ -19 = 154칸) 기준, 가운데는 상자들의 가운데
        assertEquals(154 + 60, after.size(), 1e-9);
        assertEquals((-173 + -19) / 2.0, after.x(), 1e-9);
        assertEquals(16.5, after.z(), 1e-9);
        assertEquals(List.of(), WildBorder.boxesOutside(after, List.of(mine)));
        assertEquals(List.of(0), WildBorder.boxesOutside(before, List.of(mine)));
        // 뒤집힌 모서리(x1 < x0)도 같은 상자
        Square flipped = WildBorder.compute(CENTER, 37, List.of(new VillageMeta.Box(-20, 10, 30, -90, 70, -10)), 30);
        assertTrue(after.same(flipped));
    }

    @Test
    void zeroMarginStillHoldsEveryBox() {
        List<VillageMeta.Box> boxes = List.of(new VillageMeta.Box(-148, 56, 3, -126, 73, 25), new VillageMeta.Box(-168, 58, 8, -154, 83, 26),
                new VillageMeta.Box(-200, 60, -40, -190, 70, -30));
        Square s = WildBorder.compute(CENTER, 37, boxes, 0);
        assertEquals(List.of(), WildBorder.boxesOutside(s, boxes));
        assertTrue(s.containsBlocks(-200, -40, -99, 53));
        assertFalse(s.contains(-200.5, -35), "가장자리 바로 밖");
        // 음수 margin 은 0 으로
        assertTrue(WildBorder.compute(CENTER, 37, boxes, -5).same(s));
    }

    @Test
    void namedPointsOutsideAreListed() {
        Square s = WildBorder.compute(CENTER, 37, List.of(), 30);
        Map<String, double[]> pts = new LinkedHashMap<>();
        pts.put("광장", new double[] {-128.5, 14.5});
        pts.put("입구", new double[] {-163.5, 17.5});
        pts.put("먼 곳", new double[] {500, 500});
        pts.put("없음", null);
        assertEquals(List.of("먼 곳", "없음"), WildBorder.outside(s, pts));
    }

    @Test
    void bundledVillageMarkersAreAllInside() {
        assumeTrue(BundledVillageTest.read("village/layout.json") != null, "청사진이 아직 없음");
        VillageLibrary lib = VillageLibrary.load(BundledVillageTest::read);
        assumeTrue(lib.ok());
        TerrainGrid flat = Fixtures.flat(lib.planner.reach() + 4, 64);
        for (int t = 0; t < 4; t++) {
            Plan p = lib.planner.plan(flat, 0, 0, t, true);
            assertTrue(p.ok(), "평지 회전 " + t + ": " + p.reason);
            VillageMeta m = Markers.meta(p, lib.layout);
            for (int margin : new int[] {0, 30}) {
                Square s = WildBorder.compute(m, margin);
                Map<String, double[]> pts = new LinkedHashMap<>();
                pts.put("광장", new double[] {m.spawn.x(), m.spawn.z()});
                if (m.entrance != null) pts.put("입구", new double[] {m.entrance.x(), m.entrance.z()});
                for (Map.Entry<String, VillageMeta.Pos> n : m.npcs.entrySet()) pts.put(n.getKey(), new double[] {n.getValue().x(), n.getValue().z()});
                assertEquals(List.of(), WildBorder.outside(s, pts), "회전 " + t + " margin " + margin);
                assertEquals(List.of(), WildBorder.boxesOutside(s, m.protect), "회전 " + t + " margin " + margin);
                assertFalse(m.protect.isEmpty());
            }
        }
    }

    // ── 켬/끔 판정 ───────────────────────────────────────────────────────

    static final Square TARGET = WildBorder.compute(CENTER, 37, List.of(), 30);
    static final Square VANILLA = WildBorder.vanilla(WildBorder.VANILLA_WARNING);
    static final Square ADMIN = new Square(0, 0, 2000, 5);

    @Test
    void freshWorldGetsVillageBorderAndRemembersVanilla() {
        Decision d = WildBorder.decide(true, VANILLA, TARGET, null);
        assertEquals(Action.APPLY, d.action());
        assertTrue(d.set().same(TARGET));
        assertTrue(d.record().ours().same(TARGET));
        assertTrue(d.record().previous().vanillaDefault());
        // 다음 시작: 이미 우리 경계 → 아무것도 안 함, 기록 그대로
        Decision again = WildBorder.decide(true, TARGET, TARGET, d.record());
        assertEquals(Action.NONE, again.action());
        assertEquals(d.record(), again.record());
    }

    @Test
    void growingVillageMovesOurBorderButKeepsTheOriginalPrevious() {
        Record rec = new Record(TARGET, VANILLA);
        Square wider = WildBorder.compute(CENTER, 37, List.of(new VillageMeta.Box(-90, 10, -10, -20, 70, 30)), 30);
        Decision d = WildBorder.decide(true, TARGET, wider, rec);
        assertEquals(Action.APPLY, d.action());
        assertTrue(d.set().same(wider));
        assertTrue(d.record().previous().vanillaDefault(), "처음 경계를 기억 (중간 단계 경계가 아니라)");
        // margin 을 바꿔도 같은 길
        Decision m = WildBorder.decide(true, TARGET, WildBorder.compute(CENTER, 37, List.of(), 10), rec);
        assertEquals(Action.APPLY, m.action());
    }

    @Test
    void adminBorderIsNeverClobbered() {
        // 처음부터 관리자가 정한 경계
        Decision d = WildBorder.decide(true, ADMIN, TARGET, null);
        assertEquals(Action.ADMIN, d.action());
        assertNull(d.set());
        assertNull(d.record());
        // 우리가 정한 뒤 관리자가 /worldborder 로 바꿈 → 그대로 두고 기록 버림
        Decision changed = WildBorder.decide(true, ADMIN, TARGET, new Record(TARGET, VANILLA));
        assertEquals(Action.ADMIN, changed.action());
        assertNull(changed.record());
        // 그 뒤 끄면: 기록이 없으니 아무것도 안 함
        assertEquals(Action.NONE, WildBorder.decide(false, ADMIN, TARGET, null).action());
        // 관리자 경계가 마을 경계와 우연히 같으면 우리 것으로 기억 (이전 = 바닐라)
        Decision same = WildBorder.decide(true, TARGET, TARGET, null);
        assertEquals(Action.NONE, same.action());
        assertTrue(same.record().previous().vanillaDefault());
    }

    @Test
    void turningOffRestoresOnlyOurOwnBorder() {
        Square prevAdmin = new Square(10, 10, 5000, 7);
        Record rec = new Record(TARGET, prevAdmin);
        Decision d = WildBorder.decide(false, TARGET, TARGET, rec);
        assertEquals(Action.RESTORE, d.action());
        assertTrue(d.set().same(prevAdmin));
        assertEquals(7, d.set().warning());
        assertNull(d.record());
        // 꺼진 사이 관리자가 바꿨으면 되돌리지 않고 기록만 버림
        Decision forget = WildBorder.decide(false, ADMIN, TARGET, rec);
        assertEquals(Action.FORGET, forget.action());
        assertNull(forget.set());
        assertNull(forget.record());
        // 기록도 없으면 아무것도 안 함
        Decision none = WildBorder.decide(false, VANILLA, TARGET, null);
        assertEquals(Action.NONE, none.action());
        // 마을이 없음(target null) = 끔과 같음
        assertEquals(Action.RESTORE, WildBorder.decide(true, TARGET, null, rec).action());
    }

    @Test
    void vanillaResetWhileRecordedIsReapplied() {
        // 기록은 있는데 경계가 바닐라로 돌아가 있음 (level.dat 을 되돌림 등) → 다시 정함
        Decision d = WildBorder.decide(true, VANILLA, TARGET, new Record(TARGET, VANILLA));
        assertEquals(Action.APPLY, d.action());
        assertTrue(d.record().previous().vanillaDefault());
    }

    @Test
    void forceOverwritesAdminButRemembersIt() {
        Decision d = WildBorder.force(ADMIN, TARGET, null);
        assertEquals(Action.APPLY, d.action());
        assertTrue(d.record().previous().same(ADMIN));
        // 이미 우리 것이면 원래 이전 경계를 그대로
        Decision ours = WildBorder.force(TARGET, TARGET, new Record(TARGET, VANILLA));
        assertTrue(ours.record().previous().vanillaDefault());
    }

    @Test
    void sameIgnoresWarningAndTinyFloatNoise() {
        assertTrue(TARGET.same(TARGET.withWarning(2)));
        assertTrue(TARGET.same(new Square(TARGET.x() + 0.001, TARGET.z(), TARGET.size() - 0.001, 6)));
        assertFalse(TARGET.same(new Square(TARGET.x() + 1, TARGET.z(), TARGET.size(), 6)));
        assertFalse(TARGET.same(null));
        assertTrue(VANILLA.vanillaDefault());
        assertFalse(TARGET.vanillaDefault());
    }
    // ── 줄지 않는 경계 (0.3.7 review R6) ──

    @Test
    void growNeverShrinks() {
        // 지난번 우리 경계 = 광산까지 넓힌 것 · 이번 계산(target)은 마을만 (광산 기록을 못 읽음 등) → 지난번 그대로
        Square wide = WildBorder.compute(CENTER, 37, List.of(new VillageMeta.Box(-90, 10, -10, -20, 70, 30)), 30);
        Record rec = new Record(wide, VANILLA);
        Square g = WildBorder.grow(TARGET, rec);
        assertTrue(g.same(wide));
        assertTrue(g.containsBlocks(-173, -21, -99, 53));
        assertEquals(Action.NONE, WildBorder.decide(true, wide, g, rec).action(), "줄이지 않으니 할 일 없음");
        // 기록 없음 · 바닐라 기록 → target 그대로
        assertTrue(WildBorder.grow(TARGET, null).same(TARGET));
        assertTrue(WildBorder.grow(TARGET, new Record(VANILLA, VANILLA)).same(TARGET));
        assertTrue(WildBorder.grow(TARGET, new Record(TARGET, VANILLA)).same(TARGET));
        // 경고 거리는 target 것
        assertEquals(3, WildBorder.grow(TARGET.withWarning(3), rec).warning());
    }

    @Test
    void growUnionsNewDistrict() {
        // 지난번 = 마을 + 광산(동쪽) · 이번 = 마을 + 집 구역(남서쪽 -178..-116 · 26..105) → 둘을 다 덮는 정사각형
        VillageMeta.Box mine = new VillageMeta.Box(-90, 10, -10, -20, 70, 30);
        VillageMeta.Box homes = new VillageMeta.Box(-178, 58, 26, -116, 110, 105);
        Square last = WildBorder.compute(CENTER, 37, List.of(mine), 30);
        Square now = WildBorder.compute(CENTER, 37, List.of(homes), 30);
        Square g = WildBorder.grow(now, new Record(last, VANILLA));
        assertTrue(g.size() >= last.size() && g.size() >= now.size());
        for (Square s : new Square[] {last, now}) {
            assertTrue(g.contains(s.minX(), s.minZ()) && g.contains(s.maxX(), s.maxZ()), "앞뒤 경계를 다 덮음");
        }
        assertTrue(g.containsBlocks(mine.x0(), mine.z0(), mine.x1(), mine.z1()));
        assertTrue(g.containsBlocks(homes.x0(), homes.z0(), homes.x1(), homes.z1()));
        // 관리자 apply = 이번 계산 그대로 (줄 수 있음 — WildService.forceBorder 는 grow 를 거치지 않음)
        Decision f = WildBorder.force(last, now, new Record(last, VANILLA));
        assertTrue(f.set().same(now));
        assertTrue(f.record().previous().vanillaDefault());
    }
}
