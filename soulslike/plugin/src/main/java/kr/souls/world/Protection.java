package kr.souls.world;

import org.bukkit.GameMode;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.ArmorStand;
import org.bukkit.entity.Entity;
import org.bukkit.entity.FallingBlock;
import org.bukkit.entity.ItemFrame;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockBurnEvent;
import org.bukkit.event.block.BlockFadeEvent;
import org.bukkit.event.block.BlockFormEvent;
import org.bukkit.event.block.BlockFromToEvent;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.block.BlockSpreadEvent;
import org.bukkit.event.block.LeavesDecayEvent;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.hanging.HangingBreakByEntityEvent;
import org.bukkit.event.hanging.HangingPlaceEvent;
import org.bukkit.event.player.PlayerArmorStandManipulateEvent;
import org.bukkit.event.player.PlayerBucketEmptyEvent;
import org.bukkit.event.player.PlayerBucketFillEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerRecipeDiscoverEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

/**
 * 모험 모드 보호 (12.7). 모험 모드에서도 혹시 몰라 블록 부수기·놓기·양동이·액자·갑옷 거치대·밭 밟기·잎 사라짐·물 흐름을 막는다.
 * 바닐라 블록 상호작용(문, 레버, 상자, 캠프파이어 끄기 등)은 허용 목록 밖에서 막는다 (2.3.8, M0 의 허용 목록은 비어 있다).
 * 블록을 막을 때도 손에 든 아이템 쓰기(막기, 마시기)는 그대로 둔다. 버리기는 막는다 (2.3.4). 다만 막으면 사라지는 것 (가방이 다 차
 * 되돌릴 자리가 없는 것) 은 막지 않고 발밑에 떨어지게 둔다 ({@link #fitsBack}).
 * 창작 모드 + souls.build 권한이면 무엇이든 된다 (지도 손보기).
 */
public final class Protection implements Listener {
    private final WorldService worlds;

    public Protection(WorldService worlds) {
        this.worlds = worlds;
    }

    private boolean ours(World w) {
        return worlds.ours(w);
    }

    static boolean builder(Player p) {
        return p.getGameMode() == GameMode.CREATIVE && p.hasPermission("souls.build");
    }

    private void guard(Cancellable e, Player p, World w) {
        if (ours(w) && (p == null || !builder(p))) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onBreak(BlockBreakEvent e) {
        guard(e, e.getPlayer(), e.getBlock().getWorld());
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent e) {
        guard(e, e.getPlayer(), e.getBlock().getWorld());
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onBucket(PlayerBucketEmptyEvent e) {
        guard(e, e.getPlayer(), e.getBlock().getWorld());
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onBucket(PlayerBucketFillEvent e) {
        guard(e, e.getPlayer(), e.getBlock().getWorld());
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onHangingBreak(HangingBreakByEntityEvent e) {
        guard(e, e.getRemover() instanceof Player p ? p : null, e.getEntity().getWorld());
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onHangingPlace(HangingPlaceEvent e) {
        guard(e, e.getPlayer(), e.getEntity().getWorld());
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onArmorStand(PlayerArmorStandManipulateEvent e) {
        guard(e, e.getPlayer(), e.getRightClicked().getWorld());
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onFrame(PlayerInteractEntityEvent e) {
        Entity t = e.getRightClicked();
        if (t instanceof ItemFrame || t instanceof ArmorStand) guard(e, e.getPlayer(), t.getWorld());
    }

    /**
     * 버리기 막기. 막으면 CraftBukkit 이 그 아이템을 되돌린다: 바닐라가 손에서 버린 것이면 빈 손에 (또는 같은 것 하나를 손의 묶음에)
     * 넣고, 그 밖 (창을 닫을 때·나갈 때·다른 세계로 갈 때 손 (커서) 에 든 것과 2×2 의 것을 돌려주다 넘친 것) 은 addItem 으로 넣고
     * 넘친 것을 버린다. 그래서 가방에 자리가 없으면 막지 않는다: 아이템은 사라지지 않고 발밑에 떨어진다 (검토 R1: 가방이 찬 채 왼손이나
     * 반지 칸에서 집은 것을 들고 창을 닫으면 사라졌다).
     */
    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onDrop(PlayerDropItemEvent e) {
        Player p = e.getPlayer();
        if (!ours(p.getWorld()) || builder(p)) return;
        if (fitsBack(p.getInventory(), e.getItemDrop().getItemStack())) e.setCancelled(true);
    }

    /**
     * it 이 가방·단축 줄 (0..35, addItem 이 보는 칸) 에 다 들어가나: 빈 칸, 그리고 같은 것이 쌓인 칸의 남은 자리를 센다. 손 (든 칸) 이
     * 비었으면 그 칸도 빈 칸이라 들어간다. 손의 묶음에 하나를 더하는 길도 같은 것이 쌓인 칸의 남은 자리로 셈에 든다.
     */
    public static boolean fitsBack(PlayerInventory inv, ItemStack it) {
        if (it == null || it.isEmpty()) return true;
        int need = it.getAmount();
        int max = Math.min(it.getMaxStackSize(), inv.getMaxStackSize());
        ItemStack[] all = inv.getStorageContents();
        for (ItemStack cur : all) {
            if (cur == null || cur.isEmpty()) need -= max;
            else if (cur.isSimilar(it)) need -= Math.max(0, Math.min(cur.getMaxStackSize(), inv.getMaxStackSize()) - cur.getAmount());
            if (need <= 0) return true;
        }
        return false;
    }

    /** 밭 밟기·압력판 같은 발 상호작용, 그리고 바닐라 블록 상호작용. */
    @EventHandler(priority = EventPriority.LOW)
    public void onInteract(PlayerInteractEvent e) {
        Block b = e.getClickedBlock();
        if (b == null || !ours(b.getWorld()) || builder(e.getPlayer())) return;
        if (e.getAction() == Action.PHYSICAL) {
            e.setCancelled(true);
            return;
        }
        if (e.getAction() == Action.RIGHT_CLICK_BLOCK) {
            // 블록만 막는다 (허용 목록 밖은 모두). 손에 든 아이템 쓰기는 그대로 (막는 방패를 벽 쪽으로 들어도 된다)
            e.setUseInteractedBlock(Event.Result.DENY);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityChange(EntityChangeBlockEvent e) {
        if (e.getEntity() instanceof Player p) {
            guard(e, p, e.getBlock().getWorld());
            return;
        }
        // 떨어지는 블록이 내려앉는 것은 둔다 (재로 쓰는 콘크리트 가루)
        if (!(e.getEntity() instanceof FallingBlock) && ours(e.getBlock().getWorld())) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onDecay(LeavesDecayEvent e) {
        guard(e, null, e.getBlock().getWorld());
    }

    @EventHandler(ignoreCancelled = true)
    public void onFlow(BlockFromToEvent e) {
        guard(e, null, e.getBlock().getWorld());
    }

    @EventHandler(ignoreCancelled = true)
    public void onBurn(BlockBurnEvent e) {
        guard(e, null, e.getBlock().getWorld());
    }

    @EventHandler(ignoreCancelled = true)
    public void onIgnite(BlockIgniteEvent e) {
        if (e.getPlayer() != null && builder(e.getPlayer())) return;
        guard(e, null, e.getBlock().getWorld());
    }

    @EventHandler(ignoreCancelled = true)
    public void onFade(BlockFadeEvent e) {
        guard(e, null, e.getBlock().getWorld());
    }

    @EventHandler(ignoreCancelled = true)
    public void onForm(BlockFormEvent e) {
        guard(e, null, e.getBlock().getWorld());
    }

    @EventHandler(ignoreCancelled = true)
    public void onSpread(BlockSpreadEvent e) {
        guard(e, null, e.getBlock().getWorld());
    }

    /** 처음 집은 아이템마다 뜨는 "새로운 제작법" 알림을 막는다. 이 게임에는 제작이 없다 */
    @EventHandler(ignoreCancelled = true)
    public void onRecipe(PlayerRecipeDiscoverEvent e) {
        if (ours(e.getPlayer().getWorld())) e.setCancelled(true);
    }
}
