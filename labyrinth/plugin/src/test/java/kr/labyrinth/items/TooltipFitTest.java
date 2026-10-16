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
import java.util.regex.Pattern;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.IntRange;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.ArmorLooks;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.Text;
import kr.labyrinth.items.enhance.EnhanceRules;
import kr.labyrinth.items.enhance.Enhancement;
import kr.labyrinth.items.unique.UniqueText;
import kr.labyrinth.ui.menus.CodexMenu;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 장비 설명이 화면 안에 들어가는지 (GUI 크기를 크게 쓴 1080p ≈ 23줄 — 이름 포함 21줄, 폭은 화면 절반 남짓) +
 * 0.3.5 줄 계획 (review2 §4): 층·분류 글자 없음 · 요구 "또는" 없음 · 공격력(한 방) + 공격 속도 줄 · 고유 효과 2줄 · 겉모습 줄 ·
 * 보스 장비는 접어도 보스 이름이 남는다.
 */
class TooltipFitTest {
    static Content content;
    static final int MAX_WIDTH_PX = 330;
    /** 층 숫자 ("3층", "지하 4"). */
    static final Pattern FLOOR = Pattern.compile("\\d+\\s*층|지하\\s*\\d");

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        ItemTooltip.looks(ArmorLooks.DEFAULT);
    }

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
                String all = String.join("\n", l);
                assertTrue(l.size() <= ItemTooltip.MAX_LINES, d.id() + " +" + lv + " = " + l.size() + "줄\n" + all);
                // 보스 고유 장비는 강화해도 어느 보스 것인지가 남는다
                if (d.isGear() && d.sources().contains("boss")) {
                    assertTrue(l.stream().anyMatch(x -> x.startsWith(ItemTooltip.SOURCE_PREFIX + "보스 ")), d.id() + " +" + lv + " 획득처 없음\n" + all);
                }
                for (String s : l) assertTrue(width(s) <= MAX_WIDTH_PX, d.id() + " 너무 넓은 줄 (" + width(s) + "px): " + s);
                if (d.isGear()) {
                    // 장비에는 층 숫자·"또는"·굴림 품질이 없다
                    assertFalse(FLOOR.matcher(Text.strip(all)).find(), d.id() + ": 층 글자\n" + all);
                    assertFalse(all.contains("또는"), d.id() + ": " + all);
                    assertFalse(all.contains("굴림 품질"), d.id());
                }
                if (l.size() > worst) { worst = l.size(); worstId = d.id() + " +" + lv; }
            }
        }
        System.out.println("TOOLTIP 인벤토리 최대 " + worst + "줄 (" + worstId + ")");
    }

    @Test
    void weaponShowsPerHitAttackAndSpeed() {
        int n = 0;
        for (ItemDef d : content.items().values()) {
            if (!d.isWeapon()) continue;
            WeaponAttack a = WeaponAttack.of(d);
            List<String> l = ItemTooltip.lines(content, d, ItemRolls.roll(d, 3L));
            String atk = l.stream().filter(x -> x.contains("⚔ 공격력 ")).findFirst().orElse(null);
            assertNotNull(atk, d.id() + "\n" + String.join("\n", l));
            assertTrue(Text.strip(atk).endsWith("· " + a.kind().displayName()), d.id() + ": " + atk);
            assertFalse(Text.strip(atk).contains("공격력 +"), "공격력은 부호 없이: " + atk);
            String speed = "공격 속도 초당 " + ItemTooltip.perSecond(1.0 / a.interval()) + "회";
            int at = l.indexOf(atk);
            assertEquals(speed, Text.strip(l.get(at + 1)), d.id() + " — 공격력 바로 아래 공격 속도");
            // 미리보기(굴림 없음)도 같은 두 줄
            String prev = Text.strip(String.join("\n", ItemTooltip.lines(content, d, null)));
            assertTrue(prev.contains("⚔ 공격력 ") && prev.contains(speed), d.id() + "\n" + prev);
            n++;
        }
        assertTrue(n >= 245, "무기 " + n);
        ItemDef sword = content.items().values().stream()
                .filter(d -> d.isWeapon() && Math.abs(WeaponAttack.of(d).interval() - 0.67) < 1e-9).findFirst().orElseThrow();
        assertEquals("공격 속도 초당 1.5회", Text.strip(ItemTooltip.speedLine(sword)));
    }

    @Test
    void everyWeaponShowsItsUniqueInTwoLines() {
        int n = 0;
        for (ItemDef d : content.items().values()) {
            if (!d.isWeapon() || d.unique() == null) continue;
            String desc = UniqueText.desc(d.unique());
            assertTrue(desc.length() <= UniqueText.MAX_DESC, d.id() + " 설명 " + desc.length() + "자: " + desc);
            assertTrue(width(UniqueText.descLine(d.unique())) <= MAX_WIDTH_PX, d.id() + ": " + desc);
            assertTrue(width(UniqueText.head(d.unique())) <= MAX_WIDTH_PX, d.id());
            assertTrue(width(UniqueText.folded(d.unique())) <= MAX_WIDTH_PX, d.id());
            assertFalse(desc.contains("null") || desc.equals(d.unique().id()), d.id() + ": " + desc);
            // 자리가 넉넉하면 머리 + 설명 두 줄, 무기 스킬보다 앞
            List<String> l = ItemTooltip.lines(content, d, null);
            int head = l.indexOf(UniqueText.head(d.unique()));
            if (head >= 0) {
                assertEquals(UniqueText.descLine(d.unique()), l.get(head + 1), d.id());
                for (int i = 0; i < head; i++) assertFalse(l.get(i).contains("◆ "), d.id() + ": 고유 효과가 무기 스킬 뒤");
            } else {
                // 접혀도 이름은 남는다
                assertTrue(l.contains(UniqueText.folded(d.unique())), d.id() + "\n" + String.join("\n", l));
            }
            n++;
        }
        assertTrue(n >= 245, "고유 효과 " + n);
        // 설계 도구(ud_assign.desc / short)와 같은 문장
        ItemDef bow = content.item("corridor_longbow");
        assertEquals("치명타 시 출혈 (중첩당 초당 공격력 2.5%, 최대 5)", UniqueText.desc(bow.unique()));
        assertEquals("치명타 → 출혈 2.5%", UniqueText.shortText(bow.unique()));
    }

    @Test
    void armourShowsLookLinesAndNoFloor() {
        ArmorLooks cfg = ArmorLooks.DEFAULT;
        int real = 0;
        for (ItemDef d : content.items().values()) {
            if (d.type() != ItemType.ARMOR) continue;
            List<String> l = ItemTooltip.lines(content, d, null);
            String first = Text.strip(l.get(0));
            ArmorLook look = d.armorLook();
            String all = Text.strip(String.join("\n", l));
            if (look.real()) {
                assertTrue(first.startsWith(d.rarity().displayName() + " " + cfg.name(look) + " "), d.id() + ": " + first);
                assertTrue(all.contains(cfg.name(look) + " ▲") || all.contains(cfg.name(look) + " ▼"), d.id() + "\n" + all);
                if (d.isShield()) assertTrue(all.contains("4부위 수에는 안 든다"), d.id());
                else assertTrue(all.contains(cfg.name(look) + " 4부위 · " + cfg.fullName(look) + ":"), d.id() + "\n" + all);
                real++;
            } else {
                assertFalse(all.contains("▲") || all.contains("4부위 ·"), d.id() + "\n" + all);
                if (look == ArmorLook.ANY) assertTrue(all.contains("어느 겉모습과도 4부위를 이룬다"), d.id());
            }
        }
        assertTrue(real >= 100, "겉모습 있는 방어구 " + real);
        // 설정을 끄면 겉모습 글자·줄이 없다
        ItemTooltip.looks(ArmorLooks.OFF);
        try {
            ItemDef chest = content.items().values().stream().filter(d -> d.type() == ItemType.ARMOR && d.armorLook() == ArmorLook.HEAVY
                    && !d.isShield()).findFirst().orElseThrow();
            String all = Text.strip(String.join("\n", ItemTooltip.lines(content, chest, null)));
            assertFalse(all.contains("판금"), all);
        } finally {
            ItemTooltip.looks(ArmorLooks.DEFAULT);
        }
    }

    @Test
    void codexTooltipsFitOnScreen() {
        Map<String, List<String>> src = CodexMenu.buildSources(content);
        int worst = 0, worstDetail = 0;
        for (ItemDef d : content.items().values()) {
            List<String> s = src.getOrDefault(d.id(), List.of("알려진 획득처 없음"));
            // CodexMenu.itemIcon 과 같은 꼴: 한 줄 요약 없이 그리고 아래에 "◆ 획득처" + 목록
            List<String> l = CodexMenu.lore(content, d, null, s);
            assertFalse(l.stream().anyMatch(x -> x.startsWith(ItemTooltip.SOURCE_PREFIX)), d.id());
            assertTrue(l.size() <= ItemTooltip.MAX_LINES, d.id() + " 도감 " + l.size() + "줄\n" + String.join("\n", l));
            int at = l.indexOf("<#ffd36b>◆ 획득처");
            assertTrue(at >= 0 && at + 1 < l.size(), d.id() + ": 획득처 자리가 없음\n" + String.join("\n", l));
            if (s.size() <= CodexMenu.SOURCE_LINES) assertEquals(s, l.subList(at + 1, l.size()), d.id() + ": 획득처가 다 안 들어감");
            for (String x : l) assertTrue(width(x) <= MAX_WIDTH_PX, d.id() + " 너무 넓은 줄 (" + width(x) + "px): " + x);
            worst = Math.max(worst, l.size());
            if (d.isGear()) {
                List<String> det = CodexMenu.detailLore(content, d, ArmorLooks.DEFAULT, null, s);
                assertTrue(det.size() <= ItemTooltip.MAX_LINES, d.id() + " 자세히 " + det.size() + "줄\n" + String.join("\n", det));
                for (String x : det) assertTrue(width(x) <= MAX_WIDTH_PX, d.id() + " 자세히 너무 넓은 줄 (" + width(x) + "px): " + x);
                worstDetail = Math.max(worstDetail, det.size());
            }
        }
        System.out.println("TOOLTIP 도감 최대 " + worst + "줄 · 자세히 최대 " + worstDetail + "줄");
    }

    @Test
    void codexDetailShowsSkillPowerAndLookText() {
        ItemDef w = content.items().values().stream().filter(ItemDef::isWeapon).findFirst().orElseThrow();
        String all = Text.strip(String.join("\n", CodexMenu.detailLines(content, w, ArmorLooks.DEFAULT)));
        assertTrue(all.contains("스킬 위력 ") && all.contains("공격 간격 ") && all.contains("공격 방식 "), all);
        ItemDef heavy = content.items().values().stream().filter(d -> d.type() == ItemType.ARMOR && d.armorLook() == ArmorLook.HEAVY
                && !d.isShield() && d.requirement().all().size() == 2).findFirst().orElseThrow();
        String h = Text.strip(String.join("\n", CodexMenu.detailLines(content, heavy, ArmorLooks.DEFAULT)));
        assertTrue(h.contains("판금 · ") && h.contains("과 "), "요구 짝 이름: " + h);
        assertTrue(h.contains("4부위 · 버팀") && h.contains("보스가 미는 것"), h);
    }

    @Test
    void forgeListTooltipsFit() {
        // 대장간 목록 = 툴팁(획득처 한 줄 포함) + 재료 꼬리 (빈 줄 · 제목 · 재료마다 한 줄 · 골드 · 제작 안내)
        int worst = 0;
        String worstId = "";
        for (RecipeDef r : content.recipes().values()) {
            ItemDef d = content.item(r.result());
            if (d == null || !d.isGear()) continue;
            int tail = kr.labyrinth.items.crafting.BlacksmithMenu.tailSize(content, r);   // 0.3.6: 주괴 한 줄 · 재료가 많으면 제목 뺌
            List<String> l = ItemTooltip.lines(content, d, null, Map.of(), List.of(), tail, true, null);
            if (l.size() + tail > worst) { worst = l.size() + tail; worstId = r.id(); }
            assertTrue(l.size() + tail <= ItemTooltip.MAX_LINES, r.id() + " 대장간 " + (l.size() + tail) + "줄\n" + String.join("\n", l));
            for (String x : l) assertTrue(width(x) <= MAX_WIDTH_PX, r.id() + ": " + x);
        }
        System.out.println("TOOLTIP 대장간 최대 " + worst + "줄 (" + worstId + ")");
    }

    @Test
    void sourceLineNamesTheBossAndHasNoFloor() {
        int boss = 0, elite = 0, common = 0, starter = 0, trial = 0, special = 0, hoard = 0;
        for (ItemDef d : content.items().values()) {
            String line = ItemTooltip.sourceLine(content, d);
            if (d.sources().isEmpty()) {
                assertEquals(null, line, d.id());
                continue;
            }
            assertNotNull(line, d.id());
            assertTrue(width(line) <= MAX_WIDTH_PX, d.id() + " 너무 넓은 획득처 (" + width(line) + "px): " + line);
            // 예전 라벨(엘리트·업적 보상·제작·기믹 방)·한 집이 라벨 둘로 갈라진 표기·층 숫자는 없다
            for (String old : List.of("엘리트", "업적 보상", "제작", "기믹 방", "몬스터 · 보물 상자")) assertFalse(line.contains(old), d.id() + ": " + line);
            assertFalse(FLOOR.matcher(Text.strip(line)).find(), d.id() + ": " + line);
            if (!d.isGear()) continue;
            if (d.sources().contains("boss")) {
                // 보스 고유 장비 = 그 단계 보스 이름 ("획득처: 보스 테오라 · 대장간")
                assertTrue(line.startsWith(ItemTooltip.SOURCE_PREFIX + "보스 " + ItemTooltip.bossShortName(content.bossOfFloor(d.tier()))),
                        d.id() + ": " + line);
                boss++;
            }
            if (d.sources().contains("elite")) {
                assertTrue(line.contains("정예"), d.id() + ": " + line);
                elite++;
            }
            if (d.sources().contains("drop") && d.sources().contains("chest")) {
                assertTrue(line.contains("몬스터·상자"), d.id() + ": " + line);
                common++;
            }
            if (d.sources().contains("trial")) { assertTrue(line.contains("시련방"), d.id() + ": " + line); trial++; }
            if (d.sources().contains("special")) { assertTrue(line.contains("특별 시련"), d.id() + ": " + line); special++; }
            if (d.sources().contains("hoard")) { assertTrue(line.contains("금고·미믹"), d.id() + ": " + line); hoard++; }
            if (d.sources().contains("craft")) assertTrue(line.endsWith(" · 대장간") || line.equals(ItemTooltip.SOURCE_PREFIX + "대장간"), d.id() + ": " + line);
            if (d.sources().contains("starter")) {
                assertEquals(ItemTooltip.SOURCE_PREFIX + "시작 지급", line, d.id());
                starter++;
            }
        }
        assertTrue(boss >= 40 && elite >= 40 && common >= 40, "보스 " + boss + " · 정예 " + elite + " · 공용 " + common);
        assertTrue(trial >= 10 && special >= 10 && hoard >= 10, "시련방 " + trial + " · 특별 시련 " + special + " · 금고 " + hoard);
        assertEquals(4, starter, "수련생 4종");
        assertEquals(ItemTooltip.SOURCE_PREFIX + "보스 테오라 · 대장간", ItemTooltip.sourceLine(content, content.item("clockwork_bastion")));
        assertEquals(ItemTooltip.SOURCE_PREFIX + "보스 테오라", ItemTooltip.sourceLine(content, content.item("doomclock_executioner")));
        // 상인이 하나면 이름 ("상인 핀")
        ItemDef sold = content.items().values().stream().filter(d -> d.isGear() && d.sources().equals(List.of("shop"))).findFirst().orElse(null);
        if (sold != null) assertEquals(ItemTooltip.SOURCE_PREFIX + "상인 핀", ItemTooltip.sourceLine(content, sold), sold.id());
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
        // 3층 층별 나무 상자 표가 없으면 Treasures 는 구간 표를 굴린다 — 도감도 그 표를 "보물 상자"로 (장비라 층 숫자 없이)
        tables.remove("maze_chest_wood_f3");
        blade = String.join("\n", CodexMenu.buildSources(with(tables)).get("mycelking_guard_blade"));
        assertTrue(blade.contains("보물 상자") && !FLOOR.matcher(Text.strip(blade)).find(), blade);
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
        // 무기 스킬 이름·고유 효과 이름은 언제나 남는다
        for (ItemDef.WeaponSkillDef s : big.weaponSkills()) assertTrue(String.join("\n", full).contains(s.name()), big.id() + ": " + s.name());
        if (big.unique() != null) assertTrue(String.join("\n", full).contains(big.unique().name()), big.id());
        // 줄이 아주 모자라도(꼬리 10줄) 스킬 이름과 접은 고유 효과가 남는다
        List<String> tight = ItemTooltip.lines(content, big, null, Map.of(), List.of(), 10, true, null);
        for (ItemDef.WeaponSkillDef s : big.weaponSkills()) assertTrue(String.join("\n", tight).contains(s.name()), big.id() + ": " + s.name());
        if (big.unique() != null) assertTrue(tight.contains(UniqueText.folded(big.unique())), String.join("\n", tight));
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
