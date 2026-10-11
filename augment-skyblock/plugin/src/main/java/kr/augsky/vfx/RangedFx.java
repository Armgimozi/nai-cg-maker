package kr.augsky.vfx;

import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.entity.Display;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.List;

/** 투사체·폭발·광선·연쇄 번개 */
final class RangedFx {
    private RangedFx() {}

    // ------------------------------------------------------------------ 투사체

    static Track projectile(CastFx fx, Ev.Projectile ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        int r = fx.rank();
        Location start = ev.start();
        Vector vel = ev.vel();
        Location[] pos = {start.clone()};
        List<Sprite> parts = new ArrayList<>();
        boolean headOk = r >= 1 && fx.tier != Tier.MOB && !ev.ground() && (r >= 3 ? ev.count() <= 7 : ev.count() <= 3);
        if (headOk) {
            double size = (r >= 3 ? 0.85 : 0.55) * (ev.hasDisplay() ? 0.6 : 1.0);
            String m = (fx.pal.id().equals("abyss") || fx.pal.id().equals("doom")) && r >= 2 ? fx.vfx.models.pick("void_orb", "orb") : "orb";
            Sprite head = Kit.orb(fx, start, size, 215, k, m).reveal(2.5).follow(() -> pos[0], 1);
            head.go();
            parts.add(head);
            if (r >= 3 && vel.lengthSquared() > 1e-6) {
                Sprite halo = Kit.flat(fx, "ring", start, 0.5, Shapes.Frame.normal(vel), k).life(215).reveal(2.5).follow(() -> pos[0], 1);
                halo.decal = false;
                halo.end(Sprite.End.SHRINK, 2);
                halo.go();
                parts.add(halo);
            }
        }
        if (r == 0 && fx.tier != Tier.MOB && !ev.ground() && ev.count() <= 3) {
            // 초반 무기: 작고 깨끗하게. 반짝이는 별 하나가 투사체에 실려 날아간다 (눈앞 2.5칸까지는 시전자에게 숨김)
            Sprite head = Sprite.item(fx, fx.vfx.models.pick("spark", "orb"), start).size(0.25).radius(0.3).life(215)
                    .tint(k.a(), Color.WHITE, k.rim()).reveal(2.5).follow(() -> pos[0], 1).end(Sprite.End.SHRINK, 2);
            head.scaleTo(1, 2, 0.6);
            // 반짝임: 커졌다 작아졌다 (4틱 주기)
            for (int i = 3; i < 40; i += 4) {
                head.scaleTo(i, 2, 0.45);
                head.scaleTo(i + 2, 2, 0.62);
            }
            head.fallback(() -> { });
            head.go();
            parts.add(head);
        }
        if (ev.ground() && r >= 1 && fx.pal.id().equals("ocean") && fx.vfx.models.has("wave") && ev.count() <= 3) {
            Vector f = vel.clone().setY(0);
            if (f.lengthSquared() > 1e-6) {
                double w = Math.max(1.5, ev.hitRadius() * 2) / 3.0;
                Sprite wave = Sprite.item(fx, "wave", start).frame(Shapes.Frame.flat(f)).size(w * 0.3, 0.3, w * 0.3).radius(1.5)
                        .life(215).tint(k).follow(() -> pos[0], 1).end(Sprite.End.FADE, 4);
                wave.scaleTo(1, 4, w, Math.max(0.8, w * 0.9), w);
                wave.go();
                parts.add(wave);
            }
        }
        return new Track() {
            Location prev = start.clone();
            int t;
            double since;

            @Override
            public void tick(Location p, Vector v) {
                t++;
                pos[0] = p.clone();
                since += p.distance(prev);
                if (r == 0) {
                    // 초반 무기: 속성색 → 흰빛으로 식는 짧은 꼬리 + 머리 반짝임
                    Emit.spec(fx, fx.pal.spark(), p, 1, 0.03, 0.01, Emit.NORMAL);
                    Emit.streak(fx, prev, p, k.a(), 2, 4, Emit.NORMAL);
                    Vector seg = p.toVector().subtract(prev.toVector());
                    for (int i = 0; i < 3; i++) {
                        Location q = prev.clone().add(seg.clone().multiply(i / 3.0));
                        Emit.trans(fx, q, k.a(), Kit.WHITE, 0.7, Emit.NORMAL);
                    }
                } else {
                    Color tc = r >= 4 && k.rainbow() ? Palette.hue(fx.vfx.tick * 0.04) : k.a();
                    Emit.streak(fx, prev, p, tc, 2, 4, Emit.NORMAL);
                }
                if (r >= 2 && v.lengthSquared() > 1e-6 && !ev.ground()) {
                    Shapes.Frame fr = Shapes.Frame.along(v);
                    double a = t * 0.9;
                    for (int s = 0; s < 2; s++) {
                        double aa = a + Math.PI * s;
                        Location q = fr.point(p, Math.cos(aa) * 0.28, Math.sin(aa) * 0.28, 0);
                        Emit.dust(fx, q, s == 0 ? k.a() : k.b(), 0.8, Emit.DETAIL);
                    }
                    Emit.spec(fx, fx.pal.spark(), p, 1, 0.05, 0.01, Emit.DETAIL);
                }
                if (ev.ground() && r >= 1) groundTrail(fx, p, v, since);
                if (since >= 2) since = 0;
                prev = p.clone();
            }

            @Override
            public void end(Location at, boolean impact) {
                for (Sprite s : parts) s.finish(2);
                if (r == 0) {
                    // 흰 연기(POOF) 대신 속성색 작은 빛 고리(맞은 쪽을 향해 선다) + 튀는 빛 (맞았다는 것만 또렷하게)
                    if (impact && fx.tier != Tier.MOB) {
                        Vector n = vel.lengthSquared() > 1e-6 ? vel.clone() : new Vector(0, 1, 0);
                        Sprite ring = Kit.flat(fx, "ring", at, 0.15, Shapes.Frame.normal(n), k).life(6).end(Sprite.End.FADE, 2);
                        ring.decal = false;
                        ring.scaleTo(1, 3, 0.75 / Geo.FLAT_HALF, 1, 0.75 / Geo.FLAT_HALF);
                        ring.fallback(() -> Kit.dustRing(fx, at, 0.55, k.a(), 0.9, Emit.NORMAL));
                        ring.go();
                    } else {
                        Kit.dustRing(fx, at, 0.55, k.a(), 0.9, Emit.NORMAL);
                    }
                    Emit.send(fx, at, Particle.CRIT, null, 8, 0.1, 0.1, 0.1, 0.35, Emit.NORMAL);
                    Emit.trans(fx, at, Kit.WHITE, k.a(), 1.1, Emit.NORMAL);
                    return;
                }
                if (!impact) {
                    Emit.spec(fx, fx.pal.spark(), at, 4, 0.2, 0.05, Emit.DETAIL);
                    return;
                }
                if (fx.tier != Tier.MOB && ev.explodeRadius() <= 0) {
                    Kit.star(fx, at, r >= 3 ? 1.4 : 0.7, 4, k).go();
                    Location g = Kit.groundOrNull(at);
                    if (g != null && at.getY() - g.getY() < 1.5) Kit.ring(fx, g.add(0, 0.03, 0), 0.2, 1.1, 2, 6, k, null).go();
                }
                if (r >= 2) Kit.accent(fx, at, 0.9);
                if (r >= 3) Kit.debris(fx, at, 3, 0.7, null);
                if (r >= 4) Pieces.rays(fx, at, fx.n(10), 3.5, k, 7, false);
            }
        };
    }

    /** 땅을 타는 투사체 (해일·충격파·회오리) */
    static void groundTrail(CastFx fx, Location p, Vector v, double since) {
        switch (fx.pal.id()) {
            case "ocean" -> Emit.send(fx, p.clone().add(0, 0.6, 0), Particle.SPLASH, null, 8, 0.6, 0.5, 0.6, 0.1, Emit.NORMAL);
            case "earth" -> {
                if (since >= 2 && fx.rank() >= 1 && fx.moving < 12) {
                    Material m = Kit.groundMaterial(p, Material.DIRT);
                    Sprite s = Sprite.block(fx, m.createBlockData(), p.clone().add(0, -0.3, 0)).size(0.55).worldLight().life(10).end(Sprite.End.SHRINK, 4).radius(0.4);
                    s.rot.rotateXYZ((float) Kit.rnd().nextDouble(-0.5, 0.5), (float) Kit.rnd().nextDouble(3), (float) Kit.rnd().nextDouble(-0.5, 0.5));
                    s.moveBy(1, 3, 0, 0.7, 0);
                    s.go();
                }
                Emit.send(fx, p.clone().add(0, 0.2, 0), Particle.BLOCK_CRUMBLE, Material.DIRT.createBlockData(), 6, 0.4, 0.2, 0.4, 0.1, Emit.NORMAL);
            }
            case "wind" -> {
                double a = fx.vfx.tick * 0.7;
                for (int i = 0; i < 6; i++) {
                    double h = i * 0.5, rr = 0.3 + i * 0.18, aa = a + i * 0.9;
                    Emit.send(fx, p.clone().add(Math.cos(aa) * rr, h, Math.sin(aa) * rr), Particle.CLOUD, null, 1, 0, 0, 0, 0, Emit.DETAIL);
                }
            }
            default -> Emit.send(fx, p.clone().add(0, 0.1, 0), Particle.BLOCK_CRUMBLE, Kit.groundMaterial(p, Material.STONE).createBlockData(), 4, 0.3, 0.1, 0.3, 0.1, Emit.DETAIL);
        }
    }

    // ------------------------------------------------------------------ 폭발

    static void explode(CastFx fx, Ev.Explode ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        Location at = ev.at();
        double rr = ev.radius();
        Location g = Kit.groundOrNull(at);
        boolean onGround = g != null && at.getY() - g.getY() < 2;
        if (fx.rank() == 0) {
            Kit.dustRing(fx, at, rr, k.a(), 1.2, Emit.NORMAL);
            return;
        }
        if (fx.tier != Tier.MOB) {
            if (onGround) {
                Sprite ring = Kit.ring(fx, g.clone().add(0, 0.03, 0), 0.3, rr, 3, 8, k, null);
                if (fx.mob()) ring.end(Sprite.End.NONE);
                ring.go();
            }
            Kit.star(fx, at, Math.min(fx.ult() ? 4 : 2, 0.6 + rr * 0.35), 4, k).go();
        } else {
            Kit.dustRing(fx, at, rr, k.a(), 1.3, Emit.NORMAL);
        }
        if (fx.rank() >= 2) {
            if (onGround) Kit.shock(fx, g.clone().add(0, 0.02, 0), 0.2, rr * 0.9, 4, 9, k).go();
            Kit.accent(fx, at, Math.min(2, rr * 0.5));
            fx.impactSounds(at);
        }
        if (fx.rank() >= 3) {
            Kit.debris(fx, onGround ? g : at, 4, 1.0, null);
            if (rr >= 3) Emit.flash(fx, at.clone().add(0, 1, 0));
            if (onGround && !fx.mob()) Kit.afterglow(fx, g, Math.min(3, rr * 0.7), 24, k);
        }
    }

    // ------------------------------------------------------------------ 광선

    static void beam(CastFx fx, Ev.Beam ev) {
        CastFx.Cols k = fx.cols(ev.core() != null ? ev.core() : ev.yaml());
        if (Palette.yamlColors(ev.core()) == null && Palette.yamlColors(ev.yaml()) != null) k = fx.cols(ev.yaml());
        Location start = ev.start();
        Vector dir = ev.dir().clone().normalize();
        Location end = ev.end();
        double len = start.distance(end);
        double w = ev.width();
        int r = fx.rank();
        CastFx.Cols kk = k;
        if (len < 1.5) return;
        if (!fx.vfx.spritesOn() && fx.skill != null && fx.skill.contains("slash")) {
            int a = fx.aud;
            Shapes.Frame wf = Shapes.Frame.flat(dir).roll(12);
            double rr = Math.max(1.2, w * 1.3);
            fx.vfx.every(0, 1, 4, i -> fx.with(a, () ->
                    Kit.slashDust(fx, start.clone().add(dir.clone().multiply(1.5 + (len - 1.5) * i / 3.0)), wf, rr, kk)));
        }
        if (r == 0) {
            Emit.spec(fx, fx.pal.spark(), end, 6, 0.2, 0.08, Emit.NORMAL);
            return;
        }
        if (fx.tier == Tier.BOSS_MOB) {
            bossBeam(fx, ev, k);
            return;
        }
        String model = "beam";
        if (k.rainbow() && fx.vfx.models.has("beam_rainbow")) model = "beam_rainbow";
        if ((fx.pal.id().equals("abyss") || fx.pal.id().equals("doom")) && r >= 2 && fx.vfx.models.has("rift")) model = "rift";
        // 다른 사람: 눈앞 1.2칸부터 끝까지
        Location s0 = start.clone().add(dir.clone().multiply(1.2));
        double l0 = Math.max(0.5, len - 1.2);
        // 보스 몬스터 광선은 피할 대상이라 굵고 또렷하게
        double wm = fx.tier == Tier.BOSS_MOB ? 1.0 : 0.7;
        Sprite main = Kit.beam(fx, model, s0, dir, l0, w * wm, 10, k).view(fx.cp != null ? Sprite.View.HIDE : Sprite.View.AUTO);
        main.radius(w * 0.35);
        main.go();
        Kit.hallmark(fx, main);
        // 시전자: 손에서 나가는 광선 (화면 한가운데를 덮지 않게 오른손 쪽에서 조준점으로 모인다)
        if (fx.cp != null) handBeam(fx, start, dir, end, w, model, k);
        Kit.star(fx, end, r >= 3 ? 1.3 : 0.8, 5, k).go();
        Sprite endRing = Kit.flat(fx, "ring", end, 0.3, Shapes.Frame.normal(dir), k).life(7);
        endRing.decal = false;
        endRing.scaleTo(1, 3, 1.2 / Geo.FLAT_HALF * (1 + w), 1, 1.2 / Geo.FLAT_HALF * (1 + w));
        endRing.go();
        if (r >= 2) {
            String om = fx.vfx.models.pick(model + "_dim", "beam_dim", "beam");
            if (om != null) Kit.beam(fx, om, s0, dir, l0, w * (wm + 0.45), 9, k.swap()).view(fx.cp != null ? Sprite.View.HIDE : Sprite.View.AUTO).go();
            Shapes.Frame fr = Shapes.Frame.along(dir);
            int pts = (int) Math.min(60, len / 0.3);
            for (int i = 0; i < pts; i++) {
                double t = i * 0.3;
                for (int s = 0; s < 2; s++) {
                    double a = t * 2.2 + Math.PI * s;
                    Location q = fr.point(start, Math.cos(a) * w * 0.45, Math.sin(a) * w * 0.45, t);
                    Emit.dust(fx, q, s == 0 ? kk.a() : kk.b(), 0.8, Emit.DETAIL);
                }
            }
            beamAccent(fx, start, dir, len, w);
        }
        if (r >= 3) {
            // 총구 마법진: 시전자 눈앞이라 남에게만
            Sprite mz = Kit.flat(fx, "circle", start.clone().add(dir.clone().multiply(1.6)), 0.2, Shapes.Frame.normal(dir), k).life(10)
                    .view(Sprite.View.HIDE);
            mz.decal = false;
            mz.scaleTo(1, 3, (0.7 + w) / Geo.FLAT_HALF, 1, (0.7 + w) / Geo.FLAT_HALF);
            mz.go();
            for (int i = 1; i <= 3; i++) {
                double t = len * i / 4.0;
                Location q = start.clone().add(dir.clone().multiply(t));
                int d = i;
                fx.vfx.after(d, () -> {
                    Sprite rg = Kit.flat(fx, "ring", q, 0.2 + w * 0.3, Shapes.Frame.normal(dir), kk).life(6);
                    rg.decal = false;
                    rg.scaleTo(1, 4, (0.6 + w) / Geo.FLAT_HALF, 1, (0.6 + w) / Geo.FLAT_HALF);
                    rg.go();
                });
            }
            Location g = Kit.groundOrNull(end);
            if (g != null && end.getY() - g.getY() < 2) Kit.shock(fx, g.add(0, 0.03, 0), 0.3, 1.8 + w, 3, 8, k).go();
        }
        if (r >= 4) {
            Sprite core = Kit.beam(fx, model, s0, dir, l0, w * 0.3, 10, new CastFx.Cols(Color.WHITE, Color.WHITE, k.dark(), k.rim(), false))
                    .view(fx.cp != null ? Sprite.View.HIDE : Sprite.View.AUTO);
            core.go();
            List<Location> sparkle = new ArrayList<>();
            Shapes.line(start, end, 1.2, (p, t) -> sparkle.add(p));
            fx.vfx.every(2, 4, 5, i -> {
                for (Location p : sparkle) {
                    Location q = p.clone().add(Kit.rnd().nextGaussian() * 0.3, Kit.rnd().nextGaussian() * 0.3 + i * 0.05, Kit.rnd().nextGaussian() * 0.3);
                    Emit.dust(fx, q, kk.rainbow() ? Palette.hue(Kit.rnd().nextDouble()) : kk.b(), 0.7, Emit.DETAIL);
                }
            });
            Pieces.rays(fx, end, fx.n(10), 3, kk, 7, false);
        }
    }

    /**
     * 보스 몬스터 광선: 피해야 하는 기술이라 굵고 또렷하게. 흰 심 + 속성색 겉껍질(폭 1.6배) + 감아 도는 속성 조각,
     * 서리는 반투명 얼음 기둥이 실제로 길을 따라 얼었다가 깨진다. 끝에는 속성 폭발.
     */
    static void bossBeam(CastFx fx, Ev.Beam ev, CastFx.Cols k) {
        Location start = ev.start();
        Vector dir = ev.dir().clone().normalize();
        Location end = ev.end();
        double len = start.distance(end);
        double w = Math.max(0.8, ev.width());
        String id = fx.pal.id();
        boolean voidish = id.equals("abyss") || id.equals("doom") || id.equals("shadow");
        String model = voidish && fx.vfx.models.has("rift") ? "rift" : "beam";
        Location s0 = start.clone().add(dir.clone().multiply(0.8));
        double l0 = Math.max(0.5, len - 0.8);
        // 겉껍질(속성색, 굵게) → 심(흰색, 가늘게) 순서로 띄운다
        Sprite shell = Kit.beam(fx, "beam", s0, dir, l0, w * 1.7, 16, new CastFx.Cols(k.a(), k.a(), k.dark(), k.rim(), false));
        shell.radius(w * 0.8);
        shell.go();
        Sprite core = Kit.beam(fx, model, s0, dir, l0, w * 0.8, 16, new CastFx.Cols(Color.WHITE, k.b(), k.dark(), k.rim(), false));
        core.go();
        Shapes.Frame fr = Shapes.Frame.along(dir);
        if (id.equals("frost")) {
            // 얼음 기둥: 길을 따라 반투명 얼음이 얼었다가 깨진다 (팩이 없어도 보인다)
            double iw = w * 0.75;
            Sprite ice = Sprite.block(fx, org.bukkit.Material.ICE.createBlockData(), s0).frame(fr).size(iw * 0.3, iw * 0.3, l0)
                    .radius(iw).life(18).end(Sprite.End.SHRINK, 3);
            ice.centerBlock = false;
            org.joml.Vector3f half = new org.joml.Vector3f((float) (iw * 0.15), (float) (iw * 0.15), 0);
            ice.rot.transform(half);
            ice.offset(-half.x, -half.y, -half.z);
            ice.segLen = l0;
            ice.segDir = dir.clone();
            ice.key(1, 2, sp -> {
                sp.sc.set((float) iw, (float) iw, (float) l0);
                org.joml.Vector3f h2 = new org.joml.Vector3f((float) (iw / 2), (float) (iw / 2), 0);
                sp.rot.transform(h2);
                sp.tr.set(-h2.x, -h2.y, -h2.z);
            });
            ice.go();
            fx.vfx.after(16, () -> Shapes.line(s0, end, 1.0, (p, t) ->
                    Emit.send(fx, p, Particle.BLOCK, org.bukkit.Material.ICE.createBlockData(), 4, 0.25, 0.25, 0.25, 0.1, Emit.NORMAL)));
        }
        // 감아 도는 조각 (6틱 동안 앞으로 흘러간다)
        Particle spiral = switch (id) {
            case "frost" -> Particle.SNOWFLAKE;
            case "flame", "sun" -> Particle.FLAME;
            default -> voidish ? Particle.REVERSE_PORTAL : Particle.END_ROD;
        };
        fx.vfx.every(0, 2, 6, i -> {
            for (double t = 0.8; t < len; t += 0.45) {
                double a = t * 1.8 + i * 0.9;
                Location q = fr.point(start, Math.cos(a) * w * 0.85, Math.sin(a) * w * 0.85, t);
                Emit.send(fx, q, spiral, null, 1, 0, 0, 0, 0, Emit.NORMAL);
                if (id.equals("frost") && ((int) (t / 0.45)) % 3 == 0)
                    Emit.send(fx, q, Particle.BLOCK, org.bukkit.Material.PACKED_ICE.createBlockData(), 1, 0.05, 0.05, 0.05, 0, Emit.DETAIL);
            }
        });
        // 수직 고리 셋이 광선을 따라 퍼진다
        for (int i = 1; i <= 3; i++) {
            Location q = start.clone().add(dir.clone().multiply(len * i / 4.0));
            int d = i;
            fx.vfx.after(d, () -> {
                Sprite rg = Kit.flat(fx, "ring", q, 0.3, Shapes.Frame.normal(dir), k).life(8);
                rg.decal = false;
                rg.scaleTo(1, 4, (0.9 + w) / Geo.FLAT_HALF, 1, (0.9 + w) / Geo.FLAT_HALF);
                rg.go();
            });
        }
        // 끝: 속성 폭발
        Kit.star(fx, end, 2.0, 6, k).go();
        Location g = Kit.groundOrNull(end);
        boolean onGround = g != null && end.getY() - g.getY() < 2;
        if (onGround) Kit.shock(fx, g.clone().add(0, 0.03, 0), 0.3, 2.2, 3, 10, k).go();
        switch (id) {
            case "frost" -> {
                if (onGround) Kit.iceSpikes(fx, g, 1.3, 5, 16);
                Emit.send(fx, end, Particle.SNOWFLAKE, null, 24, 0.6, 0.6, 0.6, 0.12, Emit.NORMAL);
            }
            case "flame", "sun" -> {
                if (onGround) Pieces.fireSheets(fx, g, 1.0, 4, 2.2, 12, k);
                Emit.send(fx, end, Particle.LAVA, null, 6, 0.5, 0.3, 0.5, 0, Emit.NORMAL);
            }
            default -> Kit.accent(fx, end, 1.5);
        }
        fx.impactSounds(end);
    }

    /**
     * 날아가는 참격: 광선 판정(즉발)은 그대로 두고, 커다란 초승달이 광선 길을 따라 날아간다.
     * 가는 빛줄기 하나로는 '참격'이 아니라 디버그 선처럼 보였다. 지나간 자리에는 칼선(cut)이 잠깐 남는다.
     * scale = 초승달 크기 배율, roll = 기울기(옆에서도 납작하지 않게), echo = 반대로 기운 두 번째 초승달
     */
    static int slashWave(CastFx fx, Ev.Beam e, CastFx.Cols k, double scale, double roll, boolean echo) {
        Location start = e.start();
        Vector dir = e.dir().clone().normalize();
        double len = start.distance(e.end());
        if (len < 2) return 1;
        double r = Math.max(1.6, e.width() * 1.3) * scale;
        Location s0 = start.clone().add(dir.clone().multiply(1.0)).add(0, -0.3, 0);
        double travel = Math.max(1, len - 1.0 - r * 0.5);
        int T = (int) Math.max(3, Math.min(7, Math.round(travel / 2.6)));
        Shapes.Frame base = Shapes.Frame.along(dir);
        String model = MeleeFx.slashModel(fx, 160, k);
        Vector move = dir.clone().multiply(travel);
        long t0 = fx.vfx.tick;
        // 입자 판: 제자리에 남는 초승달 대신, 매 틱 앞으로 옮겨 그리는 입자 검기
        if (!fx.vfx.spritesOn()) {
            int a = fx.aud;
            fx.vfx.every(0, 1, T + 1, t -> fx.with(a, () -> {
                Location p = s0.clone().add(move.clone().multiply(Math.min(1, (t + 1) / (double) T)));
                Kit.slashDust(fx, p, base.roll(roll), r * 0.75, k, 1);
                if (echo) Kit.slashDust(fx, p.clone().subtract(dir.clone().multiply(0.6)), base.roll(-roll * 0.75), r * 0.6, k.swap(), 1);
            }));
        }
        for (int i = 0; i < (echo && fx.vfx.spritesOn() ? 2 : fx.vfx.spritesOn() ? 1 : 0); i++) {
            int d = i;
            double rl = i == 0 ? roll : -roll * 0.75;
            CastFx.Cols kk = i == 0 ? k : k.swap();
            double sr = r / Geo.FLAT_HALF * (d == 0 ? 1 : 0.82);
            fx.vfx.after(d, () -> {
                Sprite s = Kit.slash(fx, model, s0, base.roll(rl), r * 0.6, T + 6 - d, kk).reveal(4.0).slashDir(rl >= 0 ? 1 : -1);
                s.follow(() -> s0.clone().add(move.clone().multiply(Math.min(1, (fx.vfx.tick - t0) / (double) T))), 1);
                s.key(1, Math.max(1, T - d), sp -> sp.sc.set((float) sr, 1f, (float) sr));
                s.go();
                if (d == 0) Kit.hallmark(fx, s);
            });
        }
        // 지나간 자리: 속성 물결 (공허는 거꾸로 솟는 차원 입자 + 검은 먼지)
        boolean voidish = fx.pal.id().equals("abyss") || fx.pal.id().equals("doom") || fx.pal.id().equals("shadow");
        fx.vfx.every(0, 1, T + 1, t -> {
            double f = Math.min(1, (t + 1) / (double) T);
            Location p = s0.clone().add(move.clone().multiply(f));
            Shapes.arc(p, base.roll(roll), r * 0.8, -1.1, 1.1, 7, (q, u) -> {
                if (voidish) {
                    Emit.send(fx, q, Particle.REVERSE_PORTAL, null, 2, 0.1, 0.1, 0.1, 0.02, Emit.NORMAL);
                    if (u > 0.3 && u < 0.7) Emit.dust(fx, q, Color.fromRGB(0x1a0028), 1.4, Emit.DETAIL);
                } else {
                    Emit.spec(fx, fx.pal.spark(), q, 1, 0.05, 0.02, Emit.NORMAL);
                }
            });
        });
        Location endP = s0.clone().add(move);
        fx.vfx.after(Math.max(1, T / 2), () -> MeleeFx.cut(fx, s0, endP, 0.5 * scale, T + 8, k));
        fx.vfx.after(T, () -> {
            Kit.star(fx, endP, 1.2 * scale, 5, k).go();
            Kit.accent(fx, endP, 1.0 * scale);
        });
        fx.sound(start, "item.trident.riptide_1", 0.6, 1.4);
        return T;
    }

    /** 시전자 화면용 광선: 오른손(+0.45 옆, -0.35 아래)에서 1.5칸 앞부터 끝점까지, 굵기 60% + 4칸 앞부터 바깥 빛 */
    static void handBeam(CastFx fx, Location eye, Vector dir, Location end, double w, String model, CastFx.Cols k) {
        Vector side = fx.handSide(dir);
        Location hand = eye.clone().add(side.multiply(0.45)).add(0, -0.35, 0).add(dir.clone().multiply(1.5));
        Vector d = end.toVector().subtract(hand.toVector());
        double len = d.length();
        if (len < 1) return;
        d.normalize();
        Sprite s = Kit.beam(fx, model, hand, d, len, w * 0.6 * 0.7, 10, k).view(Sprite.View.ONLY);
        s.go();
        if (len > 4) {
            Location h2 = hand.clone().add(d.clone().multiply(2.5));
            String om = fx.vfx.models.pick(model + "_dim", "beam_dim", model);
            Kit.beam(fx, om, h2, d, len - 2.5, w * 0.9, 9, k.swap()).view(Sprite.View.ONLY).go();
        }
    }

    static void beamAccent(CastFx fx, Location start, Vector dir, double len, double w) {
        String id = fx.pal.id();
        switch (id) {
            case "frost" -> {
                for (int i = 1; i <= 4; i++) {
                    Location p = start.clone().add(dir.clone().multiply(len * i / 5));
                    Emit.send(fx, p, Particle.BLOCK, Material.ICE.createBlockData(), 8, 0.2, 0.2, 0.2, 0.1, Emit.NORMAL);
                    Emit.send(fx, p, Particle.SNOWFLAKE, null, 4, 0.2, 0.2, 0.2, 0.05, Emit.DETAIL);
                }
            }
            case "flame", "sun" -> Shapes.line(start, start.clone().add(dir.clone().multiply(len)), 0.8,
                    (p, t) -> Emit.send(fx, p, Particle.FLAME, null, 2, w * 0.3, w * 0.3, w * 0.3, 0.02, Emit.DETAIL));
            case "abyss", "doom" -> Shapes.line(start, start.clone().add(dir.clone().multiply(len)), 0.8,
                    (p, t) -> Emit.send(fx, p, Particle.REVERSE_PORTAL, null, 3, w * 0.5, w * 0.5, w * 0.5, 0.05, Emit.DETAIL));
            case "storm" -> {
                List<Location> b = Shapes.bolt(start, start.clone().add(dir.clone().multiply(len)), (int) Math.max(4, len / 2), 0.5, Kit.rnd());
                for (int i = 0; i + 1 < b.size(); i++) Emit.line(fx, b.get(i), b.get(i + 1), 0.35, fx.b(), 0.7, Emit.DETAIL);
            }
            default -> { }
        }
    }

    // ------------------------------------------------------------------ 연쇄 번개

    static void chain(CastFx fx, Ev.Chain ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        Location from = ev.from(), to = ev.to();
        int r = fx.rank();
        if (r == 0) {
            Emit.spec(fx, fx.pal.spark(), to, 4, 0.2, 0.1, Emit.NORMAL);
            return;
        }
        double len = from.distance(to);
        int segs = (int) Math.max(3, len / 1.2);
        drawBolt(fx, from, to, segs, 0.3, k, 0);
        Emit.send(fx, to, Particle.ELECTRIC_SPARK, null, fx.n(10), 0.25, 0.25, 0.25, 0.25, Emit.NORMAL);
        if (r >= 2) {
            if (fx.starSlot()) Kit.star(fx, to, 0.9, 4, k).go();
            for (int i = 1; i <= 2; i++) fx.vfx.after(i * 2, () -> drawBolt(fx, from, to, segs, 0.35, k, 1));
            fx.sound(to, "entity.lightning_bolt.impact", 0.3, 1.2 + 0.1 * ev.n());
        }
        if (r >= 4) {
            for (int i = 0; i < 2; i++) {
                Location mid = from.clone().add(to.toVector().subtract(from.toVector()).multiply(Kit.rnd().nextDouble(0.3, 0.7)));
                Location tip = mid.clone().add(Kit.rnd().nextGaussian() * 1.2, Kit.rnd().nextGaussian() * 0.8, Kit.rnd().nextGaussian() * 1.2);
                List<Location> b = Shapes.bolt(mid, tip, 3, 0.3, Kit.rnd());
                for (int j = 0; j + 1 < b.size(); j++) Emit.line(fx, b.get(j), b.get(j + 1), 0.3, k.b(), 0.6, Emit.DETAIL);
            }
        }
    }

    /** 흰 심 + 속성색 겉 번개 */
    static void drawBolt(CastFx fx, Location a, Location b, int segs, double jitter, CastFx.Cols k, int pri) {
        List<Location> pts = Shapes.bolt(a, b, segs, jitter, Kit.rnd());
        int p = pri == 0 ? Emit.NORMAL : Emit.DETAIL;
        for (int i = 0; i + 1 < pts.size(); i++) {
            Emit.line(fx, pts.get(i), pts.get(i + 1), 0.28, k.a(), 1.0, p);
            if (pri == 0) Emit.line(fx, pts.get(i), pts.get(i + 1), 0.4, Color.WHITE, 0.5, Emit.DETAIL);
        }
    }

    static Display.Billboard center() {
        return Display.Billboard.CENTER;
    }
}
