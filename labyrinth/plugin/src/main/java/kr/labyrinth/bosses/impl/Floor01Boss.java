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
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/**
 * 지하 1층 — 이끼 파수꾼 그로브 (GDD §7.1, core {@code destructible_pillars}).
 * 핵심: 표식 돌진을 이끼 기둥에 유도 → 기둥 파괴 + 4초 기절·받는 피해 +50%. 기둥은 소모 자원(새싹 소환의 출처이자
 * 3페이즈 2연속 돌진의 방패), 남은 기둥이 0이면 3페이즈 피해 +30%.
 * 패턴: vine_lash(부채꼴) · root_snare(발밑 원 + 속박) · rampage_charge(표식→화살표→돌진) · spore_burst(자기 중심 원 + 독)
 * · sproutling_call(기둥에서 새싹) · overgrowth(3페이즈 2연속 돌진).
 */
public final class Floor01Boss extends Boss {

    private static final class Pillar {
        final Location base;
        final List<Block> blocks = new ArrayList<>();
        final List<BlockDisplay> displays = new ArrayList<>();
        int crashes;
        boolean alive = true;

        Pillar(Location base) { this.base = base; }
    }

    private final List<Pillar> pillars = new ArrayList<>();
    private double pillarRadius = 1;

    public Floor01Boss(Init init) { super(init); }

    // ── 아레나: 이끼 기둥 ────────────────────────────────────────────────

    @Override
    protected void onSpawn() {
        Params mp = def.pattern("moss_pillars");
        int count = BossMath.countPerMembers(mp.dbl("count", 4), mp.dbl("extra_per_members", 4), partySize());
        double ring = Math.min(arenaRadius - 3, mp.dbl("ring_radius", 8));
        int pr = Math.max(0, mp.integer("pillar_radius", 1));
        int h = Math.max(2, mp.integer("height", 5));
        pillarRadius = pr;
        BlockData moss = blockData(mp.str("block", "MOSSY_STONE_BRICKS"), Material.MOSSY_STONE_BRICKS);
        // 남쪽(+z, 각도 90°)은 처치 후 계단 자리, 북쪽(270°)은 입구 — 둘 다 피해서 배치
        double[] angles = BossMath.ringAngles(count, 90, 26);
        for (double a : angles) {
            if (BossMath.angleGap(a, 270) < 14) a += 18;
            Location c = ringPoint(a, ring);
            Location base = c.getBlock().getLocation().add(0.5, 0, 0.5);
            base.setY(center.getBlockY());
            Pillar p = new Pillar(base);
            for (int dx = -pr; dx <= pr; dx++) {
                for (int dz = -pr; dz <= pr; dz++) {
                    if (dx * dx + dz * dz > pr * pr + 0.5) continue;
                    int bx = base.getBlockX() + dx, bz = base.getBlockZ() + dz;
                    if (BossMath.inStairZone(bx + 0.5 - center.getX(), bz + 0.5 - center.getZ(), 2.5)) continue;
                    boolean placed = false;
                    for (int y = 0; y < h; y++) {
                        Block b = center.getWorld().getBlockAt(bx, base.getBlockY() + y, bz);
                        if (setBlock(b, moss)) {
                            p.blocks.add(b);
                            placed = true;
                        }
                    }
                    if (!placed) {
                        Location corner = new Location(center.getWorld(), bx, base.getBlockY(), bz);
                        BlockDisplay d = fx.block(corner, moss, 1f, h, 1f);
                        if (d != null) p.displays.add(d);
                    }
                }
            }
            pillars.add(p);
            BossFx.particle(Particle.HAPPY_VILLAGER, base.clone().add(0, h / 2.0, 0), 12, 0.6, h / 3.0, 0.6, 0);
        }
    }

    private static BlockData blockData(String name, Material def) {
        Material m = Material.matchMaterial(name == null ? "" : name);
        return (m != null && m.isBlock() ? m : def).createBlockData();
    }

    private List<Pillar> alivePillars() {
        List<Pillar> out = new ArrayList<>();
        for (Pillar p : pillars) if (p.alive) out.add(p);
        return out;
    }

    private void crashInto(Pillar p) {
        Params mp = def.pattern("moss_pillars");
        p.crashes++;
        int need = Math.max(1, mp.integer("crashes_to_break", 1));
        BlockData crack = blockData(mp.str("crack_block", "CRACKED_STONE_BRICKS"), Material.CRACKED_STONE_BRICKS);
        BossFx.sound(p.base, Sound.BLOCK_STONE_BREAK, 2f, 0.5f);
        BossFx.sound(p.base, Sound.ENTITY_GENERIC_EXPLODE, 0.9f, 0.7f);
        BossFx.particle(Particle.EXPLOSION, p.base.clone().add(0, 1.5, 0), 2, 0.5, 0.8, 0.5, 0);
        BossFx.particle(Particle.SPORE_BLOSSOM_AIR, p.base.clone().add(0, 2, 0), 40, 1, 1.5, 1, 0);
        if (p.crashes >= need) {
            p.alive = false;
            // 밑동만 금 간 돌로 남기고 무너뜨린다 (인스턴스 블록 — 층 정리 때 원기둥째 비워짐)
            for (Block b : p.blocks) {
                if (b.getY() == p.base.getBlockY()) setBlock(b, crack);
                else setBlock(b, Material.AIR.createBlockData());
            }
            for (BlockDisplay d : p.displays) fx.discard(d);
            p.displays.clear();
            if (!pillars.isEmpty()) {
                int left = alivePillars().size();
                broadcastBar("<green>이끼 기둥이 무너졌다!</green> <gray>남은 기둥 " + left);
            }
        } else {
            for (Block b : p.blocks) if (rng.nextDouble() < 0.4) setBlock(b, crack);
        }
    }

    // ── 패턴 ─────────────────────────────────────────────────────────────

    @Override
    protected boolean canUse(String key) {
        if (key.equals("sproutling_call")) {
            Params p = def.pattern(key);
            return !alivePillars().isEmpty() && aliveAdds(p.str("add", "moss_sproutling")) < p.integer("max_alive", 8);
        }
        return target() != null;
    }

    @Override
    protected int startPattern(String key) {
        return switch (key) {
            case "vine_lash" -> vineLash();
            case "root_snare" -> rootSnare();
            case "rampage_charge" -> rampageCharge();
            case "spore_burst" -> sporeBurst();
            case "sproutling_call" -> sproutlingCall();
            default -> 0;
        };
    }

    @Override
    protected double outgoingMult() {
        Params og = def.pattern("overgrowth");
        if (phase() >= og.integer("phase", 3) && !pillars.isEmpty() && alivePillars().isEmpty()) return 1 + og.dbl("no_pillar_enrage", 0.3);
        return 1.0;
    }

    @Override
    protected void onPhase(int newPhase) {
        Params og = def.pattern("overgrowth");
        if (newPhase == og.integer("phase", 3)) {
            broadcastBar("<dark_green><b>대번성</b></dark_green> <gray>— 그로브의 발걸음이 멈출 줄 모른다" + (alivePillars().isEmpty() ? "… <red>가로막을 것이 하나도 남지 않았다</red>" : "…"));
            BossFx.particle(Particle.SPORE_BLOSSOM_AIR, center.clone().add(0, 3, 0), 120, arenaRadius * 0.6, 2, arenaRadius * 0.6, 0);
        }
    }

    /** 덩굴 채찍: 위협 1위 방향 부채꼴. */
    private int vineLash() {
        Params p = def.pattern("vine_lash");
        Player t = target();
        if (t == null) return 0;
        int w = windup(p, 1.0);
        Vector dir = t.getLocation().toVector().subtract(entity.getLocation().toVector());
        Telegraph.Shape cone = Telegraph.Shape.cone(feet(), dir, p.dbl("angle", 90), p.dbl("length", 6));
        double dmg = dmg(p, "damage", 1.3);
        telegraph(cone, w, Telegraph.RED, null, () -> {
            hitShape(cone, dmg, "vine_lash", DamageType.MELEE, pl -> push(pl, pl.getLocation().toVector().subtract(cone.origin().toVector()), 0.5, 0.25));
            BossFx.sound(entity.getLocation(), Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1.4f, 0.5f);
            Vector d = cone.direction();
            for (int i = 1; i <= 6; i++) BossFx.particle(Particle.SPORE_BLOSSOM_AIR, cone.origin().clone().add(d.clone().multiply(i)).add(0, 1, 0), 3, 0.6, 0.3, 0.6, 0);
        });
        return cast("vine_lash", "덩굴 채찍", w, w + 8, BossAnim.SWEEP, t.getLocation(), false);
    }

    /** 뿌리 속박: 플레이어 발밑 원 여러 개 → 피해 + 속박. */
    private int rootSnare() {
        Params p = def.pattern("root_snare");
        int count = scaling().count(p, "count", 2, 10);
        List<Player> ts = pickTargets(count, null, false);
        if (ts.isEmpty()) return 0;
        int w = windup(p, 1.4);
        double r = p.dbl("radius", 2.0);
        double dmg = dmg(p, "damage", 0.8);
        double root = p.dbl("root", 2.0);
        List<Location> spots = new ArrayList<>();
        for (Player t : ts) spots.add(ground(t.getLocation()));
        // 인원보다 개수가 많으면(난이도 추가분) 무작위 대상 주변에 덧붙인다
        while (spots.size() < count) {
            Player t = ts.get(rng.nextInt(ts.size()));
            Location l = t.getLocation().add(rng.nextGaussian() * 2.5, 0, rng.nextGaussian() * 2.5);
            spots.add(ground(l));
        }
        for (Location s : spots) {
            Telegraph.Shape c = Telegraph.Shape.circle(s, r);
            telegraph(c, w, Telegraph.RED, null, () -> {
                hitShape(c, dmg, "root_snare", DamageType.MAGIC, pl -> effect(pl, "root", root, 1));
                BossFx.particle(Particle.CRIT, c.origin().clone().add(0, 0.3, 0), 12, r * 0.5, 0.2, r * 0.5, 0.1);
                BossFx.dustRing(c.origin(), r * 0.7, org.bukkit.Color.fromRGB(90, 120, 40), 1.6f, 14);
                BossFx.sound(c.origin(), Sound.BLOCK_ROOTS_BREAK, 1.4f, 0.6f);
            });
        }
        return cast("root_snare", "뿌리 속박", Math.min(w, 20), 16, BossAnim.CAST, null, false);
    }

    /** 돌진 (핵심): 표식 → 화살표 → 직선 돌진, 기둥 충돌 = 붕괴 + 기절. */
    private int rampageCharge() {
        Player t = scaling().solo() ? target() : randomTarget();
        if (t == null) return 0;
        Params p = def.pattern("rampage_charge");
        Params og = def.pattern("overgrowth");
        boolean doubleCharge = phase() >= og.integer("phase", 3) && og.bool("double_charge", true);
        startCharge(t, p, doubleCharge, null);
        int mark = windupSec(p.dbl("mark_time", 2.0));
        return mark + ticks(p.dbl("max_distance", 28) / Math.max(0.2, p.dbl("speed", 1.4))) + 30;
    }

    private void startCharge(Player t, Params p, boolean chainNext, Player previous) {
        int mark = windupSec(p.dbl("mark_time", 2.0));
        double width = p.dbl("width", 3.0);
        double maxDist = p.dbl("max_distance", 28);
        run(new Mechanics.Marker(fx, "marker_target", t, mark, null));
        notify(t, "<light_purple><b>⚠ 돌진 표식!</b></light_purple> <gray>그로브의 눈이 당신을 붙잡았다…");
        BossFx.sound(t.getLocation(), Sound.BLOCK_NOTE_BLOCK_BELL, 1f, 0.6f);
        Telegraph.Shape init = Telegraph.Shape.arrow(feet(), dirTo(t), Math.min(maxDist, horizontalTo(t) + 4), width);
        final Vector[] locked = {init.direction()};
        Telegraph tg = new Telegraph(fx, init, mark, Telegraph.PURPLE, null, () -> charge(locked[0], p, chainNext, t));
        tg.onTick(g -> {
            if (g.elapsed() < g.total() - 6 && t.isValid()) {
                locked[0] = dirTo(t);
                g.reshape(Telegraph.Shape.arrow(feet(), locked[0], Math.min(maxDist, horizontalTo(t) + 4), width));
                faceNow(t.getLocation());
            }
        });
        run(tg);
        cast("rampage_charge", "돌진", mark, mark + 10, BossAnim.CHARGE, t.getLocation(), false);
        setPathing(false);
    }

    private Vector dirTo(Player t) {
        Vector d = t.getLocation().toVector().subtract(entity.getLocation().toVector()).setY(0);
        return d.lengthSquared() < 1e-4 ? facing() : d.normalize();
    }

    private double horizontalTo(Player t) {
        Location a = entity.getLocation(), b = t.getLocation();
        return Math.hypot(a.getX() - b.getX(), a.getZ() - b.getZ());
    }

    private void charge(Vector dir, Params p, boolean chainNext, Player first) {
        double speed = p.dbl("speed", 1.4) * scaling().speedMult();
        double maxDist = p.dbl("max_distance", 28);
        double width = p.dbl("width", 3.0);
        double dmg = dmg(p, "damage", 2.0);
        double kb = p.dbl("knockback", 1.2);
        float yaw = BossMath.yawOf(dir.getX(), dir.getZ());
        lockYaw(yaw);
        BossFx.sound(entity.getLocation(), Sound.ENTITY_RAVAGER_ROAR, 1.6f, 0.7f);
        java.util.Set<java.util.UUID> hit = new java.util.HashSet<>();
        final double[] travelled = {0};
        int maxTicks = (int) Math.ceil(maxDist / speed) + 2;
        busyFor(maxTicks + 20);
        run(new Mechanics.Repeat(maxTicks, 1, tt -> {
            Location from = entity.getLocation();
            Location to = from.clone().add(dir.clone().multiply(speed));
            to.setYaw(yaw);
            // 기둥 충돌
            for (Pillar pl : alivePillars()) {
                if (BossMath.segmentDist2(from.getX(), from.getZ(), to.getX(), to.getZ(), pl.base.getX(), pl.base.getZ())
                        <= Math.pow(pillarRadius + 1.1, 2)) {
                    crashInto(pl);
                    double stun = p.dbl("stun", 4.0);
                    stun(stun);
                    makeVulnerable(p.dbl("vulnerable", 0.5), stun);
                    rig.play(BossAnim.STUN, ticks(stun), now);
                    setPathing(true);
                    return false;
                }
            }
            // 벽·아레나 끝
            boolean wall = to.clone().add(0, 0.5, 0).getBlock().getType().isSolid() || to.clone().add(0, 1.5, 0).getBlock().getType().isSolid()
                    || Math.hypot(to.getX() - center.getX(), to.getZ() - center.getZ()) > arenaRadius - 1.2;
            if (wall || travelled[0] >= maxDist) {
                if (wall) {
                    BossFx.sound(from, Sound.ENTITY_IRON_GOLEM_DAMAGE, 1.5f, 0.5f);
                    BossFx.particle(Particle.CLOUD, from.clone().add(0, 1, 0), 10, 0.6, 0.6, 0.6, 0.05);
                }
                int recover = ticks(p.dbl("wall_recover", 1.0));
                releaseBusy();
                busyFor(recover);
                rig.play(BossAnim.STUN, recover, now);
                afterPersistent(recover, () -> setPathing(true));
                if (chainNext && !stunned()) chain(p, first);
                return false;
            }
            entity.teleport(to);
            travelled[0] += speed;
            for (Player pl : players()) {
                if (hit.contains(pl.getUniqueId())) continue;
                Location l = pl.getLocation();
                if (BossMath.segmentDist2(from.getX(), from.getZ(), to.getX(), to.getZ(), l.getX(), l.getZ()) <= Math.pow(width / 2, 2)
                        && Math.abs(l.getY() - to.getY()) < 3) {
                    hit.add(pl.getUniqueId());
                    hit(pl, dmg, "rampage_charge", DamageType.MELEE);
                    Vector side = l.toVector().subtract(to.toVector()).setY(0);
                    push(pl, dir.clone().multiply(0.7).add(side.lengthSquared() > 1e-4 ? side.normalize().multiply(0.5) : new Vector()), kb, 0.45);
                }
            }
            if (tt % 2 == 0) BossFx.particle(Particle.CAMPFIRE_COSY_SMOKE, from.clone().add(0, 0.2, 0), 2, 0.4, 0.05, 0.4, 0.01);
            if (tt % 3 == 0) BossFx.sound(from, Sound.ENTITY_IRON_GOLEM_STEP, 1.4f, 0.6f);
            return true;
        }, () -> {
            if (!stunned()) afterPersistent(ticks(p.dbl("wall_recover", 1.0)), () -> setPathing(true));
            else setPathing(true);
        }, true));
    }

    /** 대번성: 첫 돌진이 끝나면 1초 뒤 다른 대상에게 두 번째 돌진. */
    private void chain(Params p, Player first) {
        Params og = def.pattern("overgrowth");
        int delay = ticks(og.dbl("second_mark_delay", 1.0));
        busyFor(delay + windupSec(p.dbl("mark_time", 2.0)) + 40);
        after(delay, () -> {
            List<Player> others = pickTargets(1, first == null ? List.of() : List.of(first), false);
            Player t = others.isEmpty() ? target() : others.get(0);
            if (t != null) startCharge(t, p, false, null);
        });
    }

    /** 포자 폭발: 보스 중심 원 → 피해 + 독. */
    private int sporeBurst() {
        Params p = def.pattern("spore_burst");
        int w = windup(p, 1.5);
        double r = p.dbl("radius", 6);
        Telegraph.Shape c = Telegraph.Shape.circle(feet(), r);
        double dmg = dmg(p, "damage", 1.0);
        telegraph(c, w, Telegraph.RED, null, () -> {
            hitShape(c, dmg, "spore_burst", DamageType.MAGIC, pl -> effect(pl, p.str("effect", "poison"), p.dbl("effect_duration", 4), 0));
            BossFx.particle(Particle.SPORE_BLOSSOM_AIR, c.origin().clone().add(0, 1, 0), 120, r * 0.6, 1, r * 0.6, 0);
            BossFx.particle(Particle.SNEEZE, c.origin().clone().add(0, 0.8, 0), 60, r * 0.5, 0.6, r * 0.5, 0.05);
            BossFx.sound(c.origin(), Sound.BLOCK_AZALEA_LEAVES_BREAK, 2f, 0.5f);
            BossFx.sound(c.origin(), Sound.ENTITY_PUFFER_FISH_BLOW_UP, 1.5f, 0.6f);
        });
        run(new Mechanics.Repeat(w, 4, tt -> {
            BossFx.particle(Particle.SPORE_BLOSSOM_AIR, entity.getLocation().add(0, 2.5, 0), 6, 0.8, 0.6, 0.8, 0);
            return true;
        }, null, true));
        return cast("spore_burst", "포자 폭발", w, w + 10, BossAnim.CAST, null, false);
    }

    /** 새싹 부르기: 남은 기둥에서 이끼 새싹 (기둥이 많이 남을수록 많이). */
    private int sproutlingCall() {
        Params p = def.pattern("sproutling_call");
        List<Pillar> alive = alivePillars();
        if (alive.isEmpty()) return 0;
        String add = p.str("add", "moss_sproutling");
        int base = scaling().count(p, "count", 2, 0);
        int byPillars = (int) Math.ceil(base * alive.size() / (double) Math.max(1, pillars.size()));
        int room = Math.max(0, p.integer("max_alive", 8) - aliveAdds(add));
        int n = Math.min(room, Math.max(1, byPillars));
        if (n <= 0) return 0;
        for (int i = 0; i < n; i++) {
            Pillar pl = alive.get(i % alive.size());
            Vector in = center.toVector().subtract(pl.base.toVector()).setY(0);
            if (in.lengthSquared() > 1e-4) in.normalize();
            Location at = pl.base.clone().add(in.multiply(pillarRadius + 1.4)).add(rng.nextGaussian() * 0.6, 0.1, rng.nextGaussian() * 0.6);
            after(10 + i * 4, () -> {
                BossFx.particle(Particle.HAPPY_VILLAGER, at.clone().add(0, 0.5, 0), 20, 0.4, 0.6, 0.4, 0);
                BossFx.sound(at, Sound.BLOCK_BIG_DRIPLEAF_PLACE, 1.2f, 0.8f);
                spawnAdd(add, at);
            });
        }
        broadcastBar("<green>이끼 기둥에서 새싹이 꿈틀거린다…</green>");
        return cast("sproutling_call", "새싹 부르기", 24, 30, BossAnim.ROAR, null, false);
    }

    @Override
    protected void onEnd() {
        for (Pillar p : pillars) for (BlockDisplay d : p.displays) fx.discard(d);
    }
}
