package kr.souls.combat;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.CustomModelData;
import io.papermc.paper.datacomponent.item.ResolvableProfile;
import kr.souls.Config;
import kr.souls.Keys;
import kr.souls.Souls;
import kr.souls.skill.Mechanics;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 구르기 대역 (3.3 "보이는 모습", combat.roll.visual: tumble). 바닐라에는 앞구르기 몸짓이 없고, 서버는 플레이어 모형을 마음대로
 * 돌릴 수 없다. 그래서 구르는 동안 진짜 몸을 감추고 그 자리에 웅크린 대역을 띄워 구르는 쪽으로 한 바퀴 돌린다.
 *
 * <ul>
 *   <li>대역: ItemDisplay 둘. 머리는 그 사람 프로필의 player_head (팩 souls:roll_head 가 공의 앞 위에 숙여 둔다), 몸은 팩의
 *       복셀 모형 souls:roll_body. 둘 다 그 사람의 <b>탑승물</b>로 태운다: 클라이언트가 탈것(자기 몸)의 위치에 틱마다 붙이므로
 *       자기 화면에서도 미리 움직인 몸과 어긋나지 않는다 (순간이동으로 따라가게 하면 서버를 거쳐 1~2틱, 0.4~0.8칸 뒤처진다).
 *       탑승 자리는 몸 상자 꼭대기 (서 있으면 1.8) 라 변환의 이동으로 pivot 높이까지 내린다.</li>
 *   <li>회전: 두 대역에 같은 변환 (이동 + 왼쪽 회전 = 구르는 쪽 Y 회전 · 옆 축 X 회전 θ). steps 마디마다 θ 를 다음 각으로 바꾸고
 *       보간 틱을 준다. 클라이언트는 회전을 가까운 쪽으로 구면 보간하므로 한 마디가 180° 보다 작으면 앞으로만 돈다.
 *       머리를 공 앞으로 옮기는 것은 팩의 아이템 자세 (fixed) 가 한다: 변환의 이동은 직선 보간이라 이동으로 옮기면 마디 사이에서
 *       회전 중심 쪽으로 꺾인다.</li>
 *   <li>진짜 몸 감추기: 투명 효과 (입자·아이콘 없이). 투명해도 바닐라는 든 것과 입은 것을 그리므로, 그 사람 화면과 보는 사람에게만
 *       장비를 바꿔 보낸다 (sendEquipmentChange, 서버의 진짜 아이템은 그대로). 손: souls 아이템이면 custom_model_data 깃발
 *       {@link #HIDE_FLAG} 를 켠 사본 (팩이 3인칭 손·머리 자세에서 비운다. 단축 슬롯 그림과 이름은 그대로라 바닐라가 이름을
 *       다시 띄우지 않는다), 아니면 공기. 갑옷 칸: 공기.</li>
 *   <li>거두기: reveal 틱, 다음 구르기가 뒷걸음일 때, 죽음, 나가기, 순간이동, 세계 이동, 플러그인 끄기. 투명은 구르기가 건 것만 걷고
 *       (원래 투명 효과가 있었으면 건드리지 않는다), 장비는 진짜를 다시 보내고 인벤토리를 다시 맞춘다. 대역은 저장하지 않고
 *       (persistent false) souls_fx 표가 있어 켤 때 쓸어 낸다. 효과도 reveal 뒤 몇 틱이면 저절로 끝난다 (플러그인이 멈춰도).</li>
 * </ul>
 * 움직임·무적·비용은 Roll 이 그대로 한다. 이 클래스는 보이는 것만 바꾼다 (봇 시험이 같은 판정을 본다).
 */
@SuppressWarnings("UnstableApiUsage")
public final class Tumble {
    /** 팩의 아이템 정의가 3인칭 손·머리에서 비우는 custom_model_data 깃발 번호 (pack/roll_figure.py HIDE_FLAG) */
    public static final int HIDE_FLAG = 0;
    private static final Key BODY = Key.key(Keys.NS, "roll_body");
    private static final Key HEAD = Key.key(Keys.NS, "roll_head");
    private static final EquipmentSlot[] SLOTS = {EquipmentSlot.HAND, EquipmentSlot.OFF_HAND, EquipmentSlot.HEAD,
            EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET};
    /** 투명 효과의 여유 틱 (reveal 뒤 이만큼 지나면 플러그인이 거두지 못해도 저절로 끝난다) */
    private static final int SAFETY = 10;

    private final Souls plugin;
    private final Map<UUID, Fig> live = new HashMap<>();

    /** 한 사람의 대역. */
    private static final class Fig {
        final List<ItemDisplay> parts = new ArrayList<>();
        long start;
        float yaw;
        int next;
        float angle;
        /** 지금 변환이 맞춘 탑승 높이 (몸 상자 높이: 서기 1.8, 웅크리기 1.5) */
        double attach;
        /** 구르기가 투명 효과를 걸었는가 (원래 있던 효과면 거두지 않는다) */
        boolean ownInvis;
        /** 바꿔 보낸 장비 칸 */
        final List<EquipmentSlot> faked = new ArrayList<>();
    }

    public Tumble(Souls plugin) {
        this.plugin = plugin;
    }

    private Config.TumbleCfg cfg() {
        return plugin.cfg().roll.tumble();
    }

    public boolean active(Player p) {
        return live.containsKey(p.getUniqueId());
    }

    /** 구르기 시작 (틱 0). dir 은 구르는 쪽 (수평, 길이 1). 이어 구르면 대역을 그대로 쓰고 회전만 처음부터. */
    public void start(Player p, Vector dir, long now) {
        Fig f = live.get(p.getUniqueId());
        if (f != null && !intact(p, f)) {
            stop(p);
            f = null;
        }
        if (f == null) {
            f = new Fig();
            f.attach = p.getHeight();
            spawn(p, f);
            hide(p, f);
            live.put(p.getUniqueId(), f);
        } else {
            // 이어 구르기: 효과를 다시 늘린다 (장비는 아직 바꿔 보낸 그대로)
            if (f.ownInvis) invisible(p);
        }
        f.start = now;
        f.next = 0;
        f.yaw = (float) Math.atan2(dir.getX(), dir.getZ());
        f.angle = 0f;
        apply(f, 0);
    }

    /** Ticker 에서 Roll 이 부른다: 마디마다 회전, 몸 높이(자세)가 바뀌면 이동을 맞추고, reveal 틱에 거둔다. */
    public void tick(long now) {
        if (live.isEmpty()) return;
        Config.TumbleCfg c = cfg();
        for (UUID id : List.copyOf(live.keySet())) {
            Player p = Bukkit.getPlayer(id);
            Fig f = live.get(id);
            if (p == null || f == null) {
                drop(id);
                continue;
            }
            if (p.isDead() || !intact(p, f)) {
                stop(p);
                continue;
            }
            long t = now - f.start;
            if (t >= c.reveal()) {
                stop(p);
                continue;
            }
            boolean moved = false;
            while (f.next < c.steps().size() && c.steps().get(f.next).tick() <= t) {
                Config.TumbleStep s = c.steps().get(f.next++);
                f.angle = s.angle();
                apply(f, s.duration());
                moved = true;
            }
            double h = p.getHeight();
            if (!moved && Math.abs(h - f.attach) > 1e-3) {
                f.attach = h;
                apply(f, 1);
            } else {
                f.attach = h;
            }
        }
    }

    /** 대역을 거두고 진짜 몸과 장비를 되돌린다. 없으면 아무것도 하지 않는다. */
    public void stop(Player p) {
        Fig f = live.remove(p.getUniqueId());
        if (f == null) return;
        for (ItemDisplay d : f.parts) {
            if (d.isValid()) {
                d.leaveVehicle();
                d.remove();
            }
        }
        if (f.ownInvis) {
            PotionEffect e = p.getPotionEffect(PotionEffectType.INVISIBILITY);
            // 구르는 사이에 다른 투명 효과를 받았으면 (입자나 아이콘이 있는 것) 남겨 둔다
            if (e != null && !e.hasParticles() && !e.hasIcon() && !e.isAmbient()) p.removePotionEffect(PotionEffectType.INVISIBILITY);
        }
        if (!f.faked.isEmpty() && p.isOnline()) {
            EntityEquipment eq = p.getEquipment();
            Map<EquipmentSlot, ItemStack> real = new EnumMap<>(EquipmentSlot.class);
            for (EquipmentSlot s : f.faked) real.put(s, eq.getItem(s));
            p.sendEquipmentChange(p, real);
            for (Player v : p.getTrackedBy()) v.sendEquipmentChange(p, real);
            // 열린 창이 인벤토리면 갑옷·왼손 칸까지 다시 맞는다 (다른 창이 열려 있어도 위의 장비 패킷이 칸을 되돌린다)
            p.updateInventory();
        }
    }

    /** 나간 사람: 대역만 지운다 (효과는 Roll 이 나가기 전에 stop 으로 걷는다). */
    private void drop(UUID id) {
        Fig f = live.remove(id);
        if (f == null) return;
        for (ItemDisplay d : f.parts) if (d.isValid()) d.remove();
    }

    /** 플러그인을 끌 때: 모두 거둔다. */
    public void shutdown() {
        for (UUID id : List.copyOf(live.keySet())) {
            Player p = Bukkit.getPlayer(id);
            if (p != null) stop(p);
            else drop(id);
        }
        live.clear();
    }

    /**
     * 시험 (/soulstest tumble): 서 있는 대역을 at 에 세운다 (탑승하지 않는다). dir 쪽으로 angle 도 돈 자세. ticks 뒤에 지운다.
     * 실제 클라이언트에서 미리보기 (pack/preview/roll_figure.png) 와 같은 각을 견주어 본다.
     */
    public void pose(Player p, Location at, Vector dir, float angle, int ticks) {
        Location l = at.clone();
        l.setYaw(0f);
        l.setPitch(0f);
        List<ItemDisplay> ds = List.of(display(p, l, body()), display(p, l, head(p)));
        Quaternionf q = new Quaternionf().rotationY((float) Math.atan2(dir.getX(), dir.getZ())).rotateX((float) Math.toRadians(angle));
        Transformation tf = new Transformation(new Vector3f(0f, (float) cfg().pivot(), 0f), q, new Vector3f(cfg().scale()), new Quaternionf());
        for (ItemDisplay d : ds) d.setTransformation(tf);
        Bukkit.getScheduler().runTaskLater(plugin, () -> ds.forEach(Entity::remove), ticks);
    }

    // ───────────────────────── 대역 ─────────────────────────

    private void spawn(Player p, Fig f) {
        // 탑승 자리 (몸 상자 꼭대기) 에 띄운다: 첫 그림부터 탑승한 자리와 같아 한 장면 동안 바닥에 묻혀 보이지 않는다
        Location at = p.getLocation().add(0, f.attach, 0);
        at.setYaw(0f);
        at.setPitch(0f);
        f.parts.add(display(p, at, body()));
        f.parts.add(display(p, at, head(p)));
        for (ItemDisplay d : f.parts) p.addPassenger(d);
    }

    private ItemDisplay display(Player p, Location at, ItemStack item) {
        return p.getWorld().spawn(at, ItemDisplay.class, d -> {
            d.setItemStack(item);
            d.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
            d.setBillboard(Display.Billboard.FIXED);
            d.setPersistent(false);
            d.addScoreboardTag(Mechanics.FX_TAG);
            d.setTeleportDuration(0);
            d.setInterpolationDuration(0);
            d.setShadowRadius(0f);
        });
    }

    private static ItemStack body() {
        ItemStack it = ItemStack.of(Material.FLINT);
        it.setData(DataComponentTypes.ITEM_MODEL, BODY);
        return it;
    }

    private static ItemStack head(Player p) {
        ItemStack it = ItemStack.of(Material.PLAYER_HEAD);
        it.setData(DataComponentTypes.PROFILE, ResolvableProfile.resolvableProfile(p.getPlayerProfile()));
        it.setData(DataComponentTypes.ITEM_MODEL, HEAD);
        return it;
    }

    /** 대역이 아직 그 사람 위에 타 있는가 (누가 내리게 했거나 지웠으면 거둔다). */
    private static boolean intact(Player p, Fig f) {
        for (ItemDisplay d : f.parts) {
            if (!d.isValid()) return false;
            Entity v = d.getVehicle();
            if (v == null || !v.getUniqueId().equals(p.getUniqueId())) return false;
        }
        return true;
    }

    /** 지금 각 (f.angle) 으로 변환을 보낸다. duration 틱 동안 보간 (0 이면 곧바로). */
    private void apply(Fig f, int duration) {
        Config.TumbleCfg c = cfg();
        Quaternionf q = new Quaternionf().rotationY(f.yaw).rotateX((float) Math.toRadians(f.angle));
        Vector3f move = new Vector3f(0f, (float) (c.pivot() - f.attach), 0f);
        Transformation tf = new Transformation(move, q, new Vector3f(c.scale()), new Quaternionf());
        for (ItemDisplay d : f.parts) {
            if (!d.isValid()) continue;
            d.setInterpolationDelay(0);
            d.setInterpolationDuration(duration);
            d.setTransformation(tf);
        }
    }

    // ───────────────────────── 진짜 몸 감추기 ─────────────────────────

    private void hide(Player p, Fig f) {
        f.ownInvis = !p.hasPotionEffect(PotionEffectType.INVISIBILITY);
        if (f.ownInvis) invisible(p);
        EntityEquipment eq = p.getEquipment();
        Map<EquipmentSlot, ItemStack> fake = new EnumMap<>(EquipmentSlot.class);
        for (EquipmentSlot s : SLOTS) {
            ItemStack real = eq.getItem(s);
            if (real.isEmpty()) continue;
            fake.put(s, hiddenCopy(real, s));
            f.faked.add(s);
        }
        if (fake.isEmpty()) return;
        p.sendEquipmentChange(p, fake);
        for (Player v : p.getTrackedBy()) v.sendEquipmentChange(p, fake);
    }

    private void invisible(Player p) {
        int ticks = cfg().reveal() + SAFETY;
        p.addPotionEffect(new PotionEffect(PotionEffectType.INVISIBILITY, ticks, 0, false, false, false));
    }

    /**
     * 손에 든 souls 아이템: 깃발을 켠 사본 (팩이 3인칭에서 비운다, 단축 슬롯 그림과 이름은 그대로).
     * 그 밖 (바닐라 모형의 아이템, 갑옷 칸): 공기.
     */
    static ItemStack hiddenCopy(ItemStack real, EquipmentSlot slot) {
        if (slot != EquipmentSlot.HAND && slot != EquipmentSlot.OFF_HAND) return null;
        Key model = real.getData(DataComponentTypes.ITEM_MODEL);
        if (model == null || !Keys.NS.equals(model.namespace())) return null;
        ItemStack copy = real.clone();
        CustomModelData old = real.getData(DataComponentTypes.CUSTOM_MODEL_DATA);
        List<Boolean> flags = new ArrayList<>(old == null ? List.of() : old.flags());
        while (flags.size() <= HIDE_FLAG) flags.add(false);
        flags.set(HIDE_FLAG, true);
        CustomModelData.Builder b = CustomModelData.customModelData().addFlags(flags);
        if (old != null) b.addFloats(old.floats()).addStrings(old.strings()).addColors(old.colors());
        copy.setData(DataComponentTypes.CUSTOM_MODEL_DATA, b.build());
        return copy;
    }
}
