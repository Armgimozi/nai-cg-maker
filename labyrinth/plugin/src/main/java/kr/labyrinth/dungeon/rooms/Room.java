package kr.labyrinth.dungeon.rooms;

import java.util.ArrayList;
import java.util.List;
import java.util.SplittableRandom;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.gen.RoomType;
import kr.labyrinth.mobs.CustomMob;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.MultipleFacing;
import org.bukkit.entity.Player;
import org.bukkit.event.block.Action;

/**
 * 층 안의 방 하나 (런타임). 상태 IDLE → ACTIVE → CLEARED. 문 잠금/해제, 몹 추적, 내부 판정 공통.
 * 구현: {@link BattleRoom}(전투·엘리트), {@link TreasureRoom}, {@link RestRoom}, {@link StartRoom}, {@link BossRoom},
 * {@link GimmickRoom} 하위 10종 (rooms/gimmicks).
 */
public abstract class Room {

    public enum State { IDLE, ACTIVE, CLEARED }

    protected final FloorState fs;
    protected final FloorLayout.RoomInfo info;
    protected final SplittableRandom rng;
    protected State state = State.IDLE;
    protected final List<CustomMob> mobs = new ArrayList<>();
    private boolean locked;
    /** 안에 살아 있는 파티원이 없던 시간(틱) — 고착 방지 초기화용. */
    protected int emptyTicks;

    protected Room(FloorState fs, FloorLayout.RoomInfo info) {
        this.fs = fs;
        this.info = info;
        this.rng = new SplittableRandom(fs.seed() * 31 + info.index() * 7919L);
    }

    public FloorLayout.RoomInfo info() { return info; }
    public RoomType type() { return info.type(); }
    public State state() { return state; }
    public boolean cleared() { return state == State.CLEARED; }
    public boolean isLocked() { return locked; }

    /** 장식 대신 방 소품을 블록 목록에 넣는다 (층 생성 시, 월드 좌표). */
    public void prepare(BlockList list) {}

    /** 블록 배치가 끝난 뒤 (표시 엔티티·NPC 소환). */
    public void onReady() {}

    /** 살아 있는 파티원이 방 내부(출입구 제외)에 들어왔다 (들어올 때마다). */
    public void onEnter(Player p) {}

    /** 2틱마다. */
    public void tick(long t) {}

    /** 블록 상호작용 (이 방 안의 블록일 때만 호출). @return 처리했으면 true (이벤트 취소) */
    public boolean onInteract(Player p, Block block, Action action) { return false; }

    /** 투사체가 이 방 안 블록에 맞음. */
    public void onProjectileHit(Player shooter, Block block) {}

    /** 파티 전멸 (인스턴스 종료 직전). 진행 중인 보스전·시련을 실패로 기록하는 데 쓴다 (점진 힌트). */
    public void onWipe() {}

    /** 층 정리 시. */
    public void onDestroy() {
        removeMobs();
    }

    /** 장식·조명을 넣지 말아야 하는 방 (기믹방 가독성). */
    public boolean wantsDecor() { return true; }

    public boolean wantsLights() { return true; }

    // ── 판정 ──────────────────────────────────────────────────────────────

    public boolean isInside(Location loc) {
        if (!fs.onThisFloor(loc)) return false;
        return fs.layout().interior(fs.tileX(loc), fs.tileZ(loc), info.index());
    }

    public boolean isInsideOrDoor(Location loc) {
        if (!fs.onThisFloor(loc)) return false;
        return fs.layout().region(fs.tileX(loc), fs.tileZ(loc)) == info.index();
    }

    public List<Player> alivePlayersInside() {
        List<Player> out = new ArrayList<>();
        for (Player p : fs.alivePlayers()) if (isInsideOrDoor(p.getLocation())) out.add(p);
        return out;
    }

    public boolean containsBlock(Block b) {
        if (!fs.onThisFloor(b.getLocation())) return false;
        int tx = b.getX() - fs.ox(), tz = b.getZ() - fs.oz();
        return tx >= info.minX() - 1 && tx <= info.maxX() + 1 && tz >= info.minZ() - 1 && tz <= info.maxZ() + 1;
    }

    public Location center() { return fs.tile(info.centerX(), info.centerZ(), 1); }

    /** 출입구에서 dist 이상 떨어진 무작위 내부 타일 중심. */
    public Location randomSpot(int minDoorDist) {
        for (int i = 0; i < 40; i++) {
            int x = info.minX() + 1 + rng.nextInt(Math.max(1, info.width() - 2));
            int z = info.minZ() + 1 + rng.nextInt(Math.max(1, info.depth() - 2));
            if (!fs.layout().interior(x, z, info.index())) continue;
            if (doorDistance(x, z) < minDoorDist) continue;
            Block b = fs.world().getBlockAt(fs.ox() + x, fs.y0() + 1, fs.oz() + z);
            if (!b.isPassable()) continue;
            return fs.tile(x, z, 1);
        }
        return center();
    }

    protected int doorDistance(int x, int z) {
        int best = Integer.MAX_VALUE;
        for (int d : info.doors()) {
            int dx = Math.abs(FloorLayout.unpackX(d) - x), dz = Math.abs(FloorLayout.unpackZ(d) - z);
            best = Math.min(best, dx + dz);
        }
        return best;
    }

    // ── 문 ────────────────────────────────────────────────────────────────

    public void lock() {
        if (locked) return;
        locked = true;
        // 출입구 위에 선 사람은 안쪽으로 밀어 넣는다
        for (Player p : fs.allPlayers()) {
            Location l = p.getLocation();
            if (!fs.onThisFloor(l)) continue;
            int tx = fs.tileX(l), tz = fs.tileZ(l);
            if (fs.layout().kind(tx, tz) == FloorLayout.DOOR && fs.layout().region(tx, tz) == info.index()) {
                Location in = inward(tx, tz);
                in.setYaw(l.getYaw());
                in.setPitch(l.getPitch());
                kr.labyrinth.core.Teleports.to(p, in);
            }
        }
        BlockData bars = Material.IRON_BARS.createBlockData();
        for (int d : info.doors()) {
            int x = FloorLayout.unpackX(d), z = FloorLayout.unpackZ(d);
            int h = fs.layout().height(x, z);
            for (int y = 1; y <= h; y++) fs.setBlock(x, y, z, barsFor(x, z, bars));
        }
        Location c = center();
        c.getWorld().playSound(c, Sound.BLOCK_IRON_DOOR_CLOSE, 1.0f, 0.6f);
        c.getWorld().playSound(c, Sound.BLOCK_CHAIN_PLACE, 1.0f, 0.5f);
    }

    public void unlock() {
        if (!locked) return;
        locked = false;
        BlockData air = Material.AIR.createBlockData();
        for (int d : info.doors()) {
            int x = FloorLayout.unpackX(d), z = FloorLayout.unpackZ(d);
            int h = fs.layout().height(x, z);
            for (int y = 1; y <= h; y++) fs.setBlock(x, y, z, air);
            fs.world().spawnParticle(org.bukkit.Particle.CLOUD, fs.tile(x, z, 1.5), 4, 0.3, 0.6, 0.3, 0.01);
        }
        Location c = center();
        c.getWorld().playSound(c, Sound.BLOCK_IRON_DOOR_OPEN, 1.0f, 0.8f);
    }

    private BlockData barsFor(int x, int z, BlockData base) {
        BlockData b = base.clone();
        if (b instanceof MultipleFacing mf) {
            for (BlockFace f : new BlockFace[] {BlockFace.NORTH, BlockFace.EAST, BlockFace.SOUTH, BlockFace.WEST}) {
                int nx = x + f.getModX(), nz = z + f.getModZ();
                byte k = fs.layout().kind(nx, nz);
                boolean sameDoor = k == FloorLayout.DOOR && fs.layout().region(nx, nz) == info.index();
                if (sameDoor || k == FloorLayout.VOID) mf.setFace(f, true);
            }
        }
        return b;
    }

    /** 출입구 타일에서 방 안쪽으로 2칸. */
    private Location inward(int x, int z) {
        int dx = Integer.signum(info.centerX() - x), dz = Integer.signum(info.centerZ() - z);
        if (Math.abs(info.centerX() - x) > Math.abs(info.centerZ() - z)) dz = 0;
        else dx = 0;
        return fs.tile(x + dx * 2, z + dz * 2, 1);
    }

    // ── 몹 ────────────────────────────────────────────────────────────────

    protected CustomMob spawn(String mobId, Location at) {
        CustomMob m = fs.spawnMob(mobId, at);
        if (m != null) mobs.add(m);
        return m;
    }

    protected int aliveMobs() {
        mobs.removeIf(m -> !FloorState.alive(m));
        return mobs.size();
    }

    protected void removeMobs() {
        for (CustomMob m : mobs) {
            try {
                m.remove();
            } catch (Throwable ignored) {
                // 이미 사라짐
            }
        }
        mobs.clear();
    }

    /** 고착 방지: 활성 상태인데 안에 살아 있는 파티원이 없으면 true (틱 누적). */
    protected boolean abandoned(int ticksLimit) {
        if (alivePlayersInside().isEmpty()) emptyTicks += 2;
        else emptyTicks = 0;
        return emptyTicks >= ticksLimit;
    }
}
