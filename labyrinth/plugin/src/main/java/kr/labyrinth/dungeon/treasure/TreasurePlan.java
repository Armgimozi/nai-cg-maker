package kr.labyrinth.dungeon.treasure;

import java.util.List;

/**
 * 한 층의 미로 보물 배치 (순수 데이터, 층 원점 기준 타일). 보물방(TreasureRoom) 상자는 여기 없다 — 방이 따로 관리.
 *
 * @param chests      상자 전부 (막다른 길·미로 굴·비밀방·금고 안)
 * @param vault       열쇠 금고 (없으면 null)
 * @param keyChest    열쇠가 든 상자 번호 (-1 = 상자 아님)
 * @param keyFromElite 열쇠가 정예 처치에서 나오는가
 */
public record TreasurePlan(List<Chest> chests, Vault vault, int keyChest, boolean keyFromElite) {

    public static final TreasurePlan EMPTY = new TreasurePlan(List.of(), null, -1, false);

    public TreasurePlan {
        chests = List.copyOf(chests);
    }

    /** 상자 출처. */
    public enum Source { DEAD_END, MINOR, SECRET, VAULT }

    /**
     * 상자 하나. (x, z) = 상자 칸, (dirX, dirZ) = 상자가 바라보는 쪽(플레이어가 오는 쪽), ref = 막다른 길 번호(DEAD_END·MINOR)
     * 또는 비밀방 번호(SECRET) 또는 -1(VAULT).
     */
    public record Chest(int index, int x, int z, int dirX, int dirZ, ChestTier tier, Source source, boolean mimic, int ref) {
        public Chest withTier(ChestTier t) { return new Chest(index, x, z, dirX, dirZ, t, source, mimic, ref); }
        public Chest withMimic(boolean m) { return new Chest(index, x, z, dirX, dirZ, tier, source, m, ref); }
    }

    /**
     * 열쇠 금고: 막다른 구석(NOOK) 끝 5×5 칸을 잠긴 문으로 막은 방. door = 문 줄 타일(packed, 가운데 = doorX/doorZ,
     * 양옆 도랑 칸 포함), 안쪽 = minX..maxX × minZ..maxZ, chests = 안의 금 상자 번호, (dirX, dirZ) = 금고 → 복도 방향.
     */
    public record Vault(int deadEnd, int doorX, int doorZ, int[] door, int minX, int minZ, int maxX, int maxZ,
                        int dirX, int dirZ, List<Integer> chests) {
        public Vault {
            chests = List.copyOf(chests);
        }

        public boolean contains(int x, int z) { return x >= minX && x <= maxX && z >= minZ && z <= maxZ; }
    }

    public int count(ChestTier t) {
        int n = 0;
        for (Chest c : chests) if (c.tier() == t) n++;
        return n;
    }

    public int mimics() {
        int n = 0;
        for (Chest c : chests) if (c.mimic()) n++;
        return n;
    }
}
