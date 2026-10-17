package kr.labyrinth.homes;

import java.util.Locale;

/**
 * 집터 하나의 모양 (0.3.7 집 구역) — 순수 자료. 소유: 묶음 A (더하기만).
 * <ul>
 *   <li>{@code id}: 구역 집터 "1".."10", 관리자 convert 집터 "c1", "c2" …</li>
 *   <li>{@code key}: 색인·zone 값 (1 이상, 같은 서버에서 겹치지 않음 — 구역 집터는 번호, convert 는 100 + n)</li>
 *   <li>상자 x0..x1 · z0..z1 (블록, 양 끝 포함) · 바닥 {@code floorY} (잔디 윗면 블록 y) · 짓기 높이 창 {@code yMin..yMax} (양 끝 포함)</li>
 *   <li>{@code front}: 대문 쪽 "N"·"S"·"E"·"W" · 대문 칸 (gateX, gateZ) · 표지판 칸 (signX, signY, signZ) · 집 가기 칸 (homeX, homeY, homeZ, homeYaw)</li>
 * </ul>
 * 구역 기록 {@code labyrinth-district-homes.yml plots:} 에서 묶음 A 가 만들고 {@link HomesDistrict#publish} 로 알린다.
 * 지어지기 전 설계값({@link HomesLayout})은 signY = {@link Integer#MIN_VALUE}, homeY = NaN (모름).
 */
public record PlotGeom(String id, int key, int x0, int z0, int x1, int z1, int floorY, int yMin, int yMax, String front,
                       int gateX, int gateZ, int signX, int signY, int signZ, double homeX, double homeY, double homeZ, float homeYaw,
                       boolean custom) {

    public PlotGeom {
        if (id == null || id.isBlank()) throw new IllegalArgumentException("집터 id 없음");
        if (key <= 0) throw new IllegalArgumentException("집터 key 는 1 이상: " + key);
        int ax = Math.min(x0, x1), bx = Math.max(x0, x1), az = Math.min(z0, z1), bz = Math.max(z0, z1);
        x0 = ax;
        x1 = bx;
        z0 = az;
        z1 = bz;
        int ay = Math.min(yMin, yMax), by = Math.max(yMin, yMax);
        yMin = ay;
        yMax = by;
        front = front == null ? "S" : front.trim().toUpperCase(Locale.ROOT);
    }

    /** 열 (x, z) 가 집터 상자 안인가 (높이 무관). */
    public boolean containsColumn(int x, int z) { return x >= x0 && x <= x1 && z >= z0 && z <= z1; }

    /** (x, y, z) 가 집터 상자 + 높이 창 안인가. */
    public boolean contains(int x, int y, int z) { return containsColumn(x, z) && y >= yMin && y <= yMax; }

    public int width() { return x1 - x0 + 1; }

    public int depth() { return z1 - z0 + 1; }

    /** 플레이어에게 보이는 이름: "3번지" · convert 는 "c1". */
    public String label() { return custom ? id : id + "번지"; }

    /** 집 가기 칸 높이를 아는가 (지은 뒤 기록에서 온 값). */
    public boolean homeKnown() { return !Double.isNaN(homeY); }
}
