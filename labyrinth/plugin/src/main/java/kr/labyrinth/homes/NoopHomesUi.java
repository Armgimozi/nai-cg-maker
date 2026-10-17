package kr.labyrinth.homes;

import kr.labyrinth.core.Text;
import org.bukkit.entity.Player;

/** 집 기능이 꺼져 있을 때 (homes.enabled: false — 놀이 연결을 켜지 않음): 안내 글만. 소유: 묶음 C. */
public class NoopHomesUi implements HomesUi {

    @Override
    public void openEstate(Player player) { if (player != null) Text.error(player, "이 서버에서는 집 기능을 쓰지 않습니다."); }

    @Override
    public void openPlot(Player player, PlotGeom plot) { openEstate(player); }

    @Override
    public void plotChanged(PlotGeom plot, PlotInfo info) { }

    @Override
    public void claimed(Player player, PlotGeom plot, boolean firstHome) { }

    @Override
    public String selfTestLine() { return "[집 메뉴 자가 진단] 꺼짐 (homes.enabled: false)"; }
}
