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

/**
 * 모험 모드 보호 (12.7). 모험 모드에서도 혹시 몰라 블록 부수기·놓기·양동이·액자·갑옷 거치대·밭 밟기·잎 사라짐·물 흐름을 막는다.
 * 바닐라 블록 상호작용(문, 레버, 상자, 캠프파이어 끄기 등)은 허용 목록 밖에서 막는다 (2.3.8, M0 의 허용 목록은 비어 있다).
 * 블록을 막을 때도 손에 든 아이템 쓰기(막기, 마시기)는 그대로 둔다. 버리기는 늘 막는다 (2.3.4).
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

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onDrop(PlayerDropItemEvent e) {
        guard(e, e.getPlayer(), e.getPlayer().getWorld());
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
