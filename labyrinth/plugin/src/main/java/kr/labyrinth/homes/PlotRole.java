package kr.labyrinth.homes;

/** 집터에서 그 사람의 자리 (0.3.7). 소유: 묶음 B. */
public enum PlotRole {
    /** 주인. */
    OWNER,
    /** 주인이 초대한 사람 (짓기·부수기·상자 — 이름·초대·손님·비우기는 주인만). */
    TRUSTED,
    /** 손님 (손님 허용이 켜진 집: 문·작업대류·종·방문). */
    GUEST,
    /** 아무것도 못 함 (손님 허용 꺼짐 · 빈 집). */
    NONE;

    public boolean builds() { return this == OWNER || this == TRUSTED; }
}
