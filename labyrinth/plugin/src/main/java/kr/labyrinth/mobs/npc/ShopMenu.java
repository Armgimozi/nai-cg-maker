package kr.labyrinth.mobs.npc;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.ItemLore;
import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.items.sell.SellService;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.ClickContext;
import kr.labyrinth.ui.Menu;
import net.kyori.adventure.text.Component;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 떠돌이 상인 상점 (npcs.yml merchant 의 {@code shop: [{item, price, level_req?}]}).
 * 좌클릭 1개, 쉬프트+좌클릭 5개(스택 가능한 물건만), 우클릭 = 설명만. 골드는 PlayerData, 지급은 ItemService(source=shop).
 * [물건 팔기] = 판매 창({@link kr.labyrinth.items.sell.SellMenu}, {@code /미궁 판매} 와 같은 창 — 미궁 공략 중에는 막힘).
 */
public final class ShopMenu extends Menu {

    private static final int[] SLOTS = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34};

    private final Services services;
    private final NpcDef npc;

    public ShopMenu(Services services, NpcDef npc) {
        super(5, kr.labyrinth.ui.UiTheme.title("merchant", 5, "<dark_gray>" + Text.strip(npc.name()) + " · 상점"));
        this.services = services;
        this.npc = npc;
    }

    @Override
    protected void build(Player viewer) {
        ItemStack frame = Button.filler(Material.BLACK_STAINED_GLASS_PANE);
        for (int i = 0; i < size(); i++) deco(i, frame);
        PlayerData data = services.data().get(viewer);
        deco(4, Button.icon(Material.GOLD_INGOT, "<gold><b>보유 골드</b></gold>",
                List.of("<yellow>" + Text.num(data.gold()) + " G", "", "<gray>좌클릭: 1개 구매", "<gray>쉬프트+좌클릭: 5개 구매",
                        "<gray>팔 때는 아래 <green>[물건 팔기]")));
        int i = 0;
        for (NpcDef.ShopEntry entry : npc.shop()) {
            if (i >= SLOTS.length) break;
            ItemDef def = services.content().item(entry.item());
            if (def == null) continue;
            int slot = SLOTS[i++];
            set(slot, icon(entry, def, data), ctx -> buy(ctx, entry, def));
        }
        // 0.3.6 Q6: 날마다 바뀌는 희귀 도안 (셋째 줄부터)
        var bp = kr.labyrinth.items.blueprint.BlueprintService.get();
        if (bp != null && "merchant".equals(npc.role())) {
            int j = Math.max(i, 14);
            for (String rid : bp.shopToday()) {
                if (j >= SLOTS.length) break;
                ItemStack b = kr.labyrinth.items.blueprint.BlueprintItems.create(services, rid, 1);
                if (b == null) continue;
                int price = bp.shopPrice(rid);
                List<Component> lore = new ArrayList<>();
                ItemLore existing = b.getData(DataComponentTypes.LORE);
                if (existing != null) lore.addAll(existing.lines());
                lore.add(Component.empty());
                lore.add(Text.item("<gray>가격: " + (data.gold() >= price ? "<gold>" : "<red>") + Text.num(price) + " G"));
                if (bp.knows(viewer, rid)) lore.add(Text.item("<#9be89b>이미 배운 도안"));
                lore.add(Text.item("<dark_gray>오늘의 도안 — 내일은 다른 것을 팝니다"));
                lore.add(Text.item("<yellow>▶ 클릭해서 구매"));
                b.setData(DataComponentTypes.LORE, ItemLore.lore(lore));
                set(SLOTS[j++], b, ctx -> {
                    if (ctx.isRight()) return;
                    if (bp.buy(ctx.player(), rid)) refresh();
                });
            }
        }
        set(38, sellIcon(viewer), this::openSell);
        set(40, Button.icon(Material.BARRIER, "<red>닫기", List.of()), ctx -> ctx.player().closeInventory());
    }

    private ItemStack sellIcon(Player viewer) {
        SellService sell = SellService.get();
        if (sell == null || !sell.enabled()) {
            return Button.icon(Material.GRAY_DYE, "<gray>물건 팔기", List.of("<dark_gray>지금은 물건을 사지 않습니다."));
        }
        if (sell.blocked(viewer)) {
            return Button.icon(Material.GRAY_DYE, "<gray>물건 팔기", List.of("<#ff8a8a>미궁 안에서는 팔 수 없습니다.",
                    "<dark_gray>마을로 돌아온 뒤 /미궁 판매"));
        }
        return Button.icon(Material.EMERALD, "<green><b>물건 팔기</b>", List.of("<gray>가방의 미궁 재료·장비·소모품을",
                "<gray>골드를 받고 " + Text.strip(npc.name()) + " 에게 팝니다.", "<dark_gray>(시작 지급품·열쇠·전직의 두루마리 제외)", "",
                "<yellow>▶ 클릭: 판매 창 열기"));
    }

    private void openSell(ClickContext ctx) {
        Player p = ctx.player();
        SellService sell = SellService.get();
        if (sell == null || sell.blocked(p)) {
            p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.6f, 1.2f);
            if (sell != null) Text.error(p, "미궁 안에서는 물건을 팔 수 없습니다.");
            return;
        }
        p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.5f, 1.3f);
        sell.open(p, npc);
    }

    private ItemStack icon(NpcDef.ShopEntry entry, ItemDef def, PlayerData data) {
        ItemStack s = services.items().create(def.id());
        if (s == null) s = Button.icon(Material.PAPER, def.name(), List.of());
        List<Component> lore = new ArrayList<>();
        ItemLore existing = s.getData(DataComponentTypes.LORE);
        if (existing != null) lore.addAll(existing.lines());
        lore.add(Component.empty());
        boolean afford = data.gold() >= entry.price();
        boolean level = data.level() >= entry.levelReq();
        lore.add(Text.item("<gray>가격: " + (afford ? "<gold>" : "<red>") + Text.num(entry.price()) + " G"));
        if (entry.levelReq() > 1) lore.add(Text.item("<gray>필요 레벨: " + (level ? "<green>" : "<red>") + entry.levelReq()));
        lore.add(Text.item(level && afford ? "<yellow>▶ 클릭해서 구매" : "<dark_gray>구매할 수 없습니다"));
        s.setData(DataComponentTypes.LORE, ItemLore.lore(lore));
        return s;
    }

    private void buy(ClickContext ctx, NpcDef.ShopEntry entry, ItemDef def) {
        Player p = ctx.player();
        if (ctx.isRight()) return;
        PlayerData data = services.data().get(p);
        if (data.level() < entry.levelReq()) {
            Text.error(p, "레벨 " + entry.levelReq() + " 이상만 살 수 있습니다.");
            p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.6f, 1.2f);
            return;
        }
        boolean stackable = !def.isGear();
        int amount = ctx.isShift() && stackable ? 5 : 1;
        long cost = (long) entry.price() * amount;
        if (!data.takeGold(cost)) {
            Text.error(p, "골드가 부족합니다. <gray>(필요 " + Text.num(cost) + " G)");
            p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.6f, 1.2f);
            return;
        }
        int given = services.items().give(p, def.id(), amount, "shop");
        if (given < amount) data.addGold((long) entry.price() * (amount - given)); // 지급 못 한 만큼 환불
        Text.send(p, def.name() + " <gray>×" + given + " 구매 <dark_gray>(-" + Text.num((long) entry.price() * given) + " G)");
        p.playSound(p.getLocation(), Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.7f, 1.3f);
        services.hud().refresh(p);
        refresh();
    }
}
