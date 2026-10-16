package kr.labyrinth.mine;

import kr.labyrinth.content.ItemDef;
import org.bukkit.World;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 광산 (0.3.6) — 다른 패키지가 부르는 입구. 소유: Q1 (kr.labyrinth.mine.MineModule 이 {@code Services.setMine} 으로 교체).
 * 기본 구현 {@link NoopMineApi} = 광산 꺼짐 (안내만).
 * <p>
 * 계약 (tools/data/036/mine.json · design/036/CONTRACT.md): 광산 6층은 모두 열려 있고 레벨 조건이 어디에도 없다. 곡괭이 tier 는
 * 캘 수 있는 광석 (tier ≤ 곡괭이 + 1, 한 단계 위는 느림) 과 빠르기만 정한다. 광산 월드 안은 피해 0 · PvP 끔 · 어드벤처 (규칙만, 기억 없음).
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
}
