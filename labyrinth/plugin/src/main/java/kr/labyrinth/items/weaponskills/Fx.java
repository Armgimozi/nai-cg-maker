package kr.labyrinth.items.weaponskills;

import io.papermc.paper.datacomponent.DataComponentTypes;
import java.util.Collection;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.FxModelDef;
import kr.labyrinth.core.Keys;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.entity.Display;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Transformation;
import org.joml.AxisAngle4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 이펙트 모델(ItemDisplay, labyrinth:fx/&lt;name&gt;) 공용 헬퍼 — 아우라·무기 스킬이 쓴다 (ARCHITECTURE §2 표시 규칙:
 * ItemDisplay + FIXED, fx.yml 의 billboard·glow 반영). 모든 디스플레이는 임시 엔티티로 태그(Keys.FX)·비영속.
 */
public final class Fx {

    private Fx() {}

    public static ItemStack modelItem(String fxName) {
        ItemStack s = ItemStack.of(Material.PAPER);
        s.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "fx/" + fxName));
        return s;
    }

    /** fx.yml 에 있는 모델인가. */
    public static boolean exists(Services s, String fxName) {
        return fxName != null && s.content().fxModels().containsKey(fxName);
    }

    /**
     * 이펙트 디스플레이 생성. 모델이 fx.yml 에 없으면 null (호출자는 입자로 대체).
     * @param scale    표시 배율 (1 = 모델 원래 크기)
     * @param lifetime 틱 (0 이하 = 호출자가 직접 제거)
     */
    public static ItemDisplay spawn(Services s, Location at, String fxName, float scale, int lifetime) {
        if (!exists(s, fxName) || at.getWorld() == null) return null;
        FxModelDef def = s.content().fxModels().get(fxName);
        ItemDisplay d = at.getWorld().spawn(at, ItemDisplay.class, e -> {
            e.setPersistent(false);
            Keys.tagTransient(e, Keys.FX, "fx:" + fxName);
            e.setItemStack(modelItem(fxName));
            e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
            e.setBillboard(billboard(def.billboard()));
            if (def.glow()) e.setBrightness(new Display.Brightness(15, 15));
            e.setTeleportDuration(1);
            e.setInterpolationDuration(1);
            e.setViewRange(1.0f);
            e.setShadowRadius(0);
            e.setTransformation(new Transformation(new Vector3f(), new Quaternionf(), new Vector3f(scale, scale, scale),
                    new Quaternionf()));
        });
        if (lifetime > 0) Bukkit.getScheduler().runTaskLater(s.plugin(), () -> { if (d.isValid()) d.remove(); }, lifetime);
        return d;
    }

    /** 특정 플레이어들에게만 보이는 디스플레이 (아군 전용 경고 장판 등). */
    public static ItemDisplay spawnFor(Services s, Location at, String fxName, float scale, int lifetime, Collection<Player> viewers) {
        if (!exists(s, fxName) || at.getWorld() == null) return null;
        ItemDisplay d = spawn(s, at, fxName, scale, lifetime);
        if (d == null) return null;
        d.setVisibleByDefault(false);
        for (Player p : viewers) p.showEntity(s.plugin(), d);
        return d;
    }

    static Display.Billboard billboard(String b) {
        if (b == null) return Display.Billboard.FIXED;
        return switch (b.toUpperCase(java.util.Locale.ROOT)) {
            case "CENTER" -> Display.Billboard.CENTER;
            case "VERTICAL" -> Display.Billboard.VERTICAL;
            case "HORIZONTAL" -> Display.Billboard.HORIZONTAL;
            default -> Display.Billboard.FIXED;
        };
    }

    /** 크기 [w,h,d] px 의 가장 긴 변(블록). 없으면 1. */
    public static double modelLength(Services s, String fxName, int axis) {
        FxModelDef def = s.content().fxModels().get(fxName);
        if (def == null || def.size() == null || def.size().size() < 3) return 1.0;
        return Math.max(0.1, def.size().get(axis) / 16.0);
    }

    /** Y 축 회전 + 배율(x,y,z) 변환. */
    public static void transform(ItemDisplay d, float yawRad, float sx, float sy, float sz, int interp) {
        if (d == null || !d.isValid()) return;
        d.setInterpolationDelay(0);
        d.setInterpolationDuration(interp);
        d.setTransformation(new Transformation(new Vector3f(), new Quaternionf(new AxisAngle4f(yawRad, 0, 1, 0)),
                new Vector3f(sx, sy, sz), new Quaternionf()));
    }

    /** fx 모델 대표 색 (팔레트 가운데) — 입자 색에 사용. 없으면 흰색. */
    public static Color color(Services s, String fxName) {
        FxModelDef def = fxName == null ? null : s.content().fxModels().get(fxName);
        List<String> pal = def == null ? null : def.palette();
        if (pal == null || pal.isEmpty()) return Color.fromRGB(0xE8EEF8);
        return parseColor(pal.get(Math.min(pal.size() - 1, pal.size() / 2 + (pal.size() > 2 ? 1 : 0))), Color.WHITE);
    }

    public static Color parseColor(String hex, Color def) {
        if (hex == null) return def;
        try {
            String h = hex.startsWith("#") ? hex.substring(1) : hex;
            return Color.fromRGB(Integer.parseInt(h, 16) & 0xFFFFFF);
        } catch (NumberFormatException e) {
            return def;
        }
    }

    /** 색 입자 (DUST). */
    public static void dust(Location at, Color c, float size, int count, double spread) {
        if (at.getWorld() == null) return;
        at.getWorld().spawnParticle(Particle.DUST, at, count, spread, spread, spread, 0, new Particle.DustOptions(c, size), false);
    }

    /** from → to 직선 위에 step 간격으로 색 입자. */
    public static void line(Location from, Location to, Color c, float size, double step) {
        if (from.getWorld() == null) return;
        org.bukkit.util.Vector d = to.toVector().subtract(from.toVector());
        double len = d.length();
        if (len < 1e-6) return;
        d.normalize();
        Particle.DustOptions opt = new Particle.DustOptions(c, size);
        for (double t = 0; t <= len; t += step) {
            Location p = from.clone().add(d.clone().multiply(t));
            from.getWorld().spawnParticle(Particle.DUST, p, 1, 0.02, 0.02, 0.02, 0, opt, false);
        }
    }
}
