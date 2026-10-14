package kr.labyrinth.items;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.SplittableRandom;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Range;

/**
 * 장비 스탯 굴림 (GDD §11.1) — 순수 로직, Bukkit 무관(단위 테스트 대상).
 * <ul>
 *   <li>stats 의 [최소, 최대] 를 키마다 균등 굴림. 같은 시드 → 같은 결과 (정의 순서대로 난수 소비).</li>
 *   <li>정수 키(피해·스탯 6종·hp·mp·방어·치유력)는 반올림, 백분율 키는 0.1%p, 재생은 0.01 단위.</li>
 *   <li>PDC 형식({@code core.Keys.ITEM_ROLLS}) = {@code "key=value;key=value"} (Locale.ROOT).</li>
 * </ul>
 */
public final class ItemRolls {

    /** 정수로 굴리는 키. */
    public static final Set<String> INT_KEYS = Set.of("damage", "STR", "DEX", "INT", "VIT", "WIS", "LUK", "hp", "mp",
            "defense", "heal_power");
    /** 0~1 비율 키 (툴팁에 % 로 표시). */
    public static final Set<String> PERCENT_KEYS = Set.of("crit_chance", "crit_damage", "attack_speed", "move_speed",
            "cooldown_reduction", "skill_damage", "lifesteal", "damage_reduction", "evasion", "block_chance", "gold_bonus",
            "xp_bonus", "craft_discount");

    private ItemRolls() {}

    /** 시드로 굴린 스탯 (정의 순서 유지). 스탯이 없으면 빈 맵. */
    public static Map<String, Double> roll(ItemDef def, long seed) {
        Map<String, Double> out = new LinkedHashMap<>();
        if (def == null || def.stats().isEmpty()) return out;
        SplittableRandom rng = new SplittableRandom(seed);
        for (Map.Entry<String, Range> e : def.stats().entrySet()) {
            Range r = e.getValue();
            double t = rng.nextDouble();
            if (r == null) continue;
            out.put(e.getKey(), round(e.getKey(), r.lerp(t)));
        }
        return out;
    }

    /** 굴림 없이 범위 중간값 (오래된 아이템·미리보기용). */
    public static Map<String, Double> midpoint(ItemDef def) {
        Map<String, Double> out = new LinkedHashMap<>();
        if (def == null) return out;
        def.stats().forEach((k, r) -> { if (r != null) out.put(k, round(k, r.lerp(0.5))); });
        return out;
    }

    /** 키 종류에 맞춰 반올림. */
    public static double round(String key, double v) {
        if (INT_KEYS.contains(key)) return Math.round(v);
        if (PERCENT_KEYS.contains(key)) return Math.round(v * 1000.0) / 1000.0;
        return Math.round(v * 100.0) / 100.0;
    }

    public static String encode(Map<String, Double> rolls) {
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, Double> e : rolls.entrySet()) {
            if (!sb.isEmpty()) sb.append(';');
            double v = e.getValue();
            sb.append(e.getKey()).append('=');
            if (v == Math.rint(v) && Math.abs(v) < 1e12) sb.append((long) v);
            else sb.append(String.format(Locale.ROOT, "%.4f", v).replaceAll("0+$", "").replaceAll("\\.$", ""));
        }
        return sb.toString();
    }

    /** encode 의 역. 깨진 항목은 건너뛴다. */
    public static Map<String, Double> decode(String s) {
        if (s == null || s.isBlank()) return Collections.emptyMap();
        Map<String, Double> out = new LinkedHashMap<>();
        for (String part : s.split(";")) {
            int eq = part.indexOf('=');
            if (eq <= 0) continue;
            try {
                out.put(part.substring(0, eq).trim(), Double.parseDouble(part.substring(eq + 1).trim()));
            } catch (NumberFormatException ignored) {
                // 건너뜀
            }
        }
        return out;
    }

    /**
     * 굴림 품질 0~1 = 각 스탯이 범위 안에서 차지하는 위치의 평균 (최소=최대인 고정 스탯은 제외).
     * 계산할 스탯이 없으면 -1.
     */
    public static double quality(ItemDef def, Map<String, Double> rolls) {
        if (def == null) return -1;
        double sum = 0;
        int n = 0;
        for (Map.Entry<String, Range> e : def.stats().entrySet()) {
            Range r = e.getValue();
            Double v = rolls.get(e.getKey());
            if (r == null || v == null || r.max() - r.min() <= 1e-9) continue;
            sum += Math.max(0, Math.min(1, (v - r.min()) / (r.max() - r.min())));
            n++;
        }
        return n == 0 ? -1 : sum / n;
    }
}
