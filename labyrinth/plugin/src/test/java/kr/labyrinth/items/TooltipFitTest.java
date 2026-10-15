package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.IntRange;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.Text;
import kr.labyrinth.items.enhance.EnhanceRules;
import kr.labyrinth.items.enhance.Enhancement;
import kr.labyrinth.ui.menus.CodexMenu;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 장비 설명이 화면 안에 들어가는지 (GUI 크기를 크게 쓴 1080p ≈ 23줄 — 이름 포함 21줄, 폭은 화면 절반 남짓). */
class TooltipFitTest {
    static Content content;
    static final int MAX_WIDTH_PX = 330;

    @BeforeAll
    static void load() { content = ContentLoader.load(Path.of("src/main/resources/content")).content(); }

    @Test
    void inventoryTooltipsFitOnScreen() {
        EnhanceRules rules = Enhancement.rules();
        int worst = 0;
        String worstId = "";
        for (ItemDef d : content.items().values()) {
            Map<String, Double> rolls = d.isGear() ? ItemRolls.roll(d, 7L) : null;
            for (int lv : new int[] {0, 8, 10}) {
                List<String> enh = d.isGear() ? Enhancement.tooltip(content, d, lv) : List.of();
                Map<String, Double> bonus = d.isGear() && lv > 0 && EnhanceRules.enhanceable(d) ? rules.bonus(d, rolls, lv) : Map.of();
                List<String> l = ItemTooltip.lines(content, d, rolls, bonus, enh);
                assertTrue(l.size() <= ItemTooltip.MAX_LINES, d.id() + " +" + lv + " = " + l.size() + "줄\n" + String.join("\n", l));
                // 보스 고유 장비는 강화해도 어느 보스 것인지가 남는다
                if (d.isGear() && d.sources().contains("boss")) {
                    assertTrue(l.stream().anyMatch(x -> x.startsWith(ItemTooltip.SOURCE_PREFIX + "보스 ")), d.id() + " +" + lv + " 획득처 없음\n" + String.join("\n", l));
                }
                for (String s : l) assertTrue(width(s) <= MAX_WIDTH_PX, d.id() + " 너무 넓은 줄 (" + width(s) + "px): " + s);
                if (l.size() > worst) { worst = l.size(); worstId = d.id(); }
            }
        }
        System.out.println("TOOLTIP 인벤토리 최대 " + worst + "줄 (" + worstId + ")");
    }

    @Test
    void codexTooltipsFitOnScreen() {
        Map<String, List<String>> src = CodexMenu.buildSources(content);
        int worst = 0;
        for (ItemDef d : content.items().values()) {
            List<String> s = src.getOrDefault(d.id(), List.of("알려진 획득처 없음"));
            // CodexMenu.itemIcon 과 같은 순서: 한 줄 요약 없이 그리고 아래에 "◆ 획득처" + 목록
            List<String> l = new ArrayList<>(ItemTooltip.lines(content, d, null, Map.of(), List.of(), 1 + Math.min(s.size(), CodexMenu.SOURCE_LINES), false));
            assertFalse(l.stream().anyMatch(x -> x.startsWith(ItemTooltip.SOURCE_PREFIX)), d.id());
            int room = ItemTooltip.MAX_LINES - l.size() - 1;
            assertTrue(room >= 1, d.id() + ": 획득처 자리가 없음\n" + String.join("\n", l));
            worst = Math.max(worst, l.size() + 1 + Math.min(room, s.size()));
            if (s.size() <= CodexMenu.SOURCE_LINES) assertTrue(room >= s.size(), d.id() + ": 획득처 " + s.size() + "줄 중 " + room + "줄만 들어감");
            for (String x : s) assertTrue(width(x) <= MAX_WIDTH_PX, d.id() + " 너무 넓은 획득처 줄 (" + width(x) + "px): " + x);
        }
        assertTrue(worst <= ItemTooltip.MAX_LINES);
        System.out.println("TOOLTIP 도감 최대 " + worst + "줄");
    }

    @Test
    void sourceLineNamesTheBossAndKeepsOneHomePerLabel() {
        int boss = 0, elite = 0, common = 0, starter = 0;
        for (ItemDef d : content.items().values()) {
            String line = ItemTooltip.sourceLine(content, d);
            if (d.sources().isEmpty()) {
                assertEquals(null, line, d.id());
                continue;
            }
            assertNotNull(line, d.id());
            assertTrue(width(line) <= MAX_WIDTH_PX, d.id() + " 너무 넓은 획득처 (" + width(line) + "px): " + line);
            // 예전 라벨(엘리트·업적 보상·제작)과 한 집이 라벨 둘로 갈라진 표기("몬스터 · 보물 상자")는 없다
            for (String old : List.of("엘리트", "업적 보상", "제작", "몬스터 · 보물 상자")) assertFalse(line.contains(old), d.id() + ": " + line);
            if (!d.isGear()) continue;
            if (d.sources().contains("boss")) {
                // 보스 고유 장비 = 그 층 보스 이름 ("획득처: 보스 테오라(9층) · 대장간")
                BossDef b = content.bossOfFloor(d.floor());
                assertTrue(line.startsWith(ItemTooltip.SOURCE_PREFIX + "보스 " + ItemTooltip.bossShortName(b) + "(" + d.floor() + "층)"), d.id() + ": " + line);
                boss++;
            }
            if (d.sources().contains("elite")) {
                MobDef m = content.mob(content.floor(d.floor()).elite());
                assertTrue(line.contains("정예 " + Text.strip(m.name()).trim() + "(" + d.floor() + "층)"), d.id() + ": " + line);
                elite++;
            }
            if (d.sources().contains("drop")) {
                assertTrue(line.startsWith(ItemTooltip.SOURCE_PREFIX + "지하 " + d.floor() + "층 몬스터·상자"), d.id() + ": " + line);
                common++;
            }
            if (d.sources().contains("craft")) assertTrue(line.endsWith(" · 대장간") || line.equals(ItemTooltip.SOURCE_PREFIX + "대장간"), d.id() + ": " + line);
            if (d.sources().contains("starter")) {
                assertEquals(ItemTooltip.SOURCE_PREFIX + "시작 지급", line, d.id());
                starter++;
            }
        }
        assertTrue(boss >= 40 && elite >= 40 && common >= 40, "보스 " + boss + " · 정예 " + elite + " · 공용 " + common);
        assertEquals(4, starter, "수련생 4종");
        assertEquals(ItemTooltip.SOURCE_PREFIX + "보스 테오라(9층) · 대장간", ItemTooltip.sourceLine(content, content.item("clockwork_bastion")));
        assertEquals(ItemTooltip.SOURCE_PREFIX + "보스 테오라(9층)", ItemTooltip.sourceLine(content, content.item("doomclock_executioner")));
    }

    @Test
    void codexGroupsCommonWeaponsIntoOneHome() {
        Map<String, List<String>> src = CodexMenu.buildSources(content);
        for (ItemDef d : content.items().values()) {
            if (!d.isGear()) continue;
            List<String> s = src.getOrDefault(d.id(), List.of());
            assertFalse(s.isEmpty(), d.id() + " 도감 획득처 없음");
            String all = String.join("\n", s);
            if (d.sources().contains("drop")) {
                // 몹 6종·보물방·기믹방 이름이 줄줄이 붙지 않고 "몬스터·상자 지하 N층" 한 줄
                assertTrue(s.get(0).contains("몬스터·상자") && s.get(0).endsWith("지하 " + d.floor() + "층"), d.id() + ": " + all);
                assertFalse(all.contains("보물 상자") || all.contains("기믹 방") || all.contains("(" + d.floor() + "층)"), d.id() + ": " + all);
            }
            if (d.sources().contains("starter")) assertTrue(s.size() == 1 && s.get(0).contains("시작 지급"), d.id() + ": " + all);
            if (d.sources().contains("boss")) assertTrue(all.contains(ItemTooltip.bossShortName(content.bossOfFloor(d.floor())) + "(" + d.floor() + "층)"), d.id() + ": " + all);
        }
    }

    @Test
    void codexShowsChestTableTreasuresActuallyRolls() {
        // 구간 표(maze_chest_wood_1)에 3층 보스 무기를 넣어 본다 — 층별 표가 있으면 구간 표는 굴리지 않으므로 도감에도 없다
        Map<String, LootTable> tables = new HashMap<>(content.lootTables());
        LootTable b1 = tables.get("maze_chest_wood_1");
        List<LootTable.Entry> entries = new ArrayList<>(b1.entries());
        entries.add(new LootTable.Entry(LootTable.Kind.ITEM, "mycelking_guard_blade", null, 0, List.of(), null, 0.01, IntRange.ONE, null));
        tables.put("maze_chest_wood_1", new LootTable(b1.id(), b1.rolls(), entries, b1.guaranteed(), b1.gold()));
        String blade = String.join("\n", CodexMenu.buildSources(with(tables)).get("mycelking_guard_blade"));
        assertFalse(blade.contains("보물 상자"), blade);
        // 3층 층별 나무 상자 표가 없으면 Treasures 는 구간 표를 굴린다 — 도감도 그 표를 "보물 상자 지하 3층"으로
        tables.remove("maze_chest_wood_f3");
        blade = String.join("\n", CodexMenu.buildSources(with(tables)).get("mycelking_guard_blade"));
        assertTrue(blade.contains("보물 상자") && blade.contains("지하 3층") && !blade.contains("지하 1") && !blade.contains("2층"), blade);
    }

    private static Content with(Map<String, LootTable> tables) {
        Content c = content;
        return new Content(c.classes(), c.items(), c.sets(), c.mobs(), c.bosses(), c.floors(), Map.copyOf(tables), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces());
    }

    @Test
    void trimsLeastImportantFirst() {
        ItemDef big = null;
        for (ItemDef d : content.items().values()) if (big == null || d.weaponSkills().size() > big.weaponSkills().size()) big = d;
        List<String> full = ItemTooltip.lines(content, big, null);
        // 무기 스킬 이름은 언제나 남는다
        for (ItemDef.WeaponSkillDef s : big.weaponSkills()) assertTrue(String.join("\n", full).contains(s.name()), big.id() + ": " + s.name());
        // 자리가 넉넉하면 설명(이야기)도 보인다
        ItemDef simple = content.items().values().stream().filter(d -> d.isGear() && d.weaponSkills().isEmpty() && d.lore() != null && !d.lore().isBlank())
                .findFirst().orElseThrow();
        assertTrue(ItemTooltip.lines(content, simple, null).stream().anyMatch(x -> x.contains("<i>")), simple.id());
    }

    /** 대략적인 픽셀 폭: 한글 9 · 영문·숫자 6 · 공백 4 · 기호 8, 키 이름 태그는 60. */
    static int width(String mm) {
        String s = mm.replaceAll("<key:[^>]+>", "\u0001").replaceAll("<[^>]+>", "");
        int w = 0;
        for (char ch : s.toCharArray()) {
            if (ch == '\u0001') w += 60;
            else if (ch == ' ') w += 4;
            else if (ch >= 0xAC00 && ch <= 0xD7A3) w += 9;
            else if (ch < 128) w += 6;
            else w += 8;
        }
        return w;
    }
}
