package kr.labyrinth.homes.rules;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import kr.labyrinth.core.Log;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.PlotGeom;
import org.bukkit.Bukkit;
import org.bukkit.Chunk;
import org.bukkit.Material;
import org.bukkit.Nameable;
import org.bukkit.Tag;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.Campfire;
import org.bukkit.block.Chest;
import org.bukkit.block.Jukebox;
import org.bukkit.block.ShulkerBox;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.ArmorStand;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Item;
import org.bukkit.entity.ItemFrame;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.BlockStateMeta;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.util.BoundingBox;

/**
 * 비우기·회수 — 집터를 처음 틀로 되돌리고 안의 것을 맡긴 짐으로 (0.3.7, review R3). 소유: 묶음 B.
 * <ol>
 *   <li>집터 청크를 비동기로 불러 둠 (그동안 그 집은 아무도 못 씀 — {@link HomesService#busy})</li>
 *   <li>한 틱 안에: 짐 모으기 (읽기만) → {@link ParcelStore#begin} (pending, 짐 바이트) → 블록·엔티티 지우기 (틀로) → 주인 풀기·저장</li>
 *   <li>{@code World#save(true)} → {@link ParcelStore#finish} (ready)</li>
 * </ol>
 * 서버가 ②~③ 사이에 꺼지면 다음 시작 때 {@link #recoverAll} 이 지우기를 마저 하고 저장한 뒤 ready 로 바꾼다 (같은 틀로 두 번 해도 같음).
 * 짐이 두 번 생기거나 사라지지 않는다: 블록 안의 것과 pending 짐은 지우기 전에는 블록만, 저장 뒤에는 짐만 남는다.
 */
public final class PlotReset {

    private final HomesService s;
    private final Map<Material, ItemStack> tools = new EnumMap<>(Material.class);

    public PlotReset(HomesService s) { this.s = s; }

    /** 비우기 (selfVacate = 스스로 → 다시 받기 시간 적음). 끝나면 true. */
    public CompletableFuture<Boolean> start(PlotGeom plot, UUID owner, String ownerName, String reason, boolean selfVacate) {
        CompletableFuture<Boolean> done = new CompletableFuture<>();
        World w = s.mainWorld();
        if (w == null || plot == null || owner == null || s.busy(plot)) {
            done.complete(false);
            return done;
        }
        s.markBusy(plot, true);
        loadChunks(w, plot.x0(), plot.z0(), plot.x1(), plot.z1()).whenComplete((chunks, err) -> Bukkit.getScheduler().runTask(s.plugin(), () -> {
            boolean ok = false;
            try {
                if (err != null) {
                    Log.error("[집] " + plot.label() + " 청크를 불러오지 못해 비우지 않음", err);
                    s.markBusy(plot, false);
                } else ok = runNow(w, plot, owner, ownerName, reason, selfVacate);
            } catch (Throwable t) {
                Log.error("[집] " + plot.label() + " 비우기 오류", t);
                // 짐을 쓰기 전에 멈췄으면 블록은 그대로 → 다시 쓸 수 있게. 쓴 뒤면 다음 시작 때 recoverAll 이 마저 함 (그때까지 잠김)
                if (s.parcels().pending(owner) == null) s.markBusy(plot, false);
            } finally {
                release(w, chunks);
            }
            done.complete(ok);
        }));
        return done;
    }

    private boolean runNow(World w, PlotGeom plot, UUID owner, String ownerName, String reason, boolean self) {
        ParcelStore parcels = s.parcels();
        if (parcels.pending(owner) != null) {
            Log.warn("[집] " + plot.label() + ": 그 주인의 다른 짐이 비우는 중으로 남아 있어 멈춤 (다시 켜면 마저 함)");
            s.markBusy(plot, false);
            return false;
        }
        // ① 짐 모으기 (읽기만)
        List<ItemStack> items = new ArrayList<>();
        int touched = 0;
        for (int y = plot.yMax(); y >= plot.yMin(); y--) {
            for (int x = plot.x0(); x <= plot.x1(); x++) {
                for (int z = plot.z0(); z <= plot.z1(); z++) {
                    Block b = w.getBlockAt(x, y, z);
                    if (PlotResetPlan.isTemplate(b.getType().name(), y, plot.floorY())) continue;
                    touched++;
                    collectBlock(b, items);
                }
            }
        }
        List<Entity> ents = entities(w, plot);
        for (Entity e : ents) collectEntity(e, items);
        List<byte[]> bytes = new ArrayList<>();
        for (ItemStack it : items) if (it != null && !it.getType().isAir() && it.getAmount() > 0) bytes.add(it.serializeAsBytes());
        try {
            parcels.begin(owner, ownerName, new ParcelStore.Pending(plot.id(), reason, System.currentTimeMillis(), plot.x0(), plot.z0(), plot.x1(),
                    plot.z1(), plot.yMin(), plot.yMax(), plot.floorY(), plot.custom(), bytes));
        } catch (IOException | IllegalStateException e) {
            Log.warn("[집] " + plot.label() + " 맡긴 짐 파일을 쓰지 못해 멈춤 (블록은 그대로): " + e.getMessage());
            s.markBusy(plot, false);
            return false;
        }
        // ② 지우기 (여기서 멈추면 다음 시작 때 recoverAll 이 마저 함 — 그동안 집은 busy 로 잠김)
        clear(w, plot.x0(), plot.z0(), plot.x1(), plot.z1(), plot.yMin(), plot.yMax(), plot.floorY());
        // ③ 주인 풀기
        s.release(plot, owner, self);
        s.saveStore();
        // ④ 저장 → ⑤ ready
        finish(w, owner);
        s.markBusy(plot, false);
        s.changed(plot);
        Log.info("[집] " + plot.label() + " " + ("reclaim".equals(reason) ? "회수" : "비움") + " — 바꾼 칸 " + touched + " · 맡긴 짐 " + bytes.size()
                + "묶음 → " + (ownerName == null ? owner : ownerName));
        return true;
    }

    private void finish(World w, UUID owner) {
        try {
            w.save(true);
        } catch (Throwable t) {
            Log.warn("[집] 월드 저장 실패 — 맡긴 짐은 비우는 중으로 두고 다음 시작 때 마저 함: " + t.getMessage());
            return;
        }
        try {
            s.parcels().finish(owner);
        } catch (IOException e) {
            Log.warn("[집] 맡긴 짐 ready 쓰기 실패 — 다음 시작 때 마저 함: " + e.getMessage());
        }
    }

    /** 시작 때: pending 짐이 남은 집을 마저 비움 (지우기 → 주인 풀기 → 저장 → ready). */
    public void recoverAll() {
        ParcelStore parcels = s.parcels();
        if (parcels == null || parcels.dir() == null) return;
        World w = s.mainWorld();
        if (w == null) return;
        for (UUID owner : parcels.pendingOwners()) {
            ParcelStore.Pending p = parcels.pending(owner);
            if (p == null) continue;
            PlotGeom plot = s.plot(p.plotId());
            if (plot != null) s.markBusy(plot, true);
            loadChunks(w, p.x0(), p.z0(), p.x1(), p.z1()).whenComplete((chunks, err) -> Bukkit.getScheduler().runTask(s.plugin(), () -> {
                try {
                    if (err != null) {
                        Log.error("[집] 비우다 멈춘 집 (" + p.plotId() + ") 청크를 불러오지 못함 — 다음 시작 때 다시", err);
                        return;
                    }
                    clear(w, p.x0(), p.z0(), p.x1(), p.z1(), p.yMin(), p.yMax(), p.floorY());
                    if (plot != null) {
                        s.release(plot, owner, "vacate".equals(p.reason()));
                        s.saveStore();
                    }
                    finish(w, owner);
                    Log.info("[집] 비우다 멈춘 " + (plot == null ? p.plotId() : plot.label()) + " 을(를) 마저 비웠습니다 — 맡긴 짐 " + p.items().size() + "묶음");
                } catch (Throwable t) {
                    Log.error("[집] 비우다 멈춘 집 (" + p.plotId() + ") 마저 하기 실패", t);
                } finally {
                    if (plot != null) {
                        s.markBusy(plot, false);
                        s.changed(plot);
                    }
                    release(w, chunks);
                }
            }));
        }
    }

    // ── 지우기 (틀로) ────────────────────────────────────────────────────

    /** 높이 창 안을 틀로 (상자류는 먼저 비움 — 지울 때 쏟아지지 않게) + 맡긴 짐 엔티티 지움. 두 번 해도 같다. */
    static void clear(World w, int x0, int z0, int x1, int z1, int yMin, int yMax, int floorY) {
        for (int y = yMax; y >= yMin; y--) {
            Material tm = Material.matchMaterial(PlotResetPlan.template(y, floorY));
            if (tm == null) tm = Material.AIR;
            for (int x = x0; x <= x1; x++) {
                for (int z = z0; z <= z1; z++) {
                    Block b = w.getBlockAt(x, y, z);
                    if (PlotResetPlan.isTemplate(b.getType().name(), y, floorY)) continue;
                    emptyContainer(b);
                    b.setType(tm, false);
                }
            }
        }
        for (Entity e : entities(w, x0, z0, x1, z1, yMin, yMax)) e.remove();
    }

    private static void emptyContainer(Block b) {
        BlockState st = b.getState();
        try {
            if (st instanceof Jukebox jb) jb.stopPlaying();
            if (st instanceof Chest c) c.getBlockInventory().clear();
            else if (st instanceof InventoryHolder h) h.getInventory().clear();
            if (st instanceof Campfire cf) {
                for (int i = 0; i < cf.getSize(); i++) cf.setItem(i, null);
                cf.update(true, false);
            }
        } catch (Throwable ignored) {
            // 지울 블록 — 비우지 못해도 setType 이 지움
        }
    }

    // ── 짐 모으기 ────────────────────────────────────────────────────────

    private void collectBlock(Block b, List<ItemStack> out) {
        Material m = b.getType();
        BlockState st = b.getState();
        boolean container = st instanceof InventoryHolder;
        Map<String, String> props = PlotResetPlan.props(b.getBlockData().getAsString());
        PlotResetPlan.Take t = PlotResetPlan.take(m.name(), props, container);
        switch (t) {
            case NOTHING, SECOND_HALF -> { }
            case SHULKER_ITEM -> out.add(shulkerItem(m, st));
            case CONTENTS_AND_DROPS -> {
                Inventory inv = st instanceof Chest c ? c.getBlockInventory() : ((InventoryHolder) st).getInventory();
                for (ItemStack it : inv.getContents()) if (it != null && !it.getType().isAir()) out.add(it.clone());
                drops(b, m, props, out);
            }
            case DROPS -> {
                if (st instanceof Campfire cf) for (int i = 0; i < cf.getSize(); i++) {
                    ItemStack it = cf.getItem(i);
                    if (it != null && !it.getType().isAir()) out.add(it.clone());
                }
                drops(b, m, props, out);
            }
        }
    }

    private static ItemStack shulkerItem(Material m, BlockState st) {
        ItemStack it = ItemStack.of(m);
        ItemMeta meta = it.getItemMeta();
        if (meta instanceof BlockStateMeta bsm && st instanceof ShulkerBox) {
            bsm.setBlockState(st);
            if (st instanceof Nameable n && n.customName() != null) bsm.customName(n.customName());
            it.setItemMeta(bsm);
        }
        return it;
    }

    private void drops(Block b, Material m, Map<String, String> props, List<ItemStack> out) {
        Collection<ItemStack> d;
        try {
            d = b.getDrops(tool(m), null);
        } catch (Throwable t) {
            d = List.of();
        }
        boolean any = false;
        for (ItemStack it : d) if (it != null && !it.getType().isAir()) {
            out.add(it);
            any = true;
        }
        if (any) return;
        int n = PlotResetPlan.fallbackCount(m.name(), props);
        if (n <= 0) return;
        Material pm;
        try {
            pm = b.getBlockData().getPlacementMaterial();
        } catch (Throwable t) {
            pm = m;
        }
        if (pm != null && !pm.isAir() && pm.isItem()) out.add(ItemStack.of(pm, Math.min(n, pm.getMaxStackSize())));
    }

    /** 섬세한 손길 네더라이트 도구 (블록에 맞는 것). */
    private ItemStack tool(Material m) {
        Material t = Tag.MINEABLE_AXE.isTagged(m) ? Material.NETHERITE_AXE
                : Tag.MINEABLE_SHOVEL.isTagged(m) ? Material.NETHERITE_SHOVEL
                : Tag.MINEABLE_HOE.isTagged(m) ? Material.NETHERITE_HOE : Material.NETHERITE_PICKAXE;
        return tools.computeIfAbsent(t, k -> {
            ItemStack it = ItemStack.of(k);
            it.addUnsafeEnchantment(Enchantment.SILK_TOUCH, 1);
            return it;
        });
    }

    private static void collectEntity(Entity e, List<ItemStack> out) {
        PlotResetPlan.EntityTake t = PlotResetPlan.entity(e.getType().name());
        switch (t) {
            case ITEM_FRAME -> {
                ItemFrame f = (ItemFrame) e;
                ItemStack in = f.getItem();
                if (in != null && !in.getType().isAir()) out.add(in.clone());
                out.add(ItemStack.of(e.getType().name().startsWith("GLOW") ? Material.GLOW_ITEM_FRAME : Material.ITEM_FRAME));
            }
            case PAINTING -> out.add(ItemStack.of(Material.PAINTING));
            case ARMOR_STAND -> {
                EntityEquipment eq = ((ArmorStand) e).getEquipment();
                for (EquipmentSlot slot : new EquipmentSlot[] {EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET,
                        EquipmentSlot.HAND, EquipmentSlot.OFF_HAND}) {
                    try {
                        ItemStack it = eq.getItem(slot);
                        if (it != null && !it.getType().isAir()) out.add(it.clone());
                    } catch (Throwable ignored) {
                        // 그 칸 없음
                    }
                }
                out.add(ItemStack.of(Material.ARMOR_STAND));
            }
            case VEHICLE -> {
                if (e instanceof InventoryHolder h) for (ItemStack it : h.getInventory().getContents()) {
                    if (it != null && !it.getType().isAir()) out.add(it.clone());
                }
                Material item = Material.matchMaterial(e.getType().name());
                if (item != null && item.isItem()) out.add(ItemStack.of(item));
            }
            case ITEM -> {
                ItemStack it = ((Item) e).getItemStack();
                if (it != null && !it.getType().isAir()) out.add(it.clone());
            }
            case NONE -> { }
        }
    }

    private static List<Entity> entities(World w, PlotGeom p) { return entities(w, p.x0(), p.z0(), p.x1(), p.z1(), p.yMin(), p.yMax()); }

    /** 맡긴 짐으로 갈 엔티티 (액자·그림·거치대·탈것·아이템 — 동물·플레이어는 아님). */
    static List<Entity> entities(World w, int x0, int z0, int x1, int z1, int yMin, int yMax) {
        BoundingBox box = new BoundingBox(x0, yMin, z0, x1 + 1, yMax + 1, z1 + 1);
        List<Entity> out = new ArrayList<>();
        for (Entity e : w.getNearbyEntities(box)) {
            if (e instanceof Player) continue;
            if (!box.contains(e.getLocation().toVector())) continue;
            if (PlotResetPlan.entity(e.getType().name()) != PlotResetPlan.EntityTake.NONE) out.add(e);
        }
        return out;
    }

    // ── 청크 ─────────────────────────────────────────────────────────────

    private CompletableFuture<List<Chunk>> loadChunks(World w, int x0, int z0, int x1, int z1) {
        List<CompletableFuture<Chunk>> fs = new ArrayList<>();
        for (int cx = x0 >> 4; cx <= x1 >> 4; cx++) for (int cz = z0 >> 4; cz <= z1 >> 4; cz++) fs.add(w.getChunkAtAsync(cx, cz, true));
        return CompletableFuture.allOf(fs.toArray(new CompletableFuture[0])).thenApply(v -> {
            List<Chunk> out = new ArrayList<>();
            for (CompletableFuture<Chunk> f : fs) {
                Chunk c = f.join();
                if (c != null) {
                    c.addPluginChunkTicket(s.plugin());
                    out.add(c);
                }
            }
            return out;
        });
    }

    private void release(World w, List<Chunk> chunks) {
        if (chunks == null) return;
        for (Chunk c : chunks) {
            try {
                c.removePluginChunkTicket(s.plugin());
            } catch (Throwable ignored) {
                // 꺼지는 중
            }
        }
    }
}
