package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * 맡긴 짐 (review R3): pending → ready · 시작 때 pending 마저 · 두 번 받기 불가 · 월드 폴더 · 셜커 한 개 · 섬세한 손길 개수 · 큰 상자 반쪽.
 * 아이템은 바이트로 다룬다 (ItemStack 직렬화는 서버가 함).
 */
class ParcelTest {

    @TempDir
    Path world;

    private static final UUID U = UUID.fromString("00000000-0000-0000-0000-0000000000a1");

    private static byte[] b(String s) { return s.getBytes(StandardCharsets.UTF_8); }

    private static ParcelStore.Pending pending(List<byte[]> items) {
        return new ParcelStore.Pending("3", "vacate", 1000, -129, 48, -116, 61, 62, 92, 68, false, items);
    }

    @Test
    void pendingThenReady() throws Exception {
        File dir = world.resolve(ParcelStore.DIR).toFile();
        ParcelStore s = new ParcelStore(dir);
        s.begin(U, "하린", pending(List.of(b("chest"), b("glass"))));
        assertEquals(0, s.readyCount(U), "pending 동안은 꺼낼 수 없음");
        assertNotNull(s.pending(U));
        assertEquals(List.of(U), s.pendingOwners());
        assertTrue(new File(dir, U + ".yml").isFile(), "월드 폴더 안 (R3b)");

        // 서버가 여기서 죽었다 → 새로 읽어도 pending
        ParcelStore again = new ParcelStore(dir);
        ParcelStore.Pending p = again.pending(U);
        assertNotNull(p);
        assertEquals("3", p.plotId());
        assertEquals(-129, p.x0());
        assertEquals(92, p.yMax());
        assertEquals(68, p.floorY());
        assertEquals(2, p.items().size());
        assertArrayEquals(b("glass"), p.items().get(1));

        assertTrue(again.finish(U));
        assertNull(again.pending(U));
        assertEquals(2, again.readyCount(U));
        assertFalse(again.finish(U), "두 번 finish 해도 짐이 늘지 않음");
        assertEquals(2, again.readyCount(U));
        assertEquals("하린", new ParcelStore(dir).ownerName(U));
    }

    @Test
    void cannotBeginTwice() throws Exception {
        ParcelStore s = new ParcelStore(world.resolve(ParcelStore.DIR).toFile());
        s.begin(U, "a", pending(List.of(b("x"))));
        assertThrows(IllegalStateException.class, () -> s.begin(U, "a", pending(List.of(b("y")))));
        s.abort(U);
        assertNull(s.pending(U));
        assertEquals(0, s.readyCount(U), "abort = 짐을 버림 (블록이 그대로일 때만 씀)");
    }

    @Test
    void takeOnlyOnce() throws Exception {
        File dir = world.resolve(ParcelStore.DIR).toFile();
        ParcelStore s = new ParcelStore(dir);
        s.begin(U, "a", pending(List.of(b("a"), b("b"), b("c"))));
        s.finish(U);
        List<byte[]> got = s.remove(U, List.of(0, 2));
        assertEquals(2, got.size());
        assertArrayEquals(b("a"), got.get(0));
        assertArrayEquals(b("c"), got.get(1));
        assertEquals(1, s.readyCount(U));
        assertEquals(1, new ParcelStore(dir).readyCount(U), "파일에서 먼저 뺐음");
        assertTrue(s.remove(U, List.of(5)).isEmpty(), "없는 번호");
        List<byte[]> last = s.remove(U, List.of(0));
        assertEquals(1, last.size());
        assertTrue(s.remove(U, List.of(0)).isEmpty(), "두 번 받기 불가");
        assertFalse(new File(dir, U + ".yml").exists(), "빈 짐 파일은 지움");
        s.add(U, "a", List.of(b("left")));
        assertEquals(1, new ParcelStore(dir).readyCount(U), "못 준 것은 다시 넣음");
    }

    @Test
    void newVacateAddsToOldParcel() throws Exception {
        ParcelStore s = new ParcelStore(world.resolve(ParcelStore.DIR).toFile());
        s.begin(U, "a", pending(List.of(b("1"))));
        s.finish(U);
        s.begin(U, "a", pending(List.of(b("2"), b("3"))));
        assertEquals(1, s.readyCount(U));
        s.finish(U);
        assertEquals(3, s.readyCount(U));
    }

    // ── 짐 규칙 (R3c·d) ──────────────────────────────────────────────────

    @Test
    void shulkerIsOneItemWithContents() {
        assertEquals(PlotResetPlan.Take.SHULKER_ITEM, PlotResetPlan.take("shulker_box", Map.of(), true));
        assertEquals(PlotResetPlan.Take.SHULKER_ITEM, PlotResetPlan.take("minecraft:red_shulker_box[facing=up]", Map.of(), true),
                "내용을 따로 꺼내지 않음 (두 배 막기)");
        assertEquals(PlotResetPlan.Take.CONTENTS_AND_DROPS, PlotResetPlan.take("chest", Map.of("type", "left"), true), "다른 상자류는 비우고 드롭");
        assertEquals(PlotResetPlan.Take.CONTENTS_AND_DROPS, PlotResetPlan.take("barrel", Map.of(), true));
        assertEquals(PlotResetPlan.Take.CONTENTS_AND_DROPS, PlotResetPlan.take("oak_shelf", Map.of(), true));
    }

    @Test
    void bigChestHalvesEachGiveOne() {
        // 큰 상자 = 상자 블록 둘 → 반쪽마다 그 반의 내용 (Chest#getBlockInventory) + 상자 1
        Map<String, String> left = PlotResetPlan.props("minecraft:chest[facing=north,type=left,waterlogged=false]");
        Map<String, String> right = PlotResetPlan.props("minecraft:chest[facing=north,type=right,waterlogged=false]");
        assertEquals(PlotResetPlan.Take.CONTENTS_AND_DROPS, PlotResetPlan.take("chest", left, true));
        assertEquals(PlotResetPlan.Take.CONTENTS_AND_DROPS, PlotResetPlan.take("chest", right, true));
        assertEquals(1, PlotResetPlan.fallbackCount("chest", left));
    }

    @Test
    void silkCountsAndHalves() {
        assertEquals(2, PlotResetPlan.fallbackCount("oak_slab", PlotResetPlan.props("oak_slab[type=double]")), "겹 반블록 2");
        assertEquals(1, PlotResetPlan.fallbackCount("oak_slab", PlotResetPlan.props("oak_slab[type=bottom]")));
        assertEquals(4, PlotResetPlan.fallbackCount("white_candle", PlotResetPlan.props("white_candle[candles=4,lit=false]")), "초 4");
        assertEquals(3, PlotResetPlan.fallbackCount("sea_pickle", PlotResetPlan.props("sea_pickle[pickles=3]")));
        assertEquals(1, PlotResetPlan.fallbackCount("glass", Map.of()), "유리 (섬세한 손길이 아니면 0개 — 비면 1)");
        assertEquals(0, PlotResetPlan.fallbackCount("spawner", Map.of()));
        assertEquals(PlotResetPlan.Take.SECOND_HALF, PlotResetPlan.take("oak_door", PlotResetPlan.props("oak_door[half=upper]"), false), "문 윗칸은 한 번");
        assertEquals(PlotResetPlan.Take.DROPS, PlotResetPlan.take("oak_door", PlotResetPlan.props("oak_door[half=lower]"), false));
        assertEquals(PlotResetPlan.Take.SECOND_HALF, PlotResetPlan.take("red_bed", PlotResetPlan.props("red_bed[part=foot]"), false), "침대 반쪽은 한 번");
        assertEquals(PlotResetPlan.Take.DROPS, PlotResetPlan.take("red_bed", PlotResetPlan.props("red_bed[part=head]"), false));
        assertEquals(PlotResetPlan.Take.SECOND_HALF, PlotResetPlan.take("rose_bush", PlotResetPlan.props("rose_bush[half=upper]"), false));
        assertEquals(PlotResetPlan.Take.DROPS, PlotResetPlan.take("oak_stairs", PlotResetPlan.props("oak_stairs[half=top]"), false), "계단 top 은 반쪽 아님");
        assertEquals(PlotResetPlan.Take.DROPS, PlotResetPlan.take("glass", Map.of(), false));
        assertEquals(PlotResetPlan.Take.DROPS, PlotResetPlan.take("oak_leaves", Map.of(), false));
        assertEquals(PlotResetPlan.Take.NOTHING, PlotResetPlan.take("water", Map.of(), false));
        assertEquals(PlotResetPlan.Take.NOTHING, PlotResetPlan.take("fire", Map.of(), false));
        assertEquals(PlotResetPlan.Take.SECOND_HALF, PlotResetPlan.take("piston_head", Map.of(), false));
    }

    @Test
    void entitiesToParcel() {
        assertEquals(PlotResetPlan.EntityTake.ITEM_FRAME, PlotResetPlan.entity("GLOW_ITEM_FRAME"));
        assertEquals(PlotResetPlan.EntityTake.PAINTING, PlotResetPlan.entity("PAINTING"));
        assertEquals(PlotResetPlan.EntityTake.ARMOR_STAND, PlotResetPlan.entity("ARMOR_STAND"));
        assertEquals(PlotResetPlan.EntityTake.VEHICLE, PlotResetPlan.entity("OAK_CHEST_BOAT"));
        assertEquals(PlotResetPlan.EntityTake.VEHICLE, PlotResetPlan.entity("BAMBOO_RAFT"));
        assertEquals(PlotResetPlan.EntityTake.VEHICLE, PlotResetPlan.entity("HOPPER_MINECART"));
        assertEquals(PlotResetPlan.EntityTake.ITEM, PlotResetPlan.entity("ITEM"));
        assertEquals(PlotResetPlan.EntityTake.NONE, PlotResetPlan.entity("COW"), "동물은 그대로 둠");
        assertEquals(PlotResetPlan.EntityTake.NONE, PlotResetPlan.entity("PLAYER"));
    }
}
