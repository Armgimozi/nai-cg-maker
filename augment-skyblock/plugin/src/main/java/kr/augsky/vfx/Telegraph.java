package kr.augsky.vfx;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.entity.Display;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;

/**
 * 몬스터 기술 예고. 모든 몬스터가 같은 경고 말투를 쓴다:
 * 진한 주황빨강 테두리 + 검은 테 + 위험 눈금, 안쪽은 차오르는 진행 표시, 속성색은 얇은 안쪽 띠로만.
 * 마지막 4틱은 흰색·빨강으로 깜빡인다. 서리 둥지(얼음 바닥)·공허 둥지(보라 바닥)에서도 읽히게 하려고 속성색을 쓰지 않는다.
 * 예고 입자는 예산에서 빠지지 않고(TELE), 땅 높이를 점마다 따라간다.
 */
final class Telegraph {
    private Telegraph() {}

    static final Color HAZ = Color.fromRGB(0xff3b1f);
    static final Color HAZ_HOT = Color.fromRGB(0xffd21a);
    static final Color BLACK = Color.fromRGB(0x000000);

    static void windup(CastFx fx, Ev.Windup ev) {
        int ticks = ev.ticks();
        Supplier<List<Footprint>> fp = ev.footprints();
        List<Footprint> first = fp.get();
        if (first.isEmpty()) return;
        boolean boss = fx.tier == Tier.BOSS_MOB;
        if (fx.vfx.debug()) {
            fx.vfx.log("tele", "telegraph " + fx.skill + " start tick=" + fx.vfx.tick + " ticks=" + ticks + " shapes=" + first.size());
            fx.vfx.after(ticks, () -> fx.vfx.log("tele", "telegraph " + fx.skill + " end tick=" + fx.vfx.tick));
        }
        for (int i = 0; i < first.size(); i++) {
            int idx = i;
            Supplier<Footprint> one = () -> {
                List<Footprint> l = fp.get();
                return idx < l.size() ? l.get(idx) : null;
            };
            Footprint f = first.get(i);
            switch (f.shape()) {
                case CIRCLE -> circle(fx, one, ticks, boss);
                case LINE -> line(fx, one, ticks, boss);
                case CONE -> cone(fx, one, ticks);
            }
            if (boss) fx.vfx.markTele(f, ticks + 4);
        }
        if (ticks >= 10) bang(fx, ticks, boss);
    }

    /** 원형 예고: 테두리 + 차오르는 안쪽 */
    static void circle(CastFx fx, Supplier<Footprint> fp, int ticks, boolean boss) {
        Footprint f0 = fp.get();
        if (f0 == null) return;
        double r = f0.r();
        Supplier<Location> at = () -> {
            Footprint f = fp.get();
            return f == null ? null : Kit.ground(f.c()).add(0, 0.15, 0);
        };
        Location c0 = at.get();
        List<Sprite> parts = new ArrayList<>();
        boolean fits = Kit.decalFits(c0, r);
        if (boss && fits) {
            CastFx.Cols edge = new CastFx.Cols(HAZ, fx.pal.a(), BLACK, BLACK, false);
            Sprite e = Kit.flat(fx, fx.vfx.models.pick("warn", "ring"), c0, r, Shapes.Frame.FLAT, edge).tele().life(ticks + 1)
                    .end(Sprite.End.NONE).follow(at, 2);
            for (int t = Math.max(1, ticks - 4); t < ticks; t++) {
                boolean hot = (ticks - t) % 2 == 0;
                e.retint(t, hot ? Color.WHITE : HAZ, hot ? HAZ : Color.WHITE, BLACK);
            }
            e.go();
            parts.add(e);
            String fm = fx.vfx.models.pick("warn_fill", "shock_dim", "shock");
            if (fm != null) {
                CastFx.Cols fill = new CastFx.Cols(HAZ, HAZ_HOT, BLACK, BLACK, false);
                Sprite fl = Kit.flat(fx, fm, c0.clone().add(0, -0.01, 0), 0.05, Shapes.Frame.FLAT, fill).tele().life(ticks + 1)
                        .end(Sprite.End.NONE).follow(() -> {
                            Location l = at.get();
                            return l == null ? null : l.add(0, -0.01, 0);
                        }, 2);
                fl.scaleTo(1, Math.max(1, ticks - 1), r / Geo.FLAT_HALF, 1, r / Geo.FLAT_HALF);
                fl.go();
                parts.add(fl);
            }
        }
        // 입자 (팩 없이도 보이고, 모두에게 보이는 기본 예고)
        fx.vfx.every(0, 1, ticks, t -> {
            Footprint f = fp.get();
            if (f == null) return;
            Location c = f.c();
            boolean last = ticks - t <= 4;
            if (t % 3 == 0 || last) edgeRing(fx, c, f.r(), last && t % 2 == 0 ? Color.WHITE : HAZ, 1.3);
            if (t % 2 == 0) {
                double pr = f.r() * Math.min(1, (t + 1) / (double) ticks);
                edgeRing(fx, c, pr, HAZ_HOT, 0.8);
            }
            if (ticks - t <= 6) {
                for (int i = 0; i < 6; i++) {
                    double a = Kit.rnd().nextDouble(Math.PI * 2);
                    Location p = Kit.ground(c.clone().add(Math.cos(a) * f.r(), 0.5, Math.sin(a) * f.r())).add(0, 0.3, 0);
                    Emit.send(fx, p, Particle.ELECTRIC_SPARK, null, 1, 0.05, 0.1, 0.05, 0.05, Emit.TELE);
                }
            }
        });
    }

    /** 테두리 점마다 그 자리 땅 높이에 (울퉁불퉁한 섬에서 묻히지 않게) */
    static void edgeRing(CastFx fx, Location c, double r, Color col, double size) {
        int n = (int) Math.max(12, Math.min(64, Math.PI * 2 * r / 0.6));
        for (Location p : Shapes.around(c, r, n, 0)) {
            Location g = Kit.groundOrNull(p.clone().add(0, 1.0, 0));
            Location q = (g != null && Math.abs(g.getY() - c.getY()) < 3) ? g.add(0, 0.12, 0) : p.add(0, 0.12, 0);
            Emit.dust(fx, q, col, size, Emit.TELE);
        }
    }

    /** 선형 예고 (광선·돌진·빠른 투사체): 실제 높이의 얇은 선 + 땅 위 화살표 띠 */
    static void line(CastFx fx, Supplier<Footprint> fp, int ticks, boolean boss) {
        Footprint f0 = fp.get();
        if (f0 == null) return;
        if (boss && fx.vfx.models.has("warn_line")) {
            // 큰 보스는 눈이 바닥보다 6칸 넘게 높다. 시작점 바로 아래 바닥(깊이 24칸까지)에 깔고, 길이는 수평 거리만큼
            Supplier<Location> at = () -> {
                Footprint f = fp.get();
                if (f == null) return null;
                Location g = Kit.groundBelow(f.c(), 24);
                return g == null ? null : g.add(0, 0.16, 0);
            };
            Location c0 = at.get();
            Vector d = f0.dir().clone().setY(0);
            double flatLen = f0.len() * Math.sqrt(Math.max(0, 1 - f0.dir().getY() * f0.dir().getY()));
            if (c0 != null && d.lengthSquared() > 1e-6 && flatLen > 1) {
                CastFx.Cols col = new CastFx.Cols(HAZ, HAZ_HOT, BLACK, BLACK, false);
                Sprite s = Sprite.item(fx, "warn_line", c0).frame(Shapes.Frame.flat(d)).size(Math.max(0.8, f0.width()), 1, flatLen)
                        .radius(1).tint(col).tele().life(ticks + 1).end(Sprite.End.NONE).follow(at, 2);
                s.decal = true;
                // 방향이 바뀌면 판도 돌린다 (2틱마다)
                for (int t = 2; t < ticks; t += 2) {
                    s.key(t, 2, sp -> {
                        Footprint f = fp.get();
                        if (f == null) return;
                        Vector dd = f.dir().clone().setY(0);
                        if (dd.lengthSquared() > 1e-6) sp.rot.set(Shapes.Frame.flat(dd).quat());
                    });
                }
                s.go();
            }
        }
        fx.vfx.every(0, 2, Math.max(1, ticks / 2), t -> {
            Footprint f = fp.get();
            if (f == null) return;
            boolean last = ticks - t * 2 <= 4;
            Location a = f.c(), b = f.c().clone().add(f.dir().clone().multiply(f.len()));
            Emit.line(fx, a.clone().add(f.dir().clone().multiply(1.2)), b, 0.5, last ? Color.WHITE : HAZ, 0.9, Emit.TELE);
            if (t % 2 == 0) {
                Vector flat = f.dir().clone().setY(0);
                Location gs = Kit.groundBelow(a, 24);
                if (flat.lengthSquared() > 1e-6 && gs != null) {
                    double fl = f.len() * Math.sqrt(flat.lengthSquared());
                    flat.normalize();
                    Vector side = Shapes.Frame.flat(flat).side().multiply(Math.max(0.5, f.width() / 2));
                    for (double s = 1; s < fl; s += 0.8) {
                        Location p = gs.clone().add(flat.clone().multiply(s)).add(0, 1, 0);
                        Location g = Kit.groundOrNull(p);
                        if (g == null) continue;
                        Emit.dust(fx, g.clone().add(side).add(0, 0.12, 0), HAZ, 0.8, Emit.TELE);
                        Emit.dust(fx, g.clone().subtract(side).add(0, 0.12, 0), HAZ, 0.8, Emit.TELE);
                    }
                }
            }
        });
    }

    /** 부채꼴 예고: 호 + 양쪽 모서리 + 쓸고 지나가는 채움선 */
    static void cone(CastFx fx, Supplier<Footprint> fp, int ticks) {
        fx.vfx.every(0, 2, Math.max(1, ticks / 2), t -> {
            Footprint f = fp.get();
            if (f == null) return;
            Shapes.Frame fr = Shapes.Frame.flat(f.dir());
            Location c = Kit.ground(f.c()).add(0, 0.12, 0);
            boolean last = ticks - t * 2 <= 4;
            Color col = last && t % 2 == 0 ? Color.WHITE : HAZ;
            Shapes.arc(c, fr, f.r(), -f.half(), f.half(), (int) Math.max(8, f.r() * f.half() * 4), (p, s) -> Emit.dust(fx, p, col, 1.2, Emit.TELE));
            for (double e : new double[]{-f.half(), f.half()}) {
                Location tip = fr.point(c, Math.sin(e) * f.r(), 0, Math.cos(e) * f.r());
                Emit.line(fx, c, tip, 0.5, col, 1.0, Emit.TELE);
            }
            double prog = Math.min(1, (t * 2 + 2) / (double) ticks);
            Shapes.arc(c, fr, f.r() * prog, -f.half(), f.half(), 8, (p, s) -> Emit.dust(fx, p, HAZ_HOT, 0.8, Emit.TELE));
        });
    }

    /** 머리 위 "!" (팩 없이도 보이는 글자) */
    static void bang(CastFx fx, int ticks, boolean boss) {
        Supplier<Location> head = () -> fx.caster.isValid() ? fx.caster.getLocation().add(0, fx.caster.getHeight() + 0.9, 0) : null;
        Location h = head.get();
        if (h == null) return;
        Component c = Component.text("!", NamedTextColor.YELLOW).decorate(TextDecoration.BOLD);
        double s = boss ? 3.0 : 1.6;
        Sprite t = Sprite.text(fx, c, h).bill(Display.Billboard.CENTER).size(s * 0.4).tele().life(ticks).follow(head, 1).end(Sprite.End.NONE);
        t.offset(0, -0.12 * s, 0);
        t.scaleTo(1, 3, s, s, s);
        for (int i = Math.max(2, ticks - 4); i < ticks; i++) {
            boolean red = (ticks - i) % 2 == 0;
            t.at(i, sp -> {
                if (sp.e instanceof org.bukkit.entity.TextDisplay td)
                    td.text(Component.text("!", red ? NamedTextColor.RED : NamedTextColor.YELLOW).decorate(TextDecoration.BOLD));
            });
        }
        t.go();
    }

    /** 낙하 공격 표시: 떨어질 자리에 위험 고리, 떨어지는 동안 */
    static void dropMarker(CastFx fx, Location ground, double r, int fall) {
        Location g = ground.clone().add(0, 0.15, 0);
        if (fx.tier == Tier.BOSS_MOB && fx.vfx.models.has("warn")) {
            CastFx.Cols edge = new CastFx.Cols(HAZ, HAZ_HOT, BLACK, BLACK, false);
            Sprite s = Kit.flat(fx, "warn", g, r, Shapes.Frame.FLAT, edge).tele().life(fall + 1).end(Sprite.End.NONE);
            s.size(0.3 / Geo.FLAT_HALF, 1, 0.3 / Geo.FLAT_HALF);
            s.scaleTo(1, Math.max(1, fall - 1), r / Geo.FLAT_HALF, 1, r / Geo.FLAT_HALF);
            s.go();
        }
        fx.vfx.every(0, 3, Math.max(1, fall / 3), t -> {
            Kit.dustRing(fx, g.clone().add(0, 0.04, 0), r, t % 2 == 0 ? HAZ : HAZ_HOT, 1.1, Emit.TELE);
        });
    }

    /** 소용돌이가 끝날 때 터질 자리를 소용돌이 내내 채운다 (공허의 아가리) */
    static void vortexEnds(CastFx fx, Ev.Vortex ev) {
        for (Footprint f : ev.ends()) {
            if (f.shape() != Footprint.Shape.CIRCLE) continue;
            Footprint ff = f;
            circle(fx, () -> ff, ev.duration(), fx.tier == Tier.BOSS_MOB);
            if (fx.tier == Tier.BOSS_MOB) fx.vfx.markTele(f, ev.duration() + 4);
        }
    }
}
