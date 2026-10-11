package kr.augsky.vfx;

import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.entity.LivingEntity;
import org.bukkit.util.Vector;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;

/** 폭발·장판·궤도·소용돌이·낙뢰·낙하 */
final class AreaFx {
    private AreaFx() {}

    static Location groundAt(Location c0) {
        Location g = Kit.groundOrNull(c0);
        if (g == null || Math.abs(g.getY() - c0.getY()) > 2.5) g = c0.clone().add(0, -0.2, 0);
        return g;
    }

    // ------------------------------------------------------------------ 원형 폭발

    static void nova(CastFx fx, Ev.Nova ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        Location c0 = ev.center();
        double r = ev.radius();
        int ex = ev.expand();
        boolean mob = fx.mob();
        Location g = groundAt(c0);
        boolean fits = Kit.decalFits(g, r);
        int grow = Math.max(3, ex);
        // 모든 등급: 파동이 판정 끝에 닿는 순간의 선명한 테두리
        fx.vfx.after(ex, () -> Kit.dustRing(fx, c0, r, k.a(), 1.4, Emit.NORMAL));
        if (fx.rank() == 0) {
            Emit.send(fx, c0.clone().add(0, 0.3, 0), Particle.POOF, null, 6, r * 0.25, 0.1, r * 0.25, 0.02, Emit.NORMAL);
            return;
        }
        if (ex > 0) {
            fx.vfx.every(0, 1, ex, i -> Kit.rimSpray(fx, c0, r * (i + 1) / ex, fx.n(6 + r), fx.pal.spark(), 0.2, 0.12, Emit.DETAIL));
        } else {
            Kit.rimSpray(fx, c0, r, fx.n(8 + r), fx.pal.spark(), 0.25, 0.15, Emit.NORMAL);
        }
        if (fits && fx.tier != Tier.MOB) {
            Sprite ring = Kit.ring(fx, g.clone().add(0, 0.03, 0), r * 0.15, r, grow, grow + 5, k, null);
            // 몬스터 기술은 판정 끝 그대로 (더 퍼지는 연출이 범위를 속이지 않게)
            if (mob) ring.end(Sprite.End.NONE);
            ring.go();
            Kit.hallmark(fx, ring);
        }
        if (fx.rank() < 2) return;
        if (fits) {
            Sprite sh = Kit.shock(fx, g.clone().add(0, 0.02, 0), r * 0.1, r * 0.9, grow + 1, grow + 6, k);
            if (mob) sh.end(Sprite.End.NONE);
            sh.go();
        }
        fx.vfx.after(ex, () -> {
            Kit.dustRing(fx, c0.clone().add(0, 0.3, 0), r, k.a(), 1.1, Emit.DETAIL);
            Kit.dustRing(fx, c0.clone().add(0, 0.9, 0), r * 0.97, k.b(), 0.9, Emit.DETAIL);
        });
        elementRim(fx, g, r, ex);
        fx.impactSounds(c0);
        if (fx.rank() < 3) return;
        if (fits && fx.tier != Tier.MOB) {
            String dm = fx.vfx.models.pick("ring_dim", "ring");
            fx.vfx.after(2, () -> {
                Sprite r2 = Kit.ring(fx, g.clone().add(0, 0.035, 0), r * 0.2, r * (mob ? 1.0 : 1.04), grow, grow + 4, k.swap(), dm);
                if (mob) r2.end(Sprite.End.NONE);
                r2.go();
            });
            ringWall(fx, g, r, grow, k);
        }
        if (!mob || fx.ult()) {
            Kit.pillar(fx, g, 0.8, 3.0, 6, k).go();
        }
        Kit.debris(fx, g.clone().add(0, 0.1, 0), 3 + (int) r, 1.0, fx.pal.debris().length > 0 ? fx.pal.debris()[0] : null);
        if (!mob) Kit.afterglow(fx, g, Math.min(4, r * 0.6), 30, k);
        if (r >= 5) Emit.flash(fx, c0.clone().add(0, 2, 0));
        if (fx.rank() < 4) return;
        for (int i = 0; i < 3; i++) {
            int d = 2 + i * 2;
            CastFx.Cols ki = k.rainbow() ? new CastFx.Cols(Palette.hue(i / 3.0 + fx.vfx.tick * 0.01), Color.WHITE, k.dark(), k.rim(), false)
                    : (i % 2 == 0 ? k.swap() : k);
            fx.vfx.after(d, () -> {
                Sprite rr = Kit.ring(fx, g.clone().add(0, 0.036 + 0.002 * d, 0), r * 0.25, r * (1.0 + 0.05 * d), grow, grow + 3, ki, null);
                rr.go();
            });
        }
        if (fx.ult()) {
            Kit.star(fx, c0.clone().add(0, 2.5, 0), Math.min(4, r * 0.45), 5, k).go();
        }
        Shapes.helix(g, Math.min(2.5, r * 0.4), 4, 3, 1.2, 10, fx.vfx.tick * 0.2, (p, t) -> fx.vfx.after((int) (t * 10),
                () -> Emit.dust(fx, p, k.rainbow() ? Palette.hue(t) : k.b(), 0.9, Emit.DETAIL)));
    }

    /** 고리 벽 (팩에 ring_wall 이 있으면): 바닥 테두리에서 솟는 세로 띠. 옆에서 볼 때 고리가 납작해 보이지 않게 */
    static void ringWall(CastFx fx, Location g, double r, int grow, CastFx.Cols k) {
        if (!fx.vfx.models.has("ring_wall")) return;
        double s = r / Geo.FLAT_HALF;
        Sprite w = Sprite.item(fx, "ring_wall", g.clone().add(0, 0.02, 0)).size(s * 0.2, 0.2, s * 0.2).radius(r).life(grow + 6).tint(k);
        w.decal = true;
        w.scaleTo(1, grow, s, 1.2, s);
        w.go();
    }

    /** 속성 강조: 서리 가시, 화염 기둥, 공허 검은 고리... (균열 등급부터) */
    static void elementRim(CastFx fx, Location g, double r, int delay) {
        String id = fx.pal.id();
        fx.vfx.after(delay, () -> {
            switch (id) {
                case "frost" -> Kit.iceSpikes(fx, g, r * 0.92, fx.rank() >= 3 ? 8 : 5, 14);
                case "flame", "sun" -> {
                    List<Location> pts = Shapes.around(g, r * 0.95, 8, 0);
                    fx.vfx.every(0, 2, 3, i -> {
                        for (Location p : pts) Emit.dir(fx, p.clone().add(0, 0.2, 0), Particle.FLAME, null, new Vector(0, 1, 0), 0.25, Emit.NORMAL);
                    });
                }
                case "abyss", "doom", "shadow" -> {
                    Kit.dustRing(fx, g.clone().add(0, 0.15, 0), r * 0.98, Color.fromRGB(0x14001e), 1.8, Emit.NORMAL);
                    Kit.rimSpray(fx, g, r, fx.n(8), fx.pal.spark(), 0.15, 0.4, Emit.DETAIL);
                }
                case "storm" -> {
                    List<Location> pts = Shapes.around(g.clone().add(0, 0.4, 0), r * 0.95, 6, 0);
                    for (int i = 0; i < pts.size(); i++) {
                        List<Location> b = Shapes.bolt(pts.get(i), pts.get((i + 1) % pts.size()), 4, 0.35, Kit.rnd());
                        for (int j = 0; j + 1 < b.size(); j++) Emit.line(fx, b.get(j), b.get(j + 1), 0.3, fx.b(), 0.8, Emit.DETAIL);
                    }
                }
                case "ocean" -> {
                    for (Location p : Shapes.around(g, r * 0.95, 8, 0))
                        Emit.send(fx, p.clone().add(0, 0.4, 0), Particle.SPLASH, null, 10, 0.2, 0.4, 0.2, 0.1, Emit.NORMAL);
                }
                case "nature" -> {
                    if (fx.rank() >= 3) Kit.flowers(fx, g, r * 0.9, 6, 30);
                    Kit.rimSpray(fx, g, r, fx.n(8), Fx2.LEAVES, 0.15, 0.3, Emit.DETAIL);
                }
                case "holy", "gold", "genesis" -> {
                    for (Location p : Shapes.around(g, r * 0.95, 8, 0))
                        Emit.send(fx, p.clone().add(0, 0.3, 0), Particle.END_ROD, null, 2, 0.05, 0.6, 0.05, 0.02, Emit.NORMAL);
                }
                default -> {
                    for (Location p : Shapes.around(g, r * 0.95, 6, 0)) Kit.accent(fx, p.clone().add(0, 0.3, 0), 0.6);
                }
            }
        });
    }

    // ------------------------------------------------------------------ 장판

    static Track zone(CastFx fx, Ev.Zone ev) {
        CastFx.Cols k = fx.cols(ev.ring() != null ? ev.ring() : ev.yaml());
        double r = ev.radius();
        int dur = ev.duration();
        boolean follow = ev.follow();
        LivingEntity cst = fx.caster;
        Supplier<Location> feet = () -> cst.isValid() ? Kit.ground(cst.getLocation()).add(0, 0.03, 0) : null;
        Location fixed = Kit.ground(ev.center()).add(0, 0.03, 0);
        Location base = follow ? feet.get() : fixed;
        if (base == null) return Track.NOOP;
        boolean fits = Kit.decalFits(base, r);
        List<Sprite> parts = new ArrayList<>();
        int life = dur + 6;
        boolean selfCentered = follow && fx.cp != null;
        if (fx.rank() >= 1 && fits) {
            Sprite ring = Kit.ring(fx, base, r * 0.3, r, 5, life, k, fx.vfx.models.pick("ring_dim", "ring")).end(Sprite.End.FADE, 6);
            if (follow) ring.follow(feet, 2);
            ring.go();
            parts.add(ring);
        }
        if (fx.rank() >= 3 && fits) {
            List<Sprite> cs = selfCentered ? Kit.selfCircle(fx, base.clone().add(0, -0.01, 0), r * 0.92, life, k, 30, true)
                    : List.of(Kit.circle(fx, base.clone().add(0, -0.01, 0), r * 0.92, life, k, 30, true, Sprite.View.AUTO));
            for (Sprite s : cs) {
                if (s == null) continue;
                if (follow) s.follow(() -> {
                    Location f = feet.get();
                    return f == null ? null : f.add(0, -0.01, 0);
                }, 2);
                parts.add(s);
            }
        } else if (fx.rank() == 2 && fits) {
            String m = fx.vfx.models.pick("swirl", "shock_dim", "ring_dim");
            if (m != null) {
                Sprite sw = Kit.flat(fx, m, base.clone().add(0, -0.01, 0), r * 0.9, Shapes.Frame.FLAT, k).life(life).end(Sprite.End.FADE, 6);
                Kit.spinOver(sw, 1, life, selfCentered ? 15 : 45);
                if (follow) sw.follow(() -> {
                    Location f = feet.get();
                    return f == null ? null : f.add(0, -0.01, 0);
                }, 2);
                sw.go();
                parts.add(sw);
            }
        }
        if (fx.rank() >= 3) {
            switch (fx.pal.id()) {
                case "nature", "genesis" -> Kit.flowers(fx, base, r * 0.85, fx.n(6), Math.min(life, 200));
                case "holy" -> {
                    if (!follow) for (Location p : Shapes.around(base, r * 0.9, 4, Math.PI / 4))
                        Kit.pillar(fx, p, 0.4, 2.2, Math.min(life, 160), k).go();
                }
                default -> { }
            }
        }
        return new Track() {
            int t;

            @Override
            public void tick(Location cc, Vector v) {
                t++;
                Location c = follow ? feet.get() : fixed;
                if (c == null) return;
                if (t % 4 == 0) {
                    for (int i = 0; i < fx.n(2); i++) {
                        double a = Kit.rnd().nextDouble(Math.PI * 2), d = Math.sqrt(Kit.rnd().nextDouble()) * r;
                        Emit.spec(fx, fx.pal.mote(), c.clone().add(Math.cos(a) * d, 0.2, Math.sin(a) * d), 1, 0.05, 0.02, Emit.DETAIL);
                    }
                    if (fx.rank() >= 2) {
                        for (int i = 0; i < 4; i++) {
                            double a = Kit.rnd().nextDouble(Math.PI * 2);
                            Emit.dust(fx, c.clone().add(Math.cos(a) * r, 0.12, Math.sin(a) * r), k.b(), 0.9, Emit.DETAIL);
                        }
                    }
                }
                if (fx.rank() >= 3 && fx.pal.id().equals("frost") && t % 3 == 0) {
                    double ph = t * 0.25;
                    for (int s = 0; s < 2; s++) {
                        for (int i = 0; i < 3; i++) {
                            double a = ph + Math.PI * s + i * 0.5;
                            double h = 0.4 + i * 0.6;
                            Emit.send(fx, c.clone().add(Math.cos(a) * r * 0.8, h, Math.sin(a) * r * 0.8), Particle.SNOWFLAKE, null, 1, 0.05, 0.05, 0.05, 0.02, Emit.NORMAL);
                        }
                    }
                }
            }

            @Override
            public void end(Location at, boolean impact) {
                for (Sprite s : parts) s.finish(6);
            }
        };
    }

    // ------------------------------------------------------------------ 궤도 칼날

    static Track orbit(CastFx fx, Ev.Orbit ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        int n = ev.count();
        Location[] prev = new Location[n];
        Location[] cur = new Location[n];
        List<Sprite> parts = new ArrayList<>();
        LivingEntity cst = fx.caster;
        if (fx.rank() >= 2) {
            Supplier<Location> mid = () -> cst.isValid() ? cst.getLocation().add(0, ev.y(), 0) : null;
            Location m0 = mid.get();
            if (m0 != null) {
                Sprite ring = Kit.ring(fx, m0, ev.radius(), ev.radius(), 1, ev.duration() + 4, k, fx.vfx.models.pick("ring_dim", "ring"))
                        .view(Sprite.View.HIDE).follow(mid, 1);
                ring.go();
                parts.add(ring);
            }
        }
        if (fx.rank() >= 3) {
            for (int i = 0; i < Math.min(n, 6); i++) {
                int idx = i;
                Location p0 = cst.getLocation().add(0, ev.y(), 0);
                Sprite o = Kit.orb(fx, p0, ev.hasDisplay() ? 0.9 : 0.7, ev.duration() + 2, k, null).follow(() -> cur[idx], 1);
                o.go();
                parts.add(o);
            }
        }
        return new Track() {
            @Override
            public void point(int i, Location p) {
                if (i >= n) return;
                cur[i] = p.clone();
                if (fx.rank() >= 1 && prev[i] != null) Emit.streak(fx, prev[i], p, i % 2 == 0 ? k.a() : k.b(), 2, 3, Emit.NORMAL);
                if (fx.rank() >= 2) Emit.spec(fx, fx.pal.spark(), p, 1, 0.05, 0.01, Emit.DETAIL);
                prev[i] = p.clone();
            }

            @Override
            public void end(Location at, boolean impact) {
                for (Sprite s : parts) s.finish(3);
            }
        };
    }

    // ------------------------------------------------------------------ 소용돌이

    static Track vortex(CastFx fx, Ev.Vortex ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        Location c = ev.center();
        double r = ev.radius();
        int dur = ev.duration();
        Location g = groundAt(c);
        boolean fits = Kit.decalFits(g, r);
        List<Sprite> parts = new ArrayList<>();
        Sprite[] core = new Sprite[1];
        if (fx.mob()) Telegraph.vortexEnds(fx, ev);
        if (fx.rank() >= 2 && fits && fx.tier != Tier.MOB) {
            String m = fx.vfx.models.pick("swirl", "shock_dim", "ring_dim");
            if (m != null) {
                Sprite sw = Kit.flat(fx, m, g.clone().add(0, 0.03, 0), 0.5, Shapes.Frame.FLAT, k).life(dur + 4).end(Sprite.End.FADE, 4);
                sw.scaleTo(1, 4, r / Geo.FLAT_HALF, 1, r / Geo.FLAT_HALF).radius(r);
                Kit.spinOver(sw, 1, dur + 3, 360);
                sw.go();
                parts.add(sw);
            }
            Sprite edge = Kit.ring(fx, g.clone().add(0, 0.04, 0), r, r, 1, dur + 4, k, fx.vfx.models.pick("ring_dim", "ring"));
            edge.go();
            parts.add(edge);
        }
        // 끝에 터질 자리를 미리 그린다 (플레이어 기술: 기를 모으는 마법진)
        if (!fx.mob() && fx.rank() >= 3) {
            for (Footprint f : ev.ends()) {
                if (f.shape() != Footprint.Shape.CIRCLE || f.r() < 1.5) continue;
                Location fc = Kit.ground(f.c()).add(0, 0.02, 0);
                if (!Kit.decalFits(fc, f.r())) continue;
                Sprite[] cs = Kit.circle(fx, fc, f.r(), dur + 6, k, -40, fx.rank() >= 4, Sprite.View.AUTO);
                for (Sprite s : cs) if (s != null) parts.add(s);
                break;
            }
        }
        if (fx.rank() >= 3) {
            String cm = (fx.pal.id().equals("abyss") || fx.pal.id().equals("doom")) ? fx.vfx.models.pick("void_orb", "orb") : "orb";
            Sprite o = Kit.orb(fx, c.clone().add(0, 0.6, 0), 0.3, dur + 4, k, cm);
            o.scaleTo(1, Math.max(2, dur), 1.6);
            o.go();
            core[0] = o;
        }
        if (fx.rank() >= 4 && fx.ult()) {
            Sprite[] sky = Kit.circle(fx, c.clone().add(0, 4.2, 0), r * 0.7, dur + 6, k, 50, false, Sprite.View.AUTO);
            for (Sprite s : sky) if (s != null) parts.add(s);
        }
        if (fx.rank() >= 3) {
            for (int i = 0; i < 6 && fx.moving < 16; i++) {
                double a = Math.PI * 2 * i / 6;
                Location p = g.clone().add(Math.cos(a) * r * 0.9, 0.2, Math.sin(a) * r * 0.9);
                Material mt = Kit.groundMaterial(p, Material.STONE);
                Sprite d = Sprite.block(fx, mt.createBlockData(), p).size(0.3).worldLight().life(Math.min(dur, 40)).end(Sprite.End.SHRINK, 4).radius(0.3);
                Vector in = c.toVector().subtract(p.toVector()).multiply(1.0 / Math.max(10, Math.min(dur, 40)));
                d.fly(in.setY(0.08), 0.0, 2, 35f, new Vector3f(0, 1, 0));
                d.go();
            }
        }
        return new Track() {
            int t;

            @Override
            public void tick(Location pos, Vector v) {
                t++;
                if (fx.rank() < 1) return;
                double ph = t * 0.35;
                for (int arm = 0; arm < 3; arm++) {
                    double a0 = ph + arm * Math.PI * 2 / 3;
                    for (int i = 0; i < 3; i++) {
                        double f = 1 - ((t * 0.05 + i / 3.0) % 1);
                        double a = a0 + (1 - f) * 2.2;
                        Emit.dust(fx, c.clone().add(Math.cos(a) * r * f, -0.6 + 0.15 * i, Math.sin(a) * r * f), arm == 0 ? k.b() : k.a(), 1.0, Emit.DETAIL);
                    }
                }
                if (t % 2 == 0) Kit.converge(fx, c, r, Math.max(2, fx.n(3)), k.b(), 10, Emit.DETAIL);
                if (fx.rank() >= 3) {
                    double hh = (t % 10) / 10.0;
                    for (int s = 0; s < 2; s++) {
                        double a = ph * 2 + Math.PI * s;
                        double rr = 0.4 + hh * 1.6;
                        Emit.dust(fx, c.clone().add(Math.cos(a) * rr, -0.6 + hh * 3, Math.sin(a) * rr), k.a(), 0.8, Emit.DETAIL);
                    }
                    if (t % 10 == 0) fx.sound(c, "block.respawn_anchor.charge", 0.4, 0.7 + 0.6 * t / (double) Math.max(1, dur));
                }
            }

            @Override
            public void end(Location at, boolean impact) {
                if (core[0] != null && core[0].ok()) {
                    Sprite s = core[0];
                    s.key(s.age + 1, 2, sp -> sp.sc.set(0.02f));
                    s.life = s.age + 3;
                }
                for (Sprite s : parts) s.finish(3);
            }
        };
    }

    // ------------------------------------------------------------------ 낙뢰·빛기둥

    static void strike(CastFx fx, Ev.Strike ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        Location pt = ev.point().clone();
        double ir = ev.impactRadius();
        LivingEntity on = ev.on();
        double w = on != null ? on.getWidth() + 0.6 : Math.max(1.0, ir * 0.8);
        Location g = groundAt(pt.clone().add(0, 0.5, 0));
        int seq = fx.seq("strike");
        switch (ev.visual()) {
            case "lightning" -> {
                if (fx.rank() < 1) return;
                // 진짜 번개가 이미 내려온다: 납작한 번개 조각은 덧붙이지 않고 땅의 충격에 예산을 쓴다
                // 그을음: 섬 등급만 (균열 등급부터는 바닥 잔광 판이 대신한다). 큰 검은 먼지는 흙덩이처럼 보여 작게
                if (fx.rank() < 2) Kit.dustRing(fx, g.clone().add(0, 0.08, 0), Math.max(1, ir * 0.8), Color.fromRGB(0x34343c), 0.9, Emit.NORMAL);
                Emit.send(fx, g.clone().add(0, 0.4, 0), Particle.ELECTRIC_SPARK, null, fx.n(14), ir * 0.3, 0.3, ir * 0.3, 0.3, Emit.NORMAL);
                if (fx.rank() >= 3) {
                    // 번개가 지나간 자리의 잔광(약 1초): 가늘어지며 사라지는 전기 기둥 + 바닥을 기는 전기 줄기.
                    // 진짜 번개는 금방 꺼지므로 이것이 없으면 0.5초 뒤 화면이 비었다. 여러 줄기 기술에서도 먼저 자리를 잡는다
                    CastFx.Cols ion = new CastFx.Cols(k.b(), Color.WHITE, k.dark(), k.rim(), false);
                    Sprite glow = Kit.pillar(fx, g, 0.9, 7.5, 20, ion).end(Sprite.End.THIN, 12);
                    glow.go();
                    Location g0 = g.clone();
                    fx.vfx.every(2, 3, 6, i -> {
                        double a = Kit.rnd().nextDouble(Math.PI * 2);
                        double len = Math.max(1.2, ir) * Kit.rnd().nextDouble(0.6, 1.1);
                        Location tip = Kit.ground(g0.clone().add(Math.cos(a) * len, 0.6, Math.sin(a) * len)).add(0, 0.12, 0);
                        List<Location> b = Shapes.bolt(g0.clone().add(0, 0.15, 0), tip, 4, 0.25, Kit.rnd());
                        for (int j = 0; j + 1 < b.size(); j++) Emit.line(fx, b.get(j), b.get(j + 1), 0.25, j % 2 == 0 ? k.b() : Color.WHITE, 0.7, Emit.DETAIL);
                        Emit.send(fx, g0.clone().add(0, 0.3 + i * 0.5, 0), Particle.ELECTRIC_SPARK, null, 3, 0.25, 0.4, 0.25, 0.05, Emit.DETAIL);
                    });
                }
                if (fx.rank() >= 2) {
                    Kit.ring(fx, g.clone().add(0, 0.03, 0), 0.3, Math.max(1.2, ir), 3, 7, k, null).go();
                }
                if (fx.rank() >= 3) {
                    Kit.shock(fx, g.clone().add(0, 0.02, 0), 0.4, Math.max(1.5, ir * 1.1), 4, 9, k).go();
                    Kit.star(fx, g.clone().add(0, 1.2, 0), fx.ult() ? 2.2 : 1.4, 4, k).go();
                }
                if (fx.rank() >= 2) Kit.afterglow(fx, g, Math.max(1, ir * 0.7), fx.rank() >= 3 ? 40 : 24, k);
                if (fx.rank() >= 3) Kit.debris(fx, g, 4, 0.9, fx.pal.debris().length > 0 ? fx.pal.debris()[0] : null);
                if (fx.rank() >= 4) {
                    for (int b = 0; b < 2; b++) {
                        Location top = g.clone().add(Kit.rnd().nextDouble(-3, 3), 6 + Kit.rnd().nextDouble(3), Kit.rnd().nextDouble(-3, 3));
                        List<Location> pts = Shapes.bolt(top, g.clone().add(Kit.rnd().nextDouble(-1.5, 1.5), 0.2, Kit.rnd().nextDouble(-1.5, 1.5)), 6, 0.7, Kit.rnd());
                        for (int j = 0; j + 1 < pts.size(); j++) Emit.line(fx, pts.get(j), pts.get(j + 1), 0.35, k.b(), 0.9, Emit.DETAIL);
                    }
                }
            }
            case "pillar" -> {
                if (fx.rank() < 1) return;
                Kit.ring(fx, g.clone().add(0, 0.03, 0), 0.3, Math.max(1.0, ir), 3, 8, k, null).go();
                if (fx.rank() < 2) {
                    // 섬 등급: 가는 빛기둥 하나 (균열 등급부터는 굵은 기둥 + 별)
                    if (fx.rank() == 1 && fx.tier != Tier.MOB) Kit.pillar(fx, g, w * 0.45, 4, 8, k).go();
                    return;
                }
                if (fx.pal.id().equals("frost")) {
                    Kit.iceSpikes(fx, g, Math.max(0.6, ir * 0.5), 3, 16);
                } else {
                    Sprite p = Kit.pillar(fx, g, w, 6, 10, k);
                    p.go();
                    Kit.hallmark(fx, p);
                    Kit.star(fx, g.clone().add(0, 6, 0), fx.rank() >= 3 ? 1.4 : 0.8, 5, k).go();
                }
                if (fx.rank() >= 3) {
                    Kit.shock(fx, g.clone().add(0, 0.02, 0), 0.3, Math.max(1.2, ir * 1.1), 3, 9, k).go();
                    if (fx.pal.id().equals("holy")) {
                        Sprite halo = Kit.ring(fx, g.clone().add(0, 5.2, 0), 0.8, 1.2, 3, 12, k, null);
                        halo.go();
                    }
                }
                if (fx.rank() >= 4) {
                    Shapes.helix(g, w * 0.7, 5, 2, 1.5, 8, seq, (p2, t) -> fx.vfx.after((int) (t * 8),
                            () -> Emit.dust(fx, p2, k.b(), 0.8, Emit.DETAIL)));
                }
            }
            default -> {
                if (fx.rank() >= 1) Kit.accent(fx, pt.clone().add(0, 0.5, 0), 1.0);
            }
        }
    }

    // ------------------------------------------------------------------ 낙하 공격

    static void rain(CastFx fx, Ev.Rain ev) {
        if (fx.mob() || fx.rank() < 3) return;
        // 비는 떨어지기까지 시간이 있다: 그동안 마법진으로 기를 모은다
        CastFx.Cols k = fx.cols();
        Location c = Kit.ground(ev.center()).add(0, 0.02, 0);
        double rr = ev.radius() + ev.impactRadius();
        if (ev.count() <= 1 || !Kit.decalFits(c, rr)) return;
        int fall = (int) Math.ceil(ev.height() / Math.max(0.3, ev.speed()));
        int life = (ev.count() - 1) * ev.interval() + fall + 6;
        Kit.circle(fx, c, rr, life, k, 25, fx.rank() >= 4, Sprite.View.AUTO);
    }

    static Track drop(CastFx fx, Ev.Drop ev) {
        if (ev.count() == 1 && fx.rank() >= 3 && !fx.mob()) return Pieces.meteor(fx, ev);
        CastFx.Cols k = fx.cols(ev.yaml());
        Location ground = ev.ground().clone();
        double ir = ev.impactRadius();
        int fall = (int) Math.ceil(Math.abs(ev.start().getY() - ground.getY()) / Math.max(0.2, Math.abs(ev.vel().getY())));
        if (fx.mob()) Telegraph.dropMarker(fx, ground, ir, fall);
        else if (fx.rank() >= 1) {
            fx.vfx.every(0, 4, Math.max(1, fall / 4), i -> Kit.dustRing(fx, ground.clone().add(0, 0.1, 0), ir * (0.6 + 0.1 * (i % 2)), k.a(), 0.9, Emit.DETAIL));
        }
        Sprite[] head = new Sprite[1];
        if (fx.rank() >= 2 && !ev.hasDisplay()) {
            head[0] = Kit.orb(fx, ev.start(), fx.rank() >= 3 ? 0.8 : 0.6, fall + 4, k, null);
            head[0].go();
        }
        return new Track() {
            Location prev = ev.start().clone();

            @Override
            public void tick(Location pos, Vector vel) {
                if (fx.rank() >= 1) Emit.streak(fx, prev, pos, k.rainbow() ? Palette.hue(fx.vfx.tick * 0.05) : k.a(), 2, 3, Emit.NORMAL);
                if (head[0] != null && head[0].ok()) head[0].e.teleport(flat(pos));
                if (fx.rank() >= 2 && (fx.pal.id().equals("flame") || fx.pal.id().equals("sun")))
                    Emit.send(fx, pos, Particle.FLAME, null, 2, 0.15, 0.15, 0.15, 0.01, Emit.DETAIL);
                prev = pos.clone();
            }

            @Override
            public void end(Location at, boolean impact) {
                if (head[0] != null) head[0].finish(2);
                Location g = at.clone().add(0, 0.05, 0);
                if (fx.rank() == 0) {
                    Kit.dustRing(fx, g, ir, k.a(), 1.2, Emit.NORMAL);
                    return;
                }
                if (fx.tier != Tier.MOB) {
                    Sprite r = Kit.ring(fx, g.clone().add(0, 0.01, 0), 0.3, ir, 3, 7, k, null);
                    if (fx.mob()) r.end(Sprite.End.NONE);
                    r.go();
                }
                Emit.send(fx, g.clone().add(0, 0.3, 0), Particle.POOF, null, 4, ir * 0.3, 0.1, ir * 0.3, 0.02, Emit.DETAIL);
                if (fx.rank() >= 2) Kit.accent(fx, g.clone().add(0, 0.3, 0), Math.min(1.5, ir * 0.6));
                if (fx.rank() >= 3) {
                    Kit.debris(fx, g, 2, 0.8, ev.hasDisplay() ? null : (fx.pal.debris().length > 0 ? fx.pal.debris()[0] : null));
                    Kit.star(fx, g.clone().add(0, 0.8, 0), 1.0, 4, k).go();
                }
            }
        };
    }

    static Location flat(Location l) {
        Location c = l.clone();
        c.setYaw(0);
        c.setPitch(0);
        return c;
    }
}
