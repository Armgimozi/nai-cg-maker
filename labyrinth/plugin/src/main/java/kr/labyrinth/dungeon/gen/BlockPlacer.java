package kr.labyrinth.dungeon.gen;

import java.util.ArrayDeque;
import java.util.HashSet;
import java.util.Set;
import java.util.function.DoubleConsumer;
import kr.labyrinth.core.Log;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.data.BlockData;
import org.bukkit.plugin.Plugin;
import org.bukkit.scheduler.BukkitTask;

/**
 * 틱당 상한으로 블록을 나눠 쓰는 단일 작업 큐 (ARCHITECTURE §7). 배치 작업은 먼저 대상 청크를 비동기로 불러와
 * 플러그인 청크 티켓을 건다(층이 살아 있는 동안 유지 — 해제는 {@link #releaseChunks}). 물리 갱신 없이 쓴다.
 */
public final class BlockPlacer {

    private static final BlockData AIR = Material.AIR.createBlockData();

    private final Plugin plugin;
    private final ArrayDeque<Job> queue = new ArrayDeque<>();
    private BukkitTask task;
    private volatile int budget;

    public BlockPlacer(Plugin plugin, int budget) {
        this.plugin = plugin;
        this.budget = budget;
    }

    public void budget(int b) { this.budget = Math.max(200, b); }

    public void start() {
        if (task == null) task = Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 1L, 1L);
    }

    public void stop() {
        if (task != null) task.cancel();
        task = null;
    }

    public int pending() { return queue.size(); }

    /** 블록 배치 (청크 선로딩 → 배치). progress 는 0~1, done 은 메인 스레드. */
    public Runnable place(World world, BlockList list, Set<Long> chunkTickets, DoubleConsumer progress, Runnable done) {
        Job job = new Job(world, list, null, progress, done);
        Runnable cancel = () -> job.cancelled = true;
        Set<Long> chunks = new HashSet<>();
        for (int i = 0; i < list.size(); i++) {
            long p = list.pos(i);
            chunks.add(chunkKey(BlockList.x(p) >> 4, BlockList.z(p) >> 4));
        }
        job.waiting = chunks.size();
        if (chunks.isEmpty()) {
            queue.add(job);
            return cancel;
        }
        for (long key : chunks) {
            int cx = (int) (key >> 32), cz = (int) key;
            world.getChunkAtAsync(cx, cz, true).whenComplete((chunk, err) -> Bukkit.getScheduler().runTask(plugin, () -> {
                if (chunk != null && !job.cancelled) {
                    chunk.addPluginChunkTicket(plugin);
                    synchronized (chunkTickets) { chunkTickets.add(key); }
                }
                if (--job.waiting == 0 && !job.cancelled) queue.add(job);
            }));
        }
        return cancel;
    }

    /** 좌표 목록을 공기로 (정리). */
    public void clear(World world, long[] positions, Runnable done) {
        queue.add(new Job(world, null, positions, null, done));
    }

    /** 즉시 동기 정리 (서버 종료 시). */
    public static void clearNow(World world, long[] positions) {
        for (long p : positions) {
            int x = BlockList.x(p), y = BlockList.y(p), z = BlockList.z(p);
            if (!world.isChunkLoaded(x >> 4, z >> 4)) world.getChunkAt(x >> 4, z >> 4);
            world.getBlockAt(x, y, z).setBlockData(AIR, false);
        }
    }

    public void releaseChunks(World world, Set<Long> tickets) {
        synchronized (tickets) {
            for (long key : tickets) {
                try {
                    world.removePluginChunkTicket((int) (key >> 32), (int) key, plugin);
                } catch (Exception ignored) {
                    // 월드가 내려간 경우
                }
            }
            tickets.clear();
        }
    }

    public static long chunkKey(int cx, int cz) { return ((long) cx << 32) | (cz & 0xFFFFFFFFL); }

    private void tick() {
        int left = budget;
        while (left > 0 && !queue.isEmpty()) {
            Job job = queue.peek();
            if (job.cancelled) {
                queue.poll();
                continue;
            }
            try {
                left -= job.step(left);
            } catch (Throwable t) {
                Log.error("블록 작업 오류", t);
                job.index = job.total();
            }
            if (job.index >= job.total()) {
                queue.poll();
                if (job.progress != null) job.progress.accept(1.0);
                if (job.done != null) {
                    try {
                        job.done.run();
                    } catch (Throwable t) {
                        Log.error("블록 작업 완료 처리 오류", t);
                    }
                }
            } else if (job.progress != null) {
                job.progress.accept(job.index / (double) Math.max(1, job.total()));
            }
        }
    }

    private static final class Job {
        final World world;
        final BlockList list;
        final long[] clear;
        final DoubleConsumer progress;
        final Runnable done;
        int index;
        int waiting;
        boolean cancelled;

        Job(World world, BlockList list, long[] clear, DoubleConsumer progress, Runnable done) {
            this.world = world;
            this.list = list;
            this.clear = clear;
            this.progress = progress;
            this.done = done;
        }

        int total() { return list != null ? list.size() : clear.length; }

        int step(int max) {
            int n = 0;
            int total = total();
            while (n < max && index < total) {
                long p = list != null ? list.pos(index) : clear[index];
                BlockData d = list != null ? list.data(index) : AIR;
                int x = BlockList.x(p), y = BlockList.y(p), z = BlockList.z(p);
                if (y >= world.getMinHeight() && y < world.getMaxHeight()) world.getBlockAt(x, y, z).setBlockData(d, false);
                index++;
                n++;
            }
            return Math.max(1, n);
        }
    }
}
