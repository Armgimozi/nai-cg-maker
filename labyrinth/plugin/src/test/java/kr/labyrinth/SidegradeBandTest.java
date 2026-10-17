package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import kr.labyrinth.combat.CombatMath;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 옆길 무기 (gear_spec §12 Sidegrade): 비교값 = (한 방 가운데값 ÷ attack.interval) ÷ K(방식, 간격) (CombatMath — combat_spec).
 * 띠 대장간 기준 = 그 띠 가장 높은 레벨 대장간 무기들의 비교값 가운데값. 시련방·특별 시련·금고·미믹·정예 무기와 0.3.5 에 새로 넣은
 * 몬스터·상자 무기는 기준 ±5% · 상인 무기는 기준 이하(한 방 0.5 반올림 몫까지) · 보스 전설은 기준 +5~+30%.
 */
class SidegradeBandTest {

    static Content content;
    static Set<String> fresh = new HashSet<>();

    @BeforeAll
    static void load() throws IOException {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        JsonObject gs = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/gear_spec.json"), StandardCharsets.UTF_8)).getAsJsonObject();
        JsonObject p3 = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/content_p3.json"), StandardCharsets.UTF_8)).getAsJsonObject();
        fresh.addAll(gs.getAsJsonObject("weapons").keySet());
        fresh.addAll(p3.getAsJsonObject("weapons").keySet());
        fresh.removeAll(p3.getAsJsonObject("remove_weapons").keySet());
    }

    static double cv(ItemDef w, double midShift) {
        WeaponAttack a = w.attack();
        Range r = w.stats().get("damage");
        return ((r.min() + r.max()) / 2 + midShift) / a.interval() / CombatMath.k(a.style(), a.interval());
    }

    static double median(List<Double> xs) {
        List<Double> s = new ArrayList<>(xs);
        s.sort(Double::compare);
        int n = s.size();
        return n % 2 == 1 ? s.get(n / 2) : (s.get(n / 2 - 1) + s.get(n / 2)) / 2;
    }

    @Test
    void sidegradesSitOnTheForgeLine() {
        assertEquals(114, fresh.stream().filter(id -> content.item(id) != null).count(), "0.3.5 새 무기 (gear_spec 106 + B2 8)");
        List<String> off = new ArrayList<>();
        int side = 0, shop = 0, legend = 0;
        for (int band = 1; band <= 10; band++) {
            int top = 0;
            for (ItemDef w : content.items().values()) {
                if (DropRateWindowTest.forge(w) && GearModel.band(w.levelReq()) == band) top = Math.max(top, w.levelReq());
            }
            List<Double> forge = new ArrayList<>();   // 0.3.7 신화(보스 + 대장간)는 대장간 기준이 아니다
            for (ItemDef w : content.items().values()) {
                if (DropRateWindowTest.forge(w) && w.levelReq() == top) forge.add(cv(w, 0));
            }
            assertTrue(!forge.isEmpty(), "띠 " + band + " 대장간 무기 없음");
            double base = median(forge);
            for (ItemDef w : content.items().values()) {
                if (!w.isWeapon() || GearModel.band(w.levelReq()) != band) continue;
                Set<String> s = new HashSet<>(w.sources());
                double r = cv(w, 0) / base;
                boolean sideKind = s.contains("trial") || s.contains("special") || s.contains("hoard") || s.contains("elite");
                boolean newCommon = fresh.contains(w.id()) && (s.contains("drop") || s.contains("chest"));
                if (sideKind || newCommon) {
                    side++;
                    if (Math.abs(r - 1) > 0.05 + 1e-9) off.add("옆길 " + w.id() + " " + String.format("%+.1f%%", (r - 1) * 100));
                }
                if (s.contains("shop")) {
                    shop++;
                    if (cv(w, -0.5) > base + 1e-9) off.add("상인 " + w.id() + " " + String.format("%+.1f%%", (r - 1) * 100));
                }
                if (s.contains("boss") && w.rarity() == Rarity.LEGENDARY) {
                    legend++;
                    if (r < 1.05 - 1e-9 || r > 1.30 + 1e-9) off.add("보스 전설 " + w.id() + " " + String.format("%+.1f%%", (r - 1) * 100));
                }
            }
        }
        assertEquals(List.of(), off);
        assertTrue(side >= 100, "옆길 무기 " + side);
        assertEquals(3, shop, "상인 무기");
        assertTrue(legend >= 15, "보스 전설 " + legend);
    }
}
