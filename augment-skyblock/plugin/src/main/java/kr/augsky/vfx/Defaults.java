package kr.augsky.vfx;

/** 사건 종류별 기본 연출로 보낸다. 모든 스킬이 등급에 맞게 자동으로 화려해지는 곳 */
final class Defaults {
    private Defaults() {}

    static Track render(CastFx fx, Ev ev) {
        return switch (ev) {
            case Ev.Cone e -> {
                MeleeFx.cone(fx, e);
                yield Track.NOOP;
            }
            case Ev.Dash e -> MeleeFx.dash(fx, e);
            case Ev.Leap e -> MeleeFx.leap(fx, e);
            case Ev.Blink e -> {
                MeleeFx.blink(fx, e);
                yield Track.NOOP;
            }
            case Ev.Hit e -> {
                MeleeFx.hit(fx, e);
                yield Track.NOOP;
            }
            case Ev.Nova e -> {
                AreaFx.nova(fx, e);
                yield Track.NOOP;
            }
            case Ev.Zone e -> AreaFx.zone(fx, e);
            case Ev.Orbit e -> AreaFx.orbit(fx, e);
            case Ev.Vortex e -> AreaFx.vortex(fx, e);
            case Ev.Strike e -> {
                AreaFx.strike(fx, e);
                yield Track.NOOP;
            }
            case Ev.Rain e -> {
                AreaFx.rain(fx, e);
                yield Track.NOOP;
            }
            case Ev.Drop e -> AreaFx.drop(fx, e);
            case Ev.Projectile e -> RangedFx.projectile(fx, e);
            case Ev.Explode e -> {
                RangedFx.explode(fx, e);
                yield Track.NOOP;
            }
            case Ev.Beam e -> {
                RangedFx.beam(fx, e);
                yield Track.NOOP;
            }
            case Ev.Chain e -> {
                RangedFx.chain(fx, e);
                yield Track.NOOP;
            }
            case Ev.Buff e -> {
                BuffFx.buff(fx, e);
                yield Track.NOOP;
            }
            case Ev.Party e -> {
                BuffFx.party(fx, e);
                yield Track.NOOP;
            }
            case Ev.Ally e -> {
                BuffFx.ally(fx, e);
                yield Track.NOOP;
            }
            case Ev.Mark e -> {
                BuffFx.mark(fx, e);
                yield Track.NOOP;
            }
            case Ev.Summon e -> {
                BuffFx.summon(fx, e);
                yield Track.NOOP;
            }
            case Ev.Windup e -> {
                if (fx.mob()) Telegraph.windup(fx, e);
                else BuffFx.charge(fx, e);
                yield Track.NOOP;
            }
        };
    }
}
