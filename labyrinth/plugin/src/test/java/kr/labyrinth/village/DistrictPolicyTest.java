package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.BitSet;
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
}
