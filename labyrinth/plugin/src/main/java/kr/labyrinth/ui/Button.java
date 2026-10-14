package kr.labyrinth.ui;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.ItemLore;
import io.papermc.paper.datacomponent.item.TooltipDisplay;
import java.util.List;
import java.util.function.Consumer;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import net.kyori.adventure.key.Key;
import org.bukkit.Material;
import org.bukkit.inventory.ItemStack;

/** 메뉴 버튼 = 아이콘 + 클릭 콜백(없으면 장식). */
public record Button(ItemStack icon, Consumer<ClickContext> action) {

    public static Button deco(ItemStack icon) { return new Button(icon, null); }

    /** 아이콘 아이템 만들기: 이름·설명은 MiniMessage (기울임 제거). */
    public static ItemStack icon(Material material, String name, List<String> lore) {
        ItemStack s = ItemStack.of(material);
        s.setData(DataComponentTypes.ITEM_NAME, Text.item(name));
        if (lore != null && !lore.isEmpty()) s.setData(DataComponentTypes.LORE, ItemLore.lore(Text.itemLines(lore)));
        return s;
    }

    /** 리소스팩 모델(labyrinth:&lt;model&gt;)을 쓰는 아이콘. 팩이 없으면 base 재질로 보인다. */
    public static ItemStack icon(Material base, String model, String name, List<String> lore) {
        ItemStack s = icon(base, name, lore);
        if (model != null) s.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, model));
        return s;
    }

    /** 툴팁 없는 빈 칸 채우기용 아이콘. */
    public static ItemStack filler(Material material) {
        ItemStack s = ItemStack.of(material);
        s.setData(DataComponentTypes.TOOLTIP_DISPLAY, TooltipDisplay.tooltipDisplay().hideTooltip(true).build());
        return s;
    }
}
