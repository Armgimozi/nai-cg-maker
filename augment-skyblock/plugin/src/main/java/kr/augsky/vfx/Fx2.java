package kr.augsky.vfx;

import kr.augsky.util.Fx;
import org.bukkit.Material;
import org.bukkit.Particle;

/** 자주 쓰는 입자 묶음 */
final class Fx2 {
    private Fx2() {}

    static final Fx.Spec LEAVES = new Fx.Spec(Particle.BLOCK, Material.AZALEA_LEAVES.createBlockData());
    static final Fx.Spec END_ROD = new Fx.Spec(Particle.END_ROD, null);
    static final Fx.Spec FIREWORK = new Fx.Spec(Particle.FIREWORK, null);
    static final Fx.Spec FLAME = new Fx.Spec(Particle.FLAME, null);
    static final Fx.Spec SOUL = new Fx.Spec(Particle.SOUL_FIRE_FLAME, null);
    static final Fx.Spec SPARK = new Fx.Spec(Particle.ELECTRIC_SPARK, null);
    static final Fx.Spec SNOW = new Fx.Spec(Particle.SNOWFLAKE, null);
    static final Fx.Spec PORTAL_IN = new Fx.Spec(Particle.REVERSE_PORTAL, null);
}
