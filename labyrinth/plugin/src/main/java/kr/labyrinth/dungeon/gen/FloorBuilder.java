package kr.labyrinth.dungeon.gen;

import java.util.List;
import java.util.Set;
import java.util.SplittableRandom;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.Params;
import org.bukkit.Material;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.Directional;
import org.bukkit.block.data.Hangable;
import org.bukkit.block.data.Lightable;
import org.bukkit.block.data.MultipleFacing;
import org.bukkit.block.data.Rotatable;
import org.bukkit.block.data.type.Slab;
import org.bukkit.block.data.type.Speleothem;
import org.bukkit.block.data.type.Stairs;

/**
 * 타일 지도 → 블록 목록 (테마 팔레트·장식·조명). 열린 타일: 바닥(y0+e) + 천장(y0+e+h+1) + 이웃보다 낮은 천장 위 메움
 * (e = 바닥 높이 — 계단 복도 단상만 1~3, 그 아래는 벽 블록으로 받침). 계단 타일은 바닥 위에 팔레트 stairs 블록,
 * 금 간 벽 타일은 바닥 위 내부 높이만큼 팔레트 secret 블록. 열린 타일과 맞닿은 빈 타일: 벽 기둥.
 * 도랑: 바닥 아래 받침 + 액체 + 난간. 공허 월드라 공기는 쓰지 않는다.
 */
public final class FloorBuilder {

    private static final BlockFace[] SIDES = {BlockFace.NORTH, BlockFace.EAST, BlockFace.SOUTH, BlockFace.WEST};

    private final FloorLayout layout;
    private final FloorDef def;
    private final Palette palette;
    private final int ox, y0, oz;
    private final SplittableRandom rng;
    private final Set<Integer> noDecorRooms;
    private final Set<Integer> noLightRooms;
    private final String arenaShape;
    private final int arenaTile;
    private final BlockList out = new BlockList();

    public FloorBuilder(FloorLayout layout, FloorDef def, int ox, int y0, int oz, long seed,
                        Set<Integer> noDecorRooms, Set<Integer> noLightRooms, Params arenaParams) {
        this.layout = layout;
        this.def = def;
        this.palette = new Palette(def.palette());
        this.ox = ox;
        this.y0 = y0;
        this.oz = oz;
        this.rng = new SplittableRandom(seed ^ 0x5DEECE66DL);
        this.noDecorRooms = noDecorRooms;
        this.noLightRooms = noLightRooms;
        this.arenaShape = arenaParams.str("shape", "circle");
        this.arenaTile = Math.max(2, arenaParams.integer("tile_size", 3));
    }

    public Palette palette() { return palette; }

    public BlockList build() {
        int w = layout.width(), d = layout.depth();
        Material liquid = liquid();
        BlockData secret = palette.first("secret").createBlockData();
        for (int z = 0; z < d; z++) {
            for (int x = 0; x < w; x++) {
                byte k = layout.kind(x, z);
                if (k == FloorLayout.VOID) {
                    int top = neighborTop(x, z);
                    if (top > 0) wall(x, z, top);
                    continue;
                }
                int h = layout.height(x, z);
                int e = layout.elevation(x, z);
                int top = Math.max(e + h, neighborTop(x, z) - 1);
                if (k == FloorLayout.GUTTER) {
                    out.add(ox + x, y0 - 1, oz + z, palette.data("floor", rng));
                    out.add(ox + x, y0, oz + z, (liquid == null ? Material.STONE_BRICKS : liquid).createBlockData());
                    if (liquid != null) out.add(ox + x, y0 + 1, oz + z, rail(x, z));
                } else {
                    // 계단 단상: 바닥 아래를 벽으로 받친다 (공허 월드라 비어 보이지 않게)
                    for (int y = 0; y < e; y++) out.add(ox + x, y0 + y, oz + z, palette.data("wall", rng));
                    out.add(ox + x, y0 + e, oz + z, floorBlock(x, z, k));
                    if (k == FloorLayout.STAIR) out.add(ox + x, y0 + e + 1, oz + z, stair(layout.stairFacing(x, z)));
                    if (k == FloorLayout.SECRET) {
                        for (int y = 1; y <= h; y++) out.add(ox + x, y0 + e + y, oz + z, secret);
                    }
                }
                out.add(ox + x, y0 + e + h + 1, oz + z, palette.data("ceiling", rng));
                for (int y = e + h + 2; y <= top + 1; y++) out.add(ox + x, y0 + y, oz + z, palette.data("wall", rng));
            }
        }
        lights();
        decor();
        return out;
    }

    private BlockData stair(int facing) {
        BlockData b = palette.stairs().createBlockData();
        if (b instanceof Stairs st) {
            st.setFacing(SIDES[Math.max(0, Math.min(3, facing))]);
            st.setHalf(org.bukkit.block.data.Bisected.Half.BOTTOM);
            st.setShape(Stairs.Shape.STRAIGHT);
        }
        return b;
    }

    /** 이 빌더의 목록 (방 소품을 더 넣을 때). */
    public BlockList list() { return out; }

    private Material liquid() {
        String l = def.liquid();
        if (l == null || l.isBlank() || "null".equalsIgnoreCase(l)) return null;
        return "LAVA".equalsIgnoreCase(l) ? Material.LAVA : Material.WATER;
    }

    /** 8방향 이웃 중 열린 타일의 최대 천장 높이 (바닥 높이 + 내부 높이 + 1). 없으면 0. */
    private int neighborTop(int x, int z) {
        int top = 0;
        for (int dz = -1; dz <= 1; dz++) {
            for (int dx = -1; dx <= 1; dx++) {
                if (dx == 0 && dz == 0) continue;
                if (layout.open(x + dx, z + dz)) {
                    top = Math.max(top, layout.elevation(x + dx, z + dz) + layout.height(x + dx, z + dz) + 1);
                }
            }
        }
        return top;
    }

    private void wall(int x, int z, int top) {
        boolean roomSide = false;
        for (BlockFace f : SIDES) {
            int r = layout.region(x + f.getModX(), z + f.getModZ());
            if (r >= 0 && layout.kind(x + f.getModX(), z + f.getModZ()) == FloorLayout.FLOOR) roomSide = true;
        }
        for (int y = 0; y <= top; y++) {
            BlockData b;
            if (y == 0 && roomSide) b = palette.first("accent").createBlockData();
            else if (roomSide && y == 1 && corner(x, z)) b = palette.first("accent").createBlockData();
            else b = palette.data("wall", rng);
            out.add(ox + x, y0 + y, oz + z, b);
        }
    }

    /** 방 모서리 기둥 (두 방향이 모두 벽). */
    private boolean corner(int x, int z) {
        int open = 0;
        for (BlockFace f : SIDES) if (layout.open(x + f.getModX(), z + f.getModZ())) open++;
        return open == 0;
    }

    private BlockData floorBlock(int x, int z, byte kind) {
        if (kind == FloorLayout.DOOR) return palette.first("accent").createBlockData();
        int region = layout.region(x, z);
        if (region >= 0 && region == layout.bossRoom().index()) {
            FloorLayout.Arena a = layout.arena();
            int dx = x - a.centerX(), dz = z - a.centerZ();
            double dist = Math.sqrt(dx * dx + dz * dz);
            switch (arenaShape) {
                case "tiled_circle" -> {
                    boolean seam = Math.floorMod(dx, arenaTile) == 0 || Math.floorMod(dz, arenaTile) == 0;
                    if (seam && dist <= a.radius()) return palette.first("accent").createBlockData();
                }
                case "clock_face" -> {
                    if (Math.abs(dist - (a.radius() - 2)) < 0.6) return palette.first("accent").createBlockData();
                    double ang = Math.toDegrees(Math.atan2(dz, dx));
                    if (dist > a.radius() - 5 && dist < a.radius() - 2 && Math.abs(((ang % 30) + 30) % 30 - 15) > 13)
                        return palette.first("accent").createBlockData();
                }
                default -> {
                    if (Math.abs(dist - (a.radius() - 1.5)) < 0.55 || dist < 1.6) return palette.first("accent").createBlockData();
                }
            }
        }
        return palette.data("floor", rng);
    }

    private BlockData rail(int x, int z) {
        BlockData b = Material.IRON_BARS.createBlockData();
        if (b instanceof MultipleFacing mf) {
            for (BlockFace f : SIDES) {
                byte nk = layout.kind(x + f.getModX(), z + f.getModZ());
                if (nk == FloorLayout.GUTTER || nk == FloorLayout.VOID) mf.setFace(f, true);
            }
        }
        return b;
    }

    // ── 조명 ─────────────────────────────────────────────────────────────

    private void lights() {
        Material solid = palette.solidLight();
        Material hang = palette.hangingLight();
        for (FloorLayout.RoomInfo r : layout.rooms()) {
            if (noLightRooms.contains(r.index())) continue;
            if (r.type() == RoomType.BOSS) {
                arenaLights(r, solid, hang);
                continue;
            }
            for (int z = r.minZ() + 3; z <= r.maxZ() - 2; z += 6) {
                for (int x = r.minX() + 3; x <= r.maxX() - 2; x += 6) placeLight(x, z, r.height(), solid, hang);
            }
        }
        // 복도: 3칸 폭 통로 가운데 줄 7칸마다
        for (int z = 0; z < layout.depth(); z++) {
            for (int x = 0; x < layout.width(); x++) {
                if (layout.kind(x, z) != FloorLayout.FLOOR || layout.region(x, z) >= 0) continue;
                if (Math.floorMod(x + z, 7) != 0) continue;
                boolean alongX = layout.walkable(x, z - 1) && layout.walkable(x, z + 1)
                        && !layout.walkable(x, z - 2) && !layout.walkable(x, z + 2);
                boolean alongZ = layout.walkable(x - 1, z) && layout.walkable(x + 1, z)
                        && !layout.walkable(x - 2, z) && !layout.walkable(x + 2, z);
                if (alongX || alongZ) placeLight(x, z, layout.elevation(x, z) + layout.height(x, z), solid, hang);
            }
        }
        // 복도 모양별 자리 (광장·기둥 숲·막다른 길 끝·좁은 통로·계단 단상·비밀방)
        for (int pk : layout.hallLights()) {
            int x = FloorLayout.unpackX(pk), z = FloorLayout.unpackZ(pk);
            if (!layout.walkable(x, z)) continue;
            placeLight(x, z, layout.elevation(x, z) + layout.height(x, z), solid, hang);
        }
    }

    private void placeLight(int x, int z, int h, Material solid, Material hang) {
        if (solid != null) {
            out.add(ox + x, y0 + h + 1, oz + z, solid.createBlockData());
        }
        if (hang != null && (solid == null || rng.nextDouble() < 0.4)) {
            BlockData b = hang.createBlockData();
            if (b instanceof Hangable hg) hg.setHanging(true);
            out.add(ox + x, y0 + h, oz + z, b);
        }
    }

    private void arenaLights(FloorLayout.RoomInfo r, Material solid, Material hang) {
        FloorLayout.Arena a = layout.arena();
        // 천장 링
        for (int i = 0; i < 12; i++) {
            double t = Math.PI * 2 * i / 12.0;
            int x = a.centerX() + (int) Math.round(Math.cos(t) * (a.radius() * 0.6));
            int z = a.centerZ() + (int) Math.round(Math.sin(t) * (a.radius() * 0.6));
            placeLight(x, z, a.height(), solid, hang);
        }
        // 바닥 받침대 위 등불 (높은 천장이라 바닥이 어두워지지 않게)
        Material lamp = hang != null ? hang : solid;
        if (lamp == null) return;
        for (int i = 0; i < 8; i++) {
            double t = Math.PI * 2 * (i + 0.5) / 8.0;
            int x = a.centerX() + (int) Math.round(Math.cos(t) * (a.radius() - 1));
            int z = a.centerZ() + (int) Math.round(Math.sin(t) * (a.radius() - 1));
            if (!layout.walkable(x, z)) continue;
            out.add(ox + x, y0 + 1, oz + z, palette.first("accent").createBlockData());
            BlockData b = lamp.createBlockData();
            if (b instanceof Hangable hg) hg.setHanging(false);
            out.add(ox + x, y0 + 2, oz + z, b);
        }
        // 추격 복도 조명
        if (a.corridorLength() > 0) {
            for (int z = a.centerZ() + a.radius() + 4; z <= a.centerZ() + a.radius() + a.corridorLength(); z += 6) {
                placeLight(a.centerX(), z, Math.min(a.height(), 10), solid, hang);
            }
        }
    }

    // ── 장식 (floors.yml decor) ───────────────────────────────────────────

    private void decor() {
        List<Params> decor = def.decor();
        if (decor.isEmpty()) return;
        int bossIdx = layout.bossRoom().index();
        java.util.Set<Integer> keepClear = new java.util.HashSet<>();
        for (FloorLayout.DeadEnd de : layout.deadEnds()) keepClear.add(FloorLayout.pack(de.tipX(), de.tipZ()));
        for (int z = 0; z < layout.depth(); z++) {
            for (int x = 0; x < layout.width(); x++) {
                if (layout.kind(x, z) != FloorLayout.FLOOR) continue;
                int region = layout.region(x, z);
                if (region >= 0 && noDecorRooms.contains(region)) continue;
                if (nearDoor(x, z)) continue;
                int h = layout.height(x, z);
                int e = layout.elevation(x, z);
                // 막다른 길 끝 칸·비밀방 바닥은 비워 둔다 (상자 자리)
                boolean clearFloor = keepClear.contains(FloorLayout.pack(x, z)) || layout.secretRoomAt(x, z) >= 0;
                int walls = 0;
                boolean wallNS = false, wallEW = false;
                BlockFace wallDir = null;
                for (BlockFace f : SIDES) {
                    if (!layout.open(x + f.getModX(), z + f.getModZ())) {
                        walls++;
                        wallDir = f;
                        if (f.getModZ() != 0) wallNS = true;
                        else wallEW = true;
                    }
                }
                for (Params p : decor) {
                    double chance = p.dbl("chance", 0);
                    if (rng.nextDouble() >= chance) continue;
                    Material m = Material.matchMaterial(p.str("block", ""));
                    if (m == null || !m.isBlock()) continue;
                    String where = p.str("where", "floor");
                    switch (where) {
                        case "floor" -> {
                            if (region == bossIdx || clearFloor) continue;
                            BlockData b = oriented(m, BlockFace.DOWN);
                            if (b != null) out.add(ox + x, y0 + e + 1, oz + z, b);
                        }
                        case "ceiling" -> {
                            BlockData b = oriented(m, BlockFace.UP);
                            if (b != null) out.add(ox + x, y0 + e + h, oz + z, b);
                        }
                        case "wall" -> {
                            if (walls == 0 || wallDir == null) continue;
                            BlockData b = oriented(m, wallDir);
                            int y = 1 + rng.nextInt(Math.max(1, h - 1));
                            if (b != null) out.add(ox + x, y0 + e + y, oz + z, b);
                        }
                        case "corner" -> {
                            // 두 벽이 직각으로 만나는 칸만 (한 칸 폭 좁은 통로를 거미줄이 막지 않게)
                            if (!(wallNS && wallEW) || region == bossIdx || clearFloor) continue;
                            BlockData b = oriented(m, BlockFace.DOWN);
                            if (b != null) out.add(ox + x, y0 + e + 1, oz + z, b);
                        }
                        default -> { }
                    }
                    break; // 한 타일에 장식 하나
                }
            }
        }
    }

    private boolean nearDoor(int x, int z) {
        for (int dz = -2; dz <= 2; dz++)
            for (int dx = -2; dx <= 2; dx++)
                if (layout.kind(x + dx, z + dz) == FloorLayout.DOOR) return true;
        return false;
    }

    /**
     * 붙는 면 기준으로 블록 상태를 맞춘다. attach = 블록이 붙는 쪽 (바닥이면 DOWN, 천장이면 UP, 벽이면 벽 방향).
     * 붙을 수 없는 조합이면 null.
     */
    private BlockData oriented(Material m, BlockFace attach) {
        BlockData b = m.createBlockData();
        if (b instanceof MultipleFacing mf) {
            if (!mf.getAllowedFaces().contains(attach)) {
                // 판유리·창살류(수평면만)는 벽 방향만, 바닥/천장이면 그냥 기둥
                return attach == BlockFace.UP || attach == BlockFace.DOWN ? b : null;
            }
            mf.setFace(attach, true);
        } else if (b instanceof Speleothem sp) {
            sp.setVerticalDirection(attach == BlockFace.UP ? BlockFace.DOWN : BlockFace.UP);
        } else if (b instanceof Directional dir) {
            BlockFace face = attach.getOppositeFace();
            if (dir.getFaces().contains(face)) dir.setFacing(face);
            else if (attach == BlockFace.DOWN || attach == BlockFace.UP) {
                BlockFace side = SIDES[rng.nextInt(4)];
                if (dir.getFaces().contains(side)) dir.setFacing(side);
            }
        } else if (b instanceof Rotatable rot) {
            rot.setRotation(SIDES[rng.nextInt(4)]);
        }
        if (b instanceof Hangable hg) hg.setHanging(attach == BlockFace.UP);
        if (b instanceof Lightable l) l.setLit(true);
        if (b instanceof Slab s) s.setType(Slab.Type.BOTTOM);
        return b;
    }
}
