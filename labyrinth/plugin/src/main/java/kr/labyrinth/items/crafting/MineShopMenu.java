package kr.labyrinth.items.crafting;

import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.event.ItemObtainEvent;
import kr.labyrinth.items.GearItemService;
import kr.labyrinth.items.sell.SellService;
import kr.labyrinth.mine.MineNames;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.Menu;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 광부 상점 (0.3.6): 구리 곡괭이 — 처음 1개는 무료 (ext {@code mine.free_pickaxe}), 그 뒤로는 {@link #PICKAXE_PRICE} 골드 ·
 * 물건 팔기 (판매 창 {@link SellService} 그대로 — 도구는 못 팜) · 제련소. 광산 관리소의 곡괭이·팔기 탭과 광부 브론이 이것을 쓴다.
 */
public final class MineShopMenu extends Menu {

    /** 첫 곡괭이 뒤 구리 곡괭이 값 (계약 §2.6). */
    public static final int PICKAXE_PRICE = 50;
    public static final String PICKAXE = "copper_pickaxe";

    private final Services services;
    private final LabCraftingService crafting;

    MineShopMenu(Services services, LabCraftingService crafting) {
        super(3, kr.labyrinth.ui.UiTheme.title("merchant", 3, "<#d9a066>광부 상점"));
        this.services = services;
        this.crafting = crafting;
    }

    /** 이 사람이 무료 곡괭이를 받을 수 있나. */
    public static boolean freeLeft(PlayerData d) {
        return !Boolean.TRUE.equals(d.ext().get(MineNames.EXT_FREE_PICKAXE)) && !"true".equals(String.valueOf(d.ext().get(MineNames.EXT_FREE_PICKAXE)));
    }

    @Override
    protected void build(Player viewer) {
        PlayerData d = services.data().get(viewer);
        ItemDef pick = services.content().item(PICKAXE);
        boolean free = freeLeft(d);
        if (pick != null) {
            List<String> reach = new java.util.ArrayList<>(kr.labyrinth.items.ItemTooltip.reachLines(services.content(), pick.tool()));
            while (reach.size() < 2) reach.add("");
            ItemStack icon = services.items().create(PICKAXE, 1);
            if (icon == null) icon = ItemStack.of(Material.PAPER);
            icon.setData(io.papermc.paper.datacomponent.DataComponentTypes.ITEM_NAME, Text.item("<" + pick.rarity().color() + ">" + pick.name()));
            icon.setData(io.papermc.paper.datacomponent.DataComponentTypes.LORE, io.papermc.paper.datacomponent.item.ItemLore.lore(Text.itemLines(List.of(
                    "<gray>" + Text.escape(reach.get(0)),
                    "<gray>" + Text.escape(reach.get(1)),
                    "<gray>제련소에서 더 좋은 곡괭이로 벼릴 수 있습니다.",
                    "",
                    free ? "<#9be89b>처음 한 개는 무료" : (d.gold() >= PICKAXE_PRICE ? "<#ffd27a>" : "<#ff6b6b>") + "가격 " + PICKAXE_PRICE + " G",
                    "<#ffd27a>▶ 클릭하여 받기"))));
            set(11, icon, ctx -> givePickaxe(viewer));
        }
        SellService sell = SellService.get();
        boolean canSell = sell != null && sell.enabled() && !sell.blocked(viewer);
        set(13, Button.icon(canSell ? Material.EMERALD : Material.GRAY_DYE, (canSell ? "<green><b>" : "<gray>") + "물건 팔기",
                List.of("<gray>광석·주괴·보석과 미궁 재료를 팝니다.", "<dark_gray>(도구·시작 지급품·열쇠는 못 팜)", "",
                        canSell ? "<yellow>▶ 클릭: 판매 창 열기" : "<#ff8a8a>지금은 팔 수 없습니다.")), ctx -> {
            if (!canSell) {
                viewer.playSound(viewer.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.6f, 1.2f);
                return;
            }
            viewer.playSound(viewer.getLocation(), Sound.UI_BUTTON_CLICK, 0.5f, 1.3f);
            sell.open(viewer, null);
        });
        set(15, Button.icon(Material.BLAST_FURNACE, "<#ff9a5a><b>제련소</b>",
                List.of("<gray>광석을 주괴로 녹이고,", "<gray>보석으로 강화석을 새기고,", "<gray>곡괭이를 벼립니다.", "", "<yellow>▶ 클릭: 제련소 열기")), ctx -> {
            viewer.playSound(viewer.getLocation(), Sound.UI_BUTTON_CLICK, 0.5f, 1.3f);
            crafting.openSmelter(viewer);
        });
        deco(21, Button.icon(Material.GOLD_NUGGET, "<#ffd27a>보유 골드 " + Text.num(d.gold()), List.of()));
        set(23, Button.icon(Material.OAK_DOOR, "<gray>닫기", List.of()), ctx -> viewer.closeInventory());
    }

    private void givePickaxe(Player p) {
        PlayerData d = services.data().get(p);
        ItemDef def = services.content().item(PICKAXE);
        if (def == null) {
            Text.error(p, "곡괭이를 준비하지 못했습니다.");
            return;
        }
        boolean free = freeLeft(d);
        if (p.getInventory().firstEmpty() == -1) {
            Text.error(p, "인벤토리에 빈 칸이 없습니다.");
            p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.6f, 0.6f);
            return;
        }
        if (!free && !d.takeGold(PICKAXE_PRICE)) {
            Text.error(p, "골드가 부족합니다.");
            p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.6f, 0.6f);
            return;
        }
        ItemStack s = services.items().create(PICKAXE, 1);
        if (s == null) {
            if (!free) d.addGold(PICKAXE_PRICE);
            Text.error(p, "곡괭이를 준비하지 못했습니다.");
            return;
        }
        if (free) d.ext().put(MineNames.EXT_FREE_PICKAXE, true);
        d.markDirty();
        GearItemService.deliver(p, s);
        Bukkit.getPluginManager().callEvent(new ItemObtainEvent(p, def, s, "shop"));
        services.hud().refresh(p);
        p.playSound(p.getLocation(), Sound.ENTITY_ITEM_PICKUP, 0.7f, 1.0f);
        Text.send(p, "<" + def.rarity().color() + ">" + def.name() + "</" + def.rarity().color() + "> <gray>을(를) 받았습니다."
                + (free ? "" : " <dark_gray>(-" + PICKAXE_PRICE + " 골드)"));
        refresh();
    }
}
