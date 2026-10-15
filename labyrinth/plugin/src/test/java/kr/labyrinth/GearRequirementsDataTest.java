package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.dungeon.treasure.ChestTier;
import kr.labyrinth.stats.Stat;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 장비 데이터 — 착용 요구 능력치(items.yml {@code requires} · {@code requires_any})와 영웅 이상 무기 획득처 1곳.
 * 요구 능력치 = ceil(2.5 × (숨은 아이템 레벨 − 1)), 2 이하면 없음. 능력치는 무기 종류 / 방어구 겉모습으로 정한다
 * (판금·방패 VIT · 가죽 DEX · 천 INT 또는 WIS · 모든 직업용은 주 능력치 하나). '내 능력치' = 직업 기본 + 분배 포인트 (+ 칭호).
 * 파서가 아직 요구 능력치를 따로 읽지 않아도 되게 {@link ItemDef#raw()} 에서 직접 읽는다.
 */
class GearRequirementsDataTest {

    static Content content;
    static int startPoints;
    static int pointsPerLevel;
    static List<String> starterKit = new ArrayList<>();

    static final List<String> MAIN = List.of("STR", "DEX", "INT", "VIT", "WIS");
    static final Map<String, String> WEAPON_STAT = Map.of("greatsword", "STR", "sword_shield", "STR", "bow", "DEX",
            "dagger", "DEX", "staff", "INT", "scepter", "WIS");
    /** 겉모습: 세트는 흉갑 모양, 단품 투구는 투구 모양. */
    static final Map<String, String> LOOK = Map.ofEntries(Map.entry("chestplate", "heavy"), Map.entry("leather_vest", "light"),
            Map.entry("robe_top", "cloth"), Map.entry("helm_knight", "heavy"), Map.entry("helm_horned", "heavy"),
            Map.entry("helm_winged", "heavy"), Map.entry("hood", "light"), Map.entry("half_mask", "light"),
            Map.entry("circlet", "cloth"), Map.entry("crown", "cloth"), Map.entry("wizard_hat", "cloth"));
    static final Map<String, Set<String>> LOOK_CLASSES = Map.of("heavy", Set.of("guardian", "berserker"),
            "light", Set.of("hunter", "shadow"), "cloth", Set.of("arcanist", "priest"));

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        YamlConfiguration cfg = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        startPoints = cfg.getInt("level.start_points", 5);
        pointsPerLevel = cfg.getInt("level.points_per_level", 5);
        for (Map<?, ?> m : cfg.getMapList("starter_kit.items")) starterKit.add(String.valueOf(m.get("item")));
    }

    // ── 요구 능력치 ─────────────────────────────────────────────

    static Map<String, Integer> read(ItemDef d, String key) {
        Map<String, Integer> out = new LinkedHashMap<>();
        Params p = d.raw().sub(key);
        for (String k : p.keys()) out.put(k, p.integer(k, 0));
        return out;
    }

    static int value(int level) {
        int r = (int) Math.ceil(2.5 * (level - 1));
        return r > 2 ? r : 0;
    }

    static String look(ItemDef d) {
        if (d.isShield()) return "shield";
        if (d.armorSet() != null) {
            for (ItemDef o : content.items().values()) {
                if (d.armorSet().equals(o.armorSet()) && "chest".equals(o.armorSlot())) return LOOK.get(o.model().str("shape"));
            }
        }
        return LOOK.get(d.model().str("shape"));
    }

    /** 규칙대로라면 → [requires, requires_any]. */
    static List<Map<String, Integer>> expected(ItemDef d) {
        Map<String, Integer> all = new LinkedHashMap<>(), any = new LinkedHashMap<>();
        int r = value(d.levelReq());
        if (r > 0) {
            if (d.isWeapon()) all.put(WEAPON_STAT.get(d.weaponType()), r);
            else if (d.classes().isEmpty()) for (String s : MAIN) any.put(s, r);
            else switch (look(d)) {
                case "heavy", "shield" -> all.put("VIT", r);
                case "light" -> all.put("DEX", r);
                default -> { any.put("INT", r); any.put("WIS", r); }
            }
        }
        return List.of(all, any);
    }

    @Test
    void everyGearRequirementFollowsTheRule() {
        int with = 0;
        for (ItemDef d : content.items().values()) {
            Map<String, Integer> all = read(d, "requires"), any = read(d, "requires_any");
            for (String k : all.keySet()) assertNotNull(Stat.byKey(k), d.id() + " 모르는 능력치 " + k);
            for (String k : any.keySet()) assertNotNull(Stat.byKey(k), d.id() + " 모르는 능력치 " + k);
            boolean gear = d.isWeapon() || d.type() == ItemType.ARMOR;
            if (!gear) {
                assertTrue(all.isEmpty() && any.isEmpty(), d.id() + " (" + d.type() + ") 에는 요구 능력치가 없다");
                continue;
            }
            assertEquals(expected(d), List.of(all, any), d.id() + " 요구 능력치 (아이템 레벨 " + d.levelReq() + ")");
            if (!all.isEmpty() || !any.isEmpty()) with++;
            if (!d.isWeapon() && !d.isShield() && !d.classes().isEmpty()) {
                assertTrue(LOOK_CLASSES.get(look(d)).containsAll(d.classes()), d.id() + " 겉모습 " + look(d) + " 인데 classes " + d.classes());
            }
        }
        assertTrue(with >= 200, "요구 능력치가 붙은 장비 " + with);
    }

    /** 그 장비를 끼려고 직업 기본 능력치 위에 더 찍어야 하는 포인트. */
    static int pointsFor(ClassDef c, Map<String, Integer> need, List<Map<String, Integer>> anyOf) {
        Map<String, Integer> target = new HashMap<>(need);
        for (Map<String, Integer> any : anyOf) {
            if (any.isEmpty()) continue;
            boolean met = any.entrySet().stream().anyMatch(e -> Math.max(target.getOrDefault(e.getKey(), 0), base(c, e.getKey())) >= e.getValue());
            if (met) continue;
            String cheapest = any.keySet().stream().min((a, b) -> Integer.compare(
                    any.get(a) - Math.max(target.getOrDefault(a, 0), base(c, a)), any.get(b) - Math.max(target.getOrDefault(b, 0), base(c, b)))).orElseThrow();
            target.merge(cheapest, any.get(cheapest), Math::max);
        }
        int pts = 0;
        for (var e : target.entrySet()) pts += Math.max(0, e.getValue() - base(c, e.getKey()));
        return pts;
    }

    static int base(ClassDef c, String stat) { return c.baseStat(Stat.byKey(stat)); }

    static int pointsFor(ClassDef c, ItemDef d) { return pointsFor(c, read(d, "requires"), List.of(read(d, "requires_any"))); }

    @Test
    void everyClassWearsItsStarterGearFreeAndFloorOneGearWithStartPoints() {
        for (ClassDef c : content.classes().values()) {
            String wt = c.weaponTypes().get(0);
            ItemDef starter = content.items().values().stream().filter(d -> d.isWeapon() && wt.equals(d.weaponType()))
                    .min((a, b) -> a.floor() != b.floor() ? Integer.compare(a.floor(), b.floor()) : Integer.compare(a.levelReq(), b.levelReq())).orElseThrow();
            assertEquals(0, pointsFor(c, starter), c.id() + " 시작 무기 " + starter.id());
            for (String id : starterKit) {
                ItemDef d = content.item(id);
                if (d != null && d.isGear()) assertEquals(0, pointsFor(c, d), c.id() + " 시작 꾸러미 " + id);
            }
            int f1 = 0;
            for (ItemDef d : content.items().values()) {
                if (!(d.isWeapon() || d.type() == ItemType.ARMOR) || d.floor() != 1 || !d.suitedFor(c.id())) continue;
                f1++;
                assertTrue(pointsFor(c, d) <= startPoints, c.id() + " Lv.1 에서 1층 " + d.id() + " 에 포인트 " + pointsFor(c, d) + " > " + startPoints);
            }
            assertTrue(f1 >= 10, c.id() + " 1층 장비 " + f1);
        }
    }

    @Test
    void ownFloorKitFitsTheStatPointsAtItsLevel() {
        // 그 층 내 무기(가장 높은 것) + 내 겉모습 방어구 부위별 가장 높은 것 (+ 수호기사 방패) — 그 장비 레벨에서 받은 포인트로 다 낄 수 있다
        for (ClassDef c : content.classes().values()) {
            for (int f = 1; f <= content.maxFloor(); f++) {
                Map<String, ItemDef> best = new HashMap<>();
                for (ItemDef d : content.items().values()) {
                    if (d.floor() != f) continue;
                    String slot = null;
                    if (d.isWeapon() && c.recommendsWeapon(d.weaponType())) slot = "weapon";
                    else if (d.isShield() && c.id().equals("guardian")) slot = "offhand";
                    else if (!d.isWeapon() && !d.isShield() && d.type() == ItemType.ARMOR && !d.classes().isEmpty() && d.classes().contains(c.id())) slot = d.armorSlot();
                    if (slot == null) continue;
                    best.merge(slot, d, (a, b) -> a.levelReq() >= b.levelReq() ? a : b);
                }
                Map<String, Integer> need = new HashMap<>();
                List<Map<String, Integer>> any = new ArrayList<>();
                int level = 1;
                for (ItemDef d : best.values()) {
                    read(d, "requires").forEach((k, v) -> need.merge(k, v, Math::max));
                    any.add(read(d, "requires_any"));
                    level = Math.max(level, d.levelReq());
                }
                int pts = pointsFor(c, need, any), have = startPoints + pointsPerLevel * (level - 1);
                assertTrue(pts <= have, c.id() + " " + f + "층 한 벌 " + best.keySet() + " Lv" + level + ": 포인트 " + pts + " > " + have);
            }
        }
    }

    // ── 영웅 이상 무기 획득처 1곳 ─────────────────────────────────

    private static Set<String> expand(String tableId, Set<String> seen) {
        Set<String> out = new HashSet<>();
        LootTable t = content.lootTable(tableId);
        if (t == null || !seen.add(tableId)) return out;
        List<LootTable.Entry> all = new ArrayList<>(t.entries());
        all.addAll(t.guaranteed());
        for (LootTable.Entry e : all) {
            switch (e.kind()) {
                case ITEM -> out.add(e.item());
                case ONE_OF -> out.addAll(e.oneOf());
                case TABLE -> out.addAll(expand(e.table(), new HashSet<>(seen)));
                case RARITY_POOL -> { }
            }
        }
        return out;
    }

    /** 장비 → 집 (common = 몬스터·상자 · elite · boss · craft · reward · shop). */
    static Map<String, Set<String>> homes() {
        Map<String, Set<String>> h = new HashMap<>();
        Map<String, String> tables = new LinkedHashMap<>();
        for (MobDef m : content.mobs().values()) if (m.drops() != null) tables.put(m.drops(), m.isElite() ? "elite" : "common");
        for (BossDef b : content.bosses().values()) tables.put(b.drops(), "boss");
        for (int f = 1; f <= content.maxFloor(); f++) {
            tables.put("treasure_floor_" + f, "common");
            tables.put("gimmick_floor_" + f, "common");
            for (ChestTier t : ChestTier.values()) tables.put("maze_chest_" + t.id() + "_f" + f, "common");
        }
        tables.forEach((t, home) -> {
            for (String id : expand(t, new HashSet<>())) h.computeIfAbsent(id, k -> new TreeSet<>()).add(home);
        });
        for (RecipeDef r : content.recipes().values()) h.computeIfAbsent(r.result(), k -> new TreeSet<>()).add("craft");
        content.achievements().values().forEach(a -> a.rewardItems().keySet().forEach(id -> h.computeIfAbsent(id, k -> new TreeSet<>()).add("reward")));
        content.npcs().values().forEach(n -> n.shop().forEach(s -> h.computeIfAbsent(s.item(), k -> new TreeSet<>()).add("shop")));
        return h;
    }

    static boolean top(ItemDef d) { return d.isWeapon() && d.rarity().ordinal() >= Rarity.EPIC.ordinal(); }

    @Test
    void topWeaponsHaveExactlyOneHome() {
        Map<String, Set<String>> h = homes();
        Map<String, Integer> byHome = new TreeMap<>();
        Set<String> recipeResults = new HashSet<>();
        for (RecipeDef r : content.recipes().values()) recipeResults.add(r.result());
        for (ItemDef d : content.items().values()) {
            if (!top(d)) continue;
            Set<String> got = h.getOrDefault(d.id(), Set.of());
            assertEquals(1, got.size(), d.id() + " (" + d.rarity().id() + ") 획득처 " + got);
            byHome.merge(got.iterator().next(), 1, Integer::sum);
            if (d.sources().contains("boss")) {
                assertEquals(List.of("boss"), d.sources(), d.id());
                assertFalse(recipeResults.contains(d.id()), d.id() + " 보스 고유 무기에 제작법");
            }
            if (d.sources().contains("craft")) assertEquals(List.of("craft"), d.sources(), d.id() + " 대장간 무기가 드롭에도 있음");
        }
        // 보스 고유(2~10층 전설·영웅 + 신화) · 대장간(4·5·6·8·9·10층) · 5층 몬스터·상자
        assertEquals(Map.of("boss", 32, "craft", 36, "common", 6), byHome, "영웅 이상 무기 집별 수");
    }

    @Test
    void bossUniqueWeaponsDropOftenEnoughWithoutACraftFallback() {
        // 보통·솔로·LUK 0 에서 처치 1번당 '내 직업' 고유 무기 확률 = chance × (편향 + (1 − 편향) / 묶음 수) — 제작으로 메울 수 없으니
        // 영웅 30% 이상 · 전설 15% 이상 (신화는 어려움 이상 10층 전용 — 따로)
        double bias = content.lootSettings().ownClassBias();
        int checked = 0;
        for (BossDef b : content.bosses().values()) {
            for (LootTable.Entry e : content.lootTable(b.drops()).entries()) {
                List<String> ids = e.kind() == LootTable.Kind.ONE_OF ? e.oneOf() : e.kind() == LootTable.Kind.ITEM ? List.of(e.item()) : List.of();
                for (String id : ids) {
                    ItemDef d = content.item(id);
                    if (d == null || !top(d) || d.rarity() == Rarity.MYTHIC) continue;
                    double own = e.chance() * (ids.size() > 1 ? bias + (1 - bias) / ids.size() : 1.0);
                    double min = d.rarity() == Rarity.EPIC ? 0.30 : 0.15;
                    assertTrue(own >= min, d.id() + " 처치당 내 직업 확률 " + own);
                    assertTrue(own <= 0.5, d.id() + " 너무 흔함 " + own);
                    checked++;
                }
            }
        }
        assertEquals(26, checked, "영웅·전설 보스 고유 무기 수");
    }
}
