package kr.labyrinth.bosses;

import io.papermc.paper.entity.TeleportFlag;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import kr.labyrinth.content.ModelDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.mobs.ModelRig;
import kr.labyrinth.mobs.RigMath;
import net.kyori.adventure.text.Component;
import org.bukkit.Color;
import org.bukkit.Location;
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
 * 보스 3D 모델 리그. 파트·좌표 계약은 {@link ModelRig} 과 같다(ARCHITECTURE §2: 파트마다 ItemDisplay,
 * {@code labyrinth:mob/<id>/<part>}, FIXED, 피벗 = 모델 (8,8,8), Transformation 으로 위치·회전) — 여기에
 * 보스 전용 <b>시전 애니메이션 오버레이</b>({@link BossAnim}: 내려찍기·휩쓸기·돌진·포효·던지기·기절·사망…)를 얹는다.
 * 파트는 보이지 않는 앵커에 탑승 → 이동은 앵커 텔레포트 하나.
 */
public final class BossRig {

    private final String bossId;
    private final ModelDef model;
    private final float scale;
    private final float yawOffset;
    private ItemDisplay anchor;
    private final List<PartView> parts = new ArrayList<>();
    private TextDisplay nameplate;
    private Location lastAnchor;
    private boolean hidden;

    private BossAnim anim = BossAnim.NONE;
    private long animStart;
    private int animTicks = 1;
    private double animWindup = 0.7;
    private final BossAnim.Pose scratch = new BossAnim.Pose();

    private record PartView(ModelDef.Part def, ItemDisplay display, ItemStack item) {}

    public BossRig(String bossId, ModelDef model, double scale, double yawOffsetDeg) {
        this.bossId = bossId;
        this.model = model == null ? ModelDef.EMPTY : model;
        this.scale = (float) scale;
        this.yawOffset = (float) yawOffsetDeg;
    }

    public void spawn(Location loc, String tag) {
        World w = loc.getWorld();
        Location at = loc.clone();
        at.setYaw(0);
        at.setPitch(0);
        anchor = w.spawn(at, ItemDisplay.class, d -> {
            d.setPersistent(false);
            d.setTeleportDuration(2);
            Keys.tagTransient(d, Keys.BOSS, tag);
        });
        float top = 1f;
        for (ModelDef.Part p : model.parts()) {
            ItemStack item = ModelRig.modelItem(ModelRig.partModel(bossId, p.name()));
            boolean glow = p.name().contains("eye") || p.name().contains("core") || p.name().contains("crown")
                    || p.name().contains("furnace") || p.name().contains("lantern") || "crystal_cluster".equals(p.form());
            ItemDisplay d = w.spawn(at, ItemDisplay.class, e -> {
                e.setPersistent(false);
                e.setItemStack(item);
                e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
                e.setInterpolationDelay(0);
                e.setInterpolationDuration(2);
                e.setViewRange(1.2f);
                e.setShadowRadius(0f);
                e.setBrightness(new Display.Brightness(glow ? 15 : 11, 15));
                Keys.tagTransient(e, Keys.BOSS, tag);
            });
            anchor.addPassenger(d);
            parts.add(new PartView(p, d, item));
            top = Math.max(top, (float) ((p.pivotY() + p.sizeY() / 32.0) * scale));
        }
        final float plateY = top + 0.6f;
        nameplate = w.spawn(at, TextDisplay.class, t -> {
            t.setPersistent(false);
            t.setBillboard(Display.Billboard.VERTICAL);
            t.setShadowed(true);
            t.setDefaultBackground(false);
            t.setBackgroundColor(Color.fromARGB(80, 0, 0, 0));
            t.setLineWidth(260);
            t.setViewRange(0.8f);
            t.setAlignment(TextDisplay.TextAlignment.CENTER);
            t.setBrightness(new Display.Brightness(15, 15));
            t.setTransformation(new Transformation(new Vector3f(0, plateY, 0), new Quaternionf(), new Vector3f(1.1f, 1.1f, 1.1f),
                    new Quaternionf()));
            Keys.tagTransient(t, Keys.BOSS, tag);
        });
        anchor.addPassenger(nameplate);
        lastAnchor = at;
    }

    /** 시전 애니메이션 시작 (같은 애니메이션이 진행 중이면 다시 처음부터). */
    public void play(BossAnim a, int ticks, long now) {
        play(a, ticks, a.defaultWindup(), now);
    }

    public void play(BossAnim a, int ticks, double windupRatio, long now) {
        anim = a == null ? BossAnim.NONE : a;
        animStart = now;
        animTicks = Math.max(1, ticks);
        animWindup = Math.max(0.05, Math.min(0.95, windupRatio));
    }

    public void stop() { anim = BossAnim.NONE; }

    public BossAnim current(long now) {
        if (anim != BossAnim.NONE && now - animStart > animTicks && anim != BossAnim.STUN && anim != BossAnim.DEATH) anim = BossAnim.NONE;
        return anim;
    }

    public void follow(Location loc) {
        if (anchor == null || !anchor.isValid()) return;
        if (lastAnchor != null && lastAnchor.getWorld() == loc.getWorld() && lastAnchor.distanceSquared(loc) < 0.0004) return;
        Location at = loc.clone();
        at.setYaw(0);
        at.setPitch(0);
        boolean far = lastAnchor != null && lastAnchor.getWorld() == loc.getWorld() && lastAnchor.distanceSquared(loc) > 64;
        anchor.setTeleportDuration(far ? 0 : 2);
        anchor.teleport(at, TeleportFlag.EntityState.RETAIN_PASSENGERS);
        lastAnchor = at;
    }

    /** 한 프레임 적용. state 는 RigMath 기본 anim 입력, interp = 다음 갱신까지 틱. */
    public void animate(float yawDeg, RigMath.AnimState state, int interp) {
        BossAnim a = current(state.tick());
        double p = a == BossAnim.STUN ? 0.5 : Math.min(1.0, (state.tick() - animStart) / (double) animTicks);
        Quaternionf yaw = new Quaternionf().rotationY((float) Math.toRadians(-yawDeg));
        for (PartView pv : parts) {
            ItemDisplay d = pv.display();
            if (!d.isValid()) continue;
            ModelDef.Part part = pv.def();
            RigMath.Pose base = RigMath.pose(part.anim(), part.form(), state);
            BossAnim.Pose ov = BossAnim.overlay(a, part.anim(), part.name(), p, animWindup, state.tick(), scratch);
            float bw = ov.baseWeight;
            Quaternionf baseRot = new Quaternionf().slerp(base.rotation(), bw);
            Vector3f local = new Vector3f((float) part.pivotX(), (float) part.pivotY(), (float) part.pivotZ())
                    .add(new Vector3f(base.offset()).mul(bw)).add(ov.offset);
            ov.globalRotation.transform(local);
            local.add(ov.globalOffset).mul(scale);
            Vector3f tr = yaw.transform(local, new Vector3f());
            Quaternionf left = new Quaternionf(yaw).mul(ov.globalRotation).mul(ov.rotation).mul(baseRot);
            if (yawOffset != 0) left.rotateY((float) Math.toRadians(yawOffset));
            float s = scale * base.scale() * ov.scale;
            Transformation next = new Transformation(tr, left, new Vector3f(s, s, s), new Quaternionf());
            if (next.equals(d.getTransformation())) continue;
            d.setInterpolationDelay(0);
            d.setInterpolationDuration(Math.max(1, interp));
            d.setTransformation(next);
        }
    }

    public void nameplate(Component text) {
        if (nameplate != null && nameplate.isValid()) nameplate.text(hidden ? Component.empty() : text);
    }

    public void setHidden(boolean hide) {
        if (hide == hidden) return;
        hidden = hide;
        for (PartView pv : parts) if (pv.display().isValid()) pv.display().setItemStack(hide ? ItemStack.empty() : pv.item());
        if (nameplate != null && nameplate.isValid()) {
            if (hide) nameplate.text(Component.empty());
            nameplate.setBackgroundColor(hide ? Color.fromARGB(0, 0, 0, 0) : Color.fromARGB(80, 0, 0, 0));
        }
    }

    public boolean hidden() { return hidden; }

    /** 발광 윤곽 (기절·광폭화 표시). null = 끄기. */
    public void setGlow(Color color) {
        for (PartView pv : parts) {
            ItemDisplay d = pv.display();
            if (!d.isValid()) continue;
            d.setGlowing(color != null);
            d.setGlowColorOverride(color);
        }
    }

    public List<UUID> entityIds() {
        List<UUID> out = new ArrayList<>();
        if (anchor != null) out.add(anchor.getUniqueId());
        for (PartView pv : parts) out.add(pv.display().getUniqueId());
        if (nameplate != null) out.add(nameplate.getUniqueId());
        return out;
    }

    public boolean broken() { return anchor == null || !anchor.isValid(); }

    public Entity anchor() { return anchor; }

    public void remove() {
        for (PartView pv : parts) pv.display().remove();
        parts.clear();
        if (nameplate != null) nameplate.remove();
        if (anchor != null) anchor.remove();
        nameplate = null;
        anchor = null;
    }
}
