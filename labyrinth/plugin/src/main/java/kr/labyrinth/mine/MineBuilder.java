package kr.labyrinth.mine;

import java.io.File;
import java.io.IOException;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.Biome;
import org.bukkit.block.Block;
import org.bukkit.block.Sign;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.sign.Side;
import org.bukkit.block.sign.SignSide;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitTask;

/**
 * 광산 층 짓기 (틱 분할). 층마다 두 가지:
 * <ul>
 *   <li><b>다시 짓기</b> — 청사진 부피(61×16×61)의 모든 칸을 청사진과 같게 (공허 칸 ' ' 은 공기로 치움), 표지판 글, 바이옴 띠.
 *       {@code <광산 월드>/labyrinth-mine.yml} 의 층 지문({@link MineLevel#hash})이 jar 와 다를 때만 (처음 켤 때 = 모든 층).
 *       그 층 사람은 승강장으로, 그 층 광맥 기록은 지운다.</li>
 *   <li><b>맞추기</b> — 지문이 같으면 광맥·보석 칸만 다 찬 블록으로 되돌린다 (재시작 = 모든 광맥이 다 찬 상태, 계약 §0-3).</li>
 * </ul>
 * 끝나면 보석 결정(ItemDisplay)을 다시 놓는다.
 */
final class MineBuilder {

    /** 틱당 시간 예산 (ns). */
    static final long TICK_NANOS = 25_000_000L;
    /** 틱당 칸 확인 수 · 블록 쓰기 수. */
    static final int CHECKS_PER_TICK = 60_000;
    static final int SETS_PER_TICK = 8_000;

    private final MineModule module;
    private BukkitTask task;
    private final List<Step> steps = new ArrayList<>();
    private int stepIndex;
    private final List<String> report = new ArrayList<>();
    private CommandSender sender;
    private Runnable done;
    private long startedAt;
    private int placed;

    private record Step(MineLevel level, boolean rebuild) {}

    MineBuilder(MineModule module) { this.module = module; }

    boolean running() { return task != null; }

    /** 층들을 짓기 시작 (rebuild 에 든 층은 다시 짓기, 나머지는 맞추기). */
    void start(List<MineLevel> levels, Set<Integer> rebuild, CommandSender who, Runnable onDone) {
        if (task != null) return;
        steps.clear();
        report.clear();
        for (MineLevel l : levels) steps.add(new Step(l, rebuild.contains(l.n)));
        stepIndex = 0;
        sender = who;
        done = onDone;
        startedAt = System.currentTimeMillis();
        placed = 0;
        cursor = 0;
        biomeCursor = -1;
        task = Bukkit.getScheduler().runTaskTimer(module.services().plugin(), this::tick, 1L, 1L);
    }

    void cancel() {
        if (task != null) task.cancel();
        task = null;
    }

    // ── 진행 ────────────────────────────────────────────────────────────

    private int cursor;
    private int biomeCursor;

    private void tick() {
        try {
            long deadline = System.nanoTime() + TICK_NANOS;
            int checks = 0, sets = 0;
            World w = module.world();
            if (w == null) {
                finish();
                return;
            }
            while (stepIndex < steps.size() && System.nanoTime() < deadline && checks < CHECKS_PER_TICK && sets < SETS_PER_TICK) {
                Step s = steps.get(stepIndex);
                MineLevel l = s.level();
                MineBlueprint bp = l.bp;
                if (s.rebuild()) {
                    int total = bp.w * bp.h * bp.d;
                    while (cursor < total && checks < CHECKS_PER_TICK && sets < SETS_PER_TICK) {
                        // 시간 검사는 칸을 고르기 전에 (끊긴 칸을 건너뛰지 않게)
                        if ((++checks & 255) == 0 && System.nanoTime() > deadline) break;
                        int x = cursor % bp.w;
                        int z = (cursor / bp.w) % bp.d;
                        int y = cursor / (bp.w * bp.d);
                        cursor++;
                        BlockData want = l.expected(bp.cell(x, y, z));
                        if (want == null) continue;
                        Block b = w.getBlockAt(bp.ox + x, bp.oy + y, bp.oz + z);
                        if (!b.getBlockData().equals(want)) {
                            b.setBlockData(want, false);
                            sets++;
                            placed++;
                        }
                    }
                    if (cursor < total) break;
                    if (biomeCursor < 0) biomeCursor = 0;
                    if (!biomes(w, l, deadline)) break;
                    signs(w, l);
                    finishLevel(w, l, true);
                } else {
                    sets += reconcile(w, l);
                    finishLevel(w, l, false);
                }
                stepIndex++;
                cursor = 0;
                biomeCursor = -1;
            }
            if (stepIndex >= steps.size()) finish();
        } catch (Throwable t) {
            Log.error("[광산] 짓기 오류", t);
            if (sender != null) Text.error(sender, "광산 짓기 중 오류: " + Text.escape(String.valueOf(t)));
            finish();
        }
    }

    /** 바이옴 띠: 층 상자 x·z (청크 16개) × 띠 y, 4칸 간격. @return 끝났으면 true */
    private boolean biomes(World w, MineLevel l, long deadline) {
        Biome biome = MineGenerator.biome(l.def.biome());
        if (biome == null || l.def.biomeY().size() != 2) return true;
        int lo = Math.max(w.getMinHeight(), l.def.biomeY().get(0));
        int hi = Math.min(w.getMaxHeight() - 1, l.def.biomeY().get(1));
        int nx = 16, nz = 16, ny = Math.max(0, (hi - lo) / 4 + 1);
        int total = nx * nz * ny;
        int n = 0;
        while (biomeCursor < total) {
            int i = biomeCursor++;
            int x = -32 + (i % nx) * 4;
            int z = -32 + ((i / nx) % nz) * 4;
            int y = lo + (i / (nx * nz)) * 4;
            w.setBiome(x, y, z, biome);
            if ((++n & 511) == 0 && System.nanoTime() > deadline) return biomeCursor >= total;
        }
        for (int cx = -2; cx <= 1; cx++) for (int cz = -2; cz <= 1; cz++) w.refreshChunk(cx, cz);
        return true;
    }

    private void signs(World w, MineLevel l) {
        for (MineBlueprint.Marker m : l.bp.markers("sign")) {
            Block b = w.getBlockAt(m.bx(), m.by(), m.bz());
            if (!(b.getState() instanceof Sign sign)) continue;
            SignSide side = sign.getSide(Side.FRONT);
            for (int i = 0; i < 4; i++) {
                String line = i < m.lines().size() ? m.lines().get(i) : "";
                side.line(i, Text.mm(i == 0 ? "<b>" + Text.escape(line) : Text.escape(line)));
            }
            sign.setWaxed(true);
            sign.update(true, false);
        }
    }

    /** 광맥·보석 칸만 다 찬 블록으로. @return 바꾼 칸 수 */
    private int reconcile(World w, MineLevel l) {
        int n = 0;
        List<MineLevel.Vein> all = new ArrayList<>(l.veins);
        all.addAll(l.gems);
        for (MineLevel.Vein v : all) {
            Block b = w.getBlockAt(v.x(), v.y(), v.z());
            if (!b.getBlockData().equals(v.full())) {
                b.setBlockData(v.full(), false);
                n++;
            }
        }
        return n;
    }

    private void finishLevel(World w, MineLevel l, boolean rebuilt) {
        module.veins().clearLevel(l.n);
        if (rebuilt) {
            for (Player p : w.getPlayers()) {
                if (l.containsY(p.getLocation().getY())) {
                    kr.labyrinth.core.Teleports.to(p, l.landing(w));
                    Text.send(p, "<gray>" + l.coloredName() + "<gray> 을(를) 새로 지어 승강장으로 옮겼습니다.");
                }
            }
            report.add(l.n + "층 다시 지음");
            module.markBuilt(l);
        } else {
            module.markBuilt(l);
        }
        module.veins().respawnDisplays(l);
    }

    private void finish() {
        cancel();
        long ms = System.currentTimeMillis() - startedAt;
        saveMeta();
        String msg = "[광산] 층 " + steps.size() + "개 준비 (" + (report.isEmpty() ? "광맥을 다 찬 상태로" : String.join(", ", report))
                + ", 블록 " + placed + "칸, " + ms + "ms)";
        Log.info(msg);
        if (sender != null && !(sender instanceof org.bukkit.command.ConsoleCommandSender)) Text.send(sender, "<gray>" + Text.escape(msg));
        Runnable r = done;
        done = null;
        if (r != null) r.run();
    }

    // ── 메타 (층 지문) ──────────────────────────────────────────────────

    static File metaFile(World w) { return new File(w.getWorldFolder(), MineNames.WORLD_META); }

    /** 저장된 층 지문 (층 → hash). */
    static java.util.Map<Integer, String> readMeta(World w) {
        java.util.Map<Integer, String> out = new java.util.HashMap<>();
        File f = metaFile(w);
        if (!f.isFile()) return out;
        YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
        var sec = y.getConfigurationSection("levels");
        if (sec == null) return out;
        for (String k : sec.getKeys(false)) {
            try {
                out.put(Integer.parseInt(k), sec.getString(k + ".hash", ""));
            } catch (NumberFormatException ignored) {
                // 모르는 키
            }
        }
        return out;
    }

    void saveMeta() {
        World w = module.world();
        if (w == null) return;
        YamlConfiguration y = new YamlConfiguration();
        y.options().setHeader(List.of("미궁 라비린스 광산 — 층마다 지은 청사진 지문 (plugin 이 씀, 고치지 마세요).",
                "지문이 jar 와 다른 층만 다시 짓습니다. 지우면 다음 시작 때 모든 층을 다시 짓습니다."));
        y.set("format", 1);
        y.set("plugin", module.services().plugin().getPluginMeta().getVersion());
        for (MineLevel l : module.levels()) {
            String built = module.builtHash(l.n);
            if (built == null) continue;
            y.set("levels." + l.n + ".id", l.def.id());
            y.set("levels." + l.n + ".hash", built);
            y.set("levels." + l.n + ".blueprint", l.bp.sha1.substring(0, 16));
        }
        y.set("saved_at", OffsetDateTime.now(ZoneOffset.UTC).toString());
        try {
            y.save(metaFile(w));
        } catch (IOException e) {
            Log.warn("[광산] " + MineNames.WORLD_META + " 저장 실패: " + e.getMessage());
        }
    }
}
