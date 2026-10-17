package kr.labyrinth.homes.admin;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

/** {@code /labadmin plot convert} (plan §11): 가로·세로 ≤ 32 · 높이 ≤ 48 · 기본 높이 땅 최저 −8 ~ 최고 +24 · 명령 하위 목록 (R18). */
class ConvertRulesTest {

    @Test
    void sizeLimits() {
        ConvertRules.Box ok = ConvertRules.check(10, 10, -21, -21, 60, 100, 0, 0, -64, 319);
        assertTrue(ok.ok(), ok.error());
        assertEquals(-21, ok.x0());
        assertEquals(10, ok.x1());
        assertEquals(60, ok.y0());
        assertEquals(100, ok.y1());
        ConvertRules.Box wide = ConvertRules.check(0, 0, 32, 5, 60, 70, 0, 0, -64, 319);
        assertFalse(wide.ok(), "33칸");
        assertTrue(wide.error().contains("32"));
        ConvertRules.Box tall = ConvertRules.check(0, 0, 5, 5, 0, 48, 0, 0, -64, 319);
        assertFalse(tall.ok(), "49칸 높이");
    }

    @Test
    void defaultHeightFromGround() {
        ConvertRules.Box b = ConvertRules.check(0, 0, 9, 9, null, null, 66, 70, -64, 319);
        assertTrue(b.ok(), b.error());
        assertEquals(58, b.y0(), "땅 최저 66 − 8");
        assertEquals(94, b.y1(), "땅 최고 70 + 24");
        assertEquals(66, b.floorY());
        ConvertRules.Box hill = ConvertRules.check(0, 0, 9, 9, null, null, 60, 80, -64, 319);
        assertFalse(hill.ok(), "언덕이면 높이를 직접");
        assertTrue(hill.error().contains("y1 y2"));
        ConvertRules.Box clamp = ConvertRules.check(0, 0, 3, 3, -100, -60, 0, 0, -64, 319);
        assertEquals(-64, clamp.y0(), "월드 바닥 아래로는 안 감");
    }

    @Test
    void adminCommandListMatchesPlan() throws Exception {
        String src = Files.readString(Path.of("src/main/java/kr/labyrinth/homes/admin/HomesAdminCommands.java"));
        for (String sub : new String[] {"list", "info", "tp", "give", "reclaim", "convert", "unconvert", "lock", "grace", "legacy", "name", "parcel",
                "selftest"}) {
            assertTrue(src.contains("Commands.literal(\"" + sub + "\")"), "plot " + sub);
        }
        assertTrue(src.contains("cmd.addSubcommand(\"labadmin\""));
    }
}
