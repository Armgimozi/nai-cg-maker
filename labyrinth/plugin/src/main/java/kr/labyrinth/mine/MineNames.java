package kr.labyrinth.mine;

import java.util.List;

/**
 * 0.3.6 광산 — 패키지끼리 맞춘 이름 (Q0 계약: tools/data/036/mine.json {@code names} · design/036/CONTRACT.md §3).
 * 값을 바꾸면 check_contract.py 가 잡는다. 여러 패키지가 문자열을 따로 쓰지 말고 이 상수를 쓴다.
 */
public final class MineNames {

    private MineNames() {}

    /** 광산 월드 이름 (config mine.world 기본값). */
    public static final String WORLD = "labyrinth_mine";

    // ── 우클릭 칸 (village interact · 광산 청사진 마커) ──
    /** 승강기 메뉴 — 구역 승강장과 광산 각 층 승강기. 6층 모두 열림 (레벨·곡괭이 잠김 없음). */
    public static final String INTERACT_LIFT = "mine_lift";
    /** 광산 관리소 — 얕은 갱도 승강기 홀. 곡괭이 받기·사기·제련·새기기·벼리기·팔기. 구역 없이도 된다 (R §2-1). */
    public static final String INTERACT_OFFICE = "mine_office";
    /** 구역 제련소 (CraftingService.openSmelter). 레시피 station 이름과 같다. */
    public static final String INTERACT_SMELTER = "smelter";
    /** 광부 숙소 게시판 (광맥 현황·기력·기록). */
    public static final String INTERACT_INFO = "mine_info";
    public static final List<String> INTERACTS = List.of(INTERACT_LIFT, INTERACT_OFFICE, INTERACT_SMELTER, INTERACT_INFO);

    // ── NPC 역할 (npcs.yml role) ──
    /** 광부 브론 → MineApi.openOffice. */
    public static final String ROLE_MINER = "miner";
    /** 제련공 이그나 → CraftingService.openSmelter. */
    public static final String ROLE_SMELTER = "smelter";

    // ── 레시피 · 획득처 ──
    public static final String STATION_BLACKSMITH = "blacksmith";
    public static final String STATION_SMELTER = "smelter";
    public static final String CATEGORY_TOOL = "tool";
    public static final String SOURCE_MINE = "mine";
    public static final String SOURCE_SMELT = "smelt";

    // ── 마커 · 연출 ──
    public static final String MARKER_EXIT = "mine_exit";
    public static final String MARKER_OFFICE = "office";
    public static final String AMBIENT_DUST = "dust";

    // ── PlayerData ext ──
    /** "L&lt;n&gt;:v&lt;i&gt;=&lt;만료 epoch초&gt;;L&lt;n&gt;:g&lt;i&gt;=…" — 개인 빈 광맥·보석 노드. 만료 지난 것은 저장할 때 뺀다. */
    public static final String EXT_DEPLETED = "mine.depleted";
    /** "L&lt;n&gt;=&lt;청사진 해시&gt;;…" — 청사진이 바뀐 층의 기록을 지울 때. */
    public static final String EXT_HASH = "mine.hash";
    /** 기력 (실수, 최대 1200). */
    public static final String EXT_STAMINA = "mine.stamina";
    /** 기력을 마지막으로 계산한 epoch ms (오프라인 회복). */
    public static final String EXT_STAMINA_AT = "mine.stamina_at";
    /** true = 첫 무료 구리 곡괭이를 받음. */
    public static final String EXT_FREE_PICKAXE = "mine.free_pickaxe";
    /** true = 옛 광물 재료 바꿈 안내(채팅 1번)를 봄. */
    public static final String EXT_MAT036_NOTICE = "mat036.notice";
    public static final List<String> EXT_KEYS = List.of(EXT_DEPLETED, EXT_HASH, EXT_STAMINA, EXT_STAMINA_AT, EXT_FREE_PICKAXE, EXT_MAT036_NOTICE);

    // ── PDC ──
    /** 보석 노드 ItemDisplay: "L&lt;n&gt;:&lt;i&gt;". */
    public static final String PDC_NODE = "mine_node";

    /** 곡괭이가 약할 때 액션바 (주인 결정 2). */
    public static final String TOO_WEAK = "곡괭이가 약해 캘 수 없습니다";
}
