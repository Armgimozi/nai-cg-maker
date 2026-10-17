package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.loot.LootRoller;
import kr.labyrinth.stats.Stat;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 0.3.7 신화 무기 12 (직업마다 둘 — tools/data/037/mythic_037.json · tools/gen_037_mythic.py).
 * <p>주인 결정: 신화 6 → 12, 직업마다 둘째 신화는 짝과 다른 무기 종류·노는 방식. 획득 = 8·9·10층 보스 + 대장간(신화 도안), 모든 난이도.
 * <p>지수 메모 (DPS 모델 wdps — 46~50 띠 가운데값 774.4 = 100, 새 6 을 넣으면 812.5): 태산의 대망치 158 (탱커 파티 값 약 195) ·
 * 만조의 큰낫 194 (3마리 324) · 꼬리별 장궁 171 (12칸 밖 사냥꾼 245) · 도깨비불 등롱 198 (MP 제한 90%) · 새벽의 종 135 (힐러 —
 * 파티 값 약 218) · 그믐달 사슬낫 194 (그림자 231). 새로 300 을 넘는 것은 없다 — 공허의 심장(306)은 손대지 않음.
 * 수치는 이 시험이 다시 셈하지 않는다 (DPS 모델은 저장소 밖). 여기서는 짜임(짝·요구·출처·확률 순서·제작 비용)을 본다.
 */
class MythicSetTest {

    static Content content;
    static JsonObject spec;
    static ConfigurationSection lootYaml;
    static List<String> mythics;

    @BeforeAll
    static void load() throws IOException {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        spec = JsonParser.parseString(Files.readString(Path.of("../tools/data/037/mythic_037.json"), StandardCharsets.UTF_8))
                .getAsJsonObject();
        lootYaml = YamlConfiguration.loadConfiguration(new File("src/main/resources/content/loot.yml")).getConfigurationSection("tables");
        mythics = new ArrayList<>();
        spec.getAsJsonArray("mythics").forEach(x -> mythics.add(x.getAsString()));
    }

    static List<ItemDef> mythicWeapons() {
        return content.items().values().stream().filter(d -> d.isWeapon() && d.rarity() == Rarity.MYTHIC).toList();
    }

    /** loot.yml 표의 entries 원문 (blueprint_of 는 LootTable 을 거치지 않고 읽는다). */
    static List<Map<?, ?>> rawEntries(String table) {
        ConfigurationSection t = lootYaml.getConfigurationSection(table);
        return t == null ? List.of() : t.getMapList("entries");
    }

    @Test
    void twelveMythicsTwoPerClass() {
        Set<String> got = new TreeSet<>();
        for (ItemDef d : mythicWeapons()) got.add(d.id());
        assertEquals(new TreeSet<>(mythics), got, "신화 무기 = 명세 12");
        assertEquals(12, got.size());
        Map<String, List<String>> byClass = new TreeMap<>();
        JsonObject cls = spec.getAsJsonObject("class");
        for (String id : mythics) byClass.computeIfAbsent(cls.get(id).getAsString(), k -> new ArrayList<>()).add(id);
        assertEquals(Set.of("guardian", "berserker", "hunter", "arcanist", "priest", "shadow"), byClass.keySet());
        for (var e : byClass.entrySet()) {
            assertEquals(2, e.getValue().size(), e.getKey() + " 신화 " + e.getValue());
            ItemDef a = content.item(e.getValue().get(0)), b = content.item(e.getValue().get(1));
            // 짝끼리 무기 종류(모양)가 다르다
            assertNotEquals(a.model().str("shape"), b.model().str("shape"), e.getKey() + " 짝 모양이 같음");
            // 요구 1위가 다르거나, 같으면 둘째가 다르다 (빌드 갈래 · 드롭 편향이 갈림)
            List<Map.Entry<Stat, Integer>> ra = a.requirement().ordered(), rb = b.requirement().ordered();
            boolean differ = ra.get(0).getKey() != rb.get(0).getKey() || ra.get(1).getKey() != rb.get(1).getKey();
            assertTrue(differ, e.getKey() + " 짝 요구 " + ra + " · " + rb);
            assertEquals(a.levelReq(), b.levelReq(), e.getKey());
            assertEquals(a.tier(), b.tier(), e.getKey());
            assertNotNull(a.aura(), a.id() + " 아우라");
            assertNotNull(b.aura(), b.id() + " 아우라");
            assertNotEquals(a.aura(), b.aura(), e.getKey() + " 짝 아우라가 같음");
        }
        // 짝 (명세 pair) 은 같은 직업
        JsonObject pair = spec.getAsJsonObject("pair");
        for (String n : pair.keySet()) assertEquals(cls.get(n).getAsString(), cls.get(pair.get(n).getAsString()).getAsString(), n);
    }

    @Test
    void everyMythicIsBossPlusForge() {
        Map<String, RecipeDef> recipeOf = new HashMap<>();
        for (RecipeDef r : content.recipes().values()) recipeOf.putIfAbsent(r.result(), r);
        for (String id : mythics) {
            ItemDef d = content.item(id);
            assertEquals(List.of("boss", "craft"), d.sources(), id);
            RecipeDef r = recipeOf.get(id);
            assertNotNull(r, id + " 레시피");
            assertEquals(id, r.id(), "레시피 id = 결과 id");
            assertEquals(d.levelReq(), r.levelReq(), id);
            // 신화 도안 출처 하나 이상 (blueprint_of)
            int sources = 0;
            for (String t : lootYaml.getKeys(false)) {
                for (Map<?, ?> e : rawEntries(t)) {
                    if (e.get("blueprint_of") instanceof List<?> l && l.contains(id)) {
                        sources++;
                        assertFalse(e.containsKey("min_difficulty"), t + " 신화 도안에 난이도 제한");
                    }
                }
            }
            assertTrue(sources >= 1, id + " 신화 도안 출처 없음");
        }
    }

    @Test
    void floorTenDropsAllAndPerItemOddsFallWithTheFloor() {
        Map<Integer, Map<String, Double>> perItem = new TreeMap<>();
        for (int f = 8; f <= 10; f++) {
            LootTable t = content.lootTable(content.bossOfFloor(f).drops());
            for (LootTable.Entry e : t.entries()) {
                if (e.kind() != LootTable.Kind.ONE_OF || !mythics.containsAll(e.oneOf())) continue;
                assertEquals(null, e.minDifficulty(), f + "층 신화 줄에 난이도 제한");
                for (String id : e.oneOf()) perItem.computeIfAbsent(f, k -> new TreeMap<>()).put(id, e.chance() / e.oneOf().size());
            }
        }
        assertEquals(new TreeSet<>(mythics), perItem.get(10).keySet(), "10층 넬카르 표에 12개 모두");
        assertEquals(0.08 / 12, perItem.get(10).get("tempest_bow"), 1e-9, "10층 한 개당 = 지금(6개 · 0.04)과 같음");
        for (String id : mythics) {
            double p10 = perItem.get(10).get(id);
            double p9 = perItem.getOrDefault(9, Map.of()).getOrDefault(id, 0.0);
            double p8 = perItem.getOrDefault(8, Map.of()).getOrDefault(id, 0.0);
            assertTrue(p10 > p9 && p10 > p8, id + " 한 개당 10층이 가장 높아야 함: " + p10 + " · " + p9 + " · " + p8);
            if (!id.equals("voidheart_staff")) assertTrue(p9 > 0 ^ p8 > 0, id + " 8·9층 중 한 곳에만");
            else assertTrue(p9 == 0 && p8 == 0, "공허의 심장은 10층에서만 (너무 세다는 판정 — 공급을 넓히지 않음)");
        }
        // 직업마다 하나는 8층, 하나는 9층 (비전술사는 등롱 8층 · 공허 10층만)
        JsonObject cls = spec.getAsJsonObject("class");
        Map<String, Set<Integer>> homes = new TreeMap<>();
        for (int f = 8; f <= 9; f++) {
            for (String id : perItem.getOrDefault(f, Map.of()).keySet()) homes.computeIfAbsent(cls.get(id).getAsString(), k -> new TreeSet<>()).add(f);
        }
        for (var e : homes.entrySet()) {
            assertEquals(e.getKey().equals("arcanist") ? Set.of(8) : Set.of(8, 9), e.getValue(), e.getKey());
        }
        // 한 개당: 9층(5개 0.015) > 8층(6개 0.012) — 10층 > 9층 > 8층
        double nine = perItem.get(9).values().iterator().next(), eight = perItem.get(8).values().iterator().next();
        assertTrue(perItem.get(10).get("tempest_bow") > nine && nine > eight, nine + " · " + eight);
        // 신화 아이템은 보스 표에서만 (특별 시련·금고·미믹은 도안만)
        for (String t : lootYaml.getKeys(false)) {
            if (t.matches("floor(08|09|10)_boss")) continue;
            for (Map<?, ?> e : rawEntries(t)) {
                Object ids = e.get("one_of");
                if (ids instanceof List<?> l) for (Object x : l) assertFalse(mythics.contains(String.valueOf(x)), t + " 에 신화 " + x);
                assertFalse(mythics.contains(String.valueOf(e.get("item"))), t + " 에 신화 " + e.get("item"));
            }
        }
    }

    @Test
    void forgeIsALongGoalNotAShortcut() {
        // 레시피 12 는 같은 꼴: 10층 재료 + 오리하르콘 주괴 · 용혈석 + 400,000G. 묶는 것 = 심연 심장 파편 50 (넬카르 처치마다 1)
        int core = 0;
        for (LootTable.Entry e : content.lootTable("floor10_boss").guaranteed()) {
            if ("abyssal_heart_fragment".equals(e.item())) core = e.amount().max();
        }
        assertEquals(1, core, "넬카르 처치마다 심장 파편 1");
        int maxOther = 0;
        for (RecipeDef r : content.recipes().values()) {
            ItemDef res = content.item(r.result());
            if (res != null && res.rarity() != Rarity.MYTHIC) maxOther = Math.max(maxOther, r.gold());
        }
        double bias = content.lootSettings().ownBuildBias();
        for (String id : mythics) {
            RecipeDef r = content.recipes().get(id);
            ItemDef d = content.item(id);
            assertTrue(r.materials().get("abyssal_heart_fragment") >= 50, id + " 핵 50 (넬카르 50번)");
            assertTrue(r.gold() >= 10 * maxOther, id + " 골드 " + r.gold() + " — 가장 비싼 다른 레시피 " + maxOther + " 의 10배 이상");
            for (String m : r.materials().keySet()) {
                ItemDef md = content.item(m);
                assertNotNull(md, m);
                if (md.isMineMaterial()) assertTrue(Set.of("orichalcum_ingot", "dragonblood_stone").contains(m), id + " 광산 재료 " + m);
                else if (!m.equals("primordial_essence")) assertEquals(10, md.floor(), id + " 의 " + m + " 는 10층 재료가 아님");   // 태고 정수 = 10층 등급 정수
            }
            // 내 빌드(요구 위 둘)로 10층에서 그 신화를 드롭으로 얻는 기대 회차 — 제작(핵 50회)이 그보다 훨씬 짧으면 지름길
            List<Stat> build = new ArrayList<>();
            for (var x : d.requirement().ordered()) if (build.size() < LootRoller.BUILD_TOP) build.add(x.getKey());
            int fit = 0;
            for (String o : mythics) if (LootRoller.fitsBuild(content.item(o), build)) fit++;
            double perKill = 0.08 * (bias / fit + (1 - bias) / mythics.size());
            double dropRuns = 1 / perKill;
            assertTrue(50 >= 0.5 * dropRuns && 50 <= 2.0 * dropRuns, id + " 제작 50회 vs 드롭 기대 " + Math.round(dropRuns) + "회");
        }
    }

    @Test
    void uniqueStrengthStaysMythicLow() throws IOException {
        JsonObject ua = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/unique_assign.json"), StandardCharsets.UTF_8))
                .getAsJsonObject();
        for (String id : mythics) {
            JsonObject e = ua.getAsJsonObject(id);
            assertNotNull(e, id + " 고유 효과 배정");
            double s = e.get("strength").getAsDouble();
            assertTrue(s >= 0.5 - 1e-9 && s <= 0.8 + 1e-9, id + " 강도 " + s);
            List<String> kinds = new ArrayList<>();
            e.getAsJsonObject("weapon").getAsJsonArray("source_kinds").forEach(x -> kinds.add(x.getAsString()));
            assertEquals(List.of("B", "F"), kinds, id + " 획득처 종류 (보스 + 대장간 — source_factor 1.0)");
            assertEquals(1.0, e.get("source_factor").getAsDouble(), 1e-9, id);
            assertEquals(e.get("effect").getAsString(), content.item(id).unique().id(), id);
        }
    }
}
