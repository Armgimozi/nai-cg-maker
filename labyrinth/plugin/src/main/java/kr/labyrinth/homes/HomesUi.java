package kr.labyrinth.homes;

import org.bukkit.entity.Player;

/**
 * 집 메뉴·표지판·선물 (0.3.7) — 묶음 C 가 구현 ({@code homes/play/}), {@link HomesService} 가 부른다. 소유: 묶음 C (더하기만).
 * 기본 {@link NoopHomesUi} = 안내 글만.
 */
public interface HomesUi {

    /** 관리인 메뉴 (내 집 · 집 고르기 · 자재 · 맡긴 짐). */
    void openEstate(Player player);

    /** 그 집터 메뉴 (대문 표지판 우클릭). plot 이 null 이면 관리인 메뉴. */
    void openPlot(Player player, PlotGeom plot);

    /** 소유가 바뀜 (받기·비우기·이름·손님·회수·convert) — 대문 표지판 글 다시 쓰기, 열린 메뉴 새로 고침. */
    void plotChanged(PlotGeom plot, PlotInfo info);

    /** 처음 받음 — 시작 선물 고르기 (오두막·꾸러미, 한 사람 한 번 · convert 집은 꾸러미만). */
    void claimed(Player player, PlotGeom plot, boolean firstHome);

    /** "[집 메뉴 자가 진단] 결과: …" 한 줄. */
    String selfTestLine();
}
