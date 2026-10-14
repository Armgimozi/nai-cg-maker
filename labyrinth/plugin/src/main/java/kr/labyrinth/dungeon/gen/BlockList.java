package kr.labyrinth.dungeon.gen;

import java.util.Arrays;
import org.bukkit.block.data.BlockData;

/** 배치할 블록 목록 (월드 좌표를 long 하나로 압축 + BlockData). 같은 좌표를 다시 넣으면 나중 값이 이긴다(배치 순서대로). */
public final class BlockList {

    private long[] pos = new long[4096];
    private BlockData[] data = new BlockData[4096];
    private int size;

    public static long pack(int x, int y, int z) {
        return ((long) (x & 0x3FFFFFF) << 38) | ((long) (z & 0x3FFFFFF) << 12) | (y & 0xFFF);
    }

    public static int x(long p) { return (int) (p >> 38); }

    public static int y(long p) {
        int y = (int) (p & 0xFFF);
        return y >= 2048 ? y - 4096 : y;
    }

    public static int z(long p) { return (int) (p << 26 >> 38); }

    public void add(int x, int y, int z, BlockData d) {
        if (d == null) return;
        if (size == pos.length) {
            pos = Arrays.copyOf(pos, size * 2);
            data = Arrays.copyOf(data, size * 2);
        }
        pos[size] = pack(x, y, z);
        data[size] = d;
        size++;
    }

    public int size() { return size; }
    public long pos(int i) { return pos[i]; }
    public BlockData data(int i) { return data[i]; }

    /** 정리용: 좌표만 (중복 포함). */
    public long[] positions() { return Arrays.copyOf(pos, size); }
}
