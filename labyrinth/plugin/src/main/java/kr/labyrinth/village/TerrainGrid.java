package kr.labyrinth.village;

import java.util.Arrays;

/** 직사각형 영역의 열 데이터 (배열 저장). 비동기 스레드에서 채우고 읽는다 — 열마다 한 스레드만 쓴다. */
public final class TerrainGrid implements Terrain {

    public final int x0, z0, sx, sz;
    private final short[] ground;
    private final int[] holes;
    private final byte[] flags;
    private final short[] logs;
    private final String[] surface;
    private final String[] biome;
    private final String[] note;
    private final boolean[] filled;

    public TerrainGrid(int x0, int z0, int sx, int sz) {
        this.x0 = x0;
        this.z0 = z0;
        this.sx = sx;
        this.sz = sz;
        int n = sx * sz;
        ground = new short[n];
        holes = new int[n];
        flags = new byte[n];
        logs = new short[n];
        surface = new String[n];
        biome = new String[n];
        note = new String[n];
        filled = new boolean[n];
    }

    /** 중심 (cx, cz) 둘레 반경 r 정사각형. */
    public static TerrainGrid around(int cx, int cz, int r) {
        return new TerrainGrid(cx - r, cz - r, 2 * r + 1, 2 * r + 1);
    }

    private int idx(int x, int z) {
        int lx = x - x0, lz = z - z0;
        if (lx < 0 || lz < 0 || lx >= sx || lz >= sz) return -1;
        return lz * sx + lx;
    }

    public boolean contains(int x, int z) { return idx(x, z) >= 0; }

    public void set(int x, int z, int groundY, int holeBits, int flagBits, int logCount, String surf, String bio, String why) {
        int i = idx(x, z);
        if (i < 0) return;
        ground[i] = (short) groundY;
        holes[i] = holeBits;
        flags[i] = (byte) flagBits;
        logs[i] = (short) Math.min(Short.MAX_VALUE, logCount);
        surface[i] = surf == null ? null : surf.intern();
        biome[i] = bio == null ? null : bio.intern();
        note[i] = why;
        filled[i] = true;
    }

    /** 테스트용: 높이만 (잔디, 평원). */
    public void setGround(int x, int z, int y) { set(x, z, y, 0, 0, 0, "grass_block", "plains", null); }

    public void fill(int y) {
        for (int z = z0; z < z0 + sz; z++) for (int x = x0; x < x0 + sx; x++) setGround(x, z, y);
    }

    public void addFlags(int x, int z, int f, String why) {
        int i = idx(x, z);
        if (i < 0) return;
        flags[i] |= (byte) f;
        if (why != null) note[i] = why;
    }

    public void setHoles(int x, int z, int bits) {
        int i = idx(x, z);
        if (i >= 0) holes[i] = bits;
    }

    public int filledCount() {
        int n = 0;
        for (boolean b : filled) if (b) n++;
        return n;
    }

    public void clear() { Arrays.fill(filled, false); }

    @Override
    public boolean has(int x, int z) {
        int i = idx(x, z);
        return i >= 0 && filled[i];
    }

    @Override
    public int ground(int x, int z) {
        int i = idx(x, z);
        return i < 0 ? 0 : ground[i];
    }

    @Override
    public int holes(int x, int z) {
        int i = idx(x, z);
        return i < 0 ? 0 : holes[i];
    }

    @Override
    public int flags(int x, int z) {
        int i = idx(x, z);
        return i < 0 ? 0 : flags[i];
    }

    @Override
    public int logs(int x, int z) {
        int i = idx(x, z);
        return i < 0 ? 0 : logs[i];
    }

    @Override
    public String surface(int x, int z) {
        int i = idx(x, z);
        return i < 0 || surface[i] == null ? "grass_block" : surface[i];
    }

    @Override
    public String biome(int x, int z) {
        int i = idx(x, z);
        return i < 0 || biome[i] == null ? "?" : biome[i];
    }

    @Override
    public String note(int x, int z) {
        int i = idx(x, z);
        return i < 0 ? null : note[i];
    }
}
