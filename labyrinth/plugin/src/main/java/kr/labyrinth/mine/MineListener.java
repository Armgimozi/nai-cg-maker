package kr.labyrinth.mine;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ToolSpec;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.entity.EnderPearl;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityCombustEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntitySpawnEvent;
import org.bukkit.event.entity.FoodLevelChangeEvent;
import org.bukkit.event.entity.ProjectileLaunchEvent;
import org.bukkit.event.player.PlayerAnimationEvent;
import org.bukkit.event.player.PlayerAnimationType;
import org.bukkit.event.player.PlayerBucketEmptyEvent;
import org.bukkit.event.player.PlayerBucketFillEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.RayTraceResult;

/**
 * 광산 월드 이벤트: 캐기(BlockBreakEvent 는 늘 취소하고 서버가 다시 봄) · 약한 곡괭이 안내 · 승강기·관리소 우클릭 · 안전
 * (피해·불·배고픔·진주·후렴과·양동이·몹 화이트리스트) · 게임 모드 규칙 · 광산 밖 곡괭이 막기.
 */
final class MineListener implements Listener {

    /** 광산 월드에 생길 수 있는 엔티티 (R §2-4). 나머지는 생기지 않는다. */
    static final Set<EntityType> SPAWN_WHITELIST = Set.of(EntityType.MANNEQUIN, EntityType.ITEM_DISPLAY, EntityType.BLOCK_DISPLAY,
            EntityType.TEXT_DISPLAY, EntityType.INTERACTION, EntityType.ITEM);

    private final MineModule module;
    private final Map<UUID, Long> lastBar = new HashMap<>();
    private final Map<UUID, Long> lastOutside = new HashMap<>();

    MineListener(MineModule module) { this.module = module; }

    private boolean mine(org.bukkit.World w) { return module.isMineWorld(w); }

    private boolean throttle(Map<UUID, Long> map, Player p, long ms) {
        long now = System.currentTimeMillis();
        Long last = map.get(p.getUniqueId());
        if (last != null && now - last < ms) return false;
        map.put(p.getUniqueId(), now);
        return true;
    }

    ToolSpec heldTool(Player p) {
        ItemStack hand = p.getInventory().getItemInMainHand();
        if (hand.getType().isAir()) return null;
        ItemDef def = module.services().items().defOf(hand).orElse(null);
        return def != null && def.isTool() ? def.tool() : null;
    }

    // ── 캐기 ────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.HIGH)
    public void onBreak(BlockBreakEvent e) {
        Player p = e.getPlayer();
        Block b = e.getBlock();
        if (!mine(b.getWorld())) {
            outside(e);
            return;
        }
        boolean already = e.isCancelled();
        e.setCancelled(true);
        e.setDropItems(false);
        e.setExpToDrop(0);
        if (already) return;
        MineLevel.Vein v = module.veins().at(b);
        if (v == null) return;
        MineVeins.Harvest h = module.veins().harvest(p, v, heldTool(p), p.getInventory(), ThreadLocalRandom.current(), false);
        module.feedback(p, h);
    }

    /** 광산 밖(오버월드·네더·엔드·미궁)에서 광산 곡괭이로 광산 블록 12종을 부수면 취소 + 안내 (R §3-15). */
    private void outside(BlockBreakEvent e) {
        // 이미 막힌 부수기(미궁 DungeonManager 등)도 안내 글은 보인다
        if (heldTool(e.getPlayer()) == null || !module.isMineBlock(e.getBlock().getType())) return;
        e.setCancelled(true);
        if (throttle(lastOutside, e.getPlayer(), 1000)) module.services().hud().actionBar(e.getPlayer(), Text.mm("<red>" + MineNames.OUTSIDE), 40);
    }

    /** 약한 곡괭이·곡괭이 없음·빈 광맥 안내 (팔 휘두름 + 5칸 시선, 1초에 1번). */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onSwing(PlayerAnimationEvent e) {
        if (e.getAnimationType() != PlayerAnimationType.ARM_SWING) return;
        Player p = e.getPlayer();
        if (!mine(p.getWorld()) || p.getGameMode() == GameMode.SPECTATOR) return;
        RayTraceResult r = p.rayTraceBlocks(5.0);
        if (r == null || r.getHitBlock() == null) return;
        MineLevel.Vein v = module.veins().at(r.getHitBlock());
        if (v == null) return;
        String msg;
        if (module.veins().state().isDepleted(v.key())) {
            double eta = module.veins().state().etaSeconds(v.key(), module.veins().miners());
            msg = "<gray>빈 광맥 · 약 " + kr.labyrinth.ui.UiTheme.clock(Math.round(eta)) + " 뒤 다시 찹니다";
        } else {
            String m = TierRule.message(TierRule.check(heldTool(p), v.node().tier()));
            if (m == null) return;
            msg = "<red>" + m;
        }
        if (throttle(lastBar, p, 1000)) module.services().hud().actionBar(p, Text.mm(msg), 30);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onPlace(BlockPlaceEvent e) {
        if (!mine(e.getBlock().getWorld())) return;
        if (e.getPlayer().getGameMode() == GameMode.CREATIVE && e.getPlayer().hasPermission(kr.labyrinth.command.CommandService.PERM_ADMIN)) return;
        e.setCancelled(true);
    }

    // ── 우클릭: 승강기·관리소 (그 밖의 블록 쓰기는 막음 — 통·보면대 등) ───

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEvent e) {
        Player p = e.getPlayer();
        if (!mine(p.getWorld()) || e.getAction() != Action.RIGHT_CLICK_BLOCK || e.getClickedBlock() == null) return;
        if (e.getHand() != EquipmentSlot.HAND) {
            e.setUseInteractedBlock(Event.Result.DENY);
            return;
        }
        Block b = e.getClickedBlock();
        String what = module.interactAt(b);
        boolean creative = p.getGameMode() == GameMode.CREATIVE;
        if (what != null) {
            e.setCancelled(true);
            if (module.lift().riding(p)) return;
            if (MineNames.INTERACT_LIFT.equals(what)) module.lift().open(p);
            else if (MineNames.INTERACT_OFFICE.equals(what)) module.openOffice(p);
            return;
        }
        if (!creative) e.setUseInteractedBlock(Event.Result.DENY);
    }

    // ── 안전 ────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOWEST)
    public void onDamageEarly(EntityDamageEvent e) {
        if (module.config().safe() && mine(e.getEntity().getWorld())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onDamageLate(EntityDamageEvent e) {
        if (module.config().safe() && mine(e.getEntity().getWorld())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onCombust(EntityCombustEvent e) {
        if (module.config().safe() && mine(e.getEntity().getWorld())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onFood(FoodLevelChangeEvent e) {
        if (!module.config().noHunger() || !mine(e.getEntity().getWorld())) return;
        if (e.getFoodLevel() < e.getEntity().getFoodLevel()) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onSpawn(EntitySpawnEvent e) {
        if (!mine(e.getLocation().getWorld())) return;
        if (!SPAWN_WHITELIST.contains(e.getEntityType())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onLaunch(ProjectileLaunchEvent e) {
        if (e.getEntity() instanceof EnderPearl && mine(e.getEntity().getWorld())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onBucket(PlayerBucketEmptyEvent e) {
        if (mine(e.getBlock().getWorld())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onBucketFill(PlayerBucketFillEvent e) {
        if (mine(e.getBlock().getWorld())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onTeleport(PlayerTeleportEvent e) {
        PlayerTeleportEvent.TeleportCause c = e.getCause();
        boolean blocked = c == PlayerTeleportEvent.TeleportCause.ENDER_PEARL || c == PlayerTeleportEvent.TeleportCause.CHORUS_FRUIT
                || c == PlayerTeleportEvent.TeleportCause.CONSUMABLE_EFFECT;
        if (blocked && mine(e.getFrom().getWorld())) {
            e.setCancelled(true);
            return;
        }
        if (!e.isCancelled() && e.getTo() != null && (mine(e.getTo().getWorld()) || mine(e.getFrom().getWorld()))) {
            Player p = e.getPlayer();
            Bukkit.getScheduler().runTask(module.services().plugin(), () -> module.applyRules(p));
        }
    }

    // ── 게임 모드 규칙 (접속·월드 이동·리스폰) ───────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(module.services().plugin(), () -> {
            if (!p.isOnline()) return;
            module.applyRules(p);
            module.pickaxes().refresh(p);
        }, 2L);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorld(PlayerChangedWorldEvent e) {
        Player p = e.getPlayer();
        module.applyRules(p);
        if (mine(p.getWorld())) module.pickaxes().refresh(p);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(PlayerRespawnEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTask(module.services().plugin(), () -> {
            if (p.isOnline()) module.applyRules(p);
        });
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        lastBar.remove(e.getPlayer().getUniqueId());
        lastOutside.remove(e.getPlayer().getUniqueId());
    }

    static boolean isAir(Material m) { return m == null || m.isAir(); }
}
