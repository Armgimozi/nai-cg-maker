package kr.labyrinth.village;

/**
 * 계획기({@link Planner})가 보는 원래 지형 (열 단위). 서버에서는 ChunkSnapshot 으로 채운 {@link TerrainGrid},
 * 테스트에서는 가짜 높이맵. 땅높이 = 나무·풀·눈·잎을 뺀 맨 위 자연 고체 블록의 y (VILLAGE.md §4.1 1번).
 */
public interface Terrain {

    /** 물·용암·얼음이 땅 위에 있음. */
    int WATER = 1;
    /** 사람이 지은/구조물 블록이 땅 근처(위 전부 + 아래 10칸)에 있음. */
    int UNNATURAL = 2;
    /** 맨 위에 눈 한 겹. */
    int SNOW = 4;
    /** 땅 위에 나무(원목·잎) 블록이 있음. */
    int TREE = 8;

    boolean has(int x, int z);

    int ground(int x, int z);

    /** 땅 아래 빈칸 비트: bit (k−1) = (ground − k) 칸이 공기/액체 (k = 1..16). */
    int holes(int x, int z);

    int flags(int x, int z);

    /** 땅 위 원목 블록 수. */
    int logs(int x, int z);

    /** 맨 윗 땅 블록 id (예 "grass_block"). */
    String surface(int x, int z);

    String biome(int x, int z);

    /** 물·구조물 이유 설명용 블록 이름과 y (없으면 null). */
    String note(int x, int z);

    default boolean flag(int x, int z, int f) { return (flags(x, z) & f) != 0; }
}
