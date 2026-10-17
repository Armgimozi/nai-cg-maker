package kr.labyrinth.homes.play;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.ItemLore;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 자재 (0.3.7, plan §12): 윗줄 탭 9 · 가운데 36칸 (쪽 넘김) · 왼클릭 1묶음, 쉬프트 5묶음.
 * 골드를 먼저 빼고, 가방에 못 넣은 만큼 돌려준다 (ShopMenu 방식). 산 블록은 그냥 바닐라 블록이라 되팔 수 없다.
 */
final class BuildShopMenu extends HomeMenu {

    private static final int PER_PAGE = 36;
    private int tab;
    private int page;

    BuildShopMenu(PlayUi ui) { super(ui, "home_shop", 6, "<#e8c58a>자재"); }

    @Override
    protected void draw(Player p) {
        HousingCatalog cat = ui.catalog();
        List<HousingCatalog.Tab> tabs = cat.tabs();
        if (tabs.isEmpty()) {
            deco(22, Button.icon(Material.BARRIER, "<#ff6b6b>파는 자재가 없습니다", List.of("<gray>content/housing.yml 을 확인하세요.")));
            bottom(p, 0);
            return;
        }
        tab = Math.max(0, Math.min(tab, tabs.size() - 1));
        for (int i = 0; i < tabs.size() && i < 9; i++) {
            HousingCatalog.Tab t = tabs.get(i);
            final int ti = i;
            ItemStack icon = Button.icon(material(t.icon(), Material.CHEST), (i == tab ? "<#ffd36b><b>" : "<gray>") + Text.escape(t.name()),
                    List.of("<gray>" + t.items().size() + "가지", i == tab ? "<dark_gray>보는 중" : "<#ffd36b>클릭: 보기"));
            set(i, UiTheme.glint(icon, i == tab), ctx -> {
                click(ctx.player());
                tab = ti;
                page = 0;
                refresh();
            });
        }
        HousingCatalog.Tab t = tabs.get(tab);
        int pages = Math.max(1, (t.items().size() + PER_PAGE - 1) / PER_PAGE);
        page = Math.max(0, Math.min(page, pages - 1));
        double mult = homes().config().shopPriceMultiplier();
        long gold = services.data().get(p).gold();
        for (int i = 0; i < PER_PAGE; i++) {
            int idx = page * PER_PAGE + i;
            if (idx >= t.items().size()) break;
            HousingCatalog.Entry e = t.items().get(idx);
            Material m = material(e.id(), null);
            if (m == null) continue;
            long price = HousingCatalog.price(e, mult);
            List<String> lore = new ArrayList<>();
            lore.add("<gray>" + e.bundle() + "개 · " + (gold >= price ? "<gold>" : "<red>") + Text.num(price) + " G");
            if (e.bundle() > 1) lore.add("<dark_gray>한 개 " + perUnit(price, e.bundle()) + "G");
            if (!e.note().isBlank()) lore.add("<dark_gray>" + Text.escape(e.note()));
            lore.add("");
            lore.add("<#ffd36b>클릭: " + e.bundle() + "개 · 쉬프트+클릭: " + e.bundle() * 5 + "개");
            // 이름은 그대로 둬서 클라이언트 언어의 바닐라 이름이 보이게 (설명 줄만 붙임)
            ItemStack icon = ItemStack.of(m, Math.max(1, Math.min(e.bundle(), Math.min(64, safeMax(m)))));
            icon.setData(DataComponentTypes.LORE, ItemLore.lore(Text.itemLines(lore)));
            set(9 + i, icon, ctx -> buy(ctx.player(), e, m, ctx.isShift() ? 5 : 1));
        }
        bottom(p, pages);
    }

    private void bottom(Player p, int pages) {
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
        gold(49, p);
        set(53, UiTheme.close(), ctx -> ctx.player().closeInventory());
    }

    private void buy(Player p, HousingCatalog.Entry e, Material m, int bundles) {
        if (ui.inDungeon(p)) {
            deny(p);
            Text.error(p, "미궁 밖에서 살 수 있습니다.");
            return;
        }
        long cost = HousingCatalog.price(e, homes().config().shopPriceMultiplier()) * bundles;
        PlayerData d = services.data().get(p);
        if (!d.takeGold(cost)) {
            deny(p);
            Text.error(p, "골드가 모자랍니다. <gray>(" + Text.num(cost) + " G)");
            return;
        }
        int total = e.bundle() * bundles;
        int given = give(p, m, total);
        long back = HousingCatalog.refund(cost, bundles, e.bundle(), given);
        if (back > 0) d.addGold(back);
        if (given <= 0) {
            deny(p);
            Text.error(p, "가방이 가득 찼습니다.");
        } else {
            ok(p);
            Text.send(p, "<white>" + name(m, e.id()) + " <gray>×" + given + " <dark_gray>(-" + Text.num(cost - back) + " G)"
                    + (given < total ? " <gray>가방이 차서 " + (total - given) + "개는 못 받았습니다." : ""));
        }
        services.hud().refresh(p);
        refresh();
    }

    /** 가방에 넣고 넣은 개수. 넣지 못한 것은 버리지 않고 다시 꺼낸다 (환불). */
    static int give(Player p, Material m, int total) {
        int max = Math.max(1, safeMax(m));
        int given = 0;
        int left = total;
        while (left > 0) {
            int n = Math.min(max, left);
            Map<Integer, ItemStack> rest = p.getInventory().addItem(ItemStack.of(m, n));
            int miss = 0;
            for (ItemStack r : rest.values()) miss += r.getAmount();
            given += n - miss;
            left -= n;
            if (miss > 0) break;
        }
        return given;
    }

    static int safeMax(Material m) {
        try {
            return m.getMaxStackSize();
        } catch (Throwable t) {
            return 64;
        }
    }

    static Material material(String id, Material fallback) {
        try {
            Material m = Material.matchMaterial(id);
            return m == null || !m.isItem() ? fallback : m;
        } catch (Throwable t) {
            Log.warn("[집] 자재 아이템을 모름: " + id);
            return fallback;
        }
    }

    /** 글 속 바닐라 이름 (클라이언트 언어 — MiniMessage lang 태그). 키를 모르면 id. */
    static String name(Material m, String id) {
        try {
            return "<lang:" + m.translationKey() + ">";
        } catch (Throwable t) {
            return Text.escape(id.replace('_', ' '));
        }
    }

    static String perUnit(long price, int bundle) {
        double u = price / (double) bundle;
        String s = String.format(java.util.Locale.ROOT, "%.2f", u);
        while (s.contains(".") && (s.endsWith("0") || s.endsWith("."))) s = s.substring(0, s.length() - 1);
        return s;
    }
}
