package kr.augsky.vfx;

import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.entity.LivingEntity;
import org.bukkit.util.Vector;

import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

/**
 * 보스 몬스터 16개 기술. 자동 예고(Telegraph) 위에 덧붙인다.
 * 규칙: 바닥 고리·충격파는 실제로 맞는 기술에만, 판정 범위 그대로(넘치지 않게). 판정 없는 단계 변화는 세로로 솟는 연출.
 */
final class MobSigs {
    private MobSigs() {}

    static CastFx.Cols rgb(CastFx fx, int a, int b) {
        return PrismSigs.rgb(fx, a, b);
    }

    /** 보스 몸 앞에서 기를 모으는 구슬 (광선 예고와 함께) */
    static void charge(CastFx fx, int ticks, CastFx.Cols k, String sound) {
        LivingEntity c = fx.caster;
        Supplier<Location> at = () -> c.isValid() ? c.getEyeLocation().add(c.getEyeLocation().getDirection().multiply(1.2)) : null;
        Location a0 = at.get();
        if (a0 == null) return;
        Sprite o = Kit.orb(fx, a0, 0.2, ticks + 2, k, null).follow(at, 1);
        o.scaleTo(1, Math.max(2, ticks - 1), 1.2 / (2 * Geo.ORB_HALF));
        o.prio = 3;
        o.go();
        fx.vfx.every(0, 2, ticks / 2, i -> {
            Location l = at.get();
            if (l != null) Kit.converge(fx, l, 2.5, 3, k.b(), 6, Emit.NORMAL);
        });
        if (sound != null) fx.sound(a0, sound, 1.0, 1.0);
    }

    static void register(Map<String, Signature> m) {
        // ── 서리 군주 ──
        // 눈보라: 표적 위 높은 하늘에 도는 눈보라 구름(옆에서 보면 판 대신 두꺼운 구름 띠) + 얼음 줄기가 땅으로 그어진다.
        // 떨어질 자리의 빨간 예고 고리(Telegraph.dropMarker)는 그대로
        m.put("m_blizzard", Sig.of()
                .on(Ev.Rain.class, (fx, e) -> {
                    Location g = Kit.ground(e.center());
                    Location top = g.clone().add(0, Math.max(8.5, e.height() + 1), 0);
                    int fall = (int) Math.ceil(e.height() / Math.max(0.3, e.speed()));
                    int life = (e.count() - 1) * e.interval() + fall + 10;
                    Pieces.iceStorm(fx, top, g, e.radius() + 2, life);
                    fx.sound(top, "entity.breeze.wind_burst", 1.0, 0.6);
                    fx.vfx.every(0, 10, Math.max(1, life / 10), i -> fx.sound(g, "item.elytra.flying", 0.25, 1.6));
                }));

        m.put("m_ice_nova", Sig.of()
                .on(Ev.Windup.class, (fx, e) -> {
                    LivingEntity c = fx.caster;
                    // 보스 둘레 1.5칸에 얼음 결정이 자란다
                    fx.vfx.every(0, 3, e.ticks() / 3, i -> {
                        if (!c.isValid()) return;
                        for (Location p : Shapes.around(c.getLocation().add(0, 0.4 + i * 0.12, 0), 1.6, 8, i * 0.2))
                            Emit.send(fx, p, Particle.BLOCK, Material.ICE.createBlockData(), 1, 0.05, 0.05, 0.05, 0, Emit.NORMAL);
                    });
                })
                .replace(Ev.Nova.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.center());
                    Pieces.shockwave(fx, g, e.radius(), Math.max(3, e.expand()), new CastFx.Cols[]{fx.cols(), fx.cols().swap()}, 2, true);
                    fx.vfx.after(Math.max(1, e.expand()), () -> Kit.iceSpikes(fx, g, e.radius() * 0.95, 12, 16));
                    Kit.debris(fx, g, 6, 0.6, Material.PACKED_ICE);
                }));

        m.put("m_frozen_beam", Sig.of()
                .on(Ev.Windup.class, (fx, e) -> charge(fx, e.ticks(), fx.cols(), "entity.guardian.attack")));

        m.put("m_frost_roar", Sig.of().noDamage()
                .on(Ev.Buff.class, (fx, e) -> fx.sound(fx.caster.getLocation(), "entity.polar_bear.warning", 1.2, 0.5)));

        m.put("m_summon_frost", Sig.of());

        // ── 화염 거신 ──
        m.put("m_meteor_rain", Sig.of()
                .track(Ev.Drop.class, (fx, e) -> new Track() {
                    @Override
                    public void tick(Location pos, Vector vel) {
                        Emit.send(fx, pos, Particle.FLAME, null, 2, 0.2, 0.2, 0.2, 0.01, Emit.NORMAL);
                    }

                    @Override
                    public void end(Location at, boolean impact) {
                        Location g = at.clone().add(0, 0.05, 0);
                        Pieces.fireSheets(fx, g, 0.2, 1, 1.8, 8, fx.cols());
                        Emit.send(fx, g.clone().add(0, 0.4, 0), Particle.LAVA, null, 4, 0.4, 0.2, 0.4, 0, Emit.NORMAL);
                        Kit.debris(fx, g, 2, 0.6, Material.MAGMA_BLOCK);
                    }
                }));

        m.put("m_fire_ring", Sig.of()
                .on(Ev.Windup.class, (fx, e) -> {
                    // 마지막 6틱: 테두리에서 불길이 솟는다 (곧 터진다는 신호)
                    List<Footprint> f = e.footprints().get();
                    if (f.isEmpty()) return;
                    fx.vfx.every(Math.max(0, e.ticks() - 6), 2, 3, i -> {
                        Footprint ff = e.footprints().get().isEmpty() ? f.get(0) : e.footprints().get().get(0);
                        for (Location p : Shapes.around(ff.c(), ff.r(), 18, i * 0.2)) {
                            Location gg = Kit.ground(p.clone().add(0, 1, 0));
                            Emit.dir(fx, gg.add(0, 0.1, 0), Particle.FLAME, null, new Vector(0, 1, 0), 0.2, Emit.TELE);
                        }
                    });
                })
                .replace(Ev.Nova.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.center());
                    Pieces.shockwave(fx, g, e.radius(), Math.max(3, e.expand()), new CastFx.Cols[]{fx.cols(), fx.cols().swap()}, 2, true);
                    fx.vfx.after(Math.max(1, e.expand()), () -> Pieces.fireSheets(fx, g, e.radius() * 0.97, 12, 2.6, 12, fx.cols()));
                }));

        m.put("m_flame_beam", Sig.of()
                .on(Ev.Windup.class, (fx, e) -> charge(fx, e.ticks(), fx.cols(), "entity.blaze.ambient"))
                .on(Ev.Beam.class, (fx, e) -> {
                    Vector d = e.dir().clone().normalize();
                    double len = e.start().distance(e.end());
                    for (double t = 3; t < len; t += 3) {
                        Location p = e.start().clone().add(d.clone().multiply(t));
                        Location g = Kit.groundOrNull(p);
                        if (g != null && p.getY() - g.getY() < 2.5) Pieces.fireSheets(fx, g, 0.1, 1, 1.6, 10, fx.cols());
                    }
                }));

        m.put("m_summon_imps", Sig.of());

        m.put("m_inferno_rage", Sig.of()
                .replace(Ev.Nova.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    // 미리 알림 없이 바로 터지는 반지름 6: 고리는 정확히 6에서 멈춘다
                    Location g = AreaFx.groundAt(e.center());
                    Pieces.shockwave(fx, g, e.radius(), 4, new CastFx.Cols[]{fx.cols(), fx.cols().swap(), fx.cols()}, 2, true);
                    Pieces.fireSheets(fx, g, e.radius() * 0.6, 8, 4, 16, fx.cols());
                    Kit.debris(fx, g, 12, 1.0, Material.MAGMA_BLOCK);
                    Emit.flash(fx, g.clone().add(0, 3, 0));
                }));

        // ── 공허의 군주 ──
        m.put("m_void_beam", Sig.of()
                .on(Ev.Windup.class, (fx, e) -> charge(fx, e.ticks(), fx.cols(), "entity.warden.sonic_charge")));

        m.put("m_void_hole", Sig.of()
                .replace(Ev.Vortex.class)
                .track(Ev.Vortex.class, (fx, e) -> {
                    Telegraph.vortexEnds(fx, e);
                    List<Sprite> bh = Pieces.blackHole(fx, e.center().clone().add(0, -0.8, 0), e.radius() * 0.7, e.duration() + 4);
                    return new Track() {
                        @Override
                        public void end(Location at, boolean impact) {
                            Pieces.collapse(bh);
                        }
                    };
                })
                .replace(Ev.Nova.class)
                .on(Ev.Nova.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.center());
                    Pieces.shockwave(fx, g, e.radius(), 3, new CastFx.Cols[]{fx.cols(), fx.cols().swap()}, 2, true);
                    Kit.star(fx, e.center().clone().add(0, 1, 0), 2.5, 5, fx.cols()).go();
                }));

        m.put("m_void_meteors", Sig.of()
                .track(Ev.Drop.class, (fx, e) -> new Track() {
                    @Override
                    public void tick(Location pos, Vector vel) {
                        Emit.send(fx, pos, Particle.REVERSE_PORTAL, null, 2, 0.15, 0.15, 0.15, 0.02, Emit.DETAIL);
                    }

                    @Override
                    public void end(Location at, boolean impact) {
                        Kit.star(fx, at.clone().add(0, 0.7, 0), 1.2, 4, fx.cols()).go();
                        Kit.debris(fx, at, 2, 0.6, Material.OBSIDIAN);
                    }
                }));

        m.put("m_void_blink_boss", Sig.of()
                .on(Ev.Blink.class, (fx, e) -> {
                    MeleeFx.portalSlit(fx, e.from(), 10, fx.cols(), Sprite.View.AUTO);
                    MeleeFx.portalSlit(fx, e.to(), 10, fx.cols(), Sprite.View.AUTO);
                }));

        m.put("m_summon_void", Sig.of());

        m.put("m_void_awaken", Sig.of().noDamage()
                .on(Ev.Buff.class, (fx, e) -> {
                    LivingEntity c = fx.caster;
                    Location top = c.getLocation().add(0, c.getHeight() + 6, 0);
                    String sm = fx.vfx.models.pick("swirl", "shock");
                    if (sm != null) {
                        Sprite sw = Kit.flat(fx, sm, top, 0.5, Shapes.Frame.FLAT, rgb(fx, 0x5a1a9a, 0xc86bff)).life(50).range(2);
                        sw.decal = true;
                        sw.edgeOn = 0.15;
                        sw.scaleTo(1, 8, 9 / Geo.FLAT_HALF, 1, 9 / Geo.FLAT_HALF);
                        Kit.spinOver(sw, 9, 40, -90);
                        sw.go();
                    }
                    Sprite core = Kit.orb(fx, c.getLocation().add(0, c.getHeight() + 1.5, 0), 0.5, 40, fx.cols(), fx.vfx.models.pick("void_orb", "orb"));
                    for (int i = 0; i < 4; i++) {
                        core.scaleTo(1 + i * 10, 5, 1.8);
                        core.scaleTo(6 + i * 10, 5, 1.0);
                    }
                    core.go();
                    fx.vfx.every(0, 2, 20, i -> Emit.send(fx, c.getLocation().add(0, 1.5, 0), Particle.REVERSE_PORTAL, null, 20, 4, 2, 4, 0.4, Emit.NORMAL));
                    fx.sound(c.getLocation(), "entity.warden.roar", 0.8, 0.8);
                }));

        // 일반 몹: 자동 예고만 (자폭·공허 붕괴는 원형 예고가 몹을 따라다닌다)
        m.put("m_self_destruct", Sig.of());
        m.put("m_void_explode", Sig.of());
    }

    static Color hazard() {
        return Telegraph.HAZ;
    }
}
