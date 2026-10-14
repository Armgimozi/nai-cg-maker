package kr.labyrinth.classes.skills;

import io.papermc.paper.datacomponent.DataComponentTypes;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.content.FxModelDef;
import kr.labyrinth.core.Keys;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 직업 스킬·상태이상 연출 헬퍼: fx.yml 이펙트 모델(ItemDisplay, labyrinth:fx/&lt;name&gt;) + 파티클 도형 + 소리.
 * 모든 디스플레이는 {@code Keys.tagTransient(FX)} + 비영구, 수명이 끝나면 지워지고 모듈 종료 시 {@link #removeAll}.
 * 리소스팩에 모델이 없거나 fx.yml 에 정의가 없으면 디스플레이는 건너뛰고 파티클만 낸다.
 */
public final class SkillFx {

    private static final Set<ItemDisplay> LIVE = ConcurrentHashMap.newKeySet();

    private SkillFx() {}

    // ── 이펙트 모델 ───────────────────────────────────────────────────────

    /** fx 모델의 화면 너비(블록, size[0]/16). 정의가 없으면 1. */
    public static double modelWidth(String model) {
        FxModelDef d = Services.get().content().fxModels().get(model);
        if (d == null || d.size() == null || d.size().isEmpty()) return 1.0;
        return Math.max(0.0625, d.size().get(0) / 16.0);
    }

    /**
     * 이펙트 모델 띄우기. @param scale 모델 기본 크기 배율 @param lifeTicks 수명(0 이하 = 직접 제거)
     * @return 디스플레이 (모델 정의가 없으면 null)
     */
    public static ItemDisplay spawn(String model, Location at, float scale, int lifeTicks) {
        if (model == null || at.getWorld() == null) return null;
        FxModelDef def = Services.get().content().fxModels().get(model);
        if (def == null) return null;
        ItemStack stack = ItemStack.of(Material.PAPER);
        stack.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "fx/" + model));
        Display.Billboard bb = billboard(def.billboard());
        ItemDisplay d = at.getWorld().spawn(at, ItemDisplay.class, e -> {
            e.setPersistent(false);
            Keys.tagTransient(e, Keys.FX, "skill:" + model);
            e.setItemStack(stack);
            e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
            e.setBillboard(bb);
            if (def.glow() || def.animated()) e.setBrightness(new Display.Brightness(15, 15));
            e.setViewRange(1.5f);
            e.setShadowRadius(0f);
            e.setTransformation(new Transformation(new Vector3f(), new Quaternionf(), new Vector3f(scale, scale, scale),
                    new Quaternionf()));
        });
        LIVE.add(d);
        if (lifeTicks > 0) removeLater(d, lifeTicks);
        return d;
    }

    /** 바닥 고리/장판: 지름 diameter 블록이 되도록 크기를 맞추고, growTicks 동안 작은 크기에서 커진다. */
    public static ItemDisplay ground(String model, Location center, double diameter, int lifeTicks, int growTicks) {
        float full = (float) (diameter / modelWidth(model));
        Location at = center.clone();
        at.setPitch(0);
        ItemDisplay d = spawn(model, at.add(0, 0.05, 0), growTicks > 0 ? full * 0.15f : full, lifeTicks);
        if (d != null && growTicks > 0) scaleTo(d, full, growTicks);
        return d;
    }

    /** 다음 틱부터 ticks 동안 보간으로 scale 까지 키운다. */
    public static void scaleTo(ItemDisplay d, float scale, int ticks) {
        later(1, () -> {
            if (!d.isValid()) return;
            Transformation t = d.getTransformation();
            d.setInterpolationDelay(0);
            d.setInterpolationDuration(Math.max(1, ticks));
            d.setTransformation(new Transformation(t.getTranslation(), t.getLeftRotation(), new Vector3f(scale, scale, scale),
                    t.getRightRotation()));
        });
    }

    /** Y축 회전 애니메이션 (degPerTick). 수명 동안 10틱마다 보간. */
    public static void spin(ItemDisplay d, float degPerTick, int lifeTicks) {
        if (d == null) return;
        final float[] angle = {0};
        for (int t = 1; t < lifeTicks; t += 10) {
            later(t, () -> {
                if (!d.isValid()) return;
                angle[0] += degPerTick * 10;
                Transformation tr = d.getTransformation();
                d.setInterpolationDelay(0);
                d.setInterpolationDuration(10);
                d.setTransformation(new Transformation(tr.getTranslation(),
                        new Quaternionf().rotationY((float) Math.toRadians(angle[0])), tr.getScale(), tr.getRightRotation()));
            });
        }
    }

    /** 엔티티 머리 위를 따라다니는 표식 (탑승 디스플레이). */
    public static ItemDisplay attach(String model, Entity host, double yOffset, float scale, int lifeTicks) {
        ItemDisplay d = spawn(model, host.getLocation(), scale, lifeTicks);
        if (d == null) return null;
        Transformation t = d.getTransformation();
        d.setTransformation(new Transformation(new Vector3f(0, (float) yOffset, 0), t.getLeftRotation(), t.getScale(),
                t.getRightRotation()));
        if (!host.addPassenger(d)) {
            d.remove();
            LIVE.remove(d);
            return null;
        }
        return d;
    }

    public static void remove(ItemDisplay d) {
        if (d == null) return;
        LIVE.remove(d);
        if (d.isValid()) d.remove();
    }

    public static void removeLater(ItemDisplay d, int ticks) { later(ticks, () -> remove(d)); }

    public static void removeAll() {
        for (ItemDisplay d : LIVE) if (d.isValid()) d.remove();
        LIVE.clear();
    }

    private static Display.Billboard billboard(String s) {
        if (s == null) return Display.Billboard.FIXED;
        try {
            return Display.Billboard.valueOf(s.toUpperCase(java.util.Locale.ROOT));
        } catch (IllegalArgumentException e) {
            return Display.Billboard.FIXED;
        }
    }

    // ── 파티클 도형 ───────────────────────────────────────────────────────

    public static Particle.DustOptions dust(int rgb, float size) { return new Particle.DustOptions(Color.fromRGB(rgb), size); }

    public static void circle(Location center, double radius, int points, Particle particle, Object data) {
        World w = center.getWorld();
        if (w == null) return;
        for (int i = 0; i < points; i++) {
            double a = Math.PI * 2 * i / points;
            Location l = center.clone().add(Math.cos(a) * radius, 0, Math.sin(a) * radius);
            spawn(w, particle, l, 1, 0, data);
        }
    }

    /** 원판 안을 무작위로 채운다. */
    public static void disc(Location center, double radius, int count, Particle particle, Object data) {
        World w = center.getWorld();
        if (w == null) return;
        var rnd = java.util.concurrent.ThreadLocalRandom.current();
        for (int i = 0; i < count; i++) {
            double r = radius * Math.sqrt(rnd.nextDouble());
            double a = rnd.nextDouble() * Math.PI * 2;
            spawn(w, particle, center.clone().add(Math.cos(a) * r, 0.1, Math.sin(a) * r), 1, 0, data);
        }
    }

    public static void line(Location from, Location to, double step, Particle particle, Object data) {
        World w = from.getWorld();
        if (w == null || to.getWorld() != w) return;
        Vector d = to.toVector().subtract(from.toVector());
        double len = d.length();
        if (len < 1e-6) return;
        d.multiply(1.0 / len);
        for (double t = 0; t <= len; t += step) spawn(w, particle, from.clone().add(d.clone().multiply(t)), 1, 0, data);
    }

    /** 수평 부채꼴 호 (angleDeg) — 베기 궤적. */
    public static void arc(Location origin, Vector dir, double radius, double angleDeg, int points, Particle particle, Object data) {
        World w = origin.getWorld();
        if (w == null) return;
        double base = Math.atan2(dir.getZ(), dir.getX());
        double half = Math.toRadians(angleDeg) / 2;
        for (int i = 0; i <= points; i++) {
            double a = base - half + (2 * half) * i / Math.max(1, points);
            spawn(w, particle, origin.clone().add(Math.cos(a) * radius, 0, Math.sin(a) * radius), 1, 0, data);
        }
    }

    /** 나선 기둥 (치유·버프 상승 연출). */
    public static void helix(Location base, double radius, double height, int points, Particle particle, Object data) {
        World w = base.getWorld();
        if (w == null) return;
        for (int i = 0; i < points; i++) {
            double t = (double) i / points;
            double a = t * Math.PI * 4;
            spawn(w, particle, base.clone().add(Math.cos(a) * radius, t * height, Math.sin(a) * radius), 1, 0, data);
            spawn(w, particle, base.clone().add(Math.cos(a + Math.PI) * radius, t * height, Math.sin(a + Math.PI) * radius), 1, 0, data);
        }
    }

    public static void burst(Location at, Particle particle, int count, double spread, double speed, Object data) {
        World w = at.getWorld();
        if (w == null) return;
        if (data != null) w.spawnParticle(particle, at, count, spread, spread, spread, speed, data);
        else w.spawnParticle(particle, at, count, spread, spread, spread, speed);
    }

    private static void spawn(World w, Particle p, Location l, int count, double speed, Object data) {
        if (data != null) w.spawnParticle(p, l, count, 0, 0, 0, speed, data);
        else w.spawnParticle(p, l, count, 0, 0, 0, speed);
    }

    // ── 소리 ──────────────────────────────────────────────────────────────

    public static void sound(Location at, Sound sound, float volume, float pitch) {
        if (at.getWorld() != null) at.getWorld().playSound(at, sound, volume, pitch);
    }

    // ── 스케줄 ────────────────────────────────────────────────────────────

    public static void later(long ticks, Runnable r) {
        Bukkit.getScheduler().runTaskLater(Services.get().plugin(), () -> {
            try {
                r.run();
            } catch (Throwable t) {
                kr.labyrinth.core.Log.error("스킬 연출 오류", t);
            }
        }, Math.max(1, ticks));
    }
}
