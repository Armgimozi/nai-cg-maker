package kr.labyrinth.items.crafting;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.event.CraftEvent;
import kr.labyrinth.event.ItemObtainEvent;
import kr.labyrinth.items.CraftingService;
import kr.labyrinth.items.GearItemService;
import org.bukkit.Bukkit;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

/**
 * 대장장이 제작 (GDD §11.11): 레벨 → 재료 → 골드(craft_discount 할인) 확인 → 재료·골드 소모 → 결과 스탯 굴림 지급.
 * 성공 시 {@link CraftEvent} + {@link ItemObtainEvent}(source=craft).
 */
public final class LabCraftingService implements CraftingService {

    private final Services services;
    /** 강화 (대장간 [강화] 버튼 → 강화 창). ItemsModule 이 붙인다. */
    private kr.labyrinth.items.enhance.EnhanceService enhance;

    public LabCraftingService(Services services) { this.services = services; }

    public void setEnhance(kr.labyrinth.items.enhance.EnhanceService enhance) { this.enhance = enhance; }

    public kr.labyrinth.items.enhance.EnhanceService enhance() { return enhance; }

    /** 인벤토리 안의 미궁 아이템 id 개수. */
    public int count(Player p, String itemId) {
        int n = 0;
        for (ItemStack s : p.getInventory().getStorageContents()) {
            if (s == null || s.isEmpty()) continue;
            if (services.items().defOf(s).map(d -> d.id().equals(itemId)).orElse(false)) n += s.getAmount();
        }
        return n;
    }

    public long goldCost(Player p, RecipeDef r) {
        return RecipeCheck.goldCost(r, services.stats().get(p).craftDiscount());
    }

    @Override
    public Result check(Player player, RecipeDef recipe) {
        if (recipe == null || services.content().item(recipe.result()) == null) return Result.UNKNOWN_RECIPE;
        PlayerData d = services.data().get(player);
        return RecipeCheck.check(recipe, d.level(), d.gold(), services.stats().get(player).craftDiscount(),
                id -> count(player, id));
    }

    @Override
    public Result craft(Player player, String recipeId) {
        RecipeDef r = services.content().recipes().get(recipeId);
        Result res = check(player, r);
        if (res != Result.OK) return res;
        ItemDef result = services.content().item(r.result());
        int amount = Math.max(1, r.amount());
        if (!hasRoom(player.getInventory(), result, amount)) return Result.INVENTORY_FULL;
        PlayerData d = services.data().get(player);
        long gold = goldCost(player, r);
        if (!d.takeGold(gold)) return Result.NOT_ENOUGH_GOLD;
        for (Map.Entry<String, Integer> m : r.materials().entrySet()) remove(player, m.getKey(), m.getValue());

        List<ItemStack> made = new ArrayList<>();
        int left = amount;
        int max = GearItemService.maxStack(result);
        while (left > 0) {
            int n = result.isGear() ? 1 : Math.min(max, left);
            ItemStack s = services.items().create(result.id(), n);
            if (s == null) break;
            made.add(s);
            left -= n;
        }
        for (ItemStack s : made) {
            GearItemService.deliver(player, s);
            Bukkit.getPluginManager().callEvent(new ItemObtainEvent(player, result, s, "craft"));
        }
        if (!made.isEmpty()) Bukkit.getPluginManager().callEvent(new CraftEvent(player, r, made.get(0)));
        services.hud().refresh(player);
        player.playSound(player.getLocation(), Sound.BLOCK_ANVIL_USE, 0.7f, 1.2f);
        player.playSound(player.getLocation(), Sound.BLOCK_SMITHING_TABLE_USE, 0.8f, 1.0f);
        player.spawnParticle(Particle.LAVA, player.getLocation().add(0, 1, 0), 6, 0.3, 0.3, 0.3, 0);
        Text.send(player, "<" + result.rarity().color() + ">" + result.name() + (amount > 1 ? " ×" + amount : "")
                + "</" + result.rarity().color() + "> <gray>제작 완료! <dark_gray>(-" + Text.num(gold) + " 골드)");
        return Result.OK;
    }

    private boolean hasRoom(PlayerInventory inv, ItemDef def, int amount) {
        if (inv.firstEmpty() != -1) return true;
        if (def.isGear()) return false;
        int room = 0;
        for (ItemStack s : inv.getStorageContents()) {
            if (s == null || s.isEmpty()) continue;
            if (services.items().defOf(s).map(x -> x.id().equals(def.id())).orElse(false) && s.isSimilar(services.items().create(def.id(), 1))) {
                room += Math.max(0, GearItemService.maxStack(def) - s.getAmount());
            }
        }
        return room >= amount;
    }

    private void remove(Player p, String itemId, int amount) {
        int left = amount;
        ItemStack[] contents = p.getInventory().getStorageContents();
        for (int i = 0; i < contents.length && left > 0; i++) {
            ItemStack s = contents[i];
            if (s == null || s.isEmpty()) continue;
            if (!services.items().defOf(s).map(d -> d.id().equals(itemId)).orElse(false)) continue;
            int take = Math.min(left, s.getAmount());
            s.setAmount(s.getAmount() - take);
            left -= take;
            contents[i] = s.getAmount() <= 0 ? null : s;
        }
        p.getInventory().setStorageContents(contents);
    }

    @Override
    public void openBlacksmith(Player player) {
        new BlacksmithMenu(services, this, player).open(player);
        player.playSound(player.getLocation(), Sound.BLOCK_ANVIL_PLACE, 0.4f, 1.4f);
    }

    /** 결과 안내 문구. */
    public static String message(Result r) {
        return switch (r) {
            case OK -> "제작 완료";
            case UNKNOWN_RECIPE -> "알 수 없는 레시피입니다.";
            case LEVEL_TOO_LOW -> "레벨이 부족합니다.";
            case MISSING_MATERIALS -> "재료가 부족합니다.";
            case NOT_ENOUGH_GOLD -> "골드가 부족합니다.";
            case INVENTORY_FULL -> "인벤토리에 빈 칸이 없습니다.";
            case NOT_AVAILABLE -> "지금은 제작할 수 없습니다.";
        };
    }
}
