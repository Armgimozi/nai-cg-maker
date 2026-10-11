package kr.augsky.vfx;

import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.util.Vector;

import java.util.Map;

/**
 * 섬·균열 등급 무기의 몇몇 기술 전용 연출. 기본 연출로는 이름과 모양이 어긋나는 것(광선으로 그려지는 '베기')과
 * 섬 등급에서 너무 수수했던 것에 한 가지씩 굵은 요소를 더한다.
 */
final class RiftSigs {
    private RiftSigs() {}

    static void register(Map<String, Signature> m) {
        // 공허 베기: 판정은 광선이지만 보이는 것은 날아가는 보랏빛 초승달 둘 + 지나간 자리의 공허 물결
        m.put("void_slash", Sig.of()
                .replace(Ev.Beam.class)
                .on(Ev.Beam.class, (fx, e) -> RangedFx.slashWave(fx, e, PrismSigs.rgb(fx, 0x9a3aff, 0xe6b0ff), 1.0, 34, true)));

        // 지진(섬): 땅이 갈라지며 퍼지는 금 + 먼지 고리 + 가장자리에서 튀어 오르는 흙덩이
        m.put("earthquake", Sig.of()
                .on(Ev.Nova.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.center());
                    double r = e.radius();
                    int ex = Math.max(3, e.expand());
                    CastFx.Cols k = PrismSigs.rgb(fx, 0xc8a060, 0xf0d090);
                    String cm = fx.vfx.models.pick("crack", "shock_dim");
                    if (cm != null && Kit.decalFits(g, r)) {
                        Sprite cr = Kit.flat(fx, cm, g.clone().add(0, 0.04, 0), 0.6, Shapes.Frame.FLAT.yaw(Kit.rnd().nextDouble(360)),
                                new CastFx.Cols(Color.fromRGB(0xe0b060), Color.fromRGB(0xfff0c0), Color.fromRGB(0x4a3218), Color.fromRGB(0x6a4a20), false))
                                .life(ex + 26).end(Sprite.End.FADE, 8);
                        cr.scaleTo(1, ex, r * 0.85 / Geo.FLAT_HALF, 1, r * 0.85 / Geo.FLAT_HALF).radius(r * 0.85);
                        cr.go();
                    }
                    // 파동을 따라 바깥으로 밀려나는 먼지 고리
                    fx.vfx.every(0, 1, ex, i -> {
                        double rr = r * (i + 1) / ex;
                        for (Location p : Shapes.around(g, rr, fx.n(10 + rr * 2), i * 0.4)) {
                            Emit.send(fx, p.clone().add(0, 0.15, 0), Particle.DUST_PLUME, null, 1, 0.1, 0.05, 0.1, 0.02, Emit.NORMAL);
                            if (i % 2 == 0) Emit.send(fx, p.clone().add(0, 0.2, 0), Particle.BLOCK_CRUMBLE,
                                    Kit.groundMaterial(p, Material.DIRT).createBlockData(), 2, 0.2, 0.1, 0.2, 0.1, Emit.DETAIL);
                        }
                    });
                    // 가장자리에서 흙덩이가 솟았다 가라앉는다 (팩 없이도 보이는 블록 조각)
                    fx.vfx.after(Math.max(1, ex - 2), () -> {
                        int n = 6;
                        for (Location p : Shapes.around(g, r * 0.9, n, Kit.rnd().nextDouble(Math.PI))) {
                            Material mt = Kit.groundMaterial(p, Material.DIRT);
                            Sprite s = Sprite.block(fx, mt.createBlockData(), p.clone().add(0, -0.4, 0)).size(0.7).worldLight()
                                    .life(14).end(Sprite.End.SHRINK, 5).radius(0.5);
                            s.rot.rotateXYZ((float) Kit.rnd().nextDouble(-0.4, 0.4), (float) Kit.rnd().nextDouble(3), (float) Kit.rnd().nextDouble(-0.4, 0.4));
                            s.moveBy(1, 3, 0, 0.8, 0);
                            s.go();
                        }
                        fx.sound(g, "block.rooted_dirt.break", 1.0, 0.6);
                    });
                }));

        // 신성 강타(섬): 빛기둥 위에 오래 떠 있는 금빛 후광 + 바닥에 남는 빛 문양
        m.put("holy_smite", Sig.of()
                .on(Ev.Strike.class, (fx, e) -> {
                    Location g = AreaFx.groundAt(e.point().clone().add(0, 0.5, 0));
                    CastFx.Cols gold = PrismSigs.rgb(fx, 0xffc030, 0xfff6c8);
                    Sprite halo = Kit.ring(fx, g.clone().add(0, 3.4, 0), 0.3, 1.1, 4, 30, gold, null).end(Sprite.End.FADE, 8);
                    halo.decal = false;
                    Kit.spinOver(halo, 5, 24, 90);
                    halo.go();
                    Kit.afterglow(fx, g, 1.8, 34, gold);
                    fx.vfx.every(2, 4, 7, i -> {
                        for (Location p : Shapes.around(g.clone().add(0, 3.4, 0), 1.1, 6, i * 0.5))
                            Emit.send(fx, p, Particle.WAX_OFF, null, 1, 0.02, 0.02, 0.02, 0, Emit.DETAIL);
                        Emit.send(fx, g.clone().add(0, 1.2, 0), Particle.END_ROD, null, 1, 0.3, 0.8, 0.3, 0.01, Emit.DETAIL);
                    });
                }));
    }

    static Vector up() {
        return new Vector(0, 1, 0);
    }
}
