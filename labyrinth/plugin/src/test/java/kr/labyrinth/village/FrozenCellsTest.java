package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.BitSet;
import java.util.List;
import org.junit.jupiter.api.Test;

/** 얼린 칸 (0.3.6.1 CONTRACT §2.13 3): 마을 보호 상자 &gt; 마을 길 &gt; 마을이 다듬은 칸(meta.terrain.changed), 먼저 지은 구역도 더함. */
class FrozenCellsTest {

    static VillageMeta village() {
        VillageMeta m = new VillageMeta();
        // 다듬은 칸: 4×4 격자 (10..13, 20..23) 중 (10,20) (11,20) (13,23)
        BitSet ch = new BitSet();
        ch.set(0);
        ch.set(1);
        ch.set(15);
        m.terrain = new VillageMeta.TerrainRec(10, 20, 4, 60, new byte[16], ch);
        // 길: (11,20) (12,20) 높이 64
        m.paths.add(new VillageMeta.PathRec(0, 1, "main", List.of(new int[] {11, 20}, new int[] {12, 20}), -1, -1,
                List.of(new int[] {11, 20, 64}, new int[] {12, 20, 64})));
        // 보호 상자: (12..13, 20..21)
        m.protect.add(new VillageMeta.Box(12, 50, 20, 13, 80, 21));
        return m;
    }

    @Test
    void kindsAndPriority() {
        FrozenCells f = FrozenCells.of(village(), List.of());
        assertEquals(FrozenCells.Kind.TRIM, f.kind(10, 20), "다듬은 칸");
        assertEquals(FrozenCells.Kind.PATH, f.kind(11, 20), "다듬은 칸 + 길 → 길");
        assertEquals(FrozenCells.Kind.PROTECT, f.kind(12, 20), "길 + 보호 상자 → 보호");
        assertEquals(FrozenCells.Kind.PROTECT, f.kind(13, 21));
        assertEquals(FrozenCells.Kind.TRIM, f.kind(13, 23));
        assertEquals(FrozenCells.Kind.NONE, f.kind(10, 21), "바뀌지 않은 칸은 얼리지 않음");
        assertFalse(f.frozen(10, 21));
        assertTrue(f.untouchable(11, 20) && f.untouchable(12, 20));
        assertFalse(f.untouchable(10, 20), "다듬은 칸은 겉 블록만 깔 수 있음");
        assertEquals(64, f.pathY(11, 20));
        assertNull(f.pathY(10, 20));
        assertEquals(7, f.size());
    }

    @Test
    void otherDistrictsAddTheirCells() {
        VillageMeta other = new VillageMeta();
        other.protect.add(new VillageMeta.Box(100, 60, 100, 101, 70, 100));
        FrozenCells f = FrozenCells.of(village(), List.of(other));
        assertEquals(FrozenCells.Kind.PROTECT, f.kind(100, 100));
        assertEquals(FrozenCells.Kind.PROTECT, f.kind(101, 100));
        assertEquals(FrozenCells.Kind.NONE, f.kind(102, 100));
        assertEquals(0, FrozenCells.of(null, null).size());
    }
}
