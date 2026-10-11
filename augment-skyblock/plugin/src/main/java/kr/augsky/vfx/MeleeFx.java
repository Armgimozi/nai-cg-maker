package kr.augsky.vfx;

import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.List;

/** 베기·돌진·도약·순간이동·맞힘 */
final class MeleeFx {
    private MeleeFx() {}

    static String slashModel(CastFx fx, double angleDeg, CastFx.Cols k) {
        Models m = fx.vfx.models;
        if (angleDeg >= 300) {
            String w = m.pick("slash_wide");
            if (w != null) return w;
        }
        if (k.rainbow()) {
            String r = m.pick("slash_rainbow");
            if (r != null) return r;
        }
        // 속성 모양이 팩에 있으면 (서리 = 각진 결정 가장자리, 화염 = 넘실대는 불꽃 가장자리, 공허 = 검은 속 + 찢긴 보라 테)
        String sh = Kit.shape(fx);
        if (fx.rank() >= 2 && sh != null) {
            String el = m.pick("slash_" + sh);
            if (el != null) return el;
        }
        return "slash";
    }

    // ------------------------------------------------------------------ 부채꼴 베기

    static void cone(CastFx fx, Ev.Cone ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        Vector dir = ev.dir();
        double half = ev.half(), range = ev.range();
        Location base = ev.base();
        double angleDeg = Math.toDegrees(half * 2);
        Shapes.Frame fr = Shapes.Frame.flat(dir);
        int seq = fx.seq("cone");
        int side = seq % 2 == 0 ? 1 : -1;
        int n = (int) Math.max(8, Math.min(36, range * angleDeg / 22 * Math.min(1.3, fx.dens())));
        // 모든 등급: 칼끝 궤적 (판정 끝 반지름 그대로)
        Shapes.arc(base, fr, range, -half, half, n, (p, t) -> Emit.dust(fx, p, k.a(), 1.15, Emit.NORMAL));
        if (fx.rank() == 0 || fx.tier == Tier.MOB) {
            Location mid = fr.point(base, 0, 0, range * 0.6);
            Emit.send(fx, mid, Particle.SWEEP_ATTACK, null, 2, range * 0.2, 0.05, range * 0.2, 0, Emit.NORMAL);
            return;
        }
        // 섬 등급부터: 빛나는 초승달. 비스듬히(20~30도) 세워 옆에서도 납작해 보이지 않게, 시전마다 반대로 휘두른다
        double roll = (fx.rank() >= 3 ? 30 : 22) * side;
        String model = slashModel(fx, angleDeg, k);
        double r = Math.max(1.6, range);
        // 반대 방향 휘두르기는 판을 뒤집어(180도 굴림) 그림을 좌우로 바꾼다
        Shapes.Frame f0 = fr.roll(side > 0 ? roll : 180 + roll).yaw(-30);
        boolean selfView = fx.cp != null;
        Sprite s = swing(fx, model, base, f0, r, fx.rank() >= 3 ? 10 : 8, k, selfView ? Sprite.View.HIDE : Sprite.View.AUTO);
        Kit.hallmark(fx, s);
        // 시전자 1인칭: 비스듬한 판은 눈높이를 지나 화면을 가르는 선으로만 보인다.
        // 시전자에게는 조금 낮추고 앞을 살짝 든 판을 따로 보여 준다 (조준점 아래로 휘는 초승달)
        if (selfView) swing(fx, model, selfBase(fx, base, r), fr.roll(side > 0 ? 0 : 180).yaw(-30).pitch(side > 0 ? 8 : -8),
                r, fx.rank() >= 3 ? 10 : 8, k, Sprite.View.ONLY);
        // 칼날을 따라 미끄러지는 빛줄기
        int streaks = fx.rank() >= 3 ? 10 : 6;
        for (int i = 0; i < streaks; i++) {
            double a = -half + 2 * half * i / Math.max(1, streaks - 1);
            Location p = fr.point(base, Math.sin(a) * range * 0.92, 0, Math.cos(a) * range * 0.92);
            double a2 = a + Math.toRadians(25) * side;
            Location q = fr.point(base, Math.sin(a2) * range * 0.92, 0.1, Math.cos(a2) * range * 0.92);
            Emit.trail(fx, p, q, k.b(), 4, Emit.DETAIL);
        }
        fx.castSounds(base);
        if (fx.rank() >= 2) {
            CastFx.Cols inner = k.swap();
            fx.vfx.after(1, () -> {
                Sprite s2 = Kit.slash(fx, model, base.clone().add(0, 0.04, 0), fr.roll(roll + 6 * side).yaw(-10 * side), range * 0.72, 7, inner)
                        .view(selfView ? Sprite.View.HIDE : Sprite.View.AUTO).slashDir(side);
                s2.go();
                if (selfView) Kit.slash(fx, model, base.clone().add(0, -0.36, 0), fr.yaw(-10 * side).pitch(8), range * 0.72, 7, inner)
                        .view(Sprite.View.ONLY).slashDir(side).go();
            });
            for (int i = 0; i < 3; i++) {
                double a = -half + 2 * half * (i + 0.5) / 3;
                Kit.accent(fx, fr.point(base, Math.sin(a) * range * 0.8, 0, Math.cos(a) * range * 0.8), 0.8);
            }
        }
        if (fx.rank() >= 3) {
            String dm = fx.vfx.models.dim(model, 1);
            fx.vfx.after(2, () -> Kit.slash(fx, dm != null ? dm : model, base.clone().add(0, -0.03, 0), fr.roll(-roll * 0.5).yaw(12 * side),
                    range * 1.1, 8, k).view(selfView ? Sprite.View.HIDE : Sprite.View.AUTO).slashDir(side).go());
            for (double a : new double[]{-half, half}) {
                Location tip = fr.point(base, Math.sin(a) * range, 0, Math.cos(a) * range);
                Emit.spec(fx, fx.pal.spark(), tip, 4, 0.15, 0.08, Emit.NORMAL);
            }
            fx.sound(base, "item.mace.smash_air", 0.6, 0.7);
        }
        if (fx.rank() >= 4) {
            // 남는 반짝임 호가 천천히 떠오른다
            fx.vfx.every(2, 3, 4, i -> Shapes.arc(base.clone().add(0, 0.15 * (i + 1), 0), fr, range * 0.95, -half, half, 8,
                    (p, t) -> Emit.dust(fx, p, k.rainbow() ? Palette.hue(t + i * 0.1) : k.b(), 0.8, Emit.DETAIL)));
        }
    }

    /**
     * 시전자용 초승달 높이: 반지름이 크면 판이 조준점 높이를 지나가므로 발밑 가까이 내린다
     * (반지름 r 앞의 판이 눈 아래 D 에 있으면 atan(D/r) 만큼 아래에 보인다).
     */
    static Location selfBase(CastFx fx, Location base, double r) {
        Location feet = fx.caster.getLocation();
        double lift = r >= 6 ? 0.25 : r >= 4 ? 0.5 : 0.68;
        Location l = base.clone();
        l.setY(feet.getY() + lift);
        return l;
    }

    /** 휘두르는 초승달 한 장: 넘김 그림(왼→오) + 칼끝 방향으로 36도 돌며 커진다 */
    static Sprite swing(CastFx fx, String model, Location base, Shapes.Frame f0, double r, int life, CastFx.Cols k, Sprite.View view) {
        boolean wipe = "slash".equals(model) && fx.vfx.models.has("slash_w3");
        Sprite s = Kit.slash(fx, wipe ? "slash_w1" : model, base, f0, r * 0.85, life, k).view(view).slashDir(1);
        double sr = r / Geo.FLAT_HALF;
        s.key(1, 3, sp -> {
            sp.rot.rotateY((float) Math.toRadians(36));
            sp.sc.set((float) sr, 1f, (float) sr);
        });
        if (wipe) {
            s.swap(1, "slash_w2");
            s.swap(2, "slash_w3");
            s.swap(3, "slash");
        }
        s.go();
        return s;
    }

    // ------------------------------------------------------------------ 돌진

    static Track dash(CastFx fx, Ev.Dash ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        Vector dir = ev.dir().clone().setY(0);
        if (dir.lengthSquared() < 1e-6) dir = new Vector(0, 0, 1);
        dir.normalize();
        Vector d0 = dir;
        Location start = ev.start().clone();
        List<Location> path = new ArrayList<>();
        Vector sideV = Shapes.Frame.flat(dir).side();
        return new Track() {
            @Override
            public void tick(Location pos, Vector vel) {
                path.add(pos.clone());
                double[] hs = fx.rank() == 0 ? new double[]{0} : new double[]{-0.5, 0.05, 0.6};
                for (double h : hs) {
                    double so = (h == 0.05 ? 0 : (h < 0 ? 0.25 : -0.25));
                    Location to = pos.clone().add(0, h, 0).add(sideV.clone().multiply(so));
                    Location from = to.clone().subtract(d0.clone().multiply(2.2));
                    Emit.streak(fx, from, to, h > 0 ? k.b() : k.a(), fx.rank() >= 2 ? 3 : 2, 3, Emit.NORMAL);
                }
                if (fx.rank() >= 2) {
                    Location feet = pos.clone().add(0, -0.85, 0);
                    Kit.accent(fx, feet, 0.5);
                }
            }

            @Override
            public void end(Location at, boolean impact) {
                Location endFeet = Kit.ground(at.clone());
                if (fx.rank() >= 1) Kit.ring(fx, endFeet.clone().add(0, 0.03, 0), 0.4, 1.6, 3, 8, k, null).go();
                if (fx.rank() >= 2 && !path.isEmpty()) {
                    Location a = start.clone().add(0, 1.0, 0), b = path.get(path.size() - 1).clone().add(0, 0.1, 0);
                    int delay = fx.rank() >= 3 ? 2 : 0;
                    fx.vfx.after(delay, () -> cut(fx, a, b, 0.6, 8, k));
                    // 지나간 길에 남는 속성 자국
                    List<Location> trail = new ArrayList<>(path);
                    fx.vfx.every(1, 3, 4, i -> {
                        for (int j = 0; j < trail.size(); j += 2) {
                            Location g = trail.get(j).clone().add(0, -0.8, 0);
                            Emit.dust(fx, g, k.a(), 1.0, Emit.DETAIL);
                        }
                    });
                }
                if (fx.rank() >= 4 && fx.cp != null && path.size() >= 3) afterimages(fx, path);
            }
        };
    }

    /** 길을 따라 늘인 칼선 (cut 모델: 앞(Z)으로 길이 3, 폭 0.5 의 엇갈린 두 판) */
    static Sprite cut(CastFx fx, Location a, Location b, double width, int life, CastFx.Cols k) {
        Vector d = b.toVector().subtract(a.toVector());
        double len = d.length();
        if (len < 0.5) return null;
        Shapes.Frame fr = Shapes.Frame.along(d);
        Location mid = a.clone().add(d.clone().multiply(0.5));
        double sl = len / 3.0, sw = width / 0.5;
        Sprite s = Sprite.item(fx, "cut", mid).frame(fr).size(sw * 2.2, sw * 2.2, sl).radius(width).life(life).tint(k).end(Sprite.End.THIN, 4);
        s.segLen = 0;
        s.key(1, 2, sp -> sp.sc.set((float) sw, (float) sw, (float) sl));
        s.fallback(() -> Shapes.line(a, b, 0.3, (p, t) -> Emit.dust(fx, p, t > 0.5 ? k.b() : k.a(), 1.2, Emit.NORMAL)));
        s.go();
        Kit.hallmark(fx, s);
        return s;
    }

    /** 프리즘: 시전자가 들고 있던 무기의 잔상 셋이 길 위에 남았다가 사라진다 */
    static void afterimages(CastFx fx, List<Location> path) {
        ItemStack held = fx.cp.getInventory().getItemInMainHand();
        if (held == null || held.getType() == Material.AIR) return;
        for (int i = 1; i <= 3; i++) {
            Location p = path.get(Math.min(path.size() - 1, path.size() * i / 4)).clone();
            Sprite s = Sprite.stack(fx, held.clone(), p).size(0.9).life(10).end(Sprite.End.SHRINK, 8);
            s.rot.rotateY((float) Math.toRadians(-p.getYaw()));
            s.go();
        }
    }

    // ------------------------------------------------------------------ 도약

    static Track leap(CastFx fx, Ev.Leap ev) {
        CastFx.Cols k = fx.cols(ev.yaml());
        Location st = Kit.ground(ev.start());
        if (fx.rank() >= 1) {
            Kit.dustRing(fx, st.clone().add(0, 0.1, 0), 1.2, k.a(), 1.2, Emit.NORMAL);
            Kit.accent(fx, st.clone().add(0, 0.2, 0), 0.8);
        }
        if (fx.rank() >= 2) {
            // 박차고 오르는 순간: 발밑 충격 고리 + 위로 뻗는 빛줄기
            Kit.ring(fx, st.clone().add(0, 0.03, 0), 0.3, 1.8, 3, 7, k, null).go();
            Pieces.rays(fx, st.clone().add(0, 0.2, 0), fx.n(8), 2.2, k, 5, true);
        }
        return new Track() {
            int t;
            Location prev = ev.start().clone().add(0, 0.6, 0);

            @Override
            public void tick(Location pos, Vector vel) {
                t++;
                if (fx.rank() >= 2) {
                    // 날아가는 몸을 따라 속성 꼬리 (불꽃·눈송이·공허 입자 + 색 빛줄기)
                    Location body = pos.clone().add(0, 0.6, 0);
                    Emit.streak(fx, prev, body, k.a(), 3, 5, Emit.NORMAL);
                    Emit.spec(fx, fx.pal.spark(), body, fx.n(3), 0.25, 0.02, Emit.NORMAL);
                    prev = body;
                }
                if (fx.rank() >= 1 && t % 2 == 0) {
                    double a = t * 0.9;
                    for (int i = 0; i < 2; i++) {
                        double aa = a + Math.PI * i;
                        Emit.dust(fx, pos.clone().add(Math.cos(aa) * 0.6, 0.4, Math.sin(aa) * 0.6), i == 0 ? k.a() : k.b(), 1.1, Emit.DETAIL);
                    }
                }
            }

            @Override
            public void end(Location at, boolean impact) {
                if (fx.rank() < 2) return;
                Location g = Kit.ground(at).add(0, 0.04, 0);
                Kit.shock(fx, g, 0.6, 2.6, 3, 10, k).go();
                Material m = Kit.groundMaterial(g, Material.STONE);
                Emit.send(fx, g.clone().add(0, 0.2, 0), Particle.DUST_PILLAR, m.createBlockData(), 16, 0.8, 0.1, 0.8, 0.2, Emit.NORMAL);
                Kit.debris(fx, g, fx.tier.debris, 1.0, fx.pal.debris().length > 0 ? fx.pal.debris()[0] : null);
                Kit.afterglow(fx, g, 2.4, 30, k);
            }
        };
    }

    // ------------------------------------------------------------------ 순간이동

    static void blink(CastFx fx, Ev.Blink ev) {
        if (fx.rank() < 1) return;
        CastFx.Cols k = fx.cols(ev.yaml());
        Location from = ev.from().clone().add(0, 1, 0), to = ev.to().clone().add(0, 1, 0);
        Emit.streak(fx, from, to, k.a(), 5, 3, Emit.NORMAL);
        Kit.dustRing(fx, ev.from().clone().add(0, 0.1, 0), 0.9, k.a(), 1.0, Emit.NORMAL);
        Kit.dustRing(fx, ev.to().clone().add(0, 0.1, 0), 0.9, k.b(), 1.0, Emit.NORMAL);
        if (fx.rank() >= 2) {
            // 떠난 자리에 잠깐 남는 실루엣
            Location f0 = ev.from().clone();
            fx.vfx.every(0, 2, 4, i -> {
                for (double y = 0.1; y < 1.9; y += 0.25) {
                    double w = y > 1.4 ? 0.18 : 0.28;
                    Emit.dust(fx, f0.clone().add(0, y, 0), k.a(), 0.9, 2, w, Emit.DETAIL);
                }
            });
            Kit.converge(fx, from, 1.6, 6, k.b(), 6, Emit.DETAIL);
            Kit.accent(fx, to, 1.0);
        }
        if (fx.rank() >= 3) {
            portalSlit(fx, ev.from(), 8, k, Sprite.View.AUTO);
            portalSlit(fx, ev.to(), 8, k, Sprite.View.HIDE);
        }
    }

    /** 세로로 선 칼선 = 차원 틈 */
    static void portalSlit(CastFx fx, Location feet, int life, CastFx.Cols k, Sprite.View view) {
        Location c = feet.clone().add(0, 1.0, 0);
        Vector look = fx.caster.getLocation().getDirection().setY(0);
        if (look.lengthSquared() < 1e-6) look = new Vector(0, 0, 1);
        // 칼선(cut)을 세로로 세운다: 앞 축 = 위
        Shapes.Frame fr = Shapes.Frame.along(new Vector(0, 1, 0));
        Sprite s = Sprite.item(fx, "cut", c).frame(fr).size(0.05, 0.05, 0.75).radius(1).life(life).tint(k)
                .view(view).end(Sprite.End.THIN, 3);
        s.key(1, 2, sp -> sp.sc.set(1.3f, 1.3f, 0.75f));
        s.fallback(() -> Shapes.line(c.clone().add(0, -1, 0), c.clone().add(0, 1, 0), 0.25, (p, t) -> Emit.dust(fx, p, k.a(), 1.1, Emit.NORMAL)));
        s.go();
    }

    // ------------------------------------------------------------------ 맞힘

    static void hit(CastFx fx, Ev.Hit ev) {
        LivingEntity t = ev.target();
        if (t == null || !t.isValid()) return;
        double w = Math.max(0.4, t.getWidth()), h = t.getHeight();
        Location c = t.getLocation().add(0, h * 0.55, 0);
        Vector toward = ev.origin().toVector().subtract(c.toVector()).setY(0);
        if (toward.lengthSquared() < 1e-6) toward = new Vector(0, 0, 1);
        toward.normalize();
        Location face = c.clone().add(toward.multiply(w * 0.5));
        if (ev.tick()) {
            Emit.spec(fx, fx.pal.spark(), face, 1, 0.1, 0.02, Emit.DETAIL);
            return;
        }
        int r = fx.rank();
        if (r == 0) {
            Emit.send(fx, face, Particle.CRIT, null, 4, 0.15, 0.15, 0.15, 0.2, Emit.NORMAL);
            return;
        }
        // END_ROD·FIREWORK 처럼 3초씩 떠 있는 입자는 맞을 때마다 쌓여 바닥이 흰 점투성이가 된다:
        // 짧은 빛줄기(TRAIL)로 튀기고 진짜 입자는 두어 개만
        if (Emit.lingers(fx.pal.spark().particle())) {
            Pieces.rays(fx, face, r >= 2 ? 6 : 4, 0.9 + 0.2 * r, fx.cols(), 5, false);
        } else {
            Emit.spec(fx, fx.pal.spark(), face, r >= 2 ? 8 : 6, 0.2, 0.08, Emit.NORMAL);
        }
        if (r >= 2) Emit.dust(fx, face, fx.a(), 1.3, 5, 0.2, Emit.DETAIL);
        boolean bossMobOnPlayer = fx.mob() && t instanceof Player;
        if (r >= 3 && !bossMobOnPlayer && fx.starSlot()) {
            CastFx.Cols k = fx.cols();
            double size = Math.min(1.2, w * 0.5 + 0.2);
            Kit.star(fx, face, size, 4, k).go();
        }
        if (r >= 4) Pieces.rays(fx, face, 5, 1.6, fx.prism() && fx.pal.rainbow() ? PrismSigs.rainbow(fx) : fx.cols(), 6, false);
    }

    static Color white() {
        return Color.WHITE;
    }
}
