package kr.labyrinth.homes;

/** 집 일(받기·비우기·초대 …)의 결과: 됐는가 + 플레이어에게 보낼 글 (MiniMessage, 짧게). 소유: 묶음 B. */
public record HomesResult(boolean ok, String message) {

    public static HomesResult ok(String message) { return new HomesResult(true, message); }

    public static HomesResult fail(String message) { return new HomesResult(false, message); }

    /** 아직 만들지 않은 일 (뼈대). */
    static HomesResult notReady() { return fail("집 기능을 준비하는 중입니다."); }
}
