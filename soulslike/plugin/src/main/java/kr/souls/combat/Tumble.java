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
 *   <li>진짜 몸 감추기: 투명 깃발 (Bukkit setInvisible: 효과가 아니라 아이콘·입자·효과 이벤트가 없고, F 를 받은 그 틱의 추적 단계에서
 *       곧바로 나간다. 투명 효과는 다음 틱에야 깃발이 서서 진짜 몸과 대역이 한 틱 겹쳤다). 투명해도 바닐라는 든 것과 입은 것을
 *       그리므로, 그 사람 화면과 보는 사람에게만 장비를 바꿔 보낸다 (sendEquipmentChange, 서버의 진짜 아이템은 그대로).
 *       손: souls 아이템이면 custom_model_data 깃발 {@link #HIDE_FLAG} 를 켠 사본 (팩이 손·머리 자세에서 비운다 (1·3인칭). 단축 슬롯
 *       그림과 이름은 그대로라 바닐라가 아이템 이름을 다시 띄우지 않는다), 아니면 공기. 갑옷 칸: 공기.</li>
 *   <li>때: 투명 깃발과 대역은 F 를 받자마자 (클라이언트는 표시 물체를 첫 틱에야 그리고 깃발은 다음 추적 단계에서 나가므로,
 *       진짜 몸과 대역이 엇갈리는 틈은 0~1틱, 평균 1/3 틱 남짓), 장비 바꾸기는 그 틱 끝 (ServerTickEndEvent, 깃발이 나간 바로 뒤).
 *       거둘 때는 reveal 틱 처음에 투명을 걷고 그 틱 끝에 대역을 지운다 (지우기는 클라이언트가 곧바로 반영한다).</li>
 *   <li>거두기: reveal 틱, 다음 구르기가 뒷걸음일 때, 죽음, 나가기, 순간이동, 세계 이동, 플러그인 끄기. 투명은 구르기가 건 것만
 *       걷고 (원래 투명했으면 건드리지 않는다), 장비는 진짜를 다시 보내고 인벤토리를 다시 맞춘다. 대역은 저장하지 않고
 *       (persistent false) souls_fx 표가 있어 켤 때 쓸어 낸다. 투명 깃발도 저장되지 않는다 (다시 들어오면 풀린다).</li>
 * </ul>
 * 움직임·무적·비용은 Roll 이 그대로 한다. 이 클래스는 보이는 것만 바꾼다 (봇 시험이 같은 판정을 본다).
 */
@SuppressWarnings("UnstableApiUsage")
public final class Tumble {
    /** 팩의 아이템 정의가 손·머리 자세 (1·3인칭) 에서 비우는 custom_model_data 깃발 번호 (pack/roll_figure.py HIDE_FLAG) */
    public static final int HIDE_FLAG = 0;
    private static final Key BODY = Key.key(Keys.NS, "roll_body");
    private static final Key HEAD = Key.key(Keys.NS, "roll_head");
    private static final EquipmentSlot[] SLOTS = {EquipmentSlot.HAND, EquipmentSlot.OFF_HAND, EquipmentSlot.HEAD,
            EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET};

    private final Souls plugin;
    private final Map<UUID, Fig> live = new HashMap<>();

    /** 한 사람의 대역. */
    private static final class Fig {
        final List<ItemDisplay> parts = new ArrayList<>();
        /** 마디와 reveal 을 세는 기준 틱 (구르기 시작 틱) */
        long base;
        float yaw;
        int next;
        float angle;
        /** 이 틱이 끝날 때 장비를 바꿔 보낸다 / 대역을 거둔다 (ServerTickEndEvent) */
        boolean equipPending, revealPending;
        /** 지금 변환이 맞춘 탑승 높이 (몸 상자 높이: 서기 1.8, 웅크리기 1.5) */
        double attach;
        /** 구르기가 몸을 투명하게 했는가 (원래 투명했으면 (물약 등) 건드리지 않는다) */
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

    /**
     * 구르기 시작 (F 를 받은 때). dir 은 구르는 쪽 (수평, 길이 1).
     * 처음이면 몸을 투명하게 하고 대역을 곧바로 띄운다. 대역의 생성 패킷은 곧바로 나가지만 클라이언트는 표시 물체를 첫 틱에야
     * 그리고 (0~1틱 뒤), 투명 깃발은 다음 엔티티 추적 단계에서 나간다 (0~1틱 뒤). 그래서 둘이 엇갈리는 틈은 평균 1/3 틱 남짓이다.
     * (깃발을 보낸 뒤 틱 끝에 띄우면 늘 0~1틱 비었고, 투명 효과로 감추면 깃발이 한 틱 늦어 늘 겹쳤다.)
     * 장비 바꾸기는 그 틱 끝 (깃발이 나간 바로 뒤) 에 한다. 진짜 몸이 보이는 동안 든 것만 먼저 사라지지 않게.
     * 이어 구르면 (앞 대역이 아직 있으면) 대역을 그대로 쓰고 회전을 처음부터 (0° 와 360° 는 같은 자세라 튀지 않는다).
     */
    public void start(Player p, Vector dir, long now) {
        Fig f = live.get(p.getUniqueId());
        if (f != null && !intact(p, f)) {
            stop(p);
            f = null;
        }
        boolean fresh = f == null;
        if (fresh) {
            f = new Fig();
            f.ownInvis = !p.isInvisible();
            live.put(p.getUniqueId(), f);
        }
        f.revealPending = false;
        f.base = now;
        f.next = 0;
        f.yaw = (float) Math.atan2(dir.getX(), dir.getZ());
        f.angle = 0f;
        f.attach = p.getHeight();
        if (fresh) {
            if (f.ownInvis) p.setInvisible(true);
            spawn(p, f);
            f.equipPending = true;
        } else {
            // 거두려던 틱에 다시 구르면 (투명을 이미 걷었으면) 다시 감춘다
            if (!f.ownInvis && !p.isInvisible()) {
                f.ownInvis = true;
                p.setInvisible(true);
            }
            apply(f, 0);
        }
    }

    /** Ticker 에서 Roll 이 부른다 (틱 처음): 마디마다 회전, 몸 높이(자세)가 바뀌면 이동을 맞추고, reveal 틱에 투명을 걷는다. */
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
            if (p.isDead()) {
                stop(p);
                continue;
            }
            if (f.revealPending) continue;
            if (!intact(p, f)) {
                stop(p);
                continue;
            }
            long t = now - f.base;
            if (t >= c.reveal()) {
                // 투명 깃발은 이 틱의 추적 단계에서 걷히고, 대역은 그 뒤 (tickEnd) 에 지운다
                unInvisible(p, f);
                f.revealPending = true;
                continue;
            }
            // 자세가 바뀌면 (웅크리기) 탑승 자리가 바뀐다: 이동을 다시 맞춘다
            double h = p.getHeight();
            boolean resized = Math.abs(h - f.attach) > 1e-3;
            f.attach = h;
            boolean moved = false;
            while (f.next < c.steps().size() && c.steps().get(f.next).tick() <= t) {
                Config.TumbleStep s = c.steps().get(f.next++);
                f.angle = s.angle();
                apply(f, s.duration());
                moved = true;
            }
            if (!moved && resized) apply(f, 1);
        }
    }

    /** ServerTickEndEvent (Roll 이 부른다, 엔티티 추적 단계 뒤): 이 틱에 시작한 구르기의 장비를 바꾸고, 이 틱에 끝난 대역을 거둔다. */
    public void tickEnd() {
        if (live.isEmpty()) return;
        for (UUID id : List.copyOf(live.keySet())) {
            Player p = Bukkit.getPlayer(id);
            Fig f = live.get(id);
            if (p == null || f == null) {
                drop(id);
                continue;
            }
            if (f.revealPending) {
                stop(p);
            } else if (f.equipPending) {
                f.equipPending = false;
                hideEquipment(p, f);
            }
        }
    }

    /** 대역을 거두고 진짜 몸과 장비를 되돌린다 (곧바로). 없으면 아무것도 하지 않는다. */
    public void stop(Player p) {
        Fig f = live.remove(p.getUniqueId());
        if (f == null) return;
        for (ItemDisplay d : f.parts) {
            if (d.isValid()) {
                d.leaveVehicle();
                d.remove();
            }
        }
        unInvisible(p, f);
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

    /**
     * 투명을 걷는다. Bukkit 의 setInvisible 은 효과와 상관없이 깃발을 붙들어 두는 값이라 (저장되지 않는다) 구르기가 건 것만
     * 걷는다. 구르는 사이에 투명 물약을 받았으면 효과를 다시 걸어 바닐라가 깃발을 다시 세우게 한다.
     */
    private static void unInvisible(Player p, Fig f) {
        if (!f.ownInvis) return;
        f.ownInvis = false;
        p.setInvisible(false);
        PotionEffect e = p.getPotionEffect(PotionEffectType.INVISIBILITY);
        if (e != null) {
            p.removePotionEffect(PotionEffectType.INVISIBILITY);
            p.addPotionEffect(e);
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
        Quaternionf q = new Quaternionf().rotationY((float) Math.atan2(dir.getX(), dir.getZ())).rotateX((float) Math.toRadians(angle));
        Transformation tf = new Transformation(new Vector3f(0f, (float) cfg().pivot(), 0f), q, new Vector3f(cfg().scale()), new Quaternionf());
        List<ItemDisplay> ds = List.of(display(p, l, body(), tf), display(p, l, head(p), tf));
        Bukkit.getScheduler().runTaskLater(plugin, () -> ds.forEach(Entity::remove), ticks);
    }

    // ───────────────────────── 대역 ─────────────────────────

    private void spawn(Player p, Fig f) {
        // 탑승 자리 (몸 상자 꼭대기) 에 띄운다: 첫 그림부터 탑승한 자리와 같다. 변환도 만들 때 넣는다 (생성 패킷에 실려
        // 나간다. 만든 뒤에 바꾸면 클라이언트가 한 틱 동안 변환 없이 머리 위에 그렸다)
        Location at = p.getLocation().add(0, f.attach, 0);
        at.setYaw(0f);
        at.setPitch(0f);
        Transformation tf = transform(f);
        f.parts.add(display(p, at, body(), tf));
        f.parts.add(display(p, at, head(p), tf));
        for (ItemDisplay d : f.parts) p.addPassenger(d);
    }

    private ItemDisplay display(Player p, Location at, ItemStack item, Transformation tf) {
        return p.getWorld().spawn(at, ItemDisplay.class, d -> {
            d.setTransformation(tf);
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

    /** 지금 각 (f.angle) 의 변환: 탑승 자리에서 pivot 높이로 내리고, 구르는 쪽으로 돌린 뒤 옆 축으로 앞으로 angle. */
    private Transformation transform(Fig f) {
        Config.TumbleCfg c = cfg();
        Quaternionf q = new Quaternionf().rotationY(f.yaw).rotateX((float) Math.toRadians(f.angle));
        Vector3f move = new Vector3f(0f, (float) (c.pivot() - f.attach), 0f);
        return new Transformation(move, q, new Vector3f(c.scale()), new Quaternionf());
    }

    /** 지금 각 (f.angle) 으로 변환을 보낸다. duration 틱 동안 보간 (0 이면 곧바로). */
    private void apply(Fig f, int duration) {
        Transformation tf = transform(f);
        for (ItemDisplay d : f.parts) {
            if (!d.isValid()) continue;
            d.setInterpolationDelay(0);
            d.setInterpolationDuration(duration);
            d.setTransformation(tf);
        }
    }

    // ───────────────────────── 진짜 몸 감추기 ─────────────────────────

    private void hideEquipment(Player p, Fig f) {
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

    /**
     * 손에 든 souls 아이템: 깃발을 켠 사본 (팩이 1·3인칭 손에서 비운다, 단축 슬롯 그림과 이름은 그대로).
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
