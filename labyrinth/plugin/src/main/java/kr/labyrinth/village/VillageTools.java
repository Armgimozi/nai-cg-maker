package kr.labyrinth.village;

import java.io.BufferedWriter;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.Future;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.data.BlockData;
import org.bukkit.command.CommandSender;

/** village dump · village pregen (VILLAGE.md §4.4). */
final class VillageTools {

    private VillageTools() {}

    /**
     * 마을 상자 + 16칸 여유 안 모든 비공기 블록 → plugins/Labyrinth/village/dump.txt ({@code x y z|blockdata}, render.py --dump).
     * 높이는 다듬은 땅 맨 아래 − 6 부터 (그 아래 돌은 생략).
     */
    static final class Dump extends VillageJob {
        private final World world;
        private final VillageMeta meta;
        private Scan.ChunkPump pump;
        private Scan.Snapshots snaps;
        private Future<Integer> future;
        private int x0, z0, x1, z1, y0, y1;
        private File out;

        Dump(VillageModule module, CommandSender sender, World world, VillageMeta meta) {
            super(module, sender, "마을 덤프");
            this.world = world;
            this.meta = meta;
        }

        @Override
        protected void begin() {
            x0 = Integer.MAX_VALUE;
            z0 = Integer.MAX_VALUE;
            x1 = Integer.MIN_VALUE;
            z1 = Integer.MIN_VALUE;
            y0 = Integer.MAX_VALUE;
            y1 = Integer.MIN_VALUE;
            for (VillageMeta.Box b : meta.protect) {
                x0 = Math.min(x0, b.x0());
                z0 = Math.min(z0, b.z0());
                x1 = Math.max(x1, b.x1());
                z1 = Math.max(z1, b.z1());
                y0 = Math.min(y0, b.y0());
                y1 = Math.max(y1, b.y1());
            }
            x0 -= 16;
            z0 -= 16;
            x1 += 16;
            z1 += 16;
            if (meta.terrain != null) y0 = Math.min(y0, meta.terrain.base() - 6);
            y0 = Math.max(world.getMinHeight(), y0);
            y1 = Math.min(world.getMaxHeight() - 1, y1 + 24);
            snaps = new Scan.Snapshots(world);
            pump = new Scan.ChunkPump(world, module.plugin(), false, false, 12, snaps::add).area(x0, z0, x1, z1);
            out = new File(module.plugin().getDataFolder(), "village/dump.txt");
            say("<gray>마을 덤프: x " + x0 + ".." + x1 + " · z " + z0 + ".." + z1 + " · y " + y0 + ".." + y1);
        }

        @Override
        protected String status() { return future == null ? "청크 " + pump.done + "/" + pump.total : "파일 쓰는 중"; }

        @Override
        protected boolean tick(Budget b) throws Exception {
            if (future == null) {
                pump.pump();
                if (!pump.finished()) return false;
                future = async().submit(this::write);
                return false;
            }
            if (!future.isDone()) return false;
            int n = future.get();
            say("<#7fe07f>덤프 완료</#7fe07f> <gray>블록 " + n + "개 → <white>" + out.getPath() + "</white> (render.py --dump)");
            snaps = null;
            return true;
        }

        private int write() throws Exception {
            out.getParentFile().mkdirs();
            int n = 0;
            try (BufferedWriter w = Files.newBufferedWriter(out.toPath(), StandardCharsets.UTF_8)) {
                for (int y = y0; y <= y1; y++) {
                    for (int z = z0; z <= z1; z++) {
                        for (int x = x0; x <= x1; x++) {
                            Material m = snaps.type(x, y, z);
                            if (m == null || m.isAir()) continue;
                            BlockData d = snaps.data(x, y, z);
                            w.write(x + " " + y + " " + z + "|" + d.getAsString());
                            w.newLine();
                            n++;
                        }
                    }
                }
            }
            return n;
        }
    }

    /** 중심 둘레 반경(블록) 안 청크를 비동기로 미리 생성 (동시 요청 8개, 진행률). */
    static final class Pregen extends VillageJob {
        private final World world;
        private final int cx, cz, radius;
        private Scan.ChunkPump pump;

        Pregen(VillageModule module, CommandSender sender, World world, int cx, int cz, int radius) {
            super(module, sender, "청크 미리 생성");
            this.world = world;
            this.cx = cx;
            this.cz = cz;
            this.radius = radius;
        }

        @Override
        protected void begin() {
            pump = new Scan.ChunkPump(world, module.plugin(), true, false, 8, c -> { }).area(cx - radius, cz - radius, cx + radius, cz + radius);
            say("<gray>청크 미리 생성: 중심 (" + cx + ", " + cz + ") 반경 " + radius + " · 청크 " + pump.total + "개");
        }

        @Override
        protected String status() { return "청크 " + pump.done + "/" + pump.total + " (" + pct(pump.progress()) + ")"; }

        @Override
        protected boolean tick(Budget b) {
            pump.pump();
            if (!pump.finished()) return false;
            say("<#7fe07f>청크 미리 생성 완료</#7fe07f> <gray>" + pump.done + "개 (" + elapsedSec() + "초" + (pump.failed > 0 ? ", 실패 " + pump.failed : "") + ")");
            return true;
        }
    }
}
