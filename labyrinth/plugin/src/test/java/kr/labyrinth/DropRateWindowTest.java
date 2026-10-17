package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.IntRange;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.loot.LootRoller;
import kr.labyrinth.stats.Stat;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 장비 기대 회차 (gear_spec §12 DropRateWindow — 순수 계산, 설계 g2_loot 와 같은 식). 보통 · 솔로 · LUK 0 · 층 끝까지 1회:
 * 몹 수(층마다) · 미로 상자 1~3층 나무 3.3 · 철 1.3 · 금 0.6 · 비밀 1.0 / 4~10층 4.4 · 2.3 · 1.2 · 2.0 · 금고 금 상자 2.25 ·
 * 길들인 미믹 (나무 + 철) × 미믹 비율 · 보물방 상자 2.7 × 방 수 · 시련방 성공 0.8 · 특별 시련 0.395(확정 규칙 포함) × 조건 0.65 ·
 * 정예 1 (9·10층 2).
 * '그 무기 요구에 맞춘 빌드'(능력치 상위 2개 = 그 무기 요구 위 두 능력치)가 자기 단계 층을 돌 때 얻기까지 기대 회차 = 1 ÷ (1회 확률).
 */
class DropRateWindowTest {

    static Content content;
    static JsonObject gearPerRun;

    static final Map<Integer, Integer> MOBS_RUN = Map.of(1, 24, 2, 28, 3, 28, 4, 36, 5, 40, 6, 45, 7, 45, 8, 55, 9, 55, 10, 60);
    static final double[] MIMIC = {0, 0.04, 0.055, 0.07, 0.085, 0.10, 0.115, 0.13, 0.145, 0.16, 0.175};
    static final double TREASURE_CHESTS = 2.7, GIMMICK_OK = 0.8, VAULT = 2.25;
    static final double SPECIAL_Q = 0.30 / (1 - Math.pow(0.70, 4)), SPECIAL_C = 0.65;
    static final double BIAS = 0.65;

    @BeforeAll
    static void load() throws IOException {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        gearPerRun = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/gear_spec.json"), StandardCharsets.UTF_8))
                .getAsJsonObject().getAsJsonObject("gear_per_run");
    }

    // ── 1회 돌기 ─────────────────────────────────────────────

    static int elites(int f) { return f >= 9 ? 2 : 1; }

    /** 미로 상자 수: wood, iron, gold(금 + 비밀 + 금고), mimic(길들인 미믹). */
    static double[] maze(int f) {
        double wood = f <= 3 ? 3.3 : 4.4, iron = f <= 3 ? 1.3 : 2.3, gold = f <= 3 ? 0.6 : 1.2, secret = f <= 3 ? 1.0 : 2.0;
        return new double[] {wood, iron, gold + secret + VAULT, (wood + iron) * MIMIC[f]};
    }

    record Src(String table, double n) {}

    static List<String> mobTables(int f, boolean elite) {
        List<String> out = new ArrayList<>();
        for (MobDef m : content.mobs().values()) {
            if (m.floor() == f && m.drops() != null && m.isElite() == elite) out.add(m.drops());
        }
        return out;
    }

    static List<Src> runSources(int f, boolean extra) {
        List<Src> out = new ArrayList<>();
        List<String> normal = mobTables(f, false), elite = mobTables(f, true);
        for (String t : normal) out.add(new Src(t, (double) MOBS_RUN.get(f) / normal.size()));
        for (String t : elite) out.add(new Src(t, (double) elites(f) / elite.size()));
        out.add(new Src(content.bossOfFloor(f).drops(), 1.0));
        FloorDef fd = content.floor(f);
        out.add(new Src("treasure_floor_" + f, fd.rooms().getOrDefault("treasure", 1) * TREASURE_CHESTS));
        out.add(new Src("gimmick_floor_" + f, GIMMICK_OK));
        double[] c = maze(f);
        out.add(new Src("maze_chest_wood_f" + f, c[0]));
        out.add(new Src("maze_chest_iron_f" + f, c[1]));
        out.add(new Src("maze_chest_gold_f" + f, c[2]));
        if (extra) {
            out.add(new Src(String.format("hoard_f%02d", f), VAULT + c[3]));
            out.add(new Src(String.format("special_trial_f%02d", f), SPECIAL_Q * SPECIAL_C));
        }
        return out;
    }

    static int rolls(LootTable t) { return Math.max(1, t.rolls()); }

    /** 1회에 표 tid 를 곧바로 굴리는 기대 횟수. */
    static double rollsInto(String tid, int f) {
        double tot = 0;
        for (Src s : runSources(f, false)) {
            LootTable t = content.lootTable(s.table());
            if (t == null) continue;
            for (LootTable.Entry e : t.entries()) {
                if (e.kind() == LootTable.Kind.TABLE && e.table().equals(tid)) tot += s.n() * rolls(t) * Math.min(1, e.chance());
            }
        }
        return tot;
    }

    static double frac(LootTable.Entry pick, int tier) {
        double w = 0;
        for (LootTable.Pick p : pick.pick()) if (p.table().startsWith(String.format("band_t%02d_", tier))) w += p.weight();
        return w / pick.pickWeight();
    }

    static LootTable.Entry pickEntry(List<LootTable.Entry> es) {
        for (LootTable.Entry e : es) if (e.kind() == LootTable.Kind.PICK) return e;
        return null;
    }

    /** one_of 에서 target 이 나올 확률 — 줍는 사람 상위 2개 = target 요구 위 두 능력치 (LootRoller.pick 과 같은 규칙). */
    static double pickP(String target, List<String> pool) {
        List<Stat> top = new ArrayList<>();
        for (var e : content.item(target).requirement().ordered()) if (top.size() < LootRoller.BUILD_TOP) top.add(e.getKey());
        int n = pool.size();
        if (top.isEmpty()) return 1.0 / n;
        int fit = 0;
        for (String x : pool) if (LootRoller.fitsBuild(content.item(x), top)) fit++;
        return fit == 0 ? 1.0 / n : BIAS / fit + (1 - BIAS) / n;
    }

    /** 단계 풀 표 한 번 굴릴 때 그 무기가 나올 확률. */
    static double bandP(String wid, String pid) {
        LootTable t = content.lootTable(pid);
        assertNotNull(t, pid);
        double p = 0;
        for (LootTable.Entry e : t.entries()) {
            if (e.kind() == LootTable.Kind.ONE_OF && e.oneOf().contains(wid)) p += Math.min(1, e.chance()) * pickP(wid, e.oneOf());
            if (e.kind() == LootTable.Kind.ITEM && e.item().equals(wid)) p += Math.min(1, e.chance());
        }
        for (LootTable.Entry e : t.guaranteed()) if (e.kind() == LootTable.Kind.ONE_OF && e.oneOf().contains(wid)) p += pickP(wid, e.oneOf());
        return p;
    }

    /** 자기 단계 층 1회에 그 무기를 얻을 확률 (종류 M 몬스터·상자 · T 시련방 · V 금고·미믹 · S 특별 시련 · E 정예). */
    static double rate(ItemDef w, String kind) {
        int t = w.tier(), f = t;
        switch (kind) {
            case "M" -> {
                String mix = String.format("mix_f%02d_drop", f);
                LootTable.Entry e = pickEntry(content.lootTable(mix).entries());
                return rollsInto(mix, f) * Math.min(1, e.chance()) * frac(e, t) * bandP(w.id(), String.format("band_t%02d_drop", t));
            }
            case "T" -> {
                LootTable g = content.lootTable("gimmick_floor_" + f);
                LootTable.Entry e = pickEntry(g.entries());
                return GIMMICK_OK * rolls(g) * e.chance() * frac(e, t) * bandP(w.id(), String.format("band_t%02d_trial", t));
            }
            case "V" -> {
                LootTable.Entry e = pickEntry(content.lootTable(String.format("hoard_f%02d", f)).entries());
                return (VAULT + maze(f)[3]) * e.chance() * frac(e, t) * bandP(w.id(), String.format("band_t%02d_hoard", t));
            }
            case "S" -> {
                LootTable.Entry e = pickEntry(content.lootTable(String.format("special_trial_f%02d", f)).guaranteed());
                return SPECIAL_Q * SPECIAL_C * frac(e, t) * bandP(w.id(), String.format("band_t%02d_special", t));
            }
            default -> {
                List<String> el = mobTables(f, true);
                double tot = 0;
                for (String tid : el) {
                    LootTable.Entry e = pickEntry(content.lootTable(tid).entries());
                    tot += (double) elites(f) / el.size() * Math.min(1, e.chance()) * frac(e, t) * bandP(w.id(), String.format("band_t%02d_elite", t));
                }
                return tot;
            }
        }
    }

    static String kindOf(String source) {
        return switch (source) {
            case "drop", "chest" -> "M";
            case "trial" -> "T";
            case "hoard" -> "V";
            case "special" -> "S";
            case "elite" -> "E";
            default -> null;
        };
    }

    static double median(List<Double> xs) {
        List<Double> s = new ArrayList<>(xs);
        s.sort(Double::compare);
        int n = s.size();
        return n % 2 == 1 ? s.get(n / 2) : (s.get(n / 2 - 1) + s.get(n / 2)) / 2;
    }

    @Test
    void expectedRunsStayInTheirWindows() {
        Map<String, double[]> window = Map.of("M", new double[] {1, 5.5}, "T", new double[] {2.5, 7}, "V", new double[] {2.5, 9},
                "E", new double[] {3, 7}, "S", new double[] {2.5, 9});
        Map<String, List<Double>> byKind = new TreeMap<>();
        List<String> off = new ArrayList<>();
        for (ItemDef w : content.items().values()) {
            if (!w.isWeapon()) continue;
            java.util.Set<String> kinds = new java.util.TreeSet<>();
            for (String s : w.sources()) if (kindOf(s) != null) kinds.add(kindOf(s));
            for (String k : kinds) {
                if (k.equals("M") && w.levelReq() <= 1) continue; // Lv1 시작 무기 묶음은 창에서 뺀다 (설계와 같음)
                double p = rate(w, k);
                assertTrue(p > 0, w.id() + " " + k + " 자기 단계 층에서 안 나옴");
                double runs = 1 / Math.min(0.999, p);
                byKind.computeIfAbsent(k, x -> new ArrayList<>()).add(runs);
                double[] win = window.get(k);
                if (runs < win[0] - 1e-9 || runs > win[1] + 1e-9) off.add(k + " " + w.id() + " " + String.format("%.2f", runs) + "회");
            }
        }
        assertEquals(List.of(), off, "기대 회차가 창 밖");
        assertEquals(java.util.Set.of("M", "T", "V", "S", "E"), byKind.keySet());
        for (var e : byKind.entrySet()) {
            double m = median(e.getValue());
            double lo = e.getKey().equals("M") ? 2 : 3.5, hi = e.getKey().equals("M") ? 4 : 7.5;
            assertTrue(m >= lo && m <= hi, e.getKey() + " 가운데값 " + m + " (" + e.getValue().size() + "개)");
            assertTrue(e.getValue().size() >= 15, e.getKey() + " 무기 수 " + e.getValue().size());
        }
    }

    // ── 대장간 · 장비 수 ─────────────────────────────────────────

    static final List<String> SKIP = List.of("potions_", "scrolls", "tonics", "rare_consumables", "enhance_", "maze_enhance_");

    static double mid(IntRange r) { return r == null ? 1 : (r.min() + r.max()) / 2.0; }

    /** 표 1번 굴릴 때 기대 아이템 수 (물약·주문서·강화 재료 표 빼고, 어려움 이상 항목 빼고). */
    static Map<String, Double> tableYield(String tid, int depth) {
        Map<String, Double> out = new HashMap<>();
        LootTable t = content.lootTable(tid);
        if (t == null || depth > 6) return out;
        for (LootTable.Entry e : t.guaranteed()) add(out, e, 1.0, depth);
        for (LootTable.Entry e : t.entries()) {
            if (e.minDifficulty() != null && (e.minDifficulty().equals("hard") || e.minDifficulty().equals("nightmare"))) continue;
            add(out, e, rolls(t) * Math.min(1.0, e.chance()), depth);
        }
        return out;
    }

    private static void add(Map<String, Double> out, LootTable.Entry e, double mult, int depth) {
        switch (e.kind()) {
            case ITEM -> out.merge(e.item(), mult * mid(e.amount()), Double::sum);
            case ONE_OF -> { for (String x : e.oneOf()) out.merge(x, mult * mid(e.amount()) / e.oneOf().size(), Double::sum); }
            case TABLE -> {
                if (SKIP.stream().noneMatch(e.table()::startsWith)) tableYield(e.table(), depth + 1).forEach((k, v) -> out.merge(k, mult * v, Double::sum));
            }
            case PICK -> {
                for (LootTable.Pick p : e.pick()) {
                    double w = (double) p.weight() / e.pickWeight();
                    tableYield(p.table(), depth + 1).forEach((k, v) -> out.merge(k, mult * v * w, Double::sum));
                }
            }
            case RARITY_POOL -> { }
        }
    }

    static Map<String, Double> runYield(int f, boolean extra) {
        Map<String, Double> tot = new HashMap<>();
        for (Src s : runSources(f, extra)) tableYield(s.table(), 0).forEach((k, v) -> tot.merge(k, s.n() * v, Double::sum));
        return tot;
    }

    static double runGold(int f) {
        double g = 0;
        int normal = 0, elite = 0;
        double ng = 0, eg = 0;
        for (MobDef m : content.mobs().values()) {
            if (m.floor() != f) continue;
            if ("normal".equals(m.rank())) {
                normal++;
                ng += mid(m.gold());
            } else if (m.isElite()) {
                elite++;
                eg += mid(m.gold());
            }
        }
        g += MOBS_RUN.get(f) * ng / normal + elites(f) * eg / elite;
        BossDef b = content.bossOfFloor(f);
        g += mid(b.gold());
        for (Src s : runSources(f, false)) {
            LootTable t = content.lootTable(s.table());
            if (t != null && t.gold() != null && t.gold().max() > 0 && !s.table().equals(b.drops())) g += s.n() * mid(t.gold());
        }
        return g;
    }

    @Test
    void dungeonOrePerRunMatchesTheContract() {
        // 0.3.6 던전 광석 (계약 §2.8 — 모든 층): 1회(솔로) 기대 광석 = materials.json dungeon_ore.per_run ±10% (몹·정예·보스·상자 표 합)
        Map<Integer, Integer> perRun = Map.of(1, 8, 2, 7, 3, 7, 4, 8, 5, 8, 6, 11, 7, 12, 8, 11, 9, 14, 10, 13);
        List<String> off = new ArrayList<>();
        StringBuilder sb = new StringBuilder();
        for (int f = 1; f <= 10; f++) {
            double ore = 0;
            for (var e : runYield(f, false).entrySet()) {
                ItemDef d = content.item(e.getKey());
                if (d != null && d.mineKind() == kr.labyrinth.content.MineKind.ORE) ore += e.getValue();
            }
            sb.append(f).append("층 ").append(String.format("%.1f", ore)).append(" · ");
            if (Math.abs(ore - perRun.get(f)) > perRun.get(f) * 0.10) off.add(f + "층 " + String.format("%.1f", ore) + " (계약 " + perRun.get(f) + ")");
        }
        System.out.println("ORE 1회 광석 " + sb);
        assertEquals(List.of(), off, "던전 광석 1회량");
    }

    /** 대장간 기준 무기 — 대장간에서 만들 수 있는 무기 중 신화(신화 도안 + 큰 골드, 8~10회 목표)를 뺀 것. */
    static boolean forge(ItemDef w) {
        return w.isWeapon() && w.sources().contains("craft") && w.rarity() != Rarity.MYTHIC;
    }

    @Test
    void forgeBaselineRecipesTakeAFewRuns() {
        // 띠 대장간 기준 = 그 띠 가장 높은 레벨 대장간 무기 — 제작 회차 = max(재료 회차, 골드 회차) 0.3~2.5 (무기 레시피 골드 ×1.5 뒤)
        // 0.3.7 신화 레시피(CR37 — 도안 + 10층 재료 + 110,000G, 8~10회 목표)는 기준이 아니다 → MythicSetTest · MythicNoNelkarGateTest
        Map<String, RecipeDef> recipeOf = new HashMap<>();
        for (RecipeDef r : content.recipes().values()) recipeOf.putIfAbsent(r.result(), r);
        List<String> off = new ArrayList<>();
        int checked = 0;
        for (int band = 1; band <= 10; band++) {
            int top = 0;
            for (ItemDef w : content.items().values()) {
                if (forge(w) && GearModel.band(w.levelReq()) == band) top = Math.max(top, w.levelReq());
            }
            assertTrue(top > 0, "띠 " + band + " 대장간 무기 없음");
            for (ItemDef w : content.items().values()) {
                if (!forge(w) || w.levelReq() != top) continue;
                RecipeDef r = recipeOf.get(w.id());
                Map<String, Double> y = runYield(w.tier(), false);
                double mat = 0;
                for (var m : r.materials().entrySet()) {
                    ItemDef md = content.item(m.getKey());
                    if (md != null && md.isMineMaterial()) continue;   // 0.3.6 주괴는 광산·제련소 몫 (계약 §5 표 C — 광산 분)
                    double per = y.getOrDefault(m.getKey(), 0.0);
                    mat = Math.max(mat, per > 0 ? m.getValue() / per : Double.POSITIVE_INFINITY);
                }
                double runs = Math.max(mat, r.gold() / runGold(w.tier()));
                if (runs < 0.3 || runs > 2.5) off.add(w.id() + " " + String.format("%.2f", runs) + "회");
                checked++;
            }
        }
        assertEquals(List.of(), off, "대장간 기준 레시피 회차가 0.3~2.5 밖");
        assertTrue(checked >= 50, "기준 레시피 " + checked);
    }

    @Test
    void gearPerRunStaysNearThe034Amount() {
        // 1회 돌기 장비(무기 + 방어구) 기대 수 (금고·미믹 · 특별 시련 포함) = 0.3.4 의 0.8~1.6배 (gear_spec gear_per_run before).
        // 0.3.4 에 층 공용 무기가 없던 층(6·8·9·10 — 무기 0.25)은 공용 무기가 있던 층들의 가운데값과 비교한다
        Map<Integer, Double> before = new LinkedHashMap<>();
        List<Double> withCommon = new ArrayList<>();
        for (int f = 1; f <= 10; f++) {
            JsonObject b = gearPerRun.getAsJsonObject(String.valueOf(f)).getAsJsonObject("before");
            double w = b.get("weapon").getAsDouble(), a = b.get("armor").getAsDouble();
            before.put(f, w >= 1 ? w + a : -1);
            if (w >= 1) withCommon.add(w + a);
        }
        double ref = median(withCommon);
        List<String> off = new ArrayList<>();
        for (int f = 1; f <= 10; f++) {
            double now = 0;
            for (var e : runYield(f, true).entrySet()) {
                ItemDef d = content.item(e.getKey());
                if (d != null && (d.isWeapon() || d.type() == ItemType.ARMOR)) now += e.getValue();
            }
            double base = before.get(f) > 0 ? before.get(f) : ref;
            double ratio = now / base;
            if (ratio < 0.8 || ratio > 1.6) off.add(f + "층 " + String.format("%.2f / %.2f = %.2f", now, base, ratio));
        }
        assertEquals(List.of(), off, "1회 장비 수가 0.3.4 의 0.8~1.6배 밖");
    }
}
