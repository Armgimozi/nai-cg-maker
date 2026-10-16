package kr.labyrinth.items.unique;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.UniqueCatalog;
import kr.labyrinth.content.UniqueDef;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 고유 효과 닫힌 목록과 배정 데이터 (unique_spec §7·§8·§9.8, review2 A6·A11·A12, 주인 결정 B3).
 * 데이터 = {@link UniqueData} (무기 237개). items.yml 에 들어가는 것은 P3 — 여기서는 같은 꼴(unique 블록)로 읽어 검사한다.
 */
class UniqueEffectCatalogTest {

    static Content content;
    static Map<String, UniqueData.Entry> data;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        data = UniqueData.all();
    }

    @Test
    void closedListHas26EffectsIn12Directions() {
        assertEquals(26, UniqueCatalog.EFFECTS.size());
        assertEquals(12, UniqueCatalog.DIRECTIONS.size());
        Set<String> used = new HashSet<>();
        for (UniqueCatalog.Effect e : UniqueCatalog.EFFECTS.values()) {
            assertTrue(UniqueCatalog.DIRECTIONS.containsKey(e.direction()), e.id() + " 방향 " + e.direction());
            used.add(e.direction());
            assertFalse(e.params().isEmpty(), e.id());
            for (UniqueCatalog.Param p : e.params()) {
                if (p.kind() == UniqueCatalog.ParamKind.ENUM) continue;
                assertTrue(p.ref() >= p.lo() - 1e-9 && p.ref() <= p.hi() + 1e-9, e.id() + "." + p.key() + " 기준값이 범위 밖");
            }
        }
        assertEquals(UniqueCatalog.DIRECTIONS.keySet(), used, "방향 12개 모두 쓰임");
    }

    @Test
    void shieldBashIsRenamedBashStun() {
        // A12: 수호기사 직업 스킬 shield_bash 와 겹치지 않게
        assertNull(UniqueCatalog.EFFECTS.get("shield_bash"));
        assertNotNull(UniqueCatalog.get("shield_bash"));
        assertEquals("bash_stun", UniqueCatalog.get("shield_bash").id());
        UniqueDef old = UniqueDef.parse(Params.of(Map.of("unique", Map.of("id", "shield_bash", "name", "옛 이름", "n", 4))));
        assertEquals("bash_stun", old.id());
        for (UniqueData.Entry e : data.values()) assertFalse(e.effect().equals("shield_bash"), e.weaponId() + " 에 옛 id");
    }

    @Test
    void onlyRangedOnlyEffectIsLongshotAndSkillProcsMatchSpec() {
        List<String> ranged = new ArrayList<>();
        Set<String> onSkill = new HashSet<>();
        for (UniqueCatalog.Effect e : UniqueCatalog.EFFECTS.values()) {
            if (e.rangedOnly()) ranged.add(e.id());
            if (e.onSkill()) onSkill.add(e.id());
        }
        assertEquals(List.of("longshot"), ranged);
        // unique_spec §7 폭주 방지 1: 스킬 적중에도 켜지는 것
        assertEquals(Set.of("rend", "hemorrhage", "execute", "exploit", "backstab", "first_strike", "berserk", "armor_break", "imbue"),
                onSkill);
        // review2 §9.2: 재발동 연쇄 번개 0.3초 · 축성 0.25초
        assertEquals(0.3, UniqueCatalog.get("chain_spark").icd(), 1e-9);
        assertEquals(0.25, UniqueCatalog.get("sanctify").icd(), 1e-9);
        assertEquals(0.30, UniqueCatalog.get("chain_spark").param("chance").ref(), 1e-9);
    }

    @Test
    void everyBundledWeaponHasAnAssignmentMatchingItsAttack() {
        int n = 0;
        for (ItemDef d : content.items().values()) {
            if (!d.isWeapon()) continue;
            n++;
            UniqueData.Entry e = data.get(d.id());
            assertNotNull(e, d.id() + " 배정 없음");
            assertFalse(e.isNew(), d.id());
            assertEquals(d.attack().style(), e.attack().style(), d.id() + " 방식");
            assertEquals(d.attack().interval(), e.attack().interval(), 1e-9, d.id() + " 간격");
        }
        assertEquals(131, n);
        assertEquals(237, data.size(), "기존 131 + 새 106");
        assertEquals(106, data.values().stream().filter(UniqueData.Entry::isNew).count());
    }

    @Test
    void everyAssignmentPassesTheCatalogCheck() {
        List<String> problems = new ArrayList<>();
        for (UniqueData.Entry e : data.values()) {
            UniqueDef u = e.def();
            assertNotNull(u, e.weaponId());
            assertNotNull(u.effect(), e.weaponId() + " 닫힌 목록에 없음: " + e.effect());
            assertEquals(u.effect().direction(), e.direction(), e.weaponId() + " 방향이 효과와 다름");
            UniqueCatalog.Check c = UniqueCatalog.check(u, e.attack());
            for (String x : c.errors()) problems.add(e.weaponId() + ": " + x);
            for (String x : c.warnings()) problems.add(e.weaponId() + " (경고): " + x);
        }
        assertTrue(problems.isEmpty(), () -> String.join("\n", problems));
    }

    @Test
    void intervalRulesAreStoredPerWeapon() {
        for (UniqueData.Entry e : data.values()) {
            UniqueDef u = e.def();
            double iv = e.attack().interval();
            if (u.is("imbue")) {
                // §9.8: 확률 = round(0.25 × min(1.5, 간격 ÷ 0.67), 2) — 서비스는 다시 곱하지 않는다(저장값 그대로)
                assertEquals(Math.round(0.25 * Math.min(1.5, iv / 0.67) * 100) / 100.0, u.num("chance"), 0.0101, e.weaponId());
                assertTrue(UniqueCatalog.ELEMENTS.contains(u.text("element", "")), e.weaponId());
            }
            if (u.is("bash_stun")) {
                int n = u.count("n");
                assertTrue(n == UniqueCatalog.bashN(4, iv) || n == UniqueCatalog.bashN(5, iv), e.weaponId() + " n=" + n);
                assertTrue(n >= 2 && n <= 8);
            }
            if (u.is("longshot")) assertTrue(e.attack().ranged(), e.weaponId() + " 원거리 아님");
        }
    }

    @Test
    void tooltipDescriptionsFit() {
        for (UniqueData.Entry e : data.values()) {
            assertEquals(2, e.tooltip().size(), e.weaponId());
            assertTrue(e.tooltip().get(1).strip().length() <= 34, e.weaponId() + " 설명 " + e.tooltip().get(1).strip().length() + "자");
            assertFalse(e.name().isBlank(), e.weaponId());
        }
    }

    @Test
    void ownerDecisionB3WeakensTheTwoBossLegendaries() {
        // 먹물 서고 지팡이 · 종말시계 단두도끼: 강도 0.6 (강도 비례 수치 = 기준값 × 0.6)
        UniqueData.Entry ink = data.get("inkwell_staff");
        UniqueData.Entry doom = data.get("doomclock_executioner");
        assertEquals(0.6, ink.strength(), 1e-9);
        assertEquals(0.6, doom.strength(), 1e-9);
        assertEquals("death_burst", ink.effect());
        assertEquals(0.80 * 0.6, ink.def().num("pct"), 1e-9);
        assertEquals("execute", doom.effect());
        assertEquals(0.25 * 0.6, doom.def().num("pct"), 1e-9);
        assertTrue(ink.tooltip().get(1).contains("48%"), ink.tooltip().get(1));
        assertTrue(doom.tooltip().get(1).contains("+15%"), doom.tooltip().get(1));
    }

    @Test
    void parserReadsTheUniqueBlockAndDefaultsMissingNumbers() {
        Map<String, Object> raw = new LinkedHashMap<>();
        raw.put("type", "weapon");
        raw.put("attack", Map.of("style", "melee", "interval", 0.48, "kind", "physical"));
        raw.put("unique", Map.of("id", "REND", "name", "아물지 않는 상처", "pct", 0.15));
        ItemDef d = weapon("spore_kris_test", Params.of(raw));
        assertNotNull(d.unique());
        assertEquals("rend", d.unique().id());
        assertEquals("아물지 않는 상처", d.unique().name());
        assertEquals(0.15, d.unique().num("pct"), 1e-9);
        assertEquals(4, d.unique().num("duration"), 1e-9, "빠진 수치 = 카탈로그 기준값");
        assertEquals(5, d.unique().count("max_stacks"));
        // 무기가 아니면 고유 효과 없음
        ItemDef armor = new ItemDef("x", "x", ItemType.ARMOR, null, "chest", null, Rarity.COMMON, 1, List.of(), Map.of(), null, null,
                List.of(), 1, true, List.of(), Params.EMPTY, Params.EMPTY, Params.EMPTY, "", Params.of(raw));
        assertNull(armor.unique());
        // withRequires 는 고유 효과를 그대로
        assertEquals(d.unique(), d.withRequires(null).unique());
    }

    @Test
    void catalogCheckCatchesBadData() {
        WeaponAttack melee = new WeaponAttack(WeaponAttack.Style.MELEE, 0.67, DamageKind.PHYSICAL, 1.0);
        assertFalse(UniqueCatalog.check(def("nope", Map.of()), melee).ok(), "닫힌 목록 밖");
        assertFalse(UniqueCatalog.check(def("longshot", Map.of("pct", 0.2)), melee).ok(), "관통 사격은 원거리만");
        assertFalse(UniqueCatalog.check(def("rend", Map.of("pct", 0.5)), melee).ok(), "상한 0.15 넘음");
        assertFalse(UniqueCatalog.check(def("cleave", Map.of("targets", 2.5)), melee).ok(), "정수 단계");
        assertFalse(UniqueCatalog.check(def("imbue", Map.of("chance", 0.25, "pct", 0.1)), melee).ok(), "element 없음");
        assertFalse(UniqueCatalog.check(def("imbue", Map.of("element", "acid")), melee).ok(), "element 닫힌 목록");
        assertTrue(UniqueCatalog.check(def("imbue", Map.of("element", "frost", "chance", 0.25)), melee).ok());
        assertFalse(UniqueCatalog.check(def("rend", Map.of("pctt", 0.1)), melee).warnings().isEmpty(), "모르는 키는 경고");
        // 선제·추격·흘려치기는 상한 × g (단검 0.45초 g ≈ 1.6 → 1.8 × 1.6)
        WeaponAttack dagger = new WeaponAttack(WeaponAttack.Style.MELEE, 0.45, DamageKind.PHYSICAL, 1.0);
        assertTrue(UniqueCatalog.check(def("first_strike", Map.of("pct", 2.88)), dagger).ok());
        assertFalse(UniqueCatalog.check(def("first_strike", Map.of("pct", 2.88)), melee).ok());
        assertFalse(UniqueCatalog.check(def("imbue", Map.of("element", "burn", "chance", 0.38)), melee).warnings().isEmpty(),
                "간격 0.67초면 확률 0.25");
    }

    private static UniqueDef def(String id, Map<String, Object> params) { return new UniqueDef(id, null, Params.of(params)); }

    private static ItemDef weapon(String id, Params raw) {
        return new ItemDef(id, id, ItemType.WEAPON, null, null, null, Rarity.RARE, 11, List.of(), Map.of(), null, null, List.of(), 0,
                true, List.of(), Params.EMPTY, Params.EMPTY, Params.EMPTY, "", raw);
    }
}
