package kr.augsky.map;

import kr.augsky.AugSky;
import kr.augsky.augment.Tier;
import kr.augsky.map.MapBuilder.Isle;
import kr.augsky.map.MapBuilder.Region;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Biome;
import org.bukkit.command.CommandSender;
import org.bukkit.scheduler.BukkitRunnable;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import java.util.function.Consumer;
import java.util.function.IntConsumer;
import java.util.logging.Level;

/**
 * 하늘 네더: 플러그인이 만든 공허 네더 월드(NetherService)에 띄운 네더 섬 17곳과 제단 섬 6곳의 배치와 짓기.
 * 하늘 좌표의 1/8 이 네더 좌표라서 하늘 맵(반지름 약 610)은 네더의 쉼터 둘레 약 80 안에 들어온다.
 * 쉼터를 가운데 두고 기본 섬 → 요새·보루 같은 다음 단계 → 먼 섬(고대 잔해) 순으로 둘러싸고, 그 사이 빈자리에 제단 섬이 있다.
 * 섬 사이는 23~37칸이라 다리로 건넌다. 이름표·위치 안내는 없다. 배치는 굳혀 두었다 (LAYOUT).
 */
public final class NetherMap {
    public static final long SEED = 20261006L;
    /** 배치 판. 지은 월드에 기록한다. 바꾸면 지은 섬과 어긋나므로 새 판은 저절로 다시 짓지 않는다 (2: 제단 섬 6곳) */
    public static final int LAYOUT = 2;
    /** 쉼터 윗면 높이. 쉼터 문은 (0, 82~84, 0) */
    public static final int HUB_Y = 80;
    static final List<String> KINDS = List.of("n_hub", "n_quartz", "n_glow", "n_crimson", "n_warped", "n_soul", "n_delta",
            "n_fortress", "n_bastion", "n_ruin_portal", "n_lava", "n_debris", "n_stone");
    /** 이보다 긴 다리가 필요하면 징검다리 (지금 배치에는 없다. 배치를 고칠 때의 안전장치) */
    private static final double MAX_BRIDGE = 40;
    /** 섬 가장자리(반지름×1.3)에서 이만큼 바깥까지는 그 섬의 생물군계 (4칸 격자로 칠해지는 것까지 감안) */
    private static final double BIOME_MARGIN = 10;
    public static final List<Biome> BIOMES = List.of(Biome.NETHER_WASTES, Biome.CRIMSON_FOREST, Biome.WARPED_FOREST,
            Biome.SOUL_SAND_VALLEY, Biome.BASALT_DELTAS);

    private static final List<Isle> ISLES = layout(LAYOUT);

    private final AugSky plugin;

    public NetherMap(AugSky plugin) {
        this.plugin = plugin;
    }

    /** 판 v 의 섬 목록. 판마다 줄을 뒤에 덧붙이기만 해서 예전 섬은 자리도 시드도 그대로다. */
    private static List<Isle> layout(int v) {
        Object[][] t = {
                // 쉼터 둘레(약 50m): 기본 네더 재료
                {"n_hub", 0, 80, 0, 9.5}, {"n_crimson", 16, 82, -46, 11.5}, {"n_quartz", 47, 77, 6, 10.0},
                {"n_soul", 10, 76, 48, 12.0}, {"n_glow", -37, 88, 31, 8.0}, {"n_warped", -44, 84, -22, 11.5},
                // 다음 단계(85~95m): 요새, 삼각주, 보루, 무너진 문, 용암 호수
                {"n_fortress", 74, 74, -44, 14.0}, {"n_delta", 70, 71, 52, 11.0}, {"n_bastion", -24, 79, 92, 15.0},
                {"n_ruin_portal", -88, 90, 14, 8.0}, {"n_lava", -52, 75, -74, 10.0},
                // 먼 섬(100~128m): 기본 섬 한 벌 더와 고대 잔해
                {"n_crimson", 28, 86, -96, 11.0}, {"n_warped", -86, 82, 66, 11.0}, {"n_quartz", 104, 80, -4, 9.0},
                {"n_soul", 44, 72, 104, 11.0}, {"n_delta", -104, 70, -36, 10.0}, {"n_debris", 118, 68, 50, 13.0}};
        // 판 2: 제단 섬 여섯. 섬 사이 빈자리(가장자리끼리 20칸 넘게)에 방향을 돌려 가며, 등급마다 둘씩 쉼터 맞은편끼리 둔다.
        // 쉼터 가까이는 북쪽 한 곳뿐이라 그곳은 실버, 나머지는 바깥 둘레
        Object[][] altars = {
                {"n_altar", -11, 83, -80, 7.0, Tier.SILVER}, {"n_altar", 118, 78, -41, 7.0, Tier.GOLD},
                {"n_altar", 85, 72, 91, 7.0, Tier.PRISM}, {"n_altar", 8, 76, 124, 7.0, Tier.SILVER},
                {"n_altar", -119, 85, 38, 7.0, Tier.GOLD}, {"n_altar", -93, 73, -75, 7.0, Tier.PRISM}};
        List<Object[]> rows = new ArrayList<>(Arrays.asList(t));
        if (v >= 2) rows.addAll(Arrays.asList(altars));
        List<Isle> out = new ArrayList<>();
        for (int i = 0; i < rows.size(); i++) {
            Object[] row = rows.get(i);
            out.add(new Isle((String) row[0], (Integer) row[1], (Integer) row[2], (Integer) row[3], (Double) row[4],
                    Region.FLAME, row.length > 5 ? (Tier) row[5] : null, 7000 + i));
        }
        for (int round = 0; round < 20; round++) {
            int[] worst = {-1, -1};
            double max = Arrays.stream(MapBuilder.bridges(out, worst)).max().orElse(0);
            if (max <= MAX_BRIDGE) break;
            Isle a = out.get(worst[0]), b = out.get(worst[1]);
            double dx = b.x() - a.x(), dz = b.z() - a.z(), len = Math.hypot(dx, dz);
            double f = (a.r() + (len - a.r() - b.r()) / 2) / len;
            int x = (int) Math.round(a.x() + dx * f), z = (int) Math.round(a.z() + dz * f);
            out.add(new Isle("n_stone", x, (a.y() + b.y()) / 2, z, 3.5, Region.FLAME, null, 7500 + out.size()));
        }
        return List.copyOf(out);
    }

    public static List<Isle> plan() {
        return ISLES;
    }

    /** 예전 판으로 지은 월드를 검사할 때: 그 판의 섬만. */
    static List<Isle> plan(int layout) {
        return layout >= LAYOUT ? ISLES : layout(Math.max(1, layout));
    }

    static boolean isNether(String kind) {
        return kind.startsWith("n_");
    }

    static Biome biome(String kind) {
        return switch (kind) {
            case "n_crimson", "n_bastion" -> Biome.CRIMSON_FOREST;
            case "n_warped" -> Biome.WARPED_FOREST;
            case "n_soul" -> Biome.SOUL_SAND_VALLEY;
            case "n_delta", "n_debris" -> Biome.BASALT_DELTAS;
            default -> Biome.NETHER_WASTES;
        };
    }

    /**
     * (x, z) 의 생물군계: 가장 가까운 섬의 것, 섬에서 멀면 네더 황무지.
     * VoidNether 가 청크를 만들 때 다른 스레드에서도 부르므로 굳힌 목록만 읽는다.
     */
    public static Biome biomeAt(int x, int z) {
        Isle best = null;
        double bd = BIOME_MARGIN;
        for (Isle is : ISLES) {
            double d = Math.hypot(x - is.x(), z - is.z()) - is.r() * 1.3;
            if (d < bd) {
                bd = d;
                best = is;
            }
        }
        return best == null ? Biome.NETHER_WASTES : biome(best.kind());
    }

    /** 섬 밑동 깊이. 요새·보루는 무거운 건물을, 검은 바위는 깊이 묻힌 고대 잔해를 받친다. */
    static int depth(Isle is) {
        return switch (is.kind()) {
            case "n_hub" -> 10;
            case "n_fortress", "n_bastion" -> 15;
            case "n_debris" -> 20;
            case "n_stone" -> 3;
            default -> Math.max(5, (int) Math.round(is.r() * 1.1));
        };
    }

    /** 검사할 깊이: 발광석 처마는 밑에 매달린 발광석까지. */
    static int checkDepth(Isle is) {
        return depth(is) + (is.kind().equals("n_glow") ? 6 : 0);
    }

    /** 쉼터에 처음 서는 자리 (문을 바라본다). */
    public static Location hubSpawn(World w) {
        return new Location(w, 0.5, HUB_Y + 1, 3.5, 180, 0);
    }

    /** 배치 한 줄 요약 (관리자용). */
    public static String summary() {
        int stones = 0;
        int[] tiers = new int[Tier.values().length];
        for (Isle is : ISLES) {
            if (is.kind().equals("n_stone")) stones++;
            if (is.tier() != null) tiers[is.tier().ordinal()]++;
        }
        double longest = Arrays.stream(MapBuilder.bridges(ISLES, new int[2])).max().orElse(0);
        return "섬 " + ISLES.size() + "곳 (제단 " + tiers[0] + "/" + tiers[1] + "/" + tiers[2] + ", 징검다리 " + stones
                + "), 가장 긴 다리 " + Math.round(longest) + "m";
    }

    // ------------------------------------------------------------------ 짓기

    /**
     * 섬을 모두 짓는다. 섬 청크를 붙잡아 두고 엔티티까지 다 불려 온 뒤(다시 지을 때 옛 주민을 지워야 해서),
     * 한 틱에 섬 몇 개씩 짓는다. 다 지으면 done(실패한 섬 수). 섬 하나가 실패해도 나머지는 짓는다.
     * clear 면 섬 자리를 먼저 비운다 (다시 지을 때 처음 모습 그대로 되돌리려고).
     */
    public void buildAll(World w, boolean clear, Consumer<String> progress, IntConsumer done) {
        long t0 = System.currentTimeMillis();
        List<Isle> isles = plan();
        // 제단은 다시 세우면 새 엔티티(새 id)라서 기록을 비우고 새로 적는다. 쓴 제단도 처음처럼 빛난다
        plugin.altars().clearRegistry(w);
        Set<Long> held = hold(w, isles);
        NetherKinds kinds = new NetherKinds(plugin, w);
        new BukkitRunnable() {
            int waited, i, failed;
            boolean cleared;

            @Override
            public void run() {
                if (!cleared) {
                    // 엔티티는 청크와 따로(비동기로) 불려 온다. 덜 불려 온 채 지우면 옛 피글린이 남아 겹친다
                    if (!entitiesLoaded(w, held) && waited++ < 200) return;
                    for (Isle is : isles) kinds.clearResidents(is);
                    cleared = true;
                    return;
                }
                long until = System.currentTimeMillis() + 40;
                while (i < isles.size() && System.currentTimeMillis() < until) {
                    Isle is = isles.get(i++);
                    try {
                        if (clear) kinds.clear(is);
                        kinds.build(is, new Random(SEED ^ is.seed() * 31));
                    } catch (RuntimeException ex) {
                        failed++;
                        plugin.getLogger().log(Level.SEVERE, "네더 섬 " + is.kind() + " (" + is.x() + ", " + is.z() + ") 짓기 실패", ex);
                    }
                    if (progress != null && i % 6 == 0) progress.accept("네더 섬 " + i + " / " + isles.size());
                }
                if (i < isles.size()) return;
                cancel();
                // 새로 세운 제단은 청크가 다시 불릴 때까지 모르는 채로 남으니 지금 찾아 둔다 (보호, 반짝임)
                plugin.altars().scanLoaded();
                int f = failed;
                plugin.getLogger().log(f == 0 ? Level.INFO : Level.SEVERE, "하늘 네더 완성: " + summary() + ", 실패 " + f
                        + " (" + (System.currentTimeMillis() - t0) + "ms)");
                // 쉼터 문의 자리(POI)는 다음 틱에 기록되므로 청크를 한 틱 더 붙잡아 둔다
                Bukkit.getScheduler().runTask(plugin, () -> {
                    release(w, held);
                    done.accept(f);
                });
            }
        }.runTaskTimer(plugin, 1, 1);
    }

    private Set<Long> hold(World w, List<Isle> isles) {
        Set<Long> held = new HashSet<>();
        for (Isle is : isles) {
            int R = (int) Math.ceil(is.r() * 1.3) + 16;
            for (int qx = (is.x() - R) >> 4; qx <= (is.x() + R) >> 4; qx++)
                for (int qz = (is.z() - R) >> 4; qz <= (is.z() + R) >> 4; qz++) {
                    if (!held.add(((long) qx << 32) | (qz & 0xffffffffL))) continue;
                    w.getChunkAt(qx, qz);
                    w.addPluginChunkTicket(qx, qz, plugin);
                }
        }
        return held;
    }

    private static boolean entitiesLoaded(World w, Set<Long> held) {
        for (long k : held) if (!w.getChunkAt((int) (k >> 32), (int) k).isEntitiesLoaded()) return false;
        return true;
    }

    private void release(World w, Set<Long> held) {
        for (long k : held) w.removePluginChunkTicket((int) (k >> 32), (int) k, plugin);
    }

    /** /증강관리 섬 n_…: 네더 섬 하나를 지금 자리에 지어 본다 (모양 확인용). 없는 종류면 false. */
    public boolean buildKind(World w, String kind, int x, int y, int z, double rad) {
        if (!KINDS.contains(kind)) return false;
        double r = rad > 0 ? rad : 3.5;
        if (rad <= 0) {
            for (Isle is : ISLES) {
                if (is.kind().equals(kind)) {
                    r = is.r();
                    break;
                }
            }
        }
        Isle is = new Isle(kind, x, y, z, r, Region.FLAME, null, System.nanoTime());
        NetherKinds kinds = new NetherKinds(plugin, w);
        kinds.build(is, new Random(is.seed()));
        kinds.paintBiome(is, biome(kind), y);
        return true;
    }

    /** /증강관리 네더 검사: 섬마다 있어야 할 것이 있는지 센다. layout 은 이 월드를 지은 판 (그 판의 섬만 본다). */
    public void check(World w, CommandSender to, int layout) {
        new IslandCheck(plugin, w).run(plan(layout), to);
    }
}
