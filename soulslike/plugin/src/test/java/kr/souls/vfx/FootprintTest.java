package kr.souls.vfx;

import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.util.Vector;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Proxy;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * skyblock 에서 그대로 옮긴 Footprint (DESIGN 12.9, 13.1 "Footprint 도형"). P1a 의 HitQuery (부채꼴·직선) 와 P2b 의 적 동작이 쓴다.
 * 원은 수평 거리, 직선은 너비/2 + 0.5 (몸 반쯤) 안, 부채꼴은 수평 각도 (0.5 칸 안은 늘 맞는다).
 */
class FootprintTest {
    private static Location at(double x, double y, double z) {
        return new Location(null, x, y, z);
    }

    @Test
    void circleIsHorizontal() {
        Footprint c = Footprint.circle(at(0, 64, 0), 2);
        assertTrue(c.contains(at(2, 64, 0)), "가장자리 포함");
        assertTrue(c.contains(at(1.4, 80, 1.4)), "높이는 보지 않는다");
        assertFalse(c.contains(at(1.5, 64, 1.5)));
    }

    @Test
    void line() {
        Footprint l = Footprint.line(at(0, 64, 0), new Vector(0, 0, 5), 4.2, 1.0);
        assertTrue(l.dir().length() > 0.999 && l.dir().length() < 1.001, "방향을 길이 1 로");
        assertTrue(l.contains(at(0, 64, 4.2)), "끝 포함");
        assertFalse(l.contains(at(0, 64, 4.3)), "끝 너머");
        assertFalse(l.contains(at(0, 64, -0.1)), "뒤");
        assertTrue(l.contains(at(1.0, 64, 2)), "너비/2 + 0.5 = 1.0 안");
        assertFalse(l.contains(at(1.05, 64, 2)));
    }

    @Test
    void cone() {
        // 직검의 부채꼴 100° (반각 50°), 3.0 칸
        Footprint c = Footprint.cone(at(0, 64, 0), new Vector(0, 0, 1), Math.toRadians(50), 3.0);
        assertTrue(c.contains(at(0, 64, 3.0)));
        assertFalse(c.contains(at(0, 64, 3.1)), "사거리 밖");
        assertTrue(c.contains(at(Math.sin(Math.toRadians(49)) * 2, 64, Math.cos(Math.toRadians(49)) * 2)), "반각 안");
        assertFalse(c.contains(at(Math.sin(Math.toRadians(51)) * 2, 64, Math.cos(Math.toRadians(51)) * 2)), "반각 밖");
        assertFalse(c.contains(at(0, 64, -2)), "뒤");
        assertTrue(c.contains(at(0, 64, -0.4)), "0.5 칸 안은 방향과 상관없이");
        assertTrue(c.contains(at(0, 70, 2)), "높이는 보지 않는다 (위아래는 HitQuery 가 따로 본다)");
    }

    @Test
    void otherWorldNeverContains() {
        World w = (World) Proxy.newProxyInstance(World.class.getClassLoader(), new Class<?>[] {World.class}, (o, m, a) -> switch (m.getName()) {
            case "hashCode" -> 1;
            case "equals" -> o == a[0];
            default -> null;
        });
        Footprint c = Footprint.circle(new Location(w, 0, 64, 0), 5);
        assertTrue(c.contains(new Location(w, 1, 64, 1)));
        assertFalse(c.contains(at(1, 64, 1)), "다른 세계");
    }
}
