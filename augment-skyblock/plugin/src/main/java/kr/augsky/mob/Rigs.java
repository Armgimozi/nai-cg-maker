package kr.augsky.mob;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Display;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.util.Transformation;
import org.joml.Quaternionf;
import org.joml.Vector3f;

import java.io.File;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.logging.Logger;

/**
 * 보스 3D 모델. 바닐라 몹은 투명하게 두고, 여러 조각(ItemDisplay)을 매 2틱마다 보스 위치로 옮기며
 * 떠다니기/흔들기/회전/공전/휘두르기 동작을 붙인다. 조각 정의는 rigs.yml (리소스팩을 만들 때 함께 생성).
 * 조각 모델의 (8,8,8) 이 회전 중심이고, 모델의 앞은 +Z, 보스 기준 좌표도 +Z 가 앞이다.
 */
public final class Rigs {
    public record Anim(String type, char axis, double amplitude, double angle, double period, double phase,
                       double speed, double radius, double height, int ticks) {}

    public record Part(String id, NamespacedKey model, double ox, double oy, double oz, float scale,
                       float pitch, float yaw, float roll, boolean world, List<Anim> anims) {}

    public record Def(String id, List<Part> parts) {}

    private static final class Instance {
        final LivingEntity boss;
        final Def def;
        final List<ItemDisplay> displays = new ArrayList<>();
        int age;
        int swingAt = -1000;
        int flashUntil = -1;

        Instance(LivingEntity boss, Def def) {
            this.boss = boss;
            this.def = def;
        }
    }

    private static final int STEP = 2;
    /** 아이템 디스플레이는 모델을 Y축으로 180도 돌려 그리므로 되돌린다. */
    private static final Quaternionf FLIP = new Quaternionf().rotateY((float) Math.PI);

    private final AugSky plugin;
    private final Logger log;
    private final Map<String, Def> defs = new HashMap<>();
    private final Map<UUID, Instance> live = new HashMap<>();

    public Rigs(AugSky plugin) {
        this.plugin = plugin;
        this.log = plugin.getLogger();
        load();
        Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 5, STEP);
    }

    // ------------------------------------------------------------------ 정의

    public void load() {
        defs.clear();
        YamlConfiguration y;
        File f = new File(plugin.getDataFolder(), "rigs.yml");
        if (f.exists()) {
            y = YamlConfiguration.loadConfiguration(f);
        } else if (plugin.getResource("rigs.yml") != null) {
            y = YamlConfiguration.loadConfiguration(new InputStreamReader(plugin.getResource("rigs.yml"), StandardCharsets.UTF_8));
        } else {
            return;
        }
        for (String id : y.getKeys(false)) {
            ConfigurationSection sec = y.getConfigurationSection(id);
            if (sec == null) continue;
            List<Part> parts = new ArrayList<>();
            for (Map<?, ?> m : sec.getMapList("parts")) {
                try {
                    parts.add(part(m));
                } catch (RuntimeException ex) {
                    log.warning("rigs.yml " + id + ": 조각을 읽지 못함 " + m + " (" + ex.getMessage() + ")");
                }
            }
            if (!parts.isEmpty()) defs.put(id, new Def(id, parts));
        }
        log.info("보스 모델 " + defs.size() + "개");
    }

    private static Part part(Map<?, ?> m) {
        String id = String.valueOf(m.get("id"));
        String model = String.valueOf(m.get("model"));
        NamespacedKey key = NamespacedKey.fromString(model.contains(":") ? model : "augsky:" + model);
        double[] off = vec(m.get("offset"), 0);
        double[] rot = vec(m.get("rotation"), 0);
        float scale = (float) num(m.get("scale"), 1);
        boolean world = "world".equals(String.valueOf(m.get("frame")));
        List<Anim> anims = new ArrayList<>();
        Object al = m.get("anims");
        if (al instanceof List<?> list) {
            for (Object o : list) {
                if (!(o instanceof Map<?, ?> a)) continue;
                String axis = String.valueOf(a.containsKey("axis") ? a.get("axis") : "y");
                anims.add(new Anim(String.valueOf(a.get("type")), axis.isEmpty() ? 'y' : axis.charAt(0),
                        num(a.get("amplitude"), 0), num(a.get("angle"), 0), Math.max(1, num(a.get("period"), 40)),
                        num(a.get("phase"), 0), num(a.get("speed"), 0), num(a.get("radius"), 0),
                        num(a.get("height"), 0), (int) Math.max(1, num(a.get("ticks"), 12))));
            }
        }
        return new Part(id, key, off[0], off[1], off[2], scale, (float) rot[0], (float) rot[1], (float) rot[2], world, anims);
    }

    private static double num(Object o, double def) {
        return o instanceof Number n ? n.doubleValue() : def;
    }

    private static double[] vec(Object o, double def) {
        double[] v = {def, def, def};
        if (o instanceof List<?> l) for (int i = 0; i < 3 && i < l.size(); i++) v[i] = num(l.get(i), def);
        return v;
    }

    /** 이 보스(UUID 문자열)의 모델이 지금 붙어 있는지. */
    public boolean isLive(String bossUuid) {
        try {
            return live.containsKey(UUID.fromString(bossUuid));
        } catch (IllegalArgumentException e) {
            return false;
        }
    }

    public boolean has(String mobId) {
        return defs.containsKey(mobId);
    }

    // ------------------------------------------------------------------ 붙이기 / 떼기

    /** 보스에 모델을 붙인다. 이미 붙어 있으면 아무것도 하지 않는다. */
    public void attach(LivingEntity boss, String mobId) {
        Def def = defs.get(mobId);
        if (def == null || live.containsKey(boss.getUniqueId())) return;
        if (!plugin.getConfig().getBoolean("resource-pack.custom-models", true)) return;
        boss.setInvisible(true);
        Instance in = new Instance(boss, def);
        Location at = boss.getLocation();
        for (Part p : def.parts()) {
            ItemStack it = new ItemStack(Material.PAPER);
            ItemMeta meta = it.getItemMeta();
            meta.setItemModel(p.model());
            it.setItemMeta(meta);
            Location l = at.clone();
            l.setPitch(0);
            l.setYaw(p.world() ? 0 : boss.getBodyYaw());
            ItemDisplay d = at.getWorld().spawn(l, ItemDisplay.class, dd -> {
                dd.setPersistent(false);
                dd.setItemStack(it);
                dd.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.NONE);
                dd.setBillboard(Display.Billboard.FIXED);
                dd.setTeleportDuration(STEP);
                dd.setInterpolationDuration(STEP);
                dd.setViewRange(2.5f);
                dd.setShadowRadius(0);
                dd.getPersistentDataContainer().set(Keys.RIG, PersistentDataType.STRING, boss.getUniqueId().toString());
                dd.setTransformation(transform(in, p, 0));
            });
            in.displays.add(d);
        }
        live.put(boss.getUniqueId(), in);
    }

    public void detach(UUID boss) {
        Instance in = live.remove(boss);
        if (in != null) for (ItemDisplay d : in.displays) d.remove();
    }

    /** 죽을 때: 조각이 사방으로 흩어지며 사라진다. */
    public void shatter(UUID boss) {
        Instance in = live.remove(boss);
        if (in == null) return;
        var rnd = java.util.concurrent.ThreadLocalRandom.current();
        for (ItemDisplay d : in.displays) {
            if (!d.isValid()) continue;
            Transformation t = d.getTransformation();
            Vector3f to = new Vector3f(t.getTranslation()).add((float) rnd.nextDouble(-2.5, 2.5), (float) rnd.nextDouble(-1.5, 1.0), (float) rnd.nextDouble(-2.5, 2.5));
            Quaternionf spin = new Quaternionf(t.getRightRotation()).rotateXYZ((float) rnd.nextDouble(-2, 2), (float) rnd.nextDouble(-2, 2), (float) rnd.nextDouble(-2, 2));
            d.setInterpolationDuration(30);
            d.setInterpolationDelay(0);
            d.setTransformation(new Transformation(to, t.getLeftRotation(), new Vector3f(0.01f), spin));
            d.setGlowing(true);
            d.setGlowColorOverride(Color.WHITE);
        }
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            for (ItemDisplay d : in.displays) d.remove();
        }, 32);
    }

    /** 공격하거나 스킬을 쓸 때: 휘두르기 동작. */
    public void swing(UUID boss) {
        Instance in = live.get(boss);
        if (in != null && in.age - in.swingAt > 10) in.swingAt = in.age;
    }

    /** 맞았을 때 잠깐 붉게 번쩍인다. */
    public void hurt(UUID boss) {
        Instance in = live.get(boss);
        if (in == null) return;
        in.flashUntil = in.age + 4;
        for (ItemDisplay d : in.displays) {
            d.setGlowing(true);
            d.setGlowColorOverride(Color.fromRGB(0xff3030));
        }
    }

    public void removeAll() {
        for (Instance in : live.values()) for (ItemDisplay d : in.displays) d.remove();
        live.clear();
    }

    // ------------------------------------------------------------------ 움직임

    private void tick() {
        for (Instance in : new ArrayList<>(live.values())) {
            LivingEntity b = in.boss;
            if (!b.isValid() || b.isDead()) {
                if (!b.isDead()) detach(b.getUniqueId());
                else if (live.containsKey(b.getUniqueId())) shatter(b.getUniqueId());
                continue;
            }
            in.age += STEP;
            Location base = b.getLocation();
            float yaw = b.getBodyYaw();
            boolean unflash = in.flashUntil >= 0 && in.age >= in.flashUntil;
            if (unflash) in.flashUntil = -1;
            for (int i = 0; i < in.displays.size(); i++) {
                ItemDisplay d = in.displays.get(i);
                Part p = in.def.parts().get(i);
                if (!d.isValid()) continue;
                Location l = base.clone();
                l.setPitch(0);
                l.setYaw(p.world() ? 0 : yaw);
                d.teleport(l);
                d.setInterpolationDelay(0);
                d.setInterpolationDuration(STEP);
                d.setTransformation(transform(in, p, in.age));
                if (unflash) d.setGlowing(false);
            }
        }
    }

    private static Transformation transform(Instance in, Part p, int t) {
        double x = p.ox(), y = p.oy(), z = p.oz();
        Quaternionf anim = new Quaternionf();
        for (Anim a : p.anims()) {
            switch (a.type()) {
                case "bob" -> y += a.amplitude() * Math.sin(2 * Math.PI * (t / a.period() + a.phase()));
                case "sway" -> rotate(anim, a.axis(), a.angle() * Math.sin(2 * Math.PI * (t / a.period() + a.phase())));
                case "spin" -> rotate(anim, a.axis(), a.speed() * t);
                case "orbit" -> {
                    double th = Math.toRadians(a.phase() + a.speed() * t);
                    x = a.radius() * Math.cos(th);
                    z = a.radius() * Math.sin(th);
                    y = p.oy() + a.height();
                }
                case "swing" -> {
                    int s = t - in.swingAt;
                    if (s >= 0 && s < a.ticks()) rotate(anim, a.axis(), a.angle() * Math.sin(Math.PI * s / a.ticks()));
                }
                default -> { }
            }
        }
        Quaternionf base = new Quaternionf()
                .rotateY((float) Math.toRadians(p.yaw()))
                .rotateX((float) Math.toRadians(p.pitch()))
                .rotateZ((float) Math.toRadians(p.roll()));
        Quaternionf right = anim.mul(base).mul(FLIP);
        return new Transformation(new Vector3f((float) x, (float) y, (float) z), new Quaternionf(),
                new Vector3f(p.scale()), right);
    }

    private static void rotate(Quaternionf q, char axis, double deg) {
        float r = (float) Math.toRadians(deg);
        switch (axis) {
            case 'x' -> q.rotateX(r);
            case 'z' -> q.rotateZ(r);
            default -> q.rotateY(r);
        }
    }
}
