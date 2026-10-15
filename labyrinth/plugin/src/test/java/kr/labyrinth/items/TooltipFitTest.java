package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
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
            List<String> l = new ArrayList<>(ItemTooltip.lines(content, d, null, Map.of(), List.of(), 1 + Math.min(s.size(), CodexMenu.SOURCE_LINES)));
            l.removeIf(x -> x.startsWith(ItemTooltip.SOURCE_PREFIX));
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
