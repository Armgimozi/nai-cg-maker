package kr.augsky.vfx;

import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;
import org.joml.Vector3f;

import java.util.List;
import java.util.function.Supplier;

/** 자기 강화·아군 강화·표식·소환·시전 순간·기 모으기 */
final class BuffFx {
    private BuffFx() {}

    /** 시전 순간: 보스 등급 이상은 무기 손 쪽에 작은 별(남에게만) + 속성 소리. 프리즘 궁극기는 종소리 */
    static void flourish(CastFx fx) {
        if (fx.cp == null || fx.mob()) return;
        if (fx.rank() >= 3) {
            Vector look = fx.eye().getDirection();
            Vector flat = look.clone().setY(0);
            Vector ahead = flat.lengthSquared() < 1e-6 ? new Vector() : flat.normalize().multiply(0.5);
            Location hand = fx.eye().add(fx.handSide(look).multiply(0.4)).add(0, -0.4, 0).add(ahead);
            Kit.star(fx, hand, 0.6, 3, fx.cols()).view(Sprite.View.HIDE).go();
            fx.castSounds(fx.caster.getLocation());
        }
        if (fx.prism() && fx.ult()) Sfx.arpeggio(fx, fx.caster.getLocation(), 0.7);
    }

    static void buff(CastFx fx, Ev.Buff ev) {
        LivingEntity w = ev.who();
        if (w == null || !w.isValid()) return;
        CastFx.Cols k = fx.cols(ev.yaml());
        if (fx.mob()) {
            if (fx.tier == Tier.BOSS_MOB) powerUp(fx, w, k);
            else Emit.spec(fx, fx.pal.mote(), w.getLocation().add(0, 1, 0), 8, 0.3, 0.05, Emit.NORMAL);
            return;
        }
        if (fx.rank() < 1) return;
        double h = w.getHeight();
        Location f = w.getLocation();
        // 발끝에서 머리로 올라가는 고리
        fx.vfx.every(0, 1, 6, i -> {
            Location c = w.getLocation().add(0, h * (i + 1) / 6.0, 0);
            Kit.dustRing(fx, c, 0.75, i % 2 == 0 ? k.a() : k.b(), 0.9, Emit.NORMAL);
        });
        Emit.spec(fx, fx.pal.mote(), f.clone().add(0, 1, 0), fx.n(6), 0.4, 0.04, Emit.DETAIL);
        if (fx.rank() >= 3) gyroscope(fx, w, 1.1, 24, k, Sprite.View.HIDE);
        if (fx.rank() >= 3 && fx.ult()) {
            Location g = Kit.ground(f).add(0, 0.03, 0);
            if (Kit.decalFits(g, 1.8)) Kit.selfCircle(fx, g, 1.8, 30, k, 15, false);
        }
    }

    /** 보스 단계 변화 (판정 없음): 바닥 고리 대신 세로로 솟는 빛 + 도는 고리 + 솟는 입자 */
    static void powerUp(CastFx fx, LivingEntity boss, CastFx.Cols k) {
        Location f = boss.getLocation();
        double h = boss.getHeight();
        Kit.pillar(fx, f, Math.max(1.6, boss.getWidth() + 0.8), Math.max(8, h * 3), 24, k).go();
        gyroscope(fx, boss, Math.max(1.4, boss.getWidth() * 0.9 + 0.4), 40, k, Sprite.View.AUTO);
        fx.vfx.every(0, 2, 12, i -> {
            for (int j = 0; j < 6; j++) {
                double a = Math.PI * 2 * j / 6 + i * 0.4;
                Location p = boss.getLocation().add(Math.cos(a) * 1.4, 0.2 + i * 0.25, Math.sin(a) * 1.4);
                Emit.dir(fx, p, fx.pal.spark(), new Vector(0, 1, 0), 0.15, Emit.NORMAL);
            }
        });
        Emit.flash(fx, f.clone().add(0, h + 2, 0));
        fx.sound(f, "entity.ravager.roar", 1.2, 0.7);
    }

    /** 몸 둘레를 도는 세 고리 */
    static void gyroscope(CastFx fx, LivingEntity who, double r, int life, CastFx.Cols k, Sprite.View view) {
        Supplier<Location> mid = () -> who.isValid() ? who.getLocation().add(0, who.getHeight() * 0.55, 0) : null;
        Location m = mid.get();
        if (m == null) return;
        double[] rolls = {0, 60, -60};
        for (int i = 0; i < 3; i++) {
            Shapes.Frame fr = Shapes.Frame.FLAT.roll(rolls[i]).yaw(i * 40);
            Sprite s = Kit.flat(fx, "ring", m, r, fr, i == 0 ? k : k.swap()).life(life).view(view).follow(mid, 1);
            s.decal = false;
            s.size(0.1);
            s.scaleTo(1, 3, r / Geo.FLAT_HALF, 1, r / Geo.FLAT_HALF);
            s.spinAxis(4, life - 6, (i == 0 ? 0 : 160) * (i == 2 ? -1 : 1), new Vector3f(1, 0, 0));
            s.fallback(() -> Kit.dustRing(fx, m, r, k.a(), 1.0, Emit.NORMAL));
            s.go();
        }
    }

    static void party(CastFx fx, Ev.Party ev) {
        if (fx.mob() || fx.rank() < 3) return;
        CastFx.Cols k = fx.cols();
        Location g = Kit.ground(ev.center()).add(0, 0.03, 0);
        if (Kit.decalFits(g, ev.radius())) Kit.ring(fx, g, 0.6, ev.radius(), 8, 14, k, null).go();
    }

    static void ally(CastFx fx, Ev.Ally ev) {
        LivingEntity w = ev.who();
        if (w == null || !w.isValid() || fx.rank() < 1) return;
        if (fx.mob()) {
            Emit.spec(fx, fx.pal.mote(), w.getLocation().add(0, 1, 0), 6, 0.3, 0.04, Emit.NORMAL);
            return;
        }
        CastFx.Cols k = fx.cols(ev.yaml());
        Location f = w.getLocation();
        // 위에서 내려오는 반짝임 기둥
        fx.vfx.every(0, 1, 6, i -> {
            Location p = w.getLocation().add(0, 3.2 - i * 0.5, 0);
            Emit.send(fx, p, Particle.END_ROD, null, 2, 0.25, 0.1, 0.25, 0.0, Emit.NORMAL);
            Emit.dust(fx, p, k.b(), 1.0, 2, 0.3, Emit.DETAIL);
        });
        Kit.dustRing(fx, f.clone().add(0, 0.1, 0), 0.8, k.a(), 1.0, Emit.NORMAL);
        if (fx.rank() >= 3) Kit.pillar(fx, f, 1.2, 3.2, 12, k).go();
        if (fx.rank() >= 4) {
            Supplier<Location> head = () -> w.isValid() ? w.getLocation().add(0, w.getHeight() + 0.45, 0) : null;
            Sprite halo = Kit.ring(fx, head.get(), 0.45, 0.45, 1, 30, k, null).follow(head, 1);
            halo.go();
        }
    }

    static void mark(CastFx fx, Ev.Mark ev) {
        LivingEntity t = ev.target();
        if (t == null || !t.isValid() || fx.rank() < 1) return;
        Location c = t.getLocation().add(0, t.getHeight() * 0.5, 0);
        Kit.accent(fx, c, 0.8);
        if (fx.rank() >= 2 && !fx.mob()) Kit.ring(fx, Kit.ground(t.getLocation()).add(0, 0.03, 0), 0.3, Math.max(0.8, t.getWidth()), 3, 8, fx.cols(ev.yaml()), null).go();
    }

    static void summon(CastFx fx, Ev.Summon ev) {
        CastFx.Cols k = fx.cols();
        Location at = ev.at();
        if (fx.rank() < 2) return;
        Location g = Kit.ground(at).add(0, 0.03, 0);
        if (fx.mob()) {
            // 몬스터 소환은 위험 지역이 아니므로 바닥 고리 없이 세로 연기 기둥만
            Emit.send(fx, g.clone().add(0, 1, 0), fx.pal.spark().particle(), fx.pal.spark().data(), 12, 0.3, 0.8, 0.3, 0.03, Emit.NORMAL);
            if (fx.tier == Tier.BOSS_MOB) Kit.pillar(fx, g, 1.0, 3, 14, k).go();
            return;
        }
        Kit.dustRing(fx, g.clone().add(0, 0.05, 0), 1.2, k.a(), 1.0, Emit.NORMAL);
        if (fx.rank() >= 3) {
            Kit.circle(fx, g, 1.5, 16, k, 60, false, Sprite.View.AUTO);
            Kit.pillar(fx, g, 0.8, 2.5, 10, k).go();
        }
    }

    /** 플레이어 기술의 기 모으기 (delay 10틱 이상, 균열 등급부터): 터질 자리에 고리/마법진이 차오르고 빛이 모인다 */
    static void charge(CastFx fx, Ev.Windup ev) {
        // 전용 연출이 있는 기술은 자기 방식으로 기를 모은다 (궁극기 안의 연속 delay 마다 마법진이 겹치지 않게)
        if (fx.rank() < 2 || ev.ticks() < 10 || fx.sig != Signature.NONE) return;
        if (fx.memo.containsKey("charging")) return;
        fx.memo.put("charging", Boolean.TRUE);
        fx.vfx.after(ev.ticks(), () -> fx.memo.remove("charging"));
        List<Footprint> fps = ev.footprints().get();
        if (fps.isEmpty()) return;
        CastFx.Cols k = fx.cols();
        for (Footprint f : fps) {
            if (f.shape() != Footprint.Shape.CIRCLE || f.r() < 1.5 || f.r() > 10) continue;
            Location c = Kit.ground(f.c()).add(0, 0.02, 0);
            if (!Kit.decalFits(c, f.r())) continue;
            if (fx.rank() >= 3) Kit.circle(fx, c, f.r(), ev.ticks() + 2, k, 40, false, Sprite.View.AUTO);
            else Kit.ring(fx, c, 0.3, f.r(), ev.ticks(), ev.ticks() + 2, k, fx.vfx.models.pick("ring_dim", "ring")).go();
            fx.vfx.every(0, 2, ev.ticks() / 2, i -> Kit.converge(fx, c.clone().add(0, 0.5, 0), f.r(), 3, k.b(), 8, Emit.DETAIL));
            break;
        }
    }

    static boolean isPlayer(LivingEntity e) {
        return e instanceof Player;
    }

    static Color white() {
        return Color.WHITE;
    }
}
