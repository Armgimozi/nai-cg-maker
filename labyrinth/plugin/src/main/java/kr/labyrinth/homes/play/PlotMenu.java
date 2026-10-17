package kr.labyrinth.homes.play;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotInfo;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/** 대문 표지판 우클릭 (interact plot:&lt;번지&gt;) — 그 집터 하나. 빈 집이면 받기, 남의 집이면 주인·손님 여부. 내 집은 관리인 메뉴로 바로 간다. */
final class PlotMenu extends HomeMenu {

    private final PlotGeom plot;

    PlotMenu(PlayUi ui, PlotGeom plot) {
        super(ui, "home_plot", 3, "<#ffd36b>" + plot.label());
        this.plot = plot;
    }

    @Override
    protected void draw(Player p) {
        var s = homes();
        PlotInfo info = s.info(plot);
        List<String> lore = new ArrayList<>();
        if (info.vacant()) {
            lore.add("<#7fe07f>빈 집");
        } else {
            lore.add("<gray>주인 <white>" + Text.escape(info.ownerName()));
            lore.add("<gray>" + Text.escape(info.name().isBlank() ? info.ownerName() + "의 집" : info.name()));
            lore.add("<gray>손님 " + (info.guests() ? "받음" : "안 받음"));
        }
        lore.add("<dark_gray>" + plot.width() + "×" + plot.depth() + " · 바닥 높이 " + plot.floorY());
        deco(13, Button.icon(info.vacant() ? Material.LIME_CONCRETE : Material.OAK_DOOR, "<#ffd36b><b>" + Text.escape(plot.label()) + "</b>", lore));
        if (info.vacant()) {
            boolean hasHome = s.homeOf(p.getUniqueId()) != null;
            set(11, Button.icon(hasHome ? Material.GRAY_DYE : Material.EMERALD, hasHome ? "<dark_gray>받기" : "<#7fe07f><b>이 집 받기</b>",
                    List.of(hasHome ? "<dark_gray>이미 집이 있습니다. 한 사람 한 집입니다." : "<gray>값은 받지 않습니다.", "",
                            hasHome ? "" : "<#ffd36b>클릭: 받기")), ctx -> {
                if (s.homeOf(ctx.player().getUniqueId()) != null) {
                    deny(ctx.player());
                    return;
                }
                click(ctx.player());
                ui.confirmClaim(ctx.player(), plot);
            });
        }
        set(15, Button.icon(Material.LANTERN, "<#ffd36b>관리인 메뉴", List.of("<gray>내 집 · 지도 · 자재 · 맡긴 짐", "", "<#ffd36b>클릭: 열기")), ctx -> {
            click(ctx.player());
            ui.openEstate(ctx.player());
        });
        set(22, UiTheme.close(), ctx -> ctx.player().closeInventory());
    }
}
