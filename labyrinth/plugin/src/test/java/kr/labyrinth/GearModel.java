package kr.labyrinth;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.combat.CombatMath;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.UniqueDef;
import kr.labyrinth.stats.Stat;

/**
 * 0.3.5 장비 설계 검사 모델 (시험 전용) — tools 설계 스크립트(g2_check · ud_value · rv2_choice)와 같은 식.
 * <ul>
 *   <li>세금 = 요구치를 채우려 '알맞은 분배'(combat_spec sensible_spread new, 또는 다른 빌드 5종) 밖으로 더 찍는 포인트 ÷ 받은 포인트.
 *       포인트 = 시작 5 + 레벨당 5, 칭호 없음, 초기화 뒤 (가장 나쁜 경우).</li>
 *   <li>한 벌 = 무기 + 방어구 세트 (그 레벨 − 15 ~ 그 레벨에 나온 것, 겉모습 무엇이든) (+ 수호기사 방패).</li>
 *   <li>무기 힘 Q = 비교값 × (1 + 부가 스탯 가치 + 0.1 × 무기 스킬 수) ÷ TP(L), 비교값 = (한 방 가운데값 ÷ 간격) ÷ K.</li>
 *   <li>상황 이득 gain(P 무리 · E 정예 · B 보스 혼자 · T 보스 파티) = 고유 효과가 그 상황에서 더해 주는 몫.</li>
 * </ul>
 */
final class GearModel {

    private GearModel() {}

    static final double TAX_OK = 0.15;
    static final List<String> CLASSES = List.of("guardian", "berserker", "hunter", "arcanist", "priest", "shadow");
    static final List<String> SITS = List.of("P", "E", "B", "T");

    /** combat_spec sensible_spread new — 직업 기본 '알맞은 분배' 비율. */
    static final Map<String, Map<Stat, Double>> SPREAD = new LinkedHashMap<>();
    /** 직업 기본 말고 고를 수 있는 빌드 5종 (g2_req ARCH). */
    static final Map<String, Map<Stat, Double>> ARCH = new LinkedHashMap<>();

    static {
        SPREAD.put("guardian", ratio(Stat.VIT, 3, Stat.STR, 2));
        SPREAD.put("berserker", ratio(Stat.STR, 3, Stat.VIT, 2));
        SPREAD.put("hunter", ratio(Stat.DEX, 2.0, Stat.STR, 1.3, Stat.VIT, 1.7));
        SPREAD.put("arcanist", ratio(Stat.INT, 3, Stat.VIT, 2));
        SPREAD.put("priest", ratio(Stat.WIS, 2.5, Stat.INT, 0.55, Stat.VIT, 1.95));
        SPREAD.put("shadow", ratio(Stat.DEX, 2.0, Stat.STR, 1.4, Stat.VIT, 1.6));
        ARCH.put("치명", ratio(Stat.DEX, 1.6, Stat.LUK, 1.2, Stat.STR, 1.0, Stat.VIT, 1.2));
        ARCH.put("마검사", ratio(Stat.STR, 1.4, Stat.INT, 1.4, Stat.VIT, 1.6, Stat.DEX, 0.4));
        ARCH.put("전투 사제", ratio(Stat.WIS, 1.8, Stat.STR, 1.2, Stat.VIT, 1.8));
        ARCH.put("민첩 시전", ratio(Stat.INT, 2.2, Stat.DEX, 1.2, Stat.VIT, 1.6));
        ARCH.put("방벽 시전", ratio(Stat.VIT, 2.2, Stat.WIS, 1.4, Stat.INT, 1.4));
    }

    private static Map<Stat, Double> ratio(Object... kv) {
        Map<Stat, Double> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((Stat) kv[i], ((Number) kv[i + 1]).doubleValue());
        return m;
    }

    static int band(int level) { return (Math.max(1, level) - 1) / 5 + 1; }

    static int pointsAt(int level) { return 5 + (Math.max(1, level) - 1) * 5; }

    static Map<Stat, Integer> base(ClassDef c) {
        Map<Stat, Integer> m = new EnumMap<>(Stat.class);
        for (Stat s : Stat.values()) m.put(s, c.baseStat(s));
        return m;
    }

    // ── 세금 ─────────────────────────────────────────────

    /** extra = 알맞은 분배 밖으로 더 찍는 포인트, need = 직업 기본 위에 찍어야 하는 포인트. */
    record Tax(double extra, boolean feasible, int need) {}

    static Tax tax(Map<Stat, Integer> base, Map<Stat, Double> ratio, int level, Map<Stat, Integer> req) {
        int n = pointsAt(level);
        int need = 0;
        for (var e : req.entrySet()) need += Math.max(0, e.getValue() - base.getOrDefault(e.getKey(), 0));
        double tot = 0, pool = n;
        for (var e : ratio.entrySet()) {
            tot += e.getValue();
            pool += base.getOrDefault(e.getKey(), 0);
        }
        Map<Stat, Double> plan = new EnumMap<>(Stat.class);
        for (var e : ratio.entrySet()) plan.put(e.getKey(), Math.max(base.getOrDefault(e.getKey(), 0), pool * e.getValue() / tot));
        double extra = 0;
        for (var e : req.entrySet()) {
            double have = plan.getOrDefault(e.getKey(), (double) base.getOrDefault(e.getKey(), 0));
            extra += Math.max(0, e.getValue() - have);
        }
        return new Tax(extra, need <= n, need);
    }

    static Map<Stat, Integer> kit(List<Map<Stat, Integer>> reqs) {
        Map<Stat, Integer> out = new EnumMap<>(Stat.class);
        for (Map<Stat, Integer> r : reqs) r.forEach((s, v) -> out.merge(s, v, Math::max));
        return out;
    }

    /** 방어구 세트 (네 부위 요구가 같다) 또는 방패. level = 그 세트 가장 높은 부위 레벨. */
    record Armor(String id, int level, Map<Stat, Integer> req) {}

    static List<Armor> sets(Content content) {
        Map<String, Armor> out = new LinkedHashMap<>();
        for (ItemDef d : content.items().values()) {
            if (d.type() != ItemType.ARMOR || d.isShield() || d.setBonus() == null) continue;
            Armor a = out.get(d.setBonus());
            out.put(d.setBonus(), a == null ? new Armor(d.setBonus(), d.levelReq(), d.requirement().all())
                    : new Armor(a.id(), Math.max(a.level(), d.levelReq()), a.req()));
        }
        return new ArrayList<>(out.values());
    }

    static List<Armor> shields(Content content) {
        List<Armor> out = new ArrayList<>();
        for (ItemDef d : content.items().values()) {
            if (d.type() == ItemType.ARMOR && d.isShield()) out.add(new Armor(d.id(), d.levelReq(), d.requirement().all()));
        }
        return out;
    }

    /** 그 직업이 레벨 p 에서 무기(요구 wreq)와 함께 끼는 한 벌 중 가장 낮은 세금 (못 끼면 null). */
    static Double bestKitTax(Map<Stat, Integer> base, String cls, int p, Map<Stat, Integer> wreq, List<Armor> sets,
                             List<Armor> shields, int lo) {
        Map<Stat, Double> ratio = SPREAD.get(cls);
        Double best = null;
        for (Armor s : sets) {
            if (s.level() > p || s.level() < lo) continue;
            List<Map<Stat, Integer>> reqs = new ArrayList<>(List.of(wreq, s.req()));
            if (cls.equals("guardian")) {
                Armor sh = null;
                double shTax = 0;
                for (Armor v : shields) {
                    if (v.level() < lo || v.level() > p) continue;
                    List<Map<Stat, Integer>> with = new ArrayList<>(reqs);
                    with.add(v.req());
                    double t = tax(base, ratio, p, kit(with)).extra();
                    if (sh == null || t < shTax || (t == shTax && v.level() > sh.level())) {
                        sh = v;
                        shTax = t;
                    }
                }
                if (sh != null) reqs.add(sh.req());
            }
            Tax t = tax(base, ratio, p, kit(reqs));
            if (!t.feasible()) continue;
            double v = t.extra() / pointsAt(p);
            if (best == null || v < best) best = v;
        }
        return best;
    }

    // ── 무기 힘 ─────────────────────────────────────────────

    static double mid(Range r) { return (r.min() + r.max()) / 2; }

    static double pL(int l) { return 7 + 0.25 * (l - 1) + 0.0195 * (l - 1) * (l - 1); }

    static double cL(int l) {
        double s = 8 + 3.6 * (l + 3);
        return (1 + 0.02 * s) / (1 + 0.01 * s);
    }

    static double tp(int l) { return pL(l) * cL(l); }

    static double spm(WeaponAttack.Style st) { return st == WeaponAttack.Style.CASTER ? 1.05 : 1.0; }

    /** 비교값 = (한 방 가운데값 ÷ 간격) ÷ K(방식, 간격). */
    static double cv(ItemDef w) {
        WeaponAttack a = w.attack();
        return (mid(w.stats().get("damage")) / a.interval()) / CombatMath.k(a.style(), a.interval());
    }

    private static final Map<String, Double> WGT = Map.of("crit_chance", 0.5, "crit_damage", 0.2, "attack_speed", 0.7,
            "lifesteal", 0.4, "skill_damage", 0.35, "cooldown_reduction", 0.45, "damage_reduction", 0.8, "evasion", 0.6,
            "move_speed", 0.15);
    private static final Set<String> STATS6 = Set.of("STR", "DEX", "INT", "VIT", "WIS", "LUK");

    static double secValue(int l, Map<String, Range> stats) {
        double sp = 8 + 2.5 * (l - 1);
        double v = 0;
        for (var e : stats.entrySet()) {
            String k = e.getKey();
            if (k.equals("damage")) continue;
            double m = mid(e.getValue());
            if (STATS6.contains(k)) v += k.equals("STR") || k.equals("INT") ? 0.01 * m / (1 + 0.01 * sp) : m * 0.002;
            else if (WGT.containsKey(k)) v += WGT.get(k) * m;
            else switch (k) {
                case "heal_power" -> v += 0.4 * m / (1.5 * sp);
                case "mana_regen" -> v += 0.2 * m / (1 + 0.05 * sp);
                case "hp" -> v += m / (100 + 9 * l) * 0.4;
                case "defense" -> v += m * 0.004;
                case "hp_regen" -> v += m * 0.01;
                case "mp" -> v += m / (80 + 3 * l) * 0.15;
                default -> { }
            }
        }
        return v;
    }

    static double q(ItemDef w) {
        int l = w.levelReq();
        return cv(w) * (1 + secValue(l, w.stats()) + 0.1 * w.weaponSkills().size()) / tp(l);
    }

    // ── 상황 이득 ─────────────────────────────────────────────

    private static final double CC = 0.25, CD = 1.5, CF = 1 + CC * (CD - 1), R_DH = 0.15, T_KILL = 3.0, W_LS = 0.4, W_DR = 0.8;
    private static final int N_EXTRA = 3;
    private static final int[] BOSS_DEF = {0, 8, 10, 12, 16, 22, 28, 34, 40, 46, 56};
    private static final List<String> STATUS_KEYS = List.of("poison", "venom", "bleed", "ignite", "frost", "slow", "weak",
            "blind", "mark", "freeze");

    static boolean hasStatusSkill(ItemDef w, List<String> keys) {
        Object raw = w.raw() == null ? null : w.raw().get("weapon_skills");
        String s = raw == null ? "" : raw.toString();
        for (String k : keys) if (s.contains(k)) return true;
        return false;
    }

    private static double by(String sit, double p, double e, double b, double t) {
        return switch (sit) {
            case "P" -> p;
            case "E" -> e;
            case "B" -> b;
            default -> t;
        };
    }

    static double gain(ItemDef w, String sit) {
        UniqueDef u = w.unique();
        if (u == null) return 0;
        WeaponAttack a = w.attack();
        double iv = a.interval();
        double al = a.style() == WeaponAttack.Style.CASTER ? 0.5 : 0.7;
        double kk = CombatMath.k(a.style(), iv) / spm(a.style());
        int b = band(w.levelReq());
        boolean pack = sit.equals("P");
        var p = u.params();
        int skills = w.weaponSkills().size();
        return switch (u.id()) {
            case "rend" -> {
                double stacks = Math.min(p.dbl("max_stacks", 5), p.dbl("duration", 4) * CC * (1 / iv + 0.5));
                yield stacks * u.num("pct") * iv * al / CF * (pack ? 0.5 : 1.0);
            }
            case "hemorrhage" -> {
                double ub = hasStatusSkill(w, List.of("bleed")) ? 0.5 : 0.15;
                yield ub * ((1 + (CC + u.num("cc")) * (CD + u.num("cd") - 1)) / CF - 1) * (pack ? 0.7 : 1.0);
            }
            case "leech" -> W_LS * u.num("pct") * al * by(sit, 1.2, 1.2, 1.0, 0.6);
            case "feast" -> pack ? W_LS * (u.num("heal") / T_KILL / R_DH + u.num("ls") * Math.min(1, p.dbl("duration", 4) / T_KILL))
                    : W_LS * u.num("heal") * 0.03 / R_DH;
            case "thorns" -> u.num("pct") * by(sit, 0.35, 0.2, 0.1, 0.1);
            case "bash_stun" -> {
                double g = al * u.num("pct") / (u.num("n") * CF);
                double period = u.num("n") * iv;
                if (sit.equals("P") || sit.equals("E")) g += W_DR * u.num("stun") / Math.max(6.0, period);
                else g += u.num("vuln") * Math.min(1.0, 3.0 / period);
                yield g;
            }
            case "steadfast" -> W_DR * u.num("dr") * by(sit, 0.5, 0.6, 0.6, 0.8);
            case "cleave" -> pack ? al * u.num("pct") * Math.min(u.num("targets"), N_EXTRA) / CF : 0;
            case "chain_spark" -> pack ? al * u.num("chance") * u.num("pct") * Math.min(u.num("targets"), N_EXTRA) / CF : 0;
            case "death_burst" -> pack ? u.num("pct") * 1.5 * al / (kk * CF * T_KILL) : 0;
            case "execute" -> u.num("thr") * u.num("pct") * by(sit, 0.8, 1.0, 0.6, 0.6);
            case "bloodrush" -> pack ? u.num("pct") * iv * al / (CF * T_KILL) : 0;
            case "momentum" -> {
                double add = Math.min(p.dbl("max_stacks", 5) * u.num("as"), 0.4);
                yield add * (al + (1 - al) * 0.5) * by(sit, 0.7, 0.9, 0.9, 0.9);
            }
            case "flurry" -> al * u.num("pct") / u.num("n");
            case "counterstep" -> {
                double procs = Math.min(0.5, 0.12 * by(sit, 2.0, 0.8, 0.4, 0.2));
                yield procs * iv * al * ((1 + u.num("pct")) * CD - CF) / CF;
            }
            case "siphon" -> {
                double ws = Math.min(0.3, 0.1 * skills);
                double g = ws * u.num("cdr") / T_KILL + (1 - al) * 0.3 * (u.num("mp") / 0.12);
                yield pack ? g : g * 0.05;
            }
            case "overcharge" -> 0.25 * u.num("pct") * al * (pack ? 3 : 1) / (kk * CF);
            case "sanctify" -> {
                double g = W_LS * u.num("pct") * al / CF;
                yield sit.equals("T") ? g : g * 0.5;
            }
            case "ward_aura" -> {
                double g = W_LS * (u.num("pct") / p.dbl("period", 8)) / R_DH;
                yield sit.equals("T") ? g * 2 : g;
            }
            case "imbue" -> {
                if ("frost".equals(u.text("element", ""))) {
                    double per = 5 / (u.num("chance") / iv);
                    yield sit.equals("P") || sit.equals("E") ? W_DR / per : 0.05 * Math.min(1, 3 / per);
                }
                yield 0.85 * u.num("pct") * al / (kk * CF) * (pack ? 0.5 : 1.0);
            }
            case "exploit" -> {
                double uu = hasStatusSkill(w, STATUS_KEYS) ? 0.8 : 0.6;
                yield u.num("pct") * (uu + 0.6 * 0.2) * (pack ? 0.7 : 1.0);
            }
            case "first_strike" -> {
                double rate = by(sit, 1 / T_KILL, 2.0 / 25, 1.0 / 30, 1.0 / 30);
                yield rate * iv * al * (u.num("pct") + p.dbl("cc", 0.2) * (CD - 1)) / CF;
            }
            case "backstab" -> u.num("pct") * by(sit, 0.2, 0.3, 0.3, 0.7);
            case "longshot" -> {
                double g = u.num("pct") * by(sit, 0.3, 0.4, 0.4, 0.7);
                if (pack) g += al * 0.8 * u.num("pierce") * 0.3 / CF;
                yield g;
            }
            case "berserk" -> by(sit, 0.25, 0.35, 0.35, 0.15) * 10 * u.num("pct") + W_LS * u.num("ls") * by(sit, 0.1, 0.15, 0.15, 0.05);
            case "armor_break" -> {
                double up = by(sit, 0.3, 0.9, 0.95, 0.95);
                double d = BOSS_DEF[Math.min(10, b)] * by(sit, 0.3, 0.6, 1.0, 1.0);
                double sh = Math.min(0.4, p.dbl("max_stacks", 5) * u.num("pct")) * up;
                double g = (100 + d) / (100 + d * (1 - sh)) - 1;
                yield g * (sit.equals("T") ? 2 : 1);
            }
            default -> throw new IllegalArgumentException("모르는 고유 효과 " + u.id() + " (" + w.id() + ")");
        };
    }

    // ── 직업 × 띠 칸 ─────────────────────────────────────────────

    /** 칸 결과. viable = 어느 상황에서든 가장 좋은 것의 90% 이상 · dom = 모든 상황에서 다른 viable 이상인 무기 · strong = 95% 이상인 보스·대장간 아닌 무기. */
    record Cell(String key, boolean ok, List<String> ids, List<String> viable, String dom, List<String> strong) {}

    static String sourceKind(String s) {
        return switch (s) {
            case "boss" -> "B";
            case "craft" -> "F";
            case "drop", "chest" -> "M";
            case "trial" -> "T";
            case "special" -> "S";
            case "hoard" -> "V";
            case "elite" -> "E";
            case "shop" -> "P";
            case "reward" -> "R";
            default -> "ST";
        };
    }

    /** 직업이 피해 종류에 맞는(물리 직업 = 물리, 비전술사·사제 = 마법, 사냥꾼은 원거리만) 그 띠 무기 중 세금 ≤ 15% 로 끼는 것. */
    static List<String> goodWeapons(Content content, String cls, int band, boolean styleRule) {
        ClassDef c = content.classes().get(cls);
        Map<Stat, Integer> base = base(c);
        List<Armor> sets = sets(content), shields = shields(content);
        int p = 5 * band, lo = Math.max(1, p - 15);
        DamageKind dk = cls.equals("arcanist") || cls.equals("priest") ? DamageKind.MAGIC : DamageKind.PHYSICAL;
        List<String> ids = new ArrayList<>();
        for (ItemDef w : content.items().values()) {
            if (!w.isWeapon() || band(w.levelReq()) != band || w.rarity() == Rarity.MYTHIC || w.attack().kind() != dk) continue;
            if (styleRule && cls.equals("hunter") && w.attack().style() != WeaponAttack.Style.RANGED) continue;
            Double t = bestKitTax(base, cls, p, w.requirement().all(), sets, shields, lo);
            if (t != null && t <= TAX_OK + 1e-9) ids.add(w.id());
        }
        return ids;
    }

    static Map<String, Cell> cells(Content content) {
        Map<String, Cell> out = new LinkedHashMap<>();
        for (int b = 1; b <= 10; b++) {
            for (String cls : CLASSES) {
                String key = cls + "|" + b;
                List<String> ids = goodWeapons(content, cls, b, true);
                if (ids.isEmpty()) {
                    out.put(key, new Cell(key, false, ids, List.of(), null, List.of()));
                    continue;
                }
                Map<String, double[]> vals = new LinkedHashMap<>();
                double[] best = new double[4];
                for (String id : ids) {
                    ItemDef w = content.item(id);
                    double q = q(w);
                    double[] v = new double[4];
                    for (int i = 0; i < 4; i++) {
                        v[i] = q * (1 + gain(w, SITS.get(i)));
                        best[i] = Math.max(best[i], v[i]);
                    }
                    vals.put(id, v);
                }
                List<String> viable = new ArrayList<>(), strong = new ArrayList<>();
                for (String id : ids) {
                    double rel = 0;
                    for (int i = 0; i < 4; i++) rel = Math.max(rel, vals.get(id)[i] / best[i]);
                    if (rel >= 0.90) viable.add(id);
                    boolean bf = false;
                    for (String s : content.item(id).sources()) bf |= sourceKind(s).equals("B") || sourceKind(s).equals("F");
                    if (rel >= 0.95 && !bf) strong.add(id);
                }
                String dom = null;
                if (viable.size() > 1) {
                    for (String id : viable) {
                        boolean all = true;
                        for (String o : viable) {
                            if (o.equals(id)) continue;
                            for (int i = 0; i < 4; i++) all &= vals.get(id)[i] >= vals.get(o)[i];
                        }
                        if (all) {
                            dom = id;
                            break;
                        }
                    }
                }
                boolean ok = viable.size() >= 3 && dom == null && !strong.isEmpty();
                out.put(key, new Cell(key, ok, ids, viable, dom, strong));
            }
        }
        return out;
    }
}
