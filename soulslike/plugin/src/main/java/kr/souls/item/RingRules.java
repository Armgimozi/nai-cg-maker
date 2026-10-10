package kr.souls.item;

/**
 * 반지 칸의 판정 (9.4). 순수 클래스: 13.1 의 RingRulesTest 가 표를 본다. {@link RingSlots} 가 클릭마다 묻고 그 답대로 한다.
 *
 * 칸 번호는 플레이어 인벤토리 창 (창 번호 0, 바닐라 InventoryMenu) 의 날 칸 번호다:
 *   0 결과 칸, 1 2×2 왼쪽 위, 2 오른쪽 위, 3 왼쪽 아래, 4 오른쪽 아래, 5..8 갑옷, 9..35 가방, 36..44 단축 슬롯, 45 왼손.
 * 반지 칸은 왼쪽 세로 두 칸 (1, 3 = 반지 칸 0, 1. 2026-10-08 사용자 결정 B 안). 나머지 셋 (0, 2, 4) 은 그림에서 지웠고 아무것도
 * 받지도 내주지도 않는다 (2×2 제작은 없다).
 *
 * 반지 칸 (1, 3) 에서
 *   왼쪽·오른쪽 누르기   손이 비고 칸에 반지 → 빼서 손에 (TAKE). 손에 반지·칸이 빔 → 낀다 (PUT). 둘 다 반지 → 바꾼다 (SWAP_CURSOR).
 *                       손에 반지가 아닌 것 → 거절.
 *   웅크리고 누르기      칸에 반지 → 가방 (없으면 단축 슬롯) 의 빈 칸으로 뺀다 (TO_STORAGE). 자리가 없으면 RingSlots 가 거절한다.
 *   숫자 키·왼손 바꾸기  그 단축 칸 (왼손) 과 반지 칸을 바꾼다 (SWAP_WITH): 저쪽이 반지이거나 비었을 때만, 둘 다 비면 거절.
 *   버리기 (Q, Ctrl+Q), 두 번 누르기, 가운데 누르기, 창작 모드 칸 쓰기, 그 밖 → 거절 (낀 반지는 빼서 버린다).
 * 반지 칸 밖에서
 *   웅크리고 누른 것이 반지이고 빈 반지 칸이 있으면 → 그 칸에 낀다 (EQUIP_FROM). 반지 칸이 차 있으면 바닐라 그대로 (가방 ↔ 단축 슬롯).
 *   손에 반지를 들고 두 번 누르기 (같은 것 모으기) → 거절 (반지는 한 칸에 하나라 모을 것이 없지만, 반지 칸에서 집어 오지 않게).
 *   그 밖 → 바닐라 그대로 (PASS).
 * 같은 반지 둘은 끼지 않는다 (다크 소울처럼, {@link #duplicate}): RingSlots 가 끼기 전에 본다.
 * 끌기 (여러 칸에 나눠 놓기) 가 2×2 칸에 닿으면 RingSlots 가 통째로 거절한다 (반지는 한 칸에 하나라 바닐라 클라이언트는 반지를
 * 끌지 않고 한 칸 누르기로 보낸다).
 */
public final class RingRules {
    /** 결과 칸 */
    public static final int RESULT = 0;
    /** 반지 칸 → 날 칸 번호 (2×2 의 왼쪽 위, 왼쪽 아래) */
    private static final int[] RING_RAW = {1, 3};

    /** 누르기 종류 (Bukkit ClickType 을 줄인 것) */
    public enum Kind { LEFT, RIGHT, SHIFT, NUMBER, OFFHAND, DROP, DOUBLE, MIDDLE, CREATIVE, OTHER }

    /** 칸·손에 있는 것 */
    public enum Thing { EMPTY, RING, OTHER }

    /** 할 일 */
    public enum Act { PASS, DENY, PUT, TAKE, SWAP_CURSOR, TO_STORAGE, SWAP_WITH, EQUIP_FROM }

    /** 판정: 할 일과 반지 칸 (0, 1. 반지 칸과 상관없으면 -1). */
    public record Decision(Act act, int ring) {
        static final Decision PASS = new Decision(Act.PASS, -1);
        static final Decision DENY = new Decision(Act.DENY, -1);
    }

    private RingRules() {}

    /** 날 칸 번호 → 반지 칸 (0, 1), 반지 칸이 아니면 -1. */
    public static int ringIndex(int raw) {
        return raw == RING_RAW[0] ? 0 : raw == RING_RAW[1] ? 1 : -1;
    }

    /** 반지 칸 → 날 칸 번호. */
    public static int rawOf(int ring) {
        return RING_RAW[ring];
    }

    /** 2×2 자리 (결과 칸 포함, 0..4). */
    public static boolean craftArea(int raw) {
        return raw >= 0 && raw <= 4;
    }

    /**
     * @param raw    누른 칸 (날 칸 번호. 창 밖은 -999)
     * @param kind   누르기 종류
     * @param cursor 손 (커서) 에 든 것
     * @param slot   누른 칸에 있는 것
     * @param other  숫자 키면 그 단축 칸, 왼손 바꾸기면 왼손에 있는 것 (그 밖은 무엇이든 상관없다)
     * @param free   비어 있는 첫 반지 칸 (0, 1), 없으면 -1
     */
    public static Decision decide(int raw, Kind kind, Thing cursor, Thing slot, Thing other, int free) {
        int ring = ringIndex(raw);
        if (craftArea(raw) && ring < 0) return Decision.DENY;
        if (ring >= 0) {
            switch (kind) {
                case LEFT, RIGHT -> {
                    if (cursor == Thing.EMPTY) return slot == Thing.RING ? new Decision(Act.TAKE, ring) : Decision.DENY;
                    if (cursor != Thing.RING) return Decision.DENY;
                    if (slot == Thing.EMPTY) return new Decision(Act.PUT, ring);
                    return slot == Thing.RING ? new Decision(Act.SWAP_CURSOR, ring) : Decision.DENY;
                }
                case SHIFT -> {
                    return slot == Thing.RING ? new Decision(Act.TO_STORAGE, ring) : Decision.DENY;
                }
                case NUMBER, OFFHAND -> {
                    if (other == Thing.OTHER || slot == Thing.OTHER) return Decision.DENY;
                    if (other == Thing.EMPTY && slot == Thing.EMPTY) return Decision.DENY;
                    return new Decision(Act.SWAP_WITH, ring);
                }
                default -> {
                    return Decision.DENY;
                }
            }
        }
        if (kind == Kind.SHIFT && slot == Thing.RING && free >= 0) return new Decision(Act.EQUIP_FROM, free);
        if (kind == Kind.DOUBLE && cursor == Thing.RING) return Decision.DENY;
        return Decision.PASS;
    }

    /** 반지 칸 ring 에 id 를 끼면 다른 반지 칸과 같은 반지가 되나 (같은 반지 둘은 끼지 않는다). worn = 칸마다 낀 id. */
    public static boolean duplicate(String[] worn, int ring, String id) {
        if (id == null || worn == null) return false;
        for (int i = 0; i < worn.length; i++) {
            if (i != ring && id.equals(worn[i])) return true;
        }
        return false;
    }

    /** 비어 있는 첫 반지 칸, 없으면 -1. */
    public static int firstFree(String[] worn) {
        for (int i = 0; i < worn.length; i++) if (worn[i] == null) return i;
        return -1;
    }
}
