package kr.labyrinth.homes.rules;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicInteger;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.village.Nature;
import kr.labyrinth.village.VillageService;
import org.bukkit.Bukkit;
import org.bukkit.ChunkSnapshot;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.WorldBorder;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.type.Leaves;
import org.bukkit.command.CommandSender;
import org.bukkit.scheduler.BukkitTask;

/**
 * 옛 건물 조사 (0.3.7, plan §10 · review R14) — 지형 잠금이 처음 켜질 때 한 번 (+ {@code /labadmin plot legacy}). 소유: 묶음 B.
 * <p>
 * 국경 (WorldBorder) 안 청크를 {@code getChunkAtAsync} 로 불러 (새로 만들지 않음) 스냅샷을 비동기로 본다. 열마다 땅 위 + 땅속 10칸 (마을 Scan 과 같은 띠)
 * 의 사람 블록 (Nature UNNATURAL · 지속 잎) 을 세고, 집터·보호 칸 열은 뺀 뒤 8칸 안끼리 묶어 큰 것부터 20곳을
 * 로그와 {@code plugins/Labyrinth/homes/legacy.txt} 에 남긴다. 규칙에는 쓰지 않는다 (관리자가 convert 를 고를 때 봄).
 */
public final class LegacyScan {

    private static final int MAX_INFLIGHT = 6;
    private static final int UNDER = 10;
    private static final int TOP = 20;
    private static final int GROUP = 8;
    /** 국경이 이보다 크면 (기본 6천만) 마을 둘레 이 반경만. */
    private static final int FALLBACK_RADIUS = 256;

    private final HomesService s;
    private volatile boolean running;
    private BukkitTask task;

    public LegacyScan(HomesService s) { this.s = s; }

    public boolean running() { return running; }

    public File reportFile() { return new File(new File(s.plugin().getDataFolder(), "homes"), "legacy.txt"); }

    public void cancel() {
        if (task != null) task.cancel();
        task = null;
        running = false;
    }

    /** 조사 시작 (이미 돌면 false). report = 끝나면 알려 줄 사람 (null = 로그만). */
    public boolean start(CommandSender report) {
        if (running) return false;
        World w = s.mainWorld();
        if (w == null) return false;
        int[] area = area(w);
        ArrayDeque<int[]> queue = new ArrayDeque<>();
        for (int cx = area[0] >> 4; cx <= area[2] >> 4; cx++) for (int cz = area[1] >> 4; cz <= area[3] >> 4; cz++) queue.add(new int[] {cx, cz});
        int total = queue.size();
        running = true;
        ConcurrentLinkedQueue<LegacyClusters.Column> found = new ConcurrentLinkedQueue<>();
        AtomicInteger inflight = new AtomicInteger(), analysing = new AtomicInteger(), done = new AtomicInteger();
        int minY = w.getMinHeight(), maxY = w.getMaxHeight() - 1;
        if (report != null) Text.send(report, "<gray>옛 건물 조사 시작 — 청크 " + total + "개 (x " + area[0] + ".." + area[2] + " · z " + area[1] + ".." + area[3] + ")");
        task = Bukkit.getScheduler().runTaskTimer(s.plugin(), () -> {
            while (inflight.get() < MAX_INFLIGHT && !queue.isEmpty()) {
                int[] c = queue.poll();
                inflight.incrementAndGet();
                w.getChunkAtAsync(c[0], c[1], false).whenComplete((chunk, err) -> {
                    inflight.decrementAndGet();
                    done.incrementAndGet();
                    if (chunk == null || err != null) return;
                    ChunkSnapshot snap = chunk.getChunkSnapshot(true, false, false);
                    analysing.incrementAndGet();
                    Bukkit.getScheduler().runTaskAsynchronously(s.plugin(), () -> {
                        try {
                            analyse(snap, minY, maxY, area, found);
                        } finally {
                            analysing.decrementAndGet();
                        }
                    });
                });
            }
            if (queue.isEmpty() && inflight.get() == 0 && analysing.get() == 0) {
                if (task != null) task.cancel();
                task = null;
                finish(w, new ArrayList<>(found), total, report);
            }
        }, 1L, 1L);
        return true;
    }

    /** 조사 범위 [x0, z0, x1, z1]: 국경 안 (너무 크면 마을 스폰 둘레). */
    private int[] area(World w) {
        WorldBorder wb = w.getWorldBorder();
        double half = wb.getSize() / 2.0;
        Location c = wb.getCenter();
        if (half > 1024) {
            VillageService v = VillageService.get();
            Location sp = v == null ? null : v.spawn();
            if (sp == null) sp = w.getSpawnLocation();
            c = sp;
            half = FALLBACK_RADIUS;
        }
        return new int[] {(int) Math.floor(c.getX() - half), (int) Math.floor(c.getZ() - half), (int) Math.ceil(c.getX() + half),
                (int) Math.ceil(c.getZ() + half)};
    }

    /** 비동기: 열마다 사람 블록 수. */
    private static void analyse(ChunkSnapshot snap, int minY, int maxY, int[] area, ConcurrentLinkedQueue<LegacyClusters.Column> out) {
        int bx = snap.getX() << 4, bz = snap.getZ() << 4;
        for (int lx = 0; lx < 16; lx++) {
            for (int lz = 0; lz < 16; lz++) {
                int x = bx + lx, z = bz + lz;
                if (x < area[0] || x > area[2] || z < area[1] || z > area[3]) continue;
                int top = Math.min(maxY, snap.getHighestBlockYAt(lx, lz) + 1);
                int count = 0, firstY = Integer.MIN_VALUE, ground = Integer.MIN_VALUE;
                for (int y = top; y >= minY; y--) {
                    Material m = snap.getBlockType(lx, y, lz);
                    Nature.Kind k = Nature.kind(m.name());
                    if (k == Nature.Kind.GROUND) {
                        ground = y;
                        break;
                    }
                    if (human(k, snap, lx, y, lz)) {
                        count++;
                        if (firstY == Integer.MIN_VALUE) firstY = y;
                    }
                }
                if (ground != Integer.MIN_VALUE) {
                    for (int d = 1; d <= UNDER && ground - d >= minY; d++) {
                        Material m = snap.getBlockType(lx, ground - d, lz);
                        if (human(Nature.kind(m.name()), snap, lx, ground - d, lz)) {
                            count++;
                            if (firstY == Integer.MIN_VALUE) firstY = ground - d;
                        }
                    }
                }
                if (count > 0) out.add(new LegacyClusters.Column(x, z, count, firstY));
            }
        }
    }

    private static boolean human(Nature.Kind k, ChunkSnapshot snap, int lx, int y, int lz) {
        if (k == Nature.Kind.UNNATURAL) return true;
        if (k == Nature.Kind.LEAVES) {
            BlockData d = snap.getBlockData(lx, y, lz);
            return d instanceof Leaves l && l.isPersistent();
        }
        return false;
    }

    /** 메인 스레드: 집터·보호 칸을 빼고 묶어 보고. */
    private void finish(World w, List<LegacyClusters.Column> cols, int chunks, CommandSender report) {
        try {
            VillageService v = VillageService.get();
            List<LegacyClusters.Column> keep = new ArrayList<>();
            for (LegacyClusters.Column c : cols) {
                if (s.columnPlot(w, c.x(), c.z()) != null) continue;
                if (v != null && v.isProtected(w.getBlockAt(c.x(), c.y(), c.z()))) continue;
                keep.add(c);
            }
            List<LegacyClusters.Cluster> top = LegacyClusters.cluster(keep, GROUP, TOP);
            List<String> lines = new ArrayList<>();
            lines.add("# 미궁 라비린스 — 옛 건물 조사 (0.3.7) " + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")));
            lines.add("# 집터·마을 보호 칸 밖에서 사람이 놓은 블록 (땅 위 + 땅속 " + UNDER + "칸). 큰 것부터 " + TOP + "곳. 청크 " + chunks + "개를 봄.");
            lines.add("# 집터로 바꾸기: /labadmin plot convert <이름> <x1> <z1> <x2> <z2>  (가로·세로 32칸까지)");
            int i = 0;
            for (LegacyClusters.Cluster c : top) {
                i++;
                lines.add(i + ". x " + c.x0() + ".." + c.x1() + " · z " + c.z0() + ".." + c.z1() + " · 블록 " + c.blocks() + " · 가운데 (" + c.cx() + ", "
                        + c.y() + ", " + c.cz() + ")");
            }
            if (top.isEmpty()) lines.add("(없음)");
            File f = reportFile();
            try {
                f.getParentFile().mkdirs();
                Files.write(f.toPath(), lines, StandardCharsets.UTF_8);
            } catch (IOException e) {
                Log.warn("[집] legacy.txt 쓰기 실패: " + e.getMessage());
            }
            s.store().legacyScannedAt = System.currentTimeMillis();
            s.saveStore();
            Log.info("[집] 옛 건물 조사 끝 — 집터 밖 사람 블록 무리 " + top.size() + "곳" + (top.isEmpty() ? "" : " (큰 것: " + lines.get(3) + ")")
                    + " · plugins/Labyrinth/homes/legacy.txt");
            if (report != null) {
                Text.send(report, "<gray>옛 건물 조사 끝 — " + top.size() + "곳 (자세히: plugins/Labyrinth/homes/legacy.txt)");
                for (int k = 3; k < Math.min(lines.size(), 8); k++) Text.send(report, "<gray> " + Text.escape(lines.get(k)));
            }
        } finally {
            running = false;
        }
    }
}
