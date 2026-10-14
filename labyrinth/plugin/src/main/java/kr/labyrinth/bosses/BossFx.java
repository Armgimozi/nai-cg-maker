package kr.labyrinth.bosses;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import kr.labyrinth.Services;
import kr.labyrinth.content.FxModelDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import kr.labyrinth.mobs.ModelRig;
import net.kyori.adventure.key.Key;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.SoundCategory;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.TextDisplay;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 보스 한 마리 몫의 시각 효과 부품 (GDD §8.1·§8.2·§14.6 크기 규칙): 바닥 경고 판, fx 모델 디스플레이, 머리 위 표식,
 * 늘인 테더, 글자 표시, 블록 디스플레이. 만든 엔티티는 전부 임시 태그(Keys.BOSS) + 이 객체가 추적 → {@link #clear()} 로 일괄 정리.
 * 블록은 절대 바꾸지 않는다.
 */
public final class BossFx {

    private final Services services;
    private final String tag;
    private final Set<Entity> spawned = new HashSet<>();

    public BossFx(Services services, String tag) {
        this.services = services;
        this.tag = tag;
    }

    double yawOffset() { return services.plugin().getConfig().getDouble("mobs.model_yaw_offset", 0.0); }

    public static Key fxKey(String model) { return Key.key(Keys.NS, "fx/" + model); }

    /** fx 모델 기본 크기(블록) [w, h, d]. 정의가 없으면 def. */
    public double[] size(String model, double def) {
        FxModelDef d = services.content().fxModels().get(model);
        double[] out = {def, def, def};
        if (d == null || d.size() == null) return out;
        for (int i = 0; i < Math.min(3, d.size().size()); i++) if (d.size().get(i) > 0) out[i] = d.size().get(i) / 16.0;
        return out;
    }

    // ── 바닥 경고 판 ─────────────────────────────────────────────────────

    /** 도형에 맞춘 바닥 판 (ARCHITECTURE §2 fx 앵커·크기 규칙). */
    public ItemDisplay plate(Telegraph.Shape s, String model) {
        Location at = s.origin().clone();
        if (s.kind() == Telegraph.Kind.TILE) at.add(s.size() / 2, 0, s.size() / 2);
        float[] sc = plateScale(s, model);
        return flat(model, at.add(0, 0.03, 0), sc[0], sc[1], plateYaw(s));
    }

    private float[] plateScale(Telegraph.Shape s, String model) {
        double[] base = size(model, 2.0);
        double w = base[0], d = base[2];
        return switch (s.kind()) {
            case CIRCLE, SAFE, RING -> new float[]{(float) (s.size() * 2 / w), (float) (s.size() * 2 / d)};
            case LINE, ARROW -> new float[]{(float) (s.width() / w), (float) (s.size() / d)};
            case CONE -> {
                float z = (float) (s.size() / d);
                double half = Math.toRadians(Math.min(160, Math.max(10, s.angle())) / 2);
                yield new float[]{(float) (z * Math.tan(half)), z};
            }
            case TILE -> new float[]{(float) (s.size() / w), (float) (s.size() / d)};
        };
    }

    private static float plateYaw(Telegraph.Shape s) {
        return switch (s.kind()) {
            case LINE, ARROW, CONE -> BossMath.yawOf(s.dirX(), s.dirZ());
            default -> 0f;
        };
    }

    /** 판 위치·방향 갱신 (보간 2틱). */
    public void movePlate(ItemDisplay d, Telegraph.Shape s) {
        if (d == null || !d.isValid()) return;
        Location at = s.origin().clone().add(0, 0.03, 0);
        at.setYaw(0);
        at.setPitch(0);
        d.teleport(at);
        Transformation tr = d.getTransformation();
        Quaternionf q = yawQ(plateYaw(s));
        if (!q.equals(tr.getLeftRotation(), 1e-4f)) {
            d.setInterpolationDelay(0);
            d.setInterpolationDuration(2);
            d.setTransformation(new Transformation(new Vector3f(), q, tr.getScale(), new Quaternionf()));
        }
    }

    private Quaternionf yawQ(float yawDeg) {
        Quaternionf q = new Quaternionf().rotationY((float) Math.toRadians(-yawDeg));
        double off = yawOffset();
        if (off != 0) q.rotateY((float) Math.toRadians(off));
        return q;
    }

    /** 바닥에 눕힌 fx 디스플레이 (flat 모델은 원래 수평). */
    public ItemDisplay flat(String model, Location at, float scaleX, float scaleZ, float yawDeg) {
        World w = at.getWorld();
        if (w == null) return null;
        Location l = at.clone();
        l.setYaw(0);
        l.setPitch(0);
        Quaternionf q = yawQ(yawDeg);
        ItemDisplay d = w.spawn(l, ItemDisplay.class, e -> {
            e.setPersistent(false);
            e.setItemStack(ModelRig.modelItem(fxKey(model)));
            e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
            e.setBrightness(new Display.Brightness(13, 15));
            e.setViewRange(1.0f);
            e.setTeleportDuration(2);
            e.setTransformation(new Transformation(new Vector3f(), q, new Vector3f(scaleX, 1f, scaleZ), new Quaternionf()));
            Keys.tagTransient(e, Keys.FX, tag);
        });
        spawned.add(d);
        return d;
    }

    /** 일반 fx 모델 디스플레이 (오브젝트·투사체·말뚝). */
    public ItemDisplay model(String model, Location at, float scale, Display.Billboard billboard) {
        World w = at.getWorld();
        if (w == null) return null;
        Location l = at.clone();
        l.setPitch(0);
        float yaw = l.getYaw();
        l.setYaw(0);
        FxModelDef def = services.content().fxModels().get(model);
        boolean glow = def != null && def.glow();
        Quaternionf q = yawQ(yaw);
        ItemDisplay d = w.spawn(l, ItemDisplay.class, e -> {
            e.setPersistent(false);
            e.setItemStack(ModelRig.modelItem(fxKey(model)));
            e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
            e.setBillboard(billboard == null ? Display.Billboard.FIXED : billboard);
            e.setBrightness(new Display.Brightness(glow ? 15 : 12, 15));
            e.setViewRange(1.0f);
            e.setTeleportDuration(2);
            e.setTransformation(new Transformation(new Vector3f(), q, new Vector3f(scale, scale, scale), new Quaternionf()));
            Keys.tagTransient(e, Keys.FX, tag);
        });
        spawned.add(d);
        return d;
    }

    public static Display.Billboard billboardOf(FxModelDef def) {
        if (def == null || def.billboard() == null) return Display.Billboard.FIXED;
        try {
            return Display.Billboard.valueOf(def.billboard().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            return Display.Billboard.FIXED;
        }
    }

    /** 진행 방향을 보도록 회전 (투사체·테더). */
    public void orient(ItemDisplay d, Vector dir, float scaleXY, float scaleZ, int interp) {
        if (d == null || !d.isValid()) return;
        double h = Math.sqrt(dir.getX() * dir.getX() + dir.getZ() * dir.getZ());
        float yaw = BossMath.yawOf(dir.getX(), dir.getZ());
        float pitch = (float) Math.toDegrees(Math.atan2(-dir.getY(), Math.max(1e-6, h)));
        Quaternionf q = new Quaternionf().rotationY((float) Math.toRadians(-yaw)).rotateX((float) Math.toRadians(pitch));
        double off = yawOffset();
        if (off != 0) q.rotateY((float) Math.toRadians(off));
        d.setInterpolationDelay(0);
        d.setInterpolationDuration(Math.max(0, interp));
        d.setTransformation(new Transformation(new Vector3f(), q, new Vector3f(scaleXY, scaleXY, scaleZ), new Quaternionf()));
    }

    /** 두 점 사이 늘인 테더 (모델 길이 = size d). */
    public ItemDisplay tether(String model, Location a, Location b) {
        ItemDisplay d = model(model, a, 1f, Display.Billboard.FIXED);
        updateTether(d, model, a, b);
        return d;
    }

    public void updateTether(ItemDisplay d, String model, Location a, Location b) {
        if (d == null || !d.isValid() || a.getWorld() != b.getWorld()) return;
        Vector v = b.toVector().subtract(a.toVector());
        double len = v.length();
        if (len < 0.05) return;
        double base = size(model, 1.0)[2];
        Location mid = a.clone().add(v.clone().multiply(0.5));
        mid.setYaw(0);
        mid.setPitch(0);
        d.teleport(mid);
        orient(d, v, 1f, (float) (len / base), 2);
    }

    // ── 글자 ─────────────────────────────────────────────────────────────

    public TextDisplay label(Location at, String mm, float scale) {
        World w = at.getWorld();
        if (w == null) return null;
        TextDisplay t = w.spawn(at.clone(), TextDisplay.class, e -> {
            e.setPersistent(false);
            e.setBillboard(Display.Billboard.VERTICAL);
            e.setShadowed(true);
            e.setDefaultBackground(false);
            e.setBackgroundColor(Color.fromARGB(90, 0, 0, 0));
            e.setAlignment(TextDisplay.TextAlignment.CENTER);
            e.setBrightness(new Display.Brightness(15, 15));
            e.setViewRange(0.8f);
            e.setTeleportDuration(2);
            e.setTransformation(new Transformation(new Vector3f(), new Quaternionf(), new Vector3f(scale, scale, scale), new Quaternionf()));
            e.text(Text.mm(mm));
            Keys.tagTransient(e, Keys.FX, tag);
        });
        spawned.add(t);
        return t;
    }

    public static void text(TextDisplay t, String mm) {
        if (t != null && t.isValid()) t.text(Text.mm(mm));
    }

    /** 블록 모양 디스플레이 (인스턴스 밖 관리자 소환에서 블록 대신 쓰는 가짜 기둥·밸브). */
    public BlockDisplay block(Location corner, BlockData data, float sx, float sy, float sz) {
        World w = corner.getWorld();
        if (w == null) return null;
        BlockDisplay d = w.spawn(corner.clone(), BlockDisplay.class, e -> {
            e.setPersistent(false);
            e.setBlock(data);
            e.setBrightness(new Display.Brightness(12, 15));
            e.setTransformation(new Transformation(new Vector3f(), new Quaternionf(), new Vector3f(sx, sy, sz), new Quaternionf()));
            Keys.tagTransient(e, Keys.FX, tag);
        });
        spawned.add(d);
        return d;
    }

    // ── 정리 ─────────────────────────────────────────────────────────────

    public void track(Entity e) { if (e != null) spawned.add(e); }

    public void discard(Entity e) {
        if (e == null) return;
        if (e.isValid()) e.remove();
        spawned.remove(e);
    }

    public void clear() {
        for (Entity e : new ArrayList<>(spawned)) if (e.isValid()) e.remove();
        spawned.clear();
    }

    public void sweep() { spawned.removeIf(e -> !e.isValid()); }

    public List<java.util.UUID> ids() {
        List<java.util.UUID> out = new ArrayList<>();
        for (Entity e : spawned) out.add(e.getUniqueId());
        return out;
    }

    // ── 지면·입자·소리 ───────────────────────────────────────────────────

    /** 발밑 지면 높이 (공중이면 아래로 최대 8칸 찾음). */
    public double groundY(Location l) {
        World w = l.getWorld();
        if (w == null) return l.getY();
        int x = l.getBlockX(), z = l.getBlockZ();
        int y = (int) Math.floor(l.getY() + 0.01);
        for (int i = 0; i <= 8; i++) {
            Block b = w.getBlockAt(x, y - 1 - i, z);
            if (b.getType().isSolid()) return y - i;
        }
        return l.getY();
    }

    /** 도형 윤곽 DUST 입자. */
    public void outline(Telegraph.Shape s, Color color, float size) {
        World w = s.origin().getWorld();
        if (w == null) return;
        Particle.DustOptions dust = new Particle.DustOptions(color, size);
        double y = s.origin().getY() + 0.15;
        double ox = s.origin().getX(), oz = s.origin().getZ();
        switch (s.kind()) {
            case CIRCLE, SAFE, RING -> {
                int n = (int) Math.max(12, Math.min(72, s.size() * 7));
                for (int i = 0; i < n; i++) {
                    double a = 2 * Math.PI * i / n;
                    w.spawnParticle(Particle.DUST, ox + Math.cos(a) * s.size(), y, oz + Math.sin(a) * s.size(), 1, 0, 0, 0, 0, dust);
                    if (s.kind() == Telegraph.Kind.RING && s.width() > 0.3 && i % 2 == 0) {
                        w.spawnParticle(Particle.DUST, ox + Math.cos(a) * s.width(), y, oz + Math.sin(a) * s.width(), 1, 0, 0, 0, 0, dust);
                    }
                }
            }
            case LINE, ARROW -> {
                Vector d = s.direction();
                Vector side = new Vector(-d.getZ(), 0, d.getX()).multiply(s.width() / 2);
                int n = (int) Math.max(4, Math.min(56, s.size() * 1.6));
                for (int i = 0; i <= n; i++) {
                    double f = s.size() * i / n;
                    double x = ox + d.getX() * f, z = oz + d.getZ() * f;
                    w.spawnParticle(Particle.DUST, x + side.getX(), y, z + side.getZ(), 1, 0, 0, 0, 0, dust);
                    w.spawnParticle(Particle.DUST, x - side.getX(), y, z - side.getZ(), 1, 0, 0, 0, 0, dust);
                }
            }
            case CONE -> {
                double base = Math.atan2(s.dirZ(), s.dirX());
                double half = Math.toRadians(s.angle() / 2);
                int n = (int) Math.max(8, Math.min(40, s.size() * s.angle() / 18));
                for (int i = 0; i <= n; i++) {
                    double a = base - half + 2 * half * i / n;
                    w.spawnParticle(Particle.DUST, ox + Math.cos(a) * s.size(), y, oz + Math.sin(a) * s.size(), 1, 0, 0, 0, 0, dust);
                }
                int m = (int) Math.max(3, s.size() * 1.5);
                for (int i = 0; i <= m; i++) {
                    double f = s.size() * i / m;
                    w.spawnParticle(Particle.DUST, ox + Math.cos(base - half) * f, y, oz + Math.sin(base - half) * f, 1, 0, 0, 0, 0, dust);
                    w.spawnParticle(Particle.DUST, ox + Math.cos(base + half) * f, y, oz + Math.sin(base + half) * f, 1, 0, 0, 0, 0, dust);
                }
            }
            case TILE -> {
                double e = s.size();
                for (int i = 0; i <= 4; i++) {
                    double f = e * i / 4;
                    w.spawnParticle(Particle.DUST, ox + f, y, oz, 1, 0, 0, 0, 0, dust);
                    w.spawnParticle(Particle.DUST, ox + f, y, oz + e, 1, 0, 0, 0, 0, dust);
                    w.spawnParticle(Particle.DUST, ox, y, oz + f, 1, 0, 0, 0, 0, dust);
                    w.spawnParticle(Particle.DUST, ox + e, y, oz + f, 1, 0, 0, 0, 0, dust);
                }
            }
        }
    }

    public static void dust(Location at, Color c, float size, int count, double spread) {
        if (at.getWorld() == null) return;
        at.getWorld().spawnParticle(Particle.DUST, at, count, spread, spread, spread, 0, new Particle.DustOptions(c, size));
    }

    /** 데이터가 필요 없는 입자만 (데이터가 필요한 입자는 무시). */
    public static void particle(Particle p, Location at, int count, double dx, double dy, double dz, double speed) {
        if (p == null || at.getWorld() == null) return;
        if (p.getDataType() != Void.class) return;
        at.getWorld().spawnParticle(p, at, count, dx, dy, dz, speed);
    }

    public static void ring(Location c, double r, Particle p, int n) {
        for (int i = 0; i < n; i++) {
            double a = 2 * Math.PI * i / n;
            particle(p, c.clone().add(Math.cos(a) * r, 0.15, Math.sin(a) * r), 1, 0, 0, 0, 0);
        }
    }

    public static void dustRing(Location c, double r, Color color, float size, int n) {
        for (int i = 0; i < n; i++) {
            double a = 2 * Math.PI * i / n;
            dust(c.clone().add(Math.cos(a) * r, 0.15, Math.sin(a) * r), color, size, 1, 0);
        }
    }

    public static void dustLine(Location a, Location b, Color color, float size, double step) {
        if (a.getWorld() != b.getWorld()) return;
        Vector v = b.toVector().subtract(a.toVector());
        double len = v.length();
        if (len < 1e-3) return;
        v.multiply(1 / len);
        for (double f = 0; f <= len; f += step) dust(a.clone().add(v.clone().multiply(f)), color, size, 1, 0);
    }

    public static void sound(Location at, Sound s, float volume, float pitch) {
        if (at.getWorld() != null) at.getWorld().playSound(at, s, SoundCategory.HOSTILE, volume, pitch);
    }

    /** YAML 사운드 키 (잘못된 키는 무시). */
    public static void sound(Location at, String key, float volume, float pitch) {
        if (key == null || key.isBlank() || at.getWorld() == null) return;
        try {
            at.getWorld().playSound(at, key, SoundCategory.HOSTILE, volume, pitch);
        } catch (Throwable ignored) {
            // 잘못된 사운드 키
        }
    }
}
