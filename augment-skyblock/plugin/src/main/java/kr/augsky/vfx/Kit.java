package kr.augsky.vfx;

import kr.augsky.skill.SkillContext;
import kr.augsky.util.Fx;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Display;
import org.bukkit.util.Vector;
import org.joml.Vector3f;

import java.util.List;
import java.util.concurrent.ThreadLocalRandom;

/** 기본 연출과 전용 연출이 같이 쓰는 조각·입자 묶음 */
public final class Kit {
    private Kit() {}

    static final Color WHITE = Color.WHITE;

    static ThreadLocalRandom rnd() {
        return ThreadLocalRandom.current();
    }

    // ------------------------------------------------------------------ 바닥

    /** l 바로 아래 바닥 높이 (l 보다 1칸 위부터 4칸 아래까지). 못 찾으면 null */
    public static Location groundOrNull(Location l) {
        World w = l.getWorld();
        if (w == null) return null;
        int y0 = (int) Math.floor(l.getY() + 1);
        for (int i = 0; i <= 5; i++) {
            Block b = w.getBlockAt(l.getBlockX(), y0 - i, l.getBlockZ());
            if (b.getType().isSolid() && !b.isPassable()) {
                Location g = l.clone();
                g.setY(y0 - i + 1);
                return g;
            }
        }
        return null;
    }

    /** l 아래로 depth 칸까지 내려가며 찾은 바닥 (높이 떠 있는 큰 보스의 눈 아래 등). 못 찾으면 null */
    public static Location groundBelow(Location l, int depth) {
        World w = l.getWorld();
        if (w == null) return null;
        int y0 = (int) Math.floor(l.getY() + 1);
        for (int i = 0; i <= depth; i++) {
            Block b = w.getBlockAt(l.getBlockX(), y0 - i, l.getBlockZ());
            if (b.getType().isSolid() && !b.isPassable()) {
                Location g = l.clone();
                g.setY(y0 - i + 1);
                return g;
            }
        }
        return null;
    }

    public static Location ground(Location l) {
        Location g = groundOrNull(l);
        return g != null ? g : l.clone();
    }

    /** 큰 바닥 문양이 울퉁불퉁한 섬에서 묻히거나 뜨지 않는지 (가장자리 8점 중 3점 넘게 1칸 이상 어긋나면 안 맞음) */
    public static boolean decalFits(Location c, double r) {
        int bad = 0;
        for (Location p : Shapes.around(c, Math.max(0.8, r * 0.9), 8, 0)) {
            Location g = groundOrNull(p);
            if (g == null || Math.abs(g.getY() - c.getY()) > 1.0) bad++;
        }
        return bad <= 3;
    }

    /** 파편으로 쓸 땅 블록. 상자·표지판·반블록처럼 표시 블록으로 이상하게 보이는 것은 팔레트 재질로 */
    static Material groundMaterial(Location at, Material fallback) {
        Location g = groundOrNull(at);
        if (g == null) return fallback;
        Block b = g.clone().add(0, -1, 0).getBlock();
        Material m = b.getType();
        if (!m.isSolid() || !m.isOccluding() || b.getState() instanceof org.bukkit.block.TileState) return fallback;
        return m;
    }

    // ------------------------------------------------------------------ 조각 (팩 모델)

    /** 판 모양 조각. 반지름 r, 좌표계 fr */
    public static Sprite flat(CastFx fx, String model, Location c, double r, Shapes.Frame fr, CastFx.Cols k) {
        double s = r / Geo.FLAT_HALF;
        Sprite sp = Sprite.item(fx, model, c).frame(fr).size(s, 1, s).radius(r);
        if (k != null) sp.tint(k);
        return sp;
    }

    /** 속성 모양 이름 (팩의 *_frost / *_flame / *_void 변형). 없으면 null */
    static String shape(CastFx fx) {
        return switch (fx.pal.id()) {
            case "frost" -> "frost";
            case "flame", "sun" -> "flame";
            // 종말(doom)은 검은 심 고리를 쓰지 않는다: 작은 낙하 충격마다 검은 바퀴 자국처럼 남았다
            case "abyss", "shadow", "ender" -> "void";
            default -> null;
        };
    }

    /** 바닥 고리. r0 → r1 로 ticks 동안 퍼진다. 균열 등급부터 속성 모양 고리(얼음 결정·불꽃·찢긴 공허) */
    public static Sprite ring(CastFx fx, Location c, double r0, double r1, int ticks, int life, CastFx.Cols k, String model) {
        String m = model;
        if (m == null) {
            String sh = shape(fx);
            if (k.rainbow() && fx.vfx.models.has("ring_rainbow")) m = "ring_rainbow";
            else if (fx.rank() >= 2 && sh != null && fx.vfx.models.has("ring_" + sh)) m = "ring_" + sh;
            else m = "ring";
        }
        Sprite s = flat(fx, m, c, Math.max(0.05, r0), Shapes.Frame.FLAT, k).life(life);
        if (r1 != r0) s.scaleTo(1, Math.max(1, ticks), r1 / Geo.FLAT_HALF, 1, r1 / Geo.FLAT_HALF).radius(r1);
        int aud = fx.aud;
        s.fallback(() -> {
            int a = fx.aud;
            if (r1 == r0 || ticks <= 1) dustRing(fx, c, r1, k.a(), 1.3, Emit.NORMAL);
            else fx.vfx.every(0, 1, Math.min(ticks, 10), i -> fx.with(a, () ->
                    dustRing(fx, c, r0 + (r1 - r0) * (i + 1) / Math.min(ticks, 10.0), k.a(), 1.2, Emit.NORMAL)));
        });
        return s;
    }

    public static Sprite shock(CastFx fx, Location c, double r0, double r1, int ticks, int life, CastFx.Cols k) {
        // 충격파 넘김 그림 (뜨거움 → 흩어짐)이 있으면 쓴다
        boolean flip = fx.vfx.models.has("shock_f3");
        String m = flip ? "shock_f1" : fx.vfx.models.pick("shock", "ring");
        Sprite s = flat(fx, m, c, Math.max(0.05, r0), Shapes.Frame.FLAT.yaw(rnd().nextDouble(360)), k).life(life);
        if (flip) {
            s.swap(Math.max(1, life * 2 / 5), "shock_f2");
            s.swap(Math.max(2, life * 7 / 10), "shock_f3");
            s.end(Sprite.End.FADE, 2);
        }
        if (r1 != r0) s.scaleTo(1, Math.max(1, ticks), r1 / Geo.FLAT_HALF, 1, r1 / Geo.FLAT_HALF).radius(r1);
        s.fallback(() -> {
            dustRing(fx, c, r1 * 0.7, k.b(), 1.0, Emit.DETAIL);
            dustRing(fx, c, r1, k.a(), 1.4, Emit.NORMAL);
        });
        return s;
    }

    /**
     * 마법진. 바깥 원 + 반대로 도는 안쪽 원. spin 은 초당 도.
     * 시전자 발밑에 까는 마법진은 시전자에게 어지럽지 않게 따로 느린 흐린 판을 보여 준다 (selfCopy).
     */
    public static Sprite[] circle(CastFx fx, Location c, double r, int life, CastFx.Cols k, double spinPerSec, boolean inner,
                                  Sprite.View view) {
        String m = k.rainbow() ? fx.vfx.models.pick("circle_rainbow", "circle") : "circle";
        Sprite outer = flat(fx, m, c, 0.2, Shapes.Frame.FLAT, k).life(life).view(view);
        outer.scaleTo(1, 5, r / Geo.FLAT_HALF, 1, r / Geo.FLAT_HALF).radius(r);
        spinOver(outer, 6, life - 6, spinPerSec);
        outer.fallback(() -> {
            int a = fx.aud;
            double dir = spinPerSec >= 0 ? 1 : -1;
            fx.vfx.every(0, 3, Math.max(1, life / 3), i -> fx.with(a, () -> swirlDust(fx, c, r, k, dir * i * 0.45)));
        });
        outer.go();
        Sprite in = null;
        if (inner && fx.vfx.models.has("circle_inner")) {
            in = flat(fx, "circle_inner", c.clone().add(0, 0.01, 0), 0.2, Shapes.Frame.FLAT, k.swap()).life(life).view(view);
            in.scaleTo(2, 5, r * 0.62 / Geo.FLAT_HALF, 1, r * 0.62 / Geo.FLAT_HALF).radius(r * 0.62);
            spinOver(in, 7, life - 7, -spinPerSec * 1.5);
            in.go();
        }
        return new Sprite[]{outer, in};
    }

    /** 시전자를 중심으로 도는 마법진: 남에게는 보통 판, 시전자에게는 느리고 흐린 판 */
    public static List<Sprite> selfCircle(CastFx fx, Location c, double r, int life, CastFx.Cols k, double spinPerSec, boolean inner) {
        List<Sprite> out = new java.util.ArrayList<>();
        if (fx.cp == null) {
            for (Sprite s : circle(fx, c, r, life, k, spinPerSec, inner, Sprite.View.AUTO)) if (s != null) out.add(s);
            return out;
        }
        for (Sprite s : circle(fx, c, r, life, k, spinPerSec, inner, Sprite.View.HIDE)) if (s != null) out.add(s);
        // 시전자에게는 마법진 무늬 없이 바깥 테두리 고리만 (흐린 마법진도 1인칭 화면 아래 절반을 굵은 선으로 채웠다)
        String dm = fx.vfx.models.pick("ring_faint", "ring_dim", "circle_faint");
        // 흐린 판의 흰 안쪽 띠가 1인칭 바닥 전체를 허옇게 덮으므로 안쪽도 색으로 칠한다
        CastFx.Cols mk = new CastFx.Cols(k.a(), Palette.mix(k.a(), Color.WHITE, 0.3), k.dark(), k.rim(), k.rainbow());
        Sprite mine = flat(fx, dm, c.clone().add(0, -0.005, 0), 0.2, Shapes.Frame.FLAT, mk).life(life).view(Sprite.View.ONLY);
        if (k.rainbow()) mine.hue(10, 0);
        mine.scaleTo(1, 5, r / Geo.FLAT_HALF, 1, r / Geo.FLAT_HALF).radius(r);
        spinOver(mine, 6, life - 6, Math.min(18, Math.abs(spinPerSec)) * Math.signum(spinPerSec));
        mine.go();
        out.add(mine);
        return out;
    }

    /** 오래 도는 판: 80도 이하 키프레임으로 나눠 예약 */
    static void spinOver(Sprite s, int from, int dur, double degPerSec) {
        if (dur <= 2 || degPerSec == 0) return;
        double total = degPerSec * dur / 20.0;
        int chunk = 20;
        for (int t = 0; t < dur; t += chunk) {
            int d = Math.min(chunk, dur - t);
            if (d < 2) break;
            s.spin(from + t, d, total * d / dur);
        }
    }

    public static Sprite star(CastFx fx, Location at, double size, int life, CastFx.Cols k) {
        boolean flip = !k.rainbow() && fx.vfx.models.has("star_f3");
        String m = k.rainbow() ? fx.vfx.models.pick("star_rainbow", "star") : flip ? "star_f1" : "star";
        Sprite s = Sprite.item(fx, m, at).size(size * 0.4).radius(size * Geo.STAR_HALF).life(life).end(Sprite.End.FADE, 2);
        s.tint(k).heat(k.a(), k.b(), k.rim());
        s.scaleTo(1, 2, size, size, size);
        // 별빛 터짐 넘김 그림: 작고 밝은 심 → 긴 빛살 → 부서지며 흩어짐
        if (flip) {
            s.swap(2, "star_f2");
            s.swap(Math.max(3, life - 2), "star_f3");
        }
        s.fallback(() -> {
            Emit.send(fx, at, Particle.FIREWORK, null, (int) Math.min(20, 6 + size * 4), 0.1, 0.1, 0.1, 0.12 * Math.max(1, size * 0.5), Emit.NORMAL);
            Emit.send(fx, at, Particle.END_ROD, null, (int) Math.min(10, 3 + size * 2), 0.05, 0.05, 0.05, 0.08, Emit.DETAIL);
        });
        return s;
    }

    public static Sprite orb(CastFx fx, Location at, double size, int life, CastFx.Cols k, String model) {
        String m = model != null ? model : "orb";
        Sprite s = Sprite.item(fx, m, at).size(size).radius(size * Geo.ORB_HALF).life(life).tint(k).end(Sprite.End.SHRINK, 3);
        s.fallback(() -> Emit.dust(fx, at, k.a(), 1.2, 4, size * 0.2, Emit.NORMAL));
        return s;
    }

    /** 빛기둥: base 에서 위로 h, 너비 w. 2틱에 솟고 끝에 가늘어진다 */
    public static Sprite pillar(CastFx fx, Location base, double w, double h, int life, CastFx.Cols k) {
        // 기둥 그림은 판 폭의 가운데 일부만 빛나므로 판을 넓게 잡는다. 굵은 기둥은 바깥 번짐이 하늘에 허연 안개처럼
        // 넓게 깔리므로 덜 넓힌다
        double sw = (w > 2 ? 1.25 : 1.6) * w / (2 * Geo.BEAM_HALF_W);
        Sprite s = Sprite.item(fx, "pillar", base).size(sw, 0.05, sw).radius(w).life(life).tint(k).end(Sprite.End.THIN, 4);
        s.scaleTo(1, 2, sw, h, sw);
        s.fallback(() -> {
            int a = fx.aud;
            fx.vfx.every(0, 3, Math.max(1, life / 3), i -> fx.with(a, () -> {
                for (double y = 0; y < h; y += 0.45) Emit.dust(fx, base.clone().add(0, y, 0), k.a(), 1.5, 2, w * 0.12, Emit.NORMAL);
                if (fx.rank() >= 2) {
                    int strands = fx.rank() >= 3 ? 3 : 2;
                    Shapes.helix(base, Math.max(0.35, w * 0.45), h, strands, h / 3.0, (int) Math.min(30, h * 3), i * 0.7,
                            (p, t) -> Emit.dust(fx, p, k.b(), 1.0, Emit.DETAIL));
                }
                Emit.send(fx, base.clone().add(0, h * 0.5, 0), Particle.END_ROD, null, 3, w * 0.2, h * 0.3, w * 0.2, 0.01, Emit.DETAIL);
            }));
        });
        return s;
    }

    /** 광선: start 에서 dir 로 len, 굵기 w (반지름 0.5w) */
    public static Sprite beam(CastFx fx, String model, Location start, Vector dir, double len, double w, int life, CastFx.Cols k) {
        double sw = (w * 0.5) / Geo.BEAM_HALF_W;
        Shapes.Frame fr = Shapes.Frame.along(dir);
        Sprite s = Sprite.item(fx, model, start).frame(fr).size(sw * 0.15, sw * 0.15, len).life(life).tint(k).end(Sprite.End.THIN, 4);
        s.segLen = len;
        s.segDir = dir.clone().normalize();
        s.scaleTo(1, 2, sw, sw, len);
        s.fallback(() -> {
            Location end = start.clone().add(dir.clone().normalize().multiply(len));
            Shapes.line(start, end, 0.3, (p, t) -> Emit.dust(fx, p, t < 0.5 ? k.b() : k.a(), Math.min(2.4, 1.0 + w), Emit.NORMAL));
            if (fx.rank() >= 2) {
                double rr = Math.max(0.3, w * 0.6);
                int n = (int) Math.min(60, len * 4);
                double ph = rnd().nextDouble(Math.PI * 2);
                for (int strand = 0; strand < 2; strand++) {
                    double off = ph + Math.PI * strand;
                    for (int j = 0; j < n; j++) {
                        double t = j / (double) Math.max(1, n - 1);
                        double ang = off + t * len * 1.6;
                        Location p = fr.point(start, Math.cos(ang) * rr, Math.sin(ang) * rr, t * len);
                        Emit.dust(fx, p, strand == 0 ? k.a() : k.rim(), 0.9, Emit.DETAIL);
                    }
                }
            }
        });
        return s;
    }

    /** 참격 초승달. c 중심, fr 좌표계(앞 = 볼록한 쪽), 반지름 r */
    public static Sprite slash(CastFx fx, String model, Location c, Shapes.Frame fr, double r, int life, CastFx.Cols k) {
        Sprite s = flat(fx, model, c, r, fr, k).life(life).end(Sprite.End.SLASH, 4);
        s.fallback(() -> slashDust(fx, c, fr, r, k));
        return s;
    }

    /**
     * 입자 참격: 두께 있는 초승달을 3틱에 걸쳐 한쪽 끝에서 다른 끝으로 쓸어 그린다.
     * 가장자리는 밝은 색, 안쪽 겹은 짙은 색이고 양 끝은 가늘다. 등급이 높을수록 겹이 많고 굵다
     */
    public static void slashDust(CastFx fx, Location c, Shapes.Frame fr, double r, CastFx.Cols k) {
        slashDust(fx, c, fr, r, k, 3);
    }

    /** steps = 몇 틱에 걸쳐 쓸어 그릴지 (1 = 한 번에. 날아가는 검기처럼 매 틱 자리를 옮겨 그릴 때) */
    public static void slashDust(CastFx fx, Location c, Shapes.Frame fr, double r, CastFx.Cols k, int steps) {
        int a = fx.aud;
        int layers = 2 + Math.min(3, fx.rank());
        double band = Math.min(r * 0.35, 0.22 + 0.1 * fx.rank());
        double a0 = -Math.toRadians(80), a1 = Math.toRadians(80);
        int per = (int) Math.max(6, Math.min(26, r * 4 * Math.min(1.6, fx.dens()) * 3 / steps));
        fx.vfx.every(0, 1, steps, i -> fx.with(a, () -> {
            double s0 = a0 + (a1 - a0) * i / steps, s1 = a0 + (a1 - a0) * (i + 1) / steps;
            for (int l = 0; l < layers; l++) {
                double depth = l / (double) Math.max(1, layers - 1);
                Color col = l == 0 ? k.a() : depth > 0.6 ? k.b() : (fx.rank() >= 3 ? k.rim() : k.b());
                double size = l == 0 ? 1.0 + 0.15 * fx.rank() : 0.8 + 0.1 * fx.rank();
                final int lay = l;
                Shapes.arc(c, fr, r - band * depth, s0, s1, per, (p, t) -> {
                    double g = (s0 + (s1 - s0) * t - a0) / (a1 - a0);
                    // 양 끝으로 갈수록 안쪽 겹을 빼서 초승달 모양으로
                    if (lay > 0 && Math.sin(Math.PI * g) < lay / (double) layers) return;
                    Emit.dust(fx, p, col, size * (0.6 + 0.4 * Math.sin(Math.PI * g)), lay == 0 ? Emit.NORMAL : Emit.DETAIL);
                });
            }
            // 균열 등급부터 속성 입자가 날 끝에서 흩날린다
            if (fx.rank() >= 2) accent(fx, fr.point(c, Math.sin((s0 + s1) / 2) * r, 0, Math.cos((s0 + s1) / 2) * r), 0.5);
            if (fx.rank() >= 3) Emit.send(fx, fr.point(c, Math.sin((s0 + s1) / 2) * r, 0, Math.cos((s0 + s1) / 2) * r),
                    Particle.CRIT, null, 3 + fx.rank(), 0.15, 0.15, 0.15, 0.25, Emit.DETAIL);
        }));
    }

    /** 프리즘 등급 표식: 자홍·청록으로 살짝 어긋난 흐린 복제 둘 (빛이 갈라지는 느낌) */
    public static void hallmark(CastFx fx, Sprite s) {
        if (!fx.prism() || s == null || !s.ok() || s.kind != Sprite.Kind.ITEM) return;
        if (fx.live > fx.spriteCap() - 6) return;
        // 넘김 그림(slash_w1, star_f1...)이면 바탕 모델의 가장 흐린 단계를 쓴다
        String base = s.model.replaceAll("_(w|f)\\d$", "").replace("_rainbow", "");
        String m = fx.vfx.models.dim(base, 2);
        // 흐린 단계가 없는 모델(빔 등)은 복제하면 그냥 더 밝고 굵어지므로 건너뛴다
        if (m == null) return;
        double o = 0.15;
        Vector side = new Vector(1, 0, 0);
        s.twin(side.getX() * o, 0.02, side.getZ() * o, Color.fromRGB(0xff3ad0), Color.fromRGB(0xff9af0), m).go();
        s.twin(-side.getX() * o, 0.03, -side.getZ() * o, Color.fromRGB(0x2ae8ff), Color.fromRGB(0xaaf8ff), m).go();
    }

    // ------------------------------------------------------------------ 입자

    public static void dustRing(CastFx fx, Location c, double r, Color col, double size, int pri) {
        int n = (int) Math.max(10, Math.min(fx.vfx.spritesOn() ? 48 : 80, r * 7 * Math.min(1.6, fx.dens())));
        Shapes.ring(c, r, n, Shapes.Frame.FLAT, (p, t) -> Emit.dust(fx, p, col, size, pri));
    }

    /** 바깥으로 튀는 입자 (고리 가장자리 물보라) */
    public static void rimSpray(CastFx fx, Location c, double r, int n, Fx.Spec spec, double speed, double up, int pri) {
        if (spec == null) return;
        double ph = rnd().nextDouble(Math.PI);
        // END_ROD·FIREWORK 는 3초씩 떠 있어 바닥에 흰 점으로 쌓인다: 같은 방향의 짧은 빛줄기(TRAIL)로 바꾼다
        boolean linger = Emit.lingers(spec.particle());
        Color lc = spec.particle() == Particle.END_ROD || spec.particle() == Particle.FIREWORK ? Color.WHITE : fx.pal.b();
        for (int i = 0; i < n; i++) {
            double a = ph + Math.PI * 2 * i / n;
            Vector out = new Vector(Math.cos(a), up, Math.sin(a));
            Location p = c.clone().add(Math.cos(a) * r, 0.1, Math.sin(a) * r);
            if (linger) {
                double len = Math.min(3.5, 0.6 + speed * 9);
                Emit.streak(fx, p, p.clone().add(out.clone().normalize().multiply(len)), lc, 2, 6, pri);
            } else {
                Emit.dir(fx, p, spec, out, speed, pri);
            }
        }
    }

    /** 가장자리에서 가운데로 모이는 빛 */
    public static void converge(CastFx fx, Location c, double r, int n, Color col, int dur, int pri) {
        double ph = rnd().nextDouble(Math.PI * 2);
        for (int i = 0; i < n; i++) {
            double a = ph + Math.PI * 2 * i / n;
            Location from = c.clone().add(Math.cos(a) * r, rnd().nextDouble(0.1, 1.6), Math.sin(a) * r);
            Emit.trail(fx, from, c, col, dur, pri);
        }
    }

    /** 바닥 입자 회오리: 가운데에서 바깥으로 휘어 나가는 팔 + 바깥 고리. 등급이 높을수록 팔이 많다 */
    public static void swirlDust(CastFx fx, Location c, double r, CastFx.Cols k, double phase) {
        int arms = 2 + Math.min(3, fx.rank());
        int per = (int) Math.max(8, Math.min(22, r * 3.5 * Math.min(1.6, fx.dens())));
        Location base = c.clone().add(0, 0.12, 0);
        for (int arm = 0; arm < arms; arm++) {
            double off = phase + Math.PI * 2 * arm / arms;
            Shapes.spiral(base, r * 0.15, r, 0.45, 0, per, off, (p, t) ->
                    Emit.dust(fx, p, t > 0.6 ? k.a() : k.b(), 0.8 + 0.6 * t, t > 0.5 ? Emit.NORMAL : Emit.DETAIL));
        }
        dustRing(fx, base, r, k.a(), 1.3, Emit.NORMAL);
        if (fx.rank() >= 2) dustRing(fx, base, r * 0.55, k.b(), 0.9, Emit.DETAIL);
    }

    public static void circleDust(CastFx fx, Location c, double r, CastFx.Cols k, double phase) {
        dustRing(fx, c, r, k.a(), 1.2, Emit.NORMAL);
        dustRing(fx, c, r * 0.86, k.b(), 0.9, Emit.DETAIL);
        List<Location> st = Shapes.star(c, 3, r * 0.84, r * 0.84, Shapes.Frame.FLAT.yaw(Math.toDegrees(phase)), 0);
        // 육각성: 한 칸 건너 꼭짓점을 잇는다
        for (int i = 0; i < 6; i++) {
            Location a = st.get(i), b = st.get((i + 2) % 6);
            Shapes.line(a, b, 0.6, (p, t) -> Emit.dust(fx, p, k.b(), 0.8, Emit.DETAIL));
        }
    }

    /** 속성 강조 (균열 등급부터) */
    public static void accent(CastFx fx, Location at, double size) {
        String id = fx.pal.id();
        int n = Math.max(2, (int) (4 * size * Math.min(1.5, fx.dens())));
        switch (id) {
            case "frost" -> {
                Emit.send(fx, at, Particle.SNOWFLAKE, null, n, size * 0.4, size * 0.3, size * 0.4, 0.03, Emit.NORMAL);
                Emit.send(fx, at, Particle.ITEM_SNOWBALL, null, n / 2 + 1, size * 0.3, size * 0.2, size * 0.3, 0.1, Emit.DETAIL);
            }
            case "flame", "sun" -> {
                Emit.send(fx, at, Particle.FLAME, null, n, size * 0.3, size * 0.2, size * 0.3, 0.05, Emit.NORMAL);
                Emit.send(fx, at, Particle.LAVA, null, Math.max(1, n / 3), size * 0.2, 0.1, size * 0.2, 0, Emit.DETAIL);
                Emit.send(fx, at, Particle.LARGE_SMOKE, null, Math.max(1, n / 3), size * 0.3, 0.2, size * 0.3, 0.02, Emit.DETAIL);
            }
            case "abyss", "ender" -> {
                Emit.send(fx, at, Particle.REVERSE_PORTAL, null, n * 2, size * 0.5, size * 0.4, size * 0.5, 0.05, Emit.NORMAL);
                Emit.dust(fx, at, Color.fromRGB(0x14001e), 1.6, n / 2 + 1, size * 0.3, Emit.DETAIL);
            }
            case "storm" -> Emit.send(fx, at, Particle.ELECTRIC_SPARK, null, n * 2, size * 0.4, size * 0.4, size * 0.4, 0.15, Emit.NORMAL);
            case "holy", "gold", "genesis" -> {
                Emit.send(fx, at, Particle.END_ROD, null, Math.max(1, n / 2), size * 0.3, size * 0.3, size * 0.3, 0.015, Emit.NORMAL);
                Pieces.rays(fx, at, Math.min(8, n), 1.2 + size * 0.6, fx.cols(), 6, true);
                Emit.send(fx, at, Particle.WAX_OFF, null, n, size * 0.4, size * 0.4, size * 0.4, 0.1, Emit.DETAIL);
            }
            case "blood" -> {
                Emit.dust(fx, at, Color.fromRGB(0xa0001c), 1.6, n, size * 0.35, Emit.NORMAL);
                Emit.send(fx, at, Particle.DAMAGE_INDICATOR, null, Math.max(1, n / 2), size * 0.2, 0.2, size * 0.2, 0.1, Emit.DETAIL);
            }
            case "nature" -> Emit.send(fx, at, Particle.BLOCK, Material.AZALEA_LEAVES.createBlockData(), n * 2, size * 0.4, size * 0.3, size * 0.4, 0.1, Emit.NORMAL);
            case "venom" -> {
                Emit.send(fx, at, Particle.ITEM_SLIME, null, n, size * 0.3, 0.2, size * 0.3, 0.05, Emit.NORMAL);
                Emit.dust(fx, at, fx.pal.a(), 1.2, n, size * 0.3, Emit.DETAIL);
            }
            case "ocean" -> {
                Emit.send(fx, at, Particle.SPLASH, null, n * 3, size * 0.4, 0.2, size * 0.4, 0.1, Emit.NORMAL);
                Emit.send(fx, at, Particle.BUBBLE_POP, null, n, size * 0.3, 0.3, size * 0.3, 0.05, Emit.DETAIL);
            }
            case "earth" -> {
                Emit.send(fx, at, Particle.BLOCK_CRUMBLE, Material.DIRT.createBlockData(), n * 2, size * 0.4, 0.2, size * 0.4, 0.1, Emit.NORMAL);
                Emit.send(fx, at, Particle.DUST_PLUME, null, n, size * 0.3, 0.1, size * 0.3, 0.05, Emit.DETAIL);
            }
            case "wind" -> Emit.send(fx, at, Particle.SMALL_GUST, null, Math.max(1, n / 2), size * 0.4, 0.3, size * 0.4, 0, Emit.NORMAL);
            case "star" -> {
                Emit.send(fx, at, Particle.END_ROD, null, Math.max(1, n / 2), size * 0.4, size * 0.4, size * 0.4, 0.015, Emit.NORMAL);
                Pieces.rays(fx, at, Math.min(8, n), 1.2 + size * 0.6, fx.cols(), 6, false);
                Emit.dust(fx, at, Color.fromRGB(0xffd86a), 0.9, n, size * 0.4, Emit.DETAIL);
            }
            case "crystal" -> {
                Emit.send(fx, at, Particle.ITEM, new org.bukkit.inventory.ItemStack(Material.AMETHYST_SHARD), n, size * 0.3, 0.2, size * 0.3, 0.1, Emit.NORMAL);
                Emit.send(fx, at, Particle.END_ROD, null, Math.max(1, n / 2), size * 0.3, 0.3, size * 0.3, 0.03, Emit.DETAIL);
            }
            case "shadow" -> Emit.send(fx, at, Particle.SQUID_INK, null, n, size * 0.3, 0.3, size * 0.3, 0.03, Emit.NORMAL);
            case "doom" -> {
                Emit.send(fx, at, Particle.SOUL_FIRE_FLAME, null, n, size * 0.3, 0.3, size * 0.3, 0.04, Emit.NORMAL);
                Emit.send(fx, at, Particle.SCULK_SOUL, null, Math.max(1, n / 2), size * 0.3, 0.3, size * 0.3, 0.03, Emit.DETAIL);
            }
            case "prism" -> {
                for (int i = 0; i < Math.min(6, n); i++)
                    Emit.dust(fx, at.clone().add(rnd().nextGaussian() * size * 0.3, rnd().nextGaussian() * size * 0.3, rnd().nextGaussian() * size * 0.3),
                            Palette.hue(i / 6.0 + fx.vfx.tick * 0.01), 1.2, Emit.NORMAL);
                Pieces.rays(fx, at, Math.min(8, n), 1.2 + size * 0.6, PrismSigs.rainbow(fx), 6, false);
            }
            default -> Emit.send(fx, at, Particle.CRIT, null, n, size * 0.3, 0.2, size * 0.3, 0.2, Emit.NORMAL);
        }
    }

    // ------------------------------------------------------------------ 파편 (블록 조각이 튀었다 떨어진다)

    public static void debris(CastFx fx, Location at, int wanted, double power, Material fallback) {
        int n = fx.debrisFor(wanted);
        if (n <= 0) return;
        Material gm = groundMaterial(at, fallback != null ? fallback : Material.STONE);
        for (int i = 0; i < n; i++) {
            if (fx.moving >= 16) break;
            Material m = (i % 3 == 2 && fallback != null) ? fallback : gm;
            BlockData bd = m.createBlockData();
            double a = rnd().nextDouble(Math.PI * 2);
            double out = fx.mob() ? rnd().nextDouble(0.02, 0.08) : rnd().nextDouble(0.25, 0.45) * power;
            Vector v = new Vector(Math.cos(a) * out, rnd().nextDouble(0.35, 0.6) * Math.max(0.8, power), Math.sin(a) * out);
            double s = rnd().nextDouble(0.25, 0.45);
            Location p = at.clone().add(Math.cos(a) * 0.5, 0.3, Math.sin(a) * 0.5);
            // 땅에 반쯤 묻혀 나오는 흙덩이는 그 자리 빛(0)을 받아 새까만 상자로 보였다 → 늘 밝게
            Sprite d = Sprite.block(fx, bd, p).size(s).life(rnd().nextInt(16, 25)).end(Sprite.End.SHRINK, 4).radius(0.3);
            // 시전자 눈앞으로 튀어 오는 흙덩이는 1인칭에서 적을 가린다
            d.selfNear = 6;
            d.fly(v, 0.08, 2, (float) rnd().nextDouble(25, 60), new Vector3f((float) rnd().nextGaussian(), (float) rnd().nextGaussian(), (float) rnd().nextGaussian()).normalize());
            d.go();
        }
    }

    /**
     * 얼음 가시: 땅에서 솟았다가 깨진다. 네모 기둥은 말뚝처럼 보여서, 45도 돌린 가는 결정(마름모 단면)에
     * 더 가는 끝 결정을 겹쳐 끝이 뾰족하게 좁아지게 하고, 가운데에서 바깥으로 기울여 터져 나오는 느낌을 준다.
     */
    public static void iceSpikes(CastFx fx, Location c, double r, int n, int life) {
        spikes(fx, c, r, n, life, new Material[]{Material.BLUE_ICE, Material.PACKED_ICE}, Material.ICE, Material.ICE, "block.glass.break");
    }

    /** 프리즘 결정 가시: 자수정·색유리 결정이 솟는다 */
    public static void crystalSpikes(CastFx fx, Location c, double r, int n, int life) {
        spikes(fx, c, r, n, life, new Material[]{Material.AMETHYST_BLOCK, Material.LIGHT_BLUE_STAINED_GLASS, Material.PINK_STAINED_GLASS,
                Material.LIME_STAINED_GLASS}, Material.WHITE_STAINED_GLASS, Material.AMETHYST_CLUSTER, "block.amethyst_cluster.break");
    }

    static void spikes(CastFx fx, Location c, double r, int n, int life, Material[] mats, Material tipMat, Material shatter, String snd) {
        for (int i = 0; i < n; i++) {
            double a = Math.PI * 2 * i / n + rnd().nextDouble(-0.2, 0.2);
            Location p = ground(c.clone().add(Math.cos(a) * r, 0.5, Math.sin(a) * r));
            Material m = mats[i % mats.length];
            double h = rnd().nextDouble(1.5, 2.6);
            // 바깥쪽으로 12~24도 기울인다 (기울기 축 = 바깥 방향과 수직인 수평축)
            float tilt = (float) Math.toRadians(rnd().nextDouble(12, 24));
            Vector3f axis = new Vector3f((float) -Math.sin(a), 0, (float) Math.cos(a));
            boolean ok = false;
            for (int part = 0; part < 2; part++) {
                if (part == 1 && fx.live > fx.spriteCap() - 4) break;
                double w = part == 0 ? 0.34 : 0.17;
                double hh = part == 0 ? h * 0.62 : h;
                Material mm = part == 0 ? m : tipMat;
                Sprite s = Sprite.block(fx, mm.createBlockData(), p).size(w, 0.05, w).radius(0.5).life(life).end(Sprite.End.SHRINK, 3);
                s.rot.rotateAxis(-tilt, axis.x, axis.y, axis.z).rotateY((float) Math.toRadians(45));
                s.centerBlock = false;
                // 회전한 판의 가운데가 p 위에 오도록 (블록 모델 원점은 모서리)
                Vector3f half = new Vector3f((float) (w / 2), 0, (float) (w / 2));
                s.rot.transform(half);
                s.offset(-half.x, -0.05, -half.z);
                s.scaleTo(1 + part, 3, w, hh, w);
                if (s.go().ok()) ok = true;
            }
            if (!ok) {
                Emit.send(fx, p.clone().add(0, 0.8, 0), Particle.BLOCK, m.createBlockData(), 12, 0.2, 0.6, 0.2, 0.05, Emit.NORMAL);
                continue;
            }
            Emit.send(fx, p.clone().add(0, 0.2, 0), shatter == Material.ICE ? Particle.SNOWFLAKE : Particle.END_ROD, null, 4, 0.2, 0.1, 0.2, 0.05, Emit.DETAIL);
            BlockData sd = (shatter.isBlock() ? shatter : Material.ICE).createBlockData();
            fx.vfx.after(life - 2, () -> Emit.send(fx, p.clone().add(0, h * 0.5, 0), Particle.BLOCK, sd, 10, 0.2, h * 0.3, 0.2, 0.1, Emit.DETAIL));
        }
        fx.sound(c, snd, 0.6, 1.6);
    }

    /** 꽃이 피어난다 (작은 블록 표시) */
    public static void flowers(CastFx fx, Location c, double r, int n, int life) {
        Material[] fl = {Material.POPPY, Material.DANDELION, Material.CORNFLOWER, Material.ALLIUM, Material.OXEYE_DAISY,
                Material.PINK_TULIP, Material.LILY_OF_THE_VALLEY};
        for (int i = 0; i < n; i++) {
            double a = rnd().nextDouble(Math.PI * 2), d = Math.sqrt(rnd().nextDouble()) * r;
            Location g = groundOrNull(c.clone().add(Math.cos(a) * d, 0.5, Math.sin(a) * d));
            if (g == null) continue;
            Sprite s = Sprite.block(fx, fl[i % fl.length].createBlockData(), g.add(0, 0.35, 0)).size(0.05).worldLight()
                    .radius(0.4).life(life).end(Sprite.End.SHRINK, 6);
            s.rot.rotateY((float) rnd().nextDouble(Math.PI * 2));
            s.scaleTo(1 + i % 4, 4, 0.7);
            s.go();
        }
    }

    /** 땅 갈라짐 (입자 선) */
    public static void cracks(CastFx fx, Location c, double r, int lines, Color glow, Particle sparkle) {
        double ph = rnd().nextDouble(Math.PI);
        for (int i = 0; i < lines; i++) {
            double a = ph + Math.PI * 2 * i / lines + rnd().nextDouble(-0.2, 0.2);
            Location prev = c.clone().add(0, 0.08, 0);
            double len = r * rnd().nextDouble(0.6, 1.0);
            for (int s = 1; s <= 4; s++) {
                double aa = a + rnd().nextDouble(-0.25, 0.25);
                Location next = c.clone().add(Math.cos(aa) * len * s / 4, 0.08, Math.sin(aa) * len * s / 4);
                Location p0 = prev;
                Shapes.line(p0, next, 0.3, (p, t) -> Emit.dust(fx, p, glow, 1.0, Emit.NORMAL));
                if (sparkle != null) Emit.send(fx, next, sparkle, null, 1, 0.05, 0.05, 0.05, 0.01, Emit.DETAIL);
                prev = next;
            }
        }
    }

    /** 바닥 잔광 (균열 문양). crack 모델이 없으면 shock 흐린 판, 그것도 없으면 입자 */
    public static void afterglow(CastFx fx, Location c, double r, int life, CastFx.Cols k) {
        Location g = ground(c).add(0, 0.05, 0);
        String el = switch (fx.pal.id()) {
            case "frost" -> "crack_rime";
            case "abyss", "doom", "shadow", "ender" -> "crack_pool";
            case "holy", "gold", "genesis", "sun", "prism", "star" -> "crack_glyph";
            default -> "crack";
        };
        String m = fx.vfx.models.pick(el, "crack", "shock_dim", "ring_dim");
        // 시전자 발밑 잔광은 1인칭 화면 아래를 하얗게 덮으므로 흐린 판으로
        if (m != null && fx.cp != null && fx.cp.getLocation().distanceSquared(g) < 4) {
            String d = fx.vfx.models.dim(m, 1);
            if (d != null) m = d;
        }
        if (m == null || !decalFits(g, r)) {
            cracks(fx, g, r, 6, k.a(), null);
            return;
        }
        // 테는 주색의 그늘(검은 테는 잔디 위 스티커처럼 보였다)
        CastFx.Cols dk = new CastFx.Cols(k.a(), k.b(), k.dark(), fx.night ? k.a() : Palette.rimOf(k.a(), k.dark()), false);
        flat(fx, m, g, r, Shapes.Frame.FLAT.yaw(rnd().nextDouble(360)), dk).life(life).end(Sprite.End.FADE, 8)
                .fallback(() -> cracks(fx, g, r, 6, k.a(), null)).go();
    }

    /**
     * 무거운 충격의 빛 반구 (팩에 dome 이 있을 때). 안에 선 사람에게는 얼굴 규칙으로 숨는다.
     * 지금은 쓰지 않는다: 낮에는 반원 판 네 장이 계단진 허연 막(유령 돔)으로 보였다
     */
    public static void dome(CastFx fx, Location g, double r, int life, CastFx.Cols k) {
        if (!fx.vfx.models.has("dome")) return;
        double s = r / 1.5;
        Sprite d = Sprite.item(fx, "dome", g).size(s * 0.2).radius(r).life(life).tint(k).end(Sprite.End.FADE, 3);
        d.decal = false;
        d.scaleTo(1, 3, s, s * 0.8, s);
        d.go();
    }

    /**
     * 시전자 화면 위쪽 1/3 에 놓는 자리: d 칸 앞, 지금 시선보다 atan(up/d) 만큼 위 (약 20~25도).
     * 시선 높이를 따라가므로 아래를 보며 써도 화면 밖(위)으로 잘리지 않고, 조준점(화면 가운데)도 가리지 않는다.
     */
    public static Location heroSpot(CastFx fx, double d, double up) {
        Location e = fx.eye();
        Vector look = e.getDirection().setY(0);
        if (look.lengthSquared() < 1e-6) look = new Vector(0, 0, 1);
        look.normalize();
        double elev = -e.getPitch() + Math.toDegrees(Math.atan2(up, d));
        double a = Math.toRadians(Math.max(-5, Math.min(60, elev)));
        return e.clone().add(look.multiply(d * Math.cos(a))).add(0, d * Math.sin(a), 0);
    }

    static Location center(SkillContext ctx) {
        return ctx.caster.getLocation();
    }

    static Display.Billboard center() {
        return Display.Billboard.CENTER;
    }
}
