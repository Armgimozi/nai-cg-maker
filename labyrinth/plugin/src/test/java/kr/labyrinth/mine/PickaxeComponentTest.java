package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.ToolSpec;
import org.junit.jupiter.api.Test;

/** 곡괭이 구성요소 계획 (계약 §2.6): Tool 규칙 · CAN_BREAK (tier 이하만) · UNBREAKABLE · 바탕 PAPER · 블록이 바뀌면 지문이 바뀜. */
class PickaxeComponentTest {

    @Test
    void rulesAndCanBreakPerTier() {
        MineDef mine = MineTestData.mine();
        var json = MineTestData.mineJson().sub("pickaxes");
        for (var e : MineTestData.pickaxes().entrySet()) {
            ToolSpec t = e.getValue();
            PickaxePlan plan = PickaxePlan.of(t, mine, MineTestData::hardness);
            Set<String> want = new HashSet<>();
            for (String id : json.sub(e.getKey()).strings("mines")) want.add(mine.node(id).block());
            assertEquals(want, new HashSet<>(plan.canBreak()), e.getKey() + " CAN_BREAK");
            assertEquals(2 * t.tier(), plan.rules().size(), e.getKey() + " 광석 tier 개 + 보석 tier 개");
            for (PickaxePlan.Rule r : plan.rules()) {
                MineDef.Node n = mine.node(r.node());
                assertTrue(n.tier() <= t.tier());
                assertEquals(n.block(), r.block());
                assertEquals(MineMath.seconds(n, t), r.seconds(), 1e-9);
                assertEquals(MineMath.toolSpeed(MineTestData.hardness(r.block()), r.seconds()), r.speed(), 1e-6);
                // 단단함이 달라도 초는 같다
                int ticks = MineMath.ticks(MineTestData.hardness(r.block()), r.speed());
                assertTrue(Math.abs(ticks - r.seconds() * 20) <= 1.0, r.node() + " " + ticks + "틱 vs " + r.seconds() + "초");
            }
            assertEquals(t.tier(), plan.tier());
        }
    }

    @Test
    void weakPickaxeCannotBreakHarderBlocks() {
        MineDef mine = MineTestData.mine();
        PickaxePlan copper = PickaxePlan.of(MineTestData.pickaxes().get("copper_pickaxe"), mine, MineTestData::hardness);
        assertEquals(List.of("minecraft:copper_ore", "minecraft:nether_quartz_ore"), copper.canBreak());
        assertTrue(!copper.canBreak().contains("minecraft:iron_ore"), "철 광석에 금도 안 감");
        PickaxePlan ori = PickaxePlan.of(MineTestData.pickaxes().get("orichalcum_pickaxe"), mine, MineTestData::hardness);
        assertEquals(12, ori.canBreak().size());
        assertEquals(2.5, copper.rules().get(0).seconds(), 1e-9, "구리 곡괭이로 구리 2.5초");
    }

    @Test
    void itemShape() {
        assertEquals("minecraft:paper", PickaxePlan.BASE_MATERIAL);
        assertTrue(PickaxePlan.UNBREAKABLE);
        assertEquals(0, PickaxePlan.DAMAGE_PER_BLOCK);
        assertEquals(1.0f, PickaxePlan.DEFAULT_SPEED);
        assertTrue(MinePickaxesHidden.ok(), "바닐라 줄 숨김: TOOL·CAN_BREAK·UNBREAKABLE·ATTRIBUTE_MODIFIERS");
    }

    @Test
    void notPickaxeHasNoPlan() {
        assertNull(PickaxePlan.of(null, MineTestData.mine(), MineTestData::hardness));
        assertNull(PickaxePlan.of(new ToolSpec("axe", 3, Map.of(), 0), MineTestData.mine(), MineTestData::hardness));
        assertNull(PickaxePlan.of(MineTestData.pickaxes().get("iron_pickaxe"), null, MineTestData::hardness));
    }

    @Test
    void signatureFollowsBlockSettings() {
        MineDef mine = MineTestData.mine();
        ToolSpec t = MineTestData.pickaxes().get("gold_pickaxe");
        PickaxePlan a = PickaxePlan.of(t, mine, MineTestData::hardness);
        PickaxePlan same = PickaxePlan.of(t, mine, MineTestData::hardness);
        assertEquals(a.signature(), same.signature());
        PickaxePlan harder = PickaxePlan.of(t, mine, b -> MineTestData.hardness(b) * 2);
        assertNotEquals(a.signature(), harder.signature(), "단단함(=블록)이 바뀌면 다시 씀");
        assertNotEquals(a.signature(), PickaxePlan.of(MineTestData.pickaxes().get("silver_pickaxe"), mine, MineTestData::hardness).signature());
    }

    /** MinePickaxes.HIDDEN 은 서버 없이 만들 수 없는 구성요소 형이라 이름만 본다. */
    static final class MinePickaxesHidden {
        static boolean ok() {
            try {
                String src = java.nio.file.Files.readString(java.nio.file.Path.of("src/main/java/kr/labyrinth/mine/MinePickaxes.java"));
                return src.contains("DataComponentTypes.TOOL, DataComponentTypes.CAN_BREAK,")
                        && src.contains("DataComponentTypes.UNBREAKABLE, DataComponentTypes.ATTRIBUTE_MODIFIERS")
                        && src.contains("MAX_STACK_SIZE, 1") && src.contains("withType(Material.PAPER)");
            } catch (java.io.IOException e) {
                return false;
            }
        }
    }
}
