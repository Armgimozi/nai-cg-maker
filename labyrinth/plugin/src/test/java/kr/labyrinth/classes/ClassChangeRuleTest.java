package kr.labyrinth.classes;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.Settings;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** 직업 변경 규칙 (GDD §4.5): 첫 선택 무료 · 전직의 두루마리 · 대기 시간 · 미궁 공략 중 금지. */
class ClassChangeRuleTest {

    private static final long H = 3_600_000L;
    private static final long M = 60_000L;
    private static final long NOW = 1_800_000_000_000L;
    private static final Settings.ClassChange RULE = Settings.ClassChange.DEFAULT; // 두루마리 1장 + 24시간

    @Test
    void firstChoiceIsFree() {
        // 지금 직업이 없으면 두루마리도 대기 시간도 보지 않는다 (기록이 방금이어도 — 관리자가 비운 경우)
        ClassChangeRule.Verdict v = ClassChangeRule.check(RULE, null, "hunter", false, false, NOW - M, NOW);
        assertTrue(v.allowed());
        assertTrue(v.first());
        assertFalse(v.needsItem());
        assertFalse(v.missingItem());
        assertFalse(v.consumesItem());
        assertEquals(0, v.cooldownLeftMs());
    }

    @Test
    void laterChangeNeedsScrollAndConsumesIt() {
        ClassChangeRule.Verdict none = ClassChangeRule.check(RULE, "guardian", "hunter", false, false, 0, NOW);
        assertFalse(none.allowed());
        assertEquals(ClassChangeRule.Block.NO_ITEM, none.block());
        assertTrue(none.needsItem());
        assertTrue(none.missingItem());
        assertFalse(none.consumesItem());

        ClassChangeRule.Verdict ok = ClassChangeRule.check(RULE, "guardian", "hunter", false, true, 0, NOW);
        assertTrue(ok.allowed());
        assertFalse(ok.first());
        assertTrue(ok.consumesItem());

        // require_item: false → 두루마리 없이
        Settings.ClassChange free = new Settings.ClassChange(false, "class_change_scroll", 24);
        ClassChangeRule.Verdict f = ClassChangeRule.check(free, "guardian", "hunter", false, false, 0, NOW);
        assertTrue(f.allowed());
        assertFalse(f.needsItem());
        assertFalse(f.consumesItem());
    }

    @Test
    void cooldownMath() {
        // 11시간 30분 전에 바꿨으면 24시간 중 12시간 30분 남음
        long last = NOW - (11 * H + 30 * M);
        assertEquals(12 * H + 30 * M, ClassChangeRule.cooldownLeft(RULE, last, NOW));
        ClassChangeRule.Verdict v = ClassChangeRule.check(RULE, "guardian", "hunter", false, true, last, NOW);
        assertEquals(ClassChangeRule.Block.COOLDOWN, v.block());
        assertEquals("12시간 30분", ClassChangeRule.duration(v.cooldownLeftMs()));
        // 대기 시간이 먼저 — 두루마리도 없으면 함께 알려 주려고 따로 표시
        ClassChangeRule.Verdict both = ClassChangeRule.check(RULE, "guardian", "hunter", false, false, last, NOW);
        assertEquals(ClassChangeRule.Block.COOLDOWN, both.block());
        assertTrue(both.missingItem());

        // 정확히 24시간 지나면 끝 · 기록 없음(예전 플레이어) = 대기 없음 · 대기 0 = 언제나
        assertEquals(0, ClassChangeRule.cooldownLeft(RULE, NOW - 24 * H, NOW));
        assertEquals(1, ClassChangeRule.cooldownLeft(RULE, NOW - 24 * H + 1, NOW));
        assertEquals(0, ClassChangeRule.cooldownLeft(RULE, 0, NOW));
        assertEquals(0, ClassChangeRule.cooldownLeft(new Settings.ClassChange(true, "class_change_scroll", 0), NOW - M, NOW));
        assertTrue(ClassChangeRule.check(RULE, "guardian", "hunter", false, true, NOW - 25 * H, NOW).allowed());
        // 시계가 거꾸로 가도(기록이 미래) 대기 시간보다 길어지지 않는다
        assertEquals(24 * H, ClassChangeRule.cooldownLeft(RULE, NOW + 5 * H, NOW));
        // 소수 시간
        Settings.ClassChange half = new Settings.ClassChange(true, "class_change_scroll", 1.5);
        assertEquals(90 * M, half.cooldownMs());
        assertEquals(30 * M, ClassChangeRule.cooldownLeft(half, NOW - 60 * M, NOW));
    }

    @Test
    void blockedInsideDungeonRunEvenForFirstChoice() {
        ClassChangeRule.Verdict first = ClassChangeRule.check(RULE, null, "hunter", true, false, 0, NOW);
        assertFalse(first.allowed());
        assertEquals(ClassChangeRule.Block.IN_RUN, first.block());
        ClassChangeRule.Verdict later = ClassChangeRule.check(RULE, "guardian", "hunter", true, true, 0, NOW);
        assertEquals(ClassChangeRule.Block.IN_RUN, later.block());
        assertFalse(later.consumesItem(), "막히면 두루마리를 쓰지 않는다");
        // 미궁 안 + 대기 중이면 미궁 쪽을 먼저 알린다
        assertEquals(ClassChangeRule.Block.IN_RUN, ClassChangeRule.check(RULE, "guardian", "hunter", true, true, NOW - H, NOW).block());
    }

    @Test
    void sameClassIsRejectedFirst() {
        assertEquals(ClassChangeRule.Block.SAME_CLASS, ClassChangeRule.check(RULE, "hunter", "hunter", true, false, NOW, NOW).block());
        // 상태만 볼 때(target null) 는 같은 직업이 아니다
        assertNull(ClassChangeRule.check(RULE, "hunter", null, false, true, 0, NOW).block());
    }

    @Test
    void durationText() {
        assertEquals("12시간 30분", ClassChangeRule.duration(12 * H + 30 * M));
        assertEquals("24시간", ClassChangeRule.duration(24 * H));
        assertEquals("45분", ClassChangeRule.duration(45 * M));
        assertEquals("1분", ClassChangeRule.duration(1_000), "1분 미만도 1분 (분 단위 올림)");
        assertEquals("2시간 1분", ClassChangeRule.duration(2 * H + 1));
        assertEquals("0분", ClassChangeRule.duration(0));
        assertEquals("24시간", ClassChangeRule.hours(24));
        assertEquals("1시간 30분", ClassChangeRule.hours(1.5));
        assertEquals("없음", ClassChangeRule.hours(0));
    }

    @Test
    void settingsDefaultsAndDisable() throws Exception {
        // 키가 없으면 코드 기본값 (기존 서버도 켜진다)
        Settings bare = new Settings(new YamlConfiguration());
        assertEquals(Settings.ClassChange.DEFAULT, bare.classChange());
        assertTrue(bare.classChange().requireItem());
        assertEquals("class_change_scroll", bare.classChange().item());
        assertEquals(24 * H, bare.classChange().cooldownMs());
        assertEquals(Settings.Death.DEFAULT, bare.death());
        assertTrue(bare.death().keepInventory() && bare.death().keepLevel());

        assertEquals(Settings.ClassChange.NONE, new Settings(yaml("class_change: false")).classChange());
        Settings custom = new Settings(yaml("""
                class_change: {require_item: false, cooldown_hours: 6}
                death: {keep_inventory: false}
                """));
        assertEquals(new Settings.ClassChange(false, "class_change_scroll", 6), custom.classChange(), "빠진 item = 기본 두루마리");
        assertFalse(custom.death().keepInventory());
        assertTrue(custom.death().keepLevel(), "빠진 키는 true");
        assertEquals(0, new Settings(yaml("class_change: {cooldown_hours: -3, item: ' '}")).classChange().cooldownMs(), "음수 = 0");
        assertEquals("class_change_scroll", new Settings(yaml("class_change: {item: ' '}")).classChange().item());

        // jar 의 config.yml = 코드 기본값
        YamlConfiguration jar = new YamlConfiguration();
        jar.load(new java.io.File("src/main/resources/config.yml"));
        Settings js = new Settings(jar);
        assertEquals(Settings.ClassChange.DEFAULT, js.classChange());
        assertEquals(Settings.Death.DEFAULT, js.death());
    }

    @Test
    void scrollExistsIsNotRightClickUsableAndSoldByMerchant() throws Exception {
        Content c = ContentLoader.load(java.nio.file.Path.of("src/main/resources/content")).content();
        ItemDef scroll = c.item(Settings.ClassChange.DEFAULT_ITEM);
        assertNotNull(scroll, "items.yml 에 class_change_scroll");
        assertEquals(ItemType.MATERIAL, scroll.type(), "우클릭 사용 없음 (consumable 이 아니다)");
        assertTrue(scroll.use() == null || scroll.use().isEmpty(), "use 없음");
        assertTrue(scroll.sources().contains("shop"));
        int price = -1;
        for (NpcDef n : c.npcs().values()) {
            if (!"merchant".equals(n.role()) || n.shop() == null) continue;
            for (NpcDef.ShopEntry e : n.shop()) if (e.item().equals(scroll.id())) price = e.price();
        }
        assertEquals(3000, price, "떠돌이 상인 핀이 3000 골드에 판다");
    }

    @Test
    void lastChangeTimePersistsInPlayerDataExt() throws Exception {
        kr.labyrinth.data.PlayerData d = new kr.labyrinth.data.PlayerData(java.util.UUID.randomUUID(), "tester");
        assertEquals(0, ClassChangeGate.lastChange(d), "기록 없음 = 0 (예전 플레이어는 대기 없이)");
        d.classId("guardian");
        d.ext().put(ClassChangeGate.CHANGED_AT, NOW);
        kr.labyrinth.data.PlayerData r = kr.labyrinth.data.PlayerData.fromYaml(d.uuid(), "tester", d.toYaml());
        assertEquals(NOW, ClassChangeGate.lastChange(r));
        assertEquals("guardian", r.classId());
    }

    private static YamlConfiguration yaml(String text) throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(text);
        return y;
    }
}
