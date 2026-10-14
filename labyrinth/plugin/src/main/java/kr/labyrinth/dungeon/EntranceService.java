package kr.labyrinth.dungeon;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import kr.labyrinth.Services;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.Tag;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.Hangable;
import org.bukkit.block.data.type.Slab;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.scheduler.BukkitTask;

/**
 * 오버월드 입구 (/labadmin setentrance [block|npc], removeentrance).
 * <ul>
 *   <li>block: 지형에 맞춘 작은 자체 디자인 석문(5×3, 높이 6). 단단한 땅을 찾고 물·용암·잎·얼음 위나 경사 2칸 이상이면 거절.
 *       발자국 안에서 공기·풀·꽃·눈 같은 대체 가능 블록만 바꾸고 원래 블록을 entrance.yml 에 기억 → removeentrance 가 그대로 복원.</li>
 *   <li>npc: 블록 변경 0 — 안내인 NPC 만 세운다.</li>
 * </ul>
 * 두 방식 모두 안내인 NPC(npcs.yml role: entrance)를 곁에 세우고 config.yml entrance 위치를 저장한다.
 */
public final class EntranceService implements Listener {

    private static final Set<Material> BAD_GROUND = EnumSet.of(Material.WATER, Material.LAVA, Material.ICE, Material.PACKED_ICE,
            Material.BLUE_ICE, Material.FROSTED_ICE, Material.SNOW, Material.POWDER_SNOW, Material.MAGMA_BLOCK, Material.CACTUS,
            Material.SCAFFOLDING, Material.BEDROCK);

    private final Services services;
    private final DungeonManager manager;
    private final File file;
    /** 원래 블록 기록: "world,x,y,z" → BlockData 문자열. */
    private final List<String[]> saved = new ArrayList<>();
    private final Set<String> gateBlocks = new HashSet<>();
    private BukkitTask fx;
    private Location gateCenter;

    EntranceService(Services services, DungeonManager manager) {
        this.services = services;
        this.manager = manager;
        this.file = new File(services.plugin().getDataFolder(), "entrance.yml");
    }

    void enable() {
        load();
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        fx = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::ambient, 40L, 20L);
    }

    void disable() {
        HandlerList.unregisterAll(this);
        if (fx != null) fx.cancel();
    }

    // ── 설치 ──────────────────────────────────────────────────────────────

    /** @return 결과 메시지 (MiniMessage) */
    public String setEntrance(Player admin, String modeArg) {
        if (manager.isLabyrinthWorld(admin.getWorld())) return "<red>미궁 월드 안에는 입구를 만들 수 없습니다.";
        String mode = modeArg != null ? modeArg : services.settings().entrance().mode();
        if (mode == null || mode.isBlank()) mode = "block";
        mode = mode.toLowerCase(java.util.Locale.ROOT);
        if (!mode.equals("block") && !mode.equals("npc")) return "<red>방식은 block 또는 npc 입니다.";
        if (!saved.isEmpty()) restoreBlocks();

        Location base = admin.getLocation().clone();
        BlockFace facing = cardinal(base.getYaw());
        Location entranceLoc;
        if (mode.equals("block")) {
            Build b = plan(base, facing);
            if (b.error != null) return "<red>여기에는 입구를 세울 수 없습니다: <white>" + b.error + "</white> <gray>(평평하고 마른 땅에서 다시 시도하거나 npc 방식을 쓰세요)";
            for (Place pl : b.places) {
                Block blk = pl.block;
                saved.add(new String[] {key(blk), blk.getBlockData().getAsString()});
                blk.setBlockData(pl.data, false);
                gateBlocks.add(key(blk));
            }
            gateCenter = b.center;
            entranceLoc = b.front;
            save();
        } else {
            entranceLoc = base;
            gateCenter = null;
        }
        String finalMode = mode;
        Location el = entranceLoc;
        services.updateConfig(c -> {
            c.set("entrance.mode", finalMode);
            c.set("entrance.world", el.getWorld().getName());
            c.set("entrance.x", el.getX());
            c.set("entrance.y", el.getY());
            c.set("entrance.z", el.getZ());
            c.set("entrance.yaw", (double) el.getYaw());
            c.set("entrance.pitch", 0.0);
        });
        // 안내인 NPC
        String guide = guideNpc();
        String npcMsg = "";
        if (guide != null) {
            try {
                Location npcAt = mode.equals("block") ? entranceLoc.clone().add(rightOf(facing).getModX() * 3, 0, rightOf(facing).getModZ() * 3) : base;
                npcAt.setYaw(base.getYaw() + 180);
                services.npcs().place(guide, npcAt);
                npcMsg = " <gray>· 안내인 NPC 배치";
            } catch (Throwable t) {
                Log.error("입구 NPC 배치 실패", t);
            }
        }
        admin.playSound(admin.getLocation(), Sound.BLOCK_END_PORTAL_FRAME_FILL, 1.0f, 0.8f);
        return "<green>미궁 입구를 만들었습니다</green> <gray>(" + (mode.equals("block") ? "석문 · 바뀐 블록 " + saved.size() + "개, removeentrance 로 복원" : "NPC 전용 · 블록 변경 없음")
                + ")" + npcMsg;
    }

    public String removeEntrance() {
        int n = saved.size();
        restoreBlocks();
        String guide = guideNpc();
        if (guide != null) {
            try {
                services.npcs().remove(guide);
            } catch (Throwable ignored) {
                // NPC 없음
            }
        }
        services.updateConfig(c -> {
            c.set("entrance.world", "");
            c.set("entrance.mode", services.settings().entrance().mode());
        });
        return "<green>입구를 제거했습니다</green> <gray>(원래 블록 " + n + "개 복원)";
    }

    /**
     * 예전 석문 기록을 복원하지 않고 버린다 (마을 월드로 바꿨을 때 — 예전 월드 좌표라 새 월드를 망가뜨림, VILLAGE.md §4.3).
     * entrance.yml → entrance.yml.old. @return 버린 블록 기록 수
     */
    public int forgetSaved() {
        int n = saved.size();
        saved.clear();
        gateBlocks.clear();
        gateCenter = null;
        if (file.exists()) {
            File old = new File(file.getParentFile(), "entrance.yml.old");
            if (old.exists() && !old.delete()) Log.warn("entrance.yml.old 지우기 실패");
            if (!file.renameTo(old)) Log.warn("entrance.yml → entrance.yml.old 이름 바꾸기 실패");
        }
        return n;
    }

    private String guideNpc() {
        for (var n : services.content().npcs().values()) if ("entrance".equals(n.role())) return n.id();
        return null;
    }

    private void restoreBlocks() {
        for (int i = saved.size() - 1; i >= 0; i--) {
            String[] s = saved.get(i);
            Block b = block(s[0]);
            if (b == null) continue;
            try {
                b.setBlockData(Bukkit.createBlockData(s[1]), false);
            } catch (IllegalArgumentException e) {
                b.setType(Material.AIR, false);
            }
        }
        saved.clear();
        gateBlocks.clear();
        gateCenter = null;
        save();
    }

    // ── 지형 판단 ─────────────────────────────────────────────────────────

    private record Place(Block block, BlockData data) {}

    private static final class Build {
        final List<Place> places = new ArrayList<>();
        String error;
        Location center;
        Location front;
    }

    /** 대체 가능한 블록 (공기·풀·꽃·덤불·눈 한 겹). */
    static boolean replaceable(Block b) {
        Material m = b.getType();
        if (m.isAir()) return true;
        if (m == Material.SNOW || m == Material.SHORT_GRASS || m == Material.TALL_GRASS || m == Material.FERN || m == Material.LARGE_FERN
                || m == Material.DEAD_BUSH || m == Material.SWEET_BERRY_BUSH) return true;
        return Tag.FLOWERS.isTagged(m) || Tag.SAPLINGS.isTagged(m);
    }

    /** 단단한 땅 높이 (x,z 열에서 from 부터 아래로). 나무 잎·물 등은 오류. */
    private int groundY(World w, int x, int z, int from, String[] err) {
        for (int y = from + 3; y >= from - 6; y--) {
            Block b = w.getBlockAt(x, y, z);
            if (replaceable(b)) continue;
            Material m = b.getType();
            if (BAD_GROUND.contains(m) || Tag.LEAVES.isTagged(m) || Tag.LOGS.isTagged(m) || b.isLiquid()) {
                err[0] = "물·얼음·나무 위";
                return Integer.MIN_VALUE;
            }
            if (!m.isSolid() || !m.isOccluding()) {
                err[0] = "단단하지 않은 바닥";
                return Integer.MIN_VALUE;
            }
            return y;
        }
        err[0] = "바닥을 찾을 수 없음";
        return Integer.MIN_VALUE;
    }

    private Build plan(Location base, BlockFace facing) {
        Build b = new Build();
        World w = base.getWorld();
        BlockFace right = rightOf(facing);
        int fx = facing.getModX(), fz = facing.getModZ(), rx = right.getModX(), rz = right.getModZ();
        // 문 중심: 관리자 앞 3칸
        int ox = base.getBlockX() + fx * 3, oz = base.getBlockZ() + fz * 3;
        int[][] heights = new int[5][3];
        int min = Integer.MAX_VALUE, max = Integer.MIN_VALUE;
        String[] err = new String[1];
        for (int u = -2; u <= 2; u++) {
            for (int v = 0; v < 3; v++) {
                int x = ox + rx * u + fx * v, z = oz + rz * u + fz * v;
                int y = groundY(w, x, z, base.getBlockY() - 1, err);
                if (y == Integer.MIN_VALUE) {
                    b.error = err[0];
                    return b;
                }
                heights[u + 2][v] = y;
                min = Math.min(min, y);
                max = Math.max(max, y);
            }
        }
        if (max - min > 1) {
            b.error = "경사가 너무 가파름 (높이 차 " + (max - min) + ")";
            return b;
        }
        int floorY = max + 1; // 발판 높이 (땅 위 반 블록 계단)
        // 낮은 칸은 받침 블록 (그 자리는 대체 가능 블록이어야 함)
        for (int u = -2; u <= 2; u++) {
            for (int v = 0; v < 3; v++) {
                int x = ox + rx * u + fx * v, z = oz + rz * u + fz * v;
                for (int y = heights[u + 2][v] + 1; y < floorY; y++) {
                    if (!add(b, w.getBlockAt(x, y, z), Material.COBBLED_DEEPSLATE.createBlockData())) return b;
                }
                Slab slab = (Slab) Material.POLISHED_DEEPSLATE_SLAB.createBlockData();
                slab.setType(Slab.Type.BOTTOM);
                if (!add(b, w.getBlockAt(x, floorY, z), slab)) return b;
            }
        }
        // 기둥 (u = ±2, v = 1)
        Material[] pillar = {Material.POLISHED_DEEPSLATE, Material.CHISELED_DEEPSLATE, Material.POLISHED_DEEPSLATE, Material.DEEPSLATE_TILES};
        for (int side : new int[] {-2, 2}) {
            int x = ox + rx * side + fx, z = oz + rz * side + fz;
            for (int i = 0; i < pillar.length; i++) if (!add(b, w.getBlockAt(x, floorY + 1 + i, z), pillar[i].createBlockData())) return b;
        }
        // 상인방 (y = floorY+5, u -2..2, v = 1)
        for (int u = -2; u <= 2; u++) {
            int x = ox + rx * u + fx, z = oz + rz * u + fz;
            Material m = u == 0 ? Material.CRYING_OBSIDIAN : Math.abs(u) == 2 ? Material.POLISHED_DEEPSLATE : Material.DEEPSLATE_BRICKS;
            if (!add(b, w.getBlockAt(x, floorY + 5, z), m.createBlockData())) return b;
        }
        // 매달린 영혼 등불 (u = ±1)
        for (int side : new int[] {-1, 1}) {
            int x = ox + rx * side + fx, z = oz + rz * side + fz;
            BlockData lantern = Material.SOUL_LANTERN.createBlockData();
            if (lantern instanceof Hangable h) h.setHanging(true);
            if (!add(b, w.getBlockAt(x, floorY + 4, z), lantern)) return b;
        }
        // 문 안쪽 공간은 비어 있어야 함 (u -1..1, v 1, 높이 1..3)
        for (int u = -1; u <= 1; u++) {
            for (int y = 1; y <= 3; y++) {
                Block blk = w.getBlockAt(ox + rx * u + fx, floorY + y, oz + rz * u + fz);
                if (!replaceable(blk)) {
                    b.error = "문 자리를 막는 블록 (" + blk.getType().name().toLowerCase() + ")";
                    return b;
                }
            }
        }
        b.center = new Location(w, ox + fx + 0.5, floorY + 1, oz + fz + 0.5);
        b.front = base.clone();
        b.front.setYaw(yawOf(facing));
        b.front.setPitch(0);
        return b;
    }

    private boolean add(Build b, Block blk, BlockData data) {
        if (!replaceable(blk)) {
            b.error = "발자국 안에 다른 블록 (" + blk.getType().name().toLowerCase() + ")";
            return false;
        }
        b.places.add(new Place(blk, data));
        return true;
    }

    static BlockFace cardinal(float yaw) {
        float y = (yaw % 360 + 360) % 360;
        if (y >= 315 || y < 45) return BlockFace.SOUTH;
        if (y < 135) return BlockFace.WEST;
        if (y < 225) return BlockFace.NORTH;
        return BlockFace.EAST;
    }

    static float yawOf(BlockFace f) {
        return switch (f) {
            case SOUTH -> 0;
            case WEST -> 90;
            case NORTH -> 180;
            default -> -90;
        };
    }

    static BlockFace rightOf(BlockFace f) {
        return switch (f) {
            case NORTH -> BlockFace.EAST;
            case EAST -> BlockFace.SOUTH;
            case SOUTH -> BlockFace.WEST;
            default -> BlockFace.NORTH;
        };
    }

    // ── 상호작용·보호·연출 ────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEvent e) {
        if (e.getAction() != Action.RIGHT_CLICK_BLOCK || e.getClickedBlock() == null || gateBlocks.isEmpty()) return;
        if (!gateBlocks.contains(key(e.getClickedBlock()))) return;
        e.setCancelled(true);
        services.menus().openEntrance(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBreak(BlockBreakEvent e) {
        if (gateBlocks.isEmpty() || !gateBlocks.contains(key(e.getBlock()))) return;
        e.setCancelled(true);
        Text.error(e.getPlayer(), "미궁 입구는 부술 수 없습니다. (관리자: /labadmin removeentrance)");
    }

    private void ambient() {
        if (gateCenter == null || gateCenter.getWorld() == null) return;
        if (!gateCenter.isChunkLoaded()) return;
        gateCenter.getWorld().spawnParticle(Particle.REVERSE_PORTAL, gateCenter.clone().add(0, 1.2, 0), 12, 0.7, 1.0, 0.15, 0.01);
        gateCenter.getWorld().spawnParticle(Particle.SOUL, gateCenter.clone().add(0, 0.3, 0), 1, 0.6, 0.1, 0.1, 0.01);
    }

    // ── 저장 ──────────────────────────────────────────────────────────────

    private static String key(Block b) { return b.getWorld().getName() + "," + b.getX() + "," + b.getY() + "," + b.getZ(); }

    private static Block block(String key) {
        String[] a = key.split(",");
        World w = Bukkit.getWorld(a[0]);
        if (w == null) return null;
        return w.getBlockAt(Integer.parseInt(a[1]), Integer.parseInt(a[2]), Integer.parseInt(a[3]));
    }

    private void load() {
        saved.clear();
        gateBlocks.clear();
        if (!file.exists()) return;
        YamlConfiguration y = YamlConfiguration.loadConfiguration(file);
        for (String line : y.getStringList("blocks")) {
            int i = line.indexOf('|');
            if (i < 0) continue;
            String k = line.substring(0, i);
            saved.add(new String[] {k, line.substring(i + 1)});
            gateBlocks.add(k);
        }
        String c = y.getString("center", "");
        gateCenter = c == null || c.isBlank() ? null : DungeonManager.deserialize(c);
    }

    private void save() {
        YamlConfiguration y = new YamlConfiguration();
        List<String> lines = new ArrayList<>();
        for (String[] s : saved) lines.add(s[0] + "|" + s[1]);
        y.set("blocks", lines);
        y.set("center", gateCenter == null ? "" : DungeonManager.serialize(gateCenter));
        y.options().setHeader(List.of("미궁 입구 석문이 바꾼 원래 블록 (removeentrance 가 복원). 직접 고치지 마세요."));
        try {
            y.save(file);
        } catch (IOException e) {
            Log.warn("entrance.yml 저장 실패: " + e.getMessage());
        }
    }
}
