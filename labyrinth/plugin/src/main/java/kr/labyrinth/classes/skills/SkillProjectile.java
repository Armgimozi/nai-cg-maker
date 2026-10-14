package kr.labyrinth.classes.skills;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.util.function.BiConsumer;
import java.util.function.Consumer;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.util.Vector;

/**
 * 자체 투사체 (바닐라 화살 아님): fx 모델 ItemDisplay 를 틱마다 이동시키고 0.5칸 간격으로 블록·적 충돌을 검사한다.
 * 적 판정은 {@link Targeting}(TargetFilter). 관통·약유도 지원.
 */
public final class SkillProjectile {

    private final SkillContext ctx;
    private Location pos;
    private Vector dir;
    private double speed = 1.0;
    private double range = 20;
    private double hitRadius = 0.5;
    private int pierce = 1;
    private double homing;
    private LivingEntity homingTarget;
    private String model;
    private Particle trail = Particle.CRIT;
    private Object trailData;
    private BiConsumer<LivingEntity, Integer> onHit = (e, i) -> {};
    private Consumer<Location> onEnd = l -> {};

    public SkillProjectile(SkillContext ctx, Location start, Vector dir) {
        this.ctx = ctx;
        this.pos = start.clone();
        this.dir = dir.clone().normalize();
    }

    /** 틱당 이동 거리(블록). */
    public SkillProjectile speed(double blocksPerTick) { this.speed = Math.max(0.1, blocksPerTick); return this; }
    public SkillProjectile range(double r) { this.range = r; return this; }
    public SkillProjectile hitRadius(double r) { this.hitRadius = r; return this; }
    /** 최대 적중 수 (1 = 첫 적에서 멈춤). */
    public SkillProjectile pierce(int n) { this.pierce = Math.max(1, n); return this; }
    /** 0~1: 틱마다 대상 쪽으로 방향을 섞는 비율. */
    public SkillProjectile homing(double strength, LivingEntity target) { this.homing = strength; this.homingTarget = target; return this; }
    public SkillProjectile model(String fxModel) { this.model = fxModel; return this; }
    public SkillProjectile trail(Particle p, Object data) { this.trail = p; this.trailData = data; return this; }
    /** (대상, 몇 번째 적중 0~) */
    public SkillProjectile onHit(BiConsumer<LivingEntity, Integer> h) { this.onHit = h; return this; }
    public SkillProjectile onEnd(Consumer<Location> h) { this.onEnd = h; return this; }

    public void launch() {
        World w = pos.getWorld();
        if (w == null) return;
        Location face = pos.clone();
        face.setDirection(dir);
        ItemDisplay display = model == null ? null : SkillFx.spawn(model, face, 1f, 0);
        if (display != null) display.setTeleportDuration(1);
        Set<UUID> hit = new HashSet<>();
        int[] hits = {0};
        double[] travelled = {0};
        int maxSteps = (int) Math.ceil(range / speed) + 2;
        SkillTask.repeat(0, 1, maxSteps, step -> {
            if (!ctx.caster().isOnline()) return false;
            if (homing > 0 && homingTarget != null && homingTarget.isValid() && !homingTarget.isDead()) {
                Vector want = homingTarget.getBoundingBox().getCenter().subtract(pos.toVector());
                if (want.lengthSquared() > 1e-6) {
                    dir = dir.multiply(1 - homing).add(want.normalize().multiply(homing)).normalize();
                }
            }
            double moved = 0;
            while (moved < speed) {
                double sub = Math.min(0.5, speed - moved);
                Location next = pos.clone().add(dir.clone().multiply(sub));
                Block b = next.getBlock();
                if (!b.isPassable() && b.getBoundingBox().contains(next.toVector())) {
                    pos = next;
                    return false;
                }
                pos = next;
                moved += sub;
                travelled[0] += sub;
                for (LivingEntity e : ctx.targets().enemiesIn(pos, hitRadius + 1.5)) {
                    if (hit.contains(e.getUniqueId())) continue;
                    if (!e.getBoundingBox().clone().expand(hitRadius).contains(pos.toVector())) continue;
                    hit.add(e.getUniqueId());
                    onHit.accept(e, hits[0]++);
                    if (hits[0] >= pierce) return false;
                }
                if (travelled[0] >= range) return false;
            }
            if (display != null && display.isValid()) {
                Location l = pos.clone();
                l.setDirection(dir);
                display.teleport(l);
            }
            if (trail != null) w.spawnParticle(trail, pos, 2, 0.05, 0.05, 0.05, 0.0, trailData);
            return true;
        }, () -> {
            SkillFx.remove(display);
            onEnd.accept(pos.clone());
        });
    }
}
