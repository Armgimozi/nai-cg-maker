package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.bosses.Boss;
import kr.labyrinth.bosses.BossAnim;
import kr.labyrinth.bosses.BossFx;
import kr.labyrinth.bosses.BossMath;
import kr.labyrinth.bosses.Mechanics;
import kr.labyrinth.bosses.Telegraph;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.Params;
import net.kyori.adventure.bossbar.BossBar;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.util.Vector;

/**
 * 지하 4층 — 수문의 망령 오스릭 (GDD §7.4, core {@code rising_water}).
 * 핵심: 수위 상승 — 물은 실제 블록이 아니라 수면 디스플레이(water_plane) + 판정 높이. 수면 아래: 둔화 35% + 초당 최대 HP 2%,
 * 보스가 물에 잠기면 받는 피해 −25%·주는 피해 +15%. 벽면 밸브를 전부(웅크린 채 3초씩) 제한 시간 안에 돌리면 배수 →
 * 보스 5초 기절 + 받는 피해 +40%, 8초 뒤 다시 차오름. 단상(높이 2) 위는 해일에서 안전.
 * 패턴: key_strike · anchor_hurl(가장 먼 대상, 끌어당김) · tidal_sweep(폭 4 직사각형) · rising_flood(상시) · whirlpool · floodling_tide.
 */
public final class Floor04Boss extends Boss {

    private static final class Valve {
        final Location at;
        TextDisplay label;
        int progress;
        boolean done;

        Valve(Location at) { this.at = at; }
    }

    private final List<Valve> valves = new ArrayList<>();
    private final List<Location> platforms = new ArrayList<>();
    private ItemDisplay water;
    private int stage;
    private double waterY;
    private long nextStage;
    private long refloodAt;
    private long windowEnd = -1;
    private int channelTicks;

    public Floor04Boss(Init init) { super(init); }

    // ── 아레나 ───────────────────────────────────────────────────────────

    @Override
    protected void onSpawn() {
        Params a = def.arena();
        Params flood = def.pattern("rising_flood");
        waterY = floorY;
        int pc = Math.max(0, a.integer("platforms", 4));
        double pr = a.dbl("platform_radius", 2.5);
        int ph = Math.max(1, a.integer("platform_height", 2));
        BlockData top = mat(a.str("platform_block", "PRISMARINE_BRICKS"), Material.PRISMARINE_BRICKS);
        BlockData side = mat(a.str("platform_base", "DARK_PRISMARINE"), Material.DARK_PRISMARINE);
        double ring = Math.min(arenaRadius - pr - 2, arenaRadius * 0.55);
        for (double ang : BossMath.ringAngles(pc, 90, 30)) {
            if (BossMath.angleGap(ang, 270) < 16) ang += 20;
            Location c = ringPoint(ang, ring).getBlock().getLocation().add(0.5, 0, 0.5);
            c.setY(center.getBlockY());
            platforms.add(c);
            int r = (int) Math.ceil(pr);
            for (int dx = -r; dx <= r; dx++) {
                for (int dz = -r; dz <= r; dz++) {
                    if (dx * dx + dz * dz > pr * pr + 0.3) continue;
                    if (BossMath.inStairZone(c.getX() + dx - center.getX(), c.getZ() + dz - center.getZ(), 2.5)) continue;
                    boolean placed = false;
                    for (int y = 0; y < ph; y++) {
                        Block b = center.getWorld().getBlockAt(c.getBlockX() + dx, c.getBlockY() + y, c.getBlockZ() + dz);
                        placed |= setBlock(b, y == ph - 1 ? top : side);
                    }
                    if (!placed) fx.block(new Location(center.getWorld(), c.getBlockX() + dx, c.getBlockY(), c.getBlockZ() + dz), top, 1f, ph, 1f);
                }
            }
        }
        int vc = BossMath.countPerMembers(flood.dbl("valves_base", a.dbl("valves", 3)), flood.dbl("valves_per_members", 4), partySize());
        BlockData valveBlock = mat(a.str("valve_block", "WAXED_OXIDIZED_COPPER"), Material.WAXED_OXIDIZED_COPPER);
        BlockData wheel = mat("LIGHTNING_ROD", Material.IRON_CHAIN);
        double[] angs = BossMath.ringAngles(vc, 90, 22);
        for (int i = 0; i < angs.length; i++) {
            double ang = angs[i] + 180.0 / Math.max(1, vc);
            if (BossMath.angleGap(ang, 270) < 16) ang += 22;
            if (BossMath.angleGap(ang, 90) < 22) ang += 30;
            Location v = ringPoint(ang, arenaRadius - 1.5).getBlock().getLocation().add(0.5, 0, 0.5);
            v.setY(center.getBlockY());
            Block base = v.getBlock();
            if (!setBlock(base, valveBlock)) fx.block(base.getLocation(), valveBlock, 1f, 1f, 1f);
            Block rod = base.getRelative(0, 1, 0);
            if (!setBlock(rod, wheel)) fx.block(rod.getLocation(), wheel, 1f, 1f, 1f);
            Valve valve = new Valve(v);
            valve.label = fx.label(v.clone().add(0, 2.6, 0), "", 1f);
            valves.add(valve);
        }
        channelTicks = ticks(flood.dbl("valve_channel", 3.0));
        water = fx.flat(flood.str("fx", "water_plane"), center.clone().add(0, -0.4, 0), (float) arenaRadius, (float) arenaRadius, 0);
        nextStage = now + ticks(flood.phased("stage_interval", 1, 12));
        refreshValves();
    }

    private static BlockData mat(String name, Material def) {
        Material m = Material.matchMaterial(name == null ? "" : name);
        return (m != null && m.isBlock() ? m : def).createBlockData();
    }

    // ── 수위 (상시) ──────────────────────────────────────────────────────

    private boolean submerged(Player p) { return stage > 0 && p.getLocation().getY() < waterY - 0.05; }

    @Override
    protected double incomingReduction() {
        return stage > 0 ? def.pattern("rising_flood").dbl("boss_water_dr", 0.25) : 0;
    }

    @Override
    protected double outgoingMult() {
        return stage > 0 ? 1 + def.pattern("rising_flood").dbl("boss_water_damage", 0.15) : 1;
    }

    @Override
    protected void tickSystem(String key) {
        if (!key.equals("rising_flood")) return;
        Params p = def.pattern(key);
        int maxStages = p.integer("stages", 3);
        if (now >= nextStage && now >= refloodAt) {
            nextStage = now + ticks(p.phased("stage_interval", phase(), 12));
            if (stage < maxStages) setStage(stage + 1, p);
        }
        if (now % 20 == 0) {
            for (Player pl : players()) {
                if (!submerged(pl)) continue;
                effect(pl, "slow", 1.4, p.dbl("submerged_slow", 0.35));
                hitPct(pl, p.dbl("submerged_dot_pct", 0.02), "rising_flood");
                BossFx.particle(Particle.BUBBLE_COLUMN_UP, pl.getLocation().add(0, 0.5, 0), 6, 0.3, 0.4, 0.3, 0.02);
            }
        }
        if (stage > 0 && now % 6 == 0) {
            Location r = randomPoint(0, arenaRadius - 1);
            r.setY(waterY + 0.05);
            BossFx.particle(Particle.SPLASH, r, 4, 0.6, 0, 0.6, 0);
        }
        tickValves(p);
    }

    private void setStage(int s, Params p) {
        int old = stage;
        stage = Math.max(0, s);
        waterY = floorY + stage * p.dbl("stage_height", 1.0);
        if (water != null && water.isValid()) {
            water.setTeleportDuration(20);
            Location at = center.clone();
            at.setY(stage == 0 ? floorY - 0.4 : waterY + 0.02);
            water.teleport(at);
        }
        if (stage > old) {
            broadcastBar("<aqua><b>수위 상승!</b></aqua> <gray>" + stage + "단계 — 단상 위로, 밸브를 돌려 배수하세요 (웅크린 채 3초 · " + kr.labyrinth.core.InputKeys.SNEAK + ")");
            BossFx.sound(center, Sound.BLOCK_WATER_AMBIENT, 2f, 0.5f);
            BossFx.sound(center, Sound.AMBIENT_UNDERWATER_ENTER, 1.2f, 0.7f);
        }
    }

    private void tickValves(Params p) {
        boolean active = stage > 0;
        for (Valve v : valves) {
            if (v.done || !active) continue;
            boolean turning = false;
            for (Player pl : players()) {
                if (pl.isSneaking() && horizontal(pl.getLocation(), v.at) <= 2.3) {
                    turning = true;
                    if (now % 10 == 0) notify(pl, "<aqua>밸브 돌리는 중…</aqua> <white>" + (int) (100.0 * v.progress / channelTicks) + "%");
                    break;
                }
            }
            if (turning) {
                v.progress++;
                if (now % 5 == 0) BossFx.sound(v.at, Sound.BLOCK_CHAIN_STEP, 0.8f, 0.6f + 0.8f * v.progress / channelTicks);
                if (v.progress >= channelTicks) {
                    v.done = true;
                    BossFx.sound(v.at, Sound.BLOCK_IRON_TRAPDOOR_OPEN, 1.5f, 0.6f);
                    BossFx.particle(Particle.SPLASH, v.at.clone().add(0, 1.5, 0), 20, 0.4, 0.4, 0.4, 0);
                    if (windowEnd < 0) {
                        int window = ticks((scaling().solo() ? p.dbl("valve_window_solo", 25) : p.dbl("valve_window_party", 10)) * scaling().timerMult());
                        windowEnd = now + window;
                        broadcastBar("<aqua>첫 밸브 개방!</aqua> <gray>" + window / 20 + "초 안에 나머지 밸브를 모두 돌리세요");
                    }
                }
            } else if (v.progress > 0 && now % 4 == 0) {
                v.progress = Math.max(0, v.progress - 1);
            }
        }
        if (windowEnd >= 0) {
            long done = valves.stream().filter(v -> v.done).count();
            int window = ticks((scaling().solo() ? p.dbl("valve_window_solo", 25) : p.dbl("valve_window_party", 10)) * scaling().timerMult());
            if (done >= valves.size()) {
                drain(p);
            } else if (now >= windowEnd) {
                windowEnd = -1;
                for (Valve v : valves) {
                    v.done = false;
                    v.progress = 0;
                }
                hideTimerBar();
                broadcastBar("<red>배수 실패!</red> <gray>밸브가 다시 잠겼습니다");
                BossFx.sound(center, Sound.BLOCK_IRON_TRAPDOOR_CLOSE, 1.5f, 0.5f);
            } else if (now % 4 == 0) {
                timerBar("<aqua>수문 배수</aqua> <white>" + done + "/" + valves.size() + "</white> <gray>남은 "
                        + String.format("%.1f", (windowEnd - now) / 20.0) + "초", (windowEnd - now) / (float) window, BossBar.Color.BLUE);
            }
        }
        if (now % 10 == 0) refreshValves();
    }

    private void drain(Params p) {
        windowEnd = -1;
        hideTimerBar();
        for (Valve v : valves) {
            v.done = false;
            v.progress = 0;
        }
        setStage(0, p);
        refloodAt = now + ticks(p.dbl("reflood_delay", 8));
        nextStage = refloodAt + ticks(p.phased("stage_interval", phase(), 12));
        double stun = p.dbl("drain_stun", 5.0);
        stun(stun);
        makeVulnerable(p.dbl("drain_vulnerable", 0.4), stun);
        broadcastBar("<aqua><b>배수 성공!</b></aqua> <yellow>오스릭 기절 " + (int) stun + "초 — 받는 피해 +40%</yellow>");
        BossFx.sound(center, Sound.BLOCK_WATER_AMBIENT, 2f, 1.6f);
        BossFx.particle(Particle.SPLASH, center.clone().add(0, 0.5, 0), 120, arenaRadius * 0.5, 0.2, arenaRadius * 0.5, 0.1);
    }

    private void refreshValves() {
        for (Valve v : valves) {
            String state = v.done ? "<green>● 개방</green>" : stage == 0 ? "<dark_gray>○ 대기</dark_gray>"
                    : v.progress > 0 ? "<aqua>◐ " + (int) (100.0 * v.progress / channelTicks) + "%</aqua>" : "<gray>○ 웅크려(" + kr.labyrinth.core.InputKeys.SNEAK + ") 돌리기</gray>";
            BossFx.text(v.label, "<#5aa8a0>수문 밸브</#5aa8a0>\n" + state);
        }
    }

    // ── 패턴 ─────────────────────────────────────────────────────────────

    @Override
    protected boolean canUse(String key) {
        if (key.equals("floodling_tide")) {
            Params p = def.pattern(key);
            return aliveAdds(p.str("add", "floodling")) < p.integer("max_alive", 10);
        }
        return target() != null;
    }

    @Override
    protected int startPattern(String key) {
        return switch (key) {
            case "key_strike" -> keyStrike();
            case "anchor_hurl" -> anchorHurl();
            case "tidal_sweep" -> tidalSweep();
            case "whirlpool" -> whirlpool();
            case "floodling_tide" -> floodlingTide();
            default -> 0;
        };
    }

    private Vector dirTo(Location to) {
        Vector d = to.toVector().subtract(entity.getLocation().toVector()).setY(0);
        return d.lengthSquared() < 1e-4 ? facing() : d.normalize();
    }

    private int keyStrike() {
        Params p = def.pattern("key_strike");
        Player t = target();
        if (t == null) return 0;
        int w = windup(p, 0.8);
        Telegraph.Shape cone = Telegraph.Shape.cone(feet(), dirTo(t.getLocation()), p.dbl("angle", 70), p.dbl("length", 5));
        double dmg = dmg(p, "damage", 1.3);
        telegraph(cone, w, Telegraph.RED, null, () -> {
            hitShape(cone, dmg, "key_strike", DamageType.MELEE, null);
            BossFx.sound(entity.getLocation(), Sound.BLOCK_CHAIN_BREAK, 1.6f, 0.5f);
            BossFx.particle(Particle.SWEEP_ATTACK, cone.origin().clone().add(cone.direction().multiply(2.5)).add(0, 1, 0), 2, 0.6, 0.2, 0.6, 0);
        });
        return cast("key_strike", "열쇠 내려치기", w, w + 8, BossAnim.SLAM, t.getLocation(), false);
    }

    private int anchorHurl() {
        Params p = def.pattern("anchor_hurl");
        Player t = "farthest".equals(p.str("target", "farthest")) ? farthest() : randomTarget();
        if (t == null) return 0;
        int w = windup(p, 1.0);
        Location impact = ground(t.getLocation());
        Vector dir = dirTo(impact);
        double dist = Math.max(1, horizontal(entity.getLocation(), impact));
        double r = p.dbl("impact_radius", 3);
        Telegraph.Shape line = Telegraph.Shape.line(feet(), dir, dist, 1.4);
        Telegraph.Shape circle = Telegraph.Shape.circle(impact, r);
        double dmg = dmg(p, "damage", 1.4);
        double pull = p.dbl("pull_strength", 1.3);
        telegraph(line, w, Telegraph.RED, null, null);
        telegraph(circle, w, Telegraph.RED, null, () -> {
            Location from = entity.getLocation().add(0, 1.6, 0);
            int travel = Math.max(3, (int) Math.ceil(dist / (1.3 * scaling().speedMult())));
            run(new Mechanics.Projectile(fx, p.str("fx", "proj_anchor"), 1.6f,
                    Mechanics.Projectile.lob(from, impact.clone().add(0, 0.4, 0), travel, 1.0), travel, 0, false, Particle.SPLASH,
                    List::of, pl -> { }, at -> {
                Location bossAt = entity.getLocation();
                hitShape(circle, dmg, "anchor_hurl", DamageType.MELEE, pl -> after(1, () -> pull(pl, bossAt, pull)));
                BossFx.sound(impact, Sound.BLOCK_ANVIL_LAND, 1.2f, 0.5f);
                BossFx.particle(Particle.SPLASH, impact.clone().add(0, 0.4, 0), 40, r * 0.4, 0.2, r * 0.4, 0.1);
                BossFx.dustLine(impact.clone().add(0, 0.6, 0), bossAt.clone().add(0, 1.2, 0), org.bukkit.Color.fromRGB(120, 130, 130), 0.9f, 0.8);
            }));
            BossFx.sound(from, Sound.ENTITY_WITCH_THROW, 1.4f, 0.5f);
        });
        return cast("anchor_hurl", "닻 던지기", w, w + 10, BossAnim.THROW, impact, false);
    }

    private int tidalSweep() {
        Params p = def.pattern("tidal_sweep");
        Player t = randomTarget();
        if (t == null) return 0;
        int w = windup(p, 1.6);
        double width = p.dbl("width", 4);
        double ang = rng.nextInt(8) * 45.0;
        Vector dir = new Vector(BossMath.ax(ang), 0, BossMath.az(ang));
        Vector side = new Vector(-dir.getZ(), 0, dir.getX());
        // 대상 위치를 지나도록 옆으로 옮긴 선, 아레나 끝에서 끝까지
        Vector rel = t.getLocation().toVector().subtract(center.toVector()).setY(0);
        double off = Math.max(-arenaRadius + 2, Math.min(arenaRadius - 2, rel.dot(side)));
        double half = Math.sqrt(Math.max(1, arenaRadius * arenaRadius - off * off));
        Location origin = center.clone().add(side.clone().multiply(off)).subtract(dir.clone().multiply(half));
        Telegraph.Shape band = Telegraph.Shape.line(origin, dir, half * 2, width);
        double dmg = dmg(p, "damage", 1.6);
        double kb = p.dbl("knockback", 1.0);
        double safe = p.dbl("safe_height", 1.5);
        telegraph(band, w, Telegraph.ORANGE, null, () -> {
            for (Player pl : players()) {
                Location l = pl.getLocation();
                if (!BossMath.inLine(origin.getX(), origin.getZ(), dir.getX(), dir.getZ(), half * 2, width, l.getX(), l.getZ())) continue;
                if (l.getY() >= waterY + safe) continue; // 단상 위 = 무사
                hit(pl, dmg, "tidal_sweep", DamageType.MAGIC);
                double plOff = l.toVector().subtract(center.toVector()).setY(0).dot(side);
                push(pl, side.clone().multiply(plOff >= off ? 1 : -1).add(dir.clone().multiply(0.4)), kb, 0.35);
            }
            BossFx.sound(origin, Sound.ENTITY_GENERIC_SPLASH, 2f, 0.5f);
            run(new Mechanics.Repeat(12, 1, tt -> {
                Location front = origin.clone().add(dir.clone().multiply(half * 2 * tt / 12.0)).add(0, 0.6, 0);
                for (double s = -width / 2; s <= width / 2; s += 1.0) BossFx.particle(Particle.SPLASH, front.clone().add(side.clone().multiply(s)), 6, 0.2, 0.4, 0.2, 0.05);
                return true;
            }, null, false));
        });
        broadcastBar("<gold>해일이 몰려옵니다!</gold> <gray>단상 위로 올라가거나 옆으로 피하세요");
        return cast("tidal_sweep", "해일 쓸기", w, w + 6, BossAnim.SWEEP, origin.clone().add(dir.clone().multiply(half)), false);
    }

    private int whirlpool() {
        Params p = def.pattern("whirlpool");
        int count = scaling().count(p, "count", 1, 6);
        List<Player> ts = pickTargets(count, null, false);
        if (ts.isEmpty()) return 0;
        int w = windup(p, 1.2);
        double r = p.dbl("radius", 4);
        int dur = ticks(p.dbl("duration", 6));
        double pullStr = p.dbl("pull", 0.25);
        double centerDmg = dmg(p, "center_damage", 0.5);
        for (Player t : ts) {
            Location c = ground(t.getLocation());
            Telegraph.Shape shape = Telegraph.Shape.circle(c, r);
            telegraph(Telegraph.Shape.ring(c, r * 0.46, r), w, Telegraph.ORANGE, "telegraph_ring", () -> {
                BossFx.sound(c, Sound.BLOCK_BUBBLE_COLUMN_WHIRLPOOL_INSIDE, 2f, 0.6f);
                ItemDisplay swirl = fx.flat("telegraph_ring", c.clone().add(0, 0.05, 0), (float) r, (float) r, 0);
                run(new Mechanics.Repeat(dur, 2, tt -> {
                    if (swirl != null && swirl.isValid()) {
                        swirl.setInterpolationDelay(0);
                        swirl.setInterpolationDuration(2);
                        org.bukkit.util.Transformation tr = swirl.getTransformation();
                        swirl.setTransformation(new org.bukkit.util.Transformation(tr.getTranslation(),
                                new org.joml.Quaternionf().rotationY((float) Math.toRadians(-tt * 9.0)), tr.getScale(), tr.getRightRotation()));
                    }
                    for (int i = 0; i < 3; i++) {
                        double a = Math.toRadians(tt * 24 + i * 120);
                        double rr = r * (1 - (tt % 20) / 20.0);
                        BossFx.particle(Particle.BUBBLE_POP, c.clone().add(Math.cos(a) * rr, 0.3, Math.sin(a) * rr), 2, 0.1, 0.1, 0.1, 0);
                    }
                    for (Player pl : players()) {
                        if (!shape.contains(pl.getLocation())) continue;
                        if (tt % 4 == 0) pull(pl, c, pullStr * 2.4);
                        if (tt % 20 == 0 && horizontal(pl.getLocation(), c) <= 1.4) hit(pl, centerDmg, "whirlpool", DamageType.MAGIC);
                    }
                    return true;
                }, () -> fx.discard(swirl), false));
            });
        }
        return cast("whirlpool", "소용돌이", Math.min(w, 20), 20, BossAnim.SPIN, null, false);
    }

    private int floodlingTide() {
        Params p = def.pattern("floodling_tide");
        String add = p.str("add", "floodling");
        int n = Math.min(scaling().count(p, "count", 2, 0), Math.max(0, p.integer("max_alive", 10) - aliveAdds(add)));
        if (n <= 0) return 0;
        for (int i = 0; i < n; i++) {
            Location at = randomPoint(3, arenaRadius - 2);
            for (int tries = 0; tries < 6 && nearPlatform(at); tries++) at = randomPoint(3, arenaRadius - 2);
            Location spawnAt = at;
            after(8 + i * 3, () -> {
                BossFx.particle(Particle.SPLASH, spawnAt.clone().add(0, 0.5, 0), 30, 0.4, 0.6, 0.4, 0.1);
                BossFx.sound(spawnAt, Sound.ENTITY_DROWNED_AMBIENT_WATER, 1.2f, 0.6f);
                spawnAdd(add, spawnAt);
            });
        }
        broadcastBar("<aqua>범람 정령이 수면에서 솟아오릅니다!</aqua> <gray>단상 위에서 터뜨리지 마세요");
        return cast("floodling_tide", "범람 정령", 20, 24, BossAnim.ROAR, null, false);
    }

    private boolean nearPlatform(Location l) {
        for (Location p : platforms) if (horizontal(p, l) < def.arena().dbl("platform_radius", 2.5) + 1) return true;
        return false;
    }

    @Override
    protected void onEnd() {
        fx.discard(water);
        hideTimerBar();
    }
}
