package kr.labyrinth.homes.play;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotInfo;
import kr.labyrinth.homes.PlotRole;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 집 고르기 지도 (0.3.7, plan §1.2·§8) — 실제 배치 4×3 ({@link ClaimMap}). 연두 = 빈 집 · 금색 = 내 집 · 흰색 = 초대받은 집 ·
 * 남의 집 = 주인 머리 (빨간 이름). 빈 집 클릭 → 한 번 더 묻고 받기, 남의 집 클릭 → 방문 (손님을 받는 집만). 아래 가운데 "아무 데나".
 */
final class ClaimMenu extends HomeMenu {

    ClaimMenu(PlayUi ui) { super(ui, "home_claim", 6, "<#ffd36b>등불 골목 지도"); }

    @Override
    protected void draw(Player p) {
        var s = homes();
        UUID me = p.getUniqueId();
        PlotGeom myHome = s.homeOf(me);
        // 길·골목·마당
        ItemStack lane = Button.icon(Material.DIRT_PATH, "<gray>골목", List.of("<dark_gray>북쪽으로 가면 마을 광장입니다."));
        deco(ClaimMap.ALLEY_COL, Button.icon(Material.LANTERN, "<#ffd36b>↑ 마을 광장", List.of("<gray>골목을 따라 북쪽으로 올라갑니다.")));
        for (int r : ClaimMap.ROW_SLOTS) deco(r * 9 + ClaimMap.ALLEY_COL, lane);
        ItemStack lanternSt = Button.icon(Material.DIRT_PATH, "<gray>등불길", List.of());
        for (int c = 1; c <= 7; c++) deco(ClaimMap.LANTERN_ROW * 9 + c, lanternSt);
        deco(ClaimMap.LANTERN_ROW * 9 + ClaimMap.ALLEY_COL, Button.icon(Material.BARREL, "<#ffd36b>관리인 노점",
                List.of("<gray>마을 관리인 모아가 있는 곳입니다.")));
        ItemStack wellSt = Button.icon(Material.DIRT_PATH, "<gray>우물길", List.of());
        for (int c = 1; c <= 7; c++) if (c != ClaimMap.ALLEY_COL) deco(ClaimMap.WELL_ROW * 9 + c, wellSt);
        int yard = ClaimMap.yardSlot();
        if (yard >= 0) deco(yard, Button.icon(Material.FLOWERING_AZALEA, "<gray>골목 마당", List.of("<dark_gray>집터가 아닙니다. 벤치와 꽃밭.")));
        for (int e : ClaimMap.emptyCells()) deco(e, Button.icon(Material.SHORT_GRASS, "<gray>들판", List.of()));

        int extra = 0;
        int vacant = 0;
        for (PlotGeom g : s.plots()) {
            Integer slot = g.custom() ? null : ClaimMap.DESIGN.get(g.id());
            if (slot == null) {
                if (extra >= ClaimMap.EXTRA_SLOTS.length) continue;
                slot = ClaimMap.EXTRA_SLOTS[extra++];
            }
            PlotInfo info = s.info(g);
            if (info.vacant()) vacant++;
            drawPlot(p, slot, g, info, myHome);
        }
        set(45, UiTheme.back(), ctx -> {
            click(ctx.player());
            ui.openEstate(ctx.player());
        });
        if (myHome == null && vacant > 0) {
            set(ClaimMap.WELL_ROW * 9 + ClaimMap.ALLEY_COL, UiTheme.glint(Button.icon(Material.COMPASS, "<#7fe07f><b>아무 데나</b>",
                    List.of("<gray>빈 집 하나를 골라 줍니다.", "", "<#ffd36b>클릭: 받기")), true), ctx -> {
                click(ctx.player());
                ui.confirmClaim(ctx.player(), null);
            });
        } else {
            deco(ClaimMap.WELL_ROW * 9 + ClaimMap.ALLEY_COL, Button.icon(Material.DIRT_PATH, "<gray>우물길",
                    List.of(myHome != null ? "<dark_gray>내 집: " + Text.escape(myHome.label()) : "<dark_gray>빈 집이 없습니다.")));
        }
        set(53, UiTheme.close(), ctx -> ctx.player().closeInventory());
    }

    private void drawPlot(Player p, int slot, PlotGeom g, PlotInfo info, PlotGeom myHome) {
        var s = homes();
        String where = "<dark_gray>바닥 높이 " + g.floorY() + " · 대문 " + dir(g.front());
        if (info.vacant()) {
            List<String> lore = new ArrayList<>();
            lore.add("<gray>빈 집 · " + g.width() + "×" + g.depth());
            lore.add(where);
            lore.add("");
            lore.add(myHome == null ? "<#ffd36b>클릭: 받기" : "<dark_gray>이미 집이 있습니다 (" + Text.escape(myHome.label()) + ")");
            set(slot, Button.icon(Material.LIME_CONCRETE, "<#7fe07f><b>" + Text.escape(g.label()) + "</b> <gray>· 빈 집", lore), ctx -> {
                if (myHome != null) {
                    deny(ctx.player());
                    Text.error(ctx.player(), "이미 집이 있습니다 (" + Text.escape(myHome.label()) + "). 한 사람 한 집입니다.");
                    return;
                }
                click(ctx.player());
                ui.confirmClaim(ctx.player(), g);
            });
            return;
        }
        String name = Text.escape(info.name().isBlank() ? info.ownerName() + "의 집" : info.name());
        if (p.getUniqueId().equals(info.owner())) {
            set(slot, UiTheme.glint(Button.icon(Material.GOLD_BLOCK, "<#ffd36b><b>" + Text.escape(g.label()) + "</b> <gray>· 내 집",
                    List.of("<gray>" + name, where, "", "<#ffd36b>클릭: 내 집 메뉴")), true), ctx -> {
                click(ctx.player());
                ui.openEstate(ctx.player());
            });
            return;
        }
        PlotRole role = s.roleIn(p, g);
        boolean visit = role != PlotRole.NONE && ui.travel().visitAllowed(p);
        List<String> lore = new ArrayList<>();
        lore.add("<gray>주인 <white>" + Text.escape(info.ownerName()));
        lore.add("<gray>" + name);
        lore.add("<gray>손님 " + (info.guests() ? "받음" : "안 받음"));
        lore.add(where);
        lore.add("");
        lore.add(visit ? "<#ffd36b>클릭: 방문" : "<dark_gray>방문할 수 없습니다");
        ItemStack icon = role == PlotRole.TRUSTED
                ? Button.icon(Material.WHITE_WOOL, "<white><b>" + Text.escape(g.label()) + "</b> <gray>· 초대받은 집", lore)
                : head(info.owner(), info.ownerName(), "<#ff6b6b><b>" + Text.escape(g.label()) + "</b> <gray>· " + Text.escape(info.ownerName()), lore);
        set(slot, icon, ctx -> {
            if (!visit) {
                deny(ctx.player());
                return;
            }
            click(ctx.player());
            ctx.player().closeInventory();
            ui.travel().visit(ctx.player(), g, info.ownerName());
        });
    }

    static String dir(String front) {
        return switch (front) {
            case "N" -> "북쪽";
            case "E" -> "동쪽";
            case "W" -> "서쪽";
            default -> "남쪽";
        };
    }
}
