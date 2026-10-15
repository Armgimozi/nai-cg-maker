package kr.labyrinth.mobs;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.entity.TeleportFlag;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.content.ModelDef;
import kr.labyrinth.core.Keys;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.TextDisplay;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Transformation;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 몹 3D 모델 리그 (ARCHITECTURE §2 · GDD §14.6): 파트마다 {@code ItemDisplay}(아이템 모델 {@code labyrinth:mob/<id>/<part>},
 * {@code ItemDisplayTransform.FIXED}) + 이름/HP 표시 {@code TextDisplay}.
 * <p>
 * 모든 파트는 보이지 않는 앵커 디스플레이(아이템 없음)에 탑승한다 → 몹이 움직일 때 앵커 하나만 텔레포트하면 파트가 한 덩어리로
 * 따라온다(패킷 절약). 파트의 피벗 위치·몹 yaw·애니메이션 회전은 전부 Display Transformation(보간)으로 표현한다:
 * translation = R(yaw)·(모델 원점 위치)·scale, left rotation = R(yaw)·애니메이션 회전. 원점 위치는 {@link RigMath.Skeleton} 이
 * 관절(joint) 기준 회전·다리 걸음·목·머리·턱·꼬리 사슬·몸 전체 변환을 이어 붙여 준다(회전 중심 = 관절).
 * 걸음 위상은 {@link RigMath.Gait} 가 갱신마다 이동 거리만큼 진행한다.
 */
public final class ModelRig {

    /** 밝기 15 로 고정할 파트 (GDD §14.3: emissive_core / glowing_eyes 류). */
    private static final Set<String> EMISSIVE_FORMS = Set.of("eye", "lantern", "crystal_cluster");
    private static final Set<String> EMISSIVE_FEATURES = Set.of("emissive_core", "glowing_eyes", "ember_glow", "spore_glow",
            "heartbeat_glow", "electric_veins", "molten_cracks", "firefly_specks");

    private final String mobId;
    private final ModelDef model;
    private final float scale;
    private final float yawOffset;
    private ItemDisplay anchor;
    private final List<PartView> parts = new ArrayList<>();
    private final RigMath.Skeleton skeleton;
    private final RigMath.Gait gait = new RigMath.Gait();
    private TextDisplay nameplate;
    private float nameplateHeight;
    private boolean hidden;
    private boolean plateVisible = true;
    private Component plateText;
    private Location lastAnchor;

    private record PartView(ModelDef.Part def, ItemDisplay display, ItemStack item) {}

    public ModelRig(String mobId, ModelDef model, double scale, double yawOffsetDeg) {
        this.mobId = mobId;
        this.model = model == null ? ModelDef.EMPTY : model;
        this.skeleton = new RigMath.Skeleton(this.model.parts(), scale);
        this.scale = (float) scale;
        this.yawOffset = (float) yawOffsetDeg;
    }

    /** 아이템 모델 키 labyrinth:mob/&lt;id&gt;/&lt;part&gt;. */
    public static Key partModel(String mobId, String part) {
        return Key.key(Keys.NS, "mob/" + mobId + "/" + part.toLowerCase(Locale.ROOT));
    }

    public static ItemStack modelItem(Key model) {
        ItemStack s = ItemStack.of(Material.PAPER);
        s.setData(DataComponentTypes.ITEM_MODEL, model);
        return s;
    }

    /** 리그 생성. nameplateBase = 히트박스 높이(블록) — 이름표는 모델/히트박스 중 높은 쪽 위에. */
    public void spawn(Location loc, double hitboxHeight, String ownerTag) {
        World w = loc.getWorld();
        Location at = loc.clone();
        at.setYaw(0);
        at.setPitch(0);
        anchor = w.spawn(at, ItemDisplay.class, d -> {
            d.setPersistent(false);
            d.setTeleportDuration(2);
            Keys.tagTransient(d, Keys.FX, ownerTag);
        });
        boolean emissiveStyle = false;
        for (String f : model.style().strings("features")) if (EMISSIVE_FEATURES.contains(f)) emissiveStyle = true;
        float top = (float) hitboxHeight;
        for (ModelDef.Part p : model.parts()) {
            ItemStack item = modelItem(partModel(mobId, p.name()));
            boolean emissive = emissiveStyle && (EMISSIVE_FORMS.contains(p.form())
                    || p.name().contains("eye") || p.name().contains("core") || p.name().contains("lantern")
                    || p.name().contains("orb") || p.name().contains("flame") || p.name().contains("crystal"));
            ItemDisplay d = w.spawn(at, ItemDisplay.class, e -> {
                e.setPersistent(false);
                e.setItemStack(item);
                e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
                e.setInterpolationDelay(0);
                e.setInterpolationDuration(2);
                e.setViewRange(0.75f);
                e.setShadowRadius(0f);
                if (emissive) e.setBrightness(new Display.Brightness(15, 15));
                Keys.tagTransient(e, Keys.FX, ownerTag);
            });
            anchor.addPassenger(d);
            parts.add(new PartView(p, d, item));
            top = Math.max(top, (float) ((p.pivotY() + p.sizeY() / 32.0) * scale));
        }
        nameplateHeight = top + 0.45f;
        nameplate = w.spawn(at, TextDisplay.class, t -> {
            t.setPersistent(false);
            t.setBillboard(Display.Billboard.VERTICAL); // 위쪽 = 월드 위 (CENTER 는 시점 피치에 따라 이름표가 밀림)
            t.setShadowed(true);
            t.setSeeThrough(false);
            t.setDefaultBackground(false);
            t.setBackgroundColor(Color.fromARGB(70, 0, 0, 0));
            t.setLineWidth(220);
            t.setViewRange(0.45f);
            t.setAlignment(TextDisplay.TextAlignment.CENTER);
            t.setBrightness(new Display.Brightness(15, 15));
            t.setTransformation(new Transformation(new Vector3f(0, nameplateHeight, 0), new Quaternionf(),
                    new Vector3f(0.85f, 0.85f, 0.85f), new Quaternionf()));
            Keys.tagTransient(t, Keys.FX, ownerTag);
        });
        anchor.addPassenger(nameplate);
        lastAnchor = at;
    }

    /** 앵커를 몹 위치로 (움직였을 때만 텔레포트 — 탑승한 파트는 클라이언트에서 함께 따라온다). */
    public void follow(Location loc) {
        if (anchor == null || !anchor.isValid()) return;
        if (lastAnchor != null && lastAnchor.getWorld() == loc.getWorld() && lastAnchor.distanceSquared(loc) < 0.0004) return;
        Location at = loc.clone();
        at.setYaw(0);
        at.setPitch(0);
        if (lastAnchor != null && lastAnchor.getWorld() == loc.getWorld() && lastAnchor.distanceSquared(loc) > 64) {
            anchor.setTeleportDuration(0);
        } else {
            anchor.setTeleportDuration(2);
        }
        anchor.teleport(at, TeleportFlag.EntityState.RETAIN_PASSENGERS);
        lastAnchor = at;
    }

    /** 애니메이션 한 번 적용. interpolationTicks = 다음 갱신까지 간격(보간 시간). */
    public void animate(float yawDeg, RigMath.AnimState state, int interpolationTicks) {
        Vector3f tr = new Vector3f();
        Quaternionf left = new Quaternionf();
        gait.advance(skeleton, state, interpolationTicks);
        RigMath.Solved[] solved = skeleton.solve(state, gait);
        for (int i = 0; i < parts.size() && i < solved.length; i++) {
            PartView pv = parts.get(i);
            ItemDisplay d = pv.display();
            if (!d.isValid()) continue;
            RigMath.Solved sp = solved[i];
            RigMath.Pose pose = new RigMath.Pose(sp.offset(), sp.rotation(), sp.scale());
            float s = RigMath.compose(yawDeg, scale, sp.pivot().x, sp.pivot().y, sp.pivot().z, pose,
                    yawOffset, tr, left);
            Transformation next = new Transformation(new Vector3f(tr), new Quaternionf(left), new Vector3f(s, s, s), new Quaternionf());
            if (next.equals(d.getTransformation())) continue;
            d.setInterpolationDelay(0);
            d.setInterpolationDuration(Math.max(1, interpolationTicks));
            d.setTransformation(next);
        }
    }

    public void nameplate(Component text) {
        plateText = text;
        if (nameplate != null && nameplate.isValid() && plateVisible) nameplate.text(text);
    }

    public void nameplateVisible(boolean visible) {
        plateVisible = visible;
        if (nameplate == null || !nameplate.isValid()) return;
        nameplate.text(visible && plateText != null ? plateText : Component.empty());
        nameplate.setBackgroundColor(visible ? Color.fromARGB(70, 0, 0, 0) : Color.fromARGB(0, 0, 0, 0));
    }

    /** 은신·위장: 파트를 숨기거나 되돌린다. */
    public void setHidden(boolean hide) {
        if (hide == hidden) return;
        hidden = hide;
        for (PartView pv : parts) {
            if (pv.display().isValid()) pv.display().setItemStack(hide ? ItemStack.empty() : pv.item());
        }
        nameplateVisible(!hide);
    }

    public boolean hidden() { return hidden; }

    /** 정예 발광 (null = 끄기). */
    public void setGlow(Color color) {
        for (PartView pv : parts) {
            ItemDisplay d = pv.display();
            if (!d.isValid()) continue;
            d.setGlowing(color != null);
            d.setGlowColorOverride(color);
        }
    }

    /** 리그 소속 엔티티 UUID (byEntity 조회용). */
    public List<UUID> entityIds() {
        List<UUID> out = new ArrayList<>();
        if (anchor != null) out.add(anchor.getUniqueId());
        for (PartView pv : parts) out.add(pv.display().getUniqueId());
        if (nameplate != null) out.add(nameplate.getUniqueId());
        return out;
    }

    public float nameplateHeight() { return nameplateHeight; }

    public boolean isEmpty() { return parts.isEmpty(); }

    public void remove() {
        for (PartView pv : parts) pv.display().remove();
        parts.clear();
        if (nameplate != null) nameplate.remove();
        if (anchor != null) anchor.remove();
        nameplate = null;
        anchor = null;
    }

    /** 리그가 깨졌는가 (청크 언로드 등으로 앵커가 사라짐). */
    public boolean broken() {
        return anchor == null || !anchor.isValid();
    }

    /** 앵커 엔티티 (이펙트 부착용). */
    public Entity anchor() { return anchor; }
}
