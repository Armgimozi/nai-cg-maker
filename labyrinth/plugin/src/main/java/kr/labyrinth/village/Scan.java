package kr.labyrinth.village;

import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.function.Consumer;
import org.bukkit.Chunk;
import org.bukkit.ChunkSnapshot;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Biome;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.type.Leaves;
import org.bukkit.plugin.Plugin;

/**
 * 지형 조사 도구: 청크 비동기 로드(동시 요청 수 제한) → 메인 스레드에서 ChunkSnapshot → 비동기 스레드에서 열 분석.
 * 비동기 쪽은 스냅샷만 읽는다 (Bukkit 월드 API 금지).
 */
final class Scan {

    private Scan() {}

    static long key(int cx, int cz) { return ((long) cx << 32) ^ (cz & 0xffffffffL); }

    // ── 블록 종류 캐시 (Material ordinal → Nature.Kind, 이름만 보므로 어느 스레드든 안전) ──────────

    private static volatile Nature.Kind[] kinds;

    static Nature.Kind kind(Material m) {
        Nature.Kind[] k = kinds;
        if (k == null) {
            Material[] all = Material.values();
            k = new Nature.Kind[all.length];
            for (Material x : all) k[x.ordinal()] = Nature.kind(x.name());
            kinds = k;
        }
        return m == null ? Nature.Kind.AIR : k[m.ordinal()];
    }

    static String id(Material m) { return m.name().toLowerCase(Locale.ROOT); }

    /** 자연 잎인가 (persistent=false). */
    static boolean naturalLeaves(BlockData d) { return d instanceof Leaves l && !l.isPersistent(); }

    // ── 청크 펌프 (메인 스레드에서 매 틱 pump) ─────────────────────────────────

    static final class ChunkPump {
        private final World world;
        private final Plugin plugin;
        private final boolean generate;
        private final boolean ticket;
        private final int max;
        private final ArrayDeque<long[]> queue = new ArrayDeque<>();
        private final Consumer<Chunk> onLoaded;
        final Set<Long> ticketed = new HashSet<>();
        int inflight, done, failed, total;

        ChunkPump(World world, Plugin plugin, boolean generate, boolean ticket, int maxInflight, Consumer<Chunk> onLoaded) {
            this.world = world;
            this.plugin = plugin;
            this.generate = generate;
            this.ticket = ticket;
            this.max = maxInflight;
            this.onLoaded = onLoaded;
        }

        /** 블록 좌표 사각형을 덮는 청크들 (가까운 것부터). */
        ChunkPump area(int minX, int minZ, int maxX, int maxZ) {
            int cx0 = minX >> 4, cz0 = minZ >> 4, cx1 = maxX >> 4, cz1 = maxZ >> 4;
            int mx = (cx0 + cx1) / 2, mz = (cz0 + cz1) / 2;
            java.util.List<long[]> all = new java.util.ArrayList<>();
            for (int cz = cz0; cz <= cz1; cz++) for (int cx = cx0; cx <= cx1; cx++) all.add(new long[] {cx, cz});
            all.sort((a, b) -> Long.compare(Math.max(Math.abs(a[0] - mx), Math.abs(a[1] - mz)), Math.max(Math.abs(b[0] - mx), Math.abs(b[1] - mz))));
            queue.addAll(all);
            total += all.size();
            return this;
        }

        void pump() {
            while (inflight < max && !queue.isEmpty()) {
                long[] c = queue.poll();
                int cx = (int) c[0], cz = (int) c[1];
                inflight++;
                world.getChunkAtAsync(cx, cz, generate).whenComplete((chunk, err) -> {
                    inflight--;
                    done++;
                    if (chunk == null || err != null) {
                        failed++;
                        return;
                    }
                    if (ticket && world.addPluginChunkTicket(cx, cz, plugin)) ticketed.add(key(cx, cz));
                    onLoaded.accept(chunk);
                });
            }
        }

        boolean finished() { return queue.isEmpty() && inflight == 0; }

        double progress() { return total == 0 ? 1 : (double) done / total; }

        void release() {
            for (long k : ticketed) world.removePluginChunkTicket((int) (k >> 32), (int) k, plugin);
            ticketed.clear();
        }
    }

    // ── 스냅샷 모음 (비동기 읽기) ─────────────────────────────────────────

    static final class Snapshots {
        final Map<Long, ChunkSnapshot> map = new java.util.concurrent.ConcurrentHashMap<>();
        final int minY, maxY;

        Snapshots(World w) {
            this.minY = w.getMinHeight();
            this.maxY = w.getMaxHeight() - 1;
        }

        void add(Chunk c) { map.put(key(c.getX(), c.getZ()), c.getChunkSnapshot(true, true, false, false)); }

        boolean has(int x, int z) { return map.containsKey(key(x >> 4, z >> 4)); }

        /** 없는 청크·범위 밖 = null. */
        Material type(int x, int y, int z) {
            if (y < minY || y > maxY) return null;
            ChunkSnapshot s = map.get(key(x >> 4, z >> 4));
            return s == null ? null : s.getBlockType(x & 15, y, z & 15);
        }

        BlockData data(int x, int y, int z) {
            if (y < minY || y > maxY) return null;
            ChunkSnapshot s = map.get(key(x >> 4, z >> 4));
            return s == null ? null : s.getBlockData(x & 15, y, z & 15);
        }

        int highest(int x, int z) {
            ChunkSnapshot s = map.get(key(x >> 4, z >> 4));
            return s == null ? minY : Math.min(maxY, s.getHighestBlockYAt(x & 15, z & 15) + 1);
        }
    }

    // ── 열 분석 (비동기) ─────────────────────────────────────────────────

    /** 스냅샷 한 청크의 열들을 grid 에 채운다 (VILLAGE.md §4.1 1번 땅높이 규칙). */
    static void columns(ChunkSnapshot snap, TerrainGrid grid, int minY, int maxY) {
        int bx = snap.getX() << 4, bz = snap.getZ() << 4;
        for (int lz = 0; lz < 16; lz++) {
            for (int lx = 0; lx < 16; lx++) {
                int wx = bx + lx, wz = bz + lz;
                if (!grid.contains(wx, wz)) continue;
                int top = Math.min(maxY, snap.getHighestBlockYAt(lx, lz) + 1);
                int ground = Integer.MIN_VALUE, flags = 0, logs = 0;
                String note = null, waterNote = null, surface = null;
                Material above = null;
                for (int y = top; y >= minY; y--) {
                    Material m = snap.getBlockType(lx, y, lz);
                    Nature.Kind k = kind(m);
                    if (k == Nature.Kind.AIR) continue;
                    switch (k) {
                        case LIQUID, ICE -> {
                            flags |= Terrain.WATER;
                            if (waterNote == null) waterNote = id(m) + "@" + y;
                        }
                        case LOG -> {
                            logs++;
                            flags |= Terrain.TREE;
                        }
                        case LEAVES -> {
                            if (naturalLeaves(snap.getBlockData(lx, y, lz))) flags |= Terrain.TREE;
                            else {
                                flags |= Terrain.UNNATURAL;
                                if (note == null) note = id(m) + "[persistent]@" + y;
                            }
                        }
                        case TREE_PART -> flags |= Terrain.TREE;
                        case UNNATURAL -> {
                            flags |= Terrain.UNNATURAL;
                            if (note == null) note = id(m) + "@" + y;
                        }
                        default -> { }
                    }
                    if (k == Nature.Kind.GROUND) {
                        ground = y;
                        surface = id(m);
                        if (above == Material.SNOW) flags |= Terrain.SNOW;
                        break;
                    }
                    above = m;
                }
                if (ground == Integer.MIN_VALUE) {
                    ground = minY;
                    flags |= Terrain.WATER;
                    if (waterNote == null) waterNote = "바닥 없음";
                }
                int holes = 0;
                for (int k = 1; k <= 16; k++) {
                    int y = ground - k;
                    if (y < minY) break;
                    Material m = snap.getBlockType(lx, y, lz);
                    Nature.Kind kk = kind(m);
                    if (kk == Nature.Kind.AIR || kk == Nature.Kind.LIQUID) holes |= 1 << (k - 1);
                    else if (kk == Nature.Kind.UNNATURAL && k <= 10) {
                        flags |= Terrain.UNNATURAL;
                        if (note == null) note = id(m) + "@" + y + "(땅속)";
                    }
                }
                String biome = "?";
                try {
                    Biome b = snap.getBiome(lx, Math.min(maxY, ground + 1), lz);
                    biome = b.getKey().getKey();
                } catch (Throwable ignored) {
                    // 바이옴 없음
                }
                String why = (flags & Terrain.UNNATURAL) != 0 ? note : waterNote;
                grid.set(wx, wz, ground, holes, flags, logs, surface, biome, why);
            }
        }
    }

    /** 청크 좌표 묶음 → 맵 (Map 이 필요할 때). */
    static Map<Long, int[]> chunks(int minX, int minZ, int maxX, int maxZ) {
        Map<Long, int[]> out = new HashMap<>();
        for (int cz = minZ >> 4; cz <= maxZ >> 4; cz++) for (int cx = minX >> 4; cx <= maxX >> 4; cx++) out.put(key(cx, cz), new int[] {cx, cz});
        return out;
    }
}
