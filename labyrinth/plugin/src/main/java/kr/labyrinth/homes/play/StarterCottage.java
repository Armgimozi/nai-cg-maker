package kr.labyrinth.homes.play;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.homes.PlotGeom;

/**
 * 시작 선물 ① 작은 오두막 7×7 (0.3.7, 설계 §4) — 순수 계획 (어느 칸에 어떤 블록).
 * <p>
 * 집터 뒤쪽 가운데: 뒤 울타리에서 한 칸 띄우고, 가로는 가운데 (14칸이면 왼쪽 3칸 · 오른쪽 4칸, 문 = 대문과 같은 줄). 앞마당 약 14×6 이 남는다.
 * 바닥 높이 = 집터 바닥 (잔디 칸을 바꿈). 벽 3칸 + 박공 지붕 3단 + 용마루. 안에 침대·상자 2·작업대·화로·등불 2.
 * 나무 4가지 (참나무·가문비·자작·벚나무). 앞 방향(N·S·E·W)에 따라 돌린다 — 문은 늘 대문 쪽.
 * <p>
 * 국소 좌표: u = 가로 0..6 (앞에서 볼 때 왼쪽 → 오른쪽), v = 깊이 0..6 (0 = 뒤 벽, 6 = 앞 벽), h = 바닥 위 높이 (0 = 바닥).
 */
public final class StarterCottage {

    private StarterCottage() {}

    public static final int SIZE = 7;
    /** 지붕 꼭대기까지 높이 (바닥 0 기준). */
    public static final int HEIGHT = 7;

    /** 오두막 나무. */
    public enum Wood {
        OAK("참나무", "oak", "red_bed"),
        SPRUCE("가문비", "spruce", "blue_bed"),
        BIRCH("자작", "birch", "green_bed"),
        CHERRY("벚나무", "cherry", "pink_bed");

        public final String label;
        public final String key;
        public final String bed;

        Wood(String label, String key, String bed) {
            this.label = label;
            this.key = key;
            this.bed = bed;
        }

        public String planks() { return key + "_planks"; }

        public String log() { return key + "_log"; }

        public String stairs() { return key + "_stairs"; }

        public String slab() { return key + "_slab"; }

        public String door() { return key + "_door"; }

        public static Wood of(String s) {
            if (s == null) return null;
            for (Wood w : values()) if (w.key.equalsIgnoreCase(s.trim()) || w.name().equalsIgnoreCase(s.trim()) || w.label.equals(s.trim())) return w;
            return null;
        }
    }

    /** 놓을 칸 하나 (월드 좌표, 블록 데이터 글 — {@code Bukkit.createBlockData}). */
    public record Cell(int x, int y, int z, String data) {}

    /** 국소 방향 → 월드 방향 이름. */
    private record Frame(int ax, int az, int ux, int uz, int vx, int vz, String back, String front, String left, String right) {
        int x(int u, int v) { return ax + u * ux + v * vx; }

        int z(int u, int v) { return az + u * uz + v * vz; }
    }

    /** 앞 방향에 따른 국소 → 월드 변환. 뒤 벽(v=0)은 뒤 울타리에서 한 칸 안쪽, u 는 가운데. */
    private static Frame frame(PlotGeom p) {
        int w = p.width(), d = p.depth();
        return switch (p.front()) {
            case "N" -> { // 대문 북쪽 → 뒤 = 남쪽 (z1). 앞에서(북) 남쪽을 보면 왼쪽 = 동쪽
                int u0 = p.x0() + (w - SIZE) / 2 + SIZE - 1;
                yield new Frame(u0, p.z1() - 1, -1, 0, 0, -1, "south", "north", "east", "west");
            }
            case "E" -> { // 대문 동쪽 → 뒤 = 서쪽 (x0). 동쪽에서 서쪽을 보면 왼쪽 = 남쪽
                int u0 = p.z0() + (d - SIZE) / 2 + SIZE - 1;
                yield new Frame(p.x0() + 1, u0, 0, -1, 1, 0, "west", "east", "south", "north");
            }
            case "W" -> { // 대문 서쪽 → 뒤 = 동쪽 (x1). 서쪽에서 동쪽을 보면 왼쪽 = 북쪽
                int u0 = p.z0() + (d - SIZE) / 2;
                yield new Frame(p.x1() - 1, u0, 0, 1, -1, 0, "east", "west", "north", "south");
            }
            default -> { // "S": 대문 남쪽 → 뒤 = 북쪽 (z0). 남쪽에서 북쪽을 보면 왼쪽 = 서쪽
                int u0 = p.x0() + (w - SIZE) / 2;
                yield new Frame(u0, p.z0() + 1, 1, 0, 0, 1, "north", "south", "west", "east");
            }
        };
    }

    /** 오두막이 들어갈 땅 칸 (월드 x, z) 49개 — 바닥 칸. */
    public static List<int[]> footprint(PlotGeom p) {
        Frame f = frame(p);
        List<int[]> out = new ArrayList<>();
        for (int v = 0; v < SIZE; v++) for (int u = 0; u < SIZE; u++) out.add(new int[] {f.x(u, v), f.z(u, v)});
        return out;
    }

    /** 문 칸 (월드 x, z). */
    public static int[] doorCell(PlotGeom p) {
        Frame f = frame(p);
        return new int[] {f.x(3, SIZE - 1), f.z(3, SIZE - 1)};
    }

    /** 놓을 칸 전부 (공기 칸 포함 — 안쪽 공간을 비움). 바닥 = p.floorY(). */
    public static List<Cell> plan(PlotGeom p, Wood wood) {
        Frame f = frame(p);
        int y0 = p.floorY();
        List<Cell> out = new ArrayList<>();
        String planks = "minecraft:" + wood.planks();
        String log = "minecraft:" + wood.log() + "[axis=y]";
        for (int v = 0; v < SIZE; v++) {
            for (int u = 0; u < SIZE; u++) {
                boolean edge = u == 0 || v == 0 || u == SIZE - 1 || v == SIZE - 1;
                boolean corner = (u == 0 || u == SIZE - 1) && (v == 0 || v == SIZE - 1);
                // 바닥: 둘레 돌벽돌, 안 판자
                out.add(cell(f, u, v, y0, edge ? "minecraft:stone_bricks" : planks));
                for (int h = 1; h <= 3; h++) {
                    String b;
                    if (!edge) b = "minecraft:air";
                    else if (corner) b = log;
                    else b = wall(f, wood, u, v, h);
                    out.add(cell(f, u, v, y0 + h, b));
                }
            }
        }
        // 지붕: 박공 (용마루가 가로 u 방향 — 앞뒤에서 올라감)
        for (int u = 0; u < SIZE; u++) {
            out.add(cell(f, u, 0, y0 + 4, stairs(wood, f.front)));
            out.add(cell(f, u, 6, y0 + 4, stairs(wood, f.back)));
            out.add(cell(f, u, 1, y0 + 5, stairs(wood, f.front)));
            out.add(cell(f, u, 5, y0 + 5, stairs(wood, f.back)));
            out.add(cell(f, u, 2, y0 + 6, stairs(wood, f.front)));
            out.add(cell(f, u, 4, y0 + 6, stairs(wood, f.back)));
            out.add(cell(f, u, 3, y0 + 6, planks));
            out.add(cell(f, u, 3, y0 + 7, "minecraft:" + wood.slab() + "[type=bottom,waterlogged=false]"));
        }
        // 박공 벽 (양 옆 세모) 과 지붕 안 공기
        for (int u = 0; u < SIZE; u++) {
            boolean side = u == 0 || u == SIZE - 1;
            for (int v = 1; v <= 5; v++) out.add(cell(f, u, v, y0 + 4, side ? planks : "minecraft:air"));
            for (int v = 2; v <= 4; v++) out.add(cell(f, u, v, y0 + 5, side ? planks : "minecraft:air"));
        }
        // 안: 침대 (뒤 왼쪽, 머리 = 뒤) · 상자 2 (뒤 오른쪽) · 작업대·화로 (오른쪽 벽) · 등불 2 (앞 두 구석)
        replace(out, f, 1, 1, y0 + 1, "minecraft:" + wood.bed + "[facing=" + f.back + ",part=head,occupied=false]");
        replace(out, f, 1, 2, y0 + 1, "minecraft:" + wood.bed + "[facing=" + f.back + ",part=foot,occupied=false]");
        replace(out, f, 4, 1, y0 + 1, "minecraft:chest[facing=" + f.front + ",type=single,waterlogged=false]");
        replace(out, f, 5, 1, y0 + 1, "minecraft:chest[facing=" + f.front + ",type=single,waterlogged=false]");
        replace(out, f, 5, 3, y0 + 1, "minecraft:crafting_table");
        replace(out, f, 5, 4, y0 + 1, "minecraft:furnace[facing=" + f.left + ",lit=false]");
        replace(out, f, 1, 5, y0 + 1, "minecraft:lantern[hanging=false,waterlogged=false]");
        replace(out, f, 5, 5, y0 + 1, "minecraft:lantern[hanging=false,waterlogged=false]");
        return out;
    }

    /** 벽 칸 (모서리 아님): 문 · 창 · 판자. */
    private static String wall(Frame f, Wood wood, int u, int v, int h) {
        boolean frontWall = v == SIZE - 1, backWall = v == 0, sideWall = u == 0 || u == SIZE - 1;
        if (frontWall && u == 3 && h <= 2) {
            return "minecraft:" + wood.door() + "[facing=" + f.back + ",half=" + (h == 1 ? "lower" : "upper")
                    + ",hinge=left,open=false,powered=false]";
        }
        if (h == 2) {
            // 유리판: 벽 줄 방향으로 이어 붙임
            if (sideWall && v >= 2 && v <= 4) return pane(f.back, f.front);
            if (backWall && u >= 2 && u <= 4) return pane(f.left, f.right);
            if (frontWall && (u == 1 || u == 5)) return pane(f.left, f.right);
        }
        return "minecraft:" + wood.planks();
    }

    private static String pane(String a, String b) {
        StringBuilder sb = new StringBuilder("minecraft:glass_pane[");
        String[] dirs = {"east", "north", "south", "west"};
        for (int i = 0; i < dirs.length; i++) {
            if (i > 0) sb.append(',');
            sb.append(dirs[i]).append('=').append(dirs[i].equals(a) || dirs[i].equals(b));
        }
        return sb.append(",waterlogged=false]").toString();
    }

    private static String stairs(Wood wood, String facing) {
        return "minecraft:" + wood.stairs() + "[facing=" + facing + ",half=bottom,shape=straight,waterlogged=false]";
    }

    private static Cell cell(Frame f, int u, int v, int y, String data) { return new Cell(f.x(u, v), y, f.z(u, v), data); }

    private static void replace(List<Cell> cells, Frame f, int u, int v, int y, String data) {
        int x = f.x(u, v), z = f.z(u, v);
        for (int i = 0; i < cells.size(); i++) {
            Cell c = cells.get(i);
            if (c.x() == x && c.y() == y && c.z() == z) {
                cells.set(i, new Cell(x, y, z, data));
                return;
            }
        }
        cells.add(new Cell(x, y, z, data));
    }

    /** 이 블록 위에는 오두막을 지어도 되나 (바닥 칸: 잔디·흙·흙길 / 그 위: 공기·풀·꽃·눈). id = minecraft: 없는 이름. */
    public static boolean replaceableFloor(String id) {
        return switch (id) {
            case "grass_block", "dirt", "coarse_dirt", "dirt_path", "podzol", "rooted_dirt", "mycelium", "moss_block" -> true;
            default -> false;
        };
    }

    public static boolean replaceableAbove(String id) {
        return switch (id) {
            case "air", "cave_air", "short_grass", "tall_grass", "fern", "large_fern", "snow", "dandelion", "poppy", "blue_orchid", "allium",
                 "azure_bluet", "red_tulip", "orange_tulip", "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley",
                 "pink_petals", "wildflowers", "leaf_litter", "bush", "short_dry_grass", "tall_dry_grass", "dead_bush" -> true;
            default -> false;
        };
    }
}
