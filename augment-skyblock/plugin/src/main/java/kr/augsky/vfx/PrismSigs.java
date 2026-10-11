package kr.augsky.vfx;

import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.entity.LivingEntity;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

/** 프리즘 무기 17개 기술의 전용 연출. 화면을 채우되 짧게, 시전자 1인칭에서도 큰 장면이 보이게 */
final class PrismSigs {
    private PrismSigs() {}

    static final Color WHITE = Color.WHITE;

    static CastFx.Cols hue(CastFx fx, double h) {
        Color a = Palette.hue(h);
        return new CastFx.Cols(a, Palette.hue(h + 0.08, 0.3, 1.0), fx.dark(), fx.night ? a : Palette.rimOf(a, fx.dark()), false);
    }

    static CastFx.Cols rgb(CastFx fx, int a, int b) {
        Color ca = Color.fromRGB(a);
        return new CastFx.Cols(ca, Color.fromRGB(b), fx.dark(), fx.night ? ca : Palette.rimOf(ca, fx.dark()), false);
    }

    static CastFx.Cols rainbow(CastFx fx) {
        return new CastFx.Cols(Palette.hue(fx.vfx.tick * 0.02), WHITE, Color.fromRGB(0x2a2a4a), fx.rim(), true);
    }

    static Supplier<Location> feet(CastFx fx, double lift) {
        LivingEntity c = fx.caster;
        return () -> c.isValid() ? Kit.ground(c.getLocation()).add(0, lift, 0) : null;
    }

    static Location chest(CastFx fx) {
        return fx.caster.getLocation().add(0, fx.caster.getHeight() * 0.6, 0);
    }

    /** 여러 겹 광선 (흰 심 + 두 색), 수직 고리, 끝 별, 총구 마법진(남에게만), 남는 반짝임 */
    static void layeredBeam(CastFx fx, Ev.Beam e, CastFx.Cols[] layers, int rings, boolean sparkle, String model, double endStar,
                            boolean rainbowRings) {
        Location start = e.start();
        Vector dir = e.dir().clone().normalize();
        Location end = e.end();
        double len = start.distance(end), w = e.width();
        if (len < 1.5) return;
        if (!fx.vfx.models.has(model)) model = "beam";
        String mdl = model;
        Location s0 = start.clone().add(dir.clone().multiply(1.2));
        double l0 = Math.max(0.5, len - 1.2);
        double[] widths = {0.28, 0.7, 1.2};
        for (int i = 0; i < layers.length && i < 3; i++) {
            String m = i == 2 ? fx.vfx.models.pick(model + "_dim", "beam_dim", model) : model;
            Sprite b = Kit.beam(fx, m, s0, dir, l0, w * widths[i], 11 - i, layers[i]).view(fx.cp != null ? Sprite.View.HIDE : Sprite.View.AUTO);
            b.radius(w * widths[i] * 0.5);
            b.go();
            if (i == 1) Kit.hallmark(fx, b);
        }
        if (fx.cp != null) RangedFx.handBeam(fx, start, dir, end, w, model, layers[Math.min(1, layers.length - 1)]);
        CastFx.Cols main = layers[Math.min(1, layers.length - 1)];
        String cm = rainbowRings ? fx.vfx.models.pick("circle_rainbow", "circle") : "circle";
        Sprite mz = Kit.flat(fx, cm, start.clone().add(dir.clone().multiply(1.8)), 0.2, Shapes.Frame.normal(dir), main).life(11).view(Sprite.View.HIDE);
        mz.decal = false;
        mz.scaleTo(1, 3, (0.9 + w) / Geo.FLAT_HALF, 1, (0.9 + w) / Geo.FLAT_HALF);
        mz.spin(4, 6, 60);
        mz.go();
        for (int j = 1; j <= rings; j++) {
            double t = len * j / (rings + 1.0);
            Location q = start.clone().add(dir.clone().multiply(t));
            CastFx.Cols rk = rainbowRings ? hue(fx, j / (double) rings) : layers[j % layers.length];
            fx.vfx.after(j, () -> {
                Sprite rg = Kit.flat(fx, "ring", q, 0.25 + w * 0.3, Shapes.Frame.normal(dir), rk).life(7);
                rg.decal = false;
                rg.scaleTo(1, 4, (0.7 + w) / Geo.FLAT_HALF, 1, (0.7 + w) / Geo.FLAT_HALF);
                rg.go();
            });
        }
        Kit.star(fx, end, endStar, 6, rainbowRings ? rainbow(fx) : main).go();
        Location g = Kit.groundOrNull(end);
        if (g != null && end.getY() - g.getY() < 2) Kit.shock(fx, g.add(0, 0.03, 0), 0.3, 1.8 + w, 3, 8, main).go();
        if (sparkle) {
            List<Location> pts = new ArrayList<>();
            Shapes.line(start.clone().add(dir.clone().multiply(1.5)), end, 1.0, (p, t) -> pts.add(p));
            fx.vfx.every(2, 4, 5, i -> {
                for (Location p : pts) {
                    Location q = p.clone().add(Kit.rnd().nextGaussian() * 0.35, Kit.rnd().nextGaussian() * 0.3 + i * 0.06, Kit.rnd().nextGaussian() * 0.35);
                    Emit.dust(fx, q, Palette.hue(Kit.rnd().nextDouble()), 0.7, Emit.DETAIL);
                }
            });
        }
        // 광선 둘레를 감는 두 줄 나선
        Shapes.Frame fr = Shapes.Frame.along(dir);
        int pts = (int) Math.min(50, len / 0.35);
        for (int i = 0; i < pts; i++) {
            double t = 1.2 + i * 0.35;
            if (t > len) break;
            for (int s = 0; s < 2; s++) {
                double a = t * 2.0 + Math.PI * s;
                Emit.dust(fx, fr.point(start, Math.cos(a) * w * 0.55, Math.sin(a) * w * 0.55, t), s == 0 ? layers[layers.length - 1].a() : main.a(), 0.7, Emit.DETAIL);
            }
        }
        String unused = mdl;
    }

    static void register(Map<String, Signature> m) {
        // ── 프리즘 대검 ──
        m.put("prism_burst", Sig.of()
                .cast(fx -> {
                    // 바닥 마법진 대신 머리 위에서 도는 프리즘 결정: 파동마다 번쩍이며 무지개 빛을 바닥으로 쏜다
                    LivingEntity c = fx.caster;
                    Supplier<Location> over = () -> c.isValid() ? c.getLocation().add(0, c.getHeight() + 1.9, 0) : null;
                    Pieces.Crystal cr = Pieces.prismCrystal(fx, over, 1.3, 30, fx.cp != null ? Sprite.View.HIDE : Sprite.View.AUTO);
                    fx.memo.put("crystal", cr);
                    if (fx.cp != null) {
                        // 시전자: 시선 위쪽 앞에 같은 결정 (머리 위는 1인칭에서 안 보인다)
                        Location hs = Kit.heroSpot(fx, 8, 3.2);
                        Pieces.Crystal mine = Pieces.prismCrystal(fx, () -> hs, 1.0, 30, Sprite.View.ONLY);
                        fx.memo.put("crystal2", mine);
                    }
                })
                .replace(Ev.Nova.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    int w = fx.seq("burst");
                    CastFx.Cols k = fx.cols(e.yaml());
                    Location c = e.center();
                    Location g = AreaFx.groundAt(c);
                    double r = e.radius();
                    int ex = Math.max(3, e.expand());
                    for (String key : new String[]{"crystal", "crystal2"}) {
                        if (fx.memo.get(key) instanceof Pieces.Crystal cr) Pieces.pulse(fx, cr);
                    }
                    // 결정에서 바닥 테두리로 내리꽂히는 무지개 빛줄기
                    Location top = fx.caster.getLocation().add(0, fx.caster.getHeight() + 1.9, 0);
                    for (int i = 0; i < 10; i++) {
                        double a = Math.PI * 2 * i / 10 + w * 0.3;
                        Location to = g.clone().add(Math.cos(a) * r * 0.9, 0.2, Math.sin(a) * r * 0.9);
                        Emit.streak(fx, top, to, Palette.hue(i / 10.0 + w * 0.33), 3, ex, Emit.NORMAL);
                    }
                    Sprite ring = Kit.ring(fx, g.clone().add(0, 0.03, 0), r * 0.15, r, ex, ex + 5, k, null);
                    ring.go();
                    Kit.hallmark(fx, ring);
                    Kit.shock(fx, g.clone().add(0, 0.025, 0), r * 0.1, r * 0.92, ex + 1, ex + 6, k.swap()).go();
                    if (w == 0) fx.vfx.every(0, 2, ex / 2, i -> Kit.rimSpray(fx, c, r * (i * 2 + 2) / ex, fx.n(5), Fx2.END_ROD, 0.15, 0.25, Emit.DETAIL));
                    fx.vfx.after(ex, () -> {
                        Kit.dustRing(fx, c, r, k.a(), 1.5, Emit.NORMAL);
                        // 첫 파동: 결정 가시가 테두리에서 솟는다 / 둘째: 무지개 빛기둥 / 셋째: 둘 다
                        if (w != 1) Kit.crystalSpikes(fx, g, r * 0.95, w == 2 ? 6 : 7, 14);
                        if (w >= 1) {
                            int n = 6;
                            int i = 0;
                            for (Location p : Shapes.around(g, r, n, w * 0.4 + 0.25)) {
                                Location pg = Kit.ground(p.clone().add(0, 0.5, 0));
                                Kit.pillar(fx, pg, 0.6, 3.0, 8, hue(fx, w / 3.0 + i++ / (double) n)).go();
                            }
                        }
                    });
                    fx.sound(c, "block.amethyst_block.chime", 1.0, 0.9 + 0.3 * w);
                    if (w == 2) {
                        Pieces.bigStar(fx, c.clone().add(0, 4.2, 0), 2.4, 12, rainbow(fx), Sprite.View.HIDE, 3);
                        Kit.debris(fx, g, 6, 1.0, Material.AMETHYST_BLOCK);
                        fx.sound(c, "block.amethyst_block.resonate", 1.2, 1.4);
                    }
                }));

        m.put("rainbow_beam", Sig.of()
                .replace(Ev.Beam.class)
                .on(Ev.Beam.class, (fx, e) -> {
                    int i = fx.seq("rb");
                    double h = i / 5.0;
                    CastFx.Cols[] layers = {rgb(fx, 0xffffff, 0xffffff), hue(fx, h), hue(fx, h + 0.15)};
                    layeredBeam(fx, e, layers, 4, true, "beam_rainbow", 1.6, true);
                }));

        m.put("spectrum_break", Sig.of()
                .cast(fx -> {
                    // 바닥 마법진 대신 '빛의 감옥': 머리 위 높이 떠서 도는 거대한 무지개 고리에서 일곱 빛 장막이 땅으로 드리우고,
                    // 기를 모으는 동안 고리가 좁아지며 장막이 시전자 쪽으로 모인다
                    LivingEntity c = fx.caster;
                    Location c0 = c.getLocation();
                    int charge = 30;
                    Supplier<Double> rad = () -> 7.0 - 3.6 * Math.min(1.0, fx.age() / (double) charge);
                    Location crown0 = c0.clone().add(0, 5.2, 0);
                    Sprite crown = Kit.flat(fx, fx.vfx.models.pick("ring_rainbow", "ring"), crown0, 0.5, Shapes.Frame.FLAT, rainbow(fx))
                            .life(charge + 8).range(2).end(Sprite.End.FADE, 4);
                    crown.decal = true;
                    crown.edgeOn = 0.12;
                    crown.radius(7);
                    crown.animate(1, charge + 4, 3, (sp, t) -> {
                        double rr = (7.0 - 3.6 * Math.min(1.0, t / (double) charge)) / Geo.FLAT_HALF;
                        sp.rot.set(new org.joml.Quaternionf().rotateY((float) Math.toRadians(-6 * t)));
                        sp.sc.set((float) rr, 1f, (float) rr);
                    });
                    crown.go();
                    Location gc = Kit.ground(c0);
                    for (int i = 0; i < 7; i++) {
                        int idx = i;
                        Supplier<Location> foot = () -> {
                            double a = idx * Math.PI * 2 / 7 + fx.age() * 0.05;
                            double rr = rad.get();
                            return gc.clone().add(Math.cos(a) * rr, 0.05, Math.sin(a) * rr);
                        };
                        Location f0 = foot.get();
                        Sprite veil = Kit.pillar(fx, f0, 0.55, 5.1, charge + 6, hue(fx, i / 7.0)).follow(foot, 1);
                        veil.go();
                    }
                    for (int i = 0; i < 7; i++) {
                        int idx = i;
                        Location p0 = c.getLocation().add(5, 3, 0);
                        Sprite s = Sprite.item(fx, fx.vfx.models.pick("spark", "star", "orb"), p0).size(0.9).radius(0.5).life(34)
                                .tint(Palette.hue(i / 7.0), WHITE, fx.dark()).end(Sprite.End.SHRINK, 3);
                        s.follow(() -> {
                            if (!c.isValid()) return null;
                            double t = Math.min(30, fx.age());
                            double rr = 5 * (1 - t / 34.0);
                            double a = idx * Math.PI * 2 / 7 + t * 0.14;
                            return c.getLocation().add(Math.cos(a) * rr, 3 - t / 30.0, Math.sin(a) * rr);
                        }, 1);
                        s.fallback(() -> Emit.dust(fx, p0, Palette.hue(idx / 7.0), 1.5, Emit.NORMAL));
                        s.go();
                    }
                    fx.vfx.every(0, 2, 15, i -> Kit.converge(fx, chest(fx), 8, 4, Palette.hue(i / 15.0), 10, Emit.NORMAL));
                    // 1인칭: 시선 앞 위쪽에서 빛이 모여 커지는 별
                    if (fx.cp != null) {
                        Location hs = Kit.heroSpot(fx, 9, 4);
                        Sprite h = Sprite.item(fx, fx.vfx.models.pick("star_rainbow", "star"), hs).size(0.3).radius(1).life(36)
                                .view(Sprite.View.ONLY).end(Sprite.End.FADE, 3).tint(WHITE, WHITE, fx.dark());
                        h.scaleTo(2, 30, 2.6);
                        h.hue(3, 0);
                        h.go();
                    }
                })
                .replace(Ev.Vortex.class)
                .track(Ev.Vortex.class, (fx, e) -> new Track() {
                    int t;

                    @Override
                    public void tick(Location pos, Vector v) {
                        t++;
                        Location c = e.center();
                        for (int arm = 0; arm < 7; arm++) {
                            double f = 1 - ((t * 0.06 + arm / 7.0) % 1);
                            double a = arm * Math.PI * 2 / 7 + (1 - f) * 2.6 + t * 0.1;
                            Emit.dust(fx, c.clone().add(Math.cos(a) * e.radius() * f, -0.6, Math.sin(a) * e.radius() * f), Palette.hue(arm / 7.0), 1.3, Emit.NORMAL);
                        }
                    }
                })
                .replace(Ev.Strike.class)
                .on(Ev.Strike.class, (fx, e) -> {
                    CastFx.Cols k = fx.cols(e.yaml());
                    double w = e.on() != null ? Math.min(3, e.on().getWidth() + 0.6) : 1.6;
                    Location g = AreaFx.groundAt(e.point().clone().add(0, 0.5, 0));
                    Pieces.lightPillar(fx, g, w, 10, 10, k, true);
                    Kit.rimSpray(fx, g, 0.6, fx.n(4), Fx2.END_ROD, 0.15, 0.6, Emit.DETAIL);
                })
                .replace(Ev.Nova.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    Location c = e.center();
                    Location g = AreaFx.groundAt(c);
                    double r = e.radius();
                    Emit.flash(fx, c.clone().add(0, 3, 0));
                    Pieces.bigStar(fx, c.clone().add(0, 3.0, 0), 6.5, 14, rainbow(fx), Sprite.View.AUTO, 3);
                    if (fx.cp != null) Pieces.bigStar(fx, Kit.heroSpot(fx, 9, 3.5), 3.2, 14, rainbow(fx), Sprite.View.ONLY, 3);
                    CastFx.Cols[] layers = {rainbow(fx), rgb(fx, 0xffffff, 0xffffff), rgb(fx, 0xff6b9d, 0xffd0e8), rgb(fx, 0x4dc3ff, 0xd0f4ff)};
                    Pieces.shockwave(fx, g, r * 1.03, Math.max(3, e.expand()), layers, 2, false);
                    fx.vfx.after(Math.max(3, e.expand()), () -> {
                        int i = 0;
                        for (Location p : Shapes.around(g, r, 12, 0)) {
                            Kit.pillar(fx, Kit.ground(p.clone().add(0, 0.5, 0)), 0.7, 4, 10, hue(fx, i++ / 12.0)).go();
                        }
                    });
                    Pieces.rays(fx, c.clone().add(0, 0.5, 0), fx.n(16), 9, rainbow(fx), 10, true);
                    Kit.debris(fx, g, 10, 1.3, Material.AMETHYST_BLOCK);
                }));

        // ── 종말의 낫 (종말: 영혼 청록 + 보랏빛 + 검정) ──
        // 하늘이 찢어져 파편이 쏟아진다: 높은 하늘의 검붉은 균열 + 바닥에는 작은 안쪽 문양만 (종말의 날 마법진과 다르게)
        m.put("apocalypse", Sig.of()
                .cast(fx -> fx.sound(fx.caster.getLocation(), "entity.wither.ambient", 0.4, 0.5))
                .replace(Ev.Rain.class)
                .on(Ev.Rain.class, (fx, e) -> {
                    Location gc = Kit.ground(e.center()).add(0, 0.02, 0);
                    int fall = (int) Math.ceil(e.height() / Math.max(0.3, e.speed()));
                    int life = (e.count() - 1) * e.interval() + fall + 8;
                    CastFx.Cols doom = rgb(fx, 0xff2a5a, 0x3ae8ff);
                    Location sky = gc.clone().add(0, Math.max(8, e.height() + 1.5), 0);
                    Pieces.skyRift(fx, sky, e.radius() + 1.5, life, new CastFx.Cols(Color.fromRGB(0xc0103a), Color.fromRGB(0xff7aa0),
                            Color.fromRGB(0x14000e), Color.fromRGB(0x5a0018), false));
                    if (Kit.decalFits(gc, e.radius() * 0.6) && fx.vfx.models.has("circle_inner")) {
                        double rr = e.radius() * 0.6;
                        Sprite in = Kit.flat(fx, "circle_inner", gc, 0.2, Shapes.Frame.FLAT, doom).life(life).end(Sprite.End.FADE, 6);
                        in.scaleTo(1, 6, rr / Geo.FLAT_HALF, 1, rr / Geo.FLAT_HALF).radius(rr);
                        Kit.spinOver(in, 7, life - 7, -45);
                        in.go();
                    }
                    fx.sound(gc, "entity.warden.ambient", 0.6, 0.5);
                })
                .track(Ev.Drop.class, (fx, e) -> new Track() {
                    Location prev = e.start().clone();

                    @Override
                    public void tick(Location pos, Vector vel) {
                        Emit.send(fx, pos, Particle.SOUL_FIRE_FLAME, null, 2, 0.12, 0.12, 0.12, 0.01, Emit.NORMAL);
                        Emit.streak(fx, prev, pos, fx.pal.a(), 2, 4, Emit.DETAIL);
                        prev = pos.clone();
                    }

                    @Override
                    public void end(Location at, boolean impact) {
                        Emit.send(fx, at.clone().add(0, 0.4, 0), Particle.SCULK_SOUL, null, 4, 0.4, 0.2, 0.4, 0.03, Emit.DETAIL);
                    }
                }));

        m.put("soul_storm", Sig.of()
                .cast(fx -> {
                    Supplier<Location> ft = feet(fx, 0.02);
                    Location g = ft.get();
                    if (g != null && Kit.decalFits(g, 3.8)) {
                        for (Sprite s : Kit.selfCircle(fx, g, 3.8, 124, fx.cols(), 30, false)) s.follow(ft, 2);
                    }
                    LivingEntity c = fx.caster;
                    fx.vfx.every(0, 10, 12, i -> {
                        if (!c.isValid()) return;
                        Emit.send(fx, c.getLocation().add(0, 0.3, 0), Particle.SCULK_SOUL, null, 3, 1.5, 0.1, 1.5, 0.03, Emit.DETAIL);
                        if (i % 2 == 0) Shapes.spiral(c.getLocation(), 3.5, 0.6, 1.5, 2.5, 14, i, (p, t) ->
                                fx.vfx.after((int) (t * 10), () -> Emit.send(fx, p, Particle.SOUL_FIRE_FLAME, null, 1, 0, 0, 0, 0, Emit.DETAIL)));
                    });
                }));

        m.put("doomsday", Sig.of()
                .cast(fx -> {
                    CastFx.Cols k = fx.cols();
                    LivingEntity c = fx.caster;
                    Supplier<Location> top = () -> c.isValid() ? c.getLocation().add(0, 6.5, 0) : null;
                    List<Sprite> eclipse = new ArrayList<>();
                    eclipse(fx, top.get(), 4.5, 66, k, Sprite.View.HIDE, top, eclipse);
                    if (fx.cp != null) eclipse(fx, Kit.heroSpot(fx, 10, 5), 3.2, 66, k, Sprite.View.ONLY, null, eclipse);
                    fx.memo.put("eclipse", eclipse);
                    Supplier<Location> ft = feet(fx, 0.02);
                    Location g = ft.get();
                    if (g != null && Kit.decalFits(g, 9)) Kit.selfCircle(fx, g, 9, 70, k, 25, true);
                    fx.vfx.every(0, 2, 25, i -> Kit.converge(fx, chest(fx), 9, 3, i % 2 == 0 ? k.a() : k.b(), 12, Emit.NORMAL));
                    // 기 모으는 2.5초가 멈춘 그림이 되지 않게: 일식에서 마법진 가장자리로 보랏빛 번개가 떨어진다
                    fx.vfx.every(6, 7, 7, i -> {
                        Location t0 = top.get();
                        Location gg = ft.get();
                        if (t0 == null || gg == null) return;
                        double a = Kit.rnd().nextDouble(Math.PI * 2);
                        Location hit = Kit.ground(gg.clone().add(Math.cos(a) * 8.5, 1, Math.sin(a) * 8.5)).add(0, 0.1, 0);
                        Location from = t0.clone().add(Math.cos(a) * 2, -2.2, Math.sin(a) * 2);
                        RangedFx.drawBolt(fx, from, hit, 9, 0.6, i % 2 == 0 ? k : k.swap(), 0);
                        Emit.send(fx, hit, Particle.SOUL_FIRE_FLAME, null, 6, 0.3, 0.1, 0.3, 0.05, Emit.DETAIL);
                        if (i % 2 == 0) fx.sound(hit, "entity.lightning_bolt.thunder", 0.25, 1.6);
                    });
                })
                .replace(Ev.Vortex.class)
                .track(Ev.Vortex.class, (fx, e) -> new Track() {
                    int t;

                    @Override
                    public void tick(Location pos, Vector v) {
                        t++;
                        Location c = e.center();
                        for (int arm = 0; arm < 4; arm++) {
                            double f = 1 - ((t * 0.05 + arm / 4.0) % 1);
                            double a = arm * Math.PI / 2 + (1 - f) * 3 + t * 0.12;
                            Emit.send(fx, c.clone().add(Math.cos(a) * e.radius() * f, -0.5, Math.sin(a) * e.radius() * f), Particle.SOUL_FIRE_FLAME, null, 1, 0, 0, 0, 0, Emit.NORMAL);
                        }
                        if (t % 4 == 0) Emit.send(fx, c, Particle.SCULK_SOUL, null, 3, e.radius() * 0.5, 0.2, e.radius() * 0.5, 0.02, Emit.DETAIL);
                    }
                })
                .replace(Ev.Cone.class)
                .on(Ev.Cone.class, (fx, e) -> {
                    int n = fx.seq("dd");
                    Location base = e.base();
                    double r = e.range();
                    CastFx.Cols cyan = rgb(fx, 0x3ae8ff, 0xc8a0ff);
                    CastFx.Cols violet = rgb(fx, 0x7a2aff, 0xffffff);
                    String wide = fx.vfx.models.pick("slash_wide", "slash");
                    if (n == 0) {
                        for (int i = 0; i < 2; i++) {
                            int d = i;
                            fx.vfx.after(d, () -> {
                                Shapes.Frame fr = Shapes.Frame.flat(e.dir()).roll(d == 0 ? 6 : -10).yaw(d * 40);
                                Sprite s = Kit.slash(fx, wide, base.clone().add(0, d * 0.05, 0), fr, r, 9, d == 0 ? cyan : violet).view(Sprite.View.SHOW);
                                s.spin(1, 4, 160);
                                s.go();
                                if (d == 0) Kit.hallmark(fx, s);
                            });
                        }
                        Kit.rimSpray(fx, base, r, fx.n(20), Fx2.SOUL, 0.3, 0.1, Emit.NORMAL);
                        fx.sound(base, "item.mace.smash_air", 1.0, 0.5);
                    } else {
                        double[] tilts = {12, -20, 24};
                        for (int i = 0; i < 3; i++) {
                            int d = i;
                            fx.vfx.after(d, () -> {
                                Shapes.Frame fr = Shapes.Frame.flat(e.dir()).roll(tilts[d]).yaw(d * 120);
                                Sprite s = Kit.slash(fx, d == 0 ? wide : MeleeFx.slashModel(fx, 160, violet), base.clone().add(0, 0.05 * d, 0), fr,
                                        r * (d == 0 ? 1.0 : 0.9), 9, d == 0 ? violet : cyan).view(Sprite.View.SHOW);
                                s.spin(1, 4, 140);
                                s.go();
                            });
                        }
                        @SuppressWarnings("unchecked")
                        List<Sprite> ec = (List<Sprite>) fx.memo.get("eclipse");
                        if (ec != null) Pieces.collapse(ec);
                        Location g = AreaFx.groundAt(base);
                        Pieces.shockwave(fx, g, r + 1, 5, new CastFx.Cols[]{cyan, violet}, 2, false);
                        Kit.debris(fx, g, 10, 1.3, Material.CRYING_OBSIDIAN);
                        Emit.flash(fx, base.clone().add(0, 3, 0));
                        Kit.afterglow(fx, g, 5, 40, violet);
                    }
                }));

        // ── 창세의 지팡이 (흰 금빛 + 초록) ──
        m.put("genesis", Sig.of()
                .cast(fx -> {
                    Location g = Kit.ground(fx.caster.getLocation()).add(0, 0.02, 0);
                    if (Kit.decalFits(g, 9)) Kit.selfCircle(fx, g, 9, 30, rainbow(fx), 40, false);
                    Kit.pillar(fx, g, 1.4, 8, 18, rgb(fx, 0xffe8a0, 0xffffff)).go();
                })
                .replace(Ev.Nova.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    Location c = e.center();
                    Location g = AreaFx.groundAt(c);
                    double r = e.radius();
                    int ex = Math.max(3, e.expand());
                    Pieces.shockwave(fx, g, r, ex, new CastFx.Cols[]{rgb(fx, 0xffd86a, 0xffffff), rainbow(fx)}, 2, false);
                    fx.vfx.every(0, 1, ex, i -> {
                        double rr = r * (i + 1) / ex;
                        for (Location p : Shapes.around(c, rr, fx.n(10), i * 0.3))
                            Emit.dir(fx, p, Particle.END_ROD, null, new Vector(0, 1, 0), 0.2, Emit.DETAIL);
                    });
                    fx.vfx.after(ex, () -> Kit.flowers(fx, g, r, 8, 40));
                }));

        m.put("time_stop", Sig.of()
                .replace(Ev.Nova.class, Ev.Hit.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    Location c = e.center();
                    Location g = AreaFx.groundAt(c).add(0, 0.02, 0);
                    // 시계가 기절 시간(4초) 동안 남는다: 처음엔 바늘이 거꾸로 돌고 멈춘다
                    if (Kit.decalFits(g, 6)) Pieces.clock(fx, g, 6, 80);
                    CastFx.Cols mono = rgb(fx, 0xffffff, 0xdfe8ff);
                    Kit.shock(fx, g.clone().add(0, 0.01, 0), 0.5, e.radius(), Math.max(3, e.expand()), Math.max(3, e.expand()) + 6, mono).go();
                    fx.sound(c, "block.bell.resonate", 1.0, 0.8);
                    fx.vfx.every(4, 2, 10, i -> fx.sound(c, "block.note_block.hat", 0.6, 1.4 - i * 0.05));
                })
                .on(Ev.Hit.class, (fx, e) -> {
                    if (e.tick()) return;
                    LivingEntity t = e.target();
                    Supplier<Location> mid = () -> t.isValid() ? t.getLocation().add(0, t.getHeight() * 0.5, 0) : null;
                    Location m0 = mid.get();
                    if (m0 == null) return;
                    double rr = Math.max(0.8, t.getWidth() * 0.8 + 0.3);
                    Sprite ring = Kit.flat(fx, "ring", m0, rr, Shapes.Frame.FLAT, rgb(fx, 0xdfe8ff, 0xffffff)).life(80).follow(mid, 2);
                    ring.decal = false;
                    Kit.spinOver(ring, 1, 78, -30);
                    ring.fallback(() -> Kit.dustRing(fx, m0, rr, Color.WHITE, 1.0, Emit.NORMAL));
                    ring.go();
                    // 멈춘 시간: 제자리에 떠 있는 빛 점들
                    fx.vfx.every(0, 10, 8, i -> {
                        Location l = mid.get();
                        if (l == null) return;
                        Emit.send(fx, l, Particle.END_ROD, null, 4, rr * 0.6, t.getHeight() * 0.4, rr * 0.6, 0, Emit.DETAIL);
                    });
                }));

        m.put("world_creation", Sig.of()
                .replace(Ev.Vortex.class)
                .track(Ev.Vortex.class, (fx, e) -> {
                    Location c = e.center();
                    Location g = AreaFx.groundAt(c).add(0, 0.02, 0);
                    int dur = e.duration();
                    List<Sprite> parts = new ArrayList<>();
                    // 창세는 금빛·초록 (무지개 마법진은 칠색 분광의 것)
                    CastFx.Cols gg = rgb(fx, 0xffc84a, 0xd8ffb0);
                    if (Kit.decalFits(g, 8)) for (Sprite s : Kit.circle(fx, g, 8, dur + 14, gg, 40, true, Sprite.View.AUTO)) if (s != null) parts.add(s);
                    for (Location p : Shapes.around(g, 8, 4, 0)) {
                        Kit.pillar(fx, Kit.ground(p.clone().add(0, 0.5, 0)), 1.8, 9, dur + 4, rgb(fx, 0xffe8a0, 0xffffff)).go();
                    }
                    Location top = c.clone().add(0, 6, 0);
                    // 모여드는 빛으로 자라는 하늘의 별 (빛살·후광이 돌며 맥박 친다)
                    Pieces.bigStar(fx, top, 3.4, dur + 8, rainbow(fx), Sprite.View.AUTO, Math.max(4, dur));
                    return new Track() {
                        int t;

                        @Override
                        public void tick(Location pos, Vector v) {
                            t++;
                            if (t % 2 == 0) {
                                for (int i = 0; i < 4; i++) {
                                    double a = Kit.rnd().nextDouble(Math.PI * 2);
                                    Location from = g.clone().add(Math.cos(a) * 8, 0.3, Math.sin(a) * 8);
                                    Emit.trail(fx, from, top, Palette.hue(Kit.rnd().nextDouble()), 14, Emit.NORMAL);
                                }
                            }
                        }

                        @Override
                        public void end(Location at, boolean impact) {
                            for (Sprite s : parts) s.finish(4);
                        }
                    };
                })
                .replace(Ev.Strike.class)
                .on(Ev.Strike.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.point().clone().add(0, 0.5, 0));
                    Pieces.lightPillar(fx, g, 3.5, 16, 12, rgb(fx, 0xffd86a, 0xfff6c8), true);
                    Emit.flash(fx, g.clone().add(0, 4, 0));
                    fx.sound(g, "block.beacon.power_select", 1.2, 0.7);
                })
                .replace(Ev.Nova.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.center());
                    Pieces.shockwave(fx, g, e.radius(), Math.max(3, e.expand()), new CastFx.Cols[]{rgb(fx, 0xfff6c8, 0xffffff), rgb(fx, 0x7cff8c, 0xe0ffe0)}, 2, false);
                    // 멈춘 시간의 흰 고리 (기절 2.5초 동안)
                    Kit.ring(fx, g.clone().add(0, 0.045, 0), e.radius(), e.radius(), 1, 50, rgb(fx, 0x9fd4ff, 0xffffff), fx.vfx.models.pick("ring_dim", "ring")).go();
                    Kit.debris(fx, g, 8, 1.2, Material.QUARTZ_BLOCK);
                })
                .track(Ev.Drop.class, (fx, e) -> {
                    Location[] at = {e.start().clone()};
                    double h = Kit.rnd().nextDouble();
                    Sprite sp = Sprite.item(fx, fx.vfx.models.pick("spark", "star", "orb"), e.start()).size(0.8).radius(0.5).life(60)
                            .tint(Palette.hue(h), WHITE, fx.dark()).follow(() -> at[0], 1).end(Sprite.End.SHRINK, 2);
                    sp.hue(3, h);
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

        // ── 뇌신의 망치 (번개: 노랑 + 청록) ──
        // 마법진은 '곧 무언가 온다'는 뜻이라 맞은 뒤에는 쓰지 않는다: 낙뢰 자리에 빛나는 전기 균열과 빛 장막
        m.put("thunder_god", Sig.of()
                .on(Ev.Strike.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.point().clone().add(0, 0.5, 0)).add(0, 0.02, 0);
                    Kit.cracks(fx, g, 3, 6, fx.pal.a(), Particle.ELECTRIC_SPARK);
                    AreaFx.ringWall(fx, g, 2.4, 3, fx.cols());
                }));

        m.put("thunderstorm", Sig.of()
                .cast(fx -> {
                    LivingEntity c = fx.caster;
                    Supplier<Location> top = () -> c.isValid() ? c.getLocation().add(0, 9, 0) : null;
                    Pieces.stormCloud(fx, top.get(), 8, 136, top);
                    fx.sound(c.getLocation(), "entity.lightning_bolt.thunder", 0.4, 0.8);
                }));

        m.put("thunder_wrath", Sig.of()
                .on(Ev.Buff.class, (fx, e) -> {
                    LivingEntity c = fx.caster;
                    fx.vfx.every(0, 1, 20, i -> {
                        if (!c.isValid()) return;
                        for (int s = 0; s < 2; s++) {
                            double a = i * 0.6 + Math.PI * s;
                            Emit.send(fx, c.getLocation().add(Math.cos(a) * 0.9, (i % 10) * 0.2, Math.sin(a) * 0.9), Particle.ELECTRIC_SPARK, null, 1, 0, 0, 0, 0, Emit.NORMAL);
                        }
                    });
                    Pieces.halo(fx, 1.1, 120, fx.cols());
                })
                .replace(Ev.Vortex.class)
                .track(Ev.Vortex.class, (fx, e) -> {
                    Location c = e.center();
                    Location g = AreaFx.groundAt(c).add(0, 0.02, 0);
                    int dur = e.duration();
                    Location cloud = g.clone().add(0, 10, 0);
                    List<Sprite> parts = new ArrayList<>(Pieces.stormCloud(fx, cloud, 8, dur + 100, null));
                    if (Kit.decalFits(g, 8)) for (Sprite s : Kit.circle(fx, g, 8, dur + 10, fx.cols(), 60, true, Sprite.View.AUTO)) if (s != null) parts.add(s);
                    fx.memo.put("cloud", cloud);
                    return new Track() {
                        int t;

                        @Override
                        public void tick(Location pos, Vector v) {
                            t++;
                            if (t % 3 == 0) {
                                double a = Kit.rnd().nextDouble(Math.PI * 2), d = Kit.rnd().nextDouble(1, 7.5);
                                Location to = Kit.ground(g.clone().add(Math.cos(a) * d, 2, Math.sin(a) * d));
                                Location from = cloud.clone().add(Kit.rnd().nextDouble(-3, 3), 0, Kit.rnd().nextDouble(-3, 3));
                                Pieces.cloudBolt(fx, from, to, fx.cols());
                            }
                            if (t % 6 == 0) fx.sound(c, "block.respawn_anchor.charge", 0.5, 0.6 + t / (double) Math.max(1, dur));
                        }
                    };
                })
                .on(Ev.Strike.class, (fx, e) -> {
                    int n = fx.seq("tw");
                    if (n != 0) return;
                    Location g = AreaFx.groundAt(e.point().clone().add(0, 0.5, 0));
                    CastFx.Cols cyan = rgb(fx, 0x5ae8ff, 0xffffff);
                    Pieces.lightPillar(fx, g, 4.5, 16, 8, cyan, false);
                    Emit.flash(fx, g.clone().add(0, 4, 0));
                    Kit.star(fx, g.clone().add(0, 2, 0), 6, 6, fx.cols()).go();
                    Pieces.shockwave(fx, g, 8, 8, new CastFx.Cols[]{fx.cols(), cyan, fx.cols()}, 2, false);
                    Kit.debris(fx, g, 12, 1.4, Material.STONE);
                    Kit.cracks(fx, g, 7, 10, fx.pal.a(), Particle.ELECTRIC_SPARK);
                    Pieces.heroStar(fx, 8, 3, 3, 6, fx.cols());
                }));

        // ── 태양검 (태양: 금빛 + 주황) ──
        m.put("solar_flare", Sig.of()
                .replace(Ev.Beam.class)
                .on(Ev.Beam.class, (fx, e) -> {
                    CastFx.Cols[] layers = {rgb(fx, 0xffffff, 0xfff6c8), rgb(fx, 0xffc030, 0xfff3a0), rgb(fx, 0xff6a10, 0xffb347)};
                    layeredBeam(fx, e, layers, 4, false, "beam", 2.0, false);
                    Shapes.Frame fr = Shapes.Frame.along(e.dir());
                    double len = e.start().distance(e.end());
                    for (double t = 1.5; t < len; t += 0.5) {
                        double a = t * 1.6;
                        Emit.send(fx, fr.point(e.start(), Math.cos(a) * 0.9, Math.sin(a) * 0.9, t), Particle.FLAME, null, 1, 0, 0, 0, 0, Emit.DETAIL);
                    }
                    Pieces.sun(fx, e.end(), 3, 8, rgb(fx, 0xffb020, 0xfff3a0), Sprite.View.AUTO);
                    Location g = Kit.groundOrNull(e.end());
                    if (g != null && e.end().getY() - g.getY() < 2.5) Pieces.fireSheets(fx, g, 2.2, 4, 2.5, 12, fx.cols());
                }));

        m.put("sunfall", Sig.of()
                .track(Ev.Drop.class, (fx, e) -> {
                    Location[] at = {e.start().clone()};
                    int fall = (int) Math.ceil(Math.abs(e.start().getY() - e.ground().getY()) / Math.max(0.2, Math.abs(e.vel().getY())));
                    Sprite sun = Pieces.sun(fx, e.start(), 4.5, fall + 4, rgb(fx, 0xffb020, 0xfff3a0), Sprite.View.AUTO, () -> at[0]);
                    return new Track() {
                        @Override
                        public void tick(Location pos, Vector vel) {
                            at[0] = pos.clone();
                        }

                        @Override
                        public void end(Location a, boolean impact) {
                            sun.finish(2);
                            if (sun.memo != null) sun.memo.finish(2);
                            Pieces.heroStar(fx, 8, 3, 3, 6, fx.cols());
                        }
                    };
                }));

        m.put("supernova", Sig.of()
                .cast(fx -> {
                    LivingEntity c = fx.caster;
                    Supplier<Location> head = () -> c.isValid() ? c.getLocation().add(0, c.getHeight() + 1.8, 0) : null;
                    CastFx.Cols k = rgb(fx, 0xffb020, 0xfff3a0);
                    Sprite sun = Pieces.sun(fx, head.get(), 3, 82, k, Sprite.View.HIDE, head);
                    BuffFx.gyroscope(fx, c, 1.3, 80, k, Sprite.View.HIDE);
                    Pieces.halo(fx, 1.3, 80, k);
                    // 터지기 1초 전: 빛이 모이고 태양이 작고 하얗게 된다
                    fx.vfx.after(60, () -> {
                        sun.key(sun.age + 1, 16, sp -> sp.sc.mul(0.3f));
                        sun.retint(sun.age + 1, Color.WHITE, Color.WHITE, fx.dark());
                        fx.sound(c.getLocation(), "block.respawn_anchor.charge", 1.0, 0.7);
                    });
                    fx.vfx.every(60, 2, 10, i -> Kit.converge(fx, chest(fx), 9, 6, i % 2 == 0 ? k.a() : Color.WHITE, 8, Emit.NORMAL));
                })
                .track(Ev.Orbit.class, (fx, e) -> {
                    Location[] cur = new Location[e.count()];
                    Location[] prev = new Location[e.count()];
                    List<Sprite> suns = new ArrayList<>();
                    for (int i = 0; i < e.count(); i++) {
                        int idx = i;
                        cur[i] = fx.caster.getLocation().add(0, e.y(), 0);
                        // 시전자 바로 앞을 지나가므로 코로나 고리 없이 작게
                        suns.add(Pieces.sun(fx, cur[i], 1.0, e.duration() + 2, fx.cols(), Sprite.View.HIDE, () -> cur[idx], false));
                    }
                    return new Track() {
                        @Override
                        public void point(int i, Location p) {
                            if (i >= cur.length) return;
                            cur[i] = p.clone();
                            if (prev[i] != null) Emit.streak(fx, prev[i], p, fx.pal.a(), 2, 4, Emit.NORMAL);
                            Emit.send(fx, p, Particle.FLAME, null, 1, 0.1, 0.1, 0.1, 0.01, Emit.DETAIL);
                            prev[i] = p.clone();
                        }

                        @Override
                        public void end(Location at, boolean impact) {
                            for (Sprite s : suns) {
                                s.finish(2);
                                if (s.memo != null) s.memo.finish(2);
                            }
                        }
                    };
                })
                .replace(Ev.Nova.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    Location c = e.center();
                    Location g = AreaFx.groundAt(c);
                    Emit.flash(fx, c.clone().add(0, 3, 0));
                    Pieces.bigStar(fx, c.clone().add(0, 2.0, 0), 7, 14, rgb(fx, 0xfff3a0, 0xffffff), Sprite.View.HIDE, 3);
                    Pieces.heroStar(fx, 8, 3.5, 4, 8, rgb(fx, 0xfff3a0, 0xffffff));
                    CastFx.Cols[] layers = {rgb(fx, 0xffffff, 0xfff6c8), rgb(fx, 0xffe84d, 0xffffff), rgb(fx, 0xff8a1a, 0xffd35c), rgb(fx, 0xff2a1a, 0xff9a5a)};
                    Pieces.shockwave(fx, g, e.radius() * 1.04, Math.max(3, e.expand()), layers, 2, false);
                    Pieces.fireSheets(fx, g, 6, 12, 3.5, 16, fx.cols());
                    Kit.debris(fx, g, 12, 1.4, Material.MAGMA_BLOCK);
                    Pieces.rays(fx, c.clone().add(0, 1, 0), Math.min(40, fx.n(22)), 9, rgb(fx, 0xff8a1a, 0xffe84d), 10, false);
                    Shapes.sphere(c.clone().add(0, 1, 0), 1, fx.n(14), (p, t) -> {
                        Vector d = p.toVector().subtract(c.clone().add(0, 1, 0).toVector());
                        Emit.dir(fx, c.clone().add(0, 1, 0), Particle.FLAME, null, d, 0.5, Emit.NORMAL);
                    });
                    Kit.afterglow(fx, g, 5, 40, fx.cols());
                }));

        // ── 프리즘 활 ──
        m.put("starfall_volley", Sig.of()
                .track(Ev.Drop.class, (fx, e) -> {
                    Location[] at = {e.start().clone()};
                    double h = Kit.rnd().nextDouble();
                    Sprite sp = Sprite.item(fx, fx.vfx.models.pick("spark", "star", "orb"), e.start()).size(0.7).radius(0.5).life(60)
                            .tint(Palette.hue(h), WHITE, fx.dark()).follow(() -> at[0], 1).end(Sprite.End.SHRINK, 2);
                    sp.go();
                    return new Track() {
                        @Override
                        public void tick(Location pos, Vector vel) {
                            at[0] = pos.clone();
                        }

                        @Override
                        public void end(Location a, boolean impact) {
                            sp.finish(2);
                            Kit.star(fx, a.clone().add(0, 0.8, 0), 1.2, 4, hue(fx, h)).go();
                        }
                    };
                }));

        m.put("rainbow_piercer", Sig.of()
                .replace(Ev.Beam.class)
                .on(Ev.Beam.class, (fx, e) -> {
                    CastFx.Cols[] layers = {rgb(fx, 0xffffff, 0xffffff), rainbow(fx), hue(fx, 0.55)};
                    layeredBeam(fx, e, layers, 6, true, "beam_rainbow", 2.0, true);
                    // 무지개 끝으로 달려가는 빛 머리
                    Vector dir = e.dir().clone().normalize();
                    Location s0 = e.start().clone().add(dir.clone().multiply(2.5));
                    Sprite head = Sprite.item(fx, fx.vfx.models.pick("spark", "star", "orb"), s0).size(1.2).radius(0.6).life(8)
                            .tint(WHITE, WHITE, fx.dark()).end(Sprite.End.SHRINK, 2);
                    head.followEvery = 4;
                    head.at(1, sp -> sp.e.teleport(AreaFx.flat(e.end())));
                    head.go();
                }));
    }

    /** 일식: 검은 핵 + 둘레 고리 두 겹 (청록·보라) */
    static void eclipse(CastFx fx, Location at, double size, int life, CastFx.Cols k, Sprite.View view, Supplier<Location> follow, List<Sprite> out) {
        if (at == null) return;
        Sprite core = Kit.orb(fx, at, size * 0.2, life, k, fx.vfx.models.pick("void_orb", "orb")).view(view);
        core.scaleTo(1, 8, size / (2 * Geo.ORB_HALF));
        if (follow != null) core.follow(follow, 1);
        core.go();
        out.add(core);
        for (int i = 0; i < 2; i++) {
            double rr = size * (0.62 + 0.18 * i);
            Sprite ring = Sprite.item(fx, i == 0 ? "ring" : fx.vfx.models.pick("ring_dim", "ring"), at).frame(Shapes.Frame.FLAT.pitch(-90))
                    .size(0.1).radius(rr).life(life).tint(i == 0 ? k : k.swap()).view(view).bill(org.bukkit.entity.Display.Billboard.CENTER);
            ring.scaleTo(1, 8, rr / Geo.FLAT_HALF, 1, rr / Geo.FLAT_HALF);
            if (follow != null) ring.follow(follow, 1);
            ring.go();
            out.add(ring);
        }
    }
}
