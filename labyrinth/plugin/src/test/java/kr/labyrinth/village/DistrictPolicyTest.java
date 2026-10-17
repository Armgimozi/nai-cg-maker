package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.BitSet;
import java.util.List;
import kr.labyrinth.village.DistrictPolicy.Item;
import kr.labyrinth.village.DistrictPolicy.Step;
import kr.labyrinth.village.DistrictMeta.State;
import kr.labyrinth.village.DistrictPolicy.Startup;
import org.junit.jupiter.api.Test;

/**
 * 구역 상태 기계 (0.3.6.1 CONTRACT §2.13 5·6): 시작할 때 할 일 · 짓다 꺼짐(building) → 되돌린 뒤 처음부터 · 지운 구역은 다시 짓지 않음 ·
 * 기록 파일 왕복 (state·자리·백업·영역·points).
 */
class DistrictPolicyTest {

    @Test
    void startupDecisions() {
        // 기록 없음: 서버팩 월드 + 자동 짓기 → 짓기
        assertEquals(Startup.AUTO_BUILD, DistrictPolicy.onStart(null, true, true, true));
        // 자동 짓기 끔 → 아무것도
        assertEquals(Startup.NONE, DistrictPolicy.onStart(null, true, false, true));
        // 마을 없는 월드 → 짓지 않음 (광산은 관리소로)
        assertEquals(Startup.NO_VILLAGE, DistrictPolicy.onStart(null, false, true, true));
        // 서버팩 월드가 아님 → 저절로 짓지 않고 미리 보기를 권함
        assertEquals(Startup.UNKNOWN_WORLD, DistrictPolicy.onStart(null, true, true, false));
        // 짓다가 꺼짐 → 무엇보다 먼저 되돌리기 (자동 짓기를 꺼 두었어도 반쯤 지은 것은 되돌린다)
        assertEquals(Startup.RECOVER, DistrictPolicy.onStart(State.BUILDING, true, true, true));
        assertEquals(Startup.RECOVER, DistrictPolicy.onStart(State.BUILDING, true, false, false));
        // 지어짐 · 지움 → 아무것도 (지운 구역을 저절로 다시 짓지 않는다)
        assertEquals(Startup.NONE, DistrictPolicy.onStart(State.BUILT, true, true, true));
        assertEquals(Startup.NONE, DistrictPolicy.onStart(State.REMOVED, true, true, true));
    }

    @Test
    void interruptedBuildRestartsFromScratch() {
        // building → (되돌린 뒤 기록을 지움) → 기록 없음과 같은 판단 = 처음부터 다시
        Startup first = DistrictPolicy.onStart(State.BUILDING, true, true, true);
        assertEquals(Startup.RECOVER, first);
        Startup after = DistrictPolicy.onStart(null, true, true, true);
        assertEquals(Startup.AUTO_BUILD, after);
    }

    @Test
    void commandsGuardState() {
        assertNull(DistrictPolicy.canBuild(null, true));
        assertNull(DistrictPolicy.canBuild(State.REMOVED, true), "지운 뒤 다시 짓기는 됨");
        assertNotNull(DistrictPolicy.canBuild(State.BUILT, true));
        assertNotNull(DistrictPolicy.canBuild(State.BUILDING, true));
        assertNotNull(DistrictPolicy.canBuild(null, false), "마을 없음");
        assertNull(DistrictPolicy.canRemove(State.BUILT, true));
        assertNull(DistrictPolicy.canRemove(State.BUILDING, true), "짓다 멈춘 것도 지울 수 있음 (짓기 전 백업으로)");
        assertNotNull(DistrictPolicy.canRemove(State.BUILT, false), "백업 없음");
        assertNotNull(DistrictPolicy.canRemove(State.REMOVED, true));
        assertNotNull(DistrictPolicy.canRemove(null, true));
    }

    @Test
    void noticeOncePerDay() {
        assertTrue(DistrictPolicy.notifyToday(Long.MIN_VALUE, 20_000));
        assertFalse(DistrictPolicy.notifyToday(20_000, 20_000));
        assertTrue(DistrictPolicy.notifyToday(20_000, 20_001));
    }

    @Test
    void metaRoundTrip() throws Exception {
        DistrictMeta d = new DistrictMeta();
        d.id = "mine";
        d.name = "광산 마을";
        d.state = State.BUILDING;
        d.site = "east";
        d.villageBuildId = "a06800d8-7a5d-452d-b3eb-79364ebfac99";
        d.backup = DistrictMeta.backupName("mine");
        d.safeMargin = 8;
        d.meta.name = "광산 마을";
        d.meta.center = new int[] {-82, 66, 17};
        d.meta.radius = 40;
        d.meta.buildId = "b-1";
        d.meta.points.put("mine_exit", new VillageMeta.Pos(-65.5, 67, 15.5, 90f));
        d.meta.npcs.put("miner", new VillageMeta.Pos(-71.5, 67, 13.5, 90f));
        d.meta.interact.put("-66,67,15", "mine_lift");
        d.meta.protect.add(new VillageMeta.Box(-73, 58, 8, -59, 92, 22));
        BitSet changed = new BitSet();
        changed.set(5);
        d.meta.terrain = new VillageMeta.TerrainRec(-100, 0, 4, 60, new byte[16], changed);
        d.region.set(5);
        d.region.set(6);
        DistrictMeta back = DistrictMeta.fromYaml(d.toYaml());
        assertEquals("mine", back.id);
        assertEquals(State.BUILDING, back.state);
        assertTrue(back.active());
        assertFalse(back.built());
        assertEquals("east", back.site);
        assertEquals(d.villageBuildId, back.villageBuildId);
        assertEquals("labyrinth-district-mine.backup.gz", back.backup);
        assertEquals(-65.5, back.meta.points.get("mine_exit").x(), 1e-9);
        assertEquals("mine_lift", back.meta.interact.get("-66,67,15"));
        assertEquals(1, back.meta.protect.size());
        // 영역: 칸 5 = (−99, 1), 6 = (−98, 1) · 7 은 아님
        assertTrue(back.inRegion(-99, 1));
        assertTrue(back.inRegion(-98, 1));
        assertFalse(back.inRegion(-97, 1));
        assertFalse(back.inRegion(-200, 1), "격자 밖");
        back.state = State.BUILT;
        assertTrue(DistrictMeta.fromYaml(back.toYaml()).built());
        back.state = State.REMOVED;
        DistrictMeta removed = DistrictMeta.fromYaml(back.toYaml());
        assertEquals(State.REMOVED, removed.state);
        assertFalse(removed.active(), "지운 구역은 보호·우클릭·NPC 없음");
        assertEquals("labyrinth-district-mine.yml", DistrictMeta.fileName("mine"));
    }
    // ── 여러 구역 차례 (0.3.7 review R8) ──

    private static Item mine(State st, boolean auto, boolean tried) { return new Item("mine", st, true, auto, true, tried); }
    private static Item homes(State st, boolean auto, boolean tried) { return new Item("homes", st, true, auto, true, tried); }

    private static String ids(List<Step> steps) {
        StringBuilder b = new StringBuilder();
        for (Step s : steps) b.append(b.length() == 0 ? "" : " ").append(s.id()).append('=').append(s.action());
        return b.toString();
    }

    @Test
    void mineFirstThenHomes() {
        // 둘 다 기록 없음 → 광산부터 (집은 이번 차례에 보지 않음)
        assertEquals("mine=AUTO_BUILD", ids(DistrictPolicy.plan(List.of(mine(null, true, false), homes(null, true, false)))));
        // 광산을 지어 봄(끝남·막힘 — tried) → 다음 부름에 집
        assertEquals("homes=AUTO_BUILD", ids(DistrictPolicy.plan(List.of(mine(State.BUILT, true, true), homes(null, true, false)))));
        assertEquals("homes=AUTO_BUILD", ids(DistrictPolicy.plan(List.of(mine(null, true, true), homes(null, true, false)))),
                "광산 짓기가 막혀(기록 없음 그대로) 끝나도 집은 짓는다");
    }

    @Test
    void homesBuildsWhenMineDoneOrOff() {
        // 0.3.6.1 월드 (광산 지어짐) → 광산 할 일 없음, 집 짓기
        assertEquals("mine=NONE homes=AUTO_BUILD", ids(DistrictPolicy.plan(List.of(mine(State.BUILT, true, false), homes(null, true, false)))));
        // 광산을 지웠음 → 다시 짓지 않고 집으로
        assertEquals("mine=NONE homes=AUTO_BUILD", ids(DistrictPolicy.plan(List.of(mine(State.REMOVED, true, false), homes(null, true, false)))));
        // 광산 꺼짐 (mine.enabled false · auto_build false) → 집으로
        assertEquals("mine=NONE homes=AUTO_BUILD", ids(DistrictPolicy.plan(List.of(mine(null, false, false), homes(null, true, false)))));
        // 집 자동 짓기 끔 → 아무것도
        assertEquals("mine=NONE homes=NONE", ids(DistrictPolicy.plan(List.of(mine(State.BUILT, true, false), homes(null, false, false)))));
        // 둘 다 지어짐
        assertEquals("mine=NONE homes=NONE", ids(DistrictPolicy.plan(List.of(mine(State.BUILT, true, false), homes(State.BUILT, true, false)))));
    }

    @Test
    void interruptedBuildIsRecoveredFirst() {
        // 집을 짓다 꺼짐 → 되돌리기 (자동 짓기를 꺼 두었어도)
        assertEquals("mine=NONE homes=RECOVER", ids(DistrictPolicy.plan(List.of(mine(State.BUILT, true, false), homes(State.BUILDING, false, false)))));
        // 광산을 짓다 꺼짐 → 광산 되돌리기에서 멈춤 (끝나면 다시 불러 광산 처음부터 → 그다음 집)
        assertEquals("mine=RECOVER", ids(DistrictPolicy.plan(List.of(mine(State.BUILDING, true, false), homes(null, true, false)))));
        // 마을 없음 · 배포 월드 아님 → 둘 다 안내만
        assertEquals("mine=NO_VILLAGE homes=NO_VILLAGE", ids(DistrictPolicy.plan(List.of(new Item("mine", null, false, true, true, false),
                new Item("homes", null, false, true, true, false)))));
        assertEquals("mine=UNKNOWN_WORLD homes=UNKNOWN_WORLD", ids(DistrictPolicy.plan(List.of(new Item("mine", null, true, true, false, false),
                new Item("homes", null, true, true, false, false)))));
        // 다 해 봄 → 빈 차례
        assertTrue(DistrictPolicy.plan(List.of(mine(State.BUILT, true, true), homes(State.BUILT, true, true))).isEmpty());
    }

    @Test
    void plotsRoundTrip() throws Exception {
        DistrictMeta d = new DistrictMeta();
        d.id = "homes";
        d.name = "집 구역";
        d.state = State.BUILT;
        d.site = "south_west";
        d.plots.add(new DistrictMeta.PlotRec("1", -178, 48, -165, 61, 73, 65, 105, "south", -172, 74, 62, -170, 75, 62, -171.5, 73, 63.5, 0f));
        d.plots.add(new DistrictMeta.PlotRec("10", -129, 84, -116, 97, 66, 58, 98, "south", -123, 67, 98, -121, 68, 98, -122.5, 66, 99.5, 0f));
        DistrictMeta back = DistrictMeta.fromYaml(d.toYaml());
        assertEquals(2, back.plots.size());
        DistrictMeta.PlotRec p = back.plots.get(0);
        assertEquals("1", p.id());
        assertEquals(-178, p.x0());
        assertEquals(61, p.z1());
        assertEquals(73, p.floor());
        assertEquals(65, p.y0());
        assertEquals(105, p.y1());
        assertEquals("south", p.front());
        assertEquals(-172, p.gateX());
        assertEquals(75, p.signY());
        assertEquals(-171.5, p.homeX(), 1e-9);
        assertEquals(63.5, p.homeZ(), 1e-9);
        assertEquals("10", back.plots.get(1).id());
        assertEquals(66, back.plots.get(1).floor());
        // 광산 기록에는 plots: 없음
        DistrictMeta m = new DistrictMeta();
        m.id = "mine";
        m.state = State.BUILT;
        assertTrue(DistrictMeta.fromYaml(m.toYaml()).plots.isEmpty());
    }
}
