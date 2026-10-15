package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ContentParser;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemSetDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.content.WeaponTypes;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.items.enhance.EnhanceRules;
import kr.labyrinth.items.enhance.Enhancement;
import kr.labyrinth.stats.Stat;
import org.bukkit.inventory.EquipmentSlot;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 장비 요구 능력치 (레벨 제한 대신): 판정·문구·툴팁·파서·검사기. 번들 데이터에 requires 가 없어도 돌아가게 만든 사본으로 시험한다. */
class StatRequirementTest {

    static Content content;

    @BeforeAll
    static void load() { content = ContentLoader.load(Path.of("src/main/resources/content")).content(); }

    private static Map<Stat, Integer> stats(Object... kv) {
        Map<Stat, Integer> m = new EnumMap<>(Stat.class);
        for (int i = 0; i < kv.length; i += 2) m.put((Stat) kv[i], (Integer) kv[i + 1]);
        return m;
    }

    private static final StatRequirement STR30 = StatRequirement.of(Map.of(Stat.STR, 30), Map.of());
    private static final StatRequirement CLOTH30 = StatRequirement.of(Map.of(), Map.of(Stat.WIS, 30, Stat.INT, 30));

    // ── 판정 ──────────────────────────────────────────────────────────────

    @Test
    void allAnyAndNone() {
        assertTrue(StatRequirement.NONE.met(Map.of()));
        assertTrue(StatRequirement.of(Map.of(), Map.of()).isEmpty());
        assertTrue(StatRequirement.of(Map.of(Stat.STR, 0), Map.of()).isEmpty(), "0 = 요구 없음");

        assertFalse(STR30.met(stats(Stat.STR, 29)));
        assertTrue(STR30.met(stats(Stat.STR, 30)));
        assertFalse(STR30.met(Map.of()), "없는 능력치 = 0");

        StatRequirement both = StatRequirement.of(Map.of(Stat.STR, 30, Stat.VIT, 20), Map.of());
        assertFalse(both.met(stats(Stat.STR, 30, Stat.VIT, 19)), "all = 전부");
        assertTrue(both.met(stats(Stat.STR, 30, Stat.VIT, 20)));

        assertFalse(CLOTH30.met(stats(Stat.INT, 29, Stat.WIS, 29)));
        assertTrue(CLOTH30.met(stats(Stat.INT, 30)), "any = 하나만");
        assertTrue(CLOTH30.met(stats(Stat.WIS, 31)));

        StatRequirement mixed = StatRequirement.of(Map.of(Stat.VIT, 10), Map.of(Stat.INT, 30, Stat.WIS, 30));
        assertFalse(mixed.met(stats(Stat.INT, 40)));
        assertTrue(mixed.met(stats(Stat.INT, 40, Stat.VIT, 10)));
    }

    @Test
    void pointsNeeded() {
        assertEquals(0, STR30.pointsNeeded(stats(Stat.STR, 30)));
        assertEquals(8, STR30.pointsNeeded(stats(Stat.STR, 22)));
        assertEquals(30, STR30.pointsNeeded(Map.of()));
        // any = 가장 가까운 하나
        assertEquals(4, CLOTH30.pointsNeeded(stats(Stat.INT, 20, Stat.WIS, 26)));
        // all 을 채운 뒤 any (같은 능력치면 겹쳐 센다)
        StatRequirement mixed = StatRequirement.of(Map.of(Stat.INT, 20), Map.of(Stat.INT, 25, Stat.WIS, 30));
        assertEquals(10 + 5, mixed.pointsNeeded(stats(Stat.INT, 10, Stat.WIS, 10)));
    }

    @Test
    void playerStatsAreBasePlusAllocatedPlusTitleNotGear() {
        ClassDef berserker = content.classDef("berserker");
        Map<Stat, Integer> s = StatRequirement.playerStats(berserker, Map.of(Stat.STR, 5), Map.of("STR", 2.4, "xp_bonus", 0.1, "LUK", 1.0));
        assertEquals(berserker.baseStat(Stat.STR) + 5 + 2, s.get(Stat.STR));
        assertEquals(berserker.baseStat(Stat.LUK) + 1, s.get(Stat.LUK));
        assertEquals(berserker.baseStat(Stat.DEX), s.get(Stat.DEX));
        assertEquals(6, s.size(), "능력치 6종 모두");
        // 직업 없음 = 기본 0, 음수는 0
        Map<Stat, Integer> none = StatRequirement.playerStats(null, Map.of(), Map.of("STR", -5.0));
        assertEquals(0, none.get(Stat.STR));
        assertEquals(StatRequirement.playerStats(null, null, null), StatRequirement.playerStats(null, Map.of(), Map.of()));
    }

    // ── 문구 ──────────────────────────────────────────────────────────────

    @Test
    void texts() {
        assertEquals("요구 힘 30", STR30.text());
        assertEquals("요구 힘 30 · 체력 20", StatRequirement.of(Map.of(Stat.VIT, 20, Stat.STR, 30), Map.of()).text(), "STR→LUK 순서");
        assertEquals("요구 지능 또는 정신 30", CLOTH30.text());
        assertEquals("요구 지능 30 또는 정신 25", StatRequirement.of(Map.of(), Map.of(Stat.INT, 30, Stat.WIS, 25)).text());
        assertEquals("", StatRequirement.NONE.text());

        assertEquals("요구 힘 30 (현재 22)", STR30.shortfall(stats(Stat.STR, 22)));
        assertEquals("", STR30.shortfall(stats(Stat.STR, 30)));
        assertEquals("요구 지능 또는 정신 30 (현재 지능 22 · 정신 18)", CLOTH30.shortfall(stats(Stat.INT, 22, Stat.WIS, 18)));
        // 맞춘 조건은 빼고 모자란 것만
        StatRequirement both = StatRequirement.of(Map.of(Stat.STR, 30, Stat.VIT, 20), Map.of());
        assertEquals("요구 체력 20 (현재 12)", both.shortfall(stats(Stat.STR, 40, Stat.VIT, 12)));
    }

    @Test
    void tooltipLineStaticAndPerViewer() {
        assertNull(StatRequirement.NONE.tooltipLine(null));
        assertEquals("<gray>요구 힘 <white>30</white>", STR30.tooltipLine(null));
        assertEquals("<gray>요구 지능 또는 정신 <white>30</white>", CLOTH30.tooltipLine(null));
        String met = STR30.tooltipLine(stats(Stat.STR, 31));
        assertTrue(met.contains(StatRequirement.MET_COLOR) && !met.contains(StatRequirement.UNMET_COLOR) && !met.contains("현재"), met);
        String unmet = STR30.tooltipLine(stats(Stat.STR, 22));
        assertTrue(unmet.contains(StatRequirement.UNMET_COLOR) && unmet.contains("힘 30 (현재 22)"), unmet);
        assertEquals("요구 힘 30 (현재 22)", kr.labyrinth.core.Text.strip(unmet));
    }

    @Test
    void equipRulesTextAndGearOnly() {
        ItemDef sword = content.item("ember_greatsword").withRequires(STR30);
        assertEquals(EquipRules.Problem.STATS, EquipRules.check(sword, stats(Stat.STR, 22)));
        assertEquals("요구 힘 30 (현재 22)", EquipRules.problemText(sword, stats(Stat.STR, 22)));
        assertTrue(EquipRules.usable(sword, stats(Stat.STR, 30)));
        // 장신구·재료·소모품은 적혀 있어도 요구 없음
        for (ItemDef d : content.items().values()) {
            if (d.type() == ItemType.WEAPON || d.type() == ItemType.ARMOR) continue;
            ItemDef x = d.withRequires(STR30);
            assertTrue(x.requirement().isEmpty(), d.id());
            assertTrue(EquipRules.usable(x, Map.of()), d.id());
        }
        // 방패도 방어구와 같이 본다
        ItemDef shield = content.items().values().stream().filter(ItemDef::isShield).findFirst().orElseThrow()
                .withRequires(StatRequirement.of(Map.of(Stat.VIT, 30), Map.of()));
        assertFalse(EquipRules.usable(shield, stats(Stat.VIT, 29)));
    }

    // ── 툴팁 ──────────────────────────────────────────────────────────────

    @Test
    void tooltipShowsRequirementInsteadOfLevel() {
        ItemDef sword = content.item("ember_greatsword");
        ItemDef req = sword.withRequires(StatRequirement.of(Map.of(Stat.STR, 60), Map.of()));
        String plain = String.join("\n", ItemTooltip.lines(content, req, null));
        assertTrue(plain.contains("<gray>요구 힘 <white>60</white>"), plain);
        assertFalse(plain.contains("요구 레벨"), plain);
        // 요구 없음 = 줄 없음 (레벨 줄도 없다)
        String free = String.join("\n", ItemTooltip.lines(content, sword.withRequires(StatRequirement.NONE), null));
        assertFalse(free.contains("요구"), free);
        // 보는 사람을 알면 색과 지금 값
        List<String> viewer = ItemTooltip.lines(content, req, null, Map.of(), List.of(), 0, true, stats(Stat.STR, 22));
        assertTrue(String.join("\n", viewer).contains("힘 60 (현재 22)"), String.join("\n", viewer));
        assertTrue(String.join("\n", ItemTooltip.lines(content, req, null, Map.of(), List.of(), 0, true, stats(Stat.STR, 60)))
                .contains(StatRequirement.MET_COLOR));
        // 소모품은 사용 레벨 그대로
        ItemDef potion = content.items().values().stream().filter(d -> d.type() == ItemType.CONSUMABLE && d.levelReq() > 1).findFirst().orElse(null);
        if (potion != null) assertTrue(String.join("\n", ItemTooltip.lines(content, potion, null)).contains("사용 레벨"), potion.id());
    }

    /**
     * 결정 1의 규칙(R = ⌈2.5 × (내부 레벨 − 1)⌉, 2 이하는 없음)을 모든 장비에 입혀 본다 — 데이터가 바뀌기 전에도
     * 툴팁이 줄 수·폭 안에 드는지 (보는 사람 능력치 0 = 모두 빨강 "(현재 0)" 이 가장 길다).
     */
    @Test
    void ruleShapedRequirementsFitTooltips() {
        EnhanceRules rules = Enhancement.rules();
        int checked = 0;
        for (ItemDef d0 : content.items().values()) {
            if (!d0.isGear()) continue;
            ItemDef d = d0.withRequires(ruleShaped(content, d0));
            Map<String, Double> rolls = ItemRolls.roll(d, 7L);
            for (int lv : new int[] {0, 10}) {
                List<String> enh = Enhancement.tooltip(content, d, lv);
                Map<String, Double> bonus = lv > 0 && EnhanceRules.enhanceable(d) ? rules.bonus(d, rolls, lv) : Map.of();
                for (Map<Stat, Integer> viewer : java.util.Arrays.asList(null, stats(), stats(Stat.INT, 999, Stat.WIS, 999))) {
                    List<String> l = ItemTooltip.lines(content, d, rolls, bonus, enh, 0, true, viewer);
                    assertTrue(l.size() <= ItemTooltip.MAX_LINES, d.id() + " +" + lv + " = " + l.size() + "줄");
                    for (String s : l) assertTrue(TooltipFitTest.width(s) <= TooltipFitTest.MAX_WIDTH_PX, d.id() + " 너무 넓은 줄: " + s);
                }
            }
            checked++;
        }
        assertTrue(checked > 100, "장비 " + checked);
    }

    /** 결정 1 의 무기 종류·외형 → 능력치 규칙 (데이터 담당과 같은 표 — 시험용 재현). */
    static StatRequirement ruleShaped(Content c, ItemDef d) {
        int r = (int) Math.ceil(2.5 * (d.levelReq() - 1));
        if (r <= 2 || d.type() == ItemType.ACCESSORY) return StatRequirement.NONE;
        if (d.isWeapon()) {
            Stat s = switch (d.weaponType()) {
                case "greatsword", "sword_shield" -> Stat.STR;
                case "bow", "dagger" -> Stat.DEX;
                case "staff" -> Stat.INT;
                default -> Stat.WIS;
            };
            return StatRequirement.of(Map.of(s, r), Map.of());
        }
        ItemSetDef set = c.setOf(d);
        String look = d.isShield() ? "heavy" : set == null ? "light" : set.look();
        return switch (look) {
            case "heavy" -> StatRequirement.of(Map.of(Stat.VIT, r), Map.of());
            case "cloth" -> StatRequirement.of(Map.of(), Map.of(Stat.INT, r, Stat.WIS, r));
            default -> StatRequirement.of(Map.of(Stat.DEX, r), Map.of());
        };
    }

    // ── 파서·검사기 ───────────────────────────────────────────────────────

    @Test
    void parserReadsRequiresAndRequiresAny() {
        Map<String, Object> blade = new LinkedHashMap<>();
        blade.put("type", "weapon");
        blade.put("weapon_type", "greatsword");
        blade.put("level_req", 13);
        blade.put("requires", Map.of("STR", 30));
        Map<String, Object> robe = new LinkedHashMap<>();
        robe.put("type", "armor");
        robe.put("armor_slot", "chest");
        robe.put("requires_any", Map.of("INT", 30, "WIS", 30));
        Map<String, Object> bad = new LinkedHashMap<>();
        bad.put("type", "armor");
        bad.put("armor_slot", "head");
        bad.put("requires", Map.of("POW", 3, "DEX", -1, "VIT", 2.5, "STR", 0));
        Map<String, Object> items = new LinkedHashMap<>();
        items.put("t_blade", blade);
        items.put("t_robe", robe);
        items.put("t_bad", bad);
        items.put("t_plain", Map.of("type", "weapon", "weapon_type", "bow"));
        ContentParser parser = new ContentParser();
        Map<String, Map<String, Object>> files = new HashMap<>();
        files.put("items.yml", Map.of("items", items));
        Content c = parser.parse(files);

        assertEquals(Map.of(Stat.STR, 30), c.item("t_blade").requirement().all());
        assertEquals(13, c.item("t_blade").levelReq(), "level_req 는 내부 레벨로 남는다");
        assertEquals(Map.of(Stat.INT, 30, Stat.WIS, 30), c.item("t_robe").requirement().any());
        assertTrue(c.item("t_plain").requirement().isEmpty());
        assertTrue(c.item("t_bad").requirement().isEmpty());
        String problems = String.join("\n", parser.problems());
        assertTrue(problems.contains("requires.POW"), problems);
        assertTrue(problems.contains("requires.DEX"), problems);
        assertTrue(problems.contains("requires.VIT"), problems);
        assertFalse(problems.contains("requires.STR"), "0 = 요구 없음 (문제 아님)\n" + problems);
    }

    @Test
    void validatorChecksStarterGearAndIgnoredRequirements() {
        // 지금 번들 데이터: 요구 능력치 관련 경고 없음
        List<String> now = ContentValidator.validate(content).warnings().stream()
                .filter(w -> w.contains("요구 능력치") || w.contains("requires") || w.contains("시작 무기")).toList();
        assertEquals(List.of(), now);

        Map<String, ItemDef> items = new LinkedHashMap<>(content.items());
        ItemDef cap = content.item("novice_cap");
        items.put(cap.id(), cap.withRequires(StatRequirement.of(Map.of(Stat.VIT, 3), Map.of())));
        ItemDef acc = content.items().values().stream().filter(d -> d.type() == ItemType.ACCESSORY).findFirst().orElseThrow();
        items.put(acc.id(), acc.withRequires(STR30));
        ClassDef arcanist = content.classDef("arcanist");
        ItemDef staff = WeaponTypes.starterWeapon(content.items().values(), arcanist);
        int base = arcanist.baseStat(Stat.INT);
        items.put(staff.id(), staff.withRequires(StatRequirement.of(Map.of(Stat.INT, base + ContentValidator.START_POINTS + 1), Map.of())));
        Content c = content;
        Content broken = new Content(c.classes(), Map.copyOf(items), c.sets(), c.mobs(), c.bosses(), c.floors(), c.lootTables(), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces());
        String all = String.join("\n", ContentValidator.validate(broken).warnings());
        assertTrue(all.contains("items.novice_cap: 시작 지급 장비인데 요구 능력치가 있음 (요구 체력 3)"), all);
        assertTrue(all.contains("items." + acc.id() + ": requires/requires_any 는 무기·방어구·방패만"), all);
        assertTrue(all.contains("items." + staff.id() + ": 직업 arcanist 의 시작 무기인데 Lv.1 에 쓸 수 없음"), all);
        // 시작 포인트로 딱 맞추면 통과
        items.put(staff.id(), staff.withRequires(StatRequirement.of(Map.of(Stat.INT, base + ContentValidator.START_POINTS), Map.of())));
        Content ok = new Content(c.classes(), Map.copyOf(items), c.sets(), c.mobs(), c.bosses(), c.floors(), c.lootTables(), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces());
        assertFalse(String.join("\n", ContentValidator.validate(ok).warnings()).contains("직업 arcanist 의 시작 무기"));
    }

    /** 번들 데이터 (데이터 담당이 requires 를 채운 뒤에도): 직업마다 시작 무기·시작 지급 장비를 Lv.1 에 쓸 수 있다. */
    @Test
    void everyClassCanUseItsStarterGearAtLevelOne() {
        for (ClassDef cls : content.classes().values()) {
            Map<Stat, Integer> lv1 = StatRequirement.playerStats(cls, Map.of(), Map.of());
            ItemDef w = WeaponTypes.starterWeapon(content.items().values(), cls);
            assertTrue(w.requirement().pointsNeeded(lv1) <= ContentValidator.START_POINTS, cls.id() + " → " + w.id() + " " + w.requirement().text());
            for (ItemDef d : content.items().values()) {
                if (d.isGear() && d.sources().contains("starter")) assertTrue(d.requirement().isEmpty(), d.id() + " " + d.requirement().text());
            }
        }
    }

    // ── 착용 막기: 칸 대응 (EquipmentListener) ──────────────────────────────

    /** 막기는 그 장비의 제 칸에서만 — 투구를 장화 칸에 대는 것처럼 바닐라가 넣지 않는 동작에는 "착용할 수 없습니다" 가 없다. */
    @Test
    void denyOnlyOnOwnSlot() {
        assertEquals(EquipmentSlot.FEET, EquipmentListener.equipSlotOf(36));
        assertEquals(EquipmentSlot.LEGS, EquipmentListener.equipSlotOf(37));
        assertEquals(EquipmentSlot.CHEST, EquipmentListener.equipSlotOf(38));
        assertEquals(EquipmentSlot.HEAD, EquipmentListener.equipSlotOf(39));
        assertEquals(EquipmentSlot.OFF_HAND, EquipmentListener.equipSlotOf(40));
        assertNull(EquipmentListener.equipSlotOf(0));
        assertNull(EquipmentListener.equipSlotOf(35));
        assertNull(EquipmentListener.equipSlotOf(41));

        Map<String, EquipmentSlot> bySlot = Map.of("head", EquipmentSlot.HEAD, "chest", EquipmentSlot.CHEST,
                "legs", EquipmentSlot.LEGS, "feet", EquipmentSlot.FEET, "offhand", EquipmentSlot.OFF_HAND);
        for (ItemDef d : content.items().values()) {
            EquipmentSlot own = EquipmentListener.ownSlot(d);
            if (d.type() == ItemType.ARMOR) assertEquals(bySlot.get(d.armorSlot()), own, d.id());
            else assertNull(own, d.id() + " — 방어구가 아니면 막지 않음 (무기는 들 수 있음, 장신구는 조건 없음)");
        }
        assertNull(EquipmentListener.ownSlot(null));
    }

    /** 예전 시그니처(requires 없음) 생성자 = 요구 없음 — 같은 기준에서 갈라진 코드가 그대로 컴파일·동작. */
    @Test
    void legacyConstructorHasNoRequirement() {
        ItemDef d = content.items().values().stream().filter(x -> x.type() == ItemType.ARMOR).findFirst().orElseThrow();
        ItemDef old = new ItemDef(d.id(), d.name(), d.type(), d.weaponType(), d.armorSlot(), d.armorSet(), d.rarity(), d.levelReq(),
                d.classes(), d.stats(), d.setBonus(), d.aura(), d.weaponSkills(), d.floor(), d.pool(), d.sources(), d.use(),
                d.model(), d.texture(), d.lore(), d.raw());
        assertTrue(old.requirement().isEmpty());
        assertEquals(d.withRequires(StatRequirement.NONE), old);
    }
}
