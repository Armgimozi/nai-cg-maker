package kr.labyrinth.homes.play;

/** 집 놀이 쪽 이름 (0.3.7) — npcs.yml role · 구역 우클릭 동작 · PlayerData ext 키. */
public final class HomesNames {

    private HomesNames() {}

    /** npcs.yml role: 마을 관리인 (관리인 메뉴). ContentValidator.NPC_ROLES · NpcServiceImpl 이 씀. */
    public static final String ROLE_ESTATE = "estate";
    /** 구역 조각 우클릭 동작: 관리인 노점 계산대 (VillageService.openMenu 가 집 모듈로 넘김). */
    public static final String INTERACT_ESTATE = "estate";
    /** 대문 표지판 우클릭 동작 접두어 (plot:&lt;번지&gt;). */
    public static final String INTERACT_PLOT = "plot:";
    /** 관리인 NPC id (구역 조각 keeper_stall 의 npc 표시). */
    public static final String NPC_ESTATE = "estate_keeper";
    /** PlayerData ext: 시작 선물을 받음 · 받은 것 (kit · cottage_oak …) · 마지막 침대 쉬기 (epoch ms). */
    public static final String EXT_STARTER_USED = StarterGift.EXT_USED;
    public static final String EXT_STARTER_KIND = StarterGift.EXT_KIND;
    public static final String EXT_REST_AT = "homes.rest_at";
}
