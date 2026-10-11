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
import java.util.Map;
import java.util.function.Supplier;

/** 보스 무기 22개 기술의 전용 연출 (기본 연출 위에 덧붙이거나 바꾼다) */
final class BossSigs {
    private BossSigs() {}

    static CastFx.Cols rgb(CastFx fx, int a, int b) {
        return PrismSigs.rgb(fx, a, b);
    }

    static void register(Map<String, Signature> m) {
        // ── 서리 군주의 대검 ──
        m.put("eternal_winter", Sig.of()
                .cast(fx -> {
                    LivingEntity c = fx.caster;
                    // 몸 둘레를 도는 얼음 결정 여섯: 네모난 덩이는 싸구려 상자처럼 보여 가늘고 긴 결정 + 빛 반짝임으로
                    for (int i = 0; i < 6; i++) {
                        int idx = i;
                        Location p0 = c.getLocation().add(5, 1.2, 0);
                        Supplier<Location> path = () -> {
                            if (!c.isValid()) return null;
                            double a = idx * Math.PI / 3 + fx.age() * 0.09;
                            return c.getLocation().add(Math.cos(a) * 5, 1.2 + 0.4 * Math.sin(fx.age() * 0.15 + idx), Math.sin(a) * 5);
                        };
                        Sprite s = Sprite.block(fx, (i % 2 == 0 ? Material.PACKED_ICE : Material.BLUE_ICE).createBlockData(), p0).size(0.05)
                                .radius(0.4).life(124).end(Sprite.End.SHRINK, 4);
                        s.rot.rotateZ((float) Math.toRadians(i % 2 == 0 ? 22 : -22));
                        s.scaleTo(1, 4, 0.2, 0.75, 0.2);
                        s.follow(path, 2);
                        s.spinAxis(5, 118, 720, new Vector3f(0, 1, 0));
                        s.go();
                        Sprite gl = Sprite.item(fx, fx.vfx.models.pick("spark", "orb"), p0).size(0.9).radius(0.5).life(124)
                                .tint(fx.cols()).end(Sprite.End.SHRINK, 4).follow(path, 2);
                        gl.go();
                    }
                    fx.vfx.every(0, 6, 20, i -> {
                        if (!c.isValid()) return;
                        Emit.send(fx, c.getLocation().add(0, 0.2, 0), Particle.WHITE_SMOKE, null, 6, 3.5, 0.05, 3.5, 0.0, Emit.DETAIL);
                    });
                    // 세로·공중 요소: 머리 위 높이 도는 눈보라 소용돌이(따라온다) + 감아 오르는 눈 나선 + 1초마다 얼음 가시가 솟는다
                    CastFx.Cols frost = rgb(fx, 0x8fd8ff, 0xeafcff);
                    Supplier<Location> sky = () -> c.isValid() ? Kit.ground(c.getLocation()).add(0, 6.5, 0) : null;
                    Location s0 = sky.get();
                    String sm = fx.vfx.models.pick("swirl_dim", "swirl");
                    if (s0 != null && sm != null) {
                        Sprite sw = Kit.flat(fx, sm, s0, 0.5, Shapes.Frame.FLAT, frost).life(122).range(2).end(Sprite.End.FADE, 6).follow(sky, 2);
                        sw.decal = true;
                        sw.edgeOn = 0.15;
                        sw.scaleTo(1, 8, 5.5 / Geo.FLAT_HALF, 1, 5.5 / Geo.FLAT_HALF).radius(5.5);
                        Kit.spinOver(sw, 9, 112, -150);
                        sw.go();
                    }
                    fx.vfx.every(0, 2, 60, i -> {
                        if (!c.isValid()) return;
                        Location f = c.getLocation();
                        for (int st = 0; st < 2; st++) {
                            double a = i * 0.35 + Math.PI * st;
                            double h = (i % 15) / 15.0 * 5.5;
                            double rr = 2.6 + h * 0.25;
                            Emit.send(fx, f.clone().add(Math.cos(a) * rr, h, Math.sin(a) * rr), Particle.SNOWFLAKE, null, 1, 0, 0, 0, 0, Emit.NORMAL);
                            Emit.dust(fx, f.clone().add(Math.cos(a + 0.3) * rr, h + 0.2, Math.sin(a + 0.3) * rr), frost.b(), 0.9, Emit.DETAIL);
                        }
                    });
                    fx.vfx.every(10, 20, 5, i -> {
                        if (!c.isValid()) return;
                        double a = Kit.rnd().nextDouble(Math.PI * 2), d = Kit.rnd().nextDouble(3.2, 5.2);
                        Kit.iceSpikes(fx, Kit.ground(c.getLocation().add(Math.cos(a) * d, 0.5, Math.sin(a) * d)), 0.7, 3, 16);
                    });
                })
                .on(Ev.Hit.class, (fx, e) -> {
                    if (!e.tick()) return;
                    Location l = e.target().getLocation().add(0, e.target().getHeight() * 0.5, 0);
                    Emit.send(fx, l, Particle.BLOCK, Material.ICE.createBlockData(), 6, 0.2, 0.3, 0.2, 0.1, Emit.DETAIL);
                }));

        m.put("glacier_prison", Sig.of()
                .on(Ev.Hit.class, (fx, e) -> {
                    if (e.tick()) return;
                    // 기절 2.5초 동안 얼음에 갇혀 있다가 깨진다
                    Pieces.encase(fx, e.target(), 50);
                })
                .on(Ev.Nova.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.center());
                    fx.vfx.after(Math.max(1, e.expand()), () -> Kit.iceSpikes(fx, g, e.radius() * 0.6, 6, 16));
                }));

        // ── 화염 망치 ──
        m.put("volcano", Sig.of()
                .cast(fx -> {
                    Location g = Kit.ground(fx.caster.getLocation());
                    Kit.cracks(fx, g, 7, 8, Color.fromRGB(0xff6a10), Particle.LAVA);
                    Pieces.fireSheets(fx, g, 0.8, 3, 4, 20, fx.cols());
                    fx.sound(g, "block.lava.extinguish", 0.8, 0.6);
                })
                .track(Ev.Drop.class, (fx, e) -> new Track() {
                    @Override
                    public void end(Location at, boolean impact) {
                        Location g = at.clone().add(0, 0.05, 0);
                        if (Kit.rnd().nextInt(3) == 0) Pieces.fireSheets(fx, g, 0.3, 1, 2, 10, fx.cols());
                        Emit.send(fx, g.clone().add(0, 0.4, 0), Particle.LAVA, null, 4, 0.4, 0.2, 0.4, 0, Emit.NORMAL);
                    }
                }));

        // ── 공허의 사신 ──
        m.put("black_hole", Sig.of()
                .replace(Ev.Vortex.class)
                .track(Ev.Vortex.class, (fx, e) -> {
                    List<Sprite> bh = Pieces.blackHole(fx, e.center().clone().add(0, -0.8, 0), e.radius(), e.duration() + 6);
                    Location g = AreaFx.groundAt(e.center()).add(0, 0.02, 0);
                    if (Kit.decalFits(g, 5)) {
                        Sprite[] cs = Kit.circle(fx, g, 5, e.duration() + 4, fx.cols(), -50, false, Sprite.View.AUTO);
                        for (Sprite s : cs) if (s != null) bh.add(s);
                    }
                    return new Track() {
                        int t;

                        @Override
                        public void tick(Location pos, Vector v) {
                            t++;
                            if (t % 10 == 0) fx.sound(e.center(), "block.respawn_anchor.charge", 0.5, 0.6 + 0.7 * t / (double) Math.max(1, e.duration()));
                        }

                        @Override
                        public void end(Location at, boolean impact) {
                            Pieces.collapse(bh);
                        }
                    };
                })
                .replace(Ev.Nova.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    Location c = e.center();
                    Location g = AreaFx.groundAt(c);
                    CastFx.Cols pw = rgb(fx, 0xb06aff, 0xffffff);
                    Pieces.starburst(fx, c.clone().add(0, 1.2, 0), 4, 6, pw, 24);
                    Pieces.shockwave(fx, g, e.radius(), 4, new CastFx.Cols[]{fx.cols(), pw, fx.cols()}, 2, false);
                    Kit.debris(fx, g, 6, 1.3, Material.CRYING_OBSIDIAN);
                    Kit.afterglow(fx, g, 3.5, 30, fx.cols());
                }));

        // 차원 베기: 거대한 초승달이 날아가고, 지나간 길에 검은 차원 틈(rift)이 뒤따라 열렸다가 닫힌다
        m.put("dimension_cut", Sig.of()
                .replace(Ev.Beam.class)
                .on(Ev.Beam.class, (fx, e) -> {
                    Vector d = e.dir().clone().normalize();
                    double len = e.start().distance(e.end());
                    CastFx.Cols k = fx.cols(e.core());
                    int T = RangedFx.slashWave(fx, e, rgb(fx, 0x9a3aff, 0xe6b0ff), 1.7, 58, true);
                    if (len > 2.5) {
                        Location s0 = e.start().clone().add(d.clone().multiply(1.2));
                        double l0 = len - 1.2;
                        double sw = e.width() * 0.6;
                        String rm = fx.vfx.models.pick("rift", "beam");
                        Sprite rift = Kit.beam(fx, rm, s0, d, 0.2, sw, T + 14, rgb(fx, 0x9a3aff, 0xe6b0ff));
                        rift.key(1, Math.max(2, T), sp -> sp.sc.set((float) sw, (float) sw, (float) l0));
                        rift.segLen = l0;
                        rift.go();
                    }
                    // 갈라진 틈으로 빨려 드는 입자, 끝의 보라 별
                    fx.vfx.every(0, 2, 6, i -> Shapes.line(e.start().clone().add(d.clone().multiply(1.5)), e.end(), 1.0, (p, t) -> {
                        Vector off = new Vector(Kit.rnd().nextGaussian(), Kit.rnd().nextGaussian(), Kit.rnd().nextGaussian()).multiply(0.9);
                        Emit.trail(fx, p.clone().add(off), p, Color.fromRGB(0xb06aff), 6, Emit.DETAIL);
                    }));
                    Kit.star(fx, e.end(), 2.0, 8, rgb(fx, 0xb06aff, 0xffffff)).go();
                    fx.sound(e.end(), "entity.enderman.stare", 0.5, 0.5);
                    if (len > 6) Kit.afterglow(fx, e.end(), 1.5, 30, fx.cols());
                }));

        // ── 천벌의 창 (번개) ──
        m.put("judgment_bolt", Sig.of()
                .on(Ev.Beam.class, (fx, e) -> {
                    // 광선이 꺼진 뒤에도 길을 따라 전기가 0.7초쯤 튄다 (이온화된 길)
                    Vector d = e.dir().clone().normalize();
                    Location a0 = e.start().clone().add(d.clone().multiply(1.5));
                    fx.vfx.every(6, 3, 5, i -> {
                        List<Location> b = Shapes.bolt(a0, e.end(), (int) Math.max(5, a0.distance(e.end()) / 1.6), 0.45, Kit.rnd());
                        for (int j = 0; j + 1 < b.size(); j++)
                            Emit.line(fx, b.get(j), b.get(j + 1), 0.3, j % 3 == 0 ? Color.WHITE : fx.pal.b(), 0.7 - i * 0.08, Emit.DETAIL);
                    });
                })
                .on(Ev.Strike.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.point().clone().add(0, 0.5, 0)).add(0, 0.02, 0);
                    Kit.cracks(fx, g, 3.2, 7, fx.pal.a(), Particle.ELECTRIC_SPARK);
                    Kit.star(fx, g.clone().add(0, 1.4, 0), 1.8, 5, fx.cols()).go();
                }));

        m.put("thunder_descent", Sig.of()
                .track(Ev.Leap.class, (fx, e) -> {
                    LivingEntity c = fx.caster;
                    // 높이 뛰어오른 동안에도 마법진은 땅에 남아 착지할 자리를 따라간다 (공중에 뜬 발판처럼 보이지 않게)
                    Location[] last = {Kit.ground(c.getLocation()).add(0, 0.02, 0)};
                    Supplier<Location> gp = () -> {
                        if (!c.isValid()) return null;
                        Location g = Kit.groundBelow(c.getLocation(), 32);
                        if (g != null) last[0] = g.add(0, 0.02, 0);
                        return last[0].clone();
                    };
                    List<Sprite> parts = new ArrayList<>();
                    Location g0 = gp.get();
                    if (g0 != null) {
                        for (Sprite s : Kit.circle(fx, g0, 3, 70, fx.cols(), 90, false, Sprite.View.AUTO)) if (s != null) {
                            s.follow(gp, 2);
                            parts.add(s);
                        }
                    }
                    return new Track() {
                        int t;

                        @Override
                        public void tick(Location pos, Vector v) {
                            t++;
                            for (int s = 0; s < 2; s++) {
                                double a = t * 0.8 + Math.PI * s;
                                Emit.send(fx, pos.clone().add(Math.cos(a) * 0.8, 0.9, Math.sin(a) * 0.8), Particle.ELECTRIC_SPARK, null, 2, 0.05, 0.3, 0.05, 0.02, Emit.NORMAL);
                            }
                            // 공중의 몸에서 땅의 마법진으로 번개가 튄다 (뛰어오른 동안에도 '번개 신'이 보이게)
                            Location gnd = gp.get();
                            if (t % 3 == 0 && gnd != null && pos.getY() - gnd.getY() > 1.5) {
                                double a = Kit.rnd().nextDouble(Math.PI * 2);
                                Location hit = gnd.clone().add(Math.cos(a) * 2.6, 0.1, Math.sin(a) * 2.6);
                                RangedFx.drawBolt(fx, pos.clone().add(0, 0.8, 0), hit, 6, 0.4, fx.cols(), t % 6 == 0 ? 0 : 1);
                                if (t % 6 == 0) fx.sound(hit, "entity.lightning_bolt.impact", 0.25, 1.8);
                            }
                        }

                        @Override
                        public void end(Location at, boolean impact) {
                            for (Sprite s : parts) s.finish(3);
                            Location g = Kit.ground(at).add(0, 0.03, 0);
                            Pieces.shockwave(fx, g, 5, 4, new CastFx.Cols[]{fx.cols(), fx.cols().swap()}, 2, false);
                            Kit.star(fx, g.clone().add(0, 1.2, 0), 2.2, 5, fx.cols()).go();
                        }
                    };
                }));

        // ── 성검 (빛) ──
        m.put("holy_judgment", Sig.of()
                .cast(fx -> {
                    Location c = fx.root.aim(20);
                    Location g = Kit.ground(c).add(0, 0.02, 0);
                    if (Kit.decalFits(g, 5)) Kit.circle(fx, g, 5, 30, fx.cols(), 30, true, Sprite.View.AUTO);
                })
                .replace(Ev.Strike.class)
                .on(Ev.Strike.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.point().clone().add(0, 0.5, 0));
                    double w = e.on() != null ? Math.min(3, e.on().getWidth() + 0.6) : 2.2;
                    Pieces.lightPillar(fx, g, w, 12, 10, fx.cols(), true);
                    Sprite halo = Kit.ring(fx, g.clone().add(0, 11.5, 0), 0.6, w * 0.9, 3, 10, fx.cols(), null);
                    halo.decal = false;
                    halo.go();
                    Kit.rimSpray(fx, g, 0.6, fx.n(8), Fx2.END_ROD, 0.2, 0.5, Emit.DETAIL);
                    fx.sound(g, "block.bell.use", 0.6, 1.6);
                }));

        m.put("guardian_light", Sig.of()
                .on(Ev.Ally.class, (fx, e) -> {
                    BuffFx.gyroscope(fx, e.who(), 1.0, 22, fx.cols(), Sprite.View.AUTO);
                    LivingEntity w = e.who();
                    Supplier<Location> head = () -> w.isValid() ? w.getLocation().add(0, w.getHeight() + 0.45, 0) : null;
                    Location h = head.get();
                    if (h != null) Kit.ring(fx, h, 0.45, 0.45, 1, 40, fx.cols(), null).follow(head, 1).go();
                }));

        // ── 혈월도 (피) ──
        m.put("crimson_moon", Sig.of()
                .cast(fx -> {
                    CastFx.Cols k = fx.cols();
                    Vector look = fx.caster.getLocation().getDirection().setY(0);
                    if (look.lengthSquared() < 1e-6) look = new Vector(0, 0, 1);
                    look.normalize();
                    // 남에게는 시전자 등 뒤 위쪽에, 시전자에게는 시선 앞 위쪽에 붉은 달
                    Location behind = fx.caster.getLocation().add(look.clone().multiply(-2)).add(0, 4.2, 0);
                    Pieces.moon(fx, behind, 5, 18, k, fx.cp != null ? Sprite.View.HIDE : Sprite.View.AUTO);
                    if (fx.cp != null) Pieces.moon(fx, Kit.heroSpot(fx, 10, 4.5), 4, 18, k, Sprite.View.ONLY);
                    fx.sound(fx.caster.getLocation(), "block.beacon.deactivate", 0.5, 0.6);
                })
                .replace(Ev.Cone.class)
                .on(Ev.Cone.class, (fx, e) -> {
                    CastFx.Cols k = fx.cols(e.yaml());
                    CastFx.Cols dark = rgb(fx, 0x7a0018, 0xff6a7e);
                    double sweep = Math.toDegrees(e.half() * 2);
                    Pieces.giantSlash(fx, e.base(), e.dir(), e.range(), 24, sweep, 9, k, false, Sprite.View.SHOW);
                    fx.vfx.after(2, () -> Kit.slash(fx, MeleeFx.slashModel(fx, 160, dark), e.base().clone().add(0, -0.05, 0),
                            Shapes.Frame.flat(e.dir()).roll(-14), e.range() * 1.08, 8, dark).view(Sprite.View.SHOW).go());
                    Shapes.arc(e.base(), Shapes.Frame.flat(e.dir()), e.range(), -e.half(), e.half(), fx.n(30),
                            (p, t) -> Emit.dust(fx, p, Color.WHITE, 0.8, Emit.DETAIL));
                    Kit.rimSpray(fx, e.base(), e.range() * 0.9, fx.n(12), fx.pal.spark(), 0.2, 0.1, Emit.DETAIL);
                })
                .on(Ev.Hit.class, (fx, e) -> {
                    if (e.tick()) return;
                    Location l = e.target().getLocation().add(0, e.target().getHeight() * 0.5, 0);
                    Emit.send(fx, l, Particle.BLOCK, Material.REDSTONE_BLOCK.createBlockData(), 12, 0.25, 0.3, 0.25, 0.15, Emit.NORMAL);
                }));

        m.put("blood_rush", Sig.of()
                .track(Ev.Dash.class, (fx, e) -> {
                    List<Location> path = new ArrayList<>();
                    return new Track() {
                        @Override
                        public void tick(Location pos, Vector vel) {
                            path.add(pos.clone());
                        }

                        @Override
                        public void end(Location at, boolean impact) {
                            List<Location> p = new ArrayList<>(path);
                            fx.vfx.every(0, 4, 4, i -> {
                                for (Location l : p) Emit.dust(fx, l.clone().add(0, -0.5 - i * 0.1, 0), Color.fromRGB(0x8a0020), 1.3, Emit.DETAIL);
                            });
                        }
                    };
                }));

        // ── 세계수 지팡이 (숲) ──
        m.put("life_garden", Sig.of()
                .track(Ev.Zone.class, (fx, e) -> {
                    Location c = Kit.ground(e.center()).add(0, 0.04, 0);
                    double r = e.radius();
                    return new Track() {
                        int t;

                        @Override
                        public void tick(Location pos, Vector v) {
                            t++;
                            if (t % 20 == 1) Kit.ring(fx, c, 0.5, r, 10, 14, fx.cols(), null).go();
                            if (t % 5 == 0) {
                                // 가장자리에서 감겨 오르는 덩굴
                                double a0 = t * 0.2;
                                for (int s = 0; s < 3; s++) {
                                    double a = a0 + s * Math.PI * 2 / 3;
                                    for (int i = 0; i < 4; i++) {
                                        double rr = r * (1 - i * 0.12), aa = a + i * 0.35;
                                        Emit.dust(fx, c.clone().add(Math.cos(aa) * rr, 0.15 + i * 0.15, Math.sin(aa) * rr), Color.fromRGB(0x3ad040), 1.0, Emit.DETAIL);
                                    }
                                }
                            }
                        }
                    };
                }));

        m.put("vine_storm", Sig.of()
                .on(Ev.Hit.class, (fx, e) -> {
                    if (e.tick()) return;
                    LivingEntity t = e.target();
                    fx.vfx.every(0, 2, 10, i -> {
                        if (!t.isValid()) return;
                        for (int s = 0; s < 2; s++) {
                            double a = i * 0.7 + Math.PI * s;
                            Location p = t.getLocation().add(Math.cos(a) * (t.getWidth() * 0.6 + 0.2), i * t.getHeight() / 10, Math.sin(a) * (t.getWidth() * 0.6 + 0.2));
                            Emit.send(fx, p, Particle.BLOCK, Material.VINE.createBlockData(), 2, 0.05, 0.05, 0.05, 0, Emit.NORMAL);
                            Emit.dust(fx, p, Color.fromRGB(0x3ad040), 0.9, Emit.DETAIL);
                        }
                    });
                }));

        // ── 심연의 삼지창 (바다) ──
        m.put("tsunami", Sig.of()
                .track(Ev.Projectile.class, (fx, e) -> new Track() {
                    @Override
                    public void tick(Location pos, Vector vel) {
                        Emit.send(fx, pos.clone().add(0, 1.6, 0), Particle.FALLING_WATER, null, 4, 0.8, 0.2, 0.8, 0, Emit.DETAIL);
                    }

                    @Override
                    public void end(Location at, boolean impact) {
                        Location g = Kit.ground(at).add(0, 0.03, 0);
                        Kit.ring(fx, g, 0.5, 2.5, 4, 9, fx.cols(), null).go();
                        Emit.send(fx, g.clone().add(0, 1, 0), Particle.SPLASH, null, 40, 1.2, 0.8, 1.2, 0.2, Emit.NORMAL);
                        fx.sound(g, "entity.generic.splash", 1.0, 0.8);
                    }
                }));

        m.put("maelstrom", Sig.of()
                .track(Ev.Vortex.class, (fx, e) -> new Track() {
                    int t;

                    @Override
                    public void tick(Location pos, Vector v) {
                        t++;
                        Location c = e.center();
                        for (int s = 0; s < 3; s++) {
                            double a = t * 0.6 + s * Math.PI * 2 / 3;
                            double h = (t % 12) / 12.0 * 5;
                            double rr = 0.5 + h * 0.3;
                            Emit.send(fx, c.clone().add(Math.cos(a) * rr, -0.6 + h, Math.sin(a) * rr), Particle.SPLASH, null, 2, 0.05, 0.05, 0.05, 0, Emit.NORMAL);
                        }
                        if (t % 2 == 0) Emit.send(fx, c.clone().add(0, 4.4, 0), Particle.FALLING_WATER, null, 6, 1.2, 0.1, 1.2, 0, Emit.DETAIL);
                    }

                    @Override
                    public void end(Location at, boolean impact) {
                        Location g = AreaFx.groundAt(e.center());
                        Pieces.lightPillar(fx, g, 2.2, 8, 10, fx.cols(), false);
                        Pieces.shockwave(fx, g, 5, 4, new CastFx.Cols[]{fx.cols(), fx.cols().swap()}, 2, false);
                        Emit.send(fx, g.clone().add(0, 2, 0), Particle.SPLASH, null, 60, 1.2, 2.5, 1.2, 0.3, Emit.NORMAL);
                    }
                }));

        // ── 그림자 쌍검 ──
        m.put("blade_dance", Sig.of()
                .track(Ev.Orbit.class, (fx, e) -> new Track() {
                    int t;

                    @Override
                    public void point(int i, Location p) {
                        if (i == 0) t++;
                        if (i == 0 && t % 4 == 0) {
                            LivingEntity c = fx.caster;
                            Location mid = c.getLocation().add(0, e.y(), 0);
                            Shapes.arc(mid, Shapes.Frame.flat(p.toVector().subtract(mid.toVector())), e.radius(), -0.6, 0.6, 8,
                                    (q, s) -> Emit.dust(fx, q, Color.fromRGB(0x6a5a9a), 1.0, Emit.DETAIL));
                        }
                        if (t % 3 == 0) Emit.send(fx, p, Particle.SMOKE, null, 1, 0.05, 0.05, 0.05, 0.01, Emit.DETAIL);
                    }
                }));

        m.put("shadow_clone", Sig.of()
                .on(Ev.Summon.class, (fx, e) -> {
                    Location g = Kit.ground(e.at());
                    fx.vfx.every(0, 2, 6, i -> {
                        Emit.send(fx, g.clone().add(0, 0.3 + i * 0.35, 0), Particle.LARGE_SMOKE, null, 3, 0.25, 0.1, 0.25, 0.01, Emit.NORMAL);
                        Emit.send(fx, g.clone().add(0, 0.3 + i * 0.35, 0), Particle.SQUID_INK, null, 2, 0.2, 0.1, 0.2, 0.01, Emit.DETAIL);
                    });
                    Emit.send(fx, g.clone().add(0, 1, 0), Particle.REVERSE_PORTAL, null, 20, 0.3, 0.6, 0.3, 0.1, Emit.NORMAL);
                }));

        // ── 별의 대검 ──
        m.put("starfall", Sig.of()
                .track(Ev.Drop.class, (fx, e) -> {
                    Location[] at = {e.start().clone()};
                    Sprite sp = Sprite.item(fx, fx.vfx.models.pick("spark", "star", "orb"), e.start()).size(0.8).radius(0.5).life(60)
                            .tint(Color.WHITE, Color.fromRGB(0xc8b8ff), fx.dark()).follow(() -> at[0], 1).end(Sprite.End.SHRINK, 2);
                    sp.go();
                    return new Track() {
                        @Override
                        public void tick(Location pos, Vector vel) {
                            at[0] = pos.clone();
                        }

                        @Override
                        public void end(Location a, boolean impact) {
                            sp.finish(2);
                        }
                    };
                }));

        m.put("galaxy_burst", Sig.of()
                .track(Ev.Vortex.class, (fx, e) -> {
                    Location c = e.center();
                    // 별자리: 가장자리 여섯 점을 잇는 선
                    List<Location> stars = Shapes.around(c.clone().add(0, -0.4, 0), e.radius() * 0.85, 6, Kit.rnd().nextDouble(Math.PI));
                    return new Track() {
                        int t;

                        @Override
                        public void tick(Location pos, Vector v) {
                            t++;
                            if (t % 4 == 0) {
                                for (int i = 0; i < stars.size(); i++) {
                                    Location a = stars.get(i), b = stars.get((i + 2) % stars.size());
                                    Emit.line(fx, a, b, 0.6, Color.fromRGB(0xc8b8ff), 0.6, Emit.DETAIL);
                                    Emit.send(fx, a, Particle.END_ROD, null, 1, 0, 0, 0, 0, Emit.NORMAL);
                                }
                            }
                        }
                    };
                })
                .on(Ev.Nova.class, (fx, e) -> {
                    Location c = e.center().clone().add(0, 1.2, 0);
                    Pieces.bigStar(fx, c.clone().add(0, 0.8, 0), 3.2, 12, rgb(fx, 0x6a5aff, 0xffffff), Sprite.View.HIDE, 3);
                    Pieces.rays(fx, c, Math.min(40, fx.n(24)), 7, rgb(fx, 0x6a5aff, 0xc8b8ff), 9, false);
                    for (Vector d : Pieces.sphereDirs(fx.n(8))) Emit.dir(fx, c, Particle.FIREWORK, null, d, 0.3, Emit.DETAIL);
                }));

        // ── 폭풍 장궁 ──
        m.put("thunder_volley", Sig.of()
                .on(Ev.Strike.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.point().clone().add(0, 0.5, 0));
                    Kit.star(fx, g.clone().add(0, 0.9, 0), 1.0, 4, fx.cols()).go();
                }));

        m.put("chain_arrow", Sig.of()
                .on(Ev.Chain.class, (fx, e) -> {
                    if (fx.starSlot()) Kit.star(fx, e.to(), 1.0, 4, fx.cols()).go();
                }));

        // 기본 연출로 충분한 보스 기술 (운석 낙하는 Pieces.meteor 가 자동으로 붙는다)
        m.putIfAbsent("meteor", Sig.of());
    }
}
