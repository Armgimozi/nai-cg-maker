package kr.labyrinth.homes;

import kr.labyrinth.core.Text;
import org.bukkit.entity.Player;

/** 메뉴가 아직 없을 때: 안내 글만 (뼈대). 소유: 묶음 C. */
public class NoopHomesUi implements HomesUi {

    @Override
    public void openEstate(Player player) { if (player != null) Text.send(player, "<gray>집 메뉴를 준비하는 중입니다."); }

    @Override
    public void openPlot(Player player, PlotGeom plot) { openEstate(player); }

    @Override
    public void plotChanged(PlotGeom plot, PlotInfo info) { }

    @Override
    public void claimed(Player player, PlotGeom plot, boolean firstHome) { }

    @Override
    public String selfTestLine() { return "[집 메뉴 자가 진단] 결과: 준비 중"; }
}
