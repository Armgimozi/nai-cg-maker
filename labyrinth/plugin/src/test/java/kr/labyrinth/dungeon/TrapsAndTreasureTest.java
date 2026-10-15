package kr.labyrinth.dungeon;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.function.Predicate;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.dungeon.gen.FloorGenerator;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.traps.HazardPlan;
import kr.labyrinth.dungeon.traps.TrapMath;
import kr.labyrinth.dungeon.traps.TrapSpot;
import kr.labyrinth.dungeon.traps.TrapType;
import kr.labyrinth.dungeon.treasure.ChestLedger;
import kr.labyrinth.dungeon.treasure.ChestSettings;
import kr.labyrinth.dungeon.treasure.ChestTier;
import kr.labyrinth.dungeon.treasure.TreasurePlan;
import kr.labyrinth.dungeon.treasure.TreasurePlanner;
import kr.labyrinth.dungeon.treasure.VaultKeys;
import kr.labyrinth.items.enhance.EnhanceRules;
import kr.labyrinth.titles.AchievementRules;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 함정 배치 규칙·해제 공식·미로 상자 개인 루팅·금고 열쇠 (GDD §5.5·§5.6). */
class TrapsAndTreasureTest {

    static Content content;
    static final int SEEDS = 20;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        FloorGeneratorTest.content = content;
    }

    static FloorLayout layout(FloorDef f, long seed) {
        return FloorGenerator.generate(FloorGeneratorTest.params(f), seed);
    }

    static HazardPlan hazards(FloorDef f, FloorLayout l, long seed) {
        return HazardPlan.plan(l, f.raw().sub("traps"), f.raw().sub("chests"), seed);
    }

    static long seed(FloorDef f, int s) { return s * 104_729L + f.number() * 31L; }

    @Test
    void trapPlacementRules() {
        for (FloorDef f : content.floors().values()) {
            Set<TrapType> used = EnumSet.noneOf(TrapType.class);
            for (int sd = 0; sd < SEEDS; sd++) {
                long seed = seed(f, sd);
                FloorLayout l = layout(f, seed);
                HazardPlan h = hazards(f, l, seed);
                String ctx = "floor " + f.number() + " seed " + sd;
                assertFalse(h.traps().isEmpty(), "함정 0개: " + ctx);
                assertTrue(h.trapSettings().types().size() >= 3 && h.trapSettings().types().size() <= 4, "층 함정 종류 3~4: " + ctx);
                Set<Integer> hall = new HashSet<>();
                for (int t : l.hallTiles()) hall.add(t);
                Set<Integer> seen = new HashSet<>();
                TreasurePlan tp = h.treasure();
                for (TrapSpot s : h.traps()) {
                    used.add(s.type());
                    assertTrue(h.trapSettings().types().contains(s.type()), "층 종류 밖: " + ctx);
                    if (s.type().shape() == TrapType.Shape.WALL) {
                        assertEquals(2, s.walls().length, ctx);
                        for (int w : s.walls()) assertFalse(l.open(FloorLayout.unpackX(w), FloorLayout.unpackZ(w)), "발사구는 벽: " + ctx);
                    }
                    if (s.type() == TrapType.PITFALL) {
                        assertEquals(0, s.elevation(), ctx);
                        assertEquals(0, s.tiles().length % 2, ctx);
                    }
                    for (int t : s.tiles()) {
                        int x = FloorLayout.unpackX(t), z = FloorLayout.unpackZ(t);
                        assertTrue(hall.contains(t), "복도 칸 밖: " + ctx);
                        assertEquals(-1, l.region(x, z), "방 안 함정: " + ctx);
                        assertEquals(FloorLayout.FLOOR, l.kind(x, z), ctx);
                        assertTrue(seen.add(t), "함정 겹침: " + ctx);
                        assertTrue(l.distance(l.cellAt(x, z)) >= 2, "시작방 바로 옆 셀: " + ctx);
                        for (TreasurePlan.Chest c : tp.chests()) {
                            assertTrue(Math.max(Math.abs(c.x() - x), Math.abs(c.z() - z)) > 2, "상자 바로 옆 함정: " + ctx);
                        }
                        if (tp.vault() != null) assertFalse(tp.vault().contains(x, z), "금고 안 함정: " + ctx);
                    }
                }
            }
            assertTrue(used.size() >= Math.min(3, content.floors().get(f.number()).raw().sub("traps").strings("types").size()),
                    "floor " + f.number() + " 쓰인 종류 " + used);
        }
    }

    @Test
    void trapsFavourDeadEndsJunctionsAndChests() {
        long trapHot = 0, trapAll = 0, tileHot = 0, tileAll = 0;
        for (FloorDef f : content.floors().values()) {
            for (int sd = 0; sd < 8; sd++) {
                long seed = seed(f, sd);
                FloorLayout l = layout(f, seed);
                HazardPlan h = hazards(f, l, seed);
                for (int t : l.hallTiles()) {
                    tileAll++;
                    if (special(l, FloorLayout.unpackX(t), FloorLayout.unpackZ(t))) tileHot++;
                }
                for (TrapSpot s : h.traps()) {
                    trapAll++;
                    if (special(l, s.x(), s.z())) trapHot++;
                }
            }
        }
        double trapShare = trapHot / (double) trapAll, tileShare = tileHot / (double) tileAll;
        assertTrue(trapShare > tileShare + 0.05, "막다른 길·갈림길 쏠림: 함정 " + trapShare + " vs 복도 " + tileShare);
    }

    private static boolean special(FloorLayout l, int x, int z) {
        int cell = l.cellAt(x, z);
        if (cell < 0) return false;
        int deg = Integer.bitCount(l.plan().exits(cell));
        return deg <= 1 || deg >= 3;
    }

    @Test
    void chestsVaultsAndKeys() {
        int vaults = 0, floors = 0;
        double mimicShallow = 0, mimicDeep = 0;
        int chestShallow = 0, chestDeep = 0;
        for (FloorDef f : content.floors().values()) {
            for (int sd = 0; sd < SEEDS; sd++) {
                long seed = seed(f, sd);
                FloorLayout l = layout(f, seed);
                TreasurePlan t = hazards(f, l, seed).treasure();
                String ctx = "floor " + f.number() + " seed " + sd;
                floors++;
                boolean[] reachOpen = l.reachable(true);
                boolean[] reach = l.reachable(false);
                assertFalse(t.chests().isEmpty(), "상자 0개: " + ctx);
                for (TreasurePlan.Chest c : t.chests()) {
                    assertEquals(FloorLayout.FLOOR, l.kind(c.x(), c.z()), ctx);
                    assertTrue(l.isReachable(reachOpen, c.x(), c.z()), "닿을 수 없는 상자: " + ctx);
                    assertEquals(1, Math.abs(c.dirX()) + Math.abs(c.dirZ()), ctx);
                    switch (c.source()) {
                        case SECRET -> {
                            assertEquals(ChestTier.GOLD, c.tier(), ctx);
                            assertTrue(l.secretRoomAt(c.x(), c.z()) >= 0, ctx);
                        }
                        case VAULT -> {
                            assertEquals(ChestTier.GOLD, c.tier(), ctx);
                            assertNotNull(t.vault(), ctx);
                            assertTrue(t.vault().contains(c.x(), c.z()), ctx);
                        }
                        default -> {
                            FloorLayout.DeadEnd de = l.deadEnds().get(c.ref());
                            assertEquals(de.tipX(), c.x(), ctx);
                            assertEquals(de.tipZ(), c.z(), ctx);
                            assertTrue(de.secret() < 0, ctx);
                            assertTrue(l.isReachable(reach, c.x(), c.z()), "비밀 통로 없이 닿아야: " + ctx);
                        }
                    }
                    if (c.mimic()) {
                        assertTrue(c.source() == TreasurePlan.Source.DEAD_END || c.source() == TreasurePlan.Source.MINOR, ctx);
                        assertTrue(c.tier() != ChestTier.GOLD, "미믹은 금 상자가 아님: " + ctx);
                    }
                    if (f.number() <= 3) { chestShallow++; if (c.mimic()) mimicShallow++; }
                    if (f.number() >= 8) { chestDeep++; if (c.mimic()) mimicDeep++; }
                }
                for (FloorLayout.SecretRoom s : l.secretRooms()) {
                    long golds = t.chests().stream().filter(c -> c.source() == TreasurePlan.Source.SECRET && c.ref() == s.index()).count();
                    assertEquals(1, golds, "비밀방마다 금 상자 1개: " + ctx);
                }
                TreasurePlan.Vault v = t.vault();
                if (v != null) {
                    vaults++;
                    assertTrue(v.chests().size() >= 2 && v.chests().size() <= 3, ctx);
                    assertEquals(FloorLayout.FLOOR, l.kind(v.doorX(), v.doorZ()), ctx);
                    assertTrue(l.isReachable(reach, v.doorX(), v.doorZ()), "금고 문에 닿아야: " + ctx);
                    assertTrue(t.keyFromElite() ^ t.keyChest() >= 0, "열쇠 출처 하나: " + ctx);
                    if (t.keyChest() >= 0) {
                        TreasurePlan.Chest k = t.chests().get(t.keyChest());
                        assertEquals(TreasurePlan.Source.DEAD_END, k.source(), ctx);
                        assertFalse(k.mimic(), ctx);
                        assertTrue(k.tier() != ChestTier.WOOD, "열쇠 상자는 철 이상: " + ctx);
                        assertFalse(v.contains(k.x(), k.z()), ctx);
                    }
                    // 문 줄이 복도를 다 막는다 (가운데 ±1 바닥, ±2 걸을 수 없음)
                    int px = v.dirZ() != 0 ? 1 : 0, pz = v.dirX() != 0 ? 1 : 0;
                    assertFalse(l.walkable(v.doorX() + 2 * px, v.doorZ() + 2 * pz), ctx);
                    assertFalse(l.walkable(v.doorX() - 2 * px, v.doorZ() - 2 * pz), ctx);
                } else {
                    assertEquals(-1, t.keyChest(), ctx);
                }
            }
        }
        assertTrue(vaults >= floors * 0.6, "금고가 대부분의 층에: " + vaults + "/" + floors);
        assertTrue(mimicDeep / chestDeep > mimicShallow / chestShallow, "깊은 층일수록 미믹이 많다");
    }

    @Test
    void sameSeedSamePlan() {
        FloorDef f = content.floor(5);
        FloorLayout l = layout(f, 77);
        HazardPlan a = hazards(f, l, 77), b = hazards(f, l, 77);
        assertEquals(a.traps().size(), b.traps().size());
        for (int i = 0; i < a.traps().size(); i++) {
            assertEquals(a.traps().get(i).type(), b.traps().get(i).type());
            assertEquals(a.traps().get(i).x(), b.traps().get(i).x());
            assertEquals(a.traps().get(i).z(), b.traps().get(i).z());
        }
        assertEquals(a.treasure().chests(), b.treasure().chests());
    }

    @Test
    void goldBehindTrap() {
        TreasurePlan.Chest c = new TreasurePlan.Chest(0, 10, 10, 0, -1, ChestTier.WOOD, TreasurePlan.Source.DEAD_END, false, 0);
        TreasurePlan p = new TreasurePlan(List.of(c), null, -1, false);
        ChestSettings always = new ChestSettings(1, 1, 0, 0, 1.0, 0, false, 0, 0);
        TreasurePlan up = TreasurePlanner.upgradeBehindTraps(p, Set.of(FloorLayout.pack(10, 6)), always, 1);
        assertEquals(ChestTier.GOLD, up.chests().get(0).tier());
        TreasurePlan same = TreasurePlanner.upgradeBehindTraps(p, Set.of(FloorLayout.pack(14, 6)), always, 1);
        assertEquals(ChestTier.WOOD, same.chests().get(0).tier());
    }

    @Test
    void personalLootEachOnce() {
        ChestLedger led = new ChestLedger();
        UUID a = UUID.randomUUID(), b = UUID.randomUUID(), c = UUID.randomUUID();
        assertTrue(led.open(0, a));
        assertFalse(led.open(0, a), "같은 사람은 한 번만");
        assertTrue(led.open(0, b), "다른 파티원은 자기 몫");
        assertFalse(led.allOpened(0, List.of(a, b, c)));
        assertTrue(led.open(0, c));
        assertTrue(led.allOpened(0, List.of(a, b, c)));
        assertFalse(led.has(1, a));
        assertFalse(led.allOpened(1, List.of()));
        assertEquals(3, led.count(0));
    }

    @Test
    void vaultKeyIsFloorBound() {
        String tag = VaultKeys.tag("run7s2", 4);
        assertTrue(VaultKeys.matches(tag, "run7s2", 4));
        assertFalse(VaultKeys.matches(tag, "run7s2", 5), "다른 층 금고는 못 연다");
        assertFalse(VaultKeys.matches(tag, "run8s2", 4), "다른 인스턴스 금고는 못 연다");
        assertFalse(VaultKeys.matches(null, "run7s2", 4));
        assertEquals(4, VaultKeys.floorOf(tag));
        assertEquals(-1, VaultKeys.floorOf("broken"));
        assertNotNull(content.item(VaultKeys.ITEM_ID), "items.yml vault_key");
        assertEquals(kr.labyrinth.content.ItemType.KEY, content.item(VaultKeys.ITEM_ID).type());
        for (ChestTier t : ChestTier.values()) {
            for (int fl = 1; fl <= 10; fl++) assertNotNull(content.lootTable(t.table(fl, 0)), t.table(fl, 0));
        }
    }

    @Test
    void mazeChestEnhanceStonesFollowStoneTiers() {
        // 강화석 등급은 상자 구간(1~3·4~6·7~9·10)이 아니라 config enhance.stones 구간 — 8~9층 상자도 최상급
        for (int fl = 1; fl <= 10; fl++) {
            assertNull(ChestTier.WOOD.enhanceTable(fl), "나무 상자는 강화석 없음");
            String want = null;
            for (EnhanceRules.Stone s : EnhanceRules.Config.DEFAULT.stones()) {
                if (fl <= s.maxFloor()) {
                    want = s.item();
                    break;
                }
            }
            for (ChestTier t : List.of(ChestTier.IRON, ChestTier.GOLD)) {
                String id = t.enhanceTable(fl);
                LootTable et = content.lootTable(id);
                assertNotNull(et, id);
                assertEquals(1, et.rolls(), id + " 는 한 번만 굴린다");
                Set<String> got = new HashSet<>();
                lootItems(et, got);
                assertEquals(Set.of(want), got, fl + "층 " + id);
                if (t == ChestTier.GOLD) assertTrue(et.entries().isEmpty() && !et.guaranteed().isEmpty(), id + " 금 상자는 확정");
                else assertTrue(et.guaranteed().isEmpty() && et.entries().get(0).chance() < 1.0, id + " 철 상자는 확률");
            }
            // 상자 표 자체는 강화석 표를 굴리지 않는다 (rolls 2 에 들어가 두 번 굴리던 문제)
            for (ChestTier t : ChestTier.values()) {
                // 층별 표(실제로 굴리는 것)와 구간 표 둘 다
                for (String tid : Set.of(t.table(fl, 0), t.table(fl, 0, content.lootTables()::containsKey))) {
                    LootTable mt = content.lootTable(tid);
                    List<LootTable.Entry> all = new ArrayList<>(mt.entries());
                    all.addAll(mt.guaranteed());
                    for (LootTable.Entry e : all) {
                        assertFalse(e.kind() == LootTable.Kind.TABLE && e.table().startsWith("enhance_"), mt.id() + " → " + e.table());
                    }
                }
            }
        }
    }

    private static void lootItems(LootTable t, Set<String> out) {
        List<LootTable.Entry> all = new ArrayList<>(t.entries());
        all.addAll(t.guaranteed());
        for (LootTable.Entry e : all) {
            if (e.kind() == LootTable.Kind.ITEM) out.add(e.item());
            else if (e.kind() == LootTable.Kind.ONE_OF) out.addAll(e.oneOf());
            else if (e.kind() == LootTable.Kind.TABLE) lootItems(content.lootTable(e.table()), out);
        }
    }

    @Test
    void mazeChestUsesPerFloorTableUnlessBracketForced() {
        Predicate<String> has = content.lootTables()::containsKey;
        for (ChestTier t : ChestTier.values()) {
            for (int fl = 1; fl <= 10; fl++) {
                // 층별 표가 있으면 그것 — 구간 표는 3개 층이 같이 써서 장비가 없다
                assertEquals("maze_chest_" + t.id() + "_f" + fl, t.table(fl, 0, has));
                // floors.yml chests.bracket 강제면 구간 표
                assertEquals("maze_chest_" + t.id() + "_2", t.table(fl, 2, has));
            }
            // 층별 표가 없는 예전 loot.yml 은 지금처럼 구간 표
            assertEquals("maze_chest_" + t.id() + "_1", t.table(3, 0, id -> false));
            assertEquals("maze_chest_" + t.id() + "_4", t.table(10, 0, id -> !id.contains("_f")));
        }
        // 층별 표는 그 층 장비만 준다 (금 상자 = 그 층 공용 무기)
        for (FloorDef f : content.floors().values()) {
            int bracket = ChestSettings.of(f.raw().sub("chests")).bracket();
            for (ChestTier t : ChestTier.values()) {
                String id = t.table(f.number(), bracket, has);
                Set<String> got = new HashSet<>();
                lootItems(content.lootTable(id), got);
                int gear = 0;
                for (String item : got) {
                    var d = content.item(item);
                    if (!d.isGear()) continue;
                    gear++;
                    assertEquals(f.number(), d.floor(), id + " → " + item);
                }
                // 6·8·9·10층은 공용 무기가 대장간 전용이라(영웅 이상 무기 획득처 1곳) 몹·상자 장비 묶음이 없다
                if (content.lootTable(String.format("gear_f%02d_common", f.number())) != null) assertTrue(gear > 0, id + " 에 장비가 없음");
            }
        }
    }

    @Test
    void validatorRequiresTheChestTableTreasuresRolls() {
        // 층별 표를 지워도 구간 표가 있으면 오류 아님, 둘 다 없으면 오류
        Map<String, LootTable> tables = new java.util.HashMap<>(content.lootTables());
        tables.remove("maze_chest_gold_f3");
        assertTrue(kr.labyrinth.core.ContentValidator.validate(withTables(tables)).errors().stream().noneMatch(e -> e.contains("미로 상자")));
        tables.remove("maze_chest_gold_1");
        List<String> errors = kr.labyrinth.core.ContentValidator.validate(withTables(tables)).errors();
        assertTrue(errors.stream().anyMatch(e -> e.startsWith("floors.3 미로 상자") && e.contains("maze_chest_gold_1")), errors.toString());
    }

    static Content withTables(Map<String, LootTable> tables) {
        Content c = content;
        return new Content(c.classes(), c.items(), c.sets(), c.mobs(), c.bosses(), c.floors(), Map.copyOf(tables), c.lootSettings(),
                c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(), c.glyphs(), c.spaces());
    }

    @Test
    void trapMath() {
        assertEquals(60, TrapMath.disarmTicks(false, 3, 1));
        assertEquals(20, TrapMath.disarmTicks(true, 3, 1), "그림자는 1초");
        double f1 = TrapMath.pct(TrapType.SPIKE, 1, 1.0), f10 = TrapMath.pct(TrapType.SPIKE, 10, 1.0);
        assertTrue(f10 > f1, "깊은 층일수록 아프다");
        assertTrue(TrapMath.pct(TrapType.SPIKE, 5, 2.0) > TrapMath.pct(TrapType.SPIKE, 5, 0.6), "난이도 배율");
        assertTrue(TrapMath.pct(TrapType.FALLING_ROCK, 10, 50) <= TrapMath.MAX_PCT);
        assertEquals(0.0, TrapMath.pct(TrapType.ALARM_RUNE, 10, 2.0));
        assertTrue(TrapMath.telegraphTicks(8, 1.3) > TrapMath.telegraphTicks(8, 0.7), "쉬움은 경고가 길다");
        assertEquals(30, TrapMath.disarmGold(5, 6, 1.0));
        // 물살: 들어온 쪽(들어오기 직전 자리)으로 — 기록이 없으면 바라보는 반대쪽
        assertEquals(-1, TrapMath.pushSide(-0.8, 1.0), "−along 쪽에서 들어오면 −along 으로");
        assertEquals(1, TrapMath.pushSide(0.7, -1.0), "+along 쪽에서 들어오면 +along 으로");
        assertEquals(-1, TrapMath.pushSide(-0.7, -1.0), "들어온 자리가 바라보는 방향보다 먼저");
        assertEquals(-1, TrapMath.pushSide(Double.NaN, 0.9), "+along 을 보고 왔으면 −along 에서 온 것");
        assertEquals(1, TrapMath.pushSide(Double.NaN, -0.9));
        assertEquals(1, TrapMath.pushSide(Double.NaN, 0));
        int warm = 0, burst = 0;
        for (int t = 0; t < 70; t++) {
            int b = TrapMath.beat(t, 13, 70, 16, 24);
            if (b == 1) warm++;
            if (b == 2) burst++;
        }
        assertEquals(16, warm);
        assertEquals(24, burst);
    }

    @Test
    void treasureAchievementCondition() {
        Params c = Params.of(Map.of("kind", "vault", "count", 1));
        assertFalse(AchievementRules.met("x", "TREASURE", c, k -> 0));
        assertTrue(AchievementRules.met("x", "TREASURE", c, k -> k.equals("titles.treasure.vault") ? 1 : 0));
        Params chest = Params.of(Map.of("kind", "chest", "count", 40));
        assertFalse(AchievementRules.met("x", "TREASURE", chest, k -> 39));
        assertTrue(AchievementRules.met("x", "TREASURE", chest, k -> 40));
        List<String> ids = new ArrayList<>();
        content.achievements().values().forEach(a -> { if ("TREASURE".equals(a.conditionType())) ids.add(a.id()); });
        assertTrue(ids.size() >= 1 && ids.size() <= 3, "보물 칭호 1~3개: " + ids);
    }
}
