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
import kr.labyrinth.mine.MineNames;
import org.bukkit.Bukkit;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

/**
 * 대장장이 제작 (GDD §11.11): 도안(0.3.6 — 희귀 이상 장비, items/blueprint) → 재료 → 골드(craft_discount 할인) 확인 → 재료·골드 소모 → 결과 스탯 굴림 지급.
 * 성공 시 {@link CraftEvent} + {@link ItemObtainEvent}(source=craft). 신화를 만들면 서버 방송 (0.3.7 — 신화 드롭 방송과 같은 꼴).
 * <p>
 * 0.3.6 제련소 (recipes.yml {@code station: smelter}): 대장간 창에는 {@code station: blacksmith} 레시피만, 제련소 창({@link SmelterMenu})에는
 * smelter 레시피만 보인다. 제련은 ×1·×8·전부({@link #craftMany}), 곡괭이 벼리기는 앞 곡괭이를 재료로 받아 없앤다(레시피 재료 그대로).
 * 광부 상점({@link MineShopMenu}) = 첫 구리 곡괭이 무료(ext mine.free_pickaxe) · 그 뒤 50G · 팔기(SellMenu 그대로) · 제련소.
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

    /** 골드 (craft_discount 할인). 제련소 레시피는 할인 없음 — 녹여 팔아 남는 일이 없게 (계약 §2.11). */
    public long goldCost(Player p, RecipeDef r) {
        return RecipeCheck.goldCost(r, discount(p, r));
    }

    private double discount(Player p, RecipeDef r) {
        return MineNames.STATION_SMELTER.equals(station(r)) ? 0 : services.stats().get(p).craftDiscount();
    }

    @Override
    public Result check(Player player, RecipeDef recipe) {
        if (recipe == null || services.content().item(recipe.result()) == null) return Result.UNKNOWN_RECIPE;
        if (!blueprintOk(player, recipe)) return Result.NEEDS_BLUEPRINT; // 0.3.6 Q6: 희귀 이상 장비는 도안을 배워야
        PlayerData d = services.data().get(player);
        return RecipeCheck.check(recipe, d.level(), d.gold(), discount(player, recipe), id -> count(player, id));
    }

    /** recipes.yml station (비면 대장간). */
    public static String station(RecipeDef r) {
        return r == null || r.station() == null || r.station().isBlank() ? MineNames.STATION_BLACKSMITH : r.station();
    }

    /** 도안 기준으로 만들 수 있는가 (도안 서비스가 없으면 막지 않는다). */
    public boolean blueprintOk(Player player, RecipeDef recipe) {
        kr.labyrinth.items.blueprint.BlueprintService bp = kr.labyrinth.items.blueprint.BlueprintService.get();
        return bp == null || bp.canCraft(player, recipe);
    }

    @Override
    public Result craft(Player player, String recipeId) {
        RecipeDef r = services.content().recipes().get(recipeId);
        Result res = craftOnce(player, r);
        if (res != Result.OK) return res;
        ItemDef result = services.content().item(r.result());
        int amount = Math.max(1, r.amount());
        services.hud().refresh(player);
        effects(player, r);
        Text.send(player, "<" + result.rarity().color() + ">" + result.name() + (amount > 1 ? " ×" + amount : "")
                + "</" + result.rarity().color() + "> <gray>" + verb(r) + " 완료! <dark_gray>(-" + Text.num(goldCost(player, r)) + " 골드)");
        return Result.OK;
    }

    /**
     * 같은 레시피를 times 번까지 (제련 ×8 · 전부 = Integer.MAX_VALUE). 재료·골드·가방 자리가 모자라면 거기서 멈춘다.
     * @return [만든 횟수, 첫 실패 까닭 ordinal(없으면 -1)]
     */
    public int[] craftMany(Player player, String recipeId, int times) {
        RecipeDef r = services.content().recipes().get(recipeId);
        int done = 0;
        Result last = Result.OK;
        long spent = 0;
        int cap = Math.max(1, Math.min(times, 64 * 36));
        while (done < cap) {
            long cost = r == null ? 0 : goldCost(player, r);
            last = craftOnce(player, r);
            if (last != Result.OK) break;
            spent += cost;
            done++;
        }
        if (done > 0) {
            ItemDef result = services.content().item(r.result());
            int amount = Math.max(1, r.amount()) * done;
            services.hud().refresh(player);
            effects(player, r);
            Text.send(player, "<" + result.rarity().color() + ">" + result.name() + " ×" + amount
                    + "</" + result.rarity().color() + "> <gray>" + verb(r) + " 완료! <dark_gray>(-" + Text.num(spent) + " 골드)");
        }
        return new int[] {done, done > 0 && last == Result.OK ? -1 : last.ordinal()};
    }

    private static String verb(RecipeDef r) {
        if (!MineNames.STATION_SMELTER.equals(station(r))) return "제작";
        if (MineNames.CATEGORY_TOOL.equals(r.category())) return "벼리기";
        return r.amount() > 1 ? "새기기" : "제련";
    }

    private void effects(Player player, RecipeDef r) {
        if (MineNames.STATION_SMELTER.equals(station(r))) {
            player.playSound(player.getLocation(), Sound.BLOCK_BLASTFURNACE_FIRE_CRACKLE, 0.8f, 1.0f);
            player.playSound(player.getLocation(), Sound.BLOCK_ANVIL_USE, 0.5f, 1.4f);
            player.spawnParticle(Particle.FLAME, player.getLocation().add(0, 1, 0), 8, 0.3, 0.3, 0.3, 0.01);
            return;
        }
        player.playSound(player.getLocation(), Sound.BLOCK_ANVIL_USE, 0.7f, 1.2f);
        player.playSound(player.getLocation(), Sound.BLOCK_SMITHING_TABLE_USE, 0.8f, 1.0f);
        player.spawnParticle(Particle.LAVA, player.getLocation().add(0, 1, 0), 6, 0.3, 0.3, 0.3, 0);
    }

    /** 한 번 만들기 (알림·소리 없이) — 확인 → 재료·골드 소모 → 지급 → 이벤트. */
    private Result craftOnce(Player player, RecipeDef r) {
        Result res = check(player, r);
        if (res != Result.OK) return res;
        ItemDef result = services.content().item(r.result());
        int amount = Math.max(1, r.amount());
        if (!hasRoom(player.getInventory(), result, amount) && !freesSlot(r)) return Result.INVENTORY_FULL;
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
        String source = MineNames.STATION_SMELTER.equals(station(r)) ? MineNames.SOURCE_SMELT : "craft";
        for (ItemStack s : made) {
            GearItemService.deliver(player, s);
            Bukkit.getPluginManager().callEvent(new ItemObtainEvent(player, result, s, source));
        }
        if (!made.isEmpty()) {
            Bukkit.getPluginManager().callEvent(new CraftEvent(player, r, made.get(0)));
            if (result.isGear() && result.rarity() == kr.labyrinth.content.Rarity.MYTHIC) announceMythic(player, result);
        }
        return Result.OK;
    }

    /** 신화를 대장간에서 만들었을 때 서버 방송 + 소리 (loot.yml announce_rarity 가 신화보다 높으면 하지 않음). */
    private void announceMythic(Player player, ItemDef result) {
        kr.labyrinth.content.Rarity announce = services.content().lootSettings().announceRarity();
        if (announce == null || !result.rarity().atLeast(announce)) return;
        Bukkit.getServer().sendMessage(Text.mm(mythicCraftLine(player.getName(), result)));
        for (Player o : Bukkit.getOnlinePlayers()) o.playSound(o.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.7f, 0.8f);
    }

    /** 신화 제작 방송 글 (MiniMessage) — 신화 드롭 방송과 같은 꼴. */
    public static String mythicCraftLine(String player, ItemDef result) {
        kr.labyrinth.content.Rarity r = result.rarity();
        return Text.PREFIX + "<white>" + Text.escape(player) + "</white><gray> 님이 대장간에서 </gray><" + r.color() + "><b>["
                + r.displayName() + "]</b> " + result.name() + "<gray> 을(를) 만들었습니다!";
    }

    /** 곡괭이 벼리기처럼 한 칸짜리 도구를 재료로 없애면 가방이 꽉 차 있어도 그 칸에 새 것이 들어간다. */
    private boolean freesSlot(RecipeDef r) {
        for (String id : r.materials().keySet()) {
            ItemDef m = services.content().item(id);
            if (m != null && (m.isTool() || m.isGear())) return true;
        }
        return false;
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

    /** 제련소 (구역 제련공 · interact smelter · 광산 관리소). 레벨 조건 없음. */
    @Override
    public void openSmelter(Player player) { openSmelter(player, "smelt"); }

    @Override
    public void openSmelter(Player player, String tab) {
        new SmelterMenu(services, this, SmelterMenu.Tab.of(tab)).open(player);
        player.playSound(player.getLocation(), Sound.BLOCK_BLASTFURNACE_FIRE_CRACKLE, 0.6f, 1.0f);
    }

    /** 광부 상점 (첫 곡괭이 무료 · 구리 곡괭이 사기 · 팔기 · 제련소). */
    @Override
    public void openMineShop(Player player) {
        new MineShopMenu(services, this).open(player);
        player.playSound(player.getLocation(), Sound.BLOCK_CHAIN_PLACE, 0.5f, 0.8f);
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
            case NEEDS_BLUEPRINT -> "도안을 먼저 배워야 합니다.";
        };
    }
}
