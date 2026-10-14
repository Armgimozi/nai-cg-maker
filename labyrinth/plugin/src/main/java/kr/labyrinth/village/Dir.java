package kr.labyrinth.village;

import java.util.Locale;

/**
 * 수평 네 방향 (시계 방향 순서 N → E → S → W). 월드 축 그대로: 북 = −Z, 동 = +X, 남 = +Z, 서 = −X.
 * 회전 수 {@code turns} 는 시계 방향 90° 단위 (VILLAGE.md §2.1 의 StructureRotation 과 같은 뜻).
 */
public enum Dir {
    NORTH(0, -1), EAST(1, 0), SOUTH(0, 1), WEST(-1, 0);

    public final int dx;
    public final int dz;

    Dir(int dx, int dz) {
        this.dx = dx;
        this.dz = dz;
    }

    /** 시계 방향으로 turns 번 (음수 = 반시계). */
    public Dir rotate(int turns) {
        return values()[Math.floorMod(ordinal() + turns, 4)];
    }

    public Dir opposite() { return rotate(2); }

    /** 이 방향을 바라보는 마인크래프트 yaw (남 0, 서 90, 북 180, 동 −90). */
    public float yaw() {
        return switch (this) {
            case SOUTH -> 0f;
            case WEST -> 90f;
            case NORTH -> 180f;
            case EAST -> -90f;
        };
    }

    /** 블록 상태 이름 ("north" …). */
    public String key() { return name().toLowerCase(Locale.ROOT); }

    /** 이 방향이 NORTH 에서 시계 방향으로 몇 번 돌린 것인지 (0..3). */
    public int turns() { return ordinal(); }

    /** "north"/"n"/"북" 등 → 방향. 모르면 null. */
    public static Dir parse(String s) {
        if (s == null) return null;
        return switch (s.trim().toLowerCase(Locale.ROOT)) {
            case "north", "n", "북", "북쪽" -> NORTH;
            case "east", "e", "동", "동쪽" -> EAST;
            case "south", "s", "남", "남쪽" -> SOUTH;
            case "west", "w", "서", "서쪽" -> WEST;
            default -> null;
        };
    }

    /**
     * 마커 face (정방향 기준) → 방향: front = 북(정면이 보는 쪽), back = 남,
     * left = 서(−X), right = 동(+X) — 건물이 북쪽을 볼 때 건물 기준 왼손/오른손 (VILLAGE.md §2.4).
     * 방향 이름(north 등)도 받는다. 모르면 front.
     */
    public static Dir face(String s) {
        if (s == null) return NORTH;
        String k = s.trim().toLowerCase(Locale.ROOT);
        return switch (k) {
            case "front", "f" -> NORTH;
            case "back", "b" -> SOUTH;
            case "left", "l" -> WEST;
            case "right", "r" -> EAST;
            default -> {
                Dir d = parse(k);
                yield d == null ? NORTH : d;
            }
        };
    }
}
