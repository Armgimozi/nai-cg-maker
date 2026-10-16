package kr.labyrinth.dungeon.treasure;

import java.util.ArrayList;
import java.util.List;
import java.util.SplittableRandom;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
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
 *   <li>줄 (부드럽게, {@link kr.labyrinth.mobs.Leash}): 상자 자리에서 {@link #LEASH} 칸 밖의 대상은 줄 끝까지만 쫓아가 버티고(혀 끌어오기는
 *       거기서도 닿음), 줄 끝 근처({@link #REACH})의 대상에게는 도약으로 덮쳤다가 걸어서 돌아온다. 순간이동은 마지막 수단 —
 *       {@link #HARD_LEASH} 칸보다 멀리 · 높이가 크게 다름 · 줄 밖에서 {@link #STUCK_MS} 동안 못 돌아옴.</li>
 *   <li>멀리서 쏘기: 상자 자리 {@link #REACH} 칸 안에 살아 있는 파티원이 {@link #SULK_MS} 동안 없으면 상처가 아문다(초당 최대 HP 의
 *       {@link #REGEN_PER_SEC}) — 줄 밖에서 안전하게 잡을 수 없다.</li>
 *   <li>시간 ({@link MimicClock}): 잠김 시간({@code treasure.mimic_lock_seconds})은 상자 자리 {@link #PRESENCE} 칸 안에 살아 있는
 *       파티원이 있을 때만 흐르고, 맞으면 적어도 {@link #ENGAGED_MS} 로 늘어난다. 다 되면 깡충 달아난다({@link State#FLED}).</li>
 *   <li>끝: 큰 미믹(첫 몹)이 정말로 쓰러지면({@link CustomMob#killed()}) {@link State#DEFEATED} — 남은 새끼 미믹은 조용히 달아난다.
 *       큰 미믹이 쓰러지지 않고 사라졌으면(히트박스 유실·관리자 정리) 달아난 것과 같다(칭호 없음).</li>
 *   <li>mobs.yml 에 미믹이 없으면(직접 고친 옛 판) 예전처럼 층 일반 몹 {@code legacyCount} 마리가 기습한다 (dungeon.yml {@code treasure.mimic_mobs})
 *       — 그때는 모두 사라졌고 하나라도 쓰러졌으면 DEFEATED.</li>
 * </ul>
 * 층을 떠나면 FloorState.destroy 가 인스턴스 몹을 모두 지운다(이 몹들도 인스턴스 태그가 달려 있다).
 */
public final class MimicEncounter {

    public enum State { ALIVE, DEFEATED, FLED }

    /** 줄 길이(블록, 수평): 이보다 먼 대상은 줄 끝까지만 쫓는다. */
    public static final double LEASH = 8.0;
    /** 이보다 멀리(블록, 수평) 나가 있으면 상자 자리로 순간이동 (마지막 수단). */
    public static final double HARD_LEASH = 12.0;
    /** 줄 밖(LEASH + 1)에서 이 시간(ms) 동안 못 돌아오면(끼임) 순간이동. 도약 뒤 멈춤(약 2초)보다 길게. */
    public static final long STUCK_MS = 4_000;
    /** 미믹이 닿는 거리 = 줄 끝 + 도약 (블록, 상자 자리에서). */
    public static final double REACH = LEASH + kr.labyrinth.mobs.Leash.LUNGE_MARGIN;
    /** REACH 안에 아무도 없이 이 시간(ms)이 지나면 상처가 아물기 시작. */
    public static final long SULK_MS = 3_000;
    /** 상처가 아무는 빠르기 (초당 최대 HP 비율). */
    public static final double REGEN_PER_SEC = 0.08;
    /** 잠김 시간은 상자 자리 이만큼(블록) 안에 살아 있는 파티원이 있을 때만 흐른다. */
    public static final double PRESENCE = 12.0;
    /** 마지막으로 맞은 뒤 이 시간(ms) 동안은 달아나지 않는다. */
    public static final long ENGAGED_MS = 12_000;
    /** 큰 미믹이 쓰러진 뒤 이만큼(ms) 지나 끝 — 쓰러지는 몸짓(뚜껑이 닫히며 가라앉음)을 다 보여 주고 상자가 나타나게. */
    public static final long RESTORE_DELAY_MS = 700;
    /** 달아나는 몸짓(깡충 뛰어올라 사라짐) 틱 — 상자는 그 뒤에 나타난다. */
    public static final long FLEE_TICKS = 8;

    private final FloorState fs;
    private final Location spot;
    private final List<CustomMob> mobs = new ArrayList<>();
    private final List<Double> lastHp = new ArrayList<>();
    private final List<Long> outsideSince = new ArrayList<>();
    private final boolean legacy;
    private final MimicClock clock;
    private long deadAt = -1;
    private long lonelySince = -1;
    private long lastRegenAt = -1;
    private boolean sulkTold;
    private boolean finished;

    private MimicEncounter(FloorState fs, Location spot, boolean legacy, long lockMs) {
        this.fs = fs;
        this.spot = spot;
        this.legacy = legacy;
        this.clock = new MimicClock(lockMs, ENGAGED_MS);
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
        MimicEncounter e = new MimicEncounter(fs, spot, pack.isEmpty(), Math.max(5, lockSeconds) * 1000L);
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
        outsideSince.add(-1L);
        if (!legacy) m.leash(spot, LEASH);
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

    /**
     * 2틱마다: 맞았는지 · 줄(마지막 수단) · 멀리서 쏘기(상처 아묾) · 끝났는지. 큰 미믹이 쓰러지면 {@link #RESTORE_DELAY_MS} 뒤 DEFEATED,
     * 쓰러지지 않고 사라졌거나 시간이 다 되면 FLED. 끝나면 부르는 쪽이 {@link #finish} 를 한 번 부른다.
     */
    public State tick(long nowMs) {
        if (finished) return State.FLED;
        boolean hit = false, any = false;
        for (int i = 0; i < mobs.size(); i++) {
            CustomMob m = mobs.get(i);
            if (!FloorState.alive(m)) continue;
            any = true;
            double h = m.health();
            if (h < lastHp.get(i) - 1e-6) hit = true;
            lastHp.set(i, h);
            if (!legacy) hardLeash(i, m, nowMs);
        }
        if (legacy) {
            if (!any) {
                if (deadAt < 0) deadAt = nowMs;
                if (nowMs - deadAt < RESTORE_DELAY_MS) return State.ALIVE;
                for (CustomMob m : mobs) if (m.killed()) return State.DEFEATED;
                return State.FLED;
            }
        } else {
            CustomMob main = mobs.isEmpty() ? null : mobs.get(0);
            if (main == null || !FloorState.alive(main)) {
                if (main == null || !main.killed()) return State.FLED;   // 쓰러지지 않고 사라짐 = 달아난 것과 같다
                if (deadAt < 0) deadAt = nowMs;
                return nowMs - deadAt >= RESTORE_DELAY_MS ? State.DEFEATED : State.ALIVE;
            }
            sulk(nowMs, anyoneWithin(REACH));
        }
        return clock.tick(nowMs, anyoneWithin(PRESENCE), hit) ? State.FLED : State.ALIVE;
    }

    /** 상자 자리 r 칸(수평, 높이 차 4 미만) 안에 살아 있는 파티원이 있나. */
    private boolean anyoneWithin(double r) {
        for (Player p : fs.alivePlayers()) {
            Location l = p.getLocation();
            if (l.getWorld() != spot.getWorld() || Math.abs(l.getY() - spot.getY()) >= 4) continue;
            double dx = l.getX() - spot.getX(), dz = l.getZ() - spot.getZ();
            if (dx * dx + dz * dz <= r * r) return true;
        }
        return false;
    }

    /** 닿는 거리 안에 아무도 없이 {@link #SULK_MS} 가 지나면 상처가 아문다 (멀리서 안전하게 쏴서 잡지 못하게). */
    private void sulk(long nowMs, boolean someoneInReach) {
        if (someoneInReach) {
            lonelySince = -1;
            lastRegenAt = -1;
            sulkTold = false;
            return;
        }
        if (lonelySince < 0) lonelySince = nowMs;
        if (nowMs - lonelySince < SULK_MS) return;
        long dt = lastRegenAt < 0 ? 100 : Math.max(0, Math.min(MimicClock.MAX_STEP_MS, nowMs - lastRegenAt));
        boolean fx = lastRegenAt < 0 || nowMs / 1000 != lastRegenAt / 1000;
        lastRegenAt = nowMs;
        for (CustomMob m : mobs) {
            if (!FloorState.alive(m) || m.health() >= m.maxHealth() - 1e-6) continue;
            double healed = m.heal(m.maxHealth() * REGEN_PER_SEC * dt / 1000.0);
            if (healed > 0 && fx) {
                fs.world().spawnParticle(Particle.HAPPY_VILLAGER, m.location().add(0, 0.8, 0), 4, 0.35, 0.3, 0.35, 0);
                if (!sulkTold) {
                    sulkTold = true;
                    fs.sound(m.location(), Sound.BLOCK_CHEST_CLOSE, 0.6f, 0.5f);
                    for (Player p : fs.alivePlayers()) {
                        if (p.getWorld() == spot.getWorld() && p.getLocation().distanceSquared(spot) <= 32 * 32) {
                            fs.services().hud().actionBar(p, Text.mm("<gray>미믹이 상처를 아물리고 있다. 가까이 가서 싸우자."), 50);
                        }
                    }
                }
            }
        }
    }

    /** 마지막 수단의 줄: 너무 멀리 · 높이가 크게 다름 · 줄 밖에서 오래 못 돌아옴 → 상자 자리로 깡충 순간이동. */
    private void hardLeash(int i, CustomMob m, long nowMs) {
        Location at = m.location();
        if (at.getWorld() != spot.getWorld()) return;
        double dx = at.getX() - spot.getX(), dz = at.getZ() - spot.getZ();
        double d2 = dx * dx + dz * dz;
        boolean outside = d2 > (LEASH + 1) * (LEASH + 1);
        if (!outside) outsideSince.set(i, -1L);
        else if (outsideSince.get(i) < 0) outsideSince.set(i, nowMs);
        boolean stuck = outside && nowMs - outsideSince.get(i) >= STUCK_MS;
        if (d2 <= HARD_LEASH * HARD_LEASH && Math.abs(at.getY() - spot.getY()) < 4 && !stuck) return;
        outsideSince.set(i, -1L);
        Location back = spot.clone();
        back.setYaw(at.getYaw());
        fs.world().spawnParticle(Particle.POOF, at.clone().add(0, 0.5, 0), 8, 0.3, 0.3, 0.3, 0.02);
        m.entity().teleport(back);
        m.entity().setVelocity(new Vector(0, 0.25, 0));
        fs.world().spawnParticle(Particle.BLOCK, back.clone().add(0, 0.5, 0), 14, 0.3, 0.3, 0.3, 0.05,
                Material.OAK_PLANKS.createBlockData());
        fs.sound(back, Sound.BLOCK_CHEST_CLOSE, 0.8f, 0.6f);
    }

    /**
     * 끝 (한 번만): 살아 남은 미믹(시간이 다 됨 · 큰 미믹이 쓰러진 뒤 남은 새끼)은 깡충 뛰어올라 사라지고, restore(상자가 다시 나타남)는
     * 그 몸짓이 끝난 뒤({@link #FLEE_TICKS}) — 남은 미믹이 없으면 바로. 층이 그 사이에 사라졌으면 부르지 않는다.
     */
    public void finish(Runnable restore) {
        if (finished) return;
        finished = true;
        if (flee() == 0) {
            restore.run();
            return;
        }
        Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> {
            if (!fs.destroyed()) restore.run();
        }, FLEE_TICKS + 1);
    }

    /** 살아 있는 미믹이 깡충 뛰어올라 사라진다. @return 달아난 수 */
    private int flee() {
        int n = 0;
        for (CustomMob m : mobs) {
            if (!FloorState.alive(m)) continue;
            n++;
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
            }, FLEE_TICKS);
        }
        return n;
    }

    /** 남은 달아날 시간(ms, 자가 진단·시험). */
    public long remainingMs() { return clock.remaining(); }

    /** 자가 진단: 달아날 시간이 다 된 것으로 (다음 {@link #tick} 이 FLED). */
    public void expireForTest() { clock.expire(); }

    /** 살아 있는 미믹 수. */
    public int aliveCount() {
        int n = 0;
        for (CustomMob m : mobs) if (FloorState.alive(m)) n++;
        return n;
    }

    /**
     * 자가 진단: 살아 있는 미믹을 모두 정말로 쓰러뜨린다 (큰 미믹 먼저, 피해 경로 그대로 — 사람 없이 보상 없음). @return 쓰러뜨린 수
     */
    public int killAllForTest() {
        int n = 0;
        for (CustomMob m : mobs) {
            if (!FloorState.alive(m)) continue;
            double amount = m.maxHealth() * 2 + 1000;
            fs.services().damage().deal(DamageContext.raw(null, m.entity(), amount, DamageType.TRUE));
            if (m.killed()) n++;
        }
        return n;
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
