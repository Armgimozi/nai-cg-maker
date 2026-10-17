package kr.labyrinth.homes.rules;

import io.papermc.paper.event.player.PlayerItemFrameChangeEvent;
import io.papermc.paper.event.player.PlayerNameEntityEvent;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.PlotGeom;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.DoubleChest;
import org.bukkit.Material;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Animals;
import org.bukkit.entity.AreaEffectCloud;
import org.bukkit.entity.ArmorStand;
import org.bukkit.entity.Enemy;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Golem;
import org.bukkit.entity.Hanging;
import org.bukkit.entity.ItemFrame;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Vehicle;
import org.bukkit.entity.WaterMob;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.AreaEffectCloudApplyEvent;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.EntityTameEvent;
import org.bukkit.event.entity.EntityTargetEvent;
import org.bukkit.event.entity.EntityTargetLivingEntityEvent;
import org.bukkit.event.entity.PotionSplashEvent;
import org.bukkit.event.entity.EntityBreedEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityPlaceEvent;
import org.bukkit.event.entity.SheepDyeWoolEvent;
import org.bukkit.event.hanging.HangingPlaceEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.player.PlayerArmorStandManipulateEvent;
import org.bukkit.event.player.PlayerFishEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerShearEntityEvent;
import org.bukkit.event.player.PlayerTakeLecternBookEvent;
import org.bukkit.event.player.PlayerUnleashEntityEvent;
import org.bukkit.event.vehicle.VehicleEnterEvent;
import org.bukkit.inventory.BlockInventoryHolder;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.util.BoundingBox;

/**
 * 집터 안 엔티티 권한과 한도 (0.3.7, plan §9 · review R4·R15). 소유: 묶음 B.
 * <ul>
 *   <li>남의 집 엔티티: 우클릭 (먹이·타기·이름표·끈·말 상자) · 때리기 · 거치대 ({@code PlayerArmorStandManipulateEvent} 는 따로) · 액자 ·
 *       털 깎기 · 염색 · 낚싯대 끌기 · 타기 · 말/상자 보트/상자 수레 열기 — 주인·초대만. 적대 몹은 누구나 때림.</li>
 *   <li>상자 열기 (InventoryOpenEvent) 를 한 번 더 봄 — 우클릭 막기가 놓친 길 (보조).</li>
 *   <li>틱 부품 16 (깔때기 8) · 동물 24 · 거치대+액자+그림 64 (번식·알·놓기 때 셈).</li>
 *   <li>집 동물·탈것 표시 (0.3.7 fix, exploit M1): 집터 안에서 생기거나 놓이거나 길들거나 사는 동물·탈것에 {@code labyrinth:home_plot} 을 적고,
 *       집 밖으로 나가도 그 집 주인·초대만 손댄다. 남이 먹이로 꾀어 내는 것 (TEMPT) 은 집 안에서 막는다.</li>
 * </ul>
 */
public final class PlotRulesListener implements Listener {

    private final HomesService service;
    private final Guard guard;

    public PlotRulesListener(HomesService service) {
        this.service = service;
        this.guard = service.guard();
    }

    HomesService service() { return service; }

    private boolean off(World w) { return !service.rulesOn() || !service.isMain(w); }

    /** 그 엔티티가 남의 집 안에 있고 그 사람이 손대면 안 되는가 (막으면 글). 집 밖이면 표시된 집 권한으로 (동물·탈것). */
    private boolean denyEntity(Player p, Entity en, PlotRules.Act act) {
        Location l = en.getLocation();
        int zone = guard.zone(en);
        if (zone <= 0 && (act == PlotRules.Act.ANIMAL || act == PlotRules.Act.VEHICLE)) {
            PlotGeom home = guard.homePlot(en);
            if (home != null) return guard.denyTagged(p, act, home); // 집 밖 (골목·들판) 으로 나간 그 집 동물·보트
        }
        if (zone <= 0 && act == PlotRules.Act.ANIMAL) return false; // 집 밖 동물은 그대로
        if (zone > 0 && (act == PlotRules.Act.ANIMAL || act == PlotRules.Act.VEHICLE)) guard.tag(en, service.index().byKey(zone));
        PlotRules.Where w = guard.where(p, l);
        boolean grace = (act == PlotRules.Act.HANGING || act == PlotRules.Act.ARMOR_STAND || act == PlotRules.Act.VEHICLE) && guard.graceEntity(w);
        return guard.deny(p, act, w, l.getBlock(), grace);
    }

    /** 집 밖이어도 그 집 것으로 따질 엔티티가 있나 (표시). */
    private boolean tagged(Entity en) { return guard.zone(en) <= 0 && guard.homePlot(en) != null; }

    private static PlotRules.Act entityAct(Entity en) {
        if (en instanceof ArmorStand) return PlotRules.Act.ARMOR_STAND;
        if (en instanceof Hanging) return PlotRules.Act.HANGING;
        if (en instanceof Vehicle && !(en instanceof LivingEntity)) return PlotRules.Act.VEHICLE;
        return PlotRules.Act.ANIMAL;
    }

    // ── 엔티티 손대기 ────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onInteractEntity(PlayerInteractEntityEvent e) { // PlayerInteractAtEntityEvent 도 (같은 목록)
        Entity en = e.getRightClicked();
        if (off(en.getWorld()) || en instanceof Player) return;
        PlotRules.Act act = entityAct(en);
        if (act == PlotRules.Act.VEHICLE) act = PlotRules.Act.ANIMAL; // 보트 타기 = 타기
        if (act == PlotRules.Act.HANGING || act == PlotRules.Act.ARMOR_STAND) act = PlotRules.Act.DECO_USE; // 액자 돌리기·거치대 (옛 것은 늘 됨)
        if (act == PlotRules.Act.ANIMAL && guard.zone(en) <= 0 && !tagged(en)) return; // 집 밖 · NPC 는 그대로
        if (denyEntity(e.getPlayer(), en, act)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onArmorStand(PlayerArmorStandManipulateEvent e) {
        ArmorStand as = e.getRightClicked();
        if (off(as.getWorld())) return;
        if (denyEntity(e.getPlayer(), as, PlotRules.Act.DECO_USE)) e.setCancelled(true); // 잠긴 들판의 옛 거치대 장비는 꺼낼 수 있음 (live 5)
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onItemFrame(PlayerItemFrameChangeEvent e) {
        Entity f = e.getItemFrame();
        if (off(f.getWorld())) return;
        if (denyEntity(e.getPlayer(), f, PlotRules.Act.DECO_USE)) e.setCancelled(true); // 옛 액자 꺼내기·넣기 (exploit M2)
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        Entity v = e.getEntity();
        if (v instanceof Player || off(v.getWorld())) return;
        boolean deco = v instanceof ArmorStand || v instanceof Hanging;
        if (e instanceof EntityDamageByEntityEvent by) {
            Player p = Guard.playerOf(by.getDamager());
            if (p != null) {
                if (v instanceof Enemy) return; // 적대 몹은 누구나
                PlotRules.Act act = entityAct(v);
                if (v instanceof ItemFrame f && f.getItem() != null && !f.getItem().getType().isAir()) act = PlotRules.Act.DECO_USE; // 든 것 꺼내기 (액자는 그대로)
                if (act == PlotRules.Act.ANIMAL && guard.zone(v) <= 0 && !tagged(v)) return;
                if (denyEntity(p, v, act)) e.setCancelled(true); // 이사 기간: 잠긴 들판의 옛 거치대·액자·수레는 부숨 (denyEntity 가 grace 를 넘김)
                return;
            }
        }
        if (!deco) return;
        // 플레이어가 아닌 것 (폭발·몹·발사기 화살): 집 안이거나 잠긴 들판의 거치대·액자는 지킴
        int zone = guard.zone(v);
        if (zone > 0 || (zone < 0 && service.lockedNow())) {
            EntityDamageEvent.DamageCause c = e.getCause();
            if (c == EntityDamageEvent.DamageCause.BLOCK_EXPLOSION || c == EntityDamageEvent.DamageCause.ENTITY_EXPLOSION
                    || c == EntityDamageEvent.DamageCause.PROJECTILE || c == EntityDamageEvent.DamageCause.ENTITY_ATTACK
                    || c == EntityDamageEvent.DamageCause.FIRE || c == EntityDamageEvent.DamageCause.FIRE_TICK
                    || c == EntityDamageEvent.DamageCause.LAVA) e.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onShear(PlayerShearEntityEvent e) {
        if (off(e.getEntity().getWorld())) return;
        if (denyEntity(e.getPlayer(), e.getEntity(), PlotRules.Act.ANIMAL)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onDye(SheepDyeWoolEvent e) {
        if (e.getPlayer() == null || off(e.getEntity().getWorld())) return;
        if (denyEntity(e.getPlayer(), e.getEntity(), PlotRules.Act.ANIMAL)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onName(PlayerNameEntityEvent e) {
        if (off(e.getEntity().getWorld())) return;
        if (denyEntity(e.getPlayer(), e.getEntity(), PlotRules.Act.ANIMAL)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onFish(PlayerFishEvent e) {
        if (e.getState() != PlayerFishEvent.State.CAUGHT_ENTITY || e.getCaught() == null || e.getCaught() instanceof Player) return;
        Entity en = e.getCaught();
        if (off(en.getWorld())) return;
        if (denyEntity(e.getPlayer(), en, entityAct(en) == PlotRules.Act.VEHICLE ? PlotRules.Act.ANIMAL : entityAct(en))) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onUnleash(PlayerUnleashEntityEvent e) {
        if (off(e.getEntity().getWorld())) return;
        if (denyEntity(e.getPlayer(), e.getEntity(), PlotRules.Act.ANIMAL)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onEnter(VehicleEnterEvent e) {
        if (!(e.getEntered() instanceof Player p) || off(e.getVehicle().getWorld())) return;
        if (denyEntity(p, e.getVehicle(), PlotRules.Act.ANIMAL)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onOpen(InventoryOpenEvent e) {
        if (!(e.getPlayer() instanceof Player p)) return;
        if (e.getInventory().getType() == org.bukkit.event.inventory.InventoryType.ENDER_CHEST) return; // 엔더 상자는 누구나
        InventoryHolder h = e.getInventory().getHolder(false);
        if (h instanceof org.bukkit.entity.HumanEntity) return; // 플레이어 자신의 것 (엔더 상자 등)
        if (h instanceof Entity en) { // 말·당나귀·라마·상자 보트·상자 수레 (집 밖으로 나간 그 집 것도)
            if (off(en.getWorld())) return;
            if (guard.zone(en) <= 0 && !tagged(en)) return;
            if (denyEntity(p, en, PlotRules.Act.ANIMAL)) e.setCancelled(true);
            return;
        }
        List<Location> cells = new ArrayList<>(2);
        if (h instanceof DoubleChest dc) { // 두 칸 다 (경계에 걸친 큰 상자 — exploit L1)
            if (dc.getLeftSide(false) instanceof BlockInventoryHolder lh) cells.add(lh.getBlock().getLocation());
            if (dc.getRightSide(false) instanceof BlockInventoryHolder rh) cells.add(rh.getBlock().getLocation());
            if (cells.isEmpty() && dc.getLocation() != null) cells.add(dc.getLocation());
        } else if (h instanceof BlockInventoryHolder bh) cells.add(bh.getBlock().getLocation());
        else return; // 엔더 상자·메뉴
        for (Location l : cells) {
            if (l == null || l.getWorld() == null || off(l.getWorld())) return;
            int zone = service.zone(l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ());
            if (zone <= 0) continue; // 집 밖 상자류는 우클릭 쪽 규칙 그대로
            if (guard.deny(p, PlotRules.Act.CONTAINER, guard.where(p, l), l.getBlock(), false)) {
                e.setCancelled(true);
                return;
            }
        }
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onLectern(PlayerTakeLecternBookEvent e) {
        Block b = e.getLectern().getBlock();
        if (off(b.getWorld()) || guard.zone(b) <= 0) return;
        if (guard.deny(e.getPlayer(), PlotRules.Act.CONTAINER, guard.where(e.getPlayer(), b), b, false)) e.setCancelled(true);
    }

    // ── 꾀어 내기 · 물약 구름 (exploit M1 · L7) ─────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onTempt(EntityTargetLivingEntityEvent e) {
        if (e.getReason() != EntityTargetEvent.TargetReason.TEMPT || !(e.getTarget() instanceof Player p)) return;
        Entity en = e.getEntity();
        if (off(en.getWorld())) return;
        PlotGeom plot = guard.plotOf(en);
        if (plot == null || Guard.bypass(p)) return;
        if (!service.roleOf(p.getUniqueId(), plot).builds()) e.setCancelled(true); // 남이 먹이로 집 동물을 데리고 나가지 못함 (글 없음 — 자주 옴)
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onCloud(AreaEffectCloudApplyEvent e) {
        AreaEffectCloud c = e.getEntity();
        if (off(c.getWorld()) || !(c.getSource() instanceof Player p) || Guard.bypass(p)) return;
        e.getAffectedEntities().removeIf(v -> protectedFrom(p, v));
    }

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onSplash(PotionSplashEvent e) {
        if (off(e.getEntity().getWorld()) || !(e.getEntity().getShooter() instanceof Player p) || Guard.bypass(p)) return;
        for (LivingEntity v : e.getAffectedEntities()) if (protectedFrom(p, v)) e.setIntensity(v, 0);
    }

    /** 그 사람이 그 엔티티 (집 동물·거치대) 에 물약을 써서는 안 되나. */
    private boolean protectedFrom(Player p, Entity v) {
        if (v instanceof Player || v instanceof Enemy) return false;
        PlotGeom plot = guard.plotOf(v);
        return plot != null && !service.roleOf(p.getUniqueId(), plot).builds();
    }

    // ── 집 동물·탈것 표시 ────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSpawnTag(CreatureSpawnEvent e) {
        LivingEntity en = e.getEntity();
        if (!creature(en) || off(en.getWorld())) return;
        tagHere(en);
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlaceTag(EntityPlaceEvent e) {
        if (e.getEntity() instanceof Vehicle && !off(e.getEntity().getWorld())) tagHere(e.getEntity());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onTame(EntityTameEvent e) {
        if (!off(e.getEntity().getWorld())) tagHere(e.getEntity());
    }

    private void tagHere(Entity en) {
        Location l = en.getLocation();
        PlotGeom plot = service.plotAt(l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ());
        if (plot != null) guard.tag(en, plot);
    }

    /** 10초마다: 집터 안 동물·탈것에 그 집 표시 (먹이 없이 걸어 나가거나 밀려 나간 것도 그 집 것으로). */
    public void sweepTags() {
        World w = service.mainWorld();
        if (w == null || off(w)) return;
        for (PlotGeom p : service.index().all()) {
            if (!kr.labyrinth.homes.HomesService.loadedPlot(w, p)) continue;
            BoundingBox box = new BoundingBox(p.x0(), p.yMin(), p.z0(), p.x1() + 1, p.yMax() + 1, p.z1() + 1);
            for (Entity e : w.getNearbyEntities(box)) {
                if (e instanceof Player || e instanceof Enemy) continue;
                if (creature(e) || (e instanceof Vehicle && !(e instanceof LivingEntity))) guard.tag(e, p);
            }
        }
    }

    // ── 두 칸 상자가 경계를 넘지 않게 (exploit L1) ───────────────────────

    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onChestPair(BlockPlaceEvent e) {
        Block b = e.getBlockPlaced();
        if (b.getType() != Material.CHEST && b.getType() != Material.TRAPPED_CHEST) return;
        if (off(b.getWorld()) || Guard.bypass(e.getPlayer())) return;
        BlockData d = b.getBlockData();
        if (!(d instanceof org.bukkit.block.data.type.Chest c) || c.getType() == org.bukkit.block.data.type.Chest.Type.SINGLE) return;
        BlockFace side = pairSide(c.getFacing(), c.getType() == org.bukkit.block.data.type.Chest.Type.LEFT);
        Block other = b.getRelative(side);
        if (guard.zone(other) == guard.zone(b)) return;
        e.setCancelled(true);
        guard.warnText(e.getPlayer(), "집터 경계를 넘어 큰 상자를 만들 수 없습니다.");
    }

    /** 큰 상자 짝이 있는 쪽 (바닐라 ChestBlock.getConnectedDirection: LEFT = 시계 방향). */
    static BlockFace pairSide(BlockFace facing, boolean left) {
        BlockFace cw = switch (facing) {
            case NORTH -> BlockFace.EAST;
            case EAST -> BlockFace.SOUTH;
            case SOUTH -> BlockFace.WEST;
            default -> BlockFace.NORTH;
        };
        return left ? cw : cw.getOppositeFace();
    }

    // ── 한도 (R15 · 틱 부품) ─────────────────────────────────────────────

    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onPlacePart(BlockPlaceEvent e) {
        Block b = e.getBlockPlaced();
        Limits.Part part = Limits.part(b.getType().name());
        if (part == null || off(b.getWorld())) return;
        PlotGeom plot = service.plotAt(b.getWorld(), b.getX(), b.getY(), b.getZ());
        if (plot == null || Guard.bypass(e.getPlayer())) return;
        Map<Limits.Part, Integer> counts = countParts(b.getWorld(), plot, b);
        String msg = Limits.tickPart(counts, part, service.config().tickParts().total(), service.config().tickParts().hoppers());
        if (msg != null) {
            e.setCancelled(true);
            guard.warnText(e.getPlayer(), msg);
        }
    }

    /** 그 집터 높이 창 안의 틱 부품 수 (except 칸은 빼고 — 지금 놓는 블록). */
    public static Map<Limits.Part, Integer> countParts(World w, PlotGeom p, Block except) {
        Map<Limits.Part, Integer> m = Limits.emptyCounts();
        for (int y = p.yMin(); y <= p.yMax(); y++) {
            for (int x = p.x0(); x <= p.x1(); x++) {
                for (int z = p.z0(); z <= p.z1(); z++) {
                    if (except != null && except.getX() == x && except.getY() == y && except.getZ() == z) continue;
                    Limits.Part part = Limits.part(w.getBlockAt(x, y, z).getType().name());
                    if (part != null) m.merge(part, 1, Integer::sum);
                }
            }
        }
        return m;
    }

    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onHangingCap(HangingPlaceEvent e) {
        if (e.getPlayer() == null || off(e.getBlock().getWorld()) || Guard.bypass(e.getPlayer())) return;
        if (decoCapHit(e.getEntity().getLocation(), e.getPlayer())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onStandCap(EntityPlaceEvent e) {
        if (!(e.getEntity() instanceof ArmorStand) || off(e.getEntity().getWorld()) || Guard.bypass(e.getPlayer())) return;
        if (decoCapHit(e.getEntity().getLocation(), e.getPlayer())) e.setCancelled(true);
    }

    private boolean decoCapHit(Location l, Player p) {
        PlotGeom plot = service.plotAt(l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ());
        if (plot == null) return false;
        int cap = service.config().entityCaps().decorations();
        int n = count(l.getWorld(), plot, Limits.EntityKind.DECORATION, null);
        if (Limits.underCap(n, cap)) return false;
        guard.warnText(p, Limits.capMessage(Limits.EntityKind.DECORATION, cap));
        return true;
    }

    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onBreed(EntityBreedEvent e) {
        LivingEntity child = e.getEntity();
        if (off(child.getWorld())) return;
        Location l = child.getLocation();
        PlotGeom plot = service.plotAt(l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ());
        if (plot == null) return;
        int cap = service.config().entityCaps().animals();
        if (Limits.underCap(count(l.getWorld(), plot, Limits.EntityKind.ANIMAL, child), cap)) return;
        e.setCancelled(true);
        if (e.getBreeder() instanceof Player p) guard.warnText(p, Limits.capMessage(Limits.EntityKind.ANIMAL, cap));
    }

    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onSpawn(CreatureSpawnEvent e) {
        switch (e.getSpawnReason()) {
            case EGG, SPAWNER_EGG, DISPENSE_EGG, BUCKET, BUILD_IRONGOLEM, BUILD_SNOWMAN, BUILD_COPPERGOLEM, DUPLICATION, OCELOT_BABY -> { }
            default -> {
                return; // 번식은 onBreed, 자연 스폰은 마을 쪽 (wild.spawns)
            }
        }
        LivingEntity en = e.getEntity();
        if (!creature(en) || off(en.getWorld())) return;
        Location l = e.getLocation();
        PlotGeom plot = service.plotAt(l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ());
        if (plot == null) return;
        if (!Limits.underCap(count(l.getWorld(), plot, Limits.EntityKind.ANIMAL, en), service.config().entityCaps().animals())) e.setCancelled(true);
    }

    static boolean creature(Entity e) { return e instanceof Animals || e instanceof WaterMob || e instanceof Golem; }

    /** 그 집터 상자 안 (높이 창) 의 그 종류 엔티티 수. */
    static int count(World w, PlotGeom p, Limits.EntityKind kind, Entity except) {
        BoundingBox box = new BoundingBox(p.x0(), p.yMin(), p.z0(), p.x1() + 1, p.yMax() + 1, p.z1() + 1);
        int n = 0;
        for (Entity e : w.getNearbyEntities(box)) {
            if (e == except || e instanceof Player) continue;
            if (Limits.entityKind(e.getType().name(), creature(e)) == kind) n++;
        }
        return n;
    }
}
