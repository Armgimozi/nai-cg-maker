package kr.labyrinth.homes.play;

import java.util.List;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.HomesConfig;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/**
 * 시작 선물 (0.3.7, 설계 §4): 작은 오두막 (참나무·가문비·자작·벚나무) 또는 집들이 꾸러미 — 한 사람 한 번.
 * 관리자가 정한 집터(convert)는 꾸러미만. 고르지 않고 닫으면 나중에 관리인 메뉴에서 고를 수 있다.
 */
final class StarterMenu extends HomeMenu {

    private static final int[] WOOD_SLOTS = {10, 11, 12, 13};
    private final PlotGeom home;

    StarterMenu(PlayUi ui, PlotGeom home) {
        super(ui, "home_starter", 3, "<#7fe07f>시작 선물 — 하나만 고릅니다");
        this.home = home;
    }

    @Override
    protected void draw(Player p) {
        HomesConfig.Starter st = homes().config().starter();
        boolean cottage = st.cottage() && !home.custom();
        StarterCottage.Wood[] woods = StarterCottage.Wood.values();
        for (int i = 0; i < woods.length && i < WOOD_SLOTS.length; i++) {
            StarterCottage.Wood w = woods[i];
            Material icon = BuildShopMenu.material(w.planks(), Material.OAK_PLANKS);
            if (!cottage) {
                deco(WOOD_SLOTS[i], Button.icon(Material.GRAY_DYE, "<dark_gray>" + w.label + " 오두막",
                        List.of(home.custom() ? "<dark_gray>관리자가 정한 집터에는 꾸러미만 줍니다." : "<dark_gray>이 서버에서는 오두막을 주지 않습니다.")));
                continue;
            }
            set(WOOD_SLOTS[i], Button.icon(icon, "<#ffd36b><b>" + w.label + " 오두막</b>",
                    List.of("<gray>7×7 작은 집을 집터 뒤쪽에 지어 줍니다.", "<gray>침대·상자 2·작업대·화로·등불", "<gray>앞마당이 14×6 쯤 남습니다.",
                            "<dark_gray>집터에 이미 블록이 있으면 꾸러미로 줍니다.", "", "<#ffd36b>클릭: 이걸로")), ctx -> {
                click(ctx.player());
                ctx.player().closeInventory();
                ui.gift().cottage(ctx.player(), home, w);
            });
        }
        if (st.kit()) {
            set(15, Button.icon(Material.CHEST, "<#ffd36b><b>집들이 꾸러미</b>",
                    List.of("<gray>상자 2 · 침대 · 작업대 · 화로", "<gray>등불 4 · 참나무 판자 64", "<gray>유리판 16 · 참나무 문", "",
                            "<#ffd36b>클릭: 이걸로")), ctx -> {
                click(ctx.player());
                ctx.player().closeInventory();
                ui.gift().kit(ctx.player(), true);
            });
        }
        deco(4, Button.icon(Material.LANTERN, "<#7fe07f>" + Text.escape(PlayUi.object(home.label())) + " 받았습니다",
                List.of("<gray>선물은 한 사람에 한 번입니다.", "<gray>지금 안 골라도 관리인 메뉴에서 고를 수 있습니다.")));
        set(22, UiTheme.close(), ctx -> {
            ctx.player().closeInventory();
            Text.send(ctx.player(), "<gray>시작 선물은 나중에 <white>/미궁 집</white> 에서 고를 수 있습니다.");
        });
    }
}
