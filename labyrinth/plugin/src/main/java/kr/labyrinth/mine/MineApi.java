package kr.labyrinth.mine;

import kr.labyrinth.content.ItemDef;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 광산 (0.3.6) — 다른 패키지가 부르는 입구. 소유: Q1 (kr.labyrinth.mine.MineModule 이 {@code Services.setMine} 으로 교체).
 * 기본 구현 {@link NoopMineApi} = 광산 꺼짐 (안내만).
 * <p>
 * 계약 (tools/data/036/mine.json · design/036/CONTRACT.md): 광산 6층은 모두 열려 있고 레벨 조건이 어디에도 없다. 곡괭이 tier 는
 * 캘 수 있는 광석 (tier ≤ 곡괭이 + 1, 한 단계 위는 느림) 과 빠르기만 정한다. 광산 월드 안은 피해 0 · 어드벤처 (규칙만, 기억 없음).
 * 0.3.7 주인 결정: 승강기 홀 밖은 PvP (플레이어끼리 때리는 것만 — {@link #pvpAllows}). 이 부분은 0.3.6 계약보다 앞선다.
 */
public interface MineApi {

    /** 광산이 켜져 있고 mine.yml 이 있는가. */
    boolean enabled();

    /** 그 월드가 광산 월드인가 (DamageService·TargetFilter·PvpModule·게임 모드 규칙이 묻는다). null 이면 false. */
    boolean isMineWorld(World world);

    /** 승강기 메뉴 (6층 + 마을로). interact mine_lift · 광산 승강기 · /미궁 광산. */
    void openLift(Player player);

    /** 광산 관리소 메뉴 (곡괭이·제련·새기기·벼리기·팔기·현황). interact mine_office · NPC miner. */
    void openOffice(Player player);

    /** 광부 게시판 (광맥 현황). interact mine_info. */
    void openInfo(Player player);

    /**
     * 곡괭이 아이템에 구성요소를 쓴다 (Tool 규칙 블록별 speed, CAN_BREAK = 캘 수 있는 광산 블록, UNBREAKABLE 숨김, 공격 속성 비움,
     * TOOLTIP_DISPLAY 로 바닐라 줄 숨김). ItemService 가 TOOL 을 만들 때·접속 때 다시 부른다. def 가 곡괭이가 아니면 stack 그대로.
     */
    ItemStack applyPickaxe(ItemStack stack, ItemDef def);

    // ── 0.3.6 Q1 더함 (이름은 그대로, 더하기만) ──────────────────────────

    /** 광산 월드 안 피해 0 인가 (config mine.safe, 기본 true). {@link MineSafety} 가 묻는다. */
    default boolean safe() { return true; }

    /**
     * {@code /미궁 광산}·메인 메뉴 "광산": 구역이 있으면 승강장 앞으로, 없으면 얕은 갱도 승강장으로 (계약 §2.5). 미궁 안에서는 못 씀.
     * config {@code mine.teleport_command} (auto = village.teleport_command) 가 끄면 관리자만. 광산 안이면 승강기 메뉴.
     * {@link #openLift} 는 승강기 앞(광산 안·구역 승강장)에서 메뉴를, 그 밖에서는 이것과 같게 움직인다.
     */
    default void openMine(Player player) { openLift(player); }

    // ── 0.3.7 광산 PvP (주인 결정 "광산 PVP 키자", 더하기만 — Noop 은 아래 기본값 = 0.3.6 처럼 PvP 없음) ──

    /** 광산 PvP 가 지금 켜져 있나 (광산 켜짐 · config mine.pvp.enabled · pvp.enabled). PvpModule 이 월드 PvP 규칙을 맞출 때 묻는다. */
    default boolean pvpEnabled() { return false; }

    /**
     * 그 자리가 PvP 안전한 곳인가 — 광산 PvP 꺼짐 · 층마다 승강기 홀(맨 위층 관리소 포함)과 둘레 {@code mine.pvp.safe_margin} 칸 ·
     * 층 상자 밖이면 true. 광산 월드 밖 위치는 부르는 쪽이 거른다 ({@link MineSafety#noPvp}).
     */
    default boolean pvpSafeAt(Location location) { return true; }

    /**
     * 광산에서 a 가 v 에게 PvP 피해를 줄 수 있나: 광산 PvP 켜짐 · v 가 광산 월드 · 쓰러지는 중 아님 ·
     * {@code TargetFilter.isEnemy(a, v)} (다른 파티 · 두 사람 다 PvP 구역 · 무적 아님). {@link MineSafety#protects(MineApi, Entity, Entity)} 가 묻는다.
     */
    default boolean pvpAllows(Player attacker, Player victim) { return false; }

    /**
     * 광산을 나가는 길(/미궁 마을 · 메인 메뉴 "마을")에서: PvP 구역에서 싸우는 중이면 {@code death.penalty.combat_exit_seconds} 초 시전을
     * 시작하고 true (끝나면 go 를 부른다 — 그때는 이 메서드가 false). 아니면 false (부른 쪽이 바로 보낸다).
     */
    default boolean holdExit(Player player, Runnable go) { return false; }

    /**
     * PvP 구역에서 싸우는 중(10초 안에 때리거나 맞음)이라 광산을 나가려면 시전이 필요한가. 미궁 입장처럼 미룰 수 없는
     * 광산 밖 이동이 이것을 보고 막는다 ({@code DungeonManager.enter}).
     */
    default boolean inPvpCombat(Player player) { return false; }

    /** 광산 PvP 로 쓰러지면 미궁과 같이 잃나 (config mine.pvp.penalty). false = 경험치만. */
    default boolean pvpPenalty() { return false; }

    /** 안전 구역이 있는 층 수 (자가 진단). */
    default int safeZoneCount() { return 0; }
}
