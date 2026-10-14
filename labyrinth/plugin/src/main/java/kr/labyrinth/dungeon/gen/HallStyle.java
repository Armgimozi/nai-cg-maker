package kr.labyrinth.dungeon.gen;

/**
 * 복도 셀 모양 (GDD §5.4). 셀 안에서 통로가 어떻게 생겼는지만 정한다 — 셀 사이 출입구는 모두 가운데 3칸(로컬 11~13).
 * <ul>
 *   <li>{@link #CROSS} 가운데에서 곧게 뻗는 기본 복도</li>
 *   <li>{@link #BENT} 셀 안에서 꺾이는 복도 (직선 셀은 옆으로 비켜 가는 지그재그, 모퉁이 셀은 계단식/갈고리)</li>
 *   <li>{@link #NARROW} 한 칸 폭의 좁은 통로 (천장도 한 칸 낮음)</li>
 *   <li>{@link #PLAZA} 갈림길의 작은 교차 광장 (가운데 기둥)</li>
 *   <li>{@link #STAIRS} 직선 셀의 오르내리는 계단 (1~3칸 높이 단상)</li>
 *   <li>{@link #PILLARS} 기둥 숲 — 넓은 홀에 기둥이 줄지어 섬</li>
 *   <li>{@link #WARREN} 셀 안의 작은 미로 굴 (3×3 칸 짧은 통로, 안에도 작은 막다른 길)</li>
 *   <li>{@link #NOOK} 막다른 길 끝의 작은 구석 (곧게 또는 옆으로 꺾여 들어감 — 보물 상자·함정 자리)</li>
 *   <li>{@link #SECRET} 막다른 길 끝이 금 간 벽 — 부수면 숨은 작은 방</li>
 * </ul>
 */
public enum HallStyle {
    CROSS("곧은 복도"),
    BENT("꺾인 복도"),
    NARROW("좁은 통로"),
    PLAZA("교차 광장"),
    STAIRS("계단 복도"),
    PILLARS("기둥 숲"),
    WARREN("미로 굴"),
    NOOK("막다른 길"),
    SECRET("막다른 길");

    private final String displayName;

    HallStyle(String displayName) { this.displayName = displayName; }

    public String displayName() { return displayName; }

    /** 막다른 길(출구 1개) 전용 모양인가. */
    public boolean deadEnd() { return this == NOOK || this == SECRET; }
}
