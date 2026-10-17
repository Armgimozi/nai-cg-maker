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
import kr.labyrinth.stats.Stat;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 0.3.7 신화 무기 12 (직업마다 둘 — tools/data/037/mythic_037.json · tools/gen_037_mythic.py).
 * <p>주인 결정: 신화 6 → 12, 직업마다 둘째 신화는 짝과 다른 무기 종류·노는 방식. 모든 난이도.
 * <p>CR37 주인 결정: 옛 6 = 넬카르가 한 자루마다 20% + 대장간(신화 도안), 새 6 = 대장간(신화 도안)만. 넬카르를 못 잡아도 만든다.
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
        newSix = new ArrayList<>();
        spec.getAsJsonArray("new").forEach(x -> newSix.add(x.getAsString()));
    }

    /** 새 신화 6 (명세 new) — 도안 제작만. 나머지 6 = 옛 신화 (넬카르 드롭 + 대장간). */
    static List<String> newSix;

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
            assertEquals(newSix.contains(id) ? List.of("craft") : List.of("boss", "craft"), d.sources(), id);
            RecipeDef r = recipeOf.get(id);
            assertNotNull(r, id + " 레시피");
            assertEquals(id, r.id(), "레시피 id = 결과 id");
            assertEquals(d.levelReq(), r.levelReq(), id);
            // 신화 도안 출처 하나 이상 (blueprint_of) — 넬카르 밖에도 하나 이상 (넬카르를 못 잡아도 도안이 나온다, CR37)
            int sources = 0, outside = 0;
            for (String t : lootYaml.getKeys(false)) {
                for (Map<?, ?> e : rawEntries(t)) {
                    if (e.get("blueprint_of") instanceof List<?> l && l.contains(id)) {
                        sources++;
                        if (!t.equals("floor10_boss")) outside++;
                        assertFalse(e.containsKey("min_difficulty"), t + " 신화 도안에 난이도 제한");
                    }
                }
            }
            assertTrue(sources >= 1, id + " 신화 도안 출처 없음");
            assertTrue(outside >= 1, id + " 넬카르 밖 신화 도안 출처 없음");
        }
    }

    @Test
    void nelkarDropsEachOldMythicAtTwentyPercent() {
        // CR37 주인 결정: 넬카르가 옛 신화 6 을 한 자루마다 따로 20% (item 줄 여섯 — one_of 가 아니라 빌드 편향 없음). 새 6 은 드롭이 없다.
        List<String> oldSix = new ArrayList<>(mythics);
        oldSix.removeAll(newSix);
        assertEquals(6, oldSix.size());
        Map<String, Double> perItem = new TreeMap<>();
        for (LootTable.Entry e : content.lootTable(content.bossOfFloor(10).drops()).entries()) {
            if (e.kind() == LootTable.Kind.ONE_OF) assertFalse(e.oneOf().stream().anyMatch(mythics::contains), "넬카르 신화는 한 자루마다 한 줄 (one_of 아님)");
            if (e.kind() == LootTable.Kind.ITEM && mythics.contains(e.item())) {
                assertEquals(null, e.minDifficulty(), e.item() + " 신화 줄에 난이도 제한");
                assertEquals(null, perItem.put(e.item(), e.chance()), e.item() + " 줄이 둘");
            }
        }
        assertEquals(new TreeSet<>(oldSix), perItem.keySet(), "넬카르 = 옛 신화 6");
        for (var e : perItem.entrySet()) assertEquals(0.2, e.getValue(), 1e-9, e.getKey() + " 한 자루마다 20%");
        // 신화 아이템은 넬카르 표에만 (8·9층 보스 · 특별 시련 · 금고·미믹 · 상자에는 도안만) · 새 6 은 어디에도 없다
        for (String t : lootYaml.getKeys(false)) {
            for (Map<?, ?> e : rawEntries(t)) {
                List<String> ids = new ArrayList<>();
                if (e.get("one_of") instanceof List<?> l) for (Object x : l) ids.add(String.valueOf(x));
                if (e.get("item") != null) ids.add(String.valueOf(e.get("item")));
                for (String x : ids) {
                    if (!mythics.contains(x)) continue;
                    assertEquals("floor10_boss", t, t + " 에 신화 " + x);
                    assertFalse(newSix.contains(x), t + " 에 새 신화 " + x + " (도안 제작만)");
                }
            }
        }
    }

    @Test
    void forgeNeedsNoNelkarOnlyMaterial() {
        // CR37: 레시피 12 는 같은 꼴 — 10층 몹·정예·상자 재료(큰 부위 150 · 작은 부위 50, 근접과 활·시전이 서로 바뀜) + 태고 정수
        // + 오리하르콘 주괴 · 용혈석 + 골드. 보스만 주는 재료(심연 심장 파편)는 없다 — 넬카르를 못 잡아도 만든다.
        // 회차 목표(재료 하나하나 10층 4회 안 · 골드 약 5회 · 제작 8~10회 / 넬카르 없이 12~16회)는 craft2/final 모델이 셈 — 여기서는 꼴만 본다.
        int maxOther = 0;
        for (RecipeDef r : content.recipes().values()) {
            ItemDef res = content.item(r.result());
            if (res != null && res.rarity() != Rarity.MYTHIC) maxOther = Math.max(maxOther, r.gold());
        }
        List<Integer> shape = null;
        int gold = -1;
        for (String id : mythics) {
            RecipeDef r = content.recipes().get(id);
            assertNotNull(r, id);
            assertFalse(r.materials().containsKey("abyssal_heart_fragment"), id + " 심연 심장 파편 (넬카르만) 이 듦");
            for (String m : r.materials().keySet()) {
                ItemDef md = content.item(m);
                assertNotNull(md, m);
                assertNotEquals(List.of("boss"), md.sources(), id + " 의 " + m + " 는 보스만 준다");
                if (md.isMineMaterial()) assertTrue(Set.of("orichalcum_ingot", "dragonblood_stone").contains(m), id + " 광산 재료 " + m);
                else if (!m.equals("primordial_essence")) assertEquals(10, md.floor(), id + " 의 " + m + " 는 10층 재료가 아님");   // 태고 정수 = 10층 등급 정수
            }
            List<Integer> counts = new ArrayList<>(r.materials().values());
            counts.sort(Integer::compare);
            if (shape == null) shape = counts;
            assertEquals(shape, counts, id + " 레시피 꼴이 다름");
            if (gold < 0) gold = r.gold();
            assertEquals(gold, r.gold(), id + " 골드가 다름");
        }
        assertTrue(gold >= 3 * maxOther && gold <= 150_000, "신화 골드 " + gold + " (가장 비싼 다른 레시피 " + maxOther + " · 노가다 상한 150,000)");
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
            // 고유 효과 강도 셈의 획득처 (보스 + 대장간 — source_factor 1.0). CR37 로 새 6 은 대장간만이 됐어도 강도·고유 효과는 그대로 둔다
            assertEquals(List.of("B", "F"), kinds, id + " 고유 효과 강도 셈 획득처 종류");
            assertEquals(1.0, e.get("source_factor").getAsDouble(), 1e-9, id);
            assertEquals(e.get("effect").getAsString(), content.item(id).unique().id(), id);
        }
    }
}
