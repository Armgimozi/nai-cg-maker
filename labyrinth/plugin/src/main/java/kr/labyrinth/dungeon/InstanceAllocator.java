package kr.labyrinth.dungeon;

import java.util.BitSet;

/**
 * 공허 월드의 격자 슬롯 배정 (순수 로직). 슬롯 i 의 원점 = (column×SPACING, row×SPACING), z ≥ 0 영역만 쓴다.
 * 한 층(최대 10×10 셀 + 투기장 + 추격 복도)은 약 300×450 블록이라 SPACING 2048 이면 서로 시야·청크가 겹치지 않는다.
 * <p>
 * <b>다른 모듈이 공허 월드에 지을 것은 z &lt; 0 영역을 쓴다</b> (ARCHITECTURE §4 dungeon 메모).
 */
public final class InstanceAllocator {

    public static final int SPACING = 2048;
    public static final int COLUMNS = 16;
    /** 첫 줄은 월드 원점(스폰 근처)을 피해 1줄 띄운다. */
    public static final int FIRST_ROW = 1;

    private final BitSet used = new BitSet();
    private final int max;

    public InstanceAllocator(int maxSlots) { this.max = Math.max(1, maxSlots); }

    /** 빈 슬롯 번호 (없으면 -1). */
    public synchronized int allocate() {
        int i = used.nextClearBit(0);
        if (i >= max) return -1;
        used.set(i);
        return i;
    }

    /** 이전 세션이 남긴 블록이 있을 수 있는 슬롯 — 이번 세션에선 배정하지 않는다. */
    public synchronized void reserve(int slot) {
        if (slot >= 0) used.set(slot);
    }

    public synchronized void release(int slot) {
        if (slot >= 0) used.clear(slot);
    }

    public synchronized boolean inUse(int slot) { return used.get(slot); }

    public synchronized int inUseCount() { return used.cardinality(); }

    public int max() { return max; }

    public static int originX(int slot) { return (slot % COLUMNS) * SPACING; }

    public static int originZ(int slot) { return (slot / COLUMNS + FIRST_ROW) * SPACING; }

    /** 블록 좌표가 속한 슬롯 (슬롯 영역 밖이면 -1). */
    public static int slotAt(int blockX, int blockZ) {
        if (blockX < 0 || blockZ < FIRST_ROW * SPACING) return -1;
        int col = blockX / SPACING, row = blockZ / SPACING - FIRST_ROW;
        if (col >= COLUMNS) return -1;
        return row * COLUMNS + col;
    }
}
