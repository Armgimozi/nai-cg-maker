package kr.labyrinth.homes.rules;

import io.papermc.paper.event.player.PlayerOpenSignEvent;
import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.village.VillageService;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.BlockState;
import org.bukkit.block.data.Bisected;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.type.Bed;
import org.bukkit.block.data.type.Stairs;
import org.bukkit.block.data.type.TrapDoor;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LeashHitch;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockMultiPlaceEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.block.SignChangeEvent;
import org.bukkit.event.entity.EntityPlaceEvent;
import org.bukkit.event.entity.PlayerLeashEntityEvent;
import org.bukkit.event.hanging.HangingBreakByEntityEvent;
import org.bukkit.event.hanging.HangingBreakEvent;
import org.bukkit.event.hanging.HangingPlaceEvent;
import org.bukkit.event.player.PlayerBucketEmptyEvent;
import org.bukkit.event.player.PlayerBucketEntityEvent;
import org.bukkit.event.player.PlayerBucketFillEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.vehicle.VehicleDamageEvent;
import org.bukkit.event.vehicle.VehicleDestroyEvent;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;

/**
 * 주 월드 지형 잠금 + 집터 블록 권한 (0.3.7, plan §9·§10 · review R4) — 우선순위 LOW. 소유: 묶음 B.
 * <p>
 * 차례: 집 기능이 안 움직임 · 주 월드 아님 → 끝 · 그 칸이 어디인지 (집터 → 주인·초대·손님 / 보호 상자 / 그 밖 잠금 켜짐·꺼짐) → {@link PlotRules} 표.
 * 보호 상자 칸은 표가 PASS 를 주면 손대지 않는다 (마을 핸들러 HIGH 가 막고 마을 글 — 글은 한 번). 마을 핸들러가 없는 것
 * (EntityPlace · VehicleDestroy · SignChange · 끈 · 엔티티 양동이) 은 여기서 막는다 (R4).
 * 이사 기간: 그 밖의 사람이 놓은 블록만 부수기 (Nature UNNATURAL · 지속 잎). 글: 풀·꽃은 글 없이, 나머지 2초에 한 번.
 */
public final class TerrainLockListener implements Listener {

    public static final String EXT_GRACE_NOTICE = "homes.grace_notice";

    private final HomesService service;
    private final Guard guard;

    public TerrainLockListener(HomesService service) {
        this.service = service;
        this.guard = service.guard();
    }

    HomesService service() { return service; }

    private boolean off(World w) { return !service.active() || !service.isMain(w); }

    // ── 부수기·놓기 ──────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onBreak(BlockBreakEvent e) {
        Block b = e.getBlock();
        if (off(b.getWorld())) return;
        Player p = e.getPlayer();
        PlotRules.Where w = guard.where(p, b);
        boolean grace = w == PlotRules.Where.WILD_LOCKED && guard.graceBreakable(b);
        if (guard.deny(p, PlotRules.Act.BREAK, w, b, grace)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent e) {
        Block b = e.getBlockPlaced();
        if (off(b.getWorld())) return;
        Player p = e.getPlayer();
        List<Block> cells = new ArrayList<>();
        cells.add(b);
        if (e instanceof BlockMultiPlaceEvent mp) for (BlockState st : mp.getReplacedBlockStates()) cells.add(st.getBlock());
        BlockData d = b.getBlockData();
        if (d instanceof Bisected bi && bi.getHalf() == Bisected.Half.BOTTOM && !(d instanceof Stairs) && !(d instanceof TrapDoor)) {
            cells.add(b.getRelative(BlockFace.UP)); // 문·큰 꽃 윗칸도 같은 창 안 (R4)
        }
        if (d instanceof Bed bed && bed.getPart() == Bed.Part.FOOT) cells.add(b.getRelative(bed.getFacing()));
        PlotRules.Where w = guard.whereAll(p, cells);
        boolean banned = service.config().denyPlace().contains(PlotRules.key(b.getType().name()));
        if (guard.deny(p, banned ? PlotRules.Act.PLACE_BANNED : PlotRules.Act.PLACE, w, b, false)) e.setCancelled(true);
    }

    // ── 양동이 ───────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onBucketEmpty(PlayerBucketEmptyEvent e) {
        Block b = e.getBlock();
        if (off(b.getWorld())) return;
        boolean banned = service.config().denyUse().contains(PlotRules.key(e.getBucket().name()));
        PlotRules.Where w = guard.where(e.getPlayer(), b);
        if (guard.deny(e.getPlayer(), banned ? PlotRules.Act.USE_BANNED : PlotRules.Act.BUCKET, w, b, false)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onBucketFill(PlayerBucketFillEvent e) {
        Block b = e.getBlock();
        if (off(b.getWorld())) return;
        if (guard.deny(e.getPlayer(), PlotRules.Act.BUCKET, guard.where(e.getPlayer(), b), b, false)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onBucketEntity(PlayerBucketEntityEvent e) {
        Entity en = e.getEntity();
        if (off(en.getWorld())) return;
        PlotRules.Act act = guard.zone(en) == 0 ? PlotRules.Act.ENTITY_GRAB : PlotRules.Act.ANIMAL;
        if (guard.deny(e.getPlayer(), act, guard.where(e.getPlayer(), en.getLocation()), en.getLocation().getBlock(), false)) e.setCancelled(true);
    }

    // ── 우클릭·좌클릭·밟기 ───────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW)
    public void onInteract(PlayerInteractEvent e) {
        Block b = e.getClickedBlock();
        if (b == null || off(b.getWorld())) return;
        Player p = e.getPlayer();
        Action a = e.getAction();
        if (a == Action.PHYSICAL) {
            PlotRules.Act act = PlotRules.physical(b.getType().name());
            if (act == PlotRules.Act.TRAMPLE && guard.deny(p, act, guard.where(p, b), b, false)) e.setCancelled(true);
            return;
        }
        boolean bypass = Guard.bypass(p);
        PlotRules.Where w = guard.where(p, b);
        if (a == Action.LEFT_CLICK_BLOCK) {
            if (w.inPlot() && PlotRules.denied(PlotRules.Act.LEFT_CLICK, w, bypass, false)) e.setUseInteractedBlock(Event.Result.DENY);
            return;
        }
        if (a != Action.RIGHT_CLICK_BLOCK) return;
        // 블록 쓰기 (남의 집 = 허용 목록만 · 리스폰 정박기 = 주 월드 어디서나 막음)
        if (e.useInteractedBlock() != Event.Result.DENY) {
            BlockState st = w == PlotRules.Where.GUEST || w == PlotRules.Where.STRANGER ? b.getState(false) : null;
            PlotRules.Act use = PlotRules.blockUse(b.getType().name(), st instanceof InventoryHolder);
            if (PlotRules.denied(use, w, bypass, false)) {
                e.setUseInteractedBlock(Event.Result.DENY);
                if (interactable(b.getType()) && !(p.isSneaking() && e.getItem() != null)) guard.warn(p, use, w, b);
            }
        }
        // 손에 든 것 쓰기 (도구 · 금지 아이템 · 부싯돌 · 끈 매듭 · 엔티티 놓는 아이템)
        ItemStack it = e.getItem();
        if (it == null || e.useItemInHand() == Event.Result.DENY) return;
        PlotRules.Act use = PlotRules.itemUse(it.getType().name(), b.getType().name(), VillageService.changesBlocks(it.getType()),
                service.config().denyUse(), service.config().denyPlace());
        if (use == null) return;
        boolean onBlock = use == PlotRules.Act.TOOL || use == PlotRules.Act.HANGING || use == PlotRules.Act.IGNITE || use == PlotRules.Act.FIRE
                || use == PlotRules.Act.USE_BANNED;
        Block at = onBlock ? b : b.getRelative(e.getBlockFace());
        PlotRules.Where wi = onBlock ? w : guard.where(p, at);
        if (guard.deny(p, use, wi, at, false)) e.setUseItemInHand(Event.Result.DENY);
    }

    @SuppressWarnings("deprecation") // Material#isInteractable — 글을 보낼지만 봄
    private static boolean interactable(Material m) { return m.isInteractable(); }

    // ── 걸개·탈것·표지판·불·끈 ──────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onHangingPlace(HangingPlaceEvent e) {
        Block support = e.getBlock();
        if (off(support.getWorld())) return;
        Player p = e.getPlayer();
        if (p == null) return;
        List<Block> cells = List.of(support, e.getEntity().getLocation().getBlock()); // 받침 칸·걸개 칸 둘 다 내 집 (R4)
        if (guard.deny(p, PlotRules.Act.HANGING, guard.whereAll(p, cells), support, false)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onHangingBreak(HangingBreakEvent e) {
        Entity h = e.getEntity();
        if (off(h.getWorld())) return;
        if (!(e instanceof HangingBreakByEntityEvent be)) return; // 폭발·받침 없어짐은 CrossZone
        Player p = Guard.playerOf(be.getRemover());
        Block at = h.getLocation().getBlock();
        if (p == null) {
            int zone = guard.zone(at);
            if (zone > 0 || (zone < 0 && service.lockedNow())) e.setCancelled(true); // 몹·발사체가 걸개를
            return;
        }
        if (guard.deny(p, PlotRules.Act.HANGING, guard.where(p, at), at, false)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onEntityPlace(EntityPlaceEvent e) {
        Entity en = e.getEntity();
        if (off(en.getWorld())) return;
        Player p = e.getPlayer();
        String type = PlotRules.key(en.getType().name());
        PlotRules.Act act = service.config().denyPlace().contains(type) ? PlotRules.Act.PLACE_BANNED
                : type.equals("armor_stand") ? PlotRules.Act.ARMOR_STAND : PlotRules.Act.VEHICLE;
        Block at = en.getLocation().getBlock();
        if (p == null) {
            // 플레이어 없이 놓임 (발사기 등): 금지 엔티티 · 보호 칸 · 잠긴 들판만 막음 (집 안은 발사기 규칙이 같은 집만 허용)
            int zone = guard.zone(at);
            if (act == PlotRules.Act.PLACE_BANNED || zone == 0 || (zone < 0 && service.lockedNow())) e.setCancelled(true);
            return;
        }
        if (guard.deny(p, act, guard.where(p, at), at, false)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onVehicleDestroy(VehicleDestroyEvent e) {
        Entity v = e.getVehicle();
        if (off(v.getWorld())) return;
        if (vehicleDenied(e.getAttacker(), v)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onVehicleDamage(VehicleDamageEvent e) {
        Entity v = e.getVehicle();
        if (off(v.getWorld())) return;
        if (vehicleDenied(e.getAttacker(), v)) e.setCancelled(true);
    }

    private boolean vehicleDenied(Entity attacker, Entity v) {
        Block at = v.getLocation().getBlock();
        Player p = Guard.playerOf(attacker);
        if (p == null) return attacker != null && guard.zone(at) > 0; // 몹이 남의 집 탈것을 (공격자 없는 용암·선인장은 그대로)
        return guard.deny(p, PlotRules.Act.VEHICLE, guard.where(p, at), at, false);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onSign(SignChangeEvent e) {
        Block b = e.getBlock();
        if (off(b.getWorld())) return;
        if (guard.deny(e.getPlayer(), PlotRules.Act.SIGN, guard.where(e.getPlayer(), b), b, false)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onOpenSign(PlayerOpenSignEvent e) {
        Block b = e.getSign().getBlock();
        if (off(b.getWorld()) || e.getCause() == PlayerOpenSignEvent.Cause.PLACE) return;
        if (guard.deny(e.getPlayer(), PlotRules.Act.SIGN, guard.where(e.getPlayer(), b), b, false)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onIgnite(BlockIgniteEvent e) {
        Block b = e.getBlock();
        if (off(b.getWorld())) return;
        Player p = e.getPlayer();
        if (p == null && e.getIgnitingEntity() != null) p = Guard.playerOf(e.getIgnitingEntity());
        if (p == null) return; // 자연 불은 CrossZone
        // 내 집의 부싯돌은 우클릭 단계에서 모닥불·초·차원문 틀만 남겼다 → 여기서는 IGNITE
        if (guard.deny(p, PlotRules.Act.IGNITE, guard.where(p, b), b, false)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onLeash(PlayerLeashEntityEvent e) {
        Entity en = e.getEntity();
        if (off(en.getWorld())) return;
        Player p = e.getPlayer();
        if (e.getLeashHolder() instanceof LeashHitch hitch) {
            Block at = hitch.getLocation().getBlock();
            if (guard.deny(p, PlotRules.Act.HANGING, guard.where(p, at), at, false)) e.setCancelled(true);
            return;
        }
        PlotRules.Act act = guard.zone(en) == 0 ? PlotRules.Act.ENTITY_GRAB : PlotRules.Act.ANIMAL;
        if (guard.deny(p, act, guard.where(p, en.getLocation()), en.getLocation().getBlock(), false)) e.setCancelled(true);
    }

    // ── 이사 기간 안내 (접속 때 하루 한 번) ──────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(service.plugin(), () -> graceNotice(p), 60L);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) { guard.forget(e.getPlayer().getUniqueId()); }

    private void graceNotice(Player p) {
        if (!p.isOnline() || !service.active() || !service.graceActive()) return;
        long now = System.currentTimeMillis();
        long today = Grace.day(now);
        PlayerData d = service.services().data().get(p);
        Object last = d.ext().get(EXT_GRACE_NOTICE);
        long lastDay = last instanceof Number n ? n.longValue() : -1;
        if (!Grace.noticeDue(lastDay, today)) return;
        d.ext().put(EXT_GRACE_NOTICE, today);
        d.markDirty();
        int left = service.grace().daysLeft(now);
        PlotGeom home = service.homeOf(p.getUniqueId());
        Text.send(p, "<#ffd36b>이사 기간 " + left + "일 남음</#ffd36b><gray> — 집터 밖에 지은 것은 그 안으로 옮기세요. 판자·유리 같은 것만 부술 수 있습니다."
                + (home == null ? " 집은 <white>/미궁 집</white>" : ""));
    }
}
