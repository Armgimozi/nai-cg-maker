package kr.augsky.map;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.augment.Tier;
import org.bukkit.GameRule;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.TreeType;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.type.EndPortalFrame;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Interaction;
import org.bukkit.entity.Marker;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.util.Transformation;
import org.joml.AxisAngle4f;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;
import java.util.function.Consumer;
import java.util.logging.Level;

/**
 * 맵 전체를 짓는다. 빈 공허 월드에서 /증강관리 맵생성 을 한 번 실행하면 된다.
 * 배포용 맵 파일은 이 코드로 지은 월드를 그대로 묶은 것이다.
 *
 * 반지름 약 610m, 섬 약 130개. 가운데 초원(반지름 175m)을 서리(서)·화염(동북)·공허(북서)·바다(남)·야생이 둘러싼다.
 * 섬마다 모습과 재료가 다르고, 위치 안내판·빛기둥은 없다.
 * 제단 18곳(실버 10, 골드 6, 프리즘 2)은 맵 전체에 고르게 흩어져 있고 등급은 거리와 상관없이 섞여 있다
 * (하늘 네더에도 6곳, NetherMap). 한 번 쓰면 힘을 잃고, 각 지역 끝의 둥지에는 보스가 산다.
 * 같은 시드로 지으면 언제나 같은 맵이 나온다.
 */
public final class MapBuilder extends MapTools {
    public record Place(String name, int x, int y, int z) {}

    /** 큰 장소. 맵을 지을 때만 쓴다. */
    public static final List<Place> PLACES = List.of(
            new Place("시작의 섬", 0, 64, 0),
            new Place("서리 균열", -370, 62, 111),
            new Place("서리 군주의 둥지", -449, 62, 137),
            new Place("화염 균열", 332, 58, -228),
            new Place("화염 거신의 둥지", 397, 56, -275),
            new Place("공허 균열", -292, 98, -349),
            new Place("공허 군주의 둥지", -338, 104, -415),
            new Place("끝의 섬", 494, 72, 323)
    );

    public enum Region { PLAINS, FROST, FLAME, VOID, OCEAN, WILD }

    /** 지을 섬 하나. */
    record Isle(String kind, int x, int y, int z, double r, Region region, Tier tier, long seed) {}

    /** 자원 섬 묶음: 종류, 지역, 시작 섬에서 떨어진 거리(m), 개수, 반지름. */
    record Spot(String kind, Region region, double rMin, double rMax, int count, double sMin, double sMax) {}

    private static final long SEED = 20261005L;
    /** 초원(가운데 지역)의 반지름 */
    private static final double PLAINS_R = 175;
    /** 이보다 긴 다리가 필요하면 가운데에 징검다리 바위를 놓는다 */
    private static final double MAX_BRIDGE = 80;
    /**
     * 제단 18곳의 등급, 시작 섬에서 가까운 순서. 등급을 거리로 나누지 않고 섞었다: 가장 가까운 제단은 실버,
     * 250m 안·250~420m·그 밖마다 실버와 골드가 있고, 골드끼리는 400m 넘게, 프리즘 둘은 서로 다른 지역 맞은편에.
     */
    private static final String ALTAR_TIERS = "SGSSSSSGPSGGPGSSSG";
    /** 제단을 흩는 거리 범위(m)와 첫 제단의 방위(북쪽에서 시계 방향, 도). 방위는 큰 장소를 피하고 지역마다 제단이 들도록 골랐다 */
    private static final double ALTAR_NEAR = 100, ALTAR_FAR = 580, ALTAR_TURN = 74;

    /**
     * 자원 섬을 놓는 순서. 위에서부터 하나씩 빈자리에 놓으므로 순서를 바꾸면 맵 전체가 바뀐다.
     * 가까운 초원에는 기본 재료, 바깥 지역에는 그 지역만의 재료가 나는 섬. 두 번째 묶음은 더 먼 곳에 하나 더.
     */
    static final List<Spot> DECK = List.of(
            spot("woods", Region.PLAINS, 60, 170, 2, 6, 8.5), spot("mine", Region.PLAINS, 90, 170, 1, 7, 8.5),
            spot("ranch", Region.PLAINS, 90, 170, 1, 7, 8.5), spot("farm", Region.PLAINS, 60, 130, 1, 6.5, 8),
            spot("pond", Region.PLAINS, 60, 170, 2, 5.5, 7), spot("pumpkin", Region.PLAINS, 90, 170, 1, 5, 6.5),
            spot("meadow", Region.PLAINS, 90, 170, 1, 6, 7.5), spot("mushroom", Region.PLAINS, 100, 170, 1, 5.5, 7),
            spot("desert", Region.PLAINS, 110, 172, 2, 7, 9), spot("spider_den", Region.PLAINS, 120, 172, 1, 6.5, 8),

            spot("taiga", Region.FROST, 180, 320, 1, 6.5, 8.5), spot("frozen_lake", Region.FROST, 180, 320, 1, 7, 9),
            spot("frost_mine", Region.FROST, 250, 380, 1, 7.5, 9), spot("igloo", Region.FROST, 280, 420, 1, 6, 7.5),
            spot("taiga", Region.FROST, 320, 620, 2, 6.5, 8.5), spot("frozen_lake", Region.FROST, 320, 560, 1, 7, 9),
            spot("frost_mine", Region.FROST, 380, 620, 1, 7.5, 9), spot("icespike", Region.FROST, 300, 620, 2, 6.5, 8.5),

            spot("basalt", Region.FLAME, 190, 320, 1, 6.5, 8.5), spot("crimson", Region.FLAME, 190, 320, 1, 6.5, 8),
            spot("soul_valley", Region.FLAME, 190, 330, 1, 6.5, 8), spot("volcano", Region.FLAME, 220, 350, 1, 7, 9),
            spot("fortress", Region.FLAME, 260, 380, 1, 7, 8.5), spot("nether_vein", Region.FLAME, 260, 400, 1, 7, 9),
            spot("basalt", Region.FLAME, 320, 620, 1, 6.5, 8.5), spot("crimson", Region.FLAME, 320, 620, 1, 6.5, 8),
            spot("soul_valley", Region.FLAME, 330, 620, 1, 6.5, 8), spot("volcano", Region.FLAME, 350, 620, 1, 7, 9),
            spot("fortress", Region.FLAME, 380, 620, 1, 7, 8.5), spot("nether_vein", Region.FLAME, 400, 620, 1, 7, 9),
            spot("warped", Region.FLAME, 350, 620, 1, 6, 7.5),

            spot("chorus", Region.VOID, 190, 320, 1, 6.5, 8.5), spot("geode", Region.VOID, 250, 620, 2, 7, 8.5),
            spot("obsidian_spire", Region.VOID, 260, 400, 1, 6, 7.5), spot("chorus", Region.VOID, 320, 620, 2, 6.5, 8.5),
            spot("purpur_ruin", Region.VOID, 330, 620, 2, 6.5, 8), spot("obsidian_spire", Region.VOID, 400, 620, 1, 6, 7.5),

            spot("beach", Region.OCEAN, 180, 300, 1, 6.5, 8.5), spot("lagoon", Region.OCEAN, 190, 330, 1, 8, 9.5),
            spot("copper_cove", Region.OCEAN, 190, 320, 1, 7, 9), spot("prismarine_ruin", Region.OCEAN, 260, 420, 1, 7, 8.5),
            spot("beach", Region.OCEAN, 300, 600, 2, 6.5, 8.5), spot("lagoon", Region.OCEAN, 330, 600, 1, 8, 9.5),
            spot("copper_cove", Region.OCEAN, 320, 600, 1, 7, 9), spot("prismarine_ruin", Region.OCEAN, 420, 620, 1, 7, 8.5),
            spot("shipwreck", Region.OCEAN, 350, 620, 1, 6.5, 8),

            spot("geode", Region.WILD, 190, 320, 1, 7, 8.5), spot("jungle", Region.WILD, 180, 320, 1, 7, 8.5),
            spot("swamp", Region.WILD, 180, 330, 1, 7, 8.5), spot("badlands", Region.WILD, 190, 350, 1, 7, 9),
            spot("savanna", Region.WILD, 180, 400, 1, 6.5, 8), spot("lush_cave", Region.WILD, 200, 380, 1, 7, 8.5),
            spot("mountain", Region.WILD, 220, 400, 1, 7.5, 9), spot("deep_mine", Region.WILD, 220, 330, 1, 7.5, 9),
            spot("spider_den", Region.WILD, 200, 450, 1, 6.5, 8), spot("dark_forest", Region.WILD, 250, 500, 1, 6.5, 8),
            spot("jungle", Region.WILD, 320, 620, 1, 7, 8.5), spot("badlands", Region.WILD, 350, 620, 1, 7, 9),
            spot("mountain", Region.WILD, 400, 620, 1, 7.5, 9), spot("deep_mine", Region.WILD, 420, 620, 1, 7.5, 9),
            spot("cherry", Region.WILD, 300, 620, 1, 6, 7.5), spot("ruin", Region.WILD, 300, 620, 1, 6, 7.5)
    );

    public MapBuilder(AugSky plugin) {
        super(plugin);
    }

    private static Spot spot(String kind, Region g, double rMin, double rMax, int n, double sMin, double sMax) {
        return new Spot(kind, g, rMin, rMax, n, sMin, sMax);
    }

    public static Place place(String name) {
        for (Place p : PLACES) if (p.name().equals(name)) return p;
        return null;
    }

    /** /증강관리 섬 탭 완성용 섬 종류 (하늘 섬과 하늘 네더 섬 n_…). */
    public static List<String> kinds() {
        List<String> all = new ArrayList<>(IslandKinds.KINDS);
        all.addAll(NetherMap.KINDS);
        return all;
    }

    /** 지역: 가운데는 초원, 바깥은 방향에 따라 나뉜다. */
    public static Region region(double x, double z) {
        double r = Math.hypot(x, z);
        if (r < PLAINS_R) return Region.PLAINS;
        double b = Math.toDegrees(Math.atan2(x, -z));
        if (b < 0) b += 360;
        if (b >= 300) return Region.VOID;
        if (b >= 222) return Region.FROST;
        if (b >= 140) return Region.OCEAN;
        if (b >= 30 && b < 125) return Region.FLAME;
        return Region.WILD;
    }

    private static int baseY(Region g, double x, double z, Random rnd) {
        double r = Math.hypot(x, z);
        return switch (g) {
            case PLAINS -> 64 + rnd.nextInt(9) - 4;
            case FROST -> 62 + rnd.nextInt(9) - 4;
            case FLAME -> 57 + rnd.nextInt(9) - 4;
            // 공허는 멀어질수록 높이 떠 있다
            case VOID -> (int) (66 + Math.min(34, Math.max(0, r - PLAINS_R) * 0.1)) + rnd.nextInt(7) - 3;
            case OCEAN -> 60 + rnd.nextInt(5) - 2;
            case WILD -> 68 + rnd.nextInt(11) - 5;
        };
    }

    // ------------------------------------------------------------------ 배치

    public static List<Isle> plan() {
        return plan(new ArrayList<>());
    }

    /**
     * 섬 목록을 만든다. 큰 장소와 제단을 먼저 놓고, DECK 순서대로 자원 섬을 놓은 뒤, 다리가 너무 길어지는 곳에 징검다리를 놓는다.
     * 난수를 쓰는 순서까지 맵의 일부라서 순서를 바꾸면 안 된다. 놓지 못한 것은 warn 에 적는다.
     */
    static List<Isle> plan(List<String> warn) {
        Random rnd = new Random(SEED);
        List<Isle> out = new ArrayList<>();
        out.add(new Isle("start", 0, 64, 0, 6, Region.PLAINS, null, 1));
        // 시작 섬 둘레 약 50m 의 세 섬: 나무, 돌과 쇠, 동물. 처음 놓는 다리는 이 셋 중 하나로 간다
        out.add(new Isle("woods", 17, 66, -47, 7, Region.PLAINS, null, 11));
        out.add(new Isle("mine", -44, 63, 24, 7.5, Region.PLAINS, null, 12));
        out.add(new Isle("ranch", 40, 65, 30, 7.5, Region.PLAINS, null, 13));

        String[][] big = {{"rift_frost", "서리 균열"}, {"lair_frost", "서리 군주의 둥지"}, {"rift_flame", "화염 균열"},
                {"lair_flame", "화염 거신의 둥지"}, {"rift_void", "공허 균열"}, {"lair_void", "공허 군주의 둥지"}, {"end", "끝의 섬"}};
        for (int i = 0; i < big.length; i++) {
            Place p = place(big[i][1]);
            double r = big[i][0].startsWith("lair_") ? 18 : big[i][0].startsWith("rift_") ? 11 : 7.5;
            out.add(new Isle(big[i][0], p.x(), p.y(), p.z(), r, region(p.x(), p.z()), null, 40 + i));
        }

        altars(out, rnd, warn);

        for (Spot s : DECK) for (int k = 0; k < s.count(); k++) place(out, rnd, s, warn);
        stones(out, warn);
        return out;
    }

    /**
     * 제단: 해바라기 씨처럼 황금각(약 137.5°)씩 돌면서 거리는 넓이에 맞춰 늘려 맵 전체에 고르게 흩는다.
     * 등급은 ALTAR_TIERS 순서라 거리와 상관없이 섞인다. 자리가 막히면 같은 거리에서 2°씩 좌우로 돌려 본다.
     */
    private static void altars(List<Isle> out, Random rnd, List<String> warn) {
        int n = ALTAR_TIERS.length();
        double golden = 180 * (3 - Math.sqrt(5));
        for (int i = 0; i < n; i++) {
            Tier tier = switch (ALTAR_TIERS.charAt(i)) {
                case 'G' -> Tier.GOLD;
                case 'P' -> Tier.PRISM;
                default -> Tier.SILVER;
            };
            double r = Math.sqrt(ALTAR_NEAR * ALTAR_NEAR + (double) i / (n - 1) * (ALTAR_FAR * ALTAR_FAR - ALTAR_NEAR * ALTAR_NEAR));
            boolean ok = false;
            for (int k = 0; k <= 20 && !ok; k++) {
                int turn = (k + 1) / 2 * 2 * (k % 2 == 1 ? 1 : -1);
                double a = Math.toRadians(ALTAR_TURN + i * golden + turn);
                int x = (int) Math.round(Math.sin(a) * r), z = (int) Math.round(-Math.cos(a) * r);
                if (!altarRoom(out, x, z)) continue;
                Region g = region(x, z);
                out.add(new Isle("altar", x, baseY(g, x, z, rnd), z, 7, g, tier, 100 + out.size()));
                ok = true;
            }
            if (!ok) warn.add("맵 배치: " + tier.korean + " 제단 " + (i + 1) + "번째를 놓을 자리가 없습니다");
        }
    }

    /**
     * 제단 자리: 다른 제단에서 180m, 시작 섬 둘레에서 40m, 큰 장소(균열, 둥지, 끝의 섬) 가장자리에서 90m.
     * 균열 몬스터와 보스가 제단까지 오지 않고, 제단이 따로 찾아갈 곳이 되게 큰 장소에서는 넉넉히 뗀다.
     */
    private static boolean altarRoom(List<Isle> out, int x, int z) {
        for (Isle i : out) {
            boolean big = i.kind().startsWith("rift_") || i.kind().startsWith("lair_") || i.kind().equals("end");
            double need = i.tier() != null ? 180 : i.r() + (big ? 90 : 40);
            if (Math.hypot(i.x() - x, i.z() - z) < need) return false;
        }
        return true;
    }

    /** 자원 섬 하나: 거리 범위 안에서 그 지역이면서 다른 섬과 충분히 떨어진 첫 자리. */
    private static void place(List<Isle> out, Random rnd, Spot s, List<String> warn) {
        for (int t = 0; t < 3000; t++) {
            double a = rnd.nextDouble(Math.PI * 2);
            double r = Math.sqrt(rnd.nextDouble(s.rMin() * s.rMin(), s.rMax() * s.rMax()));
            int x = (int) Math.round(Math.sin(a) * r), z = (int) Math.round(-Math.cos(a) * r);
            if (region(x, z) != s.region()) continue;
            double size = s.sMin() + rnd.nextDouble() * (s.sMax() - s.sMin());
            // 초원은 조금 촘촘하게, 바깥 지역은 더 띄엄띄엄
            double gap = s.region() == Region.PLAINS ? 30 : 42;
            if (!free(out, x, z, size, gap)) continue;
            out.add(new Isle(s.kind(), x, baseY(s.region(), x, z, rnd), z, size, s.region(), null, 1000 + out.size()));
            return;
        }
        warn.add("맵 배치: " + s.kind() + " 섬을 놓을 자리가 없습니다");
    }

    /** 모든 섬을 잇는 가장 짧은 다리들 중 MAX_BRIDGE 보다 긴 것이 없어질 때까지 가운데에 바위를 놓는다. */
    private static void stones(List<Isle> out, List<String> warn) {
        for (int round = 0; round < 60; round++) {
            int[] worst = worstBridge(out);
            if (worst == null) return;
            Isle a = out.get(worst[0]), b = out.get(worst[1]);
            double dx = b.x() - a.x(), dz = b.z() - a.z(), len = Math.hypot(dx, dz);
            double t = (a.r() + (len - a.r() - b.r()) / 2) / len;
            int x = (int) Math.round(a.x() + dx * t), z = (int) Math.round(a.z() + dz * t);
            out.add(new Isle("stone", x, (a.y() + b.y()) / 2, z, 3.5, region(x, z), null, 5000 + out.size()));
        }
        warn.add("맵 배치: 징검다리를 60개 놓아도 " + (int) MAX_BRIDGE + "m 보다 긴 다리가 남았습니다");
    }

    /** 가장자리 사이 거리. */
    private static double gap(Isle a, Isle b) {
        return Math.max(0, Math.hypot(a.x() - b.x(), a.z() - b.z()) - a.r() - b.r());
    }

    /** 최소 신장 트리(프림)의 다리 길이들. worst 에는 가장 긴 다리의 두 섬 번호. */
    static double[] bridges(List<Isle> out, int[] worst) {
        int n = out.size();
        boolean[] in = new boolean[n];
        double[] key = new double[n];
        int[] par = new int[n];
        Arrays.fill(key, 1e18);
        key[0] = 0;
        par[0] = -1;
        double[] edges = new double[n - 1];
        double max = 0;
        for (int k = 0; k < n; k++) {
            int u = -1;
            for (int i = 0; i < n; i++) if (!in[i] && (u < 0 || key[i] < key[u])) u = i;
            in[u] = true;
            if (k > 0) edges[k - 1] = key[u];
            if (par[u] >= 0 && key[u] > max) {
                max = key[u];
                worst[0] = par[u];
                worst[1] = u;
            }
            for (int v = 0; v < n; v++) {
                if (in[v]) continue;
                double g = gap(out.get(u), out.get(v));
                if (g < key[v]) {
                    key[v] = g;
                    par[v] = u;
                }
            }
        }
        return edges;
    }

    private static int[] worstBridge(List<Isle> out) {
        int[] worst = {-1, -1};
        double[] edges = bridges(out, worst);
        double max = Arrays.stream(edges).max().orElse(0);
        return max > MAX_BRIDGE ? worst : null;
    }

    private static boolean free(List<Isle> out, int x, int z, double r, double gap) {
        for (Isle i : out) {
            if (Math.hypot(i.x() - x, i.z() - z) < i.r() + r + gap) return false;
        }
        return true;
    }

    /** 맵 배치 한 줄 요약. 제단 수가 10/6/2 가 아니거나 가장 가까운 제단이 실버가 아니면 ok[0] 이 false. */
    static String summary(List<Isle> isles, boolean[] ok) {
        int res = 0, stones = 0;
        int[] tiers = new int[Tier.values().length];
        Isle nearest = null;
        double spacing = Double.MAX_VALUE;
        for (Isle is : isles) {
            if (is.tier() != null) {
                tiers[is.tier().ordinal()]++;
                if (nearest == null || Math.hypot(is.x(), is.z()) < Math.hypot(nearest.x(), nearest.z())) nearest = is;
                for (Isle o : isles) {
                    if (o != is && o.tier() != null) spacing = Math.min(spacing, Math.hypot(o.x() - is.x(), o.z() - is.z()));
                }
            } else if (is.kind().equals("stone")) stones++;
            else if (IslandKinds.KINDS.contains(is.kind())) res++;
        }
        double longest = Arrays.stream(bridges(isles, new int[2])).max().orElse(0);
        ok[0] = tiers[0] == 10 && tiers[1] == 6 && tiers[2] == 2 && nearest != null && nearest.tier() == Tier.SILVER;
        return "맵 배치: 섬 " + isles.size() + "개 (자원 " + res + ", 징검다리 " + stones + "), 제단 "
                + tiers[0] + "/" + tiers[1] + "/" + tiers[2] + ", 가장 긴 다리 " + Math.round(longest) + "m, 가장 가까운 제단 "
                + (nearest == null ? "없음" : Math.round(Math.hypot(nearest.x(), nearest.z())) + "m (" + nearest.tier().korean + ")")
                + ", 제단 사이 최소 " + Math.round(spacing) + "m";
    }

    // ------------------------------------------------------------------ 짓기

    /** 맵 전체를 짓는다. 서버가 멈추지 않도록 한 틱에 섬 몇 개씩 짓고, 다 지으면 done 을 부른다. */
    public void buildAll(World world, Consumer<String> progress, Runnable done) {
        this.w = world;
        long t0 = System.currentTimeMillis();
        List<String> warn = new ArrayList<>();
        List<Isle> isles = plan(warn);
        boolean[] ok = {true};
        String sum = summary(isles, ok);
        for (String s : warn) plugin.getLogger().warning(s);
        plugin.getLogger().log(ok[0] && warn.isEmpty() ? Level.INFO : Level.WARNING, sum);
        clearParts(isles);
        plugin.altars().clearRegistry(world);
        plugin.mobs().lairs().clearRegistry(world);
        IslandKinds kinds = new IslandKinds(plugin, world);
        new BukkitRunnable() {
            int i = 0, failed = 0;

            @Override
            public void run() {
                long until = System.currentTimeMillis() + 40;
                while (i < isles.size() && System.currentTimeMillis() < until) {
                    Isle is = isles.get(i++);
                    try {
                        build(is, kinds);
                    } catch (RuntimeException ex) {
                        failed++;
                        plugin.getLogger().log(Level.WARNING, "섬 " + is.kind() + " (" + is.x() + ", " + is.z() + ") 짓기 실패", ex);
                    }
                    if (i % 10 == 0 && progress != null) progress.accept("섬 " + i + " / " + isles.size());
                }
                if (i < isles.size()) return;
                cancel();
                w.setSpawnLocation(0, 65, 0);
                w.setGameRule(GameRule.SPAWN_RADIUS, 0);
                w.setGameRule(GameRule.SPAWN_CHUNK_RADIUS, 2);
                w.setTime(1000);
                plugin.altars().scanLoaded();
                plugin.mobs().scanLoaded();
                plugin.getLogger().log(failed == 0 ? Level.INFO : Level.SEVERE, "맵 생성 완료: 섬 " + isles.size()
                        + "개, 실패 " + failed + " (" + (System.currentTimeMillis() - t0) + "ms)");
                if (done != null) done.run();
            }
        }.runTaskTimer(plugin, 1, 1);
    }

    private void clearParts(List<Isle> isles) {
        for (Isle is : isles) {
            Location c = new Location(w, is.x(), is.y(), is.z());
            c.getChunk().load();
            double r = is.r() + 12;
            for (Entity e : w.getNearbyEntities(c, r, 80, r)) {
                if (e.getPersistentDataContainer().has(Keys.MAP_PART)) e.remove();
            }
        }
    }

    private void build(Isle is, IslandKinds kinds) {
        Random r = new Random(SEED ^ is.seed() * 31);
        int x = is.x(), y = is.y(), z = is.z();
        switch (is.kind()) {
            case "start" -> startIsland(x, y, z);
            case "altar" -> altarIsland(is);
            case "end" -> endIsland(x, y, z);
            default -> {
                if (is.kind().startsWith("lair_")) lairIsland(is, r);
                else if (is.kind().startsWith("rift_")) riftIsland(is, r);
                else kinds.build(is, r);
            }
        }
        kinds.paintBiome(is);
        kinds.settleGravity(is);
    }

    /** /증강관리 섬: 섬 하나를 지금 자리에 지어 본다 (모양 확인용). 없는 종류면 false. */
    public boolean buildKind(World world, String kind, int x, int y, int z, double rad) {
        if (NetherMap.isNether(kind)) return new NetherMap(plugin).buildKind(world, kind, x, y, z, rad);
        if (!IslandKinds.KINDS.contains(kind)) return false;
        double r = rad > 0 ? rad : 3.5;
        if (rad <= 0) {
            for (Spot s : DECK) {
                if (s.kind().equals(kind)) {
                    r = (s.sMin() + s.sMax()) / 2;
                    break;
                }
            }
        }
        Isle is = new Isle(kind, x, y, z, r, region(x, z), null, System.nanoTime());
        IslandKinds kinds = new IslandKinds(plugin, world);
        kinds.build(is, new Random(is.seed()));
        kinds.paintBiome(is);
        kinds.settleGravity(is);
        return true;
    }

    /** /증강관리 섬검사: 지은 맵의 섬마다 있어야 할 재료가 있는지 센다. */
    public void checkIslands(World world, CommandSender to) {
        new IslandCheck(plugin, world).run(plan(), to);
    }

    // ------------------------------------------------------------------ 시작의 섬

    private void startIsland(int cx, int y, int cz) {
        // 고전 스카이블럭처럼 L 자 모양 흙섬. 친구들과 쓰기 좋게 조금 넓혔다
        for (int x = -4; x <= 4; x++) {
            for (int z = -4; z <= 6; z++) {
                boolean in = (z <= 1) || (x <= 0);
                if (!in) continue;
                set(cx + x, y, cz + z, Material.GRASS_BLOCK);
                set(cx + x, y - 1, cz + z, Material.DIRT);
                set(cx + x, y - 2, cz + z, Material.DIRT);
                if (Math.abs(x) <= 2 && z >= -2 && z <= 0) set(cx + x, y - 3, cz + z, Material.DIRT);
            }
        }
        set(cx, y - 3, cz - 1, Material.BEDROCK);
        tree(cx + 3, y + 1, cz - 3, TreeType.TREE, Material.OAK_SAPLING);
        // 꼭 필요한 것만: 조약돌 생성기(용암, 얼음), 나무 한 그루, 밀. 나머지는 다른 섬에서 구한다
        Inventory inv = chest(cx - 3, y + 1, cz - 3, BlockFace.SOUTH);
        inv.addItem(new ItemStack(Material.LAVA_BUCKET), new ItemStack(Material.ICE, 2),
                new ItemStack(Material.OAK_SAPLING), new ItemStack(Material.WHEAT_SEEDS, 3),
                new ItemStack(Material.BONE_MEAL, 3), new ItemStack(Material.TORCH, 4));
    }

    // ------------------------------------------------------------------ 제단

    private record Ground(Material top, Material mid, Material bottom) {}

    private static Ground ground(Region g) {
        return switch (g) {
            case PLAINS -> new Ground(Material.GRASS_BLOCK, Material.DIRT, Material.STONE);
            case FROST -> new Ground(Material.SNOW_BLOCK, Material.PACKED_ICE, Material.STONE);
            case FLAME -> new Ground(Material.NETHERRACK, Material.NETHERRACK, Material.BLACKSTONE);
            case VOID -> new Ground(Material.END_STONE, Material.END_STONE, Material.OBSIDIAN);
            case OCEAN -> new Ground(Material.SAND, Material.SANDSTONE, Material.PRISMARINE);
            case WILD -> new Ground(Material.GRASS_BLOCK, Material.COARSE_DIRT, Material.ANDESITE);
        };
    }

    private void altarIsland(Isle is) {
        Ground g = ground(is.region());
        Material top = is.tier() == Tier.PRISM ? (is.region() == Region.VOID ? Material.END_STONE_BRICKS : Material.MOSS_BLOCK) : g.top();
        Material mid = is.region() == Region.PLAINS || is.region() == Region.WILD ? Material.DIRT : g.mid();
        Material bottom = is.tier() == Tier.PRISM ? Material.CALCITE : g.bottom();
        blob(is.x(), is.y(), is.z(), is.r(), (int) (is.r() * 1.1), top, mid, bottom, is.seed(), null, 0);
        altarStructure(w, is.x(), is.y(), is.z(), is.tier());
    }

    /** 제단 구조물만 짓는다. /증강관리 제단 으로 원하는 곳에 새 제단을 세울 때도 쓴다. */
    public void altarStructure(World world, int cx, int y, int cz, Tier tier) {
        this.w = world;
        Material floorA, floorB, pillar, cap, core;
        switch (tier) {
            case SILVER -> {
                floorA = Material.POLISHED_DIORITE; floorB = Material.SMOOTH_QUARTZ;
                pillar = Material.QUARTZ_PILLAR; cap = Material.SEA_LANTERN; core = Material.IRON_BLOCK;
            }
            case GOLD -> {
                floorA = Material.SMOOTH_SANDSTONE; floorB = Material.CHISELED_SANDSTONE;
                pillar = Material.CUT_SANDSTONE; cap = Material.GLOWSTONE; core = Material.GOLD_BLOCK;
            }
            default -> {
                floorA = Material.PURPUR_BLOCK; floorB = Material.PRISMARINE_BRICKS;
                pillar = Material.PURPUR_PILLAR; cap = Material.SEA_LANTERN; core = Material.AMETHYST_BLOCK;
            }
        }
        Location c0 = new Location(w, cx + 0.5, y + 2, cz + 0.5);
        for (Entity e : w.getNearbyEntities(c0, 4, 8, 4)) {
            if (e.getPersistentDataContainer().has(Keys.MAP_PART)) e.remove();
        }
        // 제단 바닥: 두 가지 블록으로 동심원 무늬
        for (int x = -4; x <= 4; x++) {
            for (int z = -4; z <= 4; z++) {
                double d = Math.sqrt(x * x + z * z);
                if (d > 4.3) continue;
                set(cx + x, y, cz + z, ((int) Math.round(d)) % 2 == 0 ? floorA : floorB);
                for (int h = 1; h <= 6; h++) set(cx + x, y + h, cz + z, Material.AIR);
            }
        }
        // 가운데 단
        for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++) set(cx + x, y + 1, cz + z, floorB);
        set(cx, y + 1, cz, cap);
        // 네 기둥
        int[][] corners = {{3, 3}, {-3, 3}, {3, -3}, {-3, -3}};
        for (int[] c : corners) {
            column(cx + c[0], y + 1, cz + c[1], 3, pillar);
            set(cx + c[0], y + 4, cz + c[1], cap);
            if (tier == Tier.PRISM) set(cx + c[0], y + 5, cz + c[1], Material.END_ROD);
            if (tier == Tier.GOLD) set(cx + c[0], y + 5, cz + c[1], Material.LANTERN);
        }
        // 클릭 판정을 먼저 세우고, 보석에 이 제단의 id 를 붙인다 (제단을 쓰면 보석이 어두워진다)
        Interaction hit = interaction(cx + 0.5, y + 2.0, cz + 0.5, 2.2f, 2.6f, Keys.ALTAR, tier.name());
        BlockDisplay cr = crystal(cx + 0.5, y + 3.0, cz + 0.5, core, 0.9f);
        cr.getPersistentDataContainer().set(Keys.ALTAR_OF, PersistentDataType.STRING, hit.getUniqueId().toString());
        plugin.altars().register(hit.getUniqueId(), tier, hit.getLocation());
    }

    private BlockDisplay crystal(double x, double y, double z, Material m, float size) {
        return tag(w.spawn(new Location(w, x, y, z), BlockDisplay.class, b -> {
            b.setBlock(m.createBlockData());
            // 정육면체를 꼭짓점이 위로 오게 세운 '보석' 모양
            AxisAngle4f rot = new AxisAngle4f((float) Math.toRadians(54.7), 1, 0, 1);
            b.setTransformation(new Transformation(new Vector3f(0, 0, 0), rot, new Vector3f(size, size, size), new AxisAngle4f()));
            b.setBrightness(new Display.Brightness(15, 15));
            // 약 64m 안에서만 보인다 (멀리서 보이면 위치 안내가 되어 버린다)
            b.setViewRange(1f);
        }));
    }

    private Interaction interaction(double x, double y, double z, float width, float height, org.bukkit.NamespacedKey key, String value) {
        return tag(w.spawn(new Location(w, x, y, z), Interaction.class, i -> {
            i.setInteractionWidth(width);
            i.setInteractionHeight(height);
            i.setResponsive(true);
            i.getPersistentDataContainer().set(key, PersistentDataType.STRING, value);
        }));
    }

    // ------------------------------------------------------------------ 균열과 둥지

    private record Theme(Material top, Material mid, Material bottom, Material deco, Material glow, Material floorA,
                         Material floorB, Material pillar, Material[] ores, String boss, Material core) {}

    private static Theme theme(String id) {
        return switch (id) {
            case "frost" -> new Theme(Material.SNOW_BLOCK, Material.PACKED_ICE, Material.STONE, Material.BLUE_ICE,
                    Material.SEA_LANTERN, Material.PACKED_ICE, Material.POLISHED_DIORITE, Material.BLUE_ICE,
                    new Material[]{Material.IRON_ORE, Material.COAL_ORE, Material.LAPIS_ORE, Material.DIAMOND_ORE},
                    "frost_tyrant", Material.BLUE_ICE);
            case "flame" -> new Theme(Material.NETHERRACK, Material.MAGMA_BLOCK, Material.BLACKSTONE, Material.BASALT,
                    Material.SHROOMLIGHT, Material.POLISHED_BLACKSTONE_BRICKS, Material.GILDED_BLACKSTONE, Material.BASALT,
                    new Material[]{Material.NETHER_GOLD_ORE, Material.NETHER_QUARTZ_ORE, Material.GOLD_ORE, Material.REDSTONE_ORE},
                    "inferno_colossus", Material.MAGMA_BLOCK);
            default -> new Theme(Material.END_STONE, Material.END_STONE, Material.OBSIDIAN, Material.CRYING_OBSIDIAN,
                    Material.END_ROD, Material.PURPUR_BLOCK, Material.END_STONE_BRICKS, Material.OBSIDIAN,
                    new Material[]{Material.DIAMOND_ORE, Material.EMERALD_ORE, Material.GOLD_ORE, Material.IRON_ORE},
                    "void_sovereign", Material.CRYING_OBSIDIAN);
        };
    }

    /** 균열 섬: 둥지로 가는 길목. 균열의 몬스터가 계속 나오고 정수를 떨군다. */
    private void riftIsland(Isle is, Random r) {
        String id = is.kind().substring("rift_".length());
        Theme t = theme(id);
        int cx = is.x(), y = is.y(), cz = is.z();
        blob(cx, y, cz, is.r(), 11, t.top(), t.mid(), t.bottom(), is.seed(), t.ores(), 0.05);
        for (int i = 0; i < 7; i++) {
            double a = r.nextDouble() * Math.PI * 2, d = 5 + r.nextDouble() * 5;
            int x = cx + (int) Math.round(Math.cos(a) * d), z = cz + (int) Math.round(Math.sin(a) * d);
            int h = 2 + r.nextInt(4);
            column(x, y + 1, z, h, t.deco());
            if (r.nextBoolean()) set(x, y + 1 + h, z, t.glow());
        }
        riftMarker(w, new Location(w, cx + 0.5, y + 1, cz + 0.5), id);
        crystal(cx + 0.5, y + 4.5, cz + 0.5, t.core(), 1.4f);
        Inventory inv = chest(cx - 6, y + 1, cz + 3, BlockFace.EAST);
        inv.addItem(plugin.items().create("shard", 4), new ItemStack(t.top(), 8), new ItemStack(Material.TORCH, 8));
    }

    /** 균열 표식만 세운다 (/증강관리 균열). */
    public void riftMarker(World world, Location at, String rift) {
        this.w = world;
        tag(w.spawn(at.clone(), Marker.class, m ->
                m.getPersistentDataContainer().set(Keys.RIFT, PersistentDataType.STRING, rift)));
        plugin.mobs().scanLoaded();
    }

    /** 둥지 표식만 세운다 (/증강관리 둥지). 보스는 누군가 다가오면 나타난다. */
    public void lairMarker(World world, Location at, String bossId) {
        plugin.mobs().lairs().create(at, bossId);
    }

    /** 보스 둥지: 넓고 평평한 결투장. 보스는 처음부터 여기를 지킨다. */
    private void lairIsland(Isle is, Random r) {
        String id = is.kind().substring("lair_".length());
        Theme t = theme(id);
        int cx = is.x(), y = is.y(), cz = is.z();
        double rad = is.r();
        blob(cx, y, cz, rad, 16, t.top(), t.mid(), t.bottom(), is.seed(), t.ores(), 0.03);
        // 결투장 바닥: 동심원 무늬, 위쪽은 비운다
        double arena = rad - 3.5;
        int A = (int) Math.ceil(arena);
        for (int x = -A; x <= A; x++)
            for (int z = -A; z <= A; z++) {
                double d = Math.sqrt(x * x + z * z);
                if (d > arena) continue;
                int ring = (int) Math.round(d);
                set(cx + x, y, cz + z, ring % 3 == 0 ? t.floorB() : t.floorA());
                for (int h = 1; h <= 14; h++) set(cx + x, y + h, cz + z, Material.AIR);
            }
        disc(cx, y, cz, 2.2, t.floorB());
        set(cx, y, cz, t.glow() == Material.END_ROD ? Material.CRYING_OBSIDIAN : t.glow());
        // 둘레의 큰 기둥 여덟 개 (입구 쪽 두 칸은 비운다)
        double toCenter = Math.atan2(-cz, -cx);
        for (int i = 0; i < 8; i++) {
            double a = i * Math.PI / 4 + Math.PI / 8;
            double diff = Math.abs(Math.atan2(Math.sin(a - toCenter), Math.cos(a - toCenter)));
            if (diff < 0.5) continue;
            int px = cx + (int) Math.round(Math.cos(a) * (arena + 0.5)), pz = cz + (int) Math.round(Math.sin(a) * (arena + 0.5));
            int h = 7 + r.nextInt(6);
            switch (id) {
                case "frost" -> spike(px, y + 1, pz, h + 3, Material.PACKED_ICE, Material.BLUE_ICE);
                case "flame" -> {
                    for (int dx = 0; dx <= 1; dx++) for (int dz = 0; dz <= 1; dz++) column(px + dx, y + 1, pz + dz, h, Material.BASALT);
                    set(px, y + 1 + h, pz, Material.NETHERRACK);
                    set(px, y + 2 + h, pz, Material.FIRE);
                    set(px + 1, y + 1 + h, pz + 1, Material.SHROOMLIGHT);
                }
                default -> {
                    spike(px, y + 1, pz, h + 2, Material.OBSIDIAN, Material.END_ROD);
                    set(px, y + 3, pz, Material.CRYING_OBSIDIAN);
                }
            }
        }
        // 보스가 사는 곳 (보이지 않는 표식)
        lairMarker(w, new Location(w, cx + 0.5, y + 1, cz + 0.5), t.boss());
    }

    private void endIsland(int cx, int y, int cz) {
        blob(cx, y, cz, 7, 7, Material.END_STONE, Material.END_STONE, Material.END_STONE, 77, null, 0);
        // 엔드 포탈 틀 12개. 눈은 직접 채워야 한다
        for (int i = -1; i <= 1; i++) {
            frame(cx + i, y + 1, cz - 2, BlockFace.SOUTH);
            frame(cx + i, y + 1, cz + 2, BlockFace.NORTH);
            frame(cx - 2, y + 1, cz + i, BlockFace.EAST);
            frame(cx + 2, y + 1, cz + i, BlockFace.WEST);
        }
        for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++) set(cx + x, y, cz + z, Material.AIR);
    }

    private void frame(int x, int y, int z, BlockFace facing) {
        Block b = w.getBlockAt(x, y, z);
        b.setType(Material.END_PORTAL_FRAME, false);
        if (b.getBlockData() instanceof EndPortalFrame f) {
            f.setFacing(facing);
            f.setEye(false);
            b.setBlockData(f, false);
        }
    }
}
