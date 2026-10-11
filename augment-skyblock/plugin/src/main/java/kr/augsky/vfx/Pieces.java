package kr.augsky.vfx;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextColor;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.entity.Display;
import org.bukkit.entity.LivingEntity;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;

/** 큰 연출 조각 모음 (프리즘·보스 전용 연출이 쓴다). 조각이 거절되면 입자로 대신한다 */
final class Pieces {
    private Pieces() {}

    // ------------------------------------------------------------------ 빛기둥 · 별 · 충격파

    /** 빛기둥 + 꼭대기 별 + 바닥 고리. descend 면 하늘에서 내려꽂힌다 */
    static Sprite lightPillar(CastFx fx, Location base, double w, double h, int life, CastFx.Cols k, boolean descend) {
        Location g = base.clone();
        Sprite p = Kit.pillar(fx, g, w, h, life, k);
        if (descend) {
            p.offset(0, h, 0);
            p.key(1, 3, sp -> {
                sp.tr.y = 0;
                sp.sc.y = (float) h;
            });
        }
        p.go();
        Kit.hallmark(fx, p);
        Kit.star(fx, g.clone().add(0, h, 0), Math.min(2.5, w * 1.2), Math.min(8, life), k).go();
        Kit.ring(fx, g.clone().add(0, 0.04, 0), w * 0.4, w * 1.4, 3, Math.min(life, 12), k, null).go();
        return p;
    }

    /** 별 터짐: 별 조각 + 사방으로 뻗는 빛줄기 */
    static void starburst(CastFx fx, Location at, double size, int life, CastFx.Cols k, int spray) {
        Kit.star(fx, at, size, life, k).go();
        rays(fx, at, Math.min(40, fx.n(spray)), 2.5 + size * 0.8, k, 8, false);
    }

    /**
     * 빛줄기 터짐. END_ROD·FIREWORK 를 뿜으면 3초 가까이 바닥에 흰 점으로 남으므로,
     * 정해진 틱 뒤 정확히 사라지는 TRAIL 로 그린다 (한 줄기 = 출발점을 엇갈린 점 3개).
     */
    static void rays(CastFx fx, Location at, int n, double len, CastFx.Cols k, int dur, boolean upOnly) {
        List<Vector> dirs = upOnly ? Shapes.hemisphere(n) : sphereDirs(n);
        int i = 0;
        for (Vector d : dirs) {
            Color c = k.rainbow() ? Palette.hue(i / (double) n) : (i % 3 == 0 ? Color.WHITE : i % 3 == 1 ? k.b() : k.a());
            double l = len * (0.7 + 0.3 * Kit.rnd().nextDouble());
            Location from = at.clone().add(d.clone().multiply(0.3));
            Emit.streak(fx, from, at.clone().add(d.clone().multiply(l)), c, 3, dur, Emit.NORMAL);
            i++;
        }
    }

    static List<Vector> sphereDirs(int n) {
        List<Vector> out = new ArrayList<>();
        Shapes.sphere(new Location(null, 0, 0, 0), 1, n, (p, t) -> out.add(new Vector(p.getX(), p.getY(), p.getZ())));
        return out;
    }

    /** 여러 겹 충격파: 색을 바꿔 가며 stagger 틱 간격으로 퍼진다. exact 면 r 에서 멈춘다 (몬스터) */
    static void shockwave(CastFx fx, Location g, double r, int expand, CastFx.Cols[] layers, int stagger, boolean exact) {
        for (int i = 0; i < layers.length; i++) {
            CastFx.Cols k = layers[i];
            int d = i * stagger;
            double rr = exact ? r : r * (1 + 0.04 * i);
            int idx = i;
            fx.vfx.after(d, () -> {
                Sprite s = idx % 2 == 0 ? Kit.ring(fx, g.clone().add(0, 0.03 + idx * 0.02, 0), rr * 0.12, rr, expand, expand + 5, k, null)
                        : Kit.shock(fx, g.clone().add(0, 0.03 + idx * 0.02, 0), rr * 0.12, rr, expand, expand + 5, k);
                if (exact) s.end(Sprite.End.NONE);
                s.go();
                if (idx == 0) Kit.hallmark(fx, s);
                if (idx == 0) {
                    fx.vfx.every(0, 1, Math.max(1, expand), t -> Kit.rimSpray(fx, g, rr * (t + 1) / Math.max(1, expand), fx.n(10), fx.pal.spark(), 0.2, 0.15, Emit.DETAIL));
                }
            });
        }
    }

    // ------------------------------------------------------------------ 거대 참격

    /**
     * 거대 참격: 한 장을 크게 돌리지 않고(보간이 반대로 돌 수 있다) 조금씩 돌린 초승달을 1틱 간격으로 이어 띄운다.
     * c 중심, dir 앞, r 반지름, tilt 기울기, sweep 휘두르는 각도
     */
    static void giantSlash(CastFx fx, Location c, Vector dir, double r, double tilt, double sweepDeg, int life, CastFx.Cols k,
                           boolean wide, Sprite.View view) {
        String model = wide ? fx.vfx.models.pick("slash_wide", "slash") : MeleeFx.slashModel(fx, 160, k);
        int n = Math.max(1, (int) Math.ceil(sweepDeg / 70.0));
        int side = tilt >= 0 ? 1 : -1;
        Shapes.Frame base = Shapes.Frame.flat(dir).roll(tilt);
        for (int i = 0; i < n; i++) {
            double yaw = -sweepDeg / 2 + sweepDeg * (i + 0.5) / n;
            int d = i;
            fx.vfx.after(d, () -> {
                // 시전자에게는 기울지 않고 낮춘 판 (1인칭에서 화면을 가르는 선이 되지 않게)
                boolean split = view == Sprite.View.SHOW && fx.cp != null;
                for (int pass = 0; pass < (split ? 2 : 1); pass++) {
                    boolean mine = split && pass == 1;
                    Shapes.Frame fr = mine ? Shapes.Frame.flat(dir).yaw(yaw * side).pitch(8) : base.yaw(yaw * side);
                    Location at = mine ? MeleeFx.selfBase(fx, c, r) : c;
                    Sprite.View v = split ? (mine ? Sprite.View.ONLY : Sprite.View.HIDE) : view;
                    Sprite s = Kit.slash(fx, model, at, fr, r, life, d == n - 1 ? k : k.swap()).view(v).slashDir(side);
                    s.size(r / Geo.FLAT_HALF * 0.9, 1, r / Geo.FLAT_HALF * 0.9);
                    s.key(1, 2, sp -> {
                        sp.rot.rotateY((float) Math.toRadians(20 * side));
                        sp.sc.set((float) (r / Geo.FLAT_HALF), 1f, (float) (r / Geo.FLAT_HALF));
                    });
                    s.go();
                    if (d == n - 1 && !mine) Kit.hallmark(fx, s);
                }
            });
        }
    }

    // ------------------------------------------------------------------ 운석

    /** 하나만 떨어지는 큰 낙하 (운석·태양 강림): 떨어지는 동안 땅의 마법진이 자라고, 닿으면 크게 터진다 */
    static Track meteor(CastFx fx, Ev.Drop ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        if (Palette.yamlColors(ev.yaml()) == null) k = fx.cols();
        CastFx.Cols kk = k;
        Location ground = ev.ground().clone().add(0, 0.03, 0);
        double ir = ev.impactRadius();
        int fall = (int) Math.ceil(Math.abs(ev.start().getY() - ground.getY()) / Math.max(0.2, Math.abs(ev.vel().getY())));
        List<Sprite> parts = new ArrayList<>();
        if (Kit.decalFits(ground, ir)) {
            Sprite[] cs = Kit.circle(fx, ground, ir, fall + 4, k, 60, true, Sprite.View.AUTO);
            for (Sprite s : cs) if (s != null) parts.add(s);
        }
        Location[] at = {ev.start().clone()};
        Sprite glow = Kit.orb(fx, ev.start(), 1.0, fall + 6, k, null).follow(() -> at[0], 1);
        glow.scaleTo(1, Math.max(2, fall), 3.2);
        glow.go();
        String fm = fx.vfx.models.pick("flame");
        return new Track() {
            Location prev = ev.start().clone();
            int t;

            @Override
            public void tick(Location pos, Vector vel) {
                t++;
                at[0] = pos.clone();
                Emit.streak(fx, prev, pos, kk.a(), 3, 4, Emit.NORMAL);
                Emit.send(fx, pos, Particle.FLAME, null, 4, 0.5, 0.5, 0.5, 0.02, Emit.NORMAL);
                Emit.send(fx, pos, Particle.LARGE_SMOKE, null, 2, 0.6, 0.6, 0.6, 0.01, Emit.DETAIL);
                if (t % 4 == 0) {
                    // 열기 고리가 운석을 감싸고 뒤로 흩어진다
                    Shapes.ring(pos, 1.6, 14, Shapes.Frame.normal(vel), (p, s) -> Emit.dust(fx, p, kk.b(), 1.0, Emit.DETAIL));
                }
                prev = pos.clone();
            }

            @Override
            public void end(Location hit, boolean impact) {
                glow.finish(2);
                for (Sprite s : parts) s.finish(3);
                Location g = Kit.ground(hit).add(0, 0.03, 0);
                boolean big = fx.ult();
                starburst(fx, g.clone().add(0, 1.5, 0), big ? 5 : 3.5, 6, kk, big ? 40 : 24);
                shockwave(fx, g, ir, 5, new CastFx.Cols[]{kk, kk.swap(), kk}, 2, false);
                fireSheets(fx, g, ir * 0.85, 6, 3.0, 14, kk);
                Kit.debris(fx, g, big ? 12 : 8, 1.3, fx.pal.debris().length > 0 ? fx.pal.debris()[0] : Material.MAGMA_BLOCK);
                Emit.flash(fx, g.clone().add(0, 2, 0));
                Kit.afterglow(fx, g, ir * 0.7, 40, kk);
                fx.vfx.every(2, 3, 7, i -> {
                    for (int j = 0; j < 6; j++) {
                        double a = Kit.rnd().nextDouble(Math.PI * 2), d = Math.sqrt(Kit.rnd().nextDouble()) * ir;
                        Emit.send(fx, g.clone().add(Math.cos(a) * d, 0.2, Math.sin(a) * d), Particle.FLAME, null, 1, 0.1, 0.1, 0.1, 0.03, Emit.DETAIL);
                    }
                    Emit.send(fx, g.clone().add(0, 0.5, 0), Particle.LAVA, null, 2, ir * 0.4, 0.1, ir * 0.4, 0, Emit.DETAIL);
                });
                fx.impactSounds(g);
                fx.sound(g, "entity.generic.explode", 1.2, 0.6);
            }
        };
    }

    /** 불꽃 혀 (flame 모델, 세로). 없으면 FLAME 입자 기둥 */
    static void fireSheets(CastFx fx, Location c, double r, int n, double h, int life, CastFx.Cols k) {
        boolean has = fx.vfx.models.has("flame");
        for (Location p : Shapes.around(c, r, n, Kit.rnd().nextDouble(Math.PI))) {
            Location g = Kit.ground(p.clone().add(0, 0.5, 0));
            if (has) {
                Sprite s = Sprite.item(fx, "flame", g).size(0.6, 0.1, 1).radius(0.6).life(life).tint(k).end(Sprite.End.THIN, 4);
                s.key(1, 3, sp -> sp.sc.set((float) Math.max(0.9, h * 0.4), (float) h, 1f));
                s.fallback(() -> Emit.send(fx, g.clone().add(0, h * 0.4, 0), Particle.FLAME, null, 10, 0.15, h * 0.3, 0.15, 0.02, Emit.NORMAL));
                s.go();
            } else {
                fx.vfx.every(0, 2, Math.max(1, life / 3), i -> Emit.send(fx, g.clone().add(0, h * 0.4, 0), Particle.FLAME, null, 8, 0.15, h * 0.3, 0.15, 0.02, Emit.NORMAL));
            }
        }
    }

    // ------------------------------------------------------------------ 해·달·블랙홀

    static Sprite sun(CastFx fx, Location at, double size, int life, CastFx.Cols k, Sprite.View view) {
        return sun(fx, at, size, life, k, view, null);
    }

    /** 태양: 원반 + 돌아가는 코로나 고리. follow 가 있으면 둘 다 따라간다 */
    static Sprite sun(CastFx fx, Location at, double size, int life, CastFx.Cols k, Sprite.View view, Supplier<Location> follow) {
        return sun(fx, at, size, life, k, view, follow, true);
    }

    static Sprite sun(CastFx fx, Location at, double size, int life, CastFx.Cols k, Sprite.View view, Supplier<Location> follow,
                      boolean corona) {
        String m = fx.vfx.models.pick("sun", "orb");
        double s = "sun".equals(m) ? size / (2 * Geo.SUN_HALF) : size / (2 * Geo.ORB_HALF);
        Sprite sp = Sprite.item(fx, m, at).size(s * 0.3).radius(size / 2).life(life).tint(k).view(view).end(Sprite.End.SHRINK, 4);
        sp.scaleTo(1, 4, s);
        sp.fallback(() -> {
            int a = fx.aud;
            fx.vfx.every(0, 3, Math.max(1, life / 3), i -> fx.with(a, () -> {
                Shapes.sphere(at, size * 0.4, 18, (p, t) -> Emit.send(fx, p, Particle.FLAME, null, 1, 0, 0, 0, 0, Emit.NORMAL));
                Emit.send(fx, at, Particle.END_ROD, null, 4, size * 0.3, size * 0.3, size * 0.3, 0.02, Emit.DETAIL);
            }));
        });
        if (follow != null) sp.follow(follow, 1);
        sp.go();
        if (corona && fx.vfx.models.has("ring")) {
            Sprite cor = Sprite.item(fx, "ring", at).frame(Shapes.Frame.FLAT.pitch(-90)).size(0.1).radius(size * 0.7).life(life).tint(k.swap()).view(view);
            if (follow != null) cor.follow(follow, 1);
            sp.memo = cor;
            cor.bill(Display.Billboard.CENTER);
            cor.decal = false;
            cor.scaleTo(1, 4, size * 0.75 / Geo.FLAT_HALF, 1, size * 0.75 / Geo.FLAT_HALF);
            cor.spinAxis(5, Math.max(2, life - 8), 180, new Vector3f(0, 1, 0));
            cor.go();
        }
        return sp;
    }

    static Sprite moon(CastFx fx, Location at, double size, int life, CastFx.Cols k, Sprite.View view) {
        String m = fx.vfx.models.pick("moon", "orb");
        double s = "moon".equals(m) ? size / (2 * Geo.SUN_HALF) : size / (2 * Geo.ORB_HALF);
        Sprite sp = Sprite.item(fx, m, at).size(s * 0.4).radius(size / 2).life(life).tint(k).view(view).end(Sprite.End.FADE, 4);
        sp.scaleTo(1, 5, s);
        sp.fallback(() -> Shapes.sphere(at, size * 0.45, 24, (p, t) -> Emit.dust(fx, p, k.a(), 1.6, Emit.NORMAL)));
        sp.go();
        return sp;
    }

    /** 블랙홀: 검은 핵 + 기울어진 소용돌이 + 렌즈 고리. collapse 로 무너진다 */
    static List<Sprite> blackHole(CastFx fx, Location c, double r, int life) {
        CastFx.Cols k = new CastFx.Cols(Color.fromRGB(0x9a3aff), Color.fromRGB(0xe6b0ff), Color.fromRGB(0x14001e), Color.fromRGB(0x9a3aff), false);
        List<Sprite> out = new ArrayList<>();
        // 끌려온 적들 머리 위에 떠 있어야 몸에 가려지지 않는다
        Location core = c.clone().add(0, 2.8, 0);
        Sprite o = Kit.orb(fx, core, 0.8, life, k, fx.vfx.models.pick("void_orb", "orb"));
        o.scaleTo(1, Math.max(2, life - 4), Math.max(2.4, r * 0.45) / Geo.ORB_HALF * 0.5);
        o.go();
        out.add(o);
        String sm = fx.vfx.models.pick("swirl", "ring");
        if (sm != null) {
            // 옆에서 봐도 소용돌이 팔이 보이게 크게 기울인다
            Sprite sw = Kit.flat(fx, sm, core, 0.5, Shapes.Frame.FLAT.roll(38).pitch(14), k).life(life);
            sw.decal = false;
            sw.scaleTo(1, 5, r * 0.8 / Geo.FLAT_HALF, 1, r * 0.8 / Geo.FLAT_HALF);
            Kit.spinOver(sw, 6, life - 6, -240);
            sw.go();
            out.add(sw);
        }
        Sprite lens = Sprite.item(fx, fx.vfx.models.pick("ring_dim", "ring"), core).frame(Shapes.Frame.FLAT.pitch(-90)).size(0.1).radius(1.6)
                .life(life).tint(k.swap()).bill(Display.Billboard.CENTER);
        double lr = Math.max(2.4, r * 0.45) * 0.9;
        lens.scaleTo(1, Math.max(2, life - 4), lr / Geo.FLAT_HALF, 1, lr / Geo.FLAT_HALF);
        lens.go();
        out.add(lens);
        fx.vfx.every(0, 2, life / 2, i -> {
            for (int j = 0; j < 4; j++) {
                double a = Kit.rnd().nextDouble(Math.PI * 2);
                Location from = core.clone().add(Math.cos(a) * r, Kit.rnd().nextDouble(-1, 2), Math.sin(a) * r);
                Emit.trail(fx, from, core, j % 2 == 0 ? k.a() : k.b(), 12, Emit.NORMAL);
            }
            Emit.send(fx, core, Particle.REVERSE_PORTAL, null, 6, r * 0.4, 1, r * 0.4, 0.2, Emit.DETAIL);
        });
        return out;
    }

    static void collapse(List<Sprite> parts) {
        for (Sprite s : parts) {
            if (!s.ok()) continue;
            s.steps.clear();
            s.key(s.age + 1, 2, sp -> sp.sc.mul(0.02f));
            s.life = s.age + 3;
        }
    }

    /** 번개 구름: 어두운 소용돌이 + 가장자리 먹구름 + 속 번쩍임. follow 가 있으면 따라간다 */
    static List<Sprite> stormCloud(CastFx fx, Location c, double r, int life, Supplier<Location> follow) {
        List<Sprite> out = new ArrayList<>();
        CastFx.Cols dark = new CastFx.Cols(Color.fromRGB(0x3a3a5a), Color.fromRGB(0x8a8ab0), Color.fromRGB(0x0a0a14), Color.fromRGB(0x0a0a14), false);
        String sm = fx.vfx.models.pick("swirl", "shock");
        if (sm != null) {
            Sprite sw = Kit.flat(fx, sm, c, 0.5, Shapes.Frame.FLAT, dark).life(life).range(2);
            sw.decal = true;
            sw.edgeOn = 0.15;
            sw.scaleTo(1, 8, r / Geo.FLAT_HALF, 1, r / Geo.FLAT_HALF);
            Kit.spinOver(sw, 9, life - 9, 40);
            if (follow != null) sw.follow(follow, 4);
            sw.go();
            out.add(sw);
        }
        fx.vfx.every(0, 5, life / 5, i -> {
            Location cc = follow != null ? follow.get() : c;
            if (cc == null) return;
            for (Location p : Shapes.around(cc, r * 0.9, 10, i * 0.3))
                Emit.dust(fx, p, Color.fromRGB(0x4a4a62), 2.6, 2, 0.5, Emit.DETAIL);
            Emit.send(fx, cc, Particle.ELECTRIC_SPARK, null, 6, r * 0.4, 0.2, r * 0.4, 0.1, Emit.DETAIL);
        });
        return out;
    }

    /** 구름에서 땅으로 번개 한 줄기 (입자 + 있으면 bolt 조각) */
    static void cloudBolt(CastFx fx, Location from, Location to, CastFx.Cols k) {
        List<Location> pts = Shapes.bolt(from, to, 7, 0.8, Kit.rnd());
        for (int i = 0; i + 1 < pts.size(); i++) {
            Emit.line(fx, pts.get(i), pts.get(i + 1), 0.3, k.b(), 1.1, Emit.NORMAL);
            Emit.line(fx, pts.get(i), pts.get(i + 1), 0.45, Color.WHITE, 0.6, Emit.DETAIL);
        }
        if (fx.vfx.models.has("bolt")) {
            double h = from.getY() - to.getY();
            Sprite b = Sprite.item(fx, "bolt", to).size(1.2, h, 1.2).radius(1).life(4).tint(k).end(Sprite.End.THIN, 2);
            b.go();
        }
        fx.sound(to, "entity.lightning_bolt.impact", 0.5, 1.3);
    }

    // ------------------------------------------------------------------ 큰 별 · 프리즘 결정 · 하늘 균열

    /**
     * 하늘의 큰 별: 한 장짜리 별은 크게 띄우면 납작한 원판 아이콘처럼 보였다.
     * 심(별) + 반대로 도는 긴 빛살(가는 별살 그림, 22.5도 어긋남) + 맥박 치는 무지개 후광 고리 + 부드러운 빛 덩이로 겹친다.
     * grow > 0 이면 그 틱 동안 0 에서 자란다. 같은 view 로 모두 띄우고 손잡이 목록을 돌려준다
     */
    static List<Sprite> bigStar(CastFx fx, Location at, double size, int life, CastFx.Cols k, Sprite.View view, int grow) {
        List<Sprite> out = new ArrayList<>();
        boolean rb = k.rainbow();
        int g = Math.max(2, grow);
        int end = Math.max(g + 2, life - 4);
        // 뒤: 부드러운 빛 덩이
        Sprite glow = Sprite.item(fx, fx.vfx.models.pick("orb_dim", "orb"), at).size(0.05).radius(size).life(life).view(view)
                .tint(rb ? Color.WHITE : k.b(), Color.WHITE, k.rim()).end(Sprite.End.FADE, 4);
        glow.scaleTo(1, g, size * 1.6);
        out.add(glow);
        // 긴 빛살: 22.5도 어긋나 천천히 반대로 돌며 숨 쉬듯 커졌다 작아진다
        String sm = fx.vfx.models.pick("star_f2", "star");
        Sprite spokes = Sprite.item(fx, sm, at).size(0.05).radius(size).life(life).view(view)
                .tint(Color.WHITE, rb ? Palette.hue(0.55) : k.b(), k.rim()).end(Sprite.End.FADE, 3);
        spokes.rot.rotateZ((float) Math.toRadians(22.5));
        spokes.scaleTo(1, g, size * 1.45);
        spokes.animate(g + 1, end, 3, (sp, t) -> {
            double f = (t - g) / (double) Math.max(1, life - g);
            sp.rot.set(new Quaternionf().rotateZ((float) Math.toRadians(22.5 - 80 * f)));
            sp.sc.set((float) (size * 1.45 * (1 + 0.08 * Math.sin(t * 0.7))));
        });
        out.add(spokes);
        // 심: 별 (무지개면 무지개 별), 맥박 치며 반대로 돈다
        String cm = rb ? fx.vfx.models.pick("star_rainbow", "star") : "star";
        Sprite core = Sprite.item(fx, cm, at).size(0.05).radius(size).life(life).view(view).tint(k).end(Sprite.End.FADE, 3);
        core.scaleTo(1, g, size);
        core.animate(g + 1, end, 3, (sp, t) -> {
            double f = (t - g) / (double) Math.max(1, life - g);
            sp.rot.set(new Quaternionf().rotateZ((float) Math.toRadians(60 * f)));
            sp.sc.set((float) (size * (1 + 0.13 * Math.sin(t * 1.05))));
        });
        out.add(core);
        // 후광 고리: 화면을 향한 고리가 맥박 치며 커진다
        String rm = rb ? fx.vfx.models.pick("ring_rainbow", "ring") : "ring";
        double rr = size * 0.85;
        Sprite halo = Sprite.item(fx, rm, at).frame(Shapes.Frame.FLAT.pitch(-90)).size(0.05).radius(rr).life(life).view(view)
                .tint(k.swap()).bill(Display.Billboard.CENTER).end(Sprite.End.FADE, 3);
        halo.decal = false;
        halo.scaleTo(1, g + 1, rr / Geo.FLAT_HALF, 1, rr / Geo.FLAT_HALF);
        halo.animate(g + 3, end, 4, (sp, t) -> {
            double m = rr / Geo.FLAT_HALF * (1 + 0.14 * Math.sin(t * 0.8));
            sp.sc.set((float) m, 1f, (float) m);
        });
        if (rb) halo.hue(4, 0.3);
        out.add(halo);
        for (Sprite sp : out) sp.go();
        if (!core.ok()) Emit.send(fx, at, Particle.END_ROD, null, 16, size * 0.2, size * 0.2, size * 0.2, 0.05, Emit.NORMAL);
        return out;
    }

    /** 공중에서 도는 프리즘 결정. boost 틱까지는 1.35배로 번쩍인다 */
    static final class Crystal {
        final List<Sprite> parts = new ArrayList<>();
        long boost;
    }

    /**
     * 공중에서 도는 프리즘 결정 (블록 표시라 팩 없이도 보인다): 꼭짓점으로 선 색유리 정육면체 둘이 반대로 돌고
     * 가운데 바다 랜턴 심이 빛난다. pulse() 로 순간 커졌다 돌아온다
     */
    static Crystal prismCrystal(CastFx fx, Supplier<Location> where, double size, int life, Sprite.View view) {
        Crystal cr = new Crystal();
        Location at = where.get();
        if (at == null) return cr;
        Material[] mats = {Material.PURPLE_STAINED_GLASS, Material.LIGHT_BLUE_STAINED_GLASS, Material.SEA_LANTERN};
        double[] sizes = {size, size * 0.74, size * 0.36};
        double[] spins = {260, -380, 200};
        double[] tilt = {45, 65, 85};
        for (int i = 0; i < 3; i++) {
            int idx = i;
            Sprite c = Sprite.block(fx, mats[i].createBlockData(), at).size(0.05).radius(size * 0.7).life(life).view(view)
                    .end(Sprite.End.SHRINK, 4).follow(where, 2);
            Quaternionf stand = new Quaternionf().rotateX((float) Math.toRadians(tilt[i])).rotateZ((float) Math.toRadians(35.26));
            c.rot.set(stand);
            c.scaleTo(1, 4, sizes[i]);
            c.animate(5, life - 4, 2, (sp, t) -> {
                double ang = Math.toRadians(spins[idx] * (t - 4) / (double) Math.max(1, life - 8));
                sp.rot.set(new Quaternionf().rotateY((float) ang).mul(stand));
                double m = fx.vfx.tick < cr.boost ? 1.35 : 1.0;
                sp.sc.set((float) (sizes[idx] * m));
            });
            c.go();
            cr.parts.add(c);
        }
        return cr;
    }

    static void pulse(CastFx fx, Crystal cr) {
        cr.boost = fx.vfx.tick + 3;
    }

    /**
     * 하늘 균열: 머리 위 높은 곳에서 도는 검붉은 소용돌이 + 가운데 검은 구 + 아래로 새어 나오는 영혼 불꽃.
     * 옆에서(거의 수평으로) 보면 판이 줄로만 보이므로 숨기고, 가장자리 입자 띠가 대신 보인다
     */
    static List<Sprite> skyRift(CastFx fx, Location c, double r, int life, CastFx.Cols k) {
        List<Sprite> out = new ArrayList<>();
        String sm = fx.vfx.models.pick("swirl", "shock");
        if (sm != null) {
            Sprite sw = Kit.flat(fx, sm, c, 0.5, Shapes.Frame.FLAT, k).life(life).range(2).end(Sprite.End.FADE, 6);
            sw.decal = true;
            sw.edgeOn = 0.18;
            sw.scaleTo(1, 8, r / Geo.FLAT_HALF, 1, r / Geo.FLAT_HALF).radius(r);
            Kit.spinOver(sw, 9, life - 9, -120);
            sw.go();
            out.add(sw);
            String dm = fx.vfx.models.pick("swirl_dim", "swirl");
            Sprite sw2 = Kit.flat(fx, dm, c.clone().add(0, -0.4, 0), 0.5, Shapes.Frame.FLAT.yaw(60), k.swap()).life(life).range(2).end(Sprite.End.FADE, 6);
            sw2.decal = true;
            sw2.edgeOn = 0.18;
            sw2.scaleTo(2, 8, r * 0.7 / Geo.FLAT_HALF, 1, r * 0.7 / Geo.FLAT_HALF).radius(r * 0.7);
            Kit.spinOver(sw2, 10, life - 10, 160);
            sw2.go();
            out.add(sw2);
        }
        Sprite core = Kit.orb(fx, c.clone().add(0, -0.6, 0), 0.3, life, k, fx.vfx.models.pick("void_orb", "orb")).range(2);
        core.scaleTo(1, 10, 2.2);
        core.go();
        out.add(core);
        fx.vfx.every(0, 3, Math.max(1, life / 3), i -> {
            // 가장자리 입자 띠 (옆에서도 보이는 구름 테)
            for (Location p : Shapes.around(c, r * (0.85 + 0.1 * Math.sin(i)), 14, i * 0.25))
                Emit.dust(fx, p, i % 2 == 0 ? k.dark() : k.a(), 2.4, 1, 0.3, Emit.DETAIL);
            for (int j = 0; j < 3; j++) {
                double a = Kit.rnd().nextDouble(Math.PI * 2), d = Math.sqrt(Kit.rnd().nextDouble()) * r * 0.8;
                Location from = c.clone().add(Math.cos(a) * d, -0.3, Math.sin(a) * d);
                Emit.trail(fx, from, from.clone().add(0, -6, 0), k.a(), 10, Emit.NORMAL);
            }
            Emit.send(fx, c.clone().add(0, -0.6, 0), Particle.SOUL_FIRE_FLAME, null, 4, r * 0.3, 0.2, r * 0.3, 0.02, Emit.DETAIL);
        });
        return out;
    }

    /**
     * 눈보라 구름: 위에서 도는 회청색 소용돌이 두 겹(옆에서 보면 숨김) + 옆에서도 보이는 짙은 구름 띠(큰 먼지·구름 입자) +
     * 아래로 그어지는 얼음 줄기(TRAIL)와 눈발. ground = 바닥 높이 기준점
     */
    static List<Sprite> iceStorm(CastFx fx, Location top, Location ground, double r, int life) {
        List<Sprite> out = new ArrayList<>();
        CastFx.Cols grey = new CastFx.Cols(Color.fromRGB(0x9ab8d8), Color.fromRGB(0xe8fbff), Color.fromRGB(0x2a3a5a),
                Color.fromRGB(0x4a5a7a), false);
        String sm = fx.vfx.models.pick("swirl", "shock_dim");
        if (sm != null) {
            Sprite sw = Kit.flat(fx, sm, top, 0.5, Shapes.Frame.FLAT, grey).life(life).range(2).end(Sprite.End.FADE, 6);
            sw.decal = true;
            sw.edgeOn = 0.16;
            sw.scaleTo(1, 6, r / Geo.FLAT_HALF, 1, r / Geo.FLAT_HALF).radius(r);
            Kit.spinOver(sw, 7, life - 7, -90);
            sw.go();
            out.add(sw);
            String dm = fx.vfx.models.pick("swirl_dim", "swirl");
            Sprite sw2 = Kit.flat(fx, dm, top.clone().add(0, -0.5, 0), 0.5, Shapes.Frame.FLAT.yaw(50), grey.swap()).life(life).range(2)
                    .end(Sprite.End.FADE, 6);
            sw2.decal = true;
            sw2.edgeOn = 0.16;
            sw2.scaleTo(2, 6, r * 0.75 / Geo.FLAT_HALF, 1, r * 0.75 / Geo.FLAT_HALF).radius(r * 0.75);
            Kit.spinOver(sw2, 8, life - 8, 130);
            sw2.go();
            out.add(sw2);
        }
        fx.vfx.every(0, 2, Math.max(1, life / 2), i -> {
            if (i % 2 == 0) {
                // 구름 띠: 옆에서 봐도 두꺼운 구름
                for (Location p : Shapes.around(top, r * 0.8, 12, i * 0.2)) {
                    Emit.dust(fx, p, Color.fromRGB(i % 4 == 0 ? 0x8a9ab0 : 0xc8d8e8), 3.2, 1, 0.5, Emit.NORMAL);
                }
                Emit.send(fx, top, Particle.CLOUD, null, 6, r * 0.45, 0.25, r * 0.45, 0.01, Emit.DETAIL);
            }
            // 얼음 줄기: 구름에서 땅으로 그어지는 빛
            for (int j = 0; j < 3; j++) {
                double a = Kit.rnd().nextDouble(Math.PI * 2), d = Math.sqrt(Kit.rnd().nextDouble()) * r * 0.85;
                Location from = top.clone().add(Math.cos(a) * d, -0.4, Math.sin(a) * d);
                Location to = from.clone();
                to.setY(ground.getY() + 0.2);
                Emit.trail(fx, from, to, j == 0 ? Color.WHITE : Color.fromRGB(0x9ad8ff), 7, Emit.NORMAL);
            }
            Emit.send(fx, top.clone().add(0, -1, 0), Particle.SNOWFLAKE, null, 8, r * 0.5, 0.6, r * 0.5, 0.03, Emit.DETAIL);
        });
        return out;
    }

    // ------------------------------------------------------------------ 시계 (시간 정지)

    /** 바닥 시계: 마법진 + 누운 숫자 12개 + 거꾸로 돌다 멈추는 바늘 둘. life 동안 = 기절 시간 */
    static void clock(CastFx fx, Location c, double r, int life) {
        CastFx.Cols k = new CastFx.Cols(Color.fromRGB(0xdfe8ff), Color.WHITE, Color.fromRGB(0x2a3a6a), Color.fromRGB(0x8aa8ff), false);
        Kit.circle(fx, c, r, life, k, 0, true, Sprite.View.AUTO);
        String[] nums = {"Ⅻ", "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "Ⅺ"};
        double s = Math.max(1.5, r * 0.45);
        for (int i = 0; i < 12; i++) {
            double a = Math.PI * 2 * i / 12;
            Location p = c.clone().add(Math.sin(a) * r * 0.78, 0.06, -Math.cos(a) * r * 0.78);
            Component t = Component.text(nums[i], TextColor.color(0xdfe8ff));
            Sprite tx = Sprite.text(fx, t, p).size(s).life(life).radius(0.5).end(Sprite.End.SHRINK, 4);
            // 눕히고(위를 보게), 글자 위쪽이 바깥을 향하게 돌린다. 글자는 원점에서 위로 자라므로 반 줄 만큼 안쪽으로
            tx.rot.rotateY((float) -a).rotateX((float) Math.toRadians(-90));
            tx.offset(Math.sin(a) * 0.12 * s, 0, -Math.cos(a) * 0.12 * s);
            tx.decal = true;
            tx.go();
        }
        // 바늘: 길게 늘인 글자 막대. 처음 10틱 거꾸로 돌고 멈춘다
        for (int h = 0; h < 2; h++) {
            double len = h == 0 ? r * 0.55 : r * 0.75;
            Component bar = Component.text("▌", TextColor.color(h == 0 ? 0xffffff : 0x9ab8ff));
            Sprite hand = Sprite.text(fx, bar, c.clone().add(0, 0.07 + h * 0.01, 0)).size(0.6, len * 4, 0.6).life(life).radius(len).end(Sprite.End.SHRINK, 4);
            hand.rot.rotateY((float) Math.toRadians(h * 150)).rotateX((float) Math.toRadians(-90));
            hand.decal = true;
            hand.spinAxis(1, 10, h == 0 ? 160 : 320, new Vector3f(0, 0, 1));
            hand.go();
        }
    }

    // ------------------------------------------------------------------ 얼음 감옥

    /** 대상을 얼음 블록으로 감쌌다가 깨뜨린다 */
    static void encase(CastFx fx, LivingEntity t, int life) {
        if (t == null || !t.isValid()) return;
        double w = t.getWidth() + 0.25, h = t.getHeight() + 0.2;
        Supplier<Location> at = () -> t.isValid() ? t.getLocation().add(0, h / 2 - 0.1, 0) : null;
        Sprite s = Sprite.block(fx, Material.ICE.createBlockData(), at.get()).size(w, h, w).life(life).radius(w).worldLight()
                .end(Sprite.End.NONE).follow(at, 2);
        s.go();
        fx.vfx.after(life - 1, () -> {
            Location l = at.get();
            if (l == null) return;
            Emit.send(fx, l, Particle.BLOCK, Material.ICE.createBlockData(), 30, w * 0.4, h * 0.4, w * 0.4, 0.15, Emit.NORMAL);
            fx.sound(l, "block.glass.break", 0.8, 1.2);
        });
    }

    // ------------------------------------------------------------------ 시전자 화면용 (1인칭에서도 보이는 큰 연출)

    /** 시전자에게만: 시선 앞 d 칸, 위로 up 칸에 별 */
    static void heroStar(CastFx fx, double d, double up, double size, int life, CastFx.Cols k) {
        if (fx.cp == null) return;
        Kit.star(fx, Kit.heroSpot(fx, d, up), size, life, k).view(Sprite.View.ONLY).go();
    }

    /** 시전자 머리 위 3칸의 후광 고리 (올려다보면 보이고, 화면을 가리지 않는다) */
    static Sprite halo(CastFx fx, double r, int life, CastFx.Cols k) {
        LivingEntity c = fx.caster;
        Supplier<Location> top = () -> c.isValid() ? c.getLocation().add(0, c.getHeight() + 2.6, 0) : null;
        Location t = top.get();
        if (t == null) return null;
        Sprite s = Kit.ring(fx, t, 0.3, r, 4, life, k, null).follow(top, 1).view(Sprite.View.SHOW);
        s.decal = false;
        s.go();
        return s;
    }

    static Location up(Location l, double y) {
        return l.clone().add(0, y, 0);
    }
}
