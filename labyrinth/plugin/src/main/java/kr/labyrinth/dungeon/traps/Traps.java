package kr.labyrinth.dungeon.traps;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;
import java.util.UUID;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.DungeonConfig;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.gen.Palette;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.Directional;
import org.bukkit.block.data.MultipleFacing;
import org.bukkit.block.data.type.Speleothem;
import org.bukkit.block.data.type.Stairs;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Display;
import org.bukkit.entity.Player;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 한 층의 함정 런타임 (GDD §5.5). 판정은 "함정 칸 집합(packed 타일 → 함정 번호)" 조회만 — 인스턴스 안 살아 있는 파티원만 본다.
 * <ul>
 *   <li>밟기 함정: 발이 바닥 높이에 닿은 채 함정 칸에 서면 → 경고 시간(난이도 telegraph 배율) 뒤 발동 → 재장전(cooldown) 또는 한 번만.</li>
 *   <li>주기 함정(화염 분사·수정 광선·회전 톱날): 근처(32칸)에 파티원이 있을 때만 박자대로 — 틈에 지나간다.</li>
 *   <li>티: 층마다 살짝 다른 바닥 블록(traps.mark)·천장 금·실·벽 발사구·얼음 + 가까이 가면 가끔 작은 입자.</li>
 *   <li>해제: 함정 칸 옆(또는 위)에서 웅크린 채 {@code traps.disarm_seconds} → 해제 + 골드·경험치. 그림자 직업은 1초, 10칸 안 함정 윤곽이 보인다.</li>
 *   <li>피해 = 최대 HP 비율 TRUE 피해 × 층·난이도 배율 ({@link TrapMath}) — 파티 인원 무관.</li>
 * </ul>
 * 블록 변경은 전부 {@link FloorState#setBlock} (정리 목록 기록) 또는 층 생성 목록 — 인스턴스 정리 때 함께 사라진다.
 */
public final class Traps {

    private static final Color SHADOW = Color.fromRGB(0xB07CFF);
    private static final Color POISON = Color.fromRGB(0x7FD14A);
    private static final Color BEAM = Color.fromRGB(0xF2A3FF);
    private static final Color WARN = Color.fromRGB(0xFF4A3A);

    private final FloorState fs;
    private final List<TrapSpot> spots;
    private final Map<Integer, Integer> byTile = new HashMap<>();
    private final St[] st;
    private final Map<UUID, int[]> disarming = new HashMap<>();
    /** 플레이어별 직전 판정(2틱 전) 자리 — 물살이 들어온 쪽을 알아내는 데 쓴다. */
    private final Map<UUID, Location> lastSeen = new HashMap<>();
    private final SplittableRandom rng;
    private BlockData mark;
    private BlockData floorData;
    private BlockData wallData;
    private BlockData ceilingMark;
    private int triggered;
    private int disarmedCount;

    /** 함정 하나의 런타임 상태. */
    private static final class St {
        boolean off;
        long cooldownUntil;
        long fireAt = -1;
        long activeUntil = -1;
        long restoreAt = -1;
        long damageAt = -1;
        boolean pitOpen;
        boolean announced;
        BlockDisplay saw;
        float sawYaw;
        final Map<UUID, Long> lastHit = new HashMap<>();
        /** 물살: 경고 중 함정 칸에 처음 보인 플레이어의 들어오기 직전 자리 (함정 가운데 기준, along 축 성분). */
        final Map<UUID, Double> entry = new HashMap<>();
    }

    public Traps(FloorState fs, List<TrapSpot> spots) {
        this.fs = fs;
        this.spots = List.copyOf(spots);
        this.st = new St[spots.size()];
        for (int i = 0; i < st.length; i++) st[i] = new St();
        for (TrapSpot s : this.spots) for (int t : s.tiles()) byTile.put(t, s.index());
        this.rng = new SplittableRandom(fs.seed() ^ 0x3D4E5F61L);
    }

    public List<TrapSpot> spots() { return spots; }
    public int count() { return spots.size(); }
    public int triggeredCount() { return triggered; }
    public int disarmedCount() { return disarmedCount; }
    public boolean isOff(int index) { return index >= 0 && index < st.length && st[index].off; }

    /** 그 칸의 함정 번호 (없으면 -1). */
    public int trapAt(int x, int z) { return byTile.getOrDefault(FloorLayout.pack(x, z), -1); }

    // ── 생성 (층 블록 목록에 표시·구덩이 넣기) ─────────────────────────────

    public void prepare(BlockList list, Palette palette, String markName) {
        floorData = palette.first("floor").createBlockData();
        wallData = palette.first("wall").createBlockData();
        Material m = markName == null ? null : Material.matchMaterial(markName);
        mark = (m != null && m.isBlock() ? m : palette.first("floor")).createBlockData();
        ceilingMark = palette.first("secret").createBlockData();
        FloorLayout l = fs.layout();
        int ox = fs.ox(), y0 = fs.y0(), oz = fs.oz();
        for (TrapSpot s : spots) {
            int e = s.elevation();
            switch (s.type()) {
                case ICE_SLIDE -> {
                    for (int t : s.tiles()) list.add(ox + ux(t), y0 + e, oz + uz(t), Material.BLUE_ICE.createBlockData());
                }
                case ARROW_WALL -> {
                    BlockData wire = tripwire(s);
                    for (int t : s.tiles()) list.add(ox + ux(t), y0 + e + 1, oz + uz(t), wire);
                    for (int i = 0; i < s.walls().length; i++) {
                        int w = s.walls()[i];
                        BlockData d = Material.DISPENSER.createBlockData();
                        int sx = i == 0 ? s.crossX() : -s.crossX(), sz = i == 0 ? s.crossZ() : -s.crossZ();
                        if (d instanceof Directional dir) dir.setFacing(face(sx, sz));
                        list.add(ox + ux(w), y0 + e + 2, oz + uz(w), d);
                    }
                }
                case CRYSTAL_BEAM -> {
                    for (int t : s.tiles()) list.add(ox + ux(t), y0 + e, oz + uz(t), mark);
                    for (int w : s.walls()) list.add(ox + ux(w), y0 + e + 1, oz + uz(w), Material.BUDDING_AMETHYST.createBlockData());
                }
                case FALLING_ROCK -> {
                    for (int t : s.tiles()) list.add(ox + ux(t), y0 + e + l.height(ux(t), uz(t)) + 1, oz + uz(t), ceilingMark);
                }
                case PITFALL -> preparePit(list, s, palette);
                case ALARM_RUNE -> list.add(ox + s.x(), y0 + e, oz + s.z(), mark);
                default -> {
                    for (int t : s.tiles()) list.add(ox + ux(t), y0 + e, oz + uz(t), mark);
                }
            }
        }
    }

    /** 구덩이: 바닥 아래 2칸을 미리 파 둔다 (바닥 y0-2, 둘레 벽, 줄마다 가운데 계단 — 밟으면 바닥 블록만 사라짐). */
    private void preparePit(BlockList list, TrapSpot s, Palette palette) {
        int ox = fs.ox(), y0 = fs.y0(), oz = fs.oz();
        java.util.Set<Integer> pit = new java.util.HashSet<>();
        for (int t : s.tiles()) pit.add(t);
        java.util.Set<Integer> rim = new java.util.HashSet<>();
        for (int t : s.tiles()) {
            int x = ux(t), z = uz(t);
            list.add(ox + x, y0 - 2, oz + z, floorData);
            list.add(ox + x, y0, oz + z, mark);
            list.add(ox + x, y0 + 1, oz + z, Material.AIR.createBlockData()); // 바닥 장식(이끼 카펫 등) 치우기
            for (int dz = -1; dz <= 1; dz++) for (int dx = -1; dx <= 1; dx++) {
                int p = FloorLayout.pack(x + dx, z + dz);
                if (!pit.contains(p)) rim.add(p);
            }
        }
        for (int p : rim) {
            list.add(ox + ux(p), y0 - 1, oz + uz(p), wallData);
            list.add(ox + ux(p), y0 - 2, oz + uz(p), wallData);
        }
        int w = s.tiles().length / 2;
        int a = s.tiles()[w / 2], b = s.tiles()[w + w / 2];
        list.add(ox + ux(a), y0 - 1, oz + uz(a), stair(palette, face(-s.alongX(), -s.alongZ())));
        list.add(ox + ux(b), y0 - 1, oz + uz(b), stair(palette, face(s.alongX(), s.alongZ())));
    }

    private static BlockData stair(Palette palette, BlockFace facing) {
        BlockData d = palette.stairs().createBlockData();
        if (d instanceof Stairs st) {
            st.setFacing(facing);
            st.setHalf(org.bukkit.block.data.Bisected.Half.BOTTOM);
        }
        return d;
    }

    private BlockData tripwire(TrapSpot s) {
        BlockData d = Material.TRIPWIRE.createBlockData();
        if (d instanceof MultipleFacing mf) {
            if (s.crossX() != 0) {
                mf.setFace(BlockFace.EAST, true);
                mf.setFace(BlockFace.WEST, true);
            } else {
                mf.setFace(BlockFace.NORTH, true);
                mf.setFace(BlockFace.SOUTH, true);
            }
        }
        return d;
    }

    /** 블록 배치 뒤: 톱날 표시. */
    public void onReady() {
        for (TrapSpot s : spots) {
            if (s.type() != TrapType.SAW_BLADE) continue;
            St t = st[s.index()];
            Location at = fs.tile(s.x(), s.z(), s.elevation() + 1.0);
            t.saw = fs.track(fs.world().spawn(at, BlockDisplay.class, d -> {
                d.setBlock(Material.STONECUTTER.createBlockData());
                d.setTransformation(new Transformation(new Vector3f(-0.45f, -0.05f, -0.45f), new Quaternionf(),
                        new Vector3f(0.9f, 0.7f, 0.9f), new Quaternionf()));
                d.setTeleportDuration(2);
                d.setBrightness(new Display.Brightness(12, 15));
            }));
        }
    }

    // ── 진행 ──────────────────────────────────────────────────────────────

    /** 2틱마다 (FloorState.tick). */
    public void tick(long t) {
        if (spots.isEmpty()) return;
        List<Player> alive = fs.alivePlayers();
        // 1. 밟기 판정 + 해제
        for (Player p : alive) {
            Location l = p.getLocation();
            Location prev = lastSeen.put(p.getUniqueId(), l);
            int tx = fs.tileX(l), tz = fs.tileZ(l);
            Integer idx = byTile.get(FloorLayout.pack(tx, tz));
            if (idx != null) {
                St s = st[idx];
                TrapSpot spot = spots.get(idx);
                double feet = l.getY() - fs.y0() - spot.elevation() - 1.0;
                if (!s.off && !spot.type().periodic() && s.fireAt < 0 && t >= s.cooldownUntil && !s.pitOpen && Math.abs(feet) < 0.35) {
                    trigger(spot, t, p);
                }
                // 물살: 경고 중 처음 보인 때 직전 자리로 들어온 쪽을 기억 (발동 땐 이미 반대편 가장자리일 수 있다)
                if (spot.type() == TrapType.CURRENT && s.fireAt >= 0 && !s.entry.containsKey(p.getUniqueId())) {
                    Location from = prev != null && prev.getWorld() == l.getWorld() && prev.distanceSquared(l) < 4 ? prev : l;
                    Location c = center(spot, 1.0);
                    s.entry.put(p.getUniqueId(), (from.getX() - c.getX()) * spot.alongX() + (from.getZ() - c.getZ()) * spot.alongZ());
                }
            }
            if (p.isSneaking()) disarmTick(p, tx, tz, t);
            else disarming.remove(p.getUniqueId());
        }
        // 2. 함정별 진행
        for (TrapSpot spot : spots) {
            St s = st[spot.index()];
            if (s.off && s.activeUntil < 0 && !s.pitOpen) continue;
            try {
                if (spot.type().periodic()) {
                    if (!s.off && near(alive, spot, 32)) periodic(spot, s, t, alive);
                } else {
                    stepped(spot, s, t, alive);
                }
            } catch (Throwable e) {
                Log.error("함정 오류 (" + spot.type().id() + ")", e);
                s.off = true;
            }
        }
        // 3. 티(가끔 작은 입자)·그림자 감지
        if (t % 40 == 0) hints(alive);
        if (t % 20 == 0) shadowSense(alive);
    }

    private boolean near(List<Player> alive, TrapSpot s, double r) {
        Location c = fs.tile(s.x(), s.z(), s.elevation() + 1);
        for (Player p : alive) if (p.getLocation().distanceSquared(c) < r * r) return true;
        return false;
    }

    private void trigger(TrapSpot spot, long t, Player by) {
        St s = st[spot.index()];
        triggered++;
        s.entry.clear();
        int delay = TrapMath.telegraphTicks(spot.type().telegraph(), fs.ctx().difficulty().telegraph());
        s.fireAt = t + delay;
        Location c = center(spot, 1.1);
        switch (spot.type()) {
            case ARROW_WALL -> fs.sound(c, Sound.BLOCK_TRIPWIRE_CLICK_ON, 1.0f, 1.2f);
            case FALLING_ROCK -> {
                fs.sound(c, Sound.BLOCK_GRAVEL_BREAK, 1.0f, 0.6f);
                fs.world().spawnParticle(Particle.FALLING_DUST, center(spot, fs.layout().height(spot.x(), spot.z()) + 0.6), 14, 0.8, 0.1, 0.8, 0, wallData);
            }
            case PITFALL -> {
                fs.sound(c, Sound.BLOCK_GRAVEL_BREAK, 1.0f, 0.8f);
                fs.world().spawnParticle(Particle.BLOCK, center(spot, 1.0), 20, 0.8, 0.05, 0.8, 0, mark);
            }
            case ALARM_RUNE -> fs.sound(c, Sound.BLOCK_BEACON_ACTIVATE, 0.8f, 1.8f);
            case VOID_RIFT -> fs.sound(c, Sound.BLOCK_PORTAL_TRIGGER, 0.4f, 1.6f);
            default -> fs.sound(c, Sound.BLOCK_STONE_PRESSURE_PLATE_CLICK_ON, 1.0f, 0.7f);
        }
        if (by != null && !s.announced) {
            s.announced = true;
            fs.services().hud().actionBar(by, Text.mm("<red><b>함정!</b></red> <gray>" + spot.type().displayName()
                    + " — 다음엔 웅크려 해제해 보자"), 40);
        }
    }

    private void stepped(TrapSpot spot, St s, long t, List<Player> alive) {
        TrapType type = spot.type();
        // 경고 중 연출
        if (s.fireAt >= 0 && t < s.fireAt) {
            if (type == TrapType.FALLING_ROCK && t % 4 == 0) ring(spot, 1.6, WARN);
            if (type == TrapType.VOID_RIFT && t % 4 == 0) {
                fs.world().spawnParticle(Particle.REVERSE_PORTAL, center(spot, 1.0), 12, 0.6, 0.1, 0.6, 0.02);
            }
            if (type == TrapType.ALARM_RUNE && t % 4 == 0) {
                fs.world().spawnParticle(Particle.ENCHANT, center(spot, 0.3), 10, 0.5, 0.1, 0.5, 0.6);
            }
            return;
        }
        if (s.fireAt >= 0 && t >= s.fireAt) {
            s.fireAt = -1;
            fire(spot, s, t, alive);
            if (type.cooldown() > 0) s.cooldownUntil = t + type.cooldown();
            else s.off = true;
        }
        // 진행 중 효과
        if (type == TrapType.POISON_GAS && s.activeUntil >= 0) {
            if (t >= s.activeUntil) {
                s.activeUntil = -1;
            } else {
                if (t % 6 == 0) {
                    fs.world().spawnParticle(Particle.DUST, center(spot, 1.0), 22, 1.4, 0.7, 1.4, 0,
                            new Particle.DustOptions(POISON, 1.8f));
                }
                if (t % 20 == 0) for (Player p : victims(spot, alive, 1)) hit(p, spot, 1.0);
            }
        }
        if (s.damageAt >= 0 && t >= s.damageAt) {
            s.damageAt = -1;
            if (type == TrapType.FALLING_ROCK) {
                Location c = center(spot, 1.0);
                fs.world().spawnParticle(Particle.BLOCK, c, 40, 0.8, 0.3, 0.8, 0, wallData);
                fs.sound(c, Sound.BLOCK_STONE_BREAK, 1.2f, 0.6f);
                for (Player p : victims(spot, alive, 1)) {
                    hit(p, spot, 1.0);
                    fs.services().effects().apply(p, "slow", 1.5, 0.3, null);
                }
            } else if (type == TrapType.PITFALL) {
                for (Player p : inPit(spot, alive)) {
                    hit(p, spot, 1.0);
                    fs.services().effects().apply(p, "slow", 2.0, 0.35, null);
                    fs.world().spawnParticle(Particle.BLOCK, p.getLocation(), 16, 0.3, 0.1, 0.3, 0,
                            Material.POINTED_DRIPSTONE.createBlockData());
                }
                fs.sound(center(spot, -1), Sound.BLOCK_POINTED_DRIPSTONE_LAND, 1.0f, 0.8f);
            }
        }
        if (s.pitOpen && t >= s.restoreAt) {
            if (inPit(spot, alive).isEmpty()) {
                for (int tile : spot.tiles()) fs.setBlock(ux(tile), 0, uz(tile), mark);
                s.pitOpen = false;
                s.cooldownUntil = t + type.cooldown();
                fs.sound(center(spot, 1), Sound.BLOCK_STONE_PLACE, 0.8f, 0.7f);
            } else {
                s.restoreAt = t + 20;
            }
        }
    }

    private void fire(TrapSpot spot, St s, long t, List<Player> alive) {
        Location c = center(spot, 1.0);
        switch (spot.type()) {
            case SPIKE -> {
                spikes(spot);
                fs.sound(c, Sound.BLOCK_POINTED_DRIPSTONE_LAND, 1.2f, 1.3f);
                for (Player p : victims(spot, alive, 0)) {
                    hit(p, spot, 1.0);
                    fs.services().effects().apply(p, "slow", 2.0, 0.35, null);
                }
            }
            case ARROW_WALL -> {
                arrows(spot);
                for (Player p : victims(spot, alive, 0)) hit(p, spot, 1.0);
            }
            case FALLING_ROCK -> {
                rock(spot);
                s.damageAt = t + 6;
            }
            case POISON_GAS -> {
                s.activeUntil = t + 100;
                fs.sound(c, Sound.BLOCK_FIRE_EXTINGUISH, 0.8f, 0.5f);
                fs.world().spawnParticle(Particle.DUST, c, 40, 1.0, 0.4, 1.0, 0, new Particle.DustOptions(POISON, 2.2f));
            }
            case PITFALL -> {
                for (int tile : spot.tiles()) fs.setBlock(ux(tile), 0, uz(tile), Material.AIR);
                s.pitOpen = true;
                s.restoreAt = t + 120;
                s.damageAt = t + 10;
                fs.world().spawnParticle(Particle.BLOCK, c, 30, 0.8, 0.1, 0.8, 0, mark);
                fs.sound(c, Sound.BLOCK_STONE_BREAK, 1.0f, 0.5f);
            }
            case ALARM_RUNE -> alarm(spot, alive);
            case CURRENT -> {
                fs.world().spawnParticle(Particle.SPLASH, c, 50, 0.8, 0.4, 0.8, 0.3);
                fs.sound(c, Sound.ITEM_BUCKET_EMPTY, 1.0f, 0.6f);
                for (Player p : victims(spot, alive, 0)) {
                    // 왔던 쪽으로 (서버 쪽 속도엔 걷기 이동이 안 담겨 못 쓴다) — 기록이 없으면 바라보는 반대쪽
                    Double from = s.entry.get(p.getUniqueId());
                    Vector look = p.getLocation().getDirection();
                    int side = TrapMath.pushSide(from == null ? Double.NaN : from,
                            look.getX() * spot.alongX() + look.getZ() * spot.alongZ());
                    p.setVelocity(new Vector(spot.alongX() * side * 1.3, 0.35, spot.alongZ() * side * 1.3));
                    hit(p, spot, 1.0);
                    fs.services().effects().apply(p, "slow", 1.5, 0.3, null);
                }
            }
            case ICE_SLIDE -> {
                fs.world().spawnParticle(Particle.SNOWFLAKE, c, 30, 0.8, 0.2, 0.8, 0.05);
                fs.sound(c, Sound.BLOCK_GLASS_BREAK, 0.7f, 1.5f);
                for (Player p : victims(spot, alive, 0)) {
                    Vector dir = p.getLocation().getDirection().setY(0);
                    if (dir.lengthSquared() < 1e-4) dir = new Vector(spot.alongX(), 0, spot.alongZ());
                    p.setVelocity(dir.normalize().multiply(1.4).setY(0.1));
                    hit(p, spot, 1.0);
                    fs.services().effects().apply(p, "frost", 5.0, 1, null);
                }
            }
            case INK_BURST -> {
                fs.world().spawnParticle(Particle.SQUID_INK, center(spot, 1.2), 60, 1.0, 0.6, 1.0, 0.05);
                fs.sound(c, Sound.ENTITY_SQUID_SQUIRT, 1.0f, 0.7f);
                for (Player p : victims(spot, alive, 1)) {
                    hit(p, spot, 1.0);
                    fs.services().effects().apply(p, "blind", 4.0, 0, null);
                }
            }
            case VOID_RIFT -> {
                fs.world().spawnParticle(Particle.PORTAL, c, 80, 1.0, 0.8, 1.0, 0.6);
                fs.sound(c, Sound.ENTITY_ENDERMAN_TELEPORT, 1.0f, 0.5f);
                for (Player p : victims(spot, alive, 2)) {
                    Vector pull = c.toVector().subtract(p.getLocation().toVector()).setY(0);
                    if (pull.lengthSquared() > 1e-4) p.setVelocity(pull.normalize().multiply(0.8).setY(0.25));
                    hit(p, spot, 1.0);
                    fs.services().effects().apply(p, "weaken", 4.0, 0.2, null);
                }
            }
            default -> { }
        }
    }

    // ── 주기 함정 ─────────────────────────────────────────────────────────

    private void periodic(TrapSpot spot, St s, long t, List<Player> alive) {
        double tele = fs.ctx().difficulty().telegraph();
        switch (spot.type()) {
            case FLAME_JET -> {
                int warn = TrapMath.telegraphTicks(spot.type().telegraph(), tele);
                int beat = TrapMath.beat(t, spot.phase(), 70, warn, 24);
                if (beat == 1 && t % 4 == 0) {
                    for (int tile : spot.tiles()) {
                        fs.world().spawnParticle(Particle.SMOKE, fs.tile(ux(tile), uz(tile), spot.elevation() + 1.05), 3, 0.2, 0.05, 0.2, 0.01);
                    }
                } else if (beat == 2) {
                    if (TrapMath.beat(t - 2, spot.phase(), 70, warn, 24) != 2) fs.sound(center(spot, 1), Sound.ITEM_FIRECHARGE_USE, 0.9f, 0.7f);
                    for (int tile : spot.tiles()) {
                        fs.world().spawnParticle(Particle.FLAME, fs.tile(ux(tile), uz(tile), spot.elevation() + 1.6), 6, 0.18, 0.55, 0.18, 0.02);
                    }
                    for (Player p : victims(spot, alive, 0)) hitThrottled(p, spot, s, t, 8);
                }
            }
            case CRYSTAL_BEAM -> {
                int warn = TrapMath.telegraphTicks(spot.type().telegraph(), tele);
                int beat = TrapMath.beat(t, spot.phase(), 80, warn, 16);
                if (beat == 1 && t % 4 == 0) beamLine(spot, Particle.END_ROD, 1, null);
                else if (beat == 2) {
                    if (TrapMath.beat(t - 2, spot.phase(), 80, warn, 16) != 2) {
                        fs.sound(center(spot, 1.3), Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 1.0f, 1.6f);
                    }
                    beamLine(spot, Particle.DUST, 3, new Particle.DustOptions(BEAM, 1.3f));
                    for (Player p : victims(spot, alive, 0)) hitThrottled(p, spot, s, t, 8);
                }
            }
            case SAW_BLADE -> saw(spot, s, t, alive);
            default -> { }
        }
    }

    private void saw(TrapSpot spot, St s, long t, List<Player> alive) {
        int[] tiles = spot.tiles();
        double a0x = ux(tiles[0]), a0z = uz(tiles[0]), a1x = ux(tiles[tiles.length - 1]), a1z = uz(tiles[tiles.length - 1]);
        double u = Math.floorMod(t + spot.phase(), 40L) / 20.0;
        double tri = u <= 1 ? u : 2 - u;
        double bx = a0x + (a1x - a0x) * tri, bz = a0z + (a1z - a0z) * tri;
        Location at = fs.tile(bx, bz, spot.elevation() + 1.0);
        if (s.saw != null && s.saw.isValid()) {
            s.sawYaw = (s.sawYaw + 47f) % 360f;
            at.setYaw(s.sawYaw);
            s.saw.teleport(at);
        }
        if (t % 4 == 0) fs.world().spawnParticle(Particle.CRIT, at.clone().add(0, 0.5, 0), 2, 0.2, 0.05, 0.2, 0.05);
        if (t % 20 == 0) fs.sound(at, Sound.BLOCK_GRINDSTONE_USE, 0.35f, 1.4f);
        for (Player p : alive) {
            Location pl = p.getLocation();
            double dx = pl.getX() - at.getX(), dz = pl.getZ() - at.getZ(), dy = pl.getY() - at.getY();
            if (dx * dx + dz * dz < 0.75 * 0.75 && dy > -0.6 && dy < 1.2) {
                if (hitThrottled(p, spot, s, t, 14)) {
                    Vector kb = new Vector(dx, 0, dz);
                    if (kb.lengthSquared() > 1e-4) p.setVelocity(kb.normalize().multiply(0.5).setY(0.2));
                }
            }
        }
    }

    private void beamLine(TrapSpot spot, Particle particle, int per, Particle.DustOptions dust) {
        int[] tiles = spot.tiles();
        double x0 = ux(tiles[0]) - spot.crossX() * 0.5, z0 = uz(tiles[0]) - spot.crossZ() * 0.5;
        int len = tiles.length;
        for (int i = 0; i <= len * 2; i++) {
            double f = i / 2.0;
            Location l = fs.tile(x0 + spot.crossX() * f, z0 + spot.crossZ() * f, spot.elevation() + 1.35);
            if (dust != null) fs.world().spawnParticle(particle, l, per, 0.03, 0.03, 0.03, 0, dust);
            else fs.world().spawnParticle(particle, l, per, 0.02, 0.02, 0.02, 0);
        }
    }

    // ── 효과 ──────────────────────────────────────────────────────────────

    private void spikes(TrapSpot spot) {
        BlockData spike = Material.POINTED_DRIPSTONE.createBlockData();
        if (spike instanceof Speleothem sp) sp.setVerticalDirection(BlockFace.UP);
        for (int tile : spot.tiles()) {
            Location at = fs.tile(ux(tile), uz(tile), spot.elevation() + 1.0);
            BlockDisplay d = fs.track(fs.world().spawn(at, BlockDisplay.class, e -> {
                e.setBlock(spike);
                e.setTransformation(new Transformation(new Vector3f(-0.4f, -0.9f, -0.4f), new Quaternionf(),
                        new Vector3f(0.8f, 0.9f, 0.8f), new Quaternionf()));
            }));
            later(1, () -> {
                d.setInterpolationDelay(0);
                d.setInterpolationDuration(2);
                d.setTransformation(new Transformation(new Vector3f(-0.4f, 0f, -0.4f), new Quaternionf(),
                        new Vector3f(0.8f, 0.9f, 0.8f), new Quaternionf()));
            });
            later(26, () -> fs.untrack(d));
        }
    }

    private void arrows(TrapSpot spot) {
        if (spot.walls().length == 0) return;
        Location c = center(spot, 1.0);
        fs.sound(c, Sound.ENTITY_ARROW_SHOOT, 1.0f, 0.9f);
        fs.sound(c, Sound.ENTITY_ARROW_SHOOT, 1.0f, 1.2f);
        int[] tiles = spot.tiles();
        double x0 = ux(tiles[0]) - spot.crossX() * 0.5, z0 = uz(tiles[0]) - spot.crossZ() * 0.5;
        for (double h : new double[] {1.2, 1.7}) {
            for (int i = 0; i <= tiles.length * 3; i++) {
                double f = i / 3.0;
                fs.world().spawnParticle(Particle.CRIT, fs.tile(x0 + spot.crossX() * f, z0 + spot.crossZ() * f, spot.elevation() + h),
                        1, 0, 0, 0, 0.0);
            }
        }
    }

    private void rock(TrapSpot spot) {
        int h = fs.layout().height(spot.x(), spot.z());
        Location top = fs.tile(spot.x(), spot.z(), spot.elevation() + h);
        BlockDisplay d = fs.track(fs.world().spawn(top, BlockDisplay.class, e -> {
            e.setBlock(wallData);
            e.setTransformation(new Transformation(new Vector3f(-0.7f, -0.2f, -0.7f), new Quaternionf(),
                    new Vector3f(1.4f, 1.1f, 1.4f), new Quaternionf()));
        }));
        float drop = h - 0.9f;
        later(1, () -> {
            d.setInterpolationDelay(0);
            d.setInterpolationDuration(5);
            d.setTransformation(new Transformation(new Vector3f(-0.7f, -0.2f - drop, -0.7f), new Quaternionf(),
                    new Vector3f(1.4f, 1.1f, 1.4f), new Quaternionf()));
        });
        later(20, () -> fs.untrack(d));
        fs.sound(top, Sound.BLOCK_DRIPSTONE_BLOCK_BREAK, 1.0f, 0.5f);
    }

    private void alarm(TrapSpot spot, List<Player> alive) {
        Location c = center(spot, 1.0);
        fs.sound(c, Sound.BLOCK_BELL_USE, 1.2f, 0.6f);
        fs.sound(c, Sound.ENTITY_EVOKER_PREPARE_SUMMON, 1.0f, 0.8f);
        fs.world().spawnParticle(Particle.WITCH, c, 40, 1.0, 0.5, 1.0, 0.1);
        int n = 2 + fs.floor() / 4;
        FloorLayout l = fs.layout();
        int spawned = 0;
        for (int k = 0; k < 12 && spawned < n; k++) {
            int d = (k % 2 == 0 ? 1 : -1) * (2 + k / 2);
            int x = spot.x() + spot.alongX() * d + (rng.nextInt(3) - 1) * spot.crossX();
            int z = spot.z() + spot.alongZ() * d + (rng.nextInt(3) - 1) * spot.crossZ();
            if (!l.walkable(x, z)) continue;
            if (fs.spawnMob(fs.randomFloorMob(rng), fs.tile(x, z, l.standHeight(x, z))) != null) spawned++;
        }
        fs.actionBar(alive.isEmpty() ? fs.allPlayers() : alive, "<red><b>경보가 울렸다!</b></red> <gray>몬스터가 몰려온다", 50);
    }

    private void ring(TrapSpot spot, double r, Color color) {
        Location c = center(spot, 0.15);
        Particle.DustOptions dust = new Particle.DustOptions(color, 1.0f);
        for (int i = 0; i < 16; i++) {
            double a = Math.PI * 2 * i / 16.0;
            fs.world().spawnParticle(Particle.DUST, c.clone().add(Math.cos(a) * r, 0, Math.sin(a) * r), 1, 0, 0, 0, 0, dust);
        }
    }

    // ── 피해 ──────────────────────────────────────────────────────────────

    private void hit(Player p, TrapSpot spot, double mult) {
        double pct = TrapMath.pct(spot.type(), fs.floor(), fs.ctx().difficulty().damage()) * mult;
        if (pct <= 0) return;
        fs.services().damage().deal(DamageContext.percent(null, p, pct).source("trap_" + spot.type().id()));
    }

    /** 같은 사람은 gap 틱에 한 번만. @return 맞았으면 true */
    private boolean hitThrottled(Player p, TrapSpot spot, St s, long t, int gap) {
        Long last = s.lastHit.get(p.getUniqueId());
        if (last != null && t - last < gap) return false;
        s.lastHit.put(p.getUniqueId(), t);
        hit(p, spot, 1.0);
        return true;
    }

    /** 함정 칸(margin 칸 둘레 포함) 위에 서 있는 살아 있는 파티원. */
    private List<Player> victims(TrapSpot spot, List<Player> alive, int margin) {
        List<Player> out = new ArrayList<>();
        for (Player p : alive) {
            Location l = p.getLocation();
            double dy = l.getY() - fs.y0() - spot.elevation();
            if (dy < -2.5 || dy > 3.2) continue;
            int tx = fs.tileX(l), tz = fs.tileZ(l);
            for (int tile : spot.tiles()) {
                if (Math.abs(ux(tile) - tx) <= margin && Math.abs(uz(tile) - tz) <= margin) {
                    out.add(p);
                    break;
                }
            }
        }
        return out;
    }

    private List<Player> inPit(TrapSpot spot, List<Player> alive) {
        List<Player> out = new ArrayList<>();
        for (Player p : alive) {
            Location l = p.getLocation();
            if (l.getY() - fs.y0() < 0.6 && spot.covers(FloorLayout.pack(fs.tileX(l), fs.tileZ(l)))) out.add(p);
        }
        return out;
    }

    // ── 해제 ──────────────────────────────────────────────────────────────

    private boolean isShadow(Player p) {
        try {
            return "shadow".equals(fs.services().data().get(p).classId());
        } catch (Throwable t) {
            return false;
        }
    }

    private void disarmTick(Player p, int tx, int tz, long t) {
        int found = -1;
        for (int dz = -1; dz <= 1 && found < 0; dz++) {
            for (int dx = -1; dx <= 1; dx++) {
                Integer idx = byTile.get(FloorLayout.pack(tx + dx, tz + dz));
                if (idx != null && !st[idx].off && st[idx].fireAt < 0 && !st[idx].pitOpen) {
                    found = idx;
                    break;
                }
            }
        }
        UUID u = p.getUniqueId();
        if (found < 0) {
            disarming.remove(u);
            return;
        }
        int[] prog = disarming.get(u);
        if (prog == null || prog[0] != found) {
            prog = new int[] {found, 0};
            disarming.put(u, prog);
        }
        prog[1] += 2;
        DungeonConfig.TrapRules r = fs.config().traps();
        int need = TrapMath.disarmTicks(isShadow(p), r.disarmSeconds(), r.shadowDisarmSeconds());
        if (prog[1] >= need) {
            disarming.remove(u);
            disarm(found, p);
            return;
        }
        if (prog[1] % 6 == 0 || prog[1] == 2) {
            int bars = 10, on = Math.min(bars, prog[1] * bars / need);
            fs.services().hud().actionBar(p, Text.mm("<gray>함정 해제 중 <white>" + spots.get(found).type().displayName() + "</white> <green>"
                    + "■".repeat(on) + "</green><dark_gray>" + "■".repeat(bars - on)), 12);
            if (prog[1] % 12 == 0) p.playSound(p.getLocation(), Sound.BLOCK_TRIPWIRE_ATTACH, 0.4f, 1.6f);
        }
    }

    /** 함정을 해제한다 (by = null 이면 자가 진단 — 보상 없음). */
    public void disarm(int index, Player by) {
        if (index < 0 || index >= st.length) return;
        St s = st[index];
        if (s.off) return;
        s.off = true;
        s.fireAt = -1;
        disarmedCount++;
        TrapSpot spot = spots.get(index);
        if (s.saw != null) {
            fs.untrack(s.saw);
            s.saw = null;
        }
        if (spot.type() == TrapType.ARROW_WALL) {
            for (int tile : spot.tiles()) fs.setBlock(ux(tile), spot.elevation() + 1, uz(tile), Material.AIR);
        }
        Location c = center(spot, 1.0);
        fs.world().spawnParticle(Particle.CLOUD, c, 12, 0.6, 0.2, 0.6, 0.02);
        fs.sound(c, Sound.BLOCK_TRIPWIRE_DETACH, 1.0f, 0.8f);
        if (by == null) return;
        DungeonConfig.TrapRules r = fs.config().traps();
        long gold = TrapMath.disarmGold(fs.floor(), r.disarmGold(), fs.ctx().goldMultiplier());
        double xp = fs.averageMobXp() * r.disarmXp() * fs.ctx().xpMultiplier();
        try {
            var d = fs.services().data().get(by);
            d.addGold(gold);
            d.increment("dungeon.traps_disarmed", 1);
            fs.services().hud().refresh(by);
            if (xp > 0) fs.services().levels().reward(by, xp);
        } catch (Throwable t) {
            Log.error("함정 해제 보상 실패", t);
        }
        by.playSound(by.getLocation(), Sound.UI_STONECUTTER_TAKE_RESULT, 0.8f, 1.4f);
        Text.send(by, "<green>함정 해제!</green> <gray>" + spot.type().displayName() + " · <#ffd27a>+" + Text.num(gold) + " 골드</#ffd27a>"
                + (xp > 0 ? " · 경험치 +" + Math.round(xp) : ""));
        for (Player o : fs.allPlayers()) {
            if (o != by) fs.services().hud().actionBar(o, Text.mm("<gray>" + Text.escape(by.getName()) + " 님이 <white>"
                    + spot.type().displayName() + "</white>을(를) 해제했습니다"), 40);
        }
    }

    // ── 티·그림자 ─────────────────────────────────────────────────────────

    private void hints(List<Player> alive) {
        for (TrapSpot spot : spots) {
            if (st[spot.index()].off || spot.type().periodic() || !near(alive, spot, 7)) continue;
            Location c = center(spot, 0.15);
            switch (spot.type()) {
                case SPIKE -> fs.world().spawnParticle(Particle.CRIT, c, 1, 0.5, 0, 0.5, 0);
                case FALLING_ROCK -> fs.world().spawnParticle(Particle.FALLING_DUST,
                        center(spot, fs.layout().height(spot.x(), spot.z()) + 0.8), 2, 0.6, 0, 0.6, 0, wallData);
                case POISON_GAS -> fs.world().spawnParticle(Particle.DUST, c, 2, 0.6, 0.05, 0.6, 0, new Particle.DustOptions(POISON, 0.7f));
                case PITFALL -> fs.world().spawnParticle(Particle.FALLING_DUST, center(spot, 0.5), 2, 0.6, 0, 0.6, 0, mark);
                case ALARM_RUNE -> fs.world().spawnParticle(Particle.ENCHANT, center(spot, 0.4), 2, 0.2, 0, 0.2, 0.2);
                case CURRENT -> fs.world().spawnParticle(Particle.SPLASH, c, 2, 0.5, 0, 0.5, 0);
                case ICE_SLIDE -> fs.world().spawnParticle(Particle.SNOWFLAKE, c, 1, 0.5, 0, 0.5, 0);
                case INK_BURST -> fs.world().spawnParticle(Particle.SQUID_INK, c, 1, 0.5, 0, 0.5, 0);
                case VOID_RIFT -> fs.world().spawnParticle(Particle.REVERSE_PORTAL, c, 2, 0.5, 0, 0.5, 0);
                default -> { }
            }
        }
    }

    /** 그림자 직업: 10칸 안 함정 윤곽 (본인에게만 보이는 보라 점). */
    private void shadowSense(List<Player> alive) {
        double r = fs.config().traps().shadowSense();
        if (r <= 0) return;
        Particle.DustOptions dust = new Particle.DustOptions(SHADOW, 0.8f);
        for (Player p : alive) {
            if (!isShadow(p)) continue;
            Location pl = p.getLocation();
            for (TrapSpot spot : spots) {
                if (st[spot.index()].off) continue;
                if (pl.distanceSquared(center(spot, 1)) > r * r) continue;
                for (int tile : spot.tiles()) {
                    double x = ux(tile), z = uz(tile);
                    for (double[] q : new double[][] {{-0.45, -0.45}, {0.45, -0.45}, {-0.45, 0.45}, {0.45, 0.45}, {0, 0}}) {
                        p.spawnParticle(Particle.DUST, fs.tile(x + q[0], z + q[1], spot.elevation() + 1.08), 1, 0, 0, 0, 0, dust);
                    }
                }
            }
        }
    }

    // ── 자가 진단 ─────────────────────────────────────────────────────────

    /** 모든 함정을 사람 없이 한 번씩 발동·주기 진행·해제해 본다 (예외는 위로). @return 종류별 개수 */
    public Map<String, Integer> selfTest(long t) {
        Map<String, Integer> out = new LinkedHashMap<>();
        List<Player> none = List.of();
        for (TrapSpot spot : spots) {
            St s = st[spot.index()];
            out.merge(spot.type().id(), 1, Integer::sum);
            if (spot.type().periodic()) {
                for (int k = 0; k < 90; k += 2) periodic(spot, s, t + k, none);
            } else {
                trigger(spot, t, null);
                stepped(spot, s, s.fireAt, none);
                stepped(spot, s, t + 400, none);
            }
            if (spot.type() == TrapType.PITFALL && fs.block(spot.x(), -2, spot.z()).getType().isAir()) {
                throw new IllegalStateException("구덩이 바닥 블록 없음");
            }
            disarm(spot.index(), null);
        }
        return out;
    }

    // ── 도우미 ────────────────────────────────────────────────────────────

    private Location center(TrapSpot s, double dy) {
        double x = 0, z = 0;
        for (int t : s.tiles()) {
            x += ux(t);
            z += uz(t);
        }
        return fs.tile(x / s.tiles().length, z / s.tiles().length, s.elevation() + dy);
    }

    private void later(long ticks, Runnable r) {
        Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> {
            if (!fs.destroyed()) r.run();
        }, ticks);
    }

    private static int ux(int p) { return FloorLayout.unpackX(p); }
    private static int uz(int p) { return FloorLayout.unpackZ(p); }

    static BlockFace face(int dx, int dz) {
        if (dx > 0) return BlockFace.EAST;
        if (dx < 0) return BlockFace.WEST;
        if (dz > 0) return BlockFace.SOUTH;
        return BlockFace.NORTH;
    }

    /** 층 정리 시. */
    public void onDestroy() {
        disarming.clear();
        for (St s : st) s.saw = null;
    }
}
