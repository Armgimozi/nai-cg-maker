package kr.labyrinth.dungeon;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.EnumMap;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.dungeon.gen.FloorGenerator;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.gen.HallStyle;
import kr.labyrinth.dungeon.gen.MazePlan;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;

/**
 * 층 배치 덤프 (눈으로 확인용 — 평소 빌드에선 건너뜀). {@code MAZE_DUMP=<폴더> [MAZE_SEEDS=1,2,3] ./gradlew test --tests '*MazeRenderDump*'}
 * → 폴더에 floorNN_sS.txt (타일 문자 지도 + 주 경로·막다른 길·비밀방 목록). PNG 는 {@code labyrinth/tools/maze_render.py}.
 * <p>
 * 문자: ' ' 빈칸 · 0~3 복도 바닥(높이) · '/' 계단 · '~' 도랑 · 'X' 금 간 벽 · 's' 비밀방 · 'D' 출입구 ·
 * 방 내부 S 시작 C 전투 E 정예 T 보물 G 시련 R 휴식 B 보스.
 */
class MazeRenderDump {

    @Test
    @EnabledIfEnvironmentVariable(named = "MAZE_DUMP", matches = ".+")
    void dump() throws IOException {
        Path out = Path.of(System.getenv("MAZE_DUMP"));
        Files.createDirectories(out);
        String seedsEnv = System.getenv().getOrDefault("MAZE_SEEDS", "1");
        Content content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        StringBuilder summary = new StringBuilder();
        for (String sd : seedsEnv.split(",")) {
            long seed = Long.parseLong(sd.trim());
            for (FloorDef f : content.floors().values()) {
                var boss = content.bossOfFloor(f.number());
                var arena = boss == null ? kr.labyrinth.content.Params.EMPTY : boss.arena();
                boolean liquid = f.liquid() != null && !f.liquid().isBlank() && !"null".equalsIgnoreCase(f.liquid());
                FloorGenerator.Params gp = override(Run.params(f, arena, liquid));
                long t0 = System.nanoTime();
                FloorLayout l = FloorGenerator.generate(gp, seed * 1_000_003L + f.number() * 7919L);
                long us = (System.nanoTime() - t0) / 1000;
                Path file = System.getenv("MAZE_NOTILES") != null ? null : out.resolve(String.format("floor%02d_s%d.txt", f.number(), seed));
                String stats = write(file, l, us);
                summary.append(String.format("floor %2d seed %d: %s%n", f.number(), seed, stats));
            }
        }
        Files.writeString(out.resolve("summary.txt"), summary.toString(), StandardCharsets.UTF_8);
    }

    /** 실험용: MAZE_OVERRIDE="branch=0.6,loop_chance=0.25" 로 모든 층 maze 값 덮어쓰기. */
    private static FloorGenerator.Params override(FloorGenerator.Params p) {
        String o = System.getenv("MAZE_OVERRIDE");
        if (o == null || o.isBlank()) return p;
        var m = p.maze();
        double keep = m.deadEndKeep(), loop = m.loopChance(), branch = m.branch(), braid = m.braid(), twist = m.twist(), sr = m.secretRatio();
        for (String kv : o.split(",")) {
            String[] a = kv.split("=");
            double v = Double.parseDouble(a[1]);
            switch (a[0].trim()) {
                case "dead_end_keep" -> keep = v;
                case "loop_chance" -> loop = v;
                case "branch" -> branch = v;
                case "braid" -> braid = v;
                case "twist" -> twist = v;
                case "secret_ratio" -> sr = v;
                default -> { }
            }
        }
        var ms = new kr.labyrinth.dungeon.gen.MazeGenerator.Settings(keep, loop, branch, braid, twist, sr, m.secretMax(), m.minPath());
        return new FloorGenerator.Params(p.cells(), p.rooms(), p.roomHeight(), p.hallHeight(), p.liquid(), p.arenaRadius(),
                p.arenaHeight(), p.arenaCorridorLength(), p.arenaCorridorWidth(), ms);
    }

    private static String write(Path file, FloorLayout l, long micros) throws IOException {
        MazePlan plan = l.plan();
        StringBuilder sb = new StringBuilder();
        sb.append(l.width()).append(' ').append(l.depth()).append(' ').append(plan.size()).append(' ')
                .append(FloorGenerator.MARGIN_X).append(' ').append(FloorGenerator.MARGIN_Z).append(' ').append(FloorGenerator.PITCH).append('\n');
        for (int z = 0; z < l.depth(); z++) {
            for (int x = 0; x < l.width(); x++) sb.append(ch(l, x, z));
            sb.append('\n');
        }
        sb.append("PATH");
        for (int c : plan.mainPath()) sb.append(' ').append(c);
        sb.append('\n');
        for (FloorLayout.DeadEnd d : l.deadEnds()) {
            sb.append("DEAD ").append(d.tipX()).append(' ').append(d.tipZ()).append(' ').append(d.dirX()).append(' ').append(d.dirZ())
                    .append(' ').append(d.secret()).append(' ').append(d.minor() ? 1 : 0).append('\n');
        }
        for (FloorLayout.SecretRoom s : l.secretRooms()) {
            sb.append("SECRET ").append(s.minX()).append(' ').append(s.minZ()).append(' ').append(s.maxX()).append(' ').append(s.maxZ()).append('\n');
        }
        long blocks = 0;
        for (int z = 0; z < l.depth(); z++) for (int x = 0; x < l.width(); x++) if (l.open(x, z)) blocks += 2 + l.elevation(x, z);
        Map<HallStyle, Integer> styles = new EnumMap<>(HallStyle.class);
        for (int c = 0; c < plan.cellCount(); c++) if (plan.style(c) != null) styles.merge(plan.style(c), 1, Integer::sum);
        String stats = "n=" + plan.size() + " used=" + plan.usedCount() + "/" + plan.cellCount() + " path=" + plan.mainPath().size()
                + " need=" + (int) Math.ceil(2.2 * plan.size()) + " loops=" + plan.loopCount() + " dead=" + plan.deadEnds().size()
                + "/" + plan.initialDeadEnds() + " secrets=" + l.secretRooms().size() + " hallTiles=" + l.hallTiles().length
                + " attempt=" + plan.attempt() + " openTiles~blocks=" + blocks + " gen=" + micros + "us styles=" + styles;
        sb.append("STAT ").append(stats).append('\n');
        sb.append("ASCII\n").append(plan.ascii());
        if (file != null) Files.writeString(file, sb.toString(), StandardCharsets.UTF_8);
        return stats;
    }

    private static char ch(FloorLayout l, int x, int z) {
        byte k = l.kind(x, z);
        switch (k) {
            case FloorLayout.VOID: return ' ';
            case FloorLayout.DOOR: return 'D';
            case FloorLayout.GUTTER: return '~';
            case FloorLayout.STAIR: return '/';
            case FloorLayout.SECRET: return 'X';
            default: break;
        }
        int r = l.region(x, z);
        if (r < 0) return l.secretRoomAt(x, z) >= 0 ? 's' : (char) ('0' + Math.min(9, l.elevation(x, z)));
        return switch (l.room(r).type()) {
            case START -> 'S';
            case COMBAT -> 'C';
            case ELITE -> 'E';
            case TREASURE -> 'T';
            case GIMMICK -> 'G';
            case REST -> 'R';
            case BOSS -> 'B';
            case HALL -> '0';
        };
    }
}
