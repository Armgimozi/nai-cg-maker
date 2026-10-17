package kr.labyrinth.homes.play;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import kr.labyrinth.homes.HomesLayout;
import kr.labyrinth.homes.PlotGeom;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 시작 오두막 (0.3.7, 설계 §4): 집터 뒤쪽 가운데 (뒤 울타리에서 한 칸, 문 = 대문 줄) · 앞마당 14×6 · 집터·높이 창 안 ·
 * 앞 방향(N·S·E·W)으로 돌림 · 나무 4가지 · 블록 데이터가 26.3 블록·속성과 맞음 (blockdata.json).
 */
class StarterCottageTest {

    static JsonObject blocks;
    static final Pattern DATA = Pattern.compile("minecraft:([a-z_]+)(?:\\[(.*)])?");

    @BeforeAll
    static void load() throws Exception {
        blocks = JsonParser.parseString(Files.readString(Path.of("../tools/village/blockdata.json"))).getAsJsonObject().getAsJsonObject("blocks");
    }

    static List<PlotGeom> designPlots() { return HomesLayout.geoms(6, 24); }

    @Test
    void sitsAtTheBackCentreInsideThePlot() {
        for (PlotGeom g : designPlots()) {
            for (StarterCottage.Wood w : StarterCottage.Wood.values()) {
                List<StarterCottage.Cell> cells = StarterCottage.plan(g, w);
                Set<String> seen = new HashSet<>();
                for (StarterCottage.Cell c : cells) {
                    assertTrue(g.containsColumn(c.x(), c.z()), g.id() + " 집터 밖: " + c);
                    assertTrue(c.y() >= g.floorY() && c.y() <= g.floorY() + StarterCottage.HEIGHT, "높이: " + c);
                    assertTrue(g.contains(c.x(), c.y(), c.z()), "높이 창 안: " + c);
                    assertTrue(seen.add(c.x() + "," + c.y() + "," + c.z()), "겹친 칸: " + c);
                }
            }
            List<int[]> fp = StarterCottage.footprint(g);
            assertEquals(49, fp.size());
            int minZ = Integer.MAX_VALUE, maxZ = Integer.MIN_VALUE, minX = Integer.MAX_VALUE, maxX = Integer.MIN_VALUE;
            for (int[] c : fp) {
                minX = Math.min(minX, c[0]);
                maxX = Math.max(maxX, c[0]);
                minZ = Math.min(minZ, c[1]);
                maxZ = Math.max(maxZ, c[1]);
            }
            assertEquals(6, maxX - minX);
            assertEquals(6, maxZ - minZ);
            assertEquals(g.x0() + 3, minX, "가로 가운데 (왼쪽 3칸)");
            int[] door = StarterCottage.doorCell(g);
            assertEquals(g.gateX(), door[0], g.id() + " 문이 대문과 같은 줄");
            if ("S".equals(g.front())) {
                assertEquals(g.z0() + 1, minZ, "뒤(북) 울타리에서 한 칸");
                assertEquals(g.z0() + 7, door[1]);
                assertEquals(6, g.z1() - maxZ, "앞마당 6칸");
            } else {
                assertEquals(g.z1() - 1, maxZ, "뒤(남) 울타리에서 한 칸");
                assertEquals(g.z1() - 7, door[1]);
                assertEquals(6, minZ - g.z0(), "앞마당 6칸");
            }
        }
    }

    @Test
    void eastAndWestFrontsRotate() {
        PlotGeom east = new PlotGeom("1", 1, 0, 0, 13, 13, 64, 58, 88, "E", 14, 6, 14, 66, 8, 0, Double.NaN, 0, 0f, false);
        PlotGeom west = new PlotGeom("2", 2, 0, 0, 13, 13, 64, 58, 88, "W", -1, 6, -1, 66, 8, 0, Double.NaN, 0, 0f, false);
        for (PlotGeom g : List.of(east, west)) {
            for (StarterCottage.Cell c : StarterCottage.plan(g, StarterCottage.Wood.OAK)) assertTrue(g.containsColumn(c.x(), c.z()), c.toString());
            int[] door = StarterCottage.doorCell(g);
            assertEquals(6, door[1], "문이 대문 줄");
            assertEquals("E".equals(g.front()) ? 7 : 6, door[0]);
        }
    }

    @Test
    void furnitureAndDoorFaceTheRightWay() {
        PlotGeom s = designPlots().get(0); // 1번 (대문 남쪽)
        PlotGeom n = designPlots().get(3); // 4번 (대문 북쪽)
        assertEquals("S", s.front());
        assertEquals("N", n.front());
        for (PlotGeom g : List.of(s, n)) {
            String back = "S".equals(g.front()) ? "north" : "south";
            List<StarterCottage.Cell> cells = StarterCottage.plan(g, StarterCottage.Wood.SPRUCE);
            int doors = 0, heads = 0, feet = 0, chests = 0, crafting = 0, furnaces = 0, lanterns = 0;
            StarterCottage.Cell head = null, foot = null;
            for (StarterCottage.Cell c : cells) {
                String d = c.data();
                if (d.startsWith("minecraft:spruce_door")) {
                    doors++;
                    assertTrue(d.contains("facing=" + back), d);
                }
                if (d.startsWith("minecraft:blue_bed") && d.contains("part=head")) {
                    heads++;
                    head = c;
                }
                if (d.startsWith("minecraft:blue_bed") && d.contains("part=foot")) {
                    feet++;
                    foot = c;
                }
                if (d.startsWith("minecraft:chest")) chests++;
                if (d.equals("minecraft:crafting_table")) crafting++;
                if (d.startsWith("minecraft:furnace")) furnaces++;
                if (d.startsWith("minecraft:lantern")) lanterns++;
            }
            assertEquals(2, doors, "문 위아래");
            assertEquals(1, heads);
            assertEquals(1, feet);
            assertEquals(2, chests, "상자 2");
            assertEquals(1, crafting);
            assertEquals(1, furnaces);
            assertEquals(2, lanterns);
            assertNotNull(head);
            assertNotNull(foot);
            // 머리가 뒤 벽 쪽
            if ("S".equals(g.front())) assertTrue(head.z() < foot.z());
            else assertTrue(head.z() > foot.z());
        }
    }

    @Test
    void blockDataMatchesTheGameBlocks() {
        Set<String> checked = new HashSet<>();
        for (StarterCottage.Wood w : StarterCottage.Wood.values()) {
            for (PlotGeom g : designPlots()) {
                for (StarterCottage.Cell c : StarterCottage.plan(g, w)) {
                    if (!checked.add(c.data())) continue;
                    Matcher m = DATA.matcher(c.data());
                    assertTrue(m.matches(), c.data());
                    String id = m.group(1);
                    assertTrue(blocks.has(id), "26.3 에 없는 블록: " + id);
                    JsonArray props = blocks.getAsJsonArray(id);
                    if (m.group(2) == null) continue;
                    List<String> names = new ArrayList<>();
                    for (JsonElement p : props) names.add(p.getAsJsonArray().get(0).getAsString());
                    for (String kv : m.group(2).split(",")) {
                        String[] parts = kv.split("=");
                        int i = names.indexOf(parts[0]);
                        assertTrue(i >= 0, id + " 에 없는 속성 " + parts[0]);
                        boolean ok = false;
                        for (JsonElement v : props.get(i).getAsJsonArray().get(1).getAsJsonArray()) if (v.getAsString().equals(parts[1])) ok = true;
                        assertTrue(ok, id + "[" + kv + "] 값이 틀림");
                    }
                }
            }
        }
        assertTrue(checked.size() > 20);
    }

    @Test
    void woodsAndReplaceables() {
        assertEquals(4, StarterCottage.Wood.values().length);
        assertEquals(StarterCottage.Wood.CHERRY, StarterCottage.Wood.of("cherry"));
        assertEquals(StarterCottage.Wood.BIRCH, StarterCottage.Wood.of("자작"));
        assertEquals(null, StarterCottage.Wood.of("bamboo"));
        assertTrue(StarterCottage.replaceableFloor("grass_block"));
        assertFalse(StarterCottage.replaceableFloor("oak_planks"), "이미 지은 것");
        assertTrue(StarterCottage.replaceableAbove("short_grass"));
        assertFalse(StarterCottage.replaceableAbove("chest"));
        // 판자·돌벽돌·계단·유리판 정도 — 설계 값 약 248G 쯤의 오두막
        long planks = StarterCottage.plan(designPlots().get(0), StarterCottage.Wood.OAK).stream().filter(c -> c.data().equals("minecraft:oak_planks")).count();
        assertTrue(planks > 60 && planks < 200, "판자 " + planks);
    }
}
