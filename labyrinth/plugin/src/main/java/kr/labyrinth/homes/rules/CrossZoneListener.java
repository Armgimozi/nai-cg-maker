package kr.labyrinth.homes.rules;

import io.papermc.paper.event.entity.ItemTransportingEntityValidateTargetEvent;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.PlotGeom;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.BlockState;
import org.bukkit.block.data.Directional;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.FallingBlock;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBurnEvent;
import org.bukkit.event.block.BlockDispenseEvent;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.block.BlockFertilizeEvent;
import org.bukkit.event.block.BlockFromToEvent;
import org.bukkit.event.block.BlockGrowEvent;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockPistonExtendEvent;
import org.bukkit.event.block.BlockPistonRetractEvent;
import org.bukkit.event.block.BlockSpreadEvent;
import org.bukkit.event.block.SpongeAbsorbEvent;
import org.bukkit.event.block.TNTPrimeEvent;
import org.bukkit.event.block.EntityBlockFormEvent;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.hanging.HangingBreakEvent;
import org.bukkit.event.inventory.InventoryMoveItemEvent;
import org.bukkit.event.inventory.InventoryPickupItemEvent;
import org.bukkit.event.world.PortalCreateEvent;
import org.bukkit.event.world.StructureGrowEvent;

/**
 * 경계 넘는 것 (0.3.7, plan §9 "경계 넘는 것" · review R4·R17) — 집터가 하나라도 있으면 늘. 소유: 묶음 B.
 * zone 이 다르면 막는다 (집터 key · 0 보호 상자 · −1 그 밖). 잦은 이벤트 (흐름·깔때기·퍼짐·자람) 는 주 월드가 아니거나
 * 관련 칸의 청크에 집터가 없으면 바로 끝낸다 (보호 상자 쪽은 마을 핸들러가 그대로 봄).
 * 불 타기·번짐·폭발 블록 피해·TNT 점화는 주 월드 전부에서 막는다.
 */
public final class CrossZoneListener implements Listener {

    private static final long GROW_NOTE_MS = 600_000L;

    private final HomesService service;
    private final Guard guard;
    private final Map<String, Long> growNote = new HashMap<>();

    public CrossZoneListener(HomesService service) {
        this.service = service;
        this.guard = service.guard();
    }

    HomesService service() { return service; }

    private boolean off(World w) { return !service.active() || !service.isMain(w); }

    private int zone(Block b) { return service.zone(b.getWorld(), b.getX(), b.getY(), b.getZ()); }

    private int zone(Location l) { return service.zone(l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ()); }

    private boolean nearPlot(Block b) { return service.index().near(b.getX(), b.getZ()); }

    private boolean nearPlot(Location l) { return service.index().near(l.getBlockX(), l.getBlockZ()); }

    // ── 흐름·피스톤 ──────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onFlow(BlockFromToEvent e) {
        Block from = e.getBlock(), to = e.getToBlock();
        if (!nearPlot(from) && !nearPlot(to)) return;
        if (off(from.getWorld())) return;
        if (!CrossZone.flow(zone(from), zone(to))) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onPistonExtend(BlockPistonExtendEvent e) {
        if (off(e.getBlock().getWorld())) return;
        if (!piston(e.getBlock(), e.getBlocks(), e.getDirection(), true)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onPistonRetract(BlockPistonRetractEvent e) {
        if (off(e.getBlock().getWorld())) return;
        if (!piston(e.getBlock(), e.getBlocks(), e.getDirection(), false)) e.setCancelled(true);
    }

    private boolean piston(Block piston, List<Block> moved, BlockFace dir, boolean extend) {
        boolean locked = service.lockedNow();
        boolean near = nearPlot(piston);
        for (Block b : moved) near |= nearPlot(b) || nearPlot(b.getRelative(dir));
        if (!near && !locked) return true;
        int[] cells = new int[moved.size() * 2 + 1];
        int i = 0;
        for (Block b : moved) {
            cells[i++] = zone(b);
            cells[i++] = zone(b.getRelative(dir));
        }
        cells[i] = extend ? zone(piston.getRelative(dir)) : zone(piston); // 머리 칸
        return CrossZone.piston(zone(piston), cells, locked);
    }

    // ── 깔때기·공급기·구리 골렘 ──────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onMove(InventoryMoveItemEvent e) {
        Location a = e.getSource().getLocation(), b = e.getDestination().getLocation();
        if (a == null || b == null || a.getWorld() == null) return;
        if (!nearPlot(a) && !nearPlot(b)) return;
        if (off(a.getWorld())) return;
        if (!CrossZone.transfer(zone(a), zone(b))) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onPickup(InventoryPickupItemEvent e) {
        Location h = e.getInventory().getLocation(), it = e.getItem().getLocation();
        if (h == null || h.getWorld() == null) return;
        if (!nearPlot(h) && !nearPlot(it)) return;
        if (off(h.getWorld())) return;
        if (!CrossZone.pickup(zone(it), zone(h))) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW)
    public void onGolem(ItemTransportingEntityValidateTargetEvent e) {
        if (!e.isAllowed()) return;
        Entity g = e.getEntity();
        Block t = e.getBlock();
        if (!nearPlot(g.getLocation()) && !nearPlot(t)) return;
        if (off(g.getWorld())) return;
        if (!CrossZone.golem(zone(g.getLocation()), zone(t))) e.setAllowed(false);
    }

    // ── 자람·퍼짐·뼛가루 ─────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onStructureGrow(StructureGrowEvent e) {
        Location l = e.getLocation();
        if (off(e.getWorld())) return;
        int origin = zone(l);
        boolean near = nearPlot(l);
        for (BlockState s : e.getBlocks()) near |= service.index().near(s.getX(), s.getZ());
        if (!near) return;
        int[] zones = new int[e.getBlocks().size()];
        int i = 0;
        for (BlockState s : e.getBlocks()) zones[i++] = service.zone(e.getWorld(), s.getX(), s.getY(), s.getZ());
        if (CrossZone.allSame(origin, zones)) return;
        e.setCancelled(true);
        growNotice(e.getPlayer(), l, origin);
    }

    /** R17: 가장자리 묘목이 못 자람 → "집터 밖으로 자랄 수 없습니다" 한 줄 (뼛가루 준 사람, 아니면 가까이 있는 주인에게 10분에 한 번). */
    private void growNotice(Player p, Location l, int origin) {
        String msg = "집터 밖으로 자랄 수 없습니다. 가장자리에서 조금 떨어진 곳에 심으세요.";
        if (p != null) {
            guard.warnText(p, msg);
            return;
        }
        if (origin <= 0) return;
        PlotGeom plot = service.index().byKey(origin);
        UUID owner = plot == null ? null : service.ownerOf(plot);
        Player op = owner == null ? null : Bukkit.getPlayer(owner);
        if (op == null || !op.getWorld().equals(l.getWorld()) || op.getLocation().distanceSquared(l) > 48 * 48) return;
        long now = System.currentTimeMillis();
        Long last = growNote.get(plot.id());
        if (last != null && now - last < GROW_NOTE_MS) return;
        growNote.put(plot.id(), now);
        Text.send(op, "<gray>" + Text.escape(msg));
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onFertilize(BlockFertilizeEvent e) {
        Block b = e.getBlock();
        if (off(b.getWorld())) return;
        boolean near = nearPlot(b);
        for (BlockState s : e.getBlocks()) near |= service.index().near(s.getX(), s.getZ());
        if (!near) return;
        int origin = zone(b);
        int[] zones = new int[e.getBlocks().size()];
        int i = 0;
        for (BlockState s : e.getBlocks()) zones[i++] = service.zone(b.getWorld(), s.getX(), s.getY(), s.getZ());
        if (!CrossZone.allSame(origin, zones)) {
            e.getBlocks().removeIf(s -> service.zone(b.getWorld(), s.getX(), s.getY(), s.getZ()) != origin); // 같은 집 칸만 자람
            if (e.getBlocks().isEmpty()) e.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onSpread(BlockSpreadEvent e) {
        Block b = e.getBlock(), src = e.getSource();
        boolean fire = e.getNewState().getType() == Material.FIRE || e.getNewState().getType() == Material.SOUL_FIRE;
        if (fire) {
            if (!off(b.getWorld())) e.setCancelled(true); // 불 번짐은 주 월드 전부
            return;
        }
        if (!nearPlot(b) && !nearPlot(src)) return;
        if (off(b.getWorld())) return;
        if (!CrossZone.spread(zone(src), zone(b), false)) e.setCancelled(true);
    }

    private static final Set<Material> UPWARD = Set.of(Material.SUGAR_CANE, Material.CACTUS, Material.BAMBOO, Material.KELP, Material.KELP_PLANT,
            Material.TWISTING_VINES, Material.TWISTING_VINES_PLANT, Material.CHORUS_FLOWER, Material.CHORUS_PLANT);
    private static final Set<Material> DOWNWARD = Set.of(Material.WEEPING_VINES, Material.WEEPING_VINES_PLANT, Material.CAVE_VINES,
            Material.CAVE_VINES_PLANT, Material.HANGING_ROOTS, Material.POINTED_DRIPSTONE);

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onGrow(BlockGrowEvent e) {
        Block b = e.getBlock();
        Material to = e.getNewState().getType();
        if (to == b.getType()) return; // 나이만 바뀜
        if (!nearPlot(b)) return;
        if (off(b.getWorld())) return;
        Block origin = null;
        if (UPWARD.contains(to)) origin = b.getRelative(BlockFace.DOWN);
        else if (DOWNWARD.contains(to)) origin = b.getRelative(BlockFace.UP);
        else if (to == Material.PUMPKIN || to == Material.MELON) {
            for (BlockFace f : new BlockFace[] {BlockFace.NORTH, BlockFace.SOUTH, BlockFace.EAST, BlockFace.WEST}) {
                Material m = b.getRelative(f).getType();
                if (m == Material.PUMPKIN_STEM || m == Material.MELON_STEM || m == Material.ATTACHED_PUMPKIN_STEM || m == Material.ATTACHED_MELON_STEM) {
                    if (zone(b.getRelative(f)) != zone(b)) {
                        e.setCancelled(true);
                        return;
                    }
                }
            }
            return;
        }
        if (origin != null && zone(origin) != zone(b)) e.setCancelled(true);
    }

    // ── 불·폭발 ──────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onBurn(BlockBurnEvent e) {
        if (!off(e.getBlock().getWorld())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onNaturalIgnite(BlockIgniteEvent e) {
        if (e.getPlayer() != null || off(e.getBlock().getWorld())) return;
        if (e.getIgnitingEntity() != null && Guard.playerOf(e.getIgnitingEntity()) != null) return; // 플레이어 불화살 = TerrainLock
        switch (e.getCause()) {
            case SPREAD, LAVA, LIGHTNING, EXPLOSION, ENDER_CRYSTAL, FIREBALL, ARROW -> e.setCancelled(true);
            default -> { }
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onEntityExplode(EntityExplodeEvent e) {
        if (!off(e.getLocation().getWorld())) e.blockList().clear();
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onBlockExplode(BlockExplodeEvent e) {
        if (!off(e.getBlock().getWorld())) e.blockList().clear();
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onHangingExplode(HangingBreakEvent e) {
        if (e.getCause() != HangingBreakEvent.RemoveCause.EXPLOSION || off(e.getEntity().getWorld())) return;
        e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onPrime(TNTPrimeEvent e) {
        if (off(e.getBlock().getWorld())) return;
        Entity by = e.getPrimingEntity();
        Player p = by == null ? null : Guard.playerOf(by);
        if (p != null && Guard.bypass(p)) return;
        e.setCancelled(true);
        if (p != null) guard.warnText(p, "TNT 와 리스폰 정박기는 쓸 수 없습니다.");
    }

    // ── 엔티티가 블록을 바꿈 ─────────────────────────────────────────────

    private static final Set<EntityType> GRIEFERS = Set.of(EntityType.ENDERMAN, EntityType.RAVAGER, EntityType.WITHER, EntityType.WITHER_SKULL,
            EntityType.ENDER_DRAGON, EntityType.ZOMBIE, EntityType.ZOMBIE_VILLAGER, EntityType.HUSK, EntityType.DROWNED, EntityType.VINDICATOR,
            EntityType.SILVERFISH, EntityType.WIND_CHARGE, EntityType.BREEZE_WIND_CHARGE);

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onEntityChange(EntityChangeBlockEvent e) {
        Block b = e.getBlock();
        Entity en = e.getEntity();
        if (off(b.getWorld())) return;
        if (en instanceof FallingBlock fb) {
            Location src = fb.getOrigin();
            if (src == null || (!nearPlot(src) && !nearPlot(b))) return;
            if (!CrossZone.falling(zone(src), zone(b))) e.setCancelled(true);
            return;
        }
        Player p = Guard.playerOf(en);
        if (p != null) {
            // 플레이어 (발사체 포함) 가 블록을 바꿈 — 부수기와 같은 규칙
            if (guard.deny(p, PlotRules.Act.BREAK, guard.where(p, b), b, en instanceof Player && guard.graceBreakable(b))) e.setCancelled(true);
            return;
        }
        boolean griefer = GRIEFERS.contains(en.getType()) || en instanceof Projectile;
        if (!CrossZone.mobChange(zone(en.getLocation()), zone(b), griefer, service.lockedNow())) e.setCancelled(true);
    }

    /** 몹이 밭·거북알을 밟음: 집 안·보호 칸·잠긴 들판에서 막음 (플레이어 밟기는 TerrainLock). */
    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onMobStep(org.bukkit.event.entity.EntityInteractEvent e) {
        Block b = e.getBlock();
        if (b.getType() != Material.FARMLAND && b.getType() != Material.TURTLE_EGG) return;
        if (off(b.getWorld())) return;
        int z = zone(b);
        if (z >= 0 || service.lockedNow()) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onEntityForm(EntityBlockFormEvent e) {
        Block b = e.getBlock();
        if (off(b.getWorld())) return;
        if (!CrossZone.entityForm(zone(b), service.lockedNow())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onSponge(SpongeAbsorbEvent e) {
        Block b = e.getBlock();
        if (off(b.getWorld())) return;
        boolean near = nearPlot(b) || service.index().near(b.getX() - 7, b.getZ() - 7) || service.index().near(b.getX() + 7, b.getZ() + 7)
                || service.index().near(b.getX() - 7, b.getZ() + 7) || service.index().near(b.getX() + 7, b.getZ() - 7);
        if (!near) return;
        int sz = zone(b);
        e.getBlocks().removeIf(s -> !CrossZone.sponge(sz, service.zone(b.getWorld(), s.getX(), s.getY(), s.getZ())));
        if (e.getBlocks().isEmpty()) e.setCancelled(true);
    }

    // ── 발사기 (R4) ──────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onDispense(BlockDispenseEvent e) {
        Block b = e.getBlock();
        if (b.getType() != Material.DISPENSER || off(b.getWorld())) return;
        BlockFace face = b.getBlockData() instanceof Directional d ? d.getFacing() : BlockFace.SELF;
        if (!CrossZone.dispense(zone(b), zone(b.getRelative(face)), service.lockedNow())) e.setCancelled(true);
    }

    // ── 차원문 (잠금 켜짐) ───────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onPortal(PortalCreateEvent e) {
        World w = e.getWorld();
        if (off(w) || !service.lockedNow()) return;
        List<BlockState> blocks = e.getBlocks();
        int[] zones = new int[blocks.size()];
        int i = 0;
        for (BlockState s : blocks) zones[i++] = service.zone(w, s.getX(), s.getY(), s.getZ());
        Player p = e.getEntity() instanceof Player pl ? pl : null;
        if (e.getReason() == PortalCreateEvent.CreateReason.FIRE) {
            if (p != null && Guard.bypass(p)) return;
            PlotGeom home = p == null ? null : service.homeOf(p.getUniqueId());
            int own = -1;
            if (p != null && zones.length > 0 && zones[0] > 0) {
                PlotGeom at = service.index().byKey(zones[0]);
                if (at != null && service.roleOf(p.getUniqueId(), at).builds()) own = at.key();
            }
            if (!CrossZone.portalByPlayer(own, zones)) {
                e.setCancelled(true);
                if (p != null) guard.warnText(p, "차원문은 내 집 안에서만 열 수 있습니다." + (home == null ? " /미궁 집" : ""));
            }
            return;
        }
        if (e.getReason() == PortalCreateEvent.CreateReason.NETHER_PAIR && !CrossZone.portalPair(zones)) {
            e.setCancelled(true);
            if (p != null) guard.warnText(p, "여기에는 돌아오는 차원문을 만들 수 없습니다. /미궁 마을 로 돌아가세요.");
        }
    }
}
