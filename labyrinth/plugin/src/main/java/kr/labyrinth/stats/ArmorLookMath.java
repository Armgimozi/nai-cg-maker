package kr.labyrinth.stats;

import java.util.Collections;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.Map;
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.core.ArmorLooks;

/**
 * 방어구 겉모습 계산 (look_spec §1.2, 순수 — 단위 테스트 대상). 장비 기여(EquipmentListener)가 요구 능력치를 맞춘 부위마다
 * StatBlock 에 겉모습 수를 넣는다:
 * <ul>
 *   <li>{@code look.<id>} — 그 겉모습 부위 수 (방패 = {@code shield_counts_as} 한 부위, 평상복·any 는 안 셈) → 숨은 효과</li>
 *   <li>{@code look_body.<id>} — 머리·몸·다리·발만 (any 포함, 방패 제외) → 4부위 판정</li>
 * </ul>
 * 숨은 효과 합 = Σ 부위 수 × 부위 하나 값. 더하는 키는 장비 스탯처럼 더하고(상한 그대로), 곱하는 키는 따로 곱한다:
 * 방어·최대 HP·MP 재생 × (1 + 합), 재사용 대기 × max(0.5, 1 + 합). 4부위 = 같은 겉모습 수 + any 수 ≥ full_pieces.
 */
public final class ArmorLookMath {

    public static final String COUNT_PREFIX = "look.";
    public static final String BODY_PREFIX = "look_body.";
    /** 밀려남 저항 상한 (힘 + 버팀). */
    public static final double CAP_KNOCKBACK = 0.85;
    /** 힘만의 밀려남 저항 상한 (0.3.4 그대로). */
    public static final double CAP_KNOCKBACK_STR = 0.5;
    /** 재사용 대기 배율 하한. */
    public static final double MIN_COOLDOWN_MULT = 0.5;

    private ArmorLookMath() {}

    public static String countKey(ArmorLook l) { return COUNT_PREFIX + l.id(); }

    public static String bodyKey(ArmorLook l) { return BODY_PREFIX + l.id(); }

    /**
     * 겉모습 계산 결과.
     * @param counts     겉모습별 부위 수 (방패 포함, 판금·가죽·천만)
     * @param body       머리·몸·다리·발 겉모습 수 (any 포함)
     * @param full       4부위 효과가 켜진 겉모습 (없으면 null)
     * @param additive   더하는 숨은 효과 합 (StatBlock 키)
     * @param ccResist   기절·속박·빙결 시간 감소 (판금 4부위)
     * @param knockbackResist 밀려남 저항 덧 (판금 4부위, 힘 몫과 더함)
     */
    public record Result(Map<ArmorLook, Integer> counts, Map<ArmorLook, Integer> body, ArmorLook full,
                         Map<String, Double> additive, double defenseMult, double hpMult, double manaRegenMult,
                         double cooldownMult, double ccResist, double knockbackResist) {

        public static final Result NONE = new Result(Map.of(), Map.of(), null, Map.of(), 1, 1, 1, 1, 0, 0);

        public int count(ArmorLook l) { return counts.getOrDefault(l, 0); }

        public int bodyCount(ArmorLook l) { return body.getOrDefault(l, 0); }
    }

    /** 겉모습 수를 읽어 숨은 효과·4부위 효과를 정한다. cfg 가 꺼져 있으면 효과 없이 수만. */
    public static Result compute(StatBlock bonus, ArmorLooks cfg) {
        EnumMap<ArmorLook, Integer> counts = new EnumMap<>(ArmorLook.class);
        EnumMap<ArmorLook, Integer> body = new EnumMap<>(ArmorLook.class);
        for (ArmorLook l : ArmorLook.values()) {
            int n = (int) Math.round(bonus.get(countKey(l)));
            int b = (int) Math.round(bonus.get(bodyKey(l)));
            if (n > 0 && l.real()) counts.put(l, n);
            if (b > 0 && (l.real() || l == ArmorLook.ANY)) body.put(l, b);
        }
        if (counts.isEmpty() && body.isEmpty()) return Result.NONE;
        Map<ArmorLook, Integer> c = Collections.unmodifiableMap(counts);
        Map<ArmorLook, Integer> bd = Collections.unmodifiableMap(body);
        if (cfg == null || !cfg.enabled()) return new Result(c, bd, null, Map.of(), 1, 1, 1, 1, 0, 0);

        Map<String, Double> add = new LinkedHashMap<>();
        double defPct = 0, hpPct = 0, mpPct = 0, cdPct = 0;
        for (Map.Entry<ArmorLook, Integer> e : counts.entrySet()) {
            ArmorLooks.Look look = cfg.look(e.getKey());
            if (look == null) continue;
            int n = e.getValue();
            for (Map.Entry<String, Double> p : look.piece().entrySet()) {
                double v = p.getValue() * n;
                switch (p.getKey()) {
                    case "defense_pct" -> defPct += v;
                    case "hp_pct" -> hpPct += v;
                    case "mana_regen_pct" -> mpPct += v;
                    case "cooldown_pct" -> cdPct += v;
                    default -> add.merge(p.getKey(), v, Double::sum);
                }
            }
        }
        ArmorLook full = fullLook(bd, cfg.fullPieces());
        double cc = full == ArmorLook.HEAVY ? cfg.steadfast().ccResist() : 0;
        double kb = full == ArmorLook.HEAVY ? cfg.steadfast().knockbackResist() : 0;
        return new Result(c, bd, full, Collections.unmodifiableMap(add), Math.max(0, 1 + defPct), Math.max(0.1, 1 + hpPct),
                Math.max(0, 1 + mpPct), Math.max(MIN_COOLDOWN_MULT, 1 + cdPct), cc, kb);
    }

    /** 머리·몸·다리·발 중 같은 겉모습 수 + any 수 ≥ need 인 겉모습 (판금·가죽·천, 없으면 null). 2 + 2 는 없음. */
    public static ArmorLook fullLook(Map<ArmorLook, Integer> body, int need) {
        int any = body.getOrDefault(ArmorLook.ANY, 0);
        ArmorLook best = null;
        int bestN = 0;
        for (ArmorLook l : ArmorLook.REAL) {
            int n = body.getOrDefault(l, 0);
            if (n > 0 && n + any >= need && n > bestN) {
                best = l;
                bestN = n;
            }
        }
        return best;
    }

    /** 밀려남 저항 = clamp(min(0.5, 0.003 × 힘) + 버팀, 0, 0.85). */
    public static double knockbackResistance(int str, double steadfast) {
        double s = Math.min(CAP_KNOCKBACK_STR, Math.max(0, str) * 0.003);
        return Math.max(0, Math.min(CAP_KNOCKBACK, s + Math.max(0, steadfast)));
    }
}
