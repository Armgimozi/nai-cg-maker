package kr.augsky.vfx;

import kr.augsky.skill.SkillContext;
import kr.augsky.util.Fx;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Supplier;

/**
 * 한 번 시전의 연출 상태: 등급·무게·속성 팔레트·전용 연출, 그리고 이번 시전의 조각/입자/소리 예산.
 * 기술 부품(Mechanics)은 여기 메서드를 한 줄씩 부른다. 모든 공개 메서드는 예외를 삼킨다
 * (기술 쪽 BukkitRunnable 안에서 예외가 나면 투사체·돌진이 멈춰 판정이 바뀌기 때문).
 */
public final class CastFx {
    public static final int AUD_ALL = 0, AUD_NOPACK = 1, AUD_PACK = 2, AUD_SELF = 3, AUD_OTHERS = 4;

    /** 이번 사건에 쓸 색. rainbow 면 a 는 시간에 따라 색상환을 돈다 */
    public record Cols(Color a, Color b, Color dark, Color rim, boolean rainbow) {
        public Cols swap() {
            return new Cols(b, a, dark, rim, rainbow);
        }
    }

    public final Vfx vfx;
    public final LivingEntity caster;
    public final Player cp;
    public final Tier tier;
    public final Tier.Weight weight;
    public final Palette pal;
    public final String skill;
    public final int slot;
    final boolean off;
    final SkillContext root;
    Signature sig = Signature.NONE;
    final boolean night;
    /** 장판·궤도·소용돌이의 주기 판정 중 (작은 불꽃만) */
    public boolean ticking;
    int live, moving, hueSprites, debris, aud;
    final long born;
    private final Map<String, Integer> seq = new HashMap<>();
    private final Map<UUID, int[]> pk = new HashMap<>();
    private long pkAt = -1, sfxAt = -1, starAt = -1;
    private int sfxN, starN;
    private final Map<UUID, Long> hitAt = new HashMap<>();
    private double yamlAcc;
    /** 시그니처끼리 주고받는 상태 (예: 블랙홀 손잡이) */
    public final Map<String, Object> memo = new HashMap<>();

    CastFx(Vfx vfx, SkillContext ctx, String skill, Tier tier, Tier.Weight weight, Palette pal, int slot) {
        this.vfx = vfx;
        this.root = ctx;
        this.caster = ctx.caster;
        this.cp = ctx.caster instanceof Player p ? p : null;
        this.tier = tier;
        this.weight = weight;
        this.pal = pal;
        this.skill = skill;
        this.slot = slot;
        this.off = false;
        this.born = vfx.tick;
        this.night = darkAround(ctx.caster.getLocation());
    }

    private CastFx(Vfx vfx, LivingEntity caster) {
        this.vfx = vfx;
        this.root = null;
        this.caster = caster;
        this.cp = caster instanceof Player p ? p : null;
        this.tier = Tier.BASIC;
        this.weight = Tier.Weight.LIGHT;
        this.pal = Palette.of("iron");
        this.skill = "";
        this.slot = 0;
        this.off = true;
        this.born = vfx == null ? 0 : vfx.tick;
        this.night = false;
    }

    /** 연출 없이 원래 입자만 그대로 (설정으로 끄거나, 무기 패시브처럼 시전이 아닌 경우) */
    public static CastFx off(Vfx vfx, LivingEntity caster) {
        return new CastFx(vfx, caster);
    }

    /** 밤·네더·지붕 밑처럼 어두우면 테두리를 어두운 색 대신 바깥 빛 색으로 (더러운 윤곽선 방지) */
    private static boolean darkAround(Location l) {
        World w = l.getWorld();
        if (w == null) return false;
        if (w.getEnvironment() != World.Environment.NORMAL) return true;
        long t = w.getTime() % 24000;
        if (t > 12800 && t < 23200) return true;
        try {
            return l.getBlock().getLightFromSky() < 8;
        } catch (Throwable e) {
            return false;
        }
    }

    void start() {
        try {
            sig.cast(this);
        } catch (Throwable t) {
            vfx.warn("sig:" + skill, "전용 연출 오류(" + skill + "): " + t);
        }
        try {
            BuffFx.flourish(this);
        } catch (Throwable t) {
            vfx.warn("flourish", "시전 연출 오류: " + t);
        }
    }

    // ------------------------------------------------------------------ 등급·색

    public int rank() {
        return tier.rank;
    }

    public boolean mob() {
        return tier.mob();
    }

    public boolean ult() {
        return weight == Tier.Weight.ULT;
    }

    public boolean prism() {
        return tier == Tier.PRISM;
    }

    /** 섬광·하늘 연출·큰 별·많은 파편: 높은 등급의 궁극기와 보스 단계 변화만 */
    public boolean mayFlash() {
        return weight == Tier.Weight.ULT && tier.rank >= 3;
    }

    public int spriteCap() {
        return (int) Math.min(40, Math.max(1, Math.round(tier.sprites * weight.sprites * vfx.density())));
    }

    double packetCap() {
        return tier.packets * weight.packets * vfx.density() * particleBoost();
    }

    public double dens() {
        return tier.density * vfx.density() * (weight == Tier.Weight.LIGHT ? 0.85 : 1.0) * (vfx.spritesOn() ? 1 : 1.3);
    }

    /** 팩 그림 없이 입자로만 그리는 판: 그림이 하던 몫까지 입자가 맡으므로 한 틱에 보내는 양을 늘린다 */
    double particleBoost() {
        return vfx.spritesOn() ? 1 : 1.8;
    }

    /** n 을 등급 밀도로 늘리거나 줄인다 */
    public int n(double base) {
        return Math.max(1, (int) Math.round(base * dens()));
    }

    public int debrisFor(int wanted) {
        int max = weight == Tier.Weight.ULT ? tier.debris : Math.min(6, tier.debris);
        if (weight == Tier.Weight.LIGHT) max = Math.min(max, 3);
        int n = Math.min(Math.min(12, wanted), Math.max(0, Math.min(max, 24 - debris)));
        debris += n;
        return n;
    }

    public Color a() {
        return pal.rainbow() ? Palette.hue(vfx.tick * 0.02 + seqPeek() * 0.14) : pal.a();
    }

    public Color b() {
        return pal.b();
    }

    public Color dark() {
        return pal.dark();
    }

    public Color rim() {
        Color a = a();
        return night ? a : Palette.rimOf(a, pal.dark());
    }

    public Cols cols() {
        Color a = a();
        return new Cols(a, pal.b(), pal.dark(), night ? a : Palette.rimOf(a, pal.dark()), pal.rainbow());
    }

    /**
     * YAML 입자에 색이 적혀 있으면 그 색을 쓴다 (칠색 분광의 일곱 빛기둥 등).
     * 아주 어두운 색은 테두리로만, 거의 흰색은 안쪽 띠로만 쓴다 (빛 색이 검게 죽지 않게).
     */
    public Cols cols(Fx.Spec yaml) {
        Cols k = cols();
        Color[] yc = Palette.yamlColors(yaml);
        if (yc == null) return k;
        Color a = k.a(), b = k.b(), dark = k.dark();
        Color c0 = yc[0];
        if (Palette.luma(c0) < 0.25) dark = c0;
        else if (Palette.nearWhite(c0)) b = c0;
        else a = c0;
        if (yc.length > 1) {
            Color c1 = yc[1];
            if (Palette.luma(c1) < 0.25) dark = c1;
            else if (!Palette.nearWhite(c1) || Palette.nearWhite(c0)) b = c1;
        }
        boolean rainbow = k.rainbow() && yc == null;
        return new Cols(a, b, dark, night ? a : Palette.rimOf(a, dark), rainbow);
    }

    public int seq(String k) {
        return seq.merge(k, 1, Integer::sum) - 1;
    }

    private int seqPeek() {
        Integer n = seq.get("hue");
        return n == null ? 0 : n;
    }

    public long age() {
        return vfx.tick - born;
    }

    public Location eye() {
        return caster.getEyeLocation();
    }

    public boolean isSelf(Player p) {
        return cp != null && cp == p;
    }

    /** 오른손(왼손잡이면 왼손) 쪽 옆 방향 */
    public Vector handSide(Vector dir) {
        Shapes.Frame f = Shapes.Frame.flat(dir);
        Vector left = f.side().clone();
        boolean rightHanded = cp == null || cp.getMainHand() == org.bukkit.inventory.MainHand.RIGHT;
        return rightHanded ? left.multiply(-1) : left;
    }

    // ------------------------------------------------------------------ 예산

    /** 받는 사람별 이번 틱 패킷 예산. 예고·YAML 은 항상, 보통은 넘치면 반만, 장식은 먼저 버린다 */
    boolean allow(Vfx.Viewer v, int pri) {
        if (pkAt != vfx.tick) {
            pk.clear();
            pkAt = vfx.tick;
        }
        int[] c = pk.computeIfAbsent(v.id, k -> new int[1]);
        double cap = packetCap();
        double g = 180 * vfx.density() * particleBoost();
        boolean ok = switch (pri) {
            case Emit.TELE, Emit.YAML -> true;
            case Emit.NORMAL -> (c[0] < cap && v.pk < g)
                    || (c[0] < cap * 1.5 && v.pk < g * 1.25 && java.util.concurrent.ThreadLocalRandom.current().nextBoolean());
            default -> c[0] < cap * 0.7 && v.pk < g * 0.7;
        };
        if (ok) {
            c[0]++;
            v.pk++;
        }
        return ok;
    }

    boolean soundSlot() {
        if (sfxAt != vfx.tick) {
            sfxAt = vfx.tick;
            sfxN = 0;
        }
        return sfxN++ < 6;
    }

    /** 맞은 대상 위 별: 한 시전 5틱에 4개까지 */
    public boolean starSlot() {
        if (vfx.tick - starAt >= 5) {
            starAt = vfx.tick;
            starN = 0;
        }
        return starN++ < 4;
    }

    public void with(int audience, Runnable r) {
        int prev = aud;
        aud = audience;
        try {
            r.run();
        } finally {
            aud = prev;
        }
    }

    public void sound(Location at, String key, double vol, double pitch) {
        Sfx.play(this, at, key, vol, pitch);
    }

    public void castSounds(Location at) {
        Sfx.layers(this, at, pal.cast(), 1 + Math.min(1, tier.sfxLayers), 1.0);
    }

    public void impactSounds(Location at) {
        Sfx.layers(this, at, pal.impact(), Math.max(1, tier.sfxLayers), 1.0);
    }

    // ------------------------------------------------------------------ 안전 장치

    void safe(String where, Runnable r) {
        try {
            r.run();
        } catch (Throwable t) {
            vfx.warn(skill + ":" + where, "연출 오류(" + skill + " " + where + "): " + t);
        }
    }

    private Track route(Ev ev) {
        if (off) return Track.NOOP;
        Track base = Track.NOOP, extra = Track.NOOP;
        try {
            if (!sig.replaces(ev.getClass())) base = Defaults.render(this, ev);
        } catch (Throwable t) {
            vfx.warn(skill + ":" + ev.getClass().getSimpleName(), "기본 연출 오류(" + skill + " " + ev.getClass().getSimpleName() + "): " + t);
        }
        try {
            extra = sig.on(this, ev);
        } catch (Throwable t) {
            vfx.warn("sig:" + skill + ":" + ev.getClass().getSimpleName(), "전용 연출 오류(" + skill + " " + ev.getClass().getSimpleName() + "): " + t);
        }
        return guard(Track.both(base, extra));
    }

    private Track guard(Track t) {
        if (t == null || t == Track.NOOP) return Track.NOOP;
        return new Track() {
            @Override
            public void tick(Location pos, Vector vel) {
                safe("tick", () -> t.tick(pos, vel));
            }

            @Override
            public void point(int i, Location p) {
                safe("point", () -> t.point(i, p));
            }

            @Override
            public void end(Location at, boolean impact) {
                safe("end", () -> t.end(at, impact));
            }
        };
    }

    private void ev(Ev e) {
        if (!off) route(e);
    }

    private Track evT(Ev e) {
        return off ? Track.NOOP : route(e);
    }

    // ------------------------------------------------------------------ YAML 입자 (원래 기술 입자는 모두 여기로)

    public void yaml(Fx.Spec s, Location at, int count, double spread, double speed) {
        yaml(s, at, count, spread, spread, spread, speed);
    }

    public void yaml(Fx.Spec s, Location at, int count, double ox, double oy, double oz, double speed) {
        if (s == null || at == null) return;
        if (off) {
            s.spawn(at, count, ox, oy, oz, speed);
            return;
        }
        try {
            // 팩이 없는 사람은 조각이 안 보이니 원래 입자를 그대로, 팩을 받은 사람은 조각이 대신하므로 등급만큼 줄인다
            if (aud == AUD_ALL && anyNoPack()) {
                int n0 = count;
                with(AUD_NOPACK, () -> Emit.spec(this, s, at, n0, ox, oy, oz, speed, Emit.YAML));
                with(AUD_PACK, () -> yamlPack(s, at, n0, ox, oy, oz, speed));
            } else {
                yamlPack(s, at, count, ox, oy, oz, speed);
            }
        } catch (Throwable t) {
            vfx.warn("yaml", "입자 오류: " + t);
        }
    }

    private void yamlPack(Fx.Spec s, Location at, int count, double ox, double oy, double oz, double speed) {
        double keep = tier.yamlKeep;
        if (count <= 1) {
            yamlAcc += keep;
            if (yamlAcc < 1) return;
            yamlAcc -= 1;
        } else {
            count = Math.max(1, (int) Math.round(count * keep));
        }
        Emit.spec(this, rank() >= 3 ? smallDust(s) : s, at, count, ox, oy, oz, speed, Emit.YAML);
    }

    private boolean anyNoPack() {
        for (Vfx.Viewer v : vfx.viewers()) if (!v.pack) return true;
        return false;
    }

    /** 보스·프리즘 등급: 조각 위에 겹치는 큰 YAML 먼지(2.0 이상)는 얼룩처럼 보여 1.3 으로 줄인다 */
    private static Fx.Spec smallDust(Fx.Spec s) {
        Object d = s.data();
        if (d instanceof org.bukkit.Particle.DustOptions o && o.getSize() > 1.3f)
            return new Fx.Spec(s.particle(), new org.bukkit.Particle.DustOptions(o.getColor(), 1.3f));
        if (d instanceof org.bukkit.Particle.DustTransition t && t.getSize() > 1.3f)
            return new Fx.Spec(s.particle(), new org.bukkit.Particle.DustTransition(t.getColor(), t.getToColor(), 1.3f));
        return s;
    }

    public void yamlRing(Fx.Spec s, Location c, double r, int n) {
        if (s == null) return;
        if (off) {
            Fx.ring(s, c, r, n);
            return;
        }
        for (int i = 0; i < n; i++) {
            double a = Math.PI * 2 * i / n;
            yaml(s, c.clone().add(Math.cos(a) * r, 0, Math.sin(a) * r), 1, 0, 0);
        }
    }

    public void yamlLine(Fx.Spec s, Location a, Location b, double step) {
        if (s == null) return;
        if (off) {
            Fx.line(s, a, b, step);
            return;
        }
        Shapes.line(a, b, step, (p, t) -> yaml(s, p, 1, 0, 0));
    }

    public void yamlBolt(Location target, Fx.Spec s) {
        if (off) {
            Fx.bolt(target, s);
            return;
        }
        Fx.Spec sp = s != null ? s : new Fx.Spec(org.bukkit.Particle.ELECTRIC_SPARK, null);
        var r = java.util.concurrent.ThreadLocalRandom.current();
        Location prev = target.clone().add(r.nextDouble(-1, 1), 12, r.nextDouble(-1, 1));
        for (int i = 0; i < 6; i++) {
            Location next = (i == 5) ? target.clone()
                    : target.clone().add(r.nextDouble(-1.2, 1.2), 12 - (i + 1) * 2.0, r.nextDouble(-1.2, 1.2));
            yamlLine(sp, prev, next, 0.35);
            prev = next;
        }
    }

    // ------------------------------------------------------------------ 사건 (Mechanics 가 부른다)

    public void cone(Location base, Vector dir, double half, double range, Fx.Spec yaml) {
        ev(new Ev.Cone(base.clone(), dir.clone(), half, range, yaml));
    }

    public void nova(Location c, double radius, int expand, Fx.Spec yaml) {
        ev(new Ev.Nova(c.clone(), radius, expand, yaml));
    }

    public Track projectile(Location start, Vector vel, boolean hasDisplay, boolean ground, double hitRadius, int count,
                            Fx.Spec yaml, double explodeRadius) {
        return evT(new Ev.Projectile(start.clone(), vel.clone(), hasDisplay, ground, hitRadius, count, yaml, explodeRadius));
    }

    public void explode(Location at, double radius, Fx.Spec yaml) {
        ev(new Ev.Explode(at.clone(), radius, yaml));
    }

    public void beam(Location start, Vector dir, Location end, double width, boolean throughWalls, Fx.Spec yaml, Fx.Spec core) {
        ev(new Ev.Beam(start.clone(), dir.clone(), end.clone(), width, throughWalls, yaml, core));
    }

    public Track dash(Location start, Vector dir, double distance, int ticks, Fx.Spec yaml) {
        return evT(new Ev.Dash(start.clone(), dir.clone(), distance, ticks, yaml));
    }

    public Track leap(Location start, Vector vel, Fx.Spec yaml) {
        return evT(new Ev.Leap(start.clone(), vel.clone(), yaml));
    }

    public void blink(Location from, Location to, Fx.Spec yaml) {
        ev(new Ev.Blink(from.clone(), to.clone(), yaml));
    }

    public void rain(Location center, double radius, int count, int interval, double impactRadius, double height, double speed) {
        ev(new Ev.Rain(center.clone(), radius, count, interval, impactRadius, height, speed));
    }

    public Track drop(Location start, Location ground, Vector vel, double impactRadius, boolean hasDisplay, Fx.Spec yaml,
                      Fx.Spec impactYaml, int count) {
        return evT(new Ev.Drop(start.clone(), ground.clone(), vel.clone(), impactRadius, hasDisplay, yaml, impactYaml, count));
    }

    public void strike(Location pt, String visual, double impactRadius, Fx.Spec yaml) {
        if (off) return;
        safe("strike", () -> {
            LivingEntity on = null;
            double best = 0.7;
            for (LivingEntity e : kr.augsky.skill.Targets.enemiesNear(caster, pt, 0.7)) {
                double d = e.getLocation().distance(pt);
                if (d < best) {
                    best = d;
                    on = e;
                }
            }
            route(new Ev.Strike(pt.clone(), visual, impactRadius, yaml, on));
        });
    }

    public void chain(Location from, Location to, int n, Fx.Spec yaml) {
        ev(new Ev.Chain(from.clone(), to.clone(), n, yaml));
    }

    public Track zone(Location c, double radius, int duration, boolean follow, Fx.Spec yaml, Fx.Spec ring, boolean heals, boolean harms) {
        return evT(new Ev.Zone(c.clone(), radius, duration, follow, yaml, ring, heals, harms));
    }

    public Track orbit(int count, double radius, double y, int duration, boolean hasDisplay, Fx.Spec yaml) {
        return evT(new Ev.Orbit(count, radius, y, duration, hasDisplay, yaml));
    }

    public Track vortex(Location c, double radius, int duration, Fx.Spec yaml, List<?> end, SkillContext ctx) {
        if (off) return Track.NOOP;
        List<Footprint> ends = new ArrayList<>();
        try {
            SkillContext at = ctx.at(c);
            for (Object m : end) if (m instanceof Telegraphable t) {
                Footprint f = t.footprint(at);
                if (f != null) ends.add(f);
            }
        } catch (Throwable t) {
            vfx.warn("vortex-ends", "소용돌이 끝자리 계산 오류: " + t);
        }
        return evT(new Ev.Vortex(c.clone(), radius, duration, yaml, ends));
    }

    public void buff(LivingEntity who, Fx.Spec yaml) {
        ev(new Ev.Buff(who, yaml));
    }

    public void mark(LivingEntity target, Fx.Spec yaml) {
        ev(new Ev.Mark(target, yaml));
    }

    public void party(Location c, double radius) {
        ev(new Ev.Party(c.clone(), radius));
    }

    public void ally(LivingEntity who, Fx.Spec yaml) {
        ev(new Ev.Ally(who, yaml));
    }

    public void summon(Location at) {
        ev(new Ev.Summon(at.clone()));
    }

    /** HitEffects.apply 가 부른다. 같은 대상은 5틱에 한 번만 */
    public void hit(LivingEntity target, Location origin) {
        if (off || target == null) return;
        safe("hit", () -> {
            Long last = hitAt.get(target.getUniqueId());
            if (last != null && vfx.tick - last < 5) return;
            hitAt.put(target.getUniqueId(), vfx.tick);
            route(new Ev.Hit(target, origin == null ? caster.getLocation() : origin.clone(), ticking));
        });
    }

    /** delay 부품: ticks 뒤에 body 가 나간다. 맞을 자리를 2틱마다 다시 계산해 예고/기 모으기를 그린다 */
    public void windup(int ticks, List<?> body, SkillContext ctx) {
        if (off || ticks < 6) return;
        safe("windup", () -> {
            Supplier<List<Footprint>> fp = () -> {
                List<Footprint> out = new ArrayList<>();
                for (Object m : body) {
                    if (m instanceof Telegraphable t) {
                        try {
                            Footprint f = t.footprint(ctx);
                            if (f != null) out.add(f);
                        } catch (Throwable ignored) {
                            // 계산 못 하면 그 부품만 빼고 그린다
                        }
                    }
                }
                return out;
            };
            route(new Ev.Windup(ticks, fp));
        });
    }
}
