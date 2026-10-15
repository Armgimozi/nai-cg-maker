package kr.labyrinth.dungeon.traps;

/**
 * 함정 하나의 자리 (순수 데이터, 층 원점 기준 타일). tiles = 밟으면 발동하는 칸 (packed {@code FloorLayout.pack}),
 * (x, z) = 기준 칸(가운데), (alongX, alongZ) = 복도가 이어지는 방향(단위), (crossX, crossZ) = 복도를 가로지르는 방향(단위),
 * walls = 발사구를 박을 양옆 벽 칸 (WALL 모양만, 없으면 빈 배열), elevation = 바닥 높이, phase = 주기 함정의 박자 어긋남(틱).
 * PIT 은 tiles 가 두 줄 (기준 줄 + along 쪽 한 줄).
 */
public record TrapSpot(int index, TrapType type, int x, int z, int[] tiles, int alongX, int alongZ, int crossX, int crossZ,
                       int[] walls, int elevation, int phase) {

    public boolean covers(int packed) {
        for (int t : tiles) if (t == packed) return true;
        return false;
    }
}
