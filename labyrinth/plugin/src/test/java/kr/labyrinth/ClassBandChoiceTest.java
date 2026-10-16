package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 직업 × 띠 칸마다 무기 고르기가 살아 있는가 (주인 결정 B4 — {@link GearModel#cells}). 칸 = 직업 6 × 5레벨 띠 10.
 * 알맞음 = 그 띠 무기 + 방어구 세트 (+ 수호기사 방패) 를 세금 ≤ 15% 로 끼고 피해 종류가 직업과 맞음 (사냥꾼은 원거리만).
 * 칸 통과 = 상황(무리 · 정예 · 보스 혼자 · 보스 파티) 어느 하나에서 가장 좋은 것의 90% 안인 무기 3개 이상 ·
 * 모든 상황에서 나머지를 이기는 무기 없음 · 보스·대장간이 아닌 곳에서 나오는 95% 안 무기 1개 이상.
 * 60칸 중 55칸 이상 · 남는 지배 무기는 보스 전설만. 설계 결과(content_p3.json cells)와 같은 칸이 남아야 한다.
 */
class ClassBandChoiceTest {

    static Content content;
    static JsonObject design;

    @BeforeAll
    static void load() throws IOException {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        design = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/content_p3.json"), StandardCharsets.UTF_8))
                .getAsJsonObject().getAsJsonObject("cells");
    }

    @Test
    void classBandCellsKeepRealChoices() {
        Map<String, GearModel.Cell> cells = GearModel.cells(content);
        assertEquals(60, cells.size());
        TreeSet<String> fail = new TreeSet<>();
        List<String> badDominators = new ArrayList<>();
        for (GearModel.Cell c : cells.values()) {
            if (!c.ok()) fail.add(c.key());
            if (c.dom() != null) {
                ItemDef d = content.item(c.dom());
                if (d.rarity() != Rarity.LEGENDARY || !d.sources().contains("boss")) badDominators.add(c.key() + " " + c.dom());
            }
            assertTrue(!c.ids().isEmpty(), c.key() + " 알맞은 무기 없음");
        }
        int pass = 60 - fail.size();
        assertTrue(pass >= 55, "통과 칸 " + pass + " — 못 넘은 칸 " + fail);
        assertEquals(List.of(), badDominators, "보스 전설이 아닌 지배 무기");
        assertEquals(design.get("pass").getAsInt(), pass, "설계 결과와 통과 칸 수가 다름 " + fail);
        assertEquals(new TreeSet<>(design.getAsJsonObject("fail").keySet()), fail, "설계 결과와 못 넘은 칸이 다름");
    }

    @Test
    void modelBasics() {
        // 세금: 직업 기본 분배 안이면 0, 밖으로 더 찍는 만큼
        var base = GearModel.base(content.classes().get("berserker"));
        assertEquals(0.0, GearModel.tax(base, GearModel.SPREAD.get("berserker"), 10, Map.of()).extra(), 1e-9);
        GearModel.Tax t = GearModel.tax(base, GearModel.SPREAD.get("berserker"), 10, Map.of(kr.labyrinth.stats.Stat.INT, 30));
        assertTrue(t.extra() > 20 && t.feasible(), t.toString());
        // 무기 힘 Q = 비교값 ÷ TP(L) × (1 + 부가 가치 …) — 일반 무기는 1 안팎
        ItemDef common = content.item("corridor_longsword");
        assertNotNull(common);
        assertTrue(GearModel.q(common) > 0.8 && GearModel.q(common) < 1.6, "Q " + GearModel.q(common));
        for (String sit : GearModel.SITS) assertTrue(GearModel.gain(common, sit) >= 0, sit);
    }
}
