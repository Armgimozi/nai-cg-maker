package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.stats.Stat;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 방어구·방패 요구 능력치 (look_spec §3 + review2 A2·A3): '모두 채움'만, 합 = T(L) = ceil(2.75(L−1)) (L ≤ 2 이면 없음),
 * 판금·가죽·천은 두 능력치 60 : 40 — 앞 = 겉모습 능력치(판금·방패 체력 · 가죽 민첩 · 천 지능 또는 정신). 한 세트 네 부위는 같은 요구.
 * 요구 짝에 맞춰 이름을 바꾼 스탯 줄(tools/data/035/armor_looks.json stats_rename)은 새 이름만 남는다.
 */
class ArmorRequirementsDataTest {

    static Content content;
    static JsonObject spec;
    /** 0.3.5 새 방어구 세트 6개 (gear_spec armor_sets — P3 가 items.yml 에 넣음). */
    static java.util.Set<String> NEW_SETS;

    @BeforeAll
    static void load() throws IOException {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        spec = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/armor_looks.json"), StandardCharsets.UTF_8))
                .getAsJsonObject();
        NEW_SETS = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/gear_spec.json"), StandardCharsets.UTF_8))
                .getAsJsonObject().getAsJsonObject("armor_sets").keySet();
        assertEquals(6, NEW_SETS.size());
        for (String set : NEW_SETS) assertNotNull(content.sets().get(set), "0.3.5 새 세트 " + set);
    }

    @Test
    void budgetFormula() {
        assertEquals(0, StatRequirement.budget(1));
        assertEquals(0, StatRequirement.budget(2));
        assertEquals(6, StatRequirement.budget(3));
        assertEquals(20, StatRequirement.budget(8));
        assertEquals(130, StatRequirement.budget(48));
        assertEquals(135, StatRequirement.budget(50));
    }

    @Test
    void everyArmourRequirementFollowsTheLookRule() {
        int with = 0;
        for (ItemDef d : content.items().values()) {
            if (d.type() != ItemType.ARMOR) continue;
            assertFalse(d.raw().has("requires_any"), d.id() + " 방어구에 requires_any ('… 중 하나')");
            Map<Stat, Integer> all = d.requirement().all();
            int t = StatRequirement.budget(d.levelReq());
            int sum = all.values().stream().mapToInt(Integer::intValue).sum();
            assertEquals(t, sum, d.id() + " 요구 합 (아이템 레벨 " + d.levelReq() + ")");
            if (t == 0) continue;
            with++;
            ArmorLook look = d.armorLook();
            if (look.real()) {
                assertEquals(2, all.size(), d.id() + " " + look + " 은 두 능력치: " + all);
                Map.Entry<Stat, Integer> lead = all.entrySet().stream().max(Map.Entry.comparingByValue()).orElseThrow();
                assertTrue(look.leadStats().contains(lead.getKey()), d.id() + " " + look + " 인데 앞 능력치 " + lead.getKey());
                assertTrue(lead.getValue() * 2 >= sum && lead.getValue() <= Math.ceil(0.6 * sum), d.id() + " 나눔 " + all);
            } else {
                assertTrue(all.size() >= 1 && all.size() <= 3, d.id() + " 능력치 수 " + all);
            }
        }
        assertTrue(with >= 90, "요구가 붙은 방어구 " + with);
    }

    @Test
    void setPiecesShareOneRequirement() {
        Map<String, StatRequirement> bySet = new HashMap<>();
        for (ItemDef d : content.items().values()) {
            if (d.type() != ItemType.ARMOR || d.setBonus() == null) continue;
            StatRequirement r = bySet.putIfAbsent(d.setBonus(), d.requirement());
            if (r != null) assertEquals(r, d.requirement(), d.id() + " 세트 " + d.setBonus() + " 부위마다 요구가 다름");
        }
    }

    @Test
    void renamedStatLinesMatchThePair() {
        JsonObject ren = spec.getAsJsonObject("stats_rename");
        int checked = 0;
        for (String set : ren.keySet()) {
            var s = content.sets().get(set);
            assertNotNull(s, set + " 세트가 items.yml 에 없음");
            JsonObject m = ren.getAsJsonObject(set);
            for (String id : s.pieces()) {
                ItemDef d = content.item(id);
                for (String old : m.keySet()) {
                    String now = m.get(old).getAsString();
                    assertFalse(d.stats().containsKey(old), id + " 스탯 줄 " + old + " 이 남음 (→ " + now + ")");
                    assertTrue(d.requirement().all().containsKey(Stat.byKey(now)), id + " 바꾼 줄 " + now + " 이 요구 짝에 없음");
                }
            }
            if (NEW_SETS.contains(set)) continue; // 0.3.5 새 세트 (P3) — 0.3.4 에 가진 사람이 없어 옮길 것 없음
            checked++;
            // 가진 아이템 옮기기(ItemMigration035)와 같은 표
            Map<String, String> mig = ItemMigration035.ARMOR_RENAME.get(set);
            assertNotNull(mig, set + " 이 ItemMigration035.ARMOR_RENAME 에 없음");
            for (String old : m.keySet()) assertEquals(m.get(old).getAsString(), mig.get(old), set + " " + old);
        }
        assertEquals(ItemMigration035.ARMOR_RENAME.size(), checked, "옮기기 표 = 지금 있는 세트의 이름 바꿈");
    }

    @Test
    void reviewFixesA2() {
        // 심연 보행자 민첩/힘 · 별 없는 성가대 지능/체력 (review2 A2)
        assertEquals(Map.of(Stat.DEX, 72, Stat.STR, 47), content.item("abyss_walker_chest").requirement().all());
        assertEquals(Map.of(Stat.INT, 72, Stat.VIT, 47), content.item("starless_choir_chest").requirement().all());
        assertTrue(content.item("abyss_walker_chest").stats().containsKey("STR"));
        assertTrue(content.item("starless_choir_chest").stats().containsKey("VIT"));
        assertEquals(Map.of(Stat.VIT, 7, Stat.WIS, 4), content.item("grove_mossguard_helm").requirement().all(), "이끼 투구 판금 체력/정신");
        assertEquals(Map.of(Stat.VIT, 4, Stat.DEX, 2), content.item("wayfarer_chest").requirement().all(), "길잡이");
    }
}
