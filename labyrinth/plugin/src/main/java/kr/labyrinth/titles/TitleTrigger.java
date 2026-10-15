package kr.labyrinth.titles;

import kr.labyrinth.content.Rarity;

/**
 * 칭호 판정을 일으킨 사건 하나 (순수 값 — Bukkit 무관, 단위 테스트 대상). 칭호는 이런 사건이 일어난 그 순간에만
 * 판정한다(접속·재접속·리로드로는 절대 주지 않는다). {@link AchievementRules#qualifies} 가 이 사건이 그 칭호의 조건을
 * 채우는지 본다 — 한 번에 끝나는 위업(혼자 돌파·무사망·난이도·시간·강화 단계)은 이 사건 자체로, 누적 조건(처치 수·제작 수 …)은
 * 이 사건이 그 조건에 맞는 것일 때 누적 카운터로.
 *
 * @param kind       사건 종류
 * @param floor      CLEAR: 돌파한 층
 * @param partySize  CLEAR: 입장 인원
 * @param deaths     CLEAR: 그 층에서 쓰러진 횟수
 * @param seconds    CLEAR: 그 층 시작~보스 처치 시간(초)
 * @param difficulty CLEAR: 서버 난이도 id
 * @param firstClear CLEAR: 이 돌파가 그 층의 서버 최초 돌파 기록(records.yml first_clear.floor_N)을 세웠는가
 * @param mobId      KILL: 몹·보스 id
 * @param rank       KILL: 몹 등급 normal|elite|add (보스면 null)
 * @param boss       KILL: 보스인가
 * @param rarity     OBTAIN·CRAFT: 장비 희귀도
 * @param level      LEVEL: 새 레벨 · ENHANCE: 강화 성공으로 오른 단계
 * @param fromLevel  LEVEL: 이전 레벨
 * @param treasure   TREASURE: chest | gold_chest | vault | mimic
 */
public record TitleTrigger(Kind kind, int floor, int partySize, int deaths, double seconds, String difficulty,
                           boolean firstClear, String mobId, String rank, boolean boss, Rarity rarity, int level,
                           int fromLevel, String treasure) {

    public enum Kind { CLEAR, KILL, LEVEL, OBTAIN, CRAFT, ENHANCE, TREASURE }

    public static TitleTrigger clear(int floor, int partySize, int deaths, double seconds, String difficulty, boolean firstClear) {
        return new TitleTrigger(Kind.CLEAR, floor, partySize, deaths, seconds, difficulty, firstClear, null, null, false, null, 0, 0, null);
    }

    public static TitleTrigger kill(String mobId, String rank, boolean boss) {
        return new TitleTrigger(Kind.KILL, 0, 0, 0, 0, null, false, mobId, rank, boss, null, 0, 0, null);
    }

    public static TitleTrigger level(int from, int to) {
        return new TitleTrigger(Kind.LEVEL, 0, 0, 0, 0, null, false, null, null, false, null, to, from, null);
    }

    public static TitleTrigger obtain(Rarity rarity) {
        return new TitleTrigger(Kind.OBTAIN, 0, 0, 0, 0, null, false, null, null, false, rarity, 0, 0, null);
    }

    public static TitleTrigger craft(Rarity rarity) {
        return new TitleTrigger(Kind.CRAFT, 0, 0, 0, 0, null, false, null, null, false, rarity, 0, 0, null);
    }

    /** 강화 성공으로 to 단계가 됨 (실패는 사건이 아니다). */
    public static TitleTrigger enhance(int to) {
        return new TitleTrigger(Kind.ENHANCE, 0, 0, 0, 0, null, false, null, null, false, null, to, 0, null);
    }

    public static TitleTrigger treasure(String kind) {
        return new TitleTrigger(Kind.TREASURE, 0, 0, 0, 0, null, false, null, null, false, null, 0, 0, kind);
    }
}
