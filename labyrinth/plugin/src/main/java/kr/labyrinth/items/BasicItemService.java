package kr.labyrinth.items;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.ItemLore;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.event.ItemObtainEvent;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

/**
 * 최소 기본 구현: 이름(희귀도 색)·ITEM_MODEL·설명·PDC id 만 붙인다. 스탯 굴림/툴팁/장비 컴포넌트는 items 담당 구현이 대체.
 */
public class BasicItemService implements ItemService {

    protected final Services services;

    public BasicItemService(Services services) { this.services = services; }

    @Override
    public ItemStack create(String id) { return create(id, 1); }

    @Override
    public ItemStack create(String id, long seed) { return create(id, 1); }

    @Override
    public ItemStack create(String id, int amount) {
        ItemDef def = services.content().item(id);
        if (def == null) return null;
        Log.notImplemented("ItemService(굴림·툴팁·장비 컴포넌트)");
        ItemStack stack = ItemStack.of(Material.PAPER, Math.max(1, Math.min(99, amount)));
        stack.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, id));
        stack.setData(DataComponentTypes.ITEM_NAME, Text.mm("<" + def.rarity().color() + ">" + def.name()));
        stack.setData(DataComponentTypes.TOOLTIP_STYLE, Key.key(Keys.NS, def.rarity().id()));
        List<String> lore = new ArrayList<>();
        // 장비는 레벨 제한 없이 요구 능력치만, 소모품은 사용 레벨
        String req = def.isGear() ? def.requirement().text() : def.levelReq() > 1 ? "사용 레벨 " + def.levelReq() : "";
        lore.add("<" + def.rarity().color() + ">" + def.rarity().displayName() + (req.isEmpty() ? "" : " <gray>· " + req));
        if (def.lore() != null && !def.lore().isBlank()) lore.add("<dark_gray>" + Text.escape(def.lore()));
        stack.setData(DataComponentTypes.LORE, ItemLore.lore(Text.itemLines(lore)));
        stack.editPersistentDataContainer(pdc -> pdc.set(Keys.ITEM_ID, PersistentDataType.STRING, id));
        if (def.isTool()) {   // 곡괭이 (0.3.6): 한 칸에 1개 · 구성요소는 광산(MineApi.applyPickaxe)
            stack.setAmount(1);
            stack.setData(DataComponentTypes.MAX_STACK_SIZE, 1);
            stack = GearItemService.applyTool(services, stack, def);
        }
        return stack;
    }

    @Override
    public Optional<ItemDef> defOf(ItemStack stack) {
        if (stack == null || stack.isEmpty()) return Optional.empty();
        String id = stack.getPersistentDataContainer().get(Keys.ITEM_ID, PersistentDataType.STRING);
        return Optional.ofNullable(services.content().item(id));
    }

    @Override
    public Map<String, Double> rolledStats(ItemStack stack) {
        Map<String, Double> out = new HashMap<>();
        defOf(stack).ifPresent(d -> d.stats().forEach((k, r) -> out.put(k, r.lerp(0.5))));
        return out;
    }

    @Override
    public int give(Player player, String id, int amount, String source) {
        ItemDef def = services.content().item(id);
        if (def == null || amount <= 0) return 0;
        int given = 0;
        boolean stackable = !def.isGear() && !def.isTool();
        while (given < amount) {
            int n = stackable ? Math.min(64, amount - given) : 1;
            ItemStack s = create(id, n);
            if (s == null) break;
            player.getInventory().addItem(s).values()
                    .forEach(left -> player.getWorld().dropItem(player.getLocation(), left, it -> it.setOwner(player.getUniqueId())));
            Bukkit.getPluginManager().callEvent(new ItemObtainEvent(player, def, s, source));
            given += n;
        }
        return given;
    }
}
