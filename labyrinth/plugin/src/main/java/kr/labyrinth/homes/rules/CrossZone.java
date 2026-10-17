package kr.labyrinth.homes.rules;

/**
 * 경계 넘는 것 (0.3.7, plan §9 "경계 넘는 것") — zone 값만 보는 순수 규칙. 소유: 묶음 B.
 * zone = 집터 key (1 이상) · 0 = 보호 상자 · −1 = 그 밖. 런타임 ({@link CrossZoneListener}) 이 칸마다 zone 을 구해 넘긴다.
 */
public final class CrossZone {

    private CrossZone() {}

    /** 물·용암 흐름: 출발 zone = 도착 zone 일 때만 (밖 → 밖 자연 물은 그대로). */
    public static boolean flow(int from, int to) { return from == to; }

    /** 깔때기·공급기 옮김: 보내는 곳·받는 곳 zone 같음. */
    public static boolean transfer(int source, int destination) { return source == destination; }

    /** 깔때기 줍기: 아이템 zone = 깔때기 zone. */
    public static boolean pickup(int item, int hopper) { return item == hopper; }

    /** 모든 칸이 origin 과 같은 zone 인가 (나무·큰 버섯 자람, 뼛가루 결과, 차원문 …). */
    public static boolean allSame(int origin, int[] zones) {
        if (zones != null) for (int z : zones) if (z != origin) return false;
        return true;
    }

    /**
     * 피스톤: 집터 안 피스톤 → 움직이는 블록·도착 칸이 모두 같은 집터. 집터 밖 피스톤 → 잠금 켜진 들판이면 취소,
     * 그 밖 (보호 상자 · 잠금 꺼진 들판) 은 집터 칸을 건드리지 않을 때만.
     */
    public static boolean piston(int piston, int[] cells, boolean locked) {
        if (piston > 0) return allSame(piston, cells);
        if (piston < 0 && locked) return false;
        if (cells != null) for (int z : cells) if (z > 0) return false;
        return true;
    }

    /** 퍼짐 (덩굴·버섯·잔디·이끼·스컬크): 출발 = 도착. 불 퍼짐은 늘 취소. */
    public static boolean spread(int source, int target, boolean fire) { return !fire && source == target; }

    /** 떨어지는 블록: 떨어지기 시작한 칸 zone = 내려앉는 칸 zone. */
    public static boolean falling(int origin, int target) { return origin == target; }

    /**
     * 발사기 (review R4): 발사기·앞 칸이 같은 집터일 때만. 집터 밖 발사기는 잠금 꺼진 들판에서 앞 칸도 들판일 때만.
     */
    public static boolean dispense(int dispenser, int front, boolean locked) {
        if (dispenser > 0) return front == dispenser;
        if (dispenser < 0) return !locked && front < 0;
        return false;
    }

    /** 구리 골렘이 옮길 상자: 골렘 zone = 상자 zone. */
    public static boolean golem(int golem, int target) { return golem == target; }

    /** 스펀지: 그 칸을 빨아들여도 되나. */
    public static boolean sponge(int sponge, int cell) { return sponge == cell; }

    /** 플레이어가 붙인 차원문 (잠금 켜짐): 모든 칸이 그 사람 집 key 안. */
    public static boolean portalByPlayer(int ownKey, int[] zones) { return ownKey > 0 && allSame(ownKey, zones); }

    /** 게임이 만드는 돌아오는 차원문 (NETHER_PAIR, 잠금 켜짐): 집터 하나 안일 때만. */
    public static boolean portalPair(int[] zones) {
        if (zones == null || zones.length == 0) return true;
        return zones[0] > 0 && allSame(zones[0], zones);
    }

    /**
     * 플레이어가 아닌 것이 블록을 바꿈. 잠금 꺼진 들판은 그대로. 망가뜨리는 것 (엔더맨·파괴수·위더·좀비 문 부수기·좀벌레·발사체 …) 은
     * 집터·보호 칸·잠긴 들판에서 막고, 그 밖 (양 풀 먹기·주민 농사·여우 열매 …) 은 엔티티와 블록이 같은 zone 일 때만.
     */
    public static boolean mobChange(int entityZone, int blockZone, boolean griefer, boolean locked) {
        if (blockZone < 0 && !locked) return true;
        if (griefer) return false;
        return entityZone == blockZone;
    }

    /** 눈 골렘 자국·차가운 걸음: 집 밖이면 취소 (잠금 꺼진 들판은 그대로). */
    public static boolean entityForm(int zone, boolean locked) { return zone > 0 || (zone < 0 && !locked); }
}
