package kr.labyrinth.village;

import java.util.LinkedHashMap;
import java.util.Map;
import org.bukkit.block.structure.StructureRotation;

/**
 * 회전 공식 (VILLAGE.md §2.1). 회전은 시계 방향 90° 단위 turns (0 = NONE, 1 = CLOCKWISE_90, 2 = CLOCKWISE_180,
 * 3 = COUNTERCLOCKWISE_90). 서버 없이 쓸 수 있는 순수 함수만 둔다 — 실제 블록 상태 회전은 {@code BlockData#rotate}
 * 가 하고, {@link #rotateState} 는 단위 테스트와 자가 진단 대조용 같은 규칙의 문자열 구현이다.
 */
public final class Rot {

    private Rot() {}

    public static int turns(StructureRotation r) {
        return switch (r) {
            case NONE -> 0;
            case CLOCKWISE_90 -> 1;
            case CLOCKWISE_180 -> 2;
            case COUNTERCLOCKWISE_90 -> 3;
        };
    }

    public static StructureRotation of(int turns) {
        return switch (Math.floorMod(turns, 4)) {
            case 1 -> StructureRotation.CLOCKWISE_90;
            case 2 -> StructureRotation.CLOCKWISE_180;
            case 3 -> StructureRotation.COUNTERCLOCKWISE_90;
            default -> StructureRotation.NONE;
        };
    }

    /** 정면 방향 → 회전 (앞이 북 = NONE, 동 = CLOCKWISE_90, 남 = CLOCKWISE_180, 서 = COUNTERCLOCKWISE_90). */
    public static StructureRotation forFront(Dir front) { return of(front.turns()); }

    /** 회전 후 발자국 크기 [W', D']. */
    public static int[] dims(int w, int d, int turns) {
        return (Math.floorMod(turns, 4) % 2 == 0) ? new int[] {w, d} : new int[] {d, w};
    }

    /**
     * 정방향 W×D 상자 안 (x, z) → 회전 후 상자 안 좌표 (§2.1 표):
     * NONE (x, z) · CW90 (D−1−z, x) · CW180 (W−1−x, D−1−z) · CCW90 (z, W−1−x).
     */
    public static int[] inBox(int x, int z, int w, int d, int turns) {
        return switch (Math.floorMod(turns, 4)) {
            case 1 -> new int[] {d - 1 - z, x};
            case 2 -> new int[] {w - 1 - x, d - 1 - z};
            case 3 -> new int[] {z, w - 1 - x};
            default -> new int[] {x, z};
        };
    }

    /** 원점 둘레 회전 (마을 좌표 → 회전된 마을 좌표). CW90: (x, z) → (−z, x) — 북쪽(−Z)이 동쪽(+X)으로. */
    public static int[] around(int x, int z, int turns) {
        return switch (Math.floorMod(turns, 4)) {
            case 1 -> new int[] {-z, x};
            case 2 -> new int[] {-x, -z};
            case 3 -> new int[] {z, -x};
            default -> new int[] {x, z};
        };
    }

    // ── 블록 상태 문자열 회전 (BlockData#rotate 와 같은 규칙) ─────────────────────

    /** "minecraft:oak_stairs[facing=north,half=bottom]" → 이름 + 속성 (순서 유지). */
    static Map<String, String> props(String state) {
        Map<String, String> out = new LinkedHashMap<>();
        int i = state.indexOf('[');
        if (i < 0 || !state.endsWith("]")) return out;
        String body = state.substring(i + 1, state.length() - 1).trim();
        if (body.isEmpty()) return out;
        for (String kv : body.split(",")) {
            int e = kv.indexOf('=');
            if (e < 0) continue;
            out.put(kv.substring(0, e).trim(), kv.substring(e + 1).trim());
        }
        return out;
    }

    static String name(String state) {
        int i = state.indexOf('[');
        return (i < 0 ? state : state.substring(0, i)).trim();
    }

    private static String rotDir(String v, int t) {
        Dir d = Dir.parse(v);
        return d == null ? v : d.rotate(t).key();
    }

    /** 레일 shape: north_south ↔ east_west, ascending_east → ascending_(회전), 굽은 레일은 두 방향 모두 회전 후 바닐라 이름 순서로. */
    private static String rotRailShape(String v, int t) {
        if (v.equals("north_south") || v.equals("east_west")) return t % 2 == 0 ? v : (v.equals("north_south") ? "east_west" : "north_south");
        if (v.startsWith("ascending_")) return "ascending_" + rotDir(v.substring("ascending_".length()), t);
        String[] p = v.split("_");
        if (p.length != 2 || Dir.parse(p[0]) == null || Dir.parse(p[1]) == null) return v;
        Dir a = Dir.parse(p[0]).rotate(t), b = Dir.parse(p[1]).rotate(t);
        // 바닐라 이름: south_east, south_west, north_west, north_east (남/북이 먼저)
        Dir ns = (a == Dir.NORTH || a == Dir.SOUTH) ? a : b;
        Dir ew = ns == a ? b : a;
        return ns.key() + "_" + ew.key();
    }

    /** jigsaw/crafter orientation "<앞>_<위>" — 수평 성분만 회전. */
    private static String rotOrientation(String v, int t) {
        String[] p = v.split("_");
        if (p.length != 2) return v;
        return rotDir(p[0], t) + "_" + rotDir(p[1], t);
    }

    /**
     * 블록 상태 문자열을 시계 방향 turns 번 돌린다: facing · axis(x↔z) · rotation(+4t mod 16) · north/east/south/west
     * 연결 속성 · 레일 shape · orientation. hinge/half/type/part/attachment/face 같은 상대 속성은 그대로.
     */
    public static String rotateState(String state, int turns) {
        int t = Math.floorMod(turns, 4);
        Map<String, String> p = props(state);
        if (t == 0 || p.isEmpty()) return state;
        Map<String, String> out = new LinkedHashMap<>();
        Map<Dir, String> sides = new java.util.EnumMap<>(Dir.class);
        boolean sidesPlaced = false;
        for (Map.Entry<String, String> e : p.entrySet()) {
            String k = e.getKey(), v = e.getValue();
            if (isSide(k)) {
                if (!sidesPlaced) {
                    out.put("\0sides", null); // 연결 속성 자리 (원래 첫 연결 속성 위치)
                    sidesPlaced = true;
                }
                sides.put(Dir.parse(k).rotate(t), v);
                continue;
            }
            String nv = switch (k) {
                case "facing", "horizontal_facing" -> rotDir(v, t);
                case "axis" -> (t % 2 == 1 && (v.equals("x") || v.equals("z"))) ? (v.equals("x") ? "z" : "x") : v;
                case "rotation" -> {
                    try {
                        yield String.valueOf(Math.floorMod(Integer.parseInt(v) + 4 * t, 16));
                    } catch (NumberFormatException ex) {
                        yield v;
                    }
                }
                case "shape" -> (v.contains("north") || v.contains("south") || v.contains("east") || v.contains("west"))
                        && !v.startsWith("inner_") && !v.startsWith("outer_") ? rotRailShape(v, t) : v;
                case "orientation" -> rotOrientation(v, t);
                default -> v;
            };
            out.put(k, nv);
        }
        StringBuilder sb = new StringBuilder(name(state)).append('[');
        boolean first = true;
        for (Map.Entry<String, String> e : out.entrySet()) {
            if (e.getKey().equals("\0sides")) {
                for (Map.Entry<Dir, String> s : sides.entrySet()) { // N, E, S, W 순서
                    if (!first) sb.append(',');
                    first = false;
                    sb.append(s.getKey().key()).append('=').append(s.getValue());
                }
                continue;
            }
            if (!first) sb.append(',');
            first = false;
            sb.append(e.getKey()).append('=').append(e.getValue());
        }
        return sb.append(']').toString();
    }

    private static boolean isSide(String k) {
        return k.equals("north") || k.equals("east") || k.equals("south") || k.equals("west");
    }
}
