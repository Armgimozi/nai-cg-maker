package kr.labyrinth.ui;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.Text;
import kr.labyrinth.ui.menus.CodexMenu;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 도감 획득처 글 (gear_spec §4.5 · review2 P6): 장비 줄에는 층 숫자가 없고 종류만 ("몬스터·상자" · "시련방" · "보스 테오라").
 * 재료·소모품은 층을 그대로 적는다 (몬스터·보스 도감의 층 정보도 그대로).
 */
class CodexSourceTextTest {
    static Content content;
    static Map<String, List<String>> sources;
    static final Pattern FLOOR = Pattern.compile("\\d+\\s*층|지하\\s*\\d|\\(\\d+층\\)");

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        sources = CodexMenu.buildSources(content);
    }

    private static List<String> plain(String id) {
        return sources.getOrDefault(id, List.of()).stream().map(Text::strip).toList();
    }

    @Test
    void gearSourcesHaveNoFloorNumbers() {
        int gear = 0;
        for (ItemDef d : content.items().values()) {
            if (!d.isGear()) continue;
            List<String> s = plain(d.id());
            assertFalse(s.isEmpty(), d.id() + " 도감 획득처 없음");
            for (String line : s) assertFalse(FLOOR.matcher(line).find(), d.id() + ": " + line);
            gear++;
        }
        assertTrue(gear >= 380, "장비 " + gear);
    }

    @Test
    void sharedDropGearIsOneLine() {
        int n = 0;
        for (ItemDef d : content.items().values()) {
            if (!d.isGear() || !d.sources().contains("drop") || !d.sources().contains("chest")) continue;
            List<String> s = plain(d.id());
            // 몹 6종·보물방·시련방 이름이 줄줄이 붙지 않고 "몬스터·상자" 한 줄 (지하 N층 무기 묶음 줄 없음)
            assertTrue(s.contains("몬스터·상자"), d.id() + ": " + s);
            assertFalse(s.stream().anyMatch(x -> x.contains("공용") || x.startsWith("몬스터 ")), d.id() + ": " + s);
            n++;
        }
        assertTrue(n >= 40, "몬스터·상자 장비 " + n);
    }

    @Test
    void eachSourceKindHasItsGroup() {
        for (String g : List.of("시련방", "특별 시련", "금고·미믹", "몬스터·상자", "보스", "정예", "대장간", "상인")) {
            assertTrue(CodexMenu.SOURCE_GROUPS.contains(g), g);
        }
        for (String old : List.of("기믹 방", "제작", "상점")) assertFalse(CodexMenu.SOURCE_GROUPS.contains(old), old);
        int trial = 0, special = 0, hoard = 0, boss = 0;
        for (ItemDef d : content.items().values()) {
            if (!d.isGear()) continue;
            List<String> s = plain(d.id());
            String all = String.join("\n", s);
            if (d.sources().contains("trial")) { assertTrue(s.contains("시련방"), d.id() + ": " + all); trial++; }
            if (d.sources().contains("special")) { assertTrue(s.contains("특별 시련"), d.id() + ": " + all); special++; }
            if (d.sources().contains("hoard")) { assertTrue(s.contains("금고·미믹"), d.id() + ": " + all); hoard++; }
            if (d.sources().contains("boss")) {
                // 보스 이름은 남고 층은 없다
                String name = kr.labyrinth.items.ItemTooltip.bossShortName(content.bossOfFloor(d.tier()));
                assertTrue(s.stream().anyMatch(x -> x.startsWith("보스 ") && x.contains(name)), d.id() + ": " + all);
                boss++;
            }
            if (d.sources().contains("starter")) assertEquals(List.of("시작 지급 처음 직업을 고를 때"), s, d.id());
        }
        assertTrue(trial >= 10 && special >= 10 && hoard >= 10 && boss >= 40, trial + " · " + special + " · " + hoard + " · " + boss);
    }

    @Test
    void materialsKeepFloors() {
        // 재료는 그 층 재료라 층을 적는다 — 장비만 층이 없다
        long withFloor = content.items().values().stream().filter(d -> !d.isGear())
                .filter(d -> plain(d.id()).stream().anyMatch(x -> FLOOR.matcher(x).find())).count();
        assertTrue(withFloor >= 10, "층을 적은 재료·소모품 " + withFloor);
    }

    /**
     * 0.3.7 신화 도안 (리뷰 LOW 4): 신화 레시피 12개마다 도감에 "신화 도안 보스 … · 특별 시련 · 금고·미믹" 한 줄 —
     * 일반 도안 뽑기·상인에 없으니 얻는 곳을 알려 준다. 장비 글처럼 층 숫자 없이, 넬카르(10층)는 12개 모두에.
     */
    @Test
    void mythicBlueprintLineNamesItsSources() {
        Map<String, String> lines = CodexMenu.mythicBlueprintLines(content);
        String nelkar = kr.labyrinth.items.ItemTooltip.bossShortName(content.bossOfFloor(10));
        int n = 0;
        for (var r : content.recipes().values()) {
            if (!kr.labyrinth.items.blueprint.BlueprintRules.isMythic(content, r)) continue;
            String line = Text.strip(lines.getOrDefault(r.id(), ""));
            assertTrue(line.startsWith("신화 도안 보스 "), r.id() + ": " + line);
            assertTrue(line.contains(nelkar) && line.contains("특별 시련") && line.contains("금고·미믹"), r.id() + ": " + line);
            assertFalse(FLOOR.matcher(line).find(), r.id() + ": " + line);
            n++;
        }
        assertEquals(12, n, "신화 레시피");
        assertEquals(12, lines.size(), "신화가 아닌 레시피에는 줄이 없다");
        // CR37: 12 모두 8·9·10층 보스 · 특별 시련 · 금고·미믹 (넬카르를 못 잡아도 도안이 나온다)
        String orbel = kr.labyrinth.items.ItemTooltip.bossShortName(content.bossOfFloor(8));
        String theora = kr.labyrinth.items.ItemTooltip.bossShortName(content.bossOfFloor(9));
        for (String id : List.of("voidheart_staff", "daybreak_bell")) {
            assertEquals("신화 도안 보스 " + orbel + "·" + theora + "·" + nelkar + " · 특별 시련 · 금고·미믹", Text.strip(lines.get(id)), id);
        }
    }

    /** 신화 도안 줄을 더해도 도감 툴팁은 20줄 안이고, 도안 줄 · 보스 줄 · 대장간 골드까지 다 보인다 (못 배운 사람 기준). */
    @Test
    void mythicCodexTooltipKeepsAllSourceLines() {
        Map<String, String> lines = CodexMenu.mythicBlueprintLines(content);
        for (var r : content.recipes().values()) {
            if (!kr.labyrinth.items.blueprint.BlueprintRules.isMythic(content, r)) continue;
            ItemDef d = content.item(r.result());
            List<String> src = new java.util.ArrayList<>();
            src.add("<#ff8a8a>✘ 도안을 아직 못 배웠다");
            src.add(lines.get(r.id()));
            src.addAll(sources.get(d.id()));
            List<String> lore = CodexMenu.lore(content, d, null, src).stream().map(Text::strip).toList();
            String all = String.join("\n", lore);
            System.out.println("[도감 신화] " + d.id() + " " + lore.size() + "줄 · 획득처 " + src.size());
            assertTrue(lore.size() <= kr.labyrinth.items.ItemTooltip.MAX_LINES, d.id() + " " + lore.size());
            assertTrue(all.contains("신화 도안 보스") && all.contains("110,000G") && !all.contains("외 더 있음"), d.id() + "\n" + all);
        }
    }
}
