package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class BlueprintParseTest {

    @Test
    void parsesSizeLayersPaletteAndMarkers() {
        Blueprint hut = Fixtures.piece("hut");
        assertEquals("hut", hut.id);
        assertEquals(5, hut.w);
        assertEquals(5, hut.h);
        assertEquals(5, hut.d);
        assertEquals(1, hut.floorY);
        assertEquals(2, hut.anchorX);
        assertEquals(1, hut.anchorZ);
        assertEquals('c', hut.cell(0, 0, 0));
        assertEquals('d', hut.cell(2, 2, 0));
        assertEquals(Blueprint.AIR, hut.cell(1, 2, 1));
        assertEquals("★".codePointAt(0), hut.cell(3, 2, 3), "유니코드 팔레트 글자");
        assertTrue(hut.state('d').contains("facing=north"));
        assertEquals(Blueprint.KEEP, hut.cell(7, 0, 0), "범위 밖 = 건드리지 않음");
        assertEquals(25, hut.occupiedCount());
        assertEquals(4, hut.markers.size());
        Blueprint.Marker inter = hut.markers("interact").get(0);
        assertEquals("blacksmith", inter.action());
        assertEquals(2, inter.pos().size(), "interact 는 pos 여러 개");
        Blueprint.Marker npc = hut.markers("npc").get(0);
        assertEquals("blacksmith", npc.id());
        assertEquals("front", npc.face());
        assertFalse(hut.deco);
        assertTrue(hut.door);
        assertEquals(2, hut.foundationMix.size());
        assertNotNull(hut.foundationAt(Blueprint.hash(1, 2, 3)));
    }

    @Test
    void spaceCellsAreNotFootprint() {
        Blueprint sq = Fixtures.piece("square");
        assertFalse(sq.occupied(0, 0), "모서리 공백은 발자국 아님");
        assertTrue(sq.occupied(4, 4));
        assertEquals(Blueprint.KEEP, sq.cell(0, 1, 0));
    }

    @Test
    void decoPieceDetectedById() {
        Blueprint lamp = Fixtures.piece("lamp_post");
        assertTrue(lamp.deco);
        assertFalse(lamp.door, "장식은 정문 검사 안 함");
    }

    @Test
    void rejectsBadRowsAndUnknownLetters() {
        String bad = """
                {"id":"x","size":[3,1,2],"palette":{"a":"minecraft:stone"},"layers":[["aaa","aa"]]}""";
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class, () -> Blueprint.parse(bad));
        assertTrue(e.getMessage().contains("길이"), e.getMessage());
        String unknown = """
                {"id":"y","size":[2,1,1],"palette":{"a":"minecraft:stone"},"layers":[["aq"]]}""";
        e = assertThrows(IllegalArgumentException.class, () -> Blueprint.parse(unknown));
        assertTrue(e.getMessage().contains("'q'"), e.getMessage());
        String badState = """
                {"id":"z","size":[1,1,1],"palette":{"a":"Stone Bricks"},"layers":[["a"]]}""";
        assertThrows(IllegalArgumentException.class, () -> Blueprint.parse(badState));
    }

    @Test
    void layoutParses() {
        Layout l = Layout.parse(Fixtures.read("village/layout.json"));
        assertEquals("시험 마을", l.name);
        assertEquals(20, l.radius);
        assertEquals(16, l.blend);
        assertEquals(4, l.pieces.size());
        assertEquals(Dir.SOUTH, l.pieces.get(1).front());
        assertEquals(2, l.paths.size());
        assertEquals(3, l.paths.get(0).width());
        assertTrue(l.pathStyles.containsKey("lane"));
        assertThrows(IllegalArgumentException.class, () -> Layout.parse("{\"pieces\":[{\"piece\":\"a\",\"at\":[0,0],\"front\":\"up\"}]}"));
    }
}
