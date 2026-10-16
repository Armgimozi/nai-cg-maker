package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.village.DistrictBackup.Decision;
import kr.labyrinth.village.DistrictBackup.Entry;
import kr.labyrinth.village.DistrictBackup.Phase;
import org.junit.jupiter.api.Test;

/** 구역 되돌리기 백업 (0.3.6.1): 파일 왕복 · 짓기 전(BEFORE) → 바뀐 칸만(DIFF) · 되돌리기 판단 (사람이 그 뒤 바꾼 칸은 건너뜀). */
class DistrictBackupTest {

    static Map<Long, String> world() {
        Map<Long, String> w = new HashMap<>();
        w.put(DistrictBackup.pack(1, 64, 1), "minecraft:grass_block[snowy=false]");
        w.put(DistrictBackup.pack(1, 65, 1), "minecraft:short_grass");
        w.put(DistrictBackup.pack(2, 65, 1), "minecraft:air");
        w.put(DistrictBackup.pack(-70, -10, 300), "minecraft:stone");
        return w;
    }

    static DistrictBackup before(Map<Long, String> w) {
        List<Entry> es = new ArrayList<>();
        for (Map.Entry<Long, String> e : w.entrySet()) {
            long k = e.getKey();
            es.add(new Entry(Trees.ux(k), Trees.uy(k), Trees.uz(k), e.getValue(), null));
        }
        return new DistrictBackup("mine", Phase.BEFORE, es);
    }

    static DistrictBackup.Lookup lookup(Map<Long, String> w) { return (x, y, z) -> w.get(DistrictBackup.pack(x, y, z)); }

    static DistrictBackup roundTrip(DistrictBackup b) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        b.write(out);
        return DistrictBackup.read(new ByteArrayInputStream(out.toByteArray()));
    }

    @Test
    void writeReadKeepsEverything() throws IOException {
        DistrictBackup b = before(world());
        DistrictBackup r = roundTrip(b);
        assertEquals("mine", r.district);
        assertEquals(Phase.BEFORE, r.phase);
        assertEquals(b.entries.size(), r.entries.size());
        for (int i = 0; i < b.entries.size(); i++) {
            assertEquals(b.entries.get(i).key(), r.entries.get(i).key());
            assertEquals(b.entries.get(i).before(), r.entries.get(i).before());
            assertNull(r.entries.get(i).after());
        }
        assertArrayEquals(new int[] {-70, 1, 2, 300}, r.bounds());
        assertThrows(IOException.class, () -> DistrictBackup.read(new ByteArrayInputStream(new byte[] {1, 2, 3})));
    }

    @Test
    void fileSaveIsAtomicAndReadable(@org.junit.jupiter.api.io.TempDir File dir) throws IOException {
        File f = new File(dir, DistrictMeta.backupName("mine"));
        before(world()).save(f);
        assertEquals(4, DistrictBackup.load(f).entries.size());
        assertEquals(List.of(f.getName()), List.of(dir.list()), "임시 파일이 남지 않음");
        Files.delete(f.toPath());
    }

    @Test
    void diffKeepsOnlyChangedCellsAndRemoveSkipsLaterEdits() throws IOException {
        Map<Long, String> w = world();
        DistrictBackup b = before(w);
        // 짓기: 잔디 → 돌 벽돌, 풀 → 공기, (2,65,1) 그대로, 땅속 돌 그대로
        w.put(DistrictBackup.pack(1, 64, 1), "minecraft:stone_bricks");
        w.put(DistrictBackup.pack(1, 65, 1), "minecraft:air");
        DistrictBackup diff = roundTrip(b.diff(lookup(w)));
        assertEquals(Phase.DIFF, diff.phase);
        assertEquals(2, diff.entries.size(), "바뀐 칸만");
        // 그 뒤 사람이 (1,65,1) 에 횃불을 놓음 → 그 칸은 건너뛰고 나머지는 되돌린다
        w.put(DistrictBackup.pack(1, 65, 1), "minecraft:torch");
        DistrictBackup.Restore r = diff.restorePlan(lookup(w));
        assertEquals(1, r.apply().size());
        assertEquals("minecraft:grass_block[snowy=false]", r.apply().get(0).before());
        assertEquals(1, r.skipped());
        // 되돌린 뒤 다시 계획하면 할 일 없음 (두 번 해도 같음)
        for (Entry e : r.apply()) w.put(e.key(), e.before());
        DistrictBackup.Restore again = diff.restorePlan(lookup(w));
        assertEquals(0, again.apply().size());
        assertEquals(1, again.same());
    }

    @Test
    void interruptedBuildRestoresEveryChangedCell() {
        Map<Long, String> w = world();
        DistrictBackup b = before(w);
        // 짓다가 꺼짐: 셋이 바뀌어 있음 (짓는 동안 상자는 보호되어 사람이 바꾼 칸은 없다) → 모두 되돌림
        w.put(DistrictBackup.pack(1, 64, 1), "minecraft:stone_bricks");
        w.put(DistrictBackup.pack(2, 65, 1), "minecraft:oak_planks");
        w.put(DistrictBackup.pack(-70, -10, 300), "minecraft:air");
        DistrictBackup.Restore r = b.restorePlan(lookup(w));
        assertEquals(3, r.apply().size());
        assertEquals(1, r.same());
        assertEquals(0, r.skipped());
        Entry e = b.entries.get(0);
        assertEquals(Decision.SAME, b.decide(e, e.before()));
        assertEquals(Decision.APPLY, b.decide(e, "minecraft:anything"));
        Entry d = new Entry(0, 0, 0, "minecraft:air", "minecraft:stone");
        DistrictBackup dd = new DistrictBackup("mine", Phase.DIFF, List.of(d));
        assertEquals(Decision.APPLY, dd.decide(d, "minecraft:stone"));
        assertEquals(Decision.SKIP, dd.decide(d, "minecraft:dirt"));
        assertEquals(Decision.SAME, dd.decide(d, "minecraft:air"));
    }
    /** 놀다가 열고 닫은 문·덧문, 흙이 된 잔디는 우리 것 — remove 가 되돌린다 (0.3.6.1 놀이 리뷰 #2). 다른 블록으로 바뀐 칸만 건너뜀. */
    @Test
    void removeRestoresTouchedDoorsShuttersAndDecayedGrass() {
        Entry door = new Entry(-80, 67, 11, "minecraft:air", "minecraft:spruce_door[facing=south,half=upper,hinge=left,open=false,powered=false]");
        Entry shutter = new Entry(-84, 70, 23, "minecraft:air", "minecraft:spruce_trapdoor[facing=north,half=top,open=true,powered=false,waterlogged=false]");
        Entry grass = new Entry(-90, 66, 16, "minecraft:air", "minecraft:grass_block[snowy=false]");
        Entry dirt = new Entry(-90, 65, 16, "minecraft:stone", "minecraft:dirt");
        DistrictBackup d = new DistrictBackup("mine", Phase.DIFF, List.of(door, shutter, grass, dirt));
        assertEquals(Decision.APPLY, d.decide(door, "minecraft:spruce_door[facing=south,half=upper,hinge=left,open=true,powered=false]"));
        assertEquals(Decision.APPLY, d.decide(shutter, "minecraft:spruce_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]"));
        assertEquals(Decision.APPLY, d.decide(grass, "minecraft:grass_block[snowy=true]"));
        assertEquals(Decision.APPLY, d.decide(grass, "minecraft:dirt"), "놓은 잔디가 흙이 됨");
        assertEquals(Decision.APPLY, d.decide(dirt, "minecraft:grass_block[snowy=false]"), "놓은 흙 위로 잔디가 번짐");
        assertEquals(Decision.SKIP, d.decide(door, "minecraft:oak_planks"), "다른 블록 = 그 뒤 바뀐 칸");
        assertEquals(Decision.SKIP, d.decide(shutter, "minecraft:cobblestone"));
        assertEquals(Decision.SAME, d.decide(door, "minecraft:air"));
        // 파일 왕복 뒤에도 같음
        Map<Long, String> w = new HashMap<>();
        w.put(door.key(), "minecraft:spruce_door[facing=south,half=upper,hinge=left,open=true,powered=false]");
        w.put(shutter.key(), "minecraft:spruce_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]");
        w.put(grass.key(), "minecraft:dirt");
        w.put(dirt.key(), "minecraft:dirt");
        DistrictBackup.Restore r = d.restorePlan(lookup(w));
        assertEquals(4, r.apply().size(), "문·덧문·흙이 된 잔디·놓은 흙");
        assertEquals(0, r.same());
        assertEquals(0, r.skipped());
    }
}
