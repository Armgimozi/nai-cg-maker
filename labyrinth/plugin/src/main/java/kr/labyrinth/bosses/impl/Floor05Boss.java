package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.bosses.Boss;
import kr.labyrinth.bosses.BossAnim;
import kr.labyrinth.bosses.BossFx;
import kr.labyrinth.bosses.BossMath;
import kr.labyrinth.bosses.Mechanics;
import kr.labyrinth.bosses.Telegraph;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.Params;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.entity.Display;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.util.Vector;

/**
 * 지하 5층 — 모루왕 카르둠 (GDD §7.5, core {@code knockback_edge}).
 * 핵심: 방사형 넉백(단조 진동) → 바깥 용암 해자. 대응 = 보스와 해자 사이에 서지 않기 / 쇠사슬 말뚝 2칸 안에서 웅크리기(말뚝당 2명,
 * 넉백 면역) / 수호기사 불굴의 성채(넉백 면역 상태이상). 용암에 닿으면 현재 최대 HP 30% + 불 끔 + 안전한 바닥으로 튕겨 올림
 * (바닐라 용암 피해는 취소, DamageService 경로).
 * 패턴: hammer_swing · forge_quake · molten_pour(평행선 3줄 + 쇳물 장판) · hammer_toss(왕복) · bellows_gale(한 방향 바람)
 * · anvil_crush(돌풍 → 1초 뒤 같은 방향 진동).
 */
public final class Floor05Boss extends Boss {

    private double moatInner, moatOuter;
    private final List<Location> anchors = new ArrayList<>();
    private final Set<UUID> gripping = new HashSet<>();
    private final Map<UUID, Long> lavaCooldown = new HashMap<>();
    private final List<ItemDisplay> fakeLava = new ArrayList<>();

    public Floor05Boss(Init init) { super(init); }

    // ── 아레나: 용암 해자 + 쇠사슬 말뚝 ──────────────────────────────────

    @Override
    protected void onSpawn() {
        Params a = def.arena();
        double w = Math.max(1, a.dbl("moat_width", 2));
        moatOuter = arenaRadius;
        moatInner = arenaRadius - w;
        Material moat = Material.matchMaterial(a.str("moat", "LAVA"));
        if (moat == null || !moat.isBlock()) moat = Material.LAVA;
        int y = center.getBlockY() - 1;
        boolean real = false;
        int r = (int) Math.ceil(moatOuter) + 1;
        for (int dx = -r; dx <= r; dx++) {
            for (int dz = -r; dz <= r; dz++) {
                double d = Math.hypot(dx + 0.5 - (center.getX() - center.getBlockX()), dz + 0.5 - (center.getZ() - center.getBlockZ()));
                if (d <= moatInner || d > moatOuter) continue;
                Block floor = center.getWorld().getBlockAt(center.getBlockX() + dx, y, center.getBlockZ() + dz);
                Block above = floor.getRelative(0, 1, 0);
                if (!floor.getType().isSolid() || !above.getType().isAir()) continue; // 아레나 바닥만 (벽·장식 제외)
                Block below = floor.getRelative(0, -1, 0);
                if (!below.getType().isSolid()) setBlock(below, Material.BLACKSTONE.createBlockData());
                if (setBlock(floor, moat.createBlockData())) real = true;
            }
        }
        if (!real) {
            // 인스턴스 밖(관리자 소환): 블록 대신 쇳물 웅덩이 디스플레이로 해자 표시 — 판정은 같다
            int n = (int) Math.ceil(2 * Math.PI * (moatInner + w / 2) / 1.4);
            for (int i = 0; i < n; i++) {
                double ang = 360.0 * i / n;
                Location l = ringPoint(ang, moatInner + w / 2);
                l.setY(center.getY() + 0.02);
                fakeLava.add(fx.flat("molten_puddle", l, (float) (w / 1.5 * 1.1), (float) (1.6 / 1.5), (float) (ang + 90)));
            }
        }
        // 해자 위에 서 있던 사람은 안쪽으로
        for (Player p : players()) {
            double d = horizontal(p.getLocation(), center);
            if (d > moatInner - 0.5) launchInward(p);
        }
        Params grip = def.pattern("chain_grip");
        int count = Math.max(1, grip.integer("anchors", a.integer("anchors", 6)));
        for (double ang : BossMath.ringAngles(count, 90, 20)) {
            if (BossMath.angleGap(ang, 270) < 12) ang += 15;
            Location l = ringPoint(ang, moatInner - 1.2);
            l.setY(center.getY());
            anchors.add(l);
            fx.model(grip.str("fx", "chain_anchor"), l.clone().add(0, 0.75, 0), 1.6f, Display.Billboard.FIXED);
            fx.label(l.clone().add(0, 2.5, 0), "<#ffb04a>쇠사슬 말뚝</#ffb04a>", 0.7f);
        }
    }

    private boolean inMoat(Location l) {
        double d = horizontal(l, center);
        return d > moatInner && d <= moatOuter + 0.6 && l.getY() < floorY + 0.25;
    }

    private void launchInward(Player p) {
        Vector out = p.getLocation().toVector().subtract(center.toVector()).setY(0);
        if (out.lengthSquared() < 1e-4) out = new Vector(1, 0, 0);
        out.normalize();
        Location safe = center.clone().add(out.multiply(Math.max(1, moatInner - 2.0)));
        safe.setY(floorY + 0.1);
        safe.setYaw(p.getLocation().getYaw());
        safe.setPitch(p.getLocation().getPitch());
        p.teleport(safe);
        p.setFireTicks(0);
        p.setVelocity(new Vector(0, 0.55, 0));
    }

    @Override
    protected void onTick() {
        // 쇠사슬 붙잡기: 말뚝 2칸 안에서 웅크린 사람 (말뚝당 최대 2명, 가까운 순)
        Params grip = def.pattern("chain_grip");
        double gr = grip.dbl("grip_radius", 2.0);
        int max = grip.integer("max_grips_per_anchor", 2);
        boolean needSneak = grip.bool("sneak_required", true);
        gripping.clear();
        List<Player> ps = players();
        for (Location a : anchors) {
            List<Player> near = new ArrayList<>();
            for (Player p : ps) if ((!needSneak || p.isSneaking()) && horizontal(p.getLocation(), a) <= gr && !gripping.contains(p.getUniqueId())) near.add(p);
            near.sort(Comparator.comparingDouble(p -> horizontal(p.getLocation(), a)));
            for (int i = 0; i < Math.min(max, near.size()); i++) {
                Player p = near.get(i);
                gripping.add(p.getUniqueId());
                if (now % 4 == 0) BossFx.dustLine(a.clone().add(0, 1.2, 0), p.getLocation().add(0, 0.9, 0), Color.fromRGB(150, 150, 160), 0.7f, 0.4);
            }
        }
        // 용암 접촉
        for (Player p : ps) {
            if (!inMoat(p.getLocation())) continue;
            long last = lavaCooldown.getOrDefault(p.getUniqueId(), -100L);
            if (now - last < 15) continue;
            lavaCooldown.put(p.getUniqueId(), now);
            hitPct(p, def.pattern("forge_quake").dbl("lava_damage_pct", 0.3), "lava_moat");
            BossFx.sound(p.getLocation(), Sound.BLOCK_LAVA_EXTINGUISH, 1.4f, 0.8f);
            BossFx.particle(Particle.LAVA, p.getLocation().add(0, 0.5, 0), 12, 0.3, 0.3, 0.3, 0);
            notify(p, "<red><b>용암 해자!</b></red> <gray>살이 타들어 간다…");
            if (def.pattern("forge_quake").bool("lava_return", true)) launchInward(p);
        }
        if (now % 10 == 0 && !fakeLava.isEmpty()) {
            Location l = ringPoint(rng.nextDouble() * 360, moatInner + (moatOuter - moatInner) / 2);
            l.setY(floorY + 0.2);
            BossFx.particle(Particle.LAVA, l, 1, 0.2, 0, 0.2, 0);
        }
    }

    @Override
    protected boolean knockbackImmune(Player p) {
        return gripping.contains(p.getUniqueId()) || super.knockbackImmune(p);
    }

    @Override
    protected void onPlayerVanillaDamage(Player p, EntityDamageEvent e) {
        switch (e.getCause()) {
            case LAVA, FIRE, FIRE_TICK, HOT_FLOOR -> {
                e.setCancelled(true);
                p.setFireTicks(0);
            }
            default -> { }
        }
    }

    // ── 패턴 ─────────────────────────────────────────────────────────────

    @Override
    protected boolean canUse(String key) { return target() != null; }

    @Override
    protected int startPattern(String key) {
        return switch (key) {
            case "hammer_swing" -> hammerSwing();
            case "forge_quake" -> forgeQuake(null, 0);
            case "molten_pour" -> moltenPour();
            case "hammer_toss" -> hammerToss();
            case "bellows_gale" -> bellowsGale(null);
            case "anvil_crush" -> anvilCrush();
            default -> 0;
        };
    }

    private Vector dirTo(Location to) {
        Vector d = to.toVector().subtract(entity.getLocation().toVector()).setY(0);
        return d.lengthSquared() < 1e-4 ? facing() : d.normalize();
    }

    private int hammerSwing() {
        Params p = def.pattern("hammer_swing");
        Player t = target();
        if (t == null) return 0;
        int w = windup(p, 0.9);
        Telegraph.Shape cone = Telegraph.Shape.cone(feet(), dirTo(t.getLocation()), p.dbl("angle", 100), p.dbl("length", 5));
        double dmg = dmg(p, "damage", 1.4);
        telegraph(cone, w, Telegraph.RED, null, () -> {
            hitShape(cone, dmg, "hammer_swing", DamageType.MELEE, pl -> push(pl, pl.getLocation().toVector().subtract(cone.origin().toVector()), 0.6, 0.3));
            BossFx.sound(entity.getLocation(), Sound.BLOCK_ANVIL_LAND, 1.2f, 0.6f);
            BossFx.particle(Particle.LAVA, cone.origin().clone().add(cone.direction().multiply(3)).add(0, 0.5, 0), 6, 1, 0.2, 1, 0);
        });
        return cast("hammer_swing", "망치 휘두르기", w, w + 8, BossAnim.SWEEP, t.getLocation(), false);
    }

    /**
     * 단조 진동: 아레나 전체 피해 + 강한 넉백. direction null = 보스 반대 방향(방사형), 아니면 그 방향(모루 분쇄).
     * @param windupOverride 0 이면 YAML windup
     */
    private int forgeQuake(Vector direction, int windupOverride) {
        Params p = def.pattern("forge_quake");
        int w = windupOverride > 0 ? windupOverride : windup(p, 2.0);
        Location c = feet();
        Telegraph.Shape all = Telegraph.Shape.ring(c, 1.5, arenaRadius + 1);
        double dmg = dmg(p, "damage", 1.0);
        double kb = p.dbl("knockback", 2.4);
        double up = p.dbl("vertical", 0.4);
        telegraph(all, w, Telegraph.ORANGE, p.str("fx", "telegraph_ring"), () -> {
            for (Player pl : players()) {
                if (Math.abs(pl.getLocation().getY() - c.getY()) > 4) continue;
                hit(pl, dmg, "forge_quake", DamageType.MAGIC);
                Vector away = direction != null ? direction.clone() : pl.getLocation().toVector().subtract(c.toVector());
                push(pl, away, kb, up);
            }
            BossFx.sound(c, Sound.BLOCK_ANVIL_LAND, 2f, 0.4f);
            BossFx.sound(c, Sound.ENTITY_GENERIC_EXPLODE, 1.4f, 0.5f);
            BossFx.particle(Particle.EXPLOSION, c.clone().add(0, 0.5, 0), 4, 1, 0.2, 1, 0);
            for (int i = 1; i <= 6; i++) {
                double rr = arenaRadius * i / 6.0;
                after(i, () -> BossFx.ring(c, rr, Particle.FLAME, (int) (rr * 6)));
            }
        });
        // 경고 동안 보스 중심에서 주황 링이 퍼져 나간다
        run(new Mechanics.Repeat(w, 4, tt -> {
            double rr = arenaRadius * ((tt % 20) / 20.0);
            BossFx.dustRing(c, Math.max(1, rr), Telegraph.ORANGE, 1.4f, (int) Math.max(10, rr * 5));
            return true;
        }, null, true));
        broadcastBar("<gold><b>단조 진동!</b></gold> <gray>모루가 울리고, 사슬이 낮게 운다…");
        return cast("forge_quake", "단조 진동", w, w + 12, BossAnim.SLAM, null, false);
    }

    private int moltenPour() {
        Params p = def.pattern("molten_pour");
        int lines = Math.max(1, p.integer("lines", 3) + (scaling().extraCount() > 0 ? 1 : 0));
        double width = p.dbl("width", 2);
        int w = windup(p, 1.5);
        double ang = rng.nextDouble() * 180;
        Vector dir = new Vector(BossMath.ax(ang), 0, BossMath.az(ang));
        Vector side = new Vector(-dir.getZ(), 0, dir.getX());
        double spacing = Math.max(width + 2.5, (arenaRadius * 2 - 2) / (lines + 1.0));
        double shift = (rng.nextDouble() - 0.5) * spacing * 0.6;
        double dmg = dmg(p, "damage", 1.2);
        double dps = dmg(p, "dps", 0.4);
        int dur = ticks(p.dbl("duration", 5));
        for (int i = 0; i < lines; i++) {
            double off = (i - (lines - 1) / 2.0) * spacing + shift;
            if (Math.abs(off) > arenaRadius - 1) continue;
            double half = Math.sqrt(Math.max(1, arenaRadius * arenaRadius - off * off));
            Location origin = center.clone().add(side.clone().multiply(off)).subtract(dir.clone().multiply(half));
            Telegraph.Shape line = Telegraph.Shape.line(origin, dir, half * 2, width);
            telegraph(line, w, Telegraph.RED, null, () -> {
                hitShape(line, dmg, "molten_pour", DamageType.MAGIC, pl -> pl.setFireTicks(0));
                BossFx.sound(origin.clone().add(dir.clone().multiply(half)), Sound.BLOCK_LAVA_POP, 2f, 0.5f);
                Location mid = origin.clone().add(dir.clone().multiply(half)).add(0, 0.04, 0);
                ItemDisplay puddle = fx.flat(p.str("fx", "molten_puddle"), mid, (float) (width / 1.5), (float) (half * 2 / 1.5), BossMath.yawOf(dir.getX(), dir.getZ()));
                run(new Mechanics.Zone(fx, line, dur, 20, null, null, Particle.LAVA, this::players,
                        pl -> hit(pl, dps, "molten_puddle", DamageType.TRUE)));
                afterPersistent(dur, () -> fx.discard(puddle));
                for (double f = 0; f < half * 2; f += 2) BossFx.particle(Particle.LAVA, origin.clone().add(dir.clone().multiply(f)).add(0, 0.5, 0), 2, 0.3, 0.2, 0.3, 0);
            });
        }
        return cast("molten_pour", "쇳물 붓기", w, w + 8, BossAnim.POUR, null, false);
    }

    private int hammerToss() {
        Params p = def.pattern("hammer_toss");
        Player t = randomTarget();
        if (t == null) return 0;
        int w = windup(p, 1.2);
        double len = p.dbl("length", 16);
        double width = p.dbl("width", 2.5);
        Vector dir = dirTo(t.getLocation());
        Location origin = feet();
        Telegraph.Shape line = Telegraph.Shape.line(origin, dir, len, width);
        double dmg = dmg(p, "damage", 1.5);
        int back = ticks(p.dbl("return_delay", 1.0));
        telegraph(line, w, Telegraph.RED, null, () -> {
            int out = Math.max(6, (int) Math.ceil(len / (1.3 * scaling().speedMult())));
            Location from = origin.clone().add(0, 1.2, 0);
            Mechanics.Projectile proj = new Mechanics.Projectile(fx, p.str("fx", "proj_hammer"), 1.8f,
                    Mechanics.Projectile.boomerang(from, dir, len, out, back), out * 2 + back, width / 2, false, Particle.FLAME, this::players,
                    pl -> {
                        hit(pl, dmg, "hammer_toss", DamageType.MELEE);
                        push(pl, dir.clone().add(new Vector(rng.nextGaussian() * 0.2, 0, rng.nextGaussian() * 0.2)), 0.6, 0.25);
                        BossFx.sound(pl.getLocation(), Sound.BLOCK_ANVIL_PLACE, 1f, 0.8f);
                    }, at -> BossFx.sound(at, Sound.BLOCK_ANVIL_LAND, 1f, 1.2f));
            proj.resetHitsAt(out + 1);
            run(proj);
            // 되돌아오는 경로 다시 경고
            after(out, () -> telegraph(line, back, Telegraph.RED, null, null));
            BossFx.sound(from, Sound.ITEM_TRIDENT_THROW, 1.6f, 0.5f);
        });
        busyFor(w + 40);
        return cast("hammer_toss", "망치 투척", w, w + 30, BossAnim.THROW, t.getLocation(), false);
    }

    /** 풀무 돌풍: 화살표 방향으로 3초간 계속 밀기. direction null = 무작위. @return 사용한 방향 */
    private int bellowsGale(Vector direction) {
        Params p = def.pattern("bellows_gale");
        Vector dir = direction != null ? direction : randomGaleDir();
        int w = windup(p, 2.0);
        Location origin = center.clone().subtract(dir.clone().multiply(arenaRadius - 1));
        Telegraph.Shape arrow = Telegraph.Shape.arrow(origin, dir, arenaRadius * 2 - 2, Math.max(4, arenaRadius * 0.7));
        double strength = p.dbl("strength", 0.18) * scaling().speedMult();
        int dur = ticks(p.dbl("duration", 3.0));
        telegraph(arrow, w, Telegraph.PURPLE, p.str("fx", "telegraph_arrow"), () -> {
            BossFx.sound(center, Sound.ENTITY_BREEZE_WIND_BURST, 2f, 0.5f);
            run(new Mechanics.Repeat(dur, 1, tt -> {
                for (Player pl : players()) {
                    if (knockbackImmune(pl)) continue;
                    Vector v = pl.getVelocity();
                    pl.setVelocity(v.add(dir.clone().multiply(strength * 0.45)).setY(Math.min(v.getY(), 0.2)));
                }
                if (tt % 2 == 0) {
                    for (int i = 0; i < 6; i++) {
                        Location l = randomPoint(0, arenaRadius - 1).add(0, 0.6 + rng.nextDouble() * 1.6, 0);
                        l.getWorld().spawnParticle(Particle.CLOUD, l, 0, dir.getX(), 0, dir.getZ(), 0.6);
                    }
                }
                if (tt % 10 == 0) BossFx.sound(center, Sound.ITEM_ELYTRA_FLYING, 0.6f, 1.4f);
                return true;
            }, null, true));
        });
        broadcastBar("<light_purple><b>풀무 돌풍!</b></light_purple> <gray>뜨거운 바람이 몰아친다…");
        return cast("bellows_gale", "풀무 돌풍", w, w + 10, BossAnim.CAST, null, false);
    }

    private Vector randomGaleDir() {
        // 남은 사람들이 해자 쪽으로 밀리도록 무작위 8방향
        double ang = rng.nextInt(8) * 45.0;
        return new Vector(BossMath.ax(ang), 0, BossMath.az(ang));
    }

    /** 모루 분쇄: 돌풍 화살표 → 돌풍 시작 1초 뒤 같은 방향 단조 진동. */
    private int anvilCrush() {
        Params p = def.pattern("anvil_crush");
        Params gale = def.pattern("bellows_gale");
        Vector dir = randomGaleDir();
        int galeW = windup(gale, 2.0);
        int delay = windupSec(p.dbl("gale_quake_delay", 1.0));
        bellowsGale(dir);
        // 돌풍이 불기 시작할 때 진동 경고가 깔리고 delay 뒤 터진다
        after(galeW, () -> forgeQuake(dir, delay));
        broadcastBar("<dark_red><b>모루 분쇄!</b></dark_red> <gray>바람이 길을 내고, 망치가 그 뒤를 따른다…");
        return cast("anvil_crush", "모루 분쇄", galeW + delay, galeW + delay + 14, BossAnim.CAST, null, false);
    }

    @Override
    protected void onEnd() {
        for (ItemDisplay d : fakeLava) fx.discard(d);
        fakeLava.clear();
        gripping.clear();
    }
}
