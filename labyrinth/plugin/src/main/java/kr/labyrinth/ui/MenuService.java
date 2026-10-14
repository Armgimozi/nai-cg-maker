package kr.labyrinth.ui;

import org.bukkit.entity.Player;

/**
 * 게임 메뉴 열기 진입점 (명령어·NPC·다른 메뉴가 호출). 소유: ui+titles 담당 (menus/*).
 * 기본 구현 {@link ChatMenuService}: 채팅 클릭 메시지로 대신 보여 준다.
 */
public interface MenuService {

    /** /미궁 — 메인(입장·파티·스탯·직업·칭호 바로가기). */
    void openMain(Player player);

    /** /스탯 — 스탯 분배. */
    void openStats(Player player);

    /** /직업 — 직업 정보·전직. */
    void openClass(Player player);

    /** /파티 — 파티 관리. */
    void openParty(Player player);

    /** /칭호 — 칭호 목록·장착. */
    void openTitles(Player player);

    /** 입장(층 선택). */
    void openEntrance(Player player);

    /** 관리자 초기 설정(난이도·입구 방식). */
    void openSetup(Player player);

    /** 장신구 2칸. */
    void openAccessories(Player player);
}
