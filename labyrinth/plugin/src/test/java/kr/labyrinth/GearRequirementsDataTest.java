package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.items.loot.LootRoller;
import kr.labyrinth.stats.Stat;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 장비 착용 요구 능력치 (0.3.5, gear_spec §2 — items.yml {@code requires} 만, '모두 채움'). 무기·방어구·방패 모두
 * 합 = T(L) = ceil(2.75 × (L − 1)), L ≤ 2 면 없음, 능력치 2~3개 60 : 40 · 50 : 30 : 20 (셋은 L ≥ 12). 물리 무기는 STR·DEX,
 * 마법 무기는 INT·WIS 가 하나 이상. 획득처 종류 1개인 영웅 이상 무기 · 보스 고유 무기 처치당 확률(own_build_bias) ·
 * 직업마다 띠마다 세금 ≤ 15% 한 벌 (g2_check 와 같은 계산, {@link GearModel}).
 * 방어구 겉모습별 규칙(앞 능력치 = 겉모습 능력치)은 {@code items.ArmorRequirementsDataTest}.
 */
class GearRequirementsDataTest {

    static Content content;
    static int startPoints;
    static int pointsPerLevel;
    static List<String> starterKit = new ArrayList<>();

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        YamlConfiguration cfg = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        startPoints = cfg.getInt("level.start_points", 5);
        pointsPerLevel = cfg.getInt("level.points_per_level", 5);
        for (Map<?, ?> m : cfg.getMapList("starter_kit.items")) starterKit.add(String.valueOf(m.get("item")));
    }

    static boolean gear(ItemDef d) { return d.isWeapon() || d.type() == ItemType.ARMOR; }

    // ── 요구 능력치 ─────────────────────────────────────────────

    @Test
    void noRequiresAnyAnywhere() {
        for (ItemDef d : content.items().values()) {
            assertFalse(d.raw() != null && d.raw().has("requires_any"), d.id() + " 에 requires_any (0.3.5 에서 없어짐)");
            Params p = d.raw() == null ? Params.EMPTY : d.raw().sub("requires");
            for (String k : p.keys()) assertNotNull(Stat.byKey(k), d.id() + " 모르는 능력치 " + k);
        }
    }

    @Test
    void everyGearRequirementFollowsTheRule() {
        int with = 0;
        for (ItemDef d : content.items().values()) {
            StatRequirement r = d.requirement();
            if (!gear(d)) {
                assertTrue(r.isEmpty(), d.id() + " (" + d.type() + ") 에는 요구 능력치가 없다");
                continue;
            }
            int t = StatRequirement.budget(d.levelReq());
            if (t == 0) {
                assertTrue(r.isEmpty(), d.id() + " Lv" + d.levelReq() + " 은 요구 없음");
                continue;
            }
            with++;
            int n = r.all().size();
            assertTrue(n >= 2 && n <= 3, d.id() + " 요구 능력치 " + n + "개 " + r.all());
            if (n == 3) assertTrue(d.levelReq() >= 12, d.id() + " 세 능력치는 Lv12 부터 (Lv" + d.levelReq() + ")");
            assertEquals(t, r.total(), d.id() + " 요구 합 (Lv" + d.levelReq() + ")");
            assertTrue(ContentValidator.splitOk(r, t), d.id() + " 나눔이 60/40 · 50/30/20 이 아님 " + r.all());
            if (d.isWeapon()) {
                Set<Stat> dmg = d.attack().kind() == DamageKind.MAGIC ? Set.of(Stat.INT, Stat.WIS) : Set.of(Stat.STR, Stat.DEX);
                assertTrue(r.all().keySet().stream().anyMatch(dmg::contains), d.id() + " " + d.attack().kind() + " 무기인데 요구 " + r.all());
            }
        }
        assertTrue(with >= 330, "요구 능력치가 붙은 장비 " + with);
    }

    @Test
    void damageStatlessWeaponsAreFewPerBand() {
        // 피해 능력치(물리 STR · 마법 INT)를 요구하지 않는 무기 — 띠 3~10 에서 띠마다 3개 이하 (1·2 띠는 요구 합 ≤ 25 라 제외)
        Map<Integer, List<String>> byBand = new TreeMap<>();
        for (ItemDef d : content.items().values()) {
            if (!d.isWeapon() || d.requirement().isEmpty()) continue;
            Stat dmg = d.attack().kind() == DamageKind.MAGIC ? Stat.INT : Stat.STR;
            if (!d.requirement().all().containsKey(dmg)) byBand.computeIfAbsent(GearModel.band(d.levelReq()), k -> new ArrayList<>()).add(d.id());
        }
        for (var e : byBand.entrySet()) {
            if (e.getKey() >= 3) assertTrue(e.getValue().size() <= 3, "띠 " + e.getKey() + " 피해 능력치 없는 무기 " + e.getValue());
        }
    }

    @Test
    void setPiecesShareTheirRequirementAndNoviceIsFree() {
        Map<String, StatRequirement> sets = new TreeMap<>();
        for (ItemDef d : content.items().values()) {
            if (d.type() != ItemType.ARMOR || d.isShield() || d.setBonus() == null) continue;
            StatRequirement prev = sets.putIfAbsent(d.setBonus(), d.requirement());
            if (prev != null) assertEquals(prev, d.requirement(), d.id() + " 세트 " + d.setBonus() + " 네 부위 요구가 다름");
        }
        assertTrue(sets.size() >= 25, "세트 " + sets.size());
        assertTrue(sets.get("novice").isEmpty(), "시작 지급(novice)은 요구 없음");
        for (String id : starterKit) {
            ItemDef d = content.item(id);
            if (d != null) assertTrue(d.requirement().isEmpty(), "시작 꾸러미 " + id + " 에 요구 " + d.requirement().all());
        }
    }

    @Test
    void starterWeaponsFree() {
        assertEquals(6, content.classes().size());
        for (ClassDef c : content.classes().values()) {
            ItemDef w = content.item(c.starterWeapon());
            assertNotNull(w, c.id() + " starter_weapon " + c.starterWeapon());
            assertTrue(w.requirement().isEmpty(), c.id() + " 시작 무기 " + w.id() + " 요구 " + w.requirement().all());
            assertEquals(1, w.levelReq(), w.id());
        }
    }

    // ── 획득처 ─────────────────────────────────────────────

    static String kind(String tag) { return tag.equals("drop") || tag.equals("chest") ? "common" : tag; }

    static boolean top(ItemDef d) { return d.isWeapon() && d.rarity().atLeast(Rarity.EPIC); }

    @Test
    void topWeaponsHaveExactlyOneSourceKind() {
        Set<String> recipeResults = new HashSet<>();
        for (RecipeDef r : content.recipes().values()) recipeResults.add(r.result());
        Map<String, Integer> byKind = new TreeMap<>();
        for (ItemDef d : content.items().values()) {
            if (!top(d)) continue;
            Set<String> kinds = new TreeSet<>();
            for (String s : d.sources()) kinds.add(kind(s));
            assertEquals(1, kinds.size(), d.id() + " (" + d.rarity().id() + ") 획득처 종류 " + kinds);
            byKind.merge(kinds.iterator().next(), 1, Integer::sum);
            if (d.sources().contains("boss")) assertFalse(recipeResults.contains(d.id()), d.id() + " 보스 고유 무기에 제작법");
            if (d.sources().contains("craft")) assertEquals(List.of("craft"), d.sources(), d.id() + " 대장간 무기가 드롭에도 있음");
        }
        // gear_spec §12 (보스 32 · 대장간 36 · 몬스터·상자 21 · 금고·미믹 16 · 특별 시련 15 · 시련방 11 · 정예 10)
        // + B2 영웅 7 (시련방 2 · 정예 3 · 금고·미믹 1 · 특별 시련 1) + 31~35 영웅 올림 8 (금고·미믹 2 · 특별 시련 2 · 시련방 2 · 정예 2)
        assertEquals(Map.of("boss", 32, "craft", 36, "common", 21, "hoard", 19, "special", 18, "trial", 15, "elite", 15), byKind,
                "영웅 이상 무기 획득처 종류별 수");
    }

    @Test
    void bossUniqueWeaponsDropOftenEnough() {
        // 보통·솔로·LUK 0 에서 처치 1번당 '그 무기 요구에 맞춘 빌드'(능력치 상위 2개 = 그 무기 요구 위 두 능력치) 확률
        // = chance × (편향 ÷ 빌드에 맞는 후보 수 + (1 − 편향) ÷ 묶음 수) — LootRoller.pick 과 같은 규칙. 제작으로 메울 수 없으니
        // 영웅 30% 이상 · 전설 15% 이상 · 55% 이하 (신화는 어려움 이상 10층 전용 — 따로)
        double bias = content.lootSettings().ownBuildBias();
        assertEquals(0.65, bias, 1e-9);
        int checked = 0;
        for (BossDef b : content.bosses().values()) {
            LootTable t = content.lootTable(b.drops());
            List<LootTable.Entry> all = new ArrayList<>(t.entries());
            all.addAll(t.guaranteed());
            for (LootTable.Entry e : all) {
                List<String> ids = e.kind() == LootTable.Kind.ONE_OF ? e.oneOf() : e.kind() == LootTable.Kind.ITEM ? List.of(e.item()) : List.of();
                double chance = t.guaranteed().contains(e) ? 1.0 : e.chance();
                for (String id : ids) {
                    ItemDef d = content.item(id);
                    if (d == null || !top(d) || d.rarity() == Rarity.MYTHIC) continue;
                    List<Stat> build = new ArrayList<>();
                    for (var r : d.requirement().ordered()) if (build.size() < LootRoller.BUILD_TOP) build.add(r.getKey());
                    double own;
                    if (ids.size() == 1) own = chance;
                    else {
                        int fit = 0;
                        for (String o : ids) if (LootRoller.fitsBuild(content.item(o), build)) fit++;
                        own = chance * (bias / fit + (1 - bias) / ids.size());
                    }
                    double min = d.rarity() == Rarity.EPIC ? 0.30 : 0.15;
                    assertTrue(own >= min, d.id() + " 처치당 내 빌드 확률 " + own);
                    // 2·3층 영웅 셋 묶음은 둘이 주 능력치를 나눠 써서 묶음 확률을 0.68 로 올렸다 — 혼자인 하나가 0.52
                    assertTrue(own <= 0.55, d.id() + " 너무 흔함 " + own);
                    checked++;
                }
            }
        }
        assertEquals(26, checked, "영웅·전설 보스 고유 무기 수");
    }

    // ── 직업마다 끼는 한 벌 ─────────────────────────────────────

    @Test
    void bandOneEarly() {
        // Lv3 (포인트 15) 에 직업마다 띠 1 무기 3개 이상 + 길손(wayfarer) 한 벌을 함께 낀다
        int lv = 3, pts = startPoints + pointsPerLevel * (lv - 1);
        assertEquals(15, pts);
        Map<Stat, Integer> wayfarer = null;
        for (ItemDef d : content.items().values()) if ("wayfarer".equals(d.setBonus()) && d.type() == ItemType.ARMOR) wayfarer = d.requirement().all();
        assertNotNull(wayfarer, "wayfarer 세트");
        for (ClassDef c : content.classes().values()) {
            Map<Stat, Integer> base = GearModel.base(c);
            List<String> ok = new ArrayList<>();
            for (ItemDef w : content.items().values()) {
                if (!w.isWeapon() || w.levelReq() > lv || w.rarity() == Rarity.MYTHIC) continue;
                Map<Stat, Integer> kit = GearModel.kit(List.of(w.requirement().all(), wayfarer));
                int need = 0;
                for (var e : kit.entrySet()) need += Math.max(0, e.getValue() - base.getOrDefault(e.getKey(), 0));
                if (need <= pts) ok.add(w.id());
            }
            assertTrue(ok.size() >= 3, c.id() + " Lv3 무기 + 길손 한 벌 " + ok);
        }
    }

    @Test
    void everyClassHasAKitEveryBand() {
        // 직업마다 띠마다 (포인트 = 5 × 띠 끝 레벨, 칭호 없음) 그 띠 무기(피해 종류 맞음) + 방어구 세트 (+ 수호기사 방패) 를
        // 세금 ≤ 15% 로 끼는 무기가 3개 이상
        List<String> short_ = new ArrayList<>();
        for (int b = 1; b <= 10; b++) {
            for (String c : GearModel.CLASSES) {
                List<String> good = GearModel.goodWeapons(content, c, b, false);
                if (good.size() < 3) short_.add(c + "|" + b + " " + good);
            }
        }
        assertTrue(short_.isEmpty(), "알맞은 한 벌이 3개 미만: " + short_);
    }

    @Test
    void noOrphanWeapon() {
        // 모든 무기는 직업 기본 분배 또는 다른 빌드 5종(치명·마검사·전투 사제·민첩 시전·방벽 시전) 중 하나로 자기 레벨 + 2 에서 세금 ≤ 15%
        List<String> orphans = new ArrayList<>();
        for (ItemDef w : content.items().values()) {
            if (!w.isWeapon() || w.requirement().isEmpty()) continue;
            int p = w.levelReq() + 2;
            boolean ok = false;
            for (ClassDef c : content.classes().values()) {
                Map<Stat, Integer> base = GearModel.base(c);
                List<Map<Stat, Double>> ratios = new ArrayList<>(List.of(GearModel.SPREAD.get(c.id())));
                ratios.addAll(GearModel.ARCH.values());
                for (Map<Stat, Double> ratio : ratios) {
                    GearModel.Tax t = GearModel.tax(base, ratio, p, w.requirement().all());
                    if (t.feasible() && t.extra() / GearModel.pointsAt(p) <= GearModel.TAX_OK + 1e-9) ok = true;
                }
            }
            if (!ok) orphans.add(w.id());
        }
        assertTrue(orphans.isEmpty(), "어떤 빌드로도 알맞게 못 끼는 무기 " + orphans);
    }
}
