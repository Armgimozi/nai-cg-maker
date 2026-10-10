package kr.souls;

import kr.souls.data.Profile;
import kr.souls.item.MasterKey;
import kr.souls.item.Weapons;
import kr.souls.progression.Origins;
import kr.souls.progression.StatBlock;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.logging.Logger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 출신 여섯 (DESIGN 5.1, content/origins.yml) 과 무기표 (weapons.yml) 가 맞는다. */
class OriginsTest {
    private final Logger log = Logger.getLogger("test");
    private Weapons weapons;
    private Origins origins;

    @BeforeEach
    void load() {
        weapons = new Weapons(log);
        weapons.load(TestFiles.yaml("content/weapons.yml"));
        origins = new Origins(log);
        origins.load(TestFiles.yaml("content/origins.yml"), weapons);
    }

    @Test
    void sixInOrder() {
        List<String> ids = origins.all().stream().map(Origins.Origin::id).toList();
        assertEquals(List.of("knight", "warrior", "thief", "archer", "sorcerer", "deprived"), ids);
    }

    @Test
    void levelIsSumMinus59() {
        for (Origins.Origin o : origins.all()) assertEquals(o.stats().sum() - 59, o.level(), o.id());
        assertEquals(1, origins.get("deprived").level());
        assertEquals(StatBlock.BASE, origins.get("deprived").stats());
        assertEquals(9, origins.get("knight").level());
    }

    /** 주 능력치 15~16, 둘째 12~13 (있으면), 나머지 9~11 (빈털터리는 모두 10). */
    @Test
    void simpleStatShape() {
        for (Origins.Origin o : origins.all()) {
            if (o.id().equals("deprived")) continue;
            int[] v = new int[6];
            for (int i = 0; i < 6; i++) v[i] = o.stats().get(StatBlock.IDS.get(i));
            int[] sorted = v.clone();
            Arrays.sort(sorted);
            assertTrue(sorted[5] >= 15 && sorted[5] <= 16, o.id() + " 주 능력치 " + sorted[5]);
            for (int x : v) assertTrue(x >= 9 && x <= 16, o.id() + " 값 " + x);
            int seconds = 0;
            for (int x : v) if (x >= 12 && x <= 13) seconds++;
            assertTrue(seconds <= 2, o.id());
            for (int x : v) assertTrue(x <= 11 || x >= 12, o.id());
        }
    }

    @Test
    void mainStatsMatchTheme() {
        assertEquals(15, origins.get("knight").stats().vig());
        assertEquals(16, origins.get("warrior").stats().str());
        assertEquals(16, origins.get("thief").stats().dex());
        assertEquals(15, origins.get("archer").stats().dex());
        assertEquals(16, origins.get("sorcerer").stats().intel());
        assertEquals(13, origins.get("sorcerer").stats().mnd());
    }

    /** 시작 무기는 모두 weapons.yml 에 있고, 주무기는 지금 판에 동작이 있는 분류 (14절). 장비에는 요구 능력치가 없다 (2026-10-10). */
    @Test
    void kitWeaponsExist() {
        for (Origins.Origin o : origins.all()) {
            boolean main = false;
            for (Origins.Kit k : o.kit()) {
                if (!k.kind().equals("weapon")) continue;
                Weapons.Def d = weapons.get(k.id());
                assertNotNull(d, o.id() + " 의 " + k.id());
                if ("main".equals(k.to())) {
                    main = true;
                    assertTrue(Origins.M1_CLASSES.contains(d.cls()), o.id() + " 주무기 분류 " + d.cls());
                }
            }
            assertTrue(main, o.id() + " 에 주무기가 없다");
        }
    }

    /** 왼손 줄은 정말 왼손으로 (YAML 의 off 가 거짓으로 읽혀 가방으로 가던 것). */
    @Test
    void offHandLines() {
        for (String id : List.of("knight", "thief", "deprived")) {
            assertTrue(origins.get(id).kit().stream().anyMatch(k -> "off".equals(k.to())), id + " 의 왼손 줄");
        }
        for (Origins.Origin o : origins.all()) {
            for (Origins.Kit k : o.kit()) {
                assertTrue(k.to() == null || k.to().equals("main") || k.to().equals("off") || k.to().startsWith("hotbar:"), o.id() + " " + k.to());
            }
        }
    }

    @Test
    void shieldsAreOffHand() {
        assertEquals(Weapons.OFF, weapons.get("plank_shield").hand());
        assertEquals(Weapons.MAIN, weapons.get("gaoler_club").hand());
    }

    @Test
    void warriorHoldsGreatswordTwoHanded() {
        Origins.Origin w = origins.get("warrior");
        assertTrue(w.kit().stream().noneMatch(k -> "off".equals(k.to())), "전사는 왼손이 비어 양손으로 잡는다");
        assertTrue(w.kit().stream().anyMatch(k -> k.id().equals("gaoler_greatsword")));
    }

    @Test
    void onlyThiefHasMasterKey() {
        for (Origins.Origin o : origins.all()) {
            boolean has = o.kit().stream().anyMatch(k -> k.kind().equals("item") && k.id().equals(MasterKey.ID));
            assertEquals(o.id().equals("thief"), has, o.id());
        }
    }

    /** 장부: 준 줄은 다시 주지 않는다. 지금 만들 수 없는 줄 (방어구·에스트·화살·술) 은 장부에 남지 않고 기다린다. */
    @Test
    void ledgerGivesOnce() {
        Origins.Origin t = origins.get("thief");
        Profile pr = Profile.fresh();
        List<String> creatable = new ArrayList<>();
        for (Origins.Kit k : t.kit()) if (Origins.creatable(k, weapons)) creatable.add(k.key());
        assertEquals(List.of("weapon:alley_dagger", "weapon:parrying_dagger", "item:master_key"), creatable);
        List<String> pending = Origins.pending(t, pr, weapons);
        assertTrue(pending.contains("armor:prisoner_rags") && pending.contains("item:estus"));
        for (String k : creatable) pr.markGiven(k);
        Profile again = Profile.parse(pr.toJson());
        for (Origins.Kit k : t.kit()) {
            boolean give = !again.wasGiven(k.key()) && Origins.creatable(k, weapons);
            assertFalse(give, "두 번 주지 않는다: " + k.key());
        }
    }

    /** 시작 값 (5.1 의 표): 최대 HP, 공격력, 술법 세기. 전사의 양손 대검이 가장 세고, 술법 세기는 마법사만. 공격력은 옛 판 (보정 C) 그대로. */
    @Test
    void startingDerivedValues() {
        var c = kr.souls.progression.StatCurves.defaults();
        var tiers = kr.souls.progression.LoadTiers.defaults();
        java.util.Map<String, kr.souls.progression.Derived> d = new java.util.LinkedHashMap<>();
        for (Origins.Origin o : origins.all()) {
            Weapons.Def main = null, off = null, cat = null;
            for (Origins.Kit k : o.kit()) {
                if (!k.kind().equals("weapon")) continue;
                Weapons.Def w = weapons.get(k.id());
                if ("main".equals(k.to())) main = w;
                else if ("off".equals(k.to())) off = w;
                if (kr.souls.progression.Stats.isCatalyst(w)) cat = w;
            }
            d.put(o.id(), kr.souls.progression.Derived.of(o.stats(), c, tiers, kr.souls.progression.Stats.arms(main), off == null,
                    cat == null ? null : kr.souls.progression.Stats.arms(cat), 0, 1.0));
        }
        assertEquals(535, d.get("knight").maxHp(), 1e-6);
        assertEquals(400, d.get("deprived").maxHp(), 1e-6);
        assertTrue(d.get("sorcerer").maxHp() < d.get("deprived").maxHp(), "마법사는 HP 가 낮다");
        assertTrue(d.get("warrior").twoHanded());
        double best = d.values().stream().mapToDouble(kr.souls.progression.Derived::attack).max().orElse(0);
        assertEquals(best, d.get("warrior").attack(), 1e-9, "양손 대검이 가장 세다");
        for (var en : d.entrySet()) {
            assertTrue(en.getValue().attack() > 0, en.getKey() + " 공격력");
            assertEquals(en.getKey().equals("sorcerer"), en.getValue().spellPower() > 0, en.getKey() + " 술법 세기");
        }
        assertEquals(72, Math.round(d.get("knight").attack()), "기사의 직검 (근력 13)");
        assertEquals(123, Math.round(d.get("warrior").attack()), "전사의 대검 양손 (근력 16 → 24)");
        assertEquals(121, Math.round(d.get("sorcerer").spellPower()), "마법사의 쇠단지 (지능 16)");
    }

    @Test
    void masterKeyOpensOnlyKeyDoors() {
        assertTrue(MasterKey.opensLock("gaol.upper_cell"));
        assertTrue(MasterKey.opensLock("barracks.cells"));
        assertFalse(MasterKey.opensLock("redin.west_tower"));
        assertFalse(MasterKey.opensLock("shrine.seal_left"));
        assertFalse(MasterKey.opensLock("nothing.here"));
    }
}
