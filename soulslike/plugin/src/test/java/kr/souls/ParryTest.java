package kr.souls;

import kr.souls.combat.Parry;
import kr.souls.item.Weapons;
import org.junit.jupiter.api.Test;

import java.util.logging.Logger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 패링 (DESIGN 3.5, DECISIONS 2026-10-10: 다크 소울 방식, 왼손 물건의 분류로 창이 정해진다). */
class ParryTest {
    private final Config cfg = new Config(TestFiles.yaml("config.yml"));
    private final Weapons weapons = new Weapons(Logger.getLogger("test"));

    {
        weapons.load(TestFiles.yaml("content/weapons.yml"));
    }

    private int base(String id) {
        return Parry.baseWindow(cfg.parry, weapons.get(id), false);
    }

    /** 패링 단검·작은 방패는 넉넉하고, 중형 방패는 보통, 왼손 무기는 짧고, 대방패는 패링하지 못한다. */
    @Test
    void windowByLeftHandClass() {
        assertEquals(9, base("parrying_dagger"));
        assertEquals(7, base("plank_shield"));
        assertEquals(7, base("pilgrim_buckler"), "같은 분류는 같은 창 (물건마다의 값이 없다)");
        assertEquals(5, base("redin_guard_shield"));
        assertEquals(0, base("volk_greatshield"), "대방패: F 는 아무것도 하지 않는다");
        assertEquals(4, base("alley_dagger"), "왼손에 든 단검");
        assertEquals(4, base("redin_guard_sword"), "왼손에 든 직검");
        assertEquals(0, base("gaoler_greatsword"));
        assertEquals(0, base("hrolf_halberd"));
        assertEquals(0, base("kiln_pot"));
        assertEquals(0, base("wall_shortbow"));
        assertTrue(base("parrying_dagger") > base("redin_guard_shield") && base("redin_guard_shield") > base("alley_dagger"));
        assertEquals(0, Parry.baseWindow(cfg.parry, null, true), "빈 왼손 (기본)");
        assertEquals(0, Parry.baseWindow(cfg.parry, null, false), "souls 물건이 아닌 것");
        assertEquals("empty", Parry.source(null, true));
        assertEquals("other", Parry.source(null, false));
        assertEquals("medium_shield", Parry.source(weapons.get("redin_guard_shield"), false));
    }

    /** 반지·난이도를 더해도 가장 짧아야 min (2) 틱, 창이 없는 것은 그대로 없다. */
    @Test
    void bonusesAndFloor() {
        assertEquals(10, Parry.window(8, 2, 2), "반지 +2");
        assertEquals(9, Parry.window(7, 2, 2), "쉬움 +2");
        assertEquals(4, Parry.window(5, -1, 2), "아주 어려움 −1");
        assertEquals(2, Parry.window(2, -1, 2), "가장 짧아도 2");
        assertEquals(0, Parry.window(0, 4, 2), "대방패는 반지를 껴도 패링하지 못한다");
    }

    /** 3.5 의 그림 (W = 6, d = 2): R = C−6 쳐냄 · C−7 놓침 · C+2 쳐냄 · C+3 놓침. */
    @Test
    void judgeWindow() {
        long c = 1000;
        assertTrue(Parry.inWindow(c - 6, c, 6, 2));
        assertFalse(Parry.inWindow(c - 7, c, 6, 2));
        assertTrue(Parry.inWindow(c + 2, c, 6, 2));
        assertFalse(Parry.inWindow(c + 3, c, 6, 2));
        assertFalse(Parry.inWindow(c, c, 0, 2), "창이 없으면 늘 놓친다");
    }

    /** 연타 잠금: 놓친 뒤 12틱, 쳐낸 뒤 6틱. */
    @Test
    void lock() {
        assertTrue(Parry.locked(111, 100, false, 12, 6));
        assertFalse(Parry.locked(112, 100, false, 12, 6));
        assertTrue(Parry.locked(105, 100, true, 12, 6));
        assertFalse(Parry.locked(106, 100, true, 12, 6));
        assertFalse(Parry.locked(0, Long.MIN_VALUE / 2, false, 12, 6), "처음 누름");
    }

    /** 빈 왼손을 바꿀 수 있다 (combat.parry.empty: 주무기로 쳐내게). */
    @Test
    void emptyHandIsAConfigChoice() {
        var y = TestFiles.yaml("config.yml");
        y.set("combat.parry.empty", 4);
        assertEquals(4, Parry.baseWindow(new Config(y).parry, null, true));
    }
}
