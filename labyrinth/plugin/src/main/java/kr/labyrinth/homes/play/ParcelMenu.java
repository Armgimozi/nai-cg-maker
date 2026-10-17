package kr.labyrinth.homes.play;

import java.util.List;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 맡긴 짐 (0.3.7, 설계 §9): 집을 비우거나 회수당했을 때 집 안 물건이 여기로 온다. 45칸씩 넘겨 보고 "모두 받기".
 * 보이는 것은 복사본이다 — 실제로 받는 일은 {@code HomesApi.takeParcel} (파일에서 먼저 빼고 가방에 넣음, 못 넣은 것은 그대로 남음).
 */
final class ParcelMenu extends HomeMenu {

    private static final int PER_PAGE = 45;
    private int page;

    ParcelMenu(PlayUi ui) { super(ui, "home_parcel", 6, "<#c9a2ff>맡긴 짐"); }

    @Override
    protected void draw(Player p) {
        List<ItemStack> items = homes().parcel(p.getUniqueId());
        int pages = Math.max(1, (items.size() + PER_PAGE - 1) / PER_PAGE);
        page = Math.max(0, Math.min(page, pages - 1));
        for (int i = 0; i < PER_PAGE; i++) {
            int idx = page * PER_PAGE + i;
            if (idx >= items.size()) break;
            ItemStack s = items.get(idx);
            if (s == null || s.isEmpty()) continue;
            deco(i, s.clone());
        }
        if (items.isEmpty()) {
            deco(22, Button.icon(Material.BARREL, "<gray>맡긴 짐이 없습니다", List.of("<dark_gray>집을 비우면 집 안 물건이 여기로 옵니다.")));
        }
        set(45, UiTheme.back(), ctx -> {
            click(ctx.player());
            ui.openEstate(ctx.player());
        });
        if (page > 0) set(47, Button.icon(Material.ARROW, "<gray>◀ 앞쪽", List.of("<dark_gray>" + page + " / " + pages + "쪽")), ctx -> {
            click(ctx.player());
            page--;
            refresh();
        });
        if (page + 1 < pages) set(51, Button.icon(Material.ARROW, "<gray>뒤쪽 ▶", List.of("<dark_gray>" + (page + 2) + " / " + pages + "쪽")), ctx -> {
            click(ctx.player());
            page++;
            refresh();
        });
        if (!items.isEmpty()) {
            set(49, UiTheme.glint(Button.icon(Material.HOPPER, "<#7fe07f><b>모두 받기</b>",
                    List.of("<gray>" + items.size() + "묶음", "<gray>가방이 차면 남은 것은 그대로 둡니다.", "", "<#ffd36b>클릭: 받기")), true), ctx -> {
                result(ctx.player(), homes().takeParcel(ctx.player()));
                refresh();
            });
        }
        set(53, UiTheme.close(), ctx -> ctx.player().closeInventory());
    }
}
