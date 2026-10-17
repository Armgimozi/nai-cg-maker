package kr.labyrinth.homes.play;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import kr.labyrinth.Services;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.homes.HomesConfig;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotRole;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 시작 선물 주기 (0.3.7): 한 사람 한 번 (PlayerData ext {@code homes.starter_used} — 주기 전에 먼저 적고 저장).
 * 오두막은 집터 청크를 비동기로 불러 둔 뒤 한 틱에 놓는다 ({@link StarterCottage}, 약 300칸). 그 자리에 이미 블록이 있으면 짓지 않고 꾸러미를 준다.
 * 꾸러미가 가방에 다 안 들어가면 남은 것은 발밑에 떨어뜨린다.
 */
final class StarterGift {

    static final String EXT_USED = "homes.starter_used";
    static final String EXT_KIND = "homes.starter";

    private final Services services;
    private final HomesService service;

    StarterGift(Services services, HomesService service) {
        this.services = services;
        this.service = service;
    }

    boolean used(Player p) { return Boolean.TRUE.equals(services.data().get(p).ext().get(EXT_USED)); }

    /** 고를 수 있나 (집이 있고, 선물을 아직 안 받았고, 줄 것이 있음). */
    boolean available(Player p, PlotGeom home) {
        HomesConfig.Starter st = service.config().starter();
        if (home == null || used(p)) return false;
        return st.kit() || (st.cottage() && !home.custom());
    }

    private void mark(Player p, String kind) {
        PlayerData d = services.data().get(p);
        d.ext().put(EXT_USED, true);
        d.ext().put(EXT_KIND, kind);
        d.markDirty();
        services.data().saveAsync(p);
    }

    /** 집들이 꾸러미. mark = 이번에 선물을 썼다고 적음 (오두막을 못 지어 대신 줄 때는 이미 적었음). */
    void kit(Player p, boolean mark) {
        if (mark) {
            if (used(p)) {
                Text.error(p, "시작 선물은 이미 받았습니다.");
                return;
            }
            if (!service.config().starter().kit()) {
                Text.error(p, "이 서버에서는 꾸러미를 주지 않습니다.");
                return;
            }
            mark(p, "kit");
        }
        List<ItemStack> items = new ArrayList<>();
        items.add(ItemStack.of(Material.CHEST, 2));
        items.add(ItemStack.of(Material.RED_BED, 1));
        items.add(ItemStack.of(Material.CRAFTING_TABLE, 1));
        items.add(ItemStack.of(Material.FURNACE, 1));
        items.add(ItemStack.of(Material.LANTERN, 4));
        items.add(ItemStack.of(Material.OAK_PLANKS, 64));
        items.add(ItemStack.of(Material.GLASS_PANE, 16));
        items.add(ItemStack.of(Material.OAK_DOOR, 1));
        Map<Integer, ItemStack> rest = p.getInventory().addItem(items.toArray(ItemStack[]::new));
        for (ItemStack r : rest.values()) p.getWorld().dropItemNaturally(p.getLocation(), r);
        p.playSound(p.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 0.6f, 1.4f);
        Text.send(p, "<gray>집들이 꾸러미를 받았습니다." + (rest.isEmpty() ? "" : " 가방이 차서 몇 개는 발밑에 두었습니다."));
    }

    /** 작은 오두막 (집터 뒤쪽 가운데). */
    void cottage(Player p, PlotGeom home, StarterCottage.Wood wood) {
        if (used(p)) {
            Text.error(p, "시작 선물은 이미 받았습니다.");
            return;
        }
        if (home == null || home.custom() || !service.config().starter().cottage()) {
            kit(p, true);
            return;
        }
        World w = Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0);
        if (w == null) return;
        mark(p, "cottage_" + wood.key);
        List<StarterCottage.Cell> cells = StarterCottage.plan(home, wood);
        int minX = Integer.MAX_VALUE, maxX = Integer.MIN_VALUE, minZ = Integer.MAX_VALUE, maxZ = Integer.MIN_VALUE;
        for (StarterCottage.Cell c : cells) {
            minX = Math.min(minX, c.x());
            maxX = Math.max(maxX, c.x());
            minZ = Math.min(minZ, c.z());
            maxZ = Math.max(maxZ, c.z());
        }
        List<CompletableFuture<?>> loads = new ArrayList<>();
        for (int cx = minX >> 4; cx <= maxX >> 4; cx++) for (int cz = minZ >> 4; cz <= maxZ >> 4; cz++) loads.add(w.getChunkAtAsync(cx, cz));
        Text.send(p, "<gray>" + wood.label + " 오두막을 짓는 중입니다…");
        CompletableFuture.allOf(loads.toArray(CompletableFuture[]::new)).whenComplete((v, err) ->
                Bukkit.getScheduler().runTask(services.plugin(), () -> place(p, home, wood, cells, w)));
    }

    private void place(Player p, PlotGeom home, StarterCottage.Wood wood, List<StarterCottage.Cell> cells, World w) {
        // 청크를 불러오는 사이 나갔어도 오두막은 짓는다 (집터는 그대로 그 사람 것). 못 지으면 꾸러미 — 나갔으면 선물을 되돌려 다음에 고르게.
        if (service.roleIn(p, home) != PlotRole.OWNER) {
            fallback(p, "집이 바뀌어 오두막을 짓지 않았습니다. 대신 꾸러미를 드립니다.");
            return;
        }
        for (StarterCottage.Cell c : cells) {
            String id = w.getBlockAt(c.x(), c.y(), c.z()).getType().getKey().getKey().toLowerCase(Locale.ROOT);
            boolean okCell = c.y() == home.floorY() ? StarterCottage.replaceableFloor(id) || StarterCottage.replaceableAbove(id)
                    : StarterCottage.replaceableAbove(id);
            if (!okCell) {
                fallback(p, "집터 뒤쪽에 이미 블록이 있어 오두막 대신 꾸러미를 드립니다.");
                return;
            }
        }
        try {
            List<BlockData> data = new ArrayList<>(cells.size());
            for (StarterCottage.Cell c : cells) data.add(Bukkit.createBlockData(c.data()));
            for (int i = 0; i < cells.size(); i++) {
                StarterCottage.Cell c = cells.get(i);
                Block b = w.getBlockAt(c.x(), c.y(), c.z());
                b.setBlockData(data.get(i), false);
            }
        } catch (Throwable t) {
            Log.error("[집] 오두막 놓기 실패 (" + home.label() + ")", t);
            fallback(p, "오두막을 짓다가 문제가 생겨 꾸러미를 드립니다.");
            return;
        }
        Log.info("[집] " + p.getName() + " — " + home.label() + " 에 " + wood.label + " 오두막 (" + cells.size() + "칸)");
        if (!p.isOnline()) return;
        p.playSound(p.getLocation(), Sound.BLOCK_WOOD_PLACE, 0.8f, 1.0f);
        p.playSound(p.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 0.6f, 1.4f);
        Text.send(p, "<gray>" + Text.escape(home.label()) + " 뒤쪽에 " + wood.label + " 오두막을 지었습니다. 블록은 마음대로 고쳐도 됩니다.");
    }

    /** 오두막 대신 꾸러미. 그사이 나갔으면 선물을 쓰지 않은 것으로 되돌린다 (나간 사람 가방에는 못 넣음). */
    private void fallback(Player p, String why) {
        if (p.isOnline()) {
            Text.send(p, "<gray>" + why);
            kit(p, false);
            return;
        }
        PlayerData d = services.data().getIfLoaded(p.getUniqueId());
        if (d == null) d = services.data().loadOffline(p);
        if (d == null) return;
        d.ext().remove(EXT_USED);
        d.ext().remove(EXT_KIND);
        d.markDirty();
        services.data().saveOffline(d);
    }
}
