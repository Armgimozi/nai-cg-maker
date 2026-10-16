package kr.labyrinth.items.blueprint;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.CustomModelData;
import io.papermc.paper.datacomponent.item.ItemLore;
import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import kr.labyrinth.items.ItemTooltip;
import net.kyori.adventure.key.Key;
import org.bukkit.Color;
import org.bukkit.NamespacedKey;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

/**
 * 도안 아이템 (0.3.6 Q6): items.yml {@code blueprint} 하나 + PDC {@code labyrinth:blueprint_recipe} = 가르치는 레시피 id.
 * 이름 "도안: &lt;장비 이름&gt;" (장비 희귀도 색), 설명 = 무엇을 가르치는지 + "우클릭: 배우기". 툴팁 테두리·그림 색 = 장비 희귀도
 * (리소스팩 labyrinth:blueprint 의 둘째 층을 CUSTOM_MODEL_DATA 색으로 칠한다). 같은 레시피 도안끼리만 겹친다.
 */
public final class BlueprintItems {

    public static final NamespacedKey RECIPE = Keys.key("blueprint_recipe");

    private BlueprintItems() {}

    /** 도안 amount 장 (아이템 정의·레시피가 없으면 null). */
    public static ItemStack create(Services services, String recipeId, int amount) {
        Content c = services.content();
        if (c.item(BlueprintRules.ITEM_ID) == null || recipeId == null || c.recipes().get(recipeId) == null) return null;
        ItemStack s = services.items().create(BlueprintRules.ITEM_ID, Math.max(1, amount));
        if (s == null) return null;
        s.editPersistentDataContainer(p -> p.set(RECIPE, PersistentDataType.STRING, recipeId));
        render(s, c);
        return s;
    }

    /** 이 아이템이 가르치는 레시피 id (도안이 아니거나 비었으면 null). */
    public static String recipeOf(ItemStack s) {
        if (s == null || s.isEmpty()) return null;
        var pdc = s.getPersistentDataContainer();
        if (!BlueprintRules.ITEM_ID.equals(pdc.get(Keys.ITEM_ID, PersistentDataType.STRING))) return null;
        return pdc.get(RECIPE, PersistentDataType.STRING);
    }

    public static boolean isBlueprint(ItemStack s) {
        return s != null && !s.isEmpty()
                && BlueprintRules.ITEM_ID.equals(s.getPersistentDataContainer().get(Keys.ITEM_ID, PersistentDataType.STRING));
    }

    /** 장비 희귀도 (모르면 희귀). */
    public static Rarity rarityOf(Content c, String recipeId) {
        RecipeDef r = recipeId == null ? null : c.recipes().get(recipeId);
        ItemDef d = r == null ? null : c.item(r.result());
        return d == null || d.rarity() == null ? Rarity.RARE : d.rarity();
    }

    /** 이름·설명·색을 PDC 레시피에서 다시 그린다 (GearItemService.render 가 부른다). */
    public static void render(ItemStack s, Content c) {
        String rid = s.getPersistentDataContainer().get(RECIPE, PersistentDataType.STRING);
        RecipeDef r = rid == null ? null : c.recipes().get(rid);
        ItemDef d = r == null ? null : c.item(r.result());
        if (d == null) {
            s.setData(DataComponentTypes.ITEM_NAME, Text.item("<gray>빈 도안"));
            s.setData(DataComponentTypes.LORE, ItemLore.lore(Text.itemLines(List.of("<dark_gray>아무것도 적혀 있지 않다."))));
            return;
        }
        Rarity rar = d.rarity() == null ? Rarity.RARE : d.rarity();
        s.setData(DataComponentTypes.ITEM_NAME, Text.item("<" + rar.color() + ">도안: " + d.name()));
        s.setData(DataComponentTypes.TOOLTIP_STYLE, Key.key(Keys.NS, rar.id()));
        s.setData(DataComponentTypes.CUSTOM_MODEL_DATA, CustomModelData.customModelData()
                .addColor(Color.fromRGB(Integer.parseInt(rar.color().substring(1), 16))).build());
        s.setData(DataComponentTypes.LORE, ItemLore.lore(Text.itemLines(lore(d, rar))));
    }

    static List<String> lore(ItemDef d, Rarity rar) {
        List<String> out = new ArrayList<>();
        out.add("<gray>" + ItemTooltip.category(d) + " · <" + rar.color() + ">" + rar.displayName());
        out.add("<gray>대장간에서 <white>" + d.name() + "</white>");
        out.add("<gray>을(를) 만드는 법이 적혀 있다.");
        out.add("");
        out.add("<#ffd27a>우클릭: 배우기");
        out.add("<dark_gray>한 번 배우면 계속 안다. 이미 알면 남에게 주거나 팔자.");
        return out;
    }
}
