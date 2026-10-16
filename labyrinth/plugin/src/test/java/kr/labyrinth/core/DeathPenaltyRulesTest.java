package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.SplittableRandom;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.core.DeathPenaltyRules.Config;
import kr.labyrinth.core.DeathPenaltyRules.Lost;
import kr.labyrinth.core.DeathPenaltyRules.Plan;
import kr.labyrinth.core.DeathPenaltyRules.Where;
import kr.labyrinth.stats.XpCurve;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** 0.3.6.1 죽음 페널티 — 칸 고르기 · 안전한 물건 · 경험치 · 어디서 죽었나 · config · 안내 문구. */
class DeathPenaltyRulesTest {

    static boolean[] full() {
        boolean[] e = new boolean[DeathPenaltyRules.STORAGE_SLOTS];
        java.util.Arrays.fill(e, true);
        return e;
    }

    // ── 칸 고르기 ────────────────────────────────────────────────────────

    @Test
    void picksTwoOrThreeUniformlyAndNeverTheHeldSlot() {
        int two = 0, three = 0;
        int[] hits = new int[DeathPenaltyRules.STORAGE_SLOTS];
        for (long seed = 0; seed < 6000; seed++) {
            int held = (int) (seed % 9);
            int[] got = DeathPenaltyRules.pickSlots(full(), held, 2, 3, new SplittableRandom(seed));
            assertTrue(got.length == 2 || got.length == 3, "2 또는 3칸");
            if (got.length == 2) two++;
            else three++;
            Set<Integer> seen = new HashSet<>();
            for (int g : got) {
                assertTrue(g >= 0 && g < 36, "단축 칸 + 가방 36칸 안");
                assertTrue(g != held, "손에 든 칸은 안전");
                assertTrue(seen.add(g), "같은 칸 두 번 없음");
                hits[g]++;
            }
        }
        // 2와 3이 반반 (±5%)
        assertTrue(Math.abs(two - three) < 600, "2칸 " + two + " · 3칸 " + three);
        // 가방 칸(9~35, 손에 든 칸이 될 수 없음)은 고르게 뽑힌다
        int min = Integer.MAX_VALUE, max = 0;
        for (int i = 9; i < 36; i++) {
            min = Math.min(min, hits[i]);
            max = Math.max(max, hits[i]);
        }
        assertTrue(min > 0 && max < min * 1.35, "고르게: " + min + " ~ " + max);
    }

    @Test
    void sameSeedSameSlots() {
        int[] a = DeathPenaltyRules.pickSlots(full(), 0, 2, 3, new SplittableRandom(42));
        int[] b = DeathPenaltyRules.pickSlots(full(), 0, 2, 3, new SplittableRandom(42));
        assertArrayEquals(a, b);
        for (int i = 1; i < a.length; i++) assertTrue(a[i - 1] < a[i], "오름차순");
    }

    @Test
    void emptyAndSafeSlotsDoNotCount() {
        boolean[] e = new boolean[36];
        e[4] = true;   // 손에 든 칸 (안전)
        e[20] = true;
        e[31] = true;
        for (long seed = 0; seed < 200; seed++) {
            int[] got = DeathPenaltyRules.pickSlots(e, 4, 2, 3, new SplittableRandom(seed));
            assertArrayEquals(new int[] {20, 31}, got, "후보 둘 → 3이 나와도 둘만");
        }
    }

    @Test
    void fewerThanTwoLosesWhatThereIs() {
        boolean[] one = new boolean[36];
        one[12] = true;
        for (long seed = 0; seed < 50; seed++) {
            assertArrayEquals(new int[] {12}, DeathPenaltyRules.pickSlots(one, 0, 2, 3, new SplittableRandom(seed)));
        }
        assertEquals(0, DeathPenaltyRules.pickSlots(new boolean[36], 0, 2, 3, new SplittableRandom(1)).length, "빈 가방");
        boolean[] onlyHeld = new boolean[36];
        onlyHeld[3] = true;
        assertEquals(0, DeathPenaltyRules.pickSlots(onlyHeld, 3, 2, 3, new SplittableRandom(1)).length, "손에 든 것만 있음");
    }

    @Test
    void armorAndOffhandIndicesAreNeverCandidates() {
        boolean[] e = new boolean[41]; // getContents() 를 잘못 넘겨도 36 이상(갑옷 36~39 · 보조손 40)은 보지 않는다
        for (int i = 36; i < 41; i++) e[i] = true;
        assertEquals(0, DeathPenaltyRules.pickSlots(e, 0, 2, 3, new SplittableRandom(7)).length);
        assertEquals(0, DeathPenaltyRules.pickSlots(null, 0, 2, 3, new SplittableRandom(7)).length);
    }

    @Test
    void rollCountBounds() {
        SplittableRandom r = new SplittableRandom(3);
        for (int i = 0; i < 100; i++) assertEquals(2, DeathPenaltyRules.rollCount(2, 2, r));
        for (int i = 0; i < 100; i++) assertEquals(4, DeathPenaltyRules.rollCount(4, 1, r), "max < min → min");
        for (int i = 0; i < 100; i++) assertEquals(0, DeathPenaltyRules.rollCount(0, 0, r));
    }

    // ── 안전한 물건 ──────────────────────────────────────────────────────

    @Test
    void keysEmblemsAndLabArrowAreAlwaysSafe() {
        Set<String> none = Set.of();
        assertTrue(DeathPenaltyRules.alwaysSafe(ItemType.KEY, "vault_key", false, none), "층 금고 열쇠");
        assertTrue(DeathPenaltyRules.alwaysSafe(ItemType.KEY, "guardian_emblem", false, none), "직업 문장");
        assertTrue(DeathPenaltyRules.alwaysSafe(null, "arrow", true, none), "미궁 활 무한 화살");
        assertFalse(DeathPenaltyRules.alwaysSafe(null, "arrow", false, none), "보통 화살은 잃을 수 있음");
    }

    @Test
    void ordinaryProgressItemsCanBeLost() {
        Set<String> none = Set.of();
        assertFalse(DeathPenaltyRules.alwaysSafe(ItemType.BLUEPRINT, "blueprint", false, none), "안 배운 도안");
        assertFalse(DeathPenaltyRules.alwaysSafe(ItemType.MATERIAL, "class_change_scroll", false, none), "전직의 두루마리 (핀이 팜)");
        assertFalse(DeathPenaltyRules.alwaysSafe(ItemType.CONSUMABLE, "return_scroll", false, none));
        assertFalse(DeathPenaltyRules.alwaysSafe(ItemType.WEAPON, "corridor_longsword", false, none));
        assertFalse(DeathPenaltyRules.alwaysSafe(ItemType.MATERIAL, "iron_ingot", false, none));
        assertFalse(DeathPenaltyRules.alwaysSafe(null, "shulker_box", false, none), "셜커 상자도 한 칸");
    }

    @Test
    void minePickaxesAreSafe() {
        // 광산 곡괭이(type tool)는 미궁에서 쓸 데가 없는 광산 성장 — 미궁 죽음으로 되돌리지 않는다
        for (String id : List.of("copper_pickaxe", "iron_pickaxe", "silver_pickaxe", "gold_pickaxe", "mithril_pickaxe", "orichalcum_pickaxe")) {
            assertTrue(DeathPenaltyRules.alwaysSafe(ItemType.TOOL, id, false, Set.of()), id);
        }
        assertFalse(DeathPenaltyRules.alwaysSafe(null, "diamond_pickaxe", false, Set.of()), "바닐라 곡괭이는 보통 물건");
    }

    @Test
    void safeItemsListFromConfig() {
        Set<String> safe = Set.of("return_scroll", "totem_of_undying");
        assertTrue(DeathPenaltyRules.alwaysSafe(ItemType.CONSUMABLE, "return_scroll", false, safe));
        assertTrue(DeathPenaltyRules.alwaysSafe(null, "TOTEM_OF_UNDYING", false, safe), "대소문자 무시");
        assertFalse(DeathPenaltyRules.alwaysSafe(null, null, false, safe));
    }

    @Test
    void bundledKeyItemsAreTypeKey() throws Exception {
        // items.yml 의 열쇠·문장이 type key 로 남아 있어야 안전 규칙이 맞는다
        YamlConfiguration items = YamlConfiguration.loadConfiguration(new File("src/main/resources/content/items.yml"));
        for (String id : List.of("vault_key", "guardian_emblem", "berserker_emblem", "hunter_emblem", "arcanist_emblem",
                "priest_emblem", "shadow_emblem")) {
            assertEquals("key", items.getString("items." + id + ".type"), id);
        }
        assertEquals("material", items.getString("items.class_change_scroll.type"), "전직의 두루마리 = 보통 물건 (잃을 수 있음)");
        for (String id : List.of("copper_pickaxe", "iron_pickaxe", "silver_pickaxe", "gold_pickaxe", "mithril_pickaxe", "orichalcum_pickaxe")) {
            assertEquals("tool", items.getString("items." + id + ".type"), id + " = 광산 곡괭이 (안전)");
        }
        // type tool 은 광산 곡괭이뿐이어야 '도구는 안전' 이 곡괭이 규칙과 같다
        for (String id : items.getConfigurationSection("items").getKeys(false)) {
            if ("tool".equals(items.getString("items." + id + ".type"))) assertTrue(id.endsWith("_pickaxe"), id);
        }
    }

    // ── 경험치 ───────────────────────────────────────────────────────────

    @Test
    void xpProgressOnlyAndNothingAtMaxLevel() {
        XpCurve curve = XpCurve.DEFAULT;
        assertEquals(120, DeathPenaltyRules.xpLost(5, 120, curve.maxLevel()));
        assertEquals(0, DeathPenaltyRules.xpLost(5, 0, curve.maxLevel()), "막 레벨업 = 잃을 것 없음");
        assertEquals(0, DeathPenaltyRules.xpLost(curve.maxLevel(), 0, curve.maxLevel()), "최고 레벨");
        assertEquals(0, DeathPenaltyRules.xpLost(curve.maxLevel(), 999, curve.maxLevel()), "최고 레벨은 경험치가 있어도 그대로");
        assertEquals(0, DeathPenaltyRules.xpLost(3, -5, curve.maxLevel()));
        // 레벨은 그대로: 잃는 양은 이번 레벨 필요량보다 작다 (진행도만)
        long need = curve.xpToNext(10);
        assertTrue(DeathPenaltyRules.xpLost(10, need - 1, curve.maxLevel()) < need);
    }

    // ── 어디서 죽었나 ────────────────────────────────────────────────────

    @Test
    void dungeonRunLosesItemsEverywhereElseOnlyXp() {
        Config c = Config.DEFAULT;
        assertEquals(new Plan(true, true), DeathPenaltyRules.plan(c, Where.DUNGEON_RUN, false));
        assertEquals(new Plan(true, false), DeathPenaltyRules.plan(c, Where.LABYRINTH_WORLD, false), "관전 중 /kill 등");
        assertEquals(new Plan(true, false), DeathPenaltyRules.plan(c, Where.OUTSIDE, false), "야생·마을·네더·엔드·PvP");
        assertEquals(new Plan(true, false), DeathPenaltyRules.plan(c, Where.DUNGEON_RUN, true), "관리자 시험 입장");
    }

    @Test
    void configSwitches() {
        assertEquals(Plan.NONE, DeathPenaltyRules.plan(Config.OFF, Where.DUNGEON_RUN, false));
        assertFalse(DeathPenaltyRules.plan(Config.OFF, Where.OUTSIDE, false).any());
        Config noItems = new Config(true, false, 2, 3, Set.of());
        assertEquals(new Plan(true, false), DeathPenaltyRules.plan(noItems, Where.DUNGEON_RUN, false));
        Config noXp = new Config(false, true, 2, 3, Set.of());
        assertEquals(new Plan(false, true), DeathPenaltyRules.plan(noXp, Where.DUNGEON_RUN, false));
        assertEquals(Plan.NONE, DeathPenaltyRules.plan(noXp, Where.OUTSIDE, false));
        Config zero = new Config(true, true, 0, 0, Set.of());
        assertFalse(DeathPenaltyRules.plan(zero, Where.DUNGEON_RUN, false).destroySlots(), "0칸 = 끔");
    }

    @Test
    void keepInventoryFalseDoesNotAddDestruction() {
        // keep_inventory false 서버: 밖에서는 바닐라처럼 떨어지고(주울 수 있음), 플러그인은 경험치만. 미궁 안 규칙은 그대로.
        Settings s = new Settings(WildConfigTest.yaml("death:\n  keep_inventory: false\n  keep_level: false\n"));
        assertFalse(s.death().keepInventory());
        assertEquals(Config.DEFAULT, s.deathPenalty(), "페널티는 keep_inventory 와 따로");
        assertEquals(new Plan(true, false), DeathPenaltyRules.plan(s.deathPenalty(), Where.OUTSIDE, false));
        assertEquals(new Plan(true, true), DeathPenaltyRules.plan(s.deathPenalty(), Where.DUNGEON_RUN, false));
    }

    // ── config ───────────────────────────────────────────────────────────

    @Test
    void missingKeysMeanDefaultsOn() {
        assertEquals(Config.DEFAULT, new Settings(new YamlConfiguration()).deathPenalty(), "death 없음");
        // 0.3.6 서버 config (death 에 keep 두 줄만) — jar 만 바꾸면 켜진다
        assertEquals(Config.DEFAULT,
                new Settings(WildConfigTest.yaml("death:\n  keep_inventory: true\n  keep_level: true\n")).deathPenalty());
        assertEquals(new Config(true, true, 2, 3, Set.of()), Config.DEFAULT);
    }

    @Test
    void bundledConfigMatchesCodeDefaults() {
        YamlConfiguration jar = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertEquals(Config.DEFAULT, new Settings(jar).deathPenalty());
        assertTrue(jar.getBoolean("death.keep_inventory") && jar.getBoolean("death.keep_level"), "인벤세이브 그대로");
    }

    @Test
    void readingDefaultsDoesNotWriteAnEmptySection() {
        YamlConfiguration file = WildConfigTest.yaml("death:\n  keep_inventory: true\n");
        file.setDefaults(YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml")));
        assertEquals(Config.DEFAULT, new Settings(file).deathPenalty());
        assertFalse(file.saveToString().contains("penalty"), "읽기만으로 penalty 섹션이 생기면 안 됨");
    }

    @Test
    void offSwitchesAndPartialKeys() {
        assertEquals(Config.OFF, new Settings(WildConfigTest.yaml("death:\n  penalty: false\n")).deathPenalty());
        Config c = new Settings(WildConfigTest.yaml("death:\n  penalty:\n    dungeon_item_loss: false\n")).deathPenalty();
        assertTrue(c.xpProgressReset());
        assertFalse(c.itemLoss());
        c = new Settings(WildConfigTest.yaml("death:\n  penalty:\n    xp_progress_reset: false\n")).deathPenalty();
        assertEquals(new Config(false, true, 2, 3, Set.of()), c);
        c = new Settings(WildConfigTest.yaml(
                "death:\n  penalty:\n    dungeon_item_loss:\n      slots_max: 5\n      safe_items: [Return_Scroll, ' ', diamond]\n"))
                .deathPenalty();
        assertEquals(new Config(true, true, 2, 5, Set.of("return_scroll", "diamond")), c);
    }

    @Test
    void slotCountsAreClamped() {
        Config c = new Settings(WildConfigTest.yaml(
                "death:\n  penalty:\n    dungeon_item_loss:\n      slots_min: 5\n      slots_max: 1\n")).deathPenalty();
        assertEquals(5, c.slotsMin());
        assertEquals(5, c.slotsMax(), "max < min → min");
        c = new Settings(WildConfigTest.yaml(
                "death:\n  penalty:\n    dungeon_item_loss:\n      slots_min: -3\n      slots_max: 99\n")).deathPenalty();
        assertEquals(0, c.slotsMin());
        assertEquals(36, c.slotsMax());
    }

    // ── 안내 문구 ────────────────────────────────────────────────────────

    @Test
    void lostLineMergesSameNamesAndSkipsCountOfOne() {
        List<String> l = DeathPenaltyRules.lines(List.of(new Lost("철 주괴", 13), new Lost("하급 치유 물약", 5),
                new Lost("철 주괴", 64)), 0);
        assertEquals(1, l.size());
        String plain = Text.strip(l.get(0));
        assertEquals("죽어서 잃었습니다: 철 주괴 ×77, 하급 치유 물약 ×5", plain);
        assertEquals("죽어서 잃었습니다: 회랑 수비대 장검",
                Text.strip(DeathPenaltyRules.lines(List.of(new Lost("회랑 수비대 장검", 1)), 0).get(0)));
    }

    @Test
    void xpLineOnlyWhenSomethingWasLost() {
        assertTrue(DeathPenaltyRules.lines(List.of(), 0).isEmpty(), "잃은 것 없음 = 말 없음");
        List<String> l = DeathPenaltyRules.lines(List.of(), 1234);
        assertEquals(1, l.size());
        assertEquals("이번 레벨 경험치가 처음으로 돌아갔습니다. (-1,234 XP)", Text.strip(l.get(0)));
        assertEquals(2, DeathPenaltyRules.lines(List.of(new Lost("빵", 3)), 10).size());
    }

    @Test
    void vanillaNamesStayTranslatable() {
        String line = DeathPenaltyRules.lines(List.of(new Lost("<lang:item.minecraft.iron_ingot>", 13)), 0).get(0);
        assertTrue(line.contains("<lang:item.minecraft.iron_ingot>"), line);
        assertNotNull(Text.mm(line));
    }

    @Test
    void menuLine() {
        assertEquals("쓰러지면 이번 레벨 경험치를 잃고, 미궁 안이면 가방 물건 2~3칸도 잃습니다.", DeathPenaltyRules.menuLine(Config.DEFAULT));
        assertEquals("쓰러지면 이번 레벨 경험치를 잃습니다.", DeathPenaltyRules.menuLine(new Config(true, false, 2, 3, Set.of())));
        assertEquals("미궁 안에서 쓰러지면 가방 물건 1칸을 잃습니다.", DeathPenaltyRules.menuLine(new Config(false, true, 1, 1, Set.of())));
        assertNull(DeathPenaltyRules.menuLine(Config.OFF));
    }

    @Test
    void noticeText() {
        String n = DeathPenaltyRules.notice(Config.DEFAULT);
        assertNotNull(n);
        assertEquals("미궁 안에서 쓰러지면 가방 속 물건 2~3칸이 사라지고, 이번 레벨 경험치도 처음으로 돌아갑니다. "
                + "손에 든 것·입은 장비·장신구·보조손·열쇠·곡괭이는 안전합니다.", Text.strip(n));
        assertTrue(Text.strip(DeathPenaltyRules.notice(new Config(false, true, 2, 2, Set.of()))).contains("물건 2칸이 사라집니다."));
        assertNull(DeathPenaltyRules.notice(Config.OFF));
        assertEquals("쓰러지면 이번 레벨 경험치가 처음으로 돌아갑니다. 미궁 밖에서도 같습니다.",
                Text.strip(DeathPenaltyRules.notice(new Config(true, false, 2, 3, Set.of()))), "물건을 꺼도 경험치 규칙은 알려 줌");
        assertNull(DeathPenaltyRules.notice(new Config(false, false, 2, 3, Set.of())));
    }

    // ── 전투 중 퇴장 ─────────────────────────────────────────────────────

    @Test
    void combatExitCastsOnlyWhenAliveAndHurtRecently() {
        Config c = Config.DEFAULT;
        assertEquals(5.0, c.combatExitSeconds());
        assertEquals(5.0, DeathPenaltyRules.exitCastSeconds(c, false, true, 0), "막 맞음");
        assertEquals(5.0, DeathPenaltyRules.exitCastSeconds(c, false, true, 9_999));
        assertEquals(0.0, DeathPenaltyRules.exitCastSeconds(c, false, true, 10_000), "10초 지나면 바로");
        assertEquals(0.0, DeathPenaltyRules.exitCastSeconds(c, false, true, -1), "맞은 적 없음");
        assertEquals(0.0, DeathPenaltyRules.exitCastSeconds(c, false, false, 0), "쓰러져 관전 중이면 바로");
        assertEquals(0.0, DeathPenaltyRules.exitCastSeconds(c, true, true, 0), "관리자 시험 입장");
        assertEquals(0.0, DeathPenaltyRules.exitCastSeconds(Config.OFF, false, true, 0), "페널티 끔 = 0.3.6 처럼 바로");
        assertEquals(0.0, DeathPenaltyRules.exitCastSeconds(null, false, true, 0));
        Config xpOnly = new Config(true, false, 2, 3, Set.of());
        assertEquals(5.0, DeathPenaltyRules.exitCastSeconds(xpOnly, false, true, 0), "경험치만 켜도 피하는 길은 막음");
        Config instant = new Config(true, true, 2, 3, Set.of(), 0);
        assertEquals(0.0, DeathPenaltyRules.exitCastSeconds(instant, false, true, 0), "combat_exit_seconds: 0");
    }

    @Test
    void combatExitSecondsFromConfig() {
        assertEquals(0.0, new Settings(WildConfigTest.yaml("death:\n  penalty:\n    combat_exit_seconds: 0\n")).deathPenalty()
                .combatExitSeconds());
        assertEquals(2.5, new Settings(WildConfigTest.yaml("death:\n  penalty:\n    combat_exit_seconds: 2.5\n")).deathPenalty()
                .combatExitSeconds());
        assertEquals(0.0, new Settings(WildConfigTest.yaml("death:\n  penalty:\n    combat_exit_seconds: -4\n")).deathPenalty()
                .combatExitSeconds());
        assertEquals(30.0, new Settings(WildConfigTest.yaml("death:\n  penalty:\n    combat_exit_seconds: 600\n")).deathPenalty()
                .combatExitSeconds());
        assertEquals(5.0, new Settings(WildConfigTest.yaml("death:\n  penalty:\n    xp_progress_reset: true\n")).deathPenalty()
                .combatExitSeconds(), "키가 없으면 5초");
        assertEquals("싸우는 중이라 5초 뒤에 나갑니다. 그동안 맞으면 끊깁니다.", Text.strip(DeathPenaltyRules.exitCastText(5)));
        assertEquals("2.5", DeathPenaltyRules.seconds(2.5));
    }
}
