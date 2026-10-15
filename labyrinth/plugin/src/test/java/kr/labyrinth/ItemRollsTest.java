package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.EquipRules;
import kr.labyrinth.items.ItemMigration035;
import kr.labyrinth.items.ItemRolls;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.stats.Stat;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 장비 스탯 굴림·인코딩·품질·툴팁·착용 조건. */
class ItemRollsTest {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @Test
    void sameSeedSameRolls() {
        ItemDef def = content.item("ember_greatsword");
        assertNotNull(def);
        assertEquals(ItemRolls.roll(def, 42L), ItemRolls.roll(def, 42L));
    }

    @Test
    void everyGearRollStaysInRangeAndIsRounded() {
        int checked = 0;
        for (ItemDef def : content.items().values()) {
            if (!def.isGear()) continue;
            for (long seed = 0; seed < 40; seed++) {
                Map<String, Double> r = ItemRolls.roll(def, seed * 7919L + def.id().hashCode());
                assertEquals(def.stats().size(), r.size(), def.id());
                for (Map.Entry<String, Range> e : def.stats().entrySet()) {
                    double v = r.get(e.getKey());
                    double lo = ItemRolls.round(e.getKey(), e.getValue().min());
                    double hi = ItemRolls.round(e.getKey(), e.getValue().max());
                    assertTrue(v >= Math.min(lo, hi) - 1e-9 && v <= Math.max(lo, hi) + 1e-9,
                            def.id() + "." + e.getKey() + "=" + v + " not in " + e.getValue());
                    if (ItemRolls.INT_KEYS.contains(e.getKey())) assertEquals(Math.rint(v), v, 1e-9, def.id() + "." + e.getKey());
                }
                checked++;
            }
        }
        assertTrue(checked > 1000);
    }

    @Test
    void rollsCoverTheRange() {
        ItemDef def = content.item("ember_greatsword");
        Range dmg = def.stats().get("damage");
        double min = Double.MAX_VALUE, max = -Double.MAX_VALUE;
        for (long s = 0; s < 2000; s++) {
            double v = ItemRolls.roll(def, s).get("damage");
            min = Math.min(min, v);
            max = Math.max(max, v);
        }
        assertEquals(Math.round(dmg.min()), min, 1e-9);
        assertEquals(Math.round(dmg.max()), max, 1e-9);
    }

    @Test
    void encodeDecodeRoundTrip() {
        ItemDef def = content.item("ember_greatsword");
        Map<String, Double> r = ItemRolls.roll(def, 123L);
        Map<String, Double> back = ItemRolls.decode(ItemRolls.encode(r));
        assertEquals(r.keySet(), back.keySet());
        r.forEach((k, v) -> assertEquals(v, back.get(k), 1e-9, k));
        assertTrue(ItemRolls.decode("garbage;;x=;=3;damage=5").containsKey("damage"));
        assertTrue(ItemRolls.decode(null).isEmpty());
    }

    @Test
    void qualityBounds() {
        ItemDef def = content.item("ember_greatsword");
        Map<String, Double> lo = new java.util.LinkedHashMap<>();
        Map<String, Double> hi = new java.util.LinkedHashMap<>();
        def.stats().forEach((k, r) -> {
            lo.put(k, r.min());
            hi.put(k, r.max());
        });
        assertEquals(0.0, ItemRolls.quality(def, lo), 1e-9);
        assertEquals(1.0, ItemRolls.quality(def, hi), 1e-9);
        double q = ItemRolls.quality(def, ItemRolls.midpoint(def));
        assertTrue(q > 0.3 && q < 0.7, "midpoint quality " + q);
    }

    @Test
    void tooltipHasRequirementsStatsAndSkills() {
        ItemDef def = content.item("ember_greatsword").withRequires(StatRequirement.of(Map.of(Stat.STR, 60), Map.of()));
        List<String> lines = ItemTooltip.lines(content, def, ItemRolls.roll(def, 1L));
        String all = String.join("\n", lines);
        assertTrue(all.contains("요구 힘 <white>60"), all);
        assertFalse(all.contains("요구 레벨"), all);
        assertTrue(all.contains("피해"), all);
        assertTrue(all.contains("잿불 검기"), all);
        assertFalse(all.contains("굴림 품질"), all); // 굴림 품질은 표시하지 않는다
        assertTrue(all.contains("아우라"), all);
        // 미리보기(굴림 없음)는 범위
        assertFalse(String.join("\n", ItemTooltip.lines(content, def, null)).contains("굴림 품질"));
    }

    @Test
    void equipRules() {
        ItemDef def = content.item("ember_greatsword").withRequires(StatRequirement.of(Map.of(Stat.STR, 60), Map.of()));
        ClassDef berserker = content.classDef("berserker"), priest = content.classDef("priest");
        Map<Stat, Integer> low = StatRequirement.playerStats(berserker, Map.of(Stat.STR, 40), Map.of());
        assertEquals(EquipRules.Problem.STATS, EquipRules.check(def, low));
        assertEquals("요구 힘 60 (현재 " + low.get(Stat.STR) + ")", EquipRules.problemText(def, low));
        // 직업 제한 없음: 광전사 추천 대검도 사제·직업 없음이 힘만 맞추면 그대로 쓴다
        assertEquals(EquipRules.Problem.NONE, EquipRules.check(def, StatRequirement.playerStats(priest, Map.of(Stat.STR, 60), Map.of())));
        assertEquals(EquipRules.Problem.NONE, EquipRules.check(def, StatRequirement.playerStats(null, Map.of(Stat.STR, 60), Map.of())));
        assertEquals("", EquipRules.problemText(def, StatRequirement.playerStats(null, Map.of(Stat.STR, 60), Map.of())));
        // 재료·장신구는 조건 없음 (장신구는 requires 가 적혀 있어도 무시)
        ItemDef mat = content.item("moss_fiber");
        assertEquals(EquipRules.Problem.NONE, EquipRules.check(mat, Map.of()));
        ItemDef acc = content.items().values().stream().filter(d -> d.type() == ItemType.ACCESSORY).findFirst().orElseThrow()
                .withRequires(StatRequirement.of(Map.of(Stat.LUK, 99), Map.of()));
        assertTrue(acc.requirement().isEmpty());
        assertEquals(EquipRules.Problem.NONE, EquipRules.check(acc, Map.of()));
    }

    // ── 0.3.5 굴림 옮기기 (ItemMigration035) ─────────────────────────────

    @Test
    void migrationKeepsRelativePositionInNewRange() {
        Range old = new Range(20, 30), now = new Range(40, 60);
        assertEquals(40, ItemMigration035.migrateDamage(20, old, now), "최소 → 최소");
        assertEquals(60, ItemMigration035.migrateDamage(30, old, now), "최대 → 최대");
        assertEquals(50, ItemMigration035.migrateDamage(25, old, now));
        assertEquals(44, ItemMigration035.migrateDamage(22, old, now));
        // 범위가 같으면 그대로, 폭 0 범위는 가운데로
        assertEquals(27, ItemMigration035.migrateDamage(27, old, old));
        assertEquals(15, ItemMigration035.migrateDamage(10, new Range(10, 10), new Range(14, 16)));
        // 옛 범위 밖(관리자 지급 등)은 가운데값 비율 (25 → 50 = ×2)
        assertEquals(80, ItemMigration035.migrateDamage(40, old, now));
        assertEquals(10, ItemMigration035.migrateDamage(5, old, now));
    }

    @Test
    void migrationTouchesOnlyWeaponDamageOnce() {
        ItemDef sword = content.item("corridor_longsword");
        Range old = ItemMigration035.OLD_DAMAGE.get(sword.id());
        assertNotNull(old);
        ItemDef rebased = withDamage(sword, new Range(8, 10)); // combat_spec 새 한 방 범위
        Map<String, Double> rolls = new java.util.LinkedHashMap<>();
        rolls.put("damage", old.max());
        rolls.put("crit_chance", 0.031);
        Map<String, Double> out = ItemMigration035.migrate(rebased, rolls);
        assertEquals(10.0, out.get("damage"), 1e-9);
        assertEquals(0.031, out.get("crit_chance"), 1e-9, "다른 스탯 굴림은 그대로");
        assertEquals(rolls.get("damage"), old.max(), 1e-9, "입력 맵은 그대로");
        // 지금 데이터 = 새 범위 (P0b 가 items.yml 에 넣음) → 같은 결과, 범위가 같으면 아무것도 안 바뀐다
        assertEquals(new Range(8, 10), sword.stats().get("damage"));
        assertEquals(out, ItemMigration035.migrate(sword, rolls));
        assertEquals(rolls, ItemMigration035.migrate(withDamage(sword, old), rolls));
        // 깃발 35 면 다시 옮기지 않음, 장비가 아니면 옮길 것 없음
        assertTrue(ItemMigration035.needed(sword, 0));
        assertFalse(ItemMigration035.needed(sword, ItemMigration035.VERSION));
        ItemDef potion = content.items().values().stream().filter(d -> d.type() == ItemType.CONSUMABLE).findFirst().orElseThrow();
        assertFalse(ItemMigration035.needed(potion, 0));
        // 방어구·표에 없는 무기는 피해 굴림을 건드리지 않음
        ItemDef armor = content.items().values().stream().filter(d -> d.type() == ItemType.ARMOR).findFirst().orElseThrow();
        assertEquals(Map.of("defense", 5.0), ItemMigration035.migrate(armor, Map.of("defense", 5.0)));
    }

    @Test
    void migrationTableCoversAll034Weapons() {
        assertEquals(131, ItemMigration035.OLD_DAMAGE.size());
        for (Map.Entry<String, Range> e : ItemMigration035.OLD_DAMAGE.entrySet()) {
            ItemDef d = content.item(e.getKey());
            assertNotNull(d, e.getKey());
            assertTrue(d.isWeapon(), e.getKey());
            assertTrue(e.getValue().min() > 0 && e.getValue().max() >= e.getValue().min(), e.getKey());
        }
    }

    private static ItemDef withDamage(ItemDef d, Range dmg) {
        Map<String, Range> stats = new java.util.LinkedHashMap<>(d.stats());
        stats.put("damage", dmg);
        return new ItemDef(d.id(), d.name(), d.type(), d.attack(), d.armorSlot(), d.armorSet(), d.rarity(), d.levelReq(),
                d.requires(), d.classes(), stats, d.setBonus(), d.aura(), d.weaponSkills(), d.floor(), d.pool(), d.sources(),
                d.use(), d.model(), d.texture(), d.lore(), d.raw());
    }
}
