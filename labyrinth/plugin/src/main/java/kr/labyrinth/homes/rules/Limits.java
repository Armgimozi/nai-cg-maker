package kr.labyrinth.homes.rules;

import java.util.EnumMap;
import java.util.Locale;
import java.util.Map;

/**
 * 집당 한도 (0.3.7) — 순수. 소유: 묶음 B.
 * <ul>
 *   <li>틱 부품: 깔때기·공급기·제작기·피스톤·끈끈이 피스톤·관측기 합 {@code tick_parts.total} (16), 그중 깔때기 {@code tick_parts.hoppers} (8).
 *       그 블록을 놓을 때만 그 집터 칸을 센다. 상자 개수는 세지 않는다 (상자는 틱을 안 씀).</li>
 *   <li>엔티티 (review R15): 동물 {@code entity_caps.animals} (24) · 장식 (갑옷 거치대 + 액자 + 그림) {@code entity_caps.decorations} (64).
 *       번식·알·놓기 때 센다.</li>
 * </ul>
 */
public final class Limits {

    private Limits() {}

    public enum Part { HOPPER, DROPPER, CRAFTER, PISTON, STICKY_PISTON, OBSERVER }

    /** 블록 id → 틱 부품 (아니면 null). */
    public static Part part(String block) {
        return switch (PlotRules.key(block)) {
            case "hopper" -> Part.HOPPER;
            case "dropper" -> Part.DROPPER;
            case "crafter" -> Part.CRAFTER;
            case "piston" -> Part.PISTON;
            case "sticky_piston" -> Part.STICKY_PISTON;
            case "observer" -> Part.OBSERVER;
            default -> null;
        };
    }

    public static Map<Part, Integer> emptyCounts() {
        Map<Part, Integer> m = new EnumMap<>(Part.class);
        for (Part p : Part.values()) m.put(p, 0);
        return m;
    }

    public static int total(Map<Part, Integer> counts) {
        int n = 0;
        for (int v : counts.values()) n += v;
        return n;
    }

    /**
     * 하나 더 놓아도 되나. counts = 지금 그 집에 있는 수 (놓을 블록은 빼고).
     *
     * @return null = 됨, 아니면 플레이어에게 보낼 글
     */
    public static String tickPart(Map<Part, Integer> counts, Part placing, int maxTotal, int maxHoppers) {
        if (placing == null) return null;
        int total = total(counts);
        if (total + 1 > maxTotal) return "장치(깔때기·공급기·제작기·피스톤·관측기)는 한 집에 " + maxTotal + "개까지 둘 수 있습니다.";
        if (placing == Part.HOPPER && counts.getOrDefault(Part.HOPPER, 0) + 1 > maxHoppers) {
            return "깔때기는 한 집에 " + maxHoppers + "개까지 둘 수 있습니다.";
        }
        return null;
    }

    /** 이미 한도를 넘었나 (자가 진단 over_cap). */
    public static boolean overTickParts(Map<Part, Integer> counts, int maxTotal, int maxHoppers) {
        return total(counts) > maxTotal || counts.getOrDefault(Part.HOPPER, 0) > maxHoppers;
    }

    public enum EntityKind { ANIMAL, DECORATION, OTHER }

    /**
     * 엔티티 종류 (EntityType 이름) → 셈 묶음.
     *
     * @param creature 동물처럼 기르는 것인가 (Animals · WaterMob · Golem — 런타임이 instanceof 로 알려 줌)
     */
    public static EntityKind entityKind(String type, boolean creature) {
        String t = type == null ? "" : type.trim().toLowerCase(Locale.ROOT);
        if (t.equals("armor_stand") || t.equals("item_frame") || t.equals("glow_item_frame") || t.equals("painting")) return EntityKind.DECORATION;
        return creature ? EntityKind.ANIMAL : EntityKind.OTHER;
    }

    /** current 마리가 있을 때 하나 더 되나. */
    public static boolean underCap(int current, int cap) { return current < cap; }

    public static String capMessage(EntityKind k, int cap) {
        return k == EntityKind.ANIMAL ? "동물은 한 집에 " + cap + "마리까지 둘 수 있습니다."
                : "거치대·액자·그림은 한 집에 합쳐서 " + cap + "개까지 둘 수 있습니다.";
    }
}
