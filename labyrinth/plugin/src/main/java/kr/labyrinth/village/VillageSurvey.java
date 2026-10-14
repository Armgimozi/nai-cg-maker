package kr.labyrinth.village;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicInteger;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.CommandSender;

/**
 * {@code /labadmin village survey [반경]} (VILLAGE.md §4.4) — 시드 고르기용. 월드 스폰 둘레 후보 중심(8칸 간격) × 회전 4방향을
 * 계획기로 계산해 깎기·메우기 총량이 가장 적은 5곳을 알려 준다. 청크는 비동기로 불러 스냅샷만 읽고, 계산은 비동기 스레드.
 * 결과는 plugins/Labyrinth/village/survey.txt 에도 적는다 (조립 스크립트용).
 */
final class VillageSurvey extends VillageJob {

    private final World world;
    private final int radius;
    private int ox, oz;
    private TerrainGrid grid;
    private Scan.ChunkPump pump;
    private final AtomicInteger pending = new AtomicInteger();
    private final AtomicInteger progress = new AtomicInteger();
    private Future<Planner.SurveyResult> future;
    private int centers;

    VillageSurvey(VillageModule module, CommandSender sender, World world, int radius) {
        super(module, sender, "마을 자리 조사");
        this.world = world;
        this.radius = radius;
    }

    @Override
    protected void begin() {
        Location sp = world.getSpawnLocation();
        ox = sp.getBlockX();
        oz = sp.getBlockZ();
        int r = radius + module.library().planner.reach() + 2;
        grid = TerrainGrid.around(ox, oz, r);
        int steps = radius / 8;
        for (int j = -steps; j <= steps; j++) for (int i = -steps; i <= steps; i++) if (i * i + j * j <= steps * steps) centers++;
        int minY = world.getMinHeight(), maxY = world.getMaxHeight() - 1;
        pump = new Scan.ChunkPump(world, module.plugin(), true, false, 16, chunk -> {
            var snap = chunk.getChunkSnapshot(true, true, false, false);
            pending.incrementAndGet();
            async().execute(() -> {
                try {
                    Scan.columns(snap, grid, minY, maxY);
                } finally {
                    pending.decrementAndGet();
                }
            });
        }).area(ox - r, oz - r, ox + r, oz + r);
        say("<#c9a2ff>마을 자리 조사 시작</#c9a2ff> <gray>— 스폰 (" + ox + ", " + oz + ") 둘레 반경 " + radius + " · 후보 " + centers
                + "곳 × 4방향 · 청크 " + pump.total + "개");
    }

    @Override
    protected String status() {
        if (future == null) return "지형 불러오기 청크 " + pump.done + "/" + pump.total;
        return "계산 " + progress.get() + "/" + centers + "곳";
    }

    @Override
    protected boolean tick(Budget b) throws Exception {
        if (future == null) {
            pump.pump();
            if (!pump.finished() || pending.get() > 0) return false;
            Planner planner = module.library().planner;
            future = async().submit(() -> planner.survey(grid, ox, oz, radius, 8, 5, progress, () -> cancelled));
            return false;
        }
        if (!future.isDone()) return false;
        Planner.SurveyResult r = future.get();
        report(r);
        grid = null;
        return true;
    }

    private void report(Planner.SurveyResult r) {
        say("<#7fe07f><b>마을 자리 조사 결과</b></#7fe07f> <gray>(" + elapsedSec() + "초 · 후보 " + r.centers() + "곳 · 계획 " + r.plans() + "개)");
        List<String> lines = new ArrayList<>();
        lines.add("# village survey — 스폰 (" + ox + ", " + oz + ") 반경 " + radius + " · 순위 x z 방향 깎기 메우기 동굴메움 원목 바이옴 H0");
        if (r.best().isEmpty()) {
            say("<#ff6b6b>  지을 수 있는 자리가 없습니다.");
        }
        int rank = 0;
        for (Plan p : r.best()) {
            rank++;
            String dir = p.front().key();
            Text.send(sender, " <gold>" + rank + ".</gold> <white>(" + p.cx + ", " + p.cz + ") " + dir + "</white> <gray>깎기 <white>" + p.cut
                    + "</white> · 메우기 <white>" + p.fill + "</white> · 동굴 메움 " + p.caveFill + " · 원목 " + p.logs + " · " + Text.escape(p.biome)
                    + " · H0 " + p.h0 + "</gray>  <dark_gray>/labadmin village build " + p.cx + " " + p.cz + " " + dir);
            String line = rank + " " + p.cx + " " + p.cz + " " + dir + " " + p.cut + " " + p.fill + " " + p.caveFill + " " + p.logs + " " + p.biome + " " + p.h0;
            lines.add(line);
            Log.info("[마을 survey] " + line);
        }
        String rej = VillageBuilder.rejects(r.rejects());
        Text.send(sender, "<gray>  탈락 (자리×방향): " + Text.escape(rej));
        lines.add("# 탈락: " + rej);
        try {
            File f = new File(module.plugin().getDataFolder(), "village/survey.txt");
            f.getParentFile().mkdirs();
            Files.write(f.toPath(), lines, StandardCharsets.UTF_8);
        } catch (Exception e) {
            Log.warn("[마을] survey.txt 저장 실패: " + e.getMessage());
        }
    }
}
