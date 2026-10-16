package kr.labyrinth.dungeon.treasure;

import java.util.ArrayList;
import java.util.List;
import java.util.SplittableRandom;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.mobs.CustomMob;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/**
 * 미믹 한 번 (미로 상자 {@link Treasures} · 보물방 {@code rooms.TreasureRoom} 공용, GDD §5.6). 상자가 사라진 자리에서 미믹 무리
 * ({@link MimicSpec#pack}: 큰 미믹 + 깊은 층이면 작은 미믹 하나, 층 수치)가 연 사람을 보고 튀어나온다. 부르는 쪽이 2틱마다 {@link #tick}.
 * <ul>
 *   <li>줄: 상자 자리에서 {@link #LEASH} 칸보다 멀어지거나 높이가 크게 달라지면 깡충 되돌아온다(나무 가루 + 덜컥).</li>
 *   <li>시간: 잠김 시간({@code treasure.mimic_lock_seconds})이 지나면 깡충 달아난다({@link State#FLED}). 맞고 있는 동안은
 *       마지막으로 맞은 뒤 {@link #ENGAGED_MS} 까지 미룬다(싸우는 도중에 사라지지 않게).</li>
 *   <li>mobs.yml 에 미믹이 없으면(직접 고친 옛 판) 예전처럼 층 일반 몹 {@code legacyCount} 마리가 기습한다 (dungeon.yml {@code treasure.mimic_mobs}).</li>
 * </ul>
 * 층을 떠나면 FloorState.destroy 가 인스턴스 몹을 모두 지운다(이 몹들도 인스턴스 태그가 달려 있다).
 */
public final class MimicEncounter {

    public enum State { ALIVE, DEFEATED, FLED }

    /** 상자 자리에서 이만큼(블록, 수평) 멀어지면 되돌아온다. */
    public static final double LEASH = 8.0;
    /** 마지막으로 맞은 뒤 이 시간(ms) 동안은 달아나지 않는다. */
    public static final long ENGAGED_MS = 12_000;
    /** 다 쓰러진 뒤 이만큼(ms) 지나 끝 — 쓰러지는 몸짓(뚜껑이 닫히며 가라앉음)을 다 보여 주고 상자가 나타나게. */
    public static final long RESTORE_DELAY_MS = 700;

    private final FloorState fs;
    private final Location spot;
    private final List<CustomMob> mobs = new ArrayList<>();
    private final List<Double> lastHp = new ArrayList<>();
    private final boolean legacy;
    private long deadline;
    private long deadAt = -1;

    private MimicEncounter(FloorState fs, Location spot, boolean legacy, long deadline) {
        this.fs = fs;
        this.spot = spot;
        this.legacy = legacy;
        this.deadline = deadline;
    }

    /**
     * 상자 자리(타일 tx, tz · 발 높이 dy)에서 미믹을 깨운다. 상자 블록은 부르는 쪽이 먼저 지운다.
     * @param dirX/dirZ 상자가 바라보는 쪽 (작은 미믹 자리 · 연 사람이 없을 때 바라볼 쪽)
     * @param opener 연 사람 (자가 진단 = null) — 미믹이 이 사람을 바라보고 노린다
     */
    public static MimicEncounter spring(FloorState fs, int tx, int tz, double dy, int dirX, int dirZ, Player opener,
                                        int lockSeconds, int legacyCount, SplittableRandom rng) {
        Location spot = fs.tile(tx, tz, dy);
        Vector look = opener != null && opener.getWorld() == spot.getWorld()
                ? opener.getLocation().toVector().subtract(spot.toVector()).setY(0) : new Vector(dirX, 0, dirZ);
        if (look.lengthSquared() < 1e-4) look = new Vector(dirX == 0 && dirZ == 0 ? 1 : dirX, 0, dirZ);
        spot.setDirection(look);
        spot.setPitch(0);
        List<MobDef> pack;
        try {
            pack = MimicSpec.pack(fs.services().content(), fs.floor());
        } catch (Throwable t) {
            Log.error("미믹 정의 읽기 실패 — 층 일반 몹으로 대신", t);
            pack = List.of();
        }
        MimicEncounter e = new MimicEncounter(fs, spot, pack.isEmpty(), System.currentTimeMillis() + Math.max(5, lockSeconds) * 1000L);
        burst(fs, spot);
        if (e.legacy) {
            // 옛 판 mobs.yml (미믹 몹 없음): 예전처럼 층 일반 몹이 기습
            FloorLayout l = fs.layout();
            for (int k = 0; k < Math.max(1, legacyCount); k++) {
                int fx = tx + dirX * (1 + k % 3), fz = tz + dirZ * (1 + k % 3);
                Location at = l.walkable(fx, fz) ? fs.tile(fx, fz, l.standHeight(fx, fz)) : spot.clone();
                at.add(rng.nextDouble() - 0.5, 0, rng.nextDouble() - 0.5);
                e.add(fs.spawnMob(fs.randomFloorMob(rng), at), opener);
            }
            return e;
        }
        e.add(fs.spawnMob(pack.get(0), spot.clone()), opener);
        for (int k = 1; k < pack.size(); k++) e.add(fs.spawnMob(pack.get(k), companionSpot(fs, tx, tz, dy, dirX, dirZ, spot)), opener);
        return e;
    }

    /** 작은 미믹 자리: 상자 앞 → 앞 왼쪽·오른쪽 → 옆 중 걸을 수 있는 첫 칸 (없으면 상자 자리 옆 반 칸). */
    private static Location companionSpot(FloorState fs, int tx, int tz, double dy, int dirX, int dirZ, Location spot) {
        FloorLayout l = fs.layout();
        int sx = -dirZ, sz = dirX;   // 옆
        int[][] cands = {{dirX, dirZ}, {dirX + sx, dirZ + sz}, {dirX - sx, dirZ - sz}, {sx, sz}, {-sx, -sz}};
        for (int[] d : cands) {
            int x = tx + d[0], z = tz + d[1];
            if (!l.walkable(x, z) || Math.abs(l.standHeight(x, z) - dy) > 1.01) continue;
            Location at = fs.tile(x, z, l.standHeight(x, z));
            at.setYaw(spot.getYaw());
            return at;
        }
        return spot.clone().add(sx * 0.5, 0, sz * 0.5);
    }

    private void add(CustomMob m, Player opener) {
        if (m == null) return;
        mobs.add(m);
        lastHp.add(m.health());
        if (opener != null) {
            try {
                m.addThreat(opener, 20);
            } catch (Throwable ignored) {
                // 위협 표가 없는 구현
            }
        }
    }

    /** 상자가 미믹으로 깨는 순간: 나무 조각 + 덥석. */
    private static void burst(FloorState fs, Location spot) {
        Location c = spot.clone().add(0, 0.5, 0);
        BlockData wood = Material.OAK_PLANKS.createBlockData();
        fs.world().spawnParticle(Particle.BLOCK, c, 40, 0.35, 0.35, 0.35, 0.1, wood);
        fs.world().spawnParticle(Particle.POOF, c, 10, 0.35, 0.3, 0.35, 0.03);
        fs.sound(c, Sound.BLOCK_CHEST_OPEN, 1.0f, 0.5f);
        fs.sound(c, Sound.ENTITY_EVOKER_FANGS_ATTACK, 1.0f, 0.8f);
        fs.sound(c, Sound.BLOCK_WOOD_BREAK, 0.9f, 0.7f);
    }

    /** 상자 자리 (발 높이, 미믹이 처음 바라본 쪽). */
    public Location spot() { return spot.clone(); }

    /** 나온 몹 수 (자가 진단). */
    public int count() { return mobs.size(); }

    /** 예전처럼 층 일반 몹이 나왔나 (mobs.yml 에 미믹 없음). */
    public boolean legacy() { return legacy; }

    public List<CustomMob> mobs() { return List.copyOf(mobs); }

    /** 2틱마다: 맞았는지(달아날 시간 미루기)·줄·끝났는지 (다 쓰러지면 {@link #RESTORE_DELAY_MS} 뒤 DEFEATED). */
    public State tick(long nowMs) {
        boolean any = false;
        for (int i = 0; i < mobs.size(); i++) {
            CustomMob m = mobs.get(i);
            if (!FloorState.alive(m)) continue;
            any = true;
            double h = m.health();
            if (h < lastHp.get(i) - 1e-6) deadline = Math.max(deadline, nowMs + ENGAGED_MS);
            lastHp.set(i, h);
            if (!legacy) leash(m);
        }
        if (!any) {
            if (deadAt < 0) deadAt = nowMs;
            return nowMs - deadAt >= RESTORE_DELAY_MS ? State.DEFEATED : State.ALIVE;
        }
        return nowMs >= deadline ? State.FLED : State.ALIVE;
    }

    /** 상자 자리에서 너무 멀어진 미믹을 깡충 되돌린다. */
    private void leash(CustomMob m) {
        Location at = m.location();
        if (at.getWorld() != spot.getWorld()) return;
        double dx = at.getX() - spot.getX(), dz = at.getZ() - spot.getZ();
        if (dx * dx + dz * dz <= LEASH * LEASH && Math.abs(at.getY() - spot.getY()) < 4) return;
        Location back = spot.clone();
        back.setYaw(at.getYaw());
        fs.world().spawnParticle(Particle.POOF, at.clone().add(0, 0.5, 0), 8, 0.3, 0.3, 0.3, 0.02);
        m.entity().teleport(back);
        m.entity().setVelocity(new Vector(0, 0.25, 0));
        fs.world().spawnParticle(Particle.BLOCK, back.clone().add(0, 0.5, 0), 14, 0.3, 0.3, 0.3, 0.05,
                Material.OAK_PLANKS.createBlockData());
        fs.sound(back, Sound.BLOCK_CHEST_CLOSE, 0.8f, 0.6f);
    }

    /** 시간이 다 됨: 살아 있는 미믹이 깡충 뛰어올라 사라진다. */
    public void flee() {
        for (CustomMob m : mobs) {
            if (!FloorState.alive(m)) continue;
            Location at = m.location();
            m.entity().setVelocity(new Vector(0, 0.55, 0));
            fs.sound(at, Sound.ENTITY_GOAT_LONG_JUMP, 0.8f, 1.2f);
            fs.sound(at, Sound.BLOCK_CHEST_CLOSE, 0.9f, 0.8f);
            Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> {
                if (!FloorState.alive(m)) return;
                Location l = m.location().add(0, 0.5, 0);
                fs.world().spawnParticle(Particle.POOF, l, 16, 0.35, 0.35, 0.35, 0.04);
                fs.world().spawnParticle(Particle.BLOCK, l, 18, 0.3, 0.3, 0.3, 0.05, Material.OAK_PLANKS.createBlockData());
                m.remove();
            }, 8L);
        }
    }

    /** 보상 없이 모두 지운다 (자가 진단). */
    public void removeAll() {
        for (CustomMob m : mobs) {
            try {
                m.remove();
            } catch (Throwable ignored) {
                // 이미 사라짐
            }
        }
    }
}
