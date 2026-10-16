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
    /** 광부 숙소 게시판 (광맥 현황). */
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
    /** true = 첫 무료 구리 곡괭이를 받음. */
    public static final String EXT_FREE_PICKAXE = "mine.free_pickaxe";
    /** true = 옛 광물 재료 바꿈 안내(채팅 1번)를 봄. */
    public static final String EXT_MAT036_NOTICE = "mat036.notice";
    /** 지금 쓰는 ext 키 (계약 §0 뒤). */
    public static final List<String> EXT_KEYS = List.of(EXT_FREE_PICKAXE, EXT_MAT036_NOTICE);

    /** 주인 늦은 결정(계약 §0)으로 없앤 ext 키 (개인 광맥·기력) — 계약 mine.json 에서도 뺐다. */
    public static final List<String> EXT_REMOVED_036 = List.of("mine.depleted", "mine.hash", "mine.stamina", "mine.stamina_at");

    // ── PDC ──
    /** 보석 노드 ItemDisplay: "L&lt;n&gt;:&lt;i&gt;". */
    public static final String PDC_NODE = "mine_node";

    /** 곡괭이가 약할 때 액션바 (주인 결정 2). */
    public static final String TOO_WEAK = "곡괭이가 약해 캘 수 없습니다";
    /** 곡괭이 없이 광맥을 칠 때 액션바. */
    public static final String NEED_PICKAXE = "곡괭이가 있어야 캘 수 있습니다";
    /** 가방이 가득 차 캐지지 않을 때. */
    public static final String BAG_FULL = "가방이 가득 찼습니다";
    /** 광산 밖에서 광산 곡괭이로 광산 블록을 칠 때 (R §3-15). */
    public static final String OUTSIDE = "광산 곡괭이는 광산에서만 캘 수 있습니다";

    // ── 곡괭이 PDC (Q1, mine 패키지 안 키 — core/Keys 를 건드리지 않음) ──
    /** 곡괭이 구성요소를 쓴 블록 설정 지문 — 달라지면 접속 때 다시 쓴다. */
    public static final String PDC_TOOL_SIG = "mine_tool_sig";

    /** 광맥이 다시 차는 시간 = 기본 ÷ min(광산 월드 사람 수, 이 값) (config mine.regen_players_cap 기본). */
    public static final int REGEN_PLAYERS_CAP = 4;
    /** 광산 월드 메타 파일 (층마다 청사진 해시). */
    public static final String WORLD_META = "labyrinth-mine.yml";
    /** jar 안 청사진 경로 (n = 1..6). */
    public static String blueprintPath(int n) { return "mine/levels/L" + n + ".json"; }
}
