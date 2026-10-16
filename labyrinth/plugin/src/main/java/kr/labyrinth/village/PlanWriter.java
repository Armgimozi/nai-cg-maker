package kr.labyrinth.village;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.LongConsumer;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.DyeColor;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Banner;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.Sign;
import org.bukkit.block.banner.Pattern;
import org.bukkit.block.banner.PatternType;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.type.Slab;
import org.bukkit.block.sign.Side;
import org.bukkit.block.sign.SignSide;

/**
 * 계획(Plan)을 월드에 쓰는 칸 단위 일 (VILLAGE.md §4.1 짓기 순서의 지형·조각·길·표지판). 마을 짓기({@link VillageBuilder})와
 * 0.3.6 구역 짓기({@link DistrictJob})가 같이 쓴다 — 마을은 예전과 같은 블록을 놓는다.
 * 구역(마스크 모드)에서는 얼린 칸(마을)의 지형을 건드리지 않고, 그 위 구역 길은 겉 블록만 깐다 (CONTRACT §2.13 3).
 * {@link #positions} 는 짓기 전에 바꿀 수 있는 칸을 모두 내놓는다 (구역 백업).
 */
final class PlanWriter {

    final World world;
    final Plan plan;
    final TerrainGrid grid;
    final Map<String, List<Blueprint.Weighted>> styles;
    /** 구역: 옹벽·기초 블록 (조각 foundation_mix 대신). null = 조각 것. */
    final List<Blueprint.Weighted> foundationMix;
    int changed, errors;
    private final Map<String, BlockData> dataCache = new HashMap<>();
    private final Map<String, BlockData> pieceCache = new HashMap<>();
    private Map<Long, Integer> pathIndex;

    PlanWriter(World world, Plan plan, TerrainGrid grid, Map<String, List<Blueprint.Weighted>> styles, List<Blueprint.Weighted> foundationMix) {
        this.world = world;
        this.plan = plan;
        this.grid = grid;
        this.styles = styles;
        this.foundationMix = foundationMix == null || foundationMix.isEmpty() ? null : foundationMix;
    }

    BlockData data(String state) {
        return dataCache.computeIfAbsent(state, s -> {
            try {
                return Bukkit.createBlockData(s);
            } catch (IllegalArgumentException e) {
                errors++;
                Log.warn("[마을] 블록 문자열 오류: " + s);
                return Material.STONE.createBlockData();
            }
        });
    }

    void set(Block blk, String state, VillageJob.Budget b) {
        BlockData d = data(state);
        if (blk.getBlockData().matches(d)) return;
        blk.setBlockData(d, false);
        b.use(1);
        changed++;
    }

    // ── 지형 ─────────────────────────────────────────────────────────────

    /** 옹벽·기초 블록: 그 칸을 덮는 조각의 foundation_mix (+ 아래쪽은 이끼 섞기), 없으면 첫 조각(광장) 것. 구역은 구역 foundation_mix. */
    String foundation(int x, int y, int z) {
        long h = Blueprint.hash(x, y, z);
        if (foundationMix != null) return Blueprint.pick(foundationMix, h, "minecraft:stone_bricks");
        Blueprint src = plan.pieces.get(0).bp;
        for (Plan.Placed pl : plan.pieces) {
            if (x >= pl.x0 - 1 && x <= pl.x0 + pl.w2 && z >= pl.z0 - 1 && z <= pl.z0 + pl.d2) {
                src = pl.bp;
                break;
            }
        }
        String f = src.foundationAt(h);
        if (Math.floorMod(h >>> 7, 5) == 0) {
            String id = Nature.key(f);
            String mossy = id.equals("cobblestone") ? "mossy_cobblestone" : id.endsWith("stone_bricks") && !id.startsWith("mossy") ? "mossy_stone_bricks" : null;
            if (mossy != null) return "minecraft:" + mossy;
        }
        return f;
    }

    static boolean replaceableTerrain(Material m) {
        Nature.Kind k = Scan.kind(m);
        return k == Nature.Kind.AIR || k == Nature.Kind.PLANT || k == Nature.Kind.GROUND || k == Nature.Kind.LEAVES
                || k == Nature.Kind.LOG || k == Nature.Kind.TREE_PART;
    }

    /** 이 격자 칸 지형을 다듬는가 (영역 안, 얼린 칸 아님, 조사된 칸, 손대는 칸). */
    private boolean terrainCell(int i) {
        int lx = i % plan.gn, lz = i / plan.gn;
        int x = plan.gx0 + lx, z = plan.gz0 + lz;
        if (!plan.inRegion(x, z) || plan.isFrozen(x, z) || !grid.has(x, z)) return false;
        int g = plan.ground[i], t = plan.field.target()[i];
        return plan.fixedSrc[i] != 0 && plan.fixedSrc[i] != 6 || t != g || plan.field.exposed()[i] > 0 || nearFixed(lx, lz, 2);
    }

    void terrainColumn(int i, VillageJob.Budget b) {
        if (!terrainCell(i)) return;
        int lx = i % plan.gn, lz = i / plan.gn;
        int x = plan.gx0 + lx, z = plan.gz0 + lz;
        int g = plan.ground[i], t = plan.field.target()[i];
        boolean colChanged = t != g;
        byte src = plan.fixedSrc[i];
        int exposed = plan.field.exposed()[i];
        String surf = grid.surface(x, z);
        String top = Nature.topFor(surf), sub = Nature.subsurface(surf);
        // 손대는 칸 = 고정 칸(조각·여유·정문 앞·길·추가 단)과 그 둘레 2칸, 높이가 바뀐 칸, 옹벽 칸.
        // 그 밖(R 안이라도 그대로인 땅)의 풀·꽃·눈은 남긴다 — 마을 둘레에 동그랗게 깎인 자국이 생기지 않게.
        boolean snowy = grid.flag(x, z, Terrain.SNOW) && src != 3 && src != 4 && src != 5;
        // 1. 목표보다 위: 공기 (식물·눈 포함, 위로 뻗은 자연 지형 덩어리까지) — 그대로인 눈 덮인 칸은 눈 유지
        int clearTop = Math.max(g, t) + 2;
        for (int y = t + 1; y <= clearTop + 14; y++) {
            Block blk = world.getBlockAt(x, y, z);
            Material m = blk.getType();
            if (m.isAir()) {
                if (y > clearTop) break;
                continue;
            }
            Nature.Kind k = Scan.kind(m);
            boolean go = y <= g ? replaceableTerrain(m) : (k == Nature.Kind.PLANT || k == Nature.Kind.GROUND || k == Nature.Kind.LIQUID);
            if (m == Material.SNOW && snowy && !colChanged && y == t + 1) go = false;
            if (!go) {
                if (y > clearTop) break;
                continue;
            }
            blk.setBlockData(data("minecraft:air"), false);
            b.use(1);
            changed++;
        }
        boolean footprint = src == 5;
        if (colChanged || exposed > 0) {
            // 2. 깎은 칸: 새 맨 윗블록 + 그 아래 두 칸 / 메운 칸: 원래 땅 위로 목표까지 (묻힌 잔디는 흙으로)
            //    옹벽 칸: 드러난 높이만큼 기초 블록(foundation_mix + 이끼)
            int lo = t < g ? t - 2 : t > g ? g : t;
            if (exposed > 0) lo = Math.min(lo, t - exposed + 1);
            for (int y = lo; y <= t; y++) {
                String want = exposed > 0 && y > t - exposed ? foundation(x, y, z) : y == t ? top : sub;
                Block blk = world.getBlockAt(x, y, z);
                if (!replaceableTerrain(blk.getType())) continue;
                set(blk, want, b);
            }
        } else if (!footprint) {
            return; // R 안 그대로인 칸: 식물만 지움
        }
        // 3. 바뀐 칸 바로 아래 빈칸 막기 (얇은 껍질 위에 서지 않게), 발자국은 기초 깊이까지 (§0 동굴)
        int depth = footprint ? plan.caveDepth : 3;
        for (int k = 1; k <= depth; k++) {
            Block blk = world.getBlockAt(x, t - k, z);
            Nature.Kind kk = Scan.kind(blk.getType());
            if (kk == Nature.Kind.AIR || kk == Nature.Kind.LIQUID) set(blk, footprint ? foundation(x, t - k, z) : sub, b);
        }
        // 4. 원래 눈 덮였던 바뀐 칸은 눈 한 겹 되살림 (길·정문 앞·조각 발자국 제외) — 눈 덮인 들판 가운데 초록 원판이 생기지 않게
        if (snowy && colChanged && exposed == 0) {
            Block above = world.getBlockAt(x, t + 1, z);
            if (above.getType().isAir()) {
                Block topBlk = world.getBlockAt(x, t, z);
                if (topBlk.getType() == Material.GRASS_BLOCK) set(topBlk, "minecraft:grass_block[snowy=true]", b);
                set(above, "minecraft:snow[layers=1]", b);
            }
        }
    }

    /** 마을이 손대는 칸인가: 고정 칸(조각·여유·정문 앞·길·추가 단)과 그 둘레 2칸, 높이가 바뀐 칸. 나무·풀·눈은 이 칸에서만 치운다. 얼린 칸은 아님. */
    boolean tidy(int x, int z) {
        if (!plan.inGrid(x, z) || plan.isFrozen(x, z)) return false;
        int i = plan.idx(x, z);
        return plan.fixedSrc[i] != 0 && plan.fixedSrc[i] != 6 || plan.field.changed()[i] || plan.field.exposed()[i] > 0
                || nearFixed(x - plan.gx0, z - plan.gz0, 2);
    }

    /** 격자 칸 (lx, lz) 둘레 r 칸 안에 고정 칸(얼린 칸 제외)이 있는가. */
    private boolean nearFixed(int lx, int lz, int r) {
        for (int dz = -r; dz <= r; dz++) {
            for (int dx = -r; dx <= r; dx++) {
                int ax = lx + dx, az = lz + dz;
                if (ax < 0 || az < 0 || ax >= plan.gn || az >= plan.gn) continue;
                byte s = plan.fixedSrc[az * plan.gn + ax];
                if (s != 0 && s != 6) return true;
            }
        }
        return false;
    }

    // ── 조각 ─────────────────────────────────────────────────────────────

    /** 회전한 팔레트 블록 (BlockData#rotate). */
    BlockData pieceData(Plan.Placed pl, int cp) {
        String key = pl.index() + ":" + cp;
        return pieceCache.computeIfAbsent(key, k -> {
            String st = pl.bp.state(cp);
            BlockData d = data(st).clone();
            d.rotate(Rot.of(pl.turns));
            return d;
        });
    }

    void pieceCell(Plan.Placed pl, int k, VillageJob.Budget b) {
        Blueprint bp = pl.bp;
        int x = k % bp.w, z = (k / bp.w) % bp.d, y = k / (bp.w * bp.d);
        int cp = bp.cell(x, y, z);
        if (cp == Blueprint.KEEP) return;
        int[] w = pl.world(x, z);
        Block blk = world.getBlockAt(w[0], pl.worldY(y), w[1]);
        if (cp == Blueprint.AIR) {
            if (!blk.getType().isAir()) {
                blk.setBlockData(data("minecraft:air"), false);
                b.use(1);
            }
            return;
        }
        blk.setBlockData(pieceData(pl, cp), false);
        b.use(1);
    }

    // ── 길 ───────────────────────────────────────────────────────────────

    /** 길 블록의 반블록 (돌 벽돌 → 돌 벽돌 반블록 …), 없으면 null. */
    static String slabOf(String block) {
        String id = Nature.key(block).replace("cracked_", "");
        String slab;
        if (id.endsWith("bricks")) slab = id.substring(0, id.length() - 1) + "_slab";
        else if (id.endsWith("tiles")) slab = id.substring(0, id.length() - 1) + "_slab";
        else if (id.endsWith("planks")) slab = id.replace("_planks", "_slab");
        else slab = id + "_slab";
        Material m = Material.matchMaterial("minecraft:" + slab);
        return m != null && m.isBlock() && m.createBlockData() instanceof Slab ? "minecraft:" + slab + "[type=bottom,waterlogged=false]" : null;
    }

    void pathCell(Plan.PathPlan pp, int[] c, VillageJob.Budget b) {
        int x = c[0], z = c[1], y = c[2];
        List<Blueprint.Weighted> style = styles.getOrDefault(pp.def.style(), List.of());
        String block = Blueprint.pick(style, Blueprint.hash(x, 0, z), "minecraft:dirt_path");
        set(world.getBlockAt(x, y, z), block, b);
        for (int dy = 1; dy <= 2; dy++) {
            Block above = world.getBlockAt(x, y + dy, z);
            Nature.Kind k = Scan.kind(above.getType());
            if (k == Nature.Kind.PLANT || k == Nature.Kind.GROUND) set(above, "minecraft:air", b);
        }
        if (plan.isFrozen(x, z)) return; // 얼린 칸(마을이 다듬은 칸): 겉 블록만
        // 이웃 길이 1 높으면 반블록으로 반 칸 계단
        boolean higher = false;
        for (int[] d : new int[][] {{1, 0}, {-1, 0}, {0, 1}, {0, -1}}) {
            int h = pathHeight(x + d[0], z + d[1]);
            if (h == y + 1) higher = true;
        }
        if (higher) {
            String slab = slabOf(block);
            if (slab == null && !style.isEmpty()) slab = slabOf(style.get(0).block());
            if (slab != null) set(world.getBlockAt(x, y + 1, z), slab, b);
        }
    }

    private int pathHeight(int x, int z) {
        if (pathIndex == null) {
            pathIndex = new HashMap<>();
            for (Plan.PathPlan pp : plan.paths) for (int[] c : pp.cells) pathIndex.putIfAbsent(PathRaster.key(c[0], c[1]), c[2]);
        }
        return pathIndex.getOrDefault(PathRaster.key(x, z), Integer.MIN_VALUE);
    }

    // ── 표지판·깃발 ──────────────────────────────────────────────────────

    /** @return {표지판, 깃발} */
    int[] post() {
        int signs = 0, banners = 0;
        for (Markers.Placed mk : Markers.all(plan)) {
            int[] w = mk.first();
            if (w == null) continue;
            Block blk = world.getBlockAt(w[0], w[1], w[2]);
            try {
                if (mk.marker().type().equals("sign")) {
                    BlockState st = blk.getState();
                    if (!(st instanceof Sign sign)) {
                        Log.warn("[마을] 표지판 마커 자리에 표지판이 없음: " + mk.piece().bp.id + " " + blk.getType());
                        errors++;
                        continue;
                    }
                    writeSide(sign.getSide(Side.FRONT), mk.marker().lines(), mk.marker().glow());
                    if (!mk.marker().back().isEmpty()) writeSide(sign.getSide(Side.BACK), mk.marker().back(), mk.marker().glow());
                    sign.setWaxed(true);
                    sign.update(true, false);
                    signs++;
                } else if (mk.marker().type().equals("banner")) {
                    BlockState st = blk.getState();
                    if (!(st instanceof Banner banner)) {
                        Log.warn("[마을] 깃발 마커 자리에 깃발이 없음: " + mk.piece().bp.id + " " + blk.getType());
                        errors++;
                        continue;
                    }
                    List<Pattern> pats = new ArrayList<>();
                    var reg = io.papermc.paper.registry.RegistryAccess.registryAccess().getRegistry(io.papermc.paper.registry.RegistryKey.BANNER_PATTERN);
                    for (String[] p : mk.marker().patterns()) {
                        PatternType type = reg.get(Key.key(p[0].contains(":") ? p[0] : "minecraft:" + p[0]));
                        DyeColor color;
                        try {
                            color = DyeColor.valueOf(p[1].toUpperCase(java.util.Locale.ROOT));
                        } catch (IllegalArgumentException e) {
                            color = null;
                        }
                        if (type == null || color == null) {
                            Log.warn("[마을] 깃발 무늬 오류: " + p[0] + " " + p[1]);
                            errors++;
                            continue;
                        }
                        pats.add(new Pattern(color, type));
                    }
                    banner.setPatterns(pats);
                    banner.update(true, false);
                    banners++;
                }
            } catch (Throwable t) {
                errors++;
                Log.error("[마을] 후처리 오류 (" + mk.marker().type() + ")", t);
            }
        }
        return new int[] {signs, banners};
    }

    private static void writeSide(SignSide side, List<String> lines, boolean glow) {
        for (int i = 0; i < 4; i++) side.line(i, Text.mm(i < lines.size() ? lines.get(i) : ""));
        side.setGlowingText(glow);
    }

    // ── 백업 칸 (구역) ───────────────────────────────────────────────────

    /**
     * 지형·조각·길이 바꿀 수 있는 칸을 모두 내놓는다 (나무 치우기 칸은 부르는 쪽이 더함). 같은 칸이 여러 번 나올 수 있다.
     * 지형 열: [min(원래, 목표) − max(기초 깊이, 옹벽) − 2, max(원래, 목표) + 16] — {@link #terrainColumn} 이 닿는 범위.
     */
    void positions(LongConsumer out) {
        int n = plan.gn * plan.gn;
        for (int i = 0; i < n; i++) {
            if (!terrainCell(i)) continue;
            int x = plan.gx0 + i % plan.gn, z = plan.gz0 + i / plan.gn;
            int g = plan.ground[i], t = plan.field.target()[i];
            int lo = Math.min(g, t) - Math.max(plan.caveDepth, plan.field.exposed()[i]) - 2, hi = Math.max(g, t) + 16;
            for (int y = lo; y <= hi; y++) out.accept(Trees.pack(x, y, z));
        }
        for (Plan.Placed pl : plan.pieces) {
            Blueprint bp = pl.bp;
            for (int y = 0; y < bp.h; y++) for (int z = 0; z < bp.d; z++) for (int x = 0; x < bp.w; x++) {
                if (bp.cell(x, y, z) == Blueprint.KEEP) continue;
                int[] w = pl.world(x, z);
                out.accept(Trees.pack(w[0], pl.worldY(y), w[1]));
            }
        }
        for (Plan.PathPlan pp : plan.paths) for (int[] c : pp.cells) for (int dy = 0; dy <= 2; dy++) out.accept(Trees.pack(c[0], c[2] + dy, c[1]));
    }

    // ── 메타데이터 ───────────────────────────────────────────────────────

    /** 발 칸 보정: 발·머리 칸이 막혔으면 위로, 발밑이 비었으면 아래로 (최대 3칸). */
    static VillageMeta.Pos standable(World w, VillageMeta.Pos p) {
        int x = (int) Math.floor(p.x()), z = (int) Math.floor(p.z()), y = (int) Math.floor(p.y());
        for (int i = 0; i < 4; i++) {
            Block feet = w.getBlockAt(x, y, z);
            if (!feet.isPassable() || !feet.getRelative(0, 1, 0).isPassable()) {
                y++;
                continue;
            }
            if (feet.getRelative(0, -1, 0).isPassable() && i < 3) {
                y--;
                continue;
            }
            break;
        }
        return new VillageMeta.Pos(p.x(), y, p.z(), p.yaw());
    }
}
