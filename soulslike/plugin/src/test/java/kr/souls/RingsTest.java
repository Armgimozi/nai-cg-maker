package kr.souls;

import kr.souls.data.Profile;
import kr.souls.item.Rings;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;
import java.util.logging.Logger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 반지 등록부 (DESIGN 9.4, content/rings.yml) 와 프로필의 반지 칸 (12.6). */
class RingsTest {
    private final Logger log = Logger.getLogger("test");

    private Rings shipped() {
        Rings r = new Rings(log);
        r.load(TestFiles.yaml("content/rings.yml"));
        return r;
    }

    /** 이야기가 정해지기 전이라 시험 반지 셋만 있고, 모두 test 표시다 (세계에 놓지 않는다). */
    @Test
    void onlyTestRingsShip() {
        Rings r = shipped();
        assertEquals(List.of("test_stamina", "test_poise", "test_parry"), List.copyOf(r.all().keySet()));
        for (Rings.Def d : r.all().values()) {
            assertTrue(d.test(), d.id());
            assertEquals("ring_" + d.id(), d.model(), d.id());
        }
        assertEquals(1.20, r.get("test_stamina").staminaRegen(), 1e-9);
        assertEquals(0.40, r.get("test_poise").poise(), 1e-9);
        assertEquals(2, r.get("test_parry").parryWindow());
        assertEquals(List.of(Rings.STAMINA_REGEN), r.get("test_stamina").effects());
    }

    @Test
    void combineMultipliesRegenAndAddsTheRest() {
        Rings r = shipped();
        Rings.Worn none = Rings.combine(Arrays.asList(null, null));
        assertEquals(Rings.Worn.NONE, none);
        Rings.Worn w = Rings.combine(List.of(r.get("test_stamina"), r.get("test_poise")));
        assertEquals(1.20, w.staminaRegen(), 1e-9);
        assertEquals(0.40, w.poise(), 1e-9);
        assertEquals(0, w.parryWindow());
        assertFalse(w.soulGuard());
        Rings.Def a = new Rings.Def("a", "a", false, 1.2, 0.1, 1, false);
        Rings.Def b = new Rings.Def("b", "b", false, 1.5, 0.2, 2, true);
        Rings.Worn ab = Rings.combine(List.of(a, b));
        assertEquals(1.8, ab.staminaRegen(), 1e-9);
        assertEquals(0.3, ab.poise(), 1e-9);
        assertEquals(3, ab.parryWindow());
        assertTrue(ab.soulGuard());
    }

    /** 잘못된 항목: 모르는 효과는 그 효과만, 범위 밖 배율은 버리고, id 가 잘못되면 반지를 뺀다. */
    @Test
    void badEntriesAreDroppedNotFatal() throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("""
                ok:
                  effects: {stamina-regen: 1.5, glow: 3, soul-guard: true}
                zero:
                  effects: {stamina-regen: 0}
                Bad-Id:
                  effects: {poise: 0.2}
                """);
        Rings r = new Rings(log);
        r.load(y);
        assertEquals(1.5, r.get("ok").staminaRegen(), 1e-9);
        assertTrue(r.get("ok").soulGuard());
        assertEquals("ok", r.get("ok").model(), "모형이 없으면 id");
        assertEquals(1.0, r.get("zero").staminaRegen(), 1e-9, "0 배율은 버린다");
        assertNull(r.get("Bad-Id"));
        assertNull(r.get(null));
    }

    /** 프로필의 반지 칸: 돌려 쓰기, 비면 칸을 쓰지 않음, 뒤의 판이 더한 셋째 칸은 지키기. */
    @Test
    void profileRings() {
        Profile p = Profile.fresh();
        assertFalse(p.hasRings());
        assertFalse(p.toJson().contains("rings"));
        p.setRing(1, "test_poise");
        Profile q = Profile.parse(p.toJson());
        assertNull(q.ring(0));
        assertEquals("test_poise", q.ring(1));
        assertTrue(q.toJson().contains("\"rings\":[null,\"test_poise\"]"), q.toJson());
        q.setRing(1, null);
        assertFalse(Profile.parse(q.toJson()).hasRings());
        assertNull(q.ring(5), "칸 밖은 null");
        Profile third = Profile.parse("{\"v\":1,\"rings\":[\"a\",null,\"later\"]}");
        assertEquals("a", third.ring(0));
        third.setRing(0, null);
        assertTrue(third.toJson().contains("\"rings\":[null,null,\"later\"]"), third.toJson());
        assertNull(Profile.parse("{\"v\":1,\"rings\":\"broken\"}").ring(0));
    }
}
