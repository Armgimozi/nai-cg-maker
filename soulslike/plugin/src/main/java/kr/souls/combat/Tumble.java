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
import org.bukkit.Color;
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
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * 구르기 대역 (3.3 "보이는 모습", combat.roll.visual: tumble). 바닐라에는 앞구르기 몸짓이 없고, 서버는 플레이어 모형을 마음대로
 * 돌릴 수 없다. 그래서 구르는 동안 진짜 몸을 감추고 그 자리에 플레이어 비례의 대역을 띄워 뛰어들기 → 웅크려 한 바퀴 → 일어서기를 보인다.
 *
 * <ul>
 *   <li>대역: ItemDisplay 둘 (투구를 썼으면 셋). 몸은 팩의 souls:roll_&lt;자세&gt; (플레이어 비례의 상자, 다섯 칸을 물들인다:
 *       {@link SkinTint} 가 그 사람 스킨·갑옷에서 고른 색을 custom_model_data colors 로), 머리는 그 사람 프로필의 player_head
 *       (팩 souls:roll_head_&lt;자세&gt; 가 그 자세의 목에 둔다), 투구는 souls:roll_helm_&lt;자세&gt; (머리와 같은 자리, 투구 색).
 *       자세 셋: dive (0틱~첫 마디), tuck (첫 마디~rise-at), rise (rise-at~reveal). 자세를 바꿀 때는 아이템을 바꾸고 같은 틱에 변환도
 *       보낸다 (한 패킷에 실린다). 모두 그 사람의 <b>탑승물</b>로 태운다: 클라이언트가 탈것(자기 몸)의 위치에 틱마다 붙이므로
 *       자기 화면에서도 미리 움직인 몸과 어긋나지 않는다 (순간이동으로 따라가게 하면 서버를 거쳐 1~2틱, 0.4~0.8칸 뒤처진다).
 *       탑승 자리는 몸 상자 꼭대기 (서 있으면 1.8) 라 변환의 이동으로 pivot 높이까지 내린다.</li>
 *   <li>회전: 모든 대역에 같은 변환 (이동 + 왼쪽 회전 = 구르는 쪽 Y · 어깨 쪽으로 tilt 만큼 기운 옆 축으로 θ). 처음 θ 는
 *       start-angle (뛰어들기 자세가 그 각에서 바로 서 보이게 만들어졌다), steps 마디마다 다음 각으로 1틱 보간. 각은 미는 거리를 따라간다
 *       (공 반지름 0.44 가 한 틱 0.42 칸 굴러가는 만큼 남짓). 클라이언트는 회전을 가까운 쪽으로 구면 보간하므로 한 마디가 180° 보다
 *       작으면 앞으로만 돈다. 기운 축 (Rz(t)·Rx(θ)·Rz(-t)) 은 θ 가 0·360° 이면 곧게 서고, 사이에서는 머리가 한쪽 어깨 너머로,
 *       발이 다른 쪽으로 돌아 등 뒤에서도 도는 방향이 읽힌다. 구를 때마다 좌우를 바꾼다. 머리를 목에 두는 것은 팩의 아이템 자세
 *       (fixed) 가 한다: 변환의 이동은 직선 보간이라 이동으로 옮기면 마디 사이에서 회전 중심 쪽으로 꺾인다.</li>
 *   <li>진짜 몸 감추기: 투명 깃발 (Bukkit setInvisible: 효과가 아니라 아이콘·입자·효과 이벤트가 없고, F 를 받은 그 틱의 추적 단계에서
 *       곧바로 나간다. 투명 효과는 다음 틱에야 깃발이 서서 진짜 몸과 대역이 한 틱 겹쳤다). 투명해도 바닐라는 든 것과 입은 것을
 *       그리므로, 그 사람 화면과 보는 사람에게만 장비를 바꿔 보낸다 (sendEquipmentChange, 서버의 진짜 아이템은 그대로).
 *       손: souls 아이템이면 custom_model_data 깃발 {@link #HIDE_FLAG} 를 켠 사본 (팩이 손·머리 자세에서 비운다 (1·3인칭). 단축 슬롯
 *       그림과 이름은 그대로라 바닐라가 아이템 이름을 다시 띄우지 않는다), 아니면 공기. 갑옷 칸: 공기 (대역이 그 색을 입는다).
 *       hand-back 틱에 그 사람 화면에만 주손을 진짜로 돌려준다 (1인칭 무기가 구르기 공격 창 전에 올라오게. 3인칭에서는 그때부터
 *       일어서는 대역 곁에 무기가 보인다).</li>
 *   <li>때: 대역은 F 를 받자마자 띄우고, 투명 깃발은 hide-delay (1) 틱 뒤에 건다. 클라이언트는 새 표시 물체를 받은 뒤 첫 틱에야
 *       그리지만 깃발은 받자마자 반영해서, 같은 틱에 보내면 몸이 먼저 사라지고 0~1틱 빈 화면이 깜빡였다 [확인 (클라): 느린 화면].
 *       한 틱 늦추면 대역이 먼저 그려지고 0~1틱 겹친다. 장비 바꾸기는 깃발을 건 틱 끝 (ServerTickEndEvent, 깃발이 나간 바로 뒤).
 *       거둘 때는 reveal 틱 처음에 투명을 걷고 대역을 곧바로 지운다 (둘 다 클라이언트가 받자마자 반영한다).</li>
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
    private static final EquipmentSlot[] SLOTS = {EquipmentSlot.HAND, EquipmentSlot.OFF_HAND, EquipmentSlot.HEAD,
            EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET};

    /** 대역 자세 (팩 souls:roll_&lt;id&gt;, roll_head_&lt;id&gt;, roll_helm_&lt;id&gt;). */
    public enum Pose {
        DIVE, TUCK, RISE;

        final String id = name().toLowerCase(Locale.ROOT);

        public static Pose parse(String s) {
            try {
                return valueOf(s.trim().toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                return null;
            }
        }
    }

    private final Souls plugin;
    private final SkinTint tint;
    private final Map<UUID, Fig> live = new HashMap<>();
    /** 사람마다 지난 구르기의 기운 쪽 (+1 / -1). 구를 때마다 바꾼다 */
    private final Map<UUID, Integer> sides = new HashMap<>();

    /** 한 사람의 대역. */
    private static final class Fig {
        ItemDisplay body, head, helm;
        /** 마디와 reveal 을 세는 기준 틱 (구르기 시작 틱) */
        long base;
        float yaw, tilt, angle;
        int next;
        Pose pose;
        List<Color> colors;
        Color helmColor;
        /** 이 틱이 끝날 때 장비를 바꿔 보낸다 (ServerTickEndEvent) / 그 사람 화면에 주손을 돌려주었다 */
        boolean equipPending, handBack;
        /** 이 틱에 진짜 몸을 감춘다 (hide-delay, 감춘 뒤 -1) */
        long hideAt = -1;
        /** 지금 변환이 맞춘 탑승 높이 (몸 상자 높이: 서기 1.8, 웅크리기 1.5) */
        double attach;
        /** 구르기가 몸을 투명하게 했는가 (원래 투명했으면 (물약 등) 건드리지 않는다) */
        boolean ownInvis;
        /** 바꿔 보낸 장비 칸 */
        final List<EquipmentSlot> faked = new ArrayList<>();

        List<ItemDisplay> parts() {
            List<ItemDisplay> out = new ArrayList<>(3);
            if (body != null) out.add(body);
            if (head != null) out.add(head);
            if (helm != null) out.add(helm);
            return out;
        }
    }

    public Tumble(Souls plugin) {
        this.plugin = plugin;
        this.tint = new SkinTint(plugin);
    }

    public SkinTint tint() {
        return tint;
    }

    private Config.TumbleCfg cfg() {
        return plugin.cfg().roll.tumble();
    }

    public boolean active(Player p) {
        return live.containsKey(p.getUniqueId());
    }

    /**
     * 구르기 시작 (F 를 받은 때). dir 은 구르는 쪽 (수평, 길이 1).
     * 처음이면 몸을 투명하게 하고 대역을 뛰어들기 자세로 곧바로 띄운다. 대역의 생성 패킷은 곧바로 나가지만 클라이언트는 표시 물체를
     * 첫 틱에야 그리고 (0~1틱 뒤), 투명 깃발은 다음 엔티티 추적 단계에서 나간다 (0~1틱 뒤). 그래서 둘이 엇갈리는 틈은 평균 1/3 틱
     * 남짓이다. 장비 바꾸기는 그 틱 끝 (깃발이 나간 바로 뒤) 에 한다. 진짜 몸이 보이는 동안 든 것만 먼저 사라지지 않게.
     * 이어 구르면 (앞 대역이 아직 있으면) 대역을 그대로 쓰고 뛰어들기 자세부터 다시.
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
            live.put(p.getUniqueId(), f);
        }
        Config.TumbleCfg c = cfg();
        int side = -sides.getOrDefault(p.getUniqueId(), -1);
        sides.put(p.getUniqueId(), side);
        f.handBack = false;
        f.base = now;
        f.next = 0;
        f.yaw = (float) Math.atan2(dir.getX(), dir.getZ());
        f.tilt = side * c.tilt();
        f.angle = c.startAngle();
        f.attach = p.getHeight();
        f.pose = Pose.DIVE;
        f.colors = tint.body(p);
        f.helmColor = tint.helm(p);
        if (fresh) {
            spawn(p, f);
            // F 는 틱 사이에 오고 (now 는 지난 틱의 번호), 새 표시 물체의 생성 패킷은 다음 틱 (now + 1) 의 추적 단계에서 나간다.
            // 그 틱에 깃발을 걸면 둘이 한 번에 나간다 (hide-delay 0: 곧바로 건다). hide-delay 틱 더 늦춘다
            f.hideAt = now + 1 + c.hideDelay();
            if (c.hideDelay() == 0) hide(p, f);
        } else {
            // 거두려던 틱에 다시 구르면 (투명을 이미 걷었으면) 다시 감춘다
            if (!f.ownInvis && !p.isInvisible()) {
                f.ownInvis = true;
                p.setInvisible(true);
            }
            // 주손을 먼저 돌려주었으면 다시 감춘다
            if (f.faked.contains(EquipmentSlot.HAND)) {
                ItemStack real = p.getEquipment().getItemInMainHand();
                ItemStack fake = hiddenCopy(real, EquipmentSlot.HAND);
                p.sendEquipmentChange(p, EquipmentSlot.HAND, fake);
            }
            dress(p, f);
            apply(f, 0);
        }
    }

    /**
     * Ticker 에서 Roll 이 부른다 (틱 처음): hide-delay 틱에 몸을 감추고, 마디마다 회전·자세, 몸 높이(자세)가 바뀌면 이동을 맞추고,
     * reveal 틱에 거둔다.
     */
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
            if (!intact(p, f)) {
                stop(p);
                continue;
            }
            long t = now - f.base;
            if (f.hideAt >= 0 && now >= f.hideAt) hide(p, f);
            if (t >= c.reveal()) {
                // 투명을 걷고 (깃발은 이 틱의 추적 단계에서 나간다) 대역을 곧바로 지운다. 틱 끝에 지우면 지우기 패킷이 다음 틱에야
                // 나가 일어서는 대역과 진짜 몸이 한 틱 겹쳐 보였다 [확인 (클라): 느린 화면]
                stop(p);
                continue;
            }
            if (!f.handBack && c.handBack() > 0 && t >= c.handBack() && f.faked.contains(EquipmentSlot.HAND)) {
                // 그 사람 화면에만 주손을 돌려준다 (보는 사람은 reveal 까지 감춘 사본)
                f.handBack = true;
                p.sendEquipmentChange(p, EquipmentSlot.HAND, p.getEquipment().getItemInMainHand());
            }
            // 자세가 바뀌면 (웅크리기) 탑승 자리가 바뀐다: 이동을 다시 맞춘다
            double h = p.getHeight();
            boolean resized = Math.abs(h - f.attach) > 1e-3;
            f.attach = h;
            boolean moved = false;
            if (f.pose != Pose.RISE && t >= c.riseAt()) {
                // 일어서기: 한 바퀴를 마친 자세 (360°) 에서 구르는 쪽 → 몸 방향으로 돌며 선다
                f.pose = Pose.RISE;
                f.angle = 360f;
                f.next = c.steps().size();
                f.yaw = (float) Math.toRadians(-p.getBodyYaw());
                dress(p, f);
                apply(f, c.riseTurn());
                moved = true;
            }
            while (f.next < c.steps().size() && c.steps().get(f.next).tick() <= t) {
                Config.TumbleStep s = c.steps().get(f.next++);
                f.angle = s.angle();
                if (f.pose == Pose.DIVE) {
                    f.pose = Pose.TUCK;
                    dress(p, f);
                }
                apply(f, s.duration());
                moved = true;
            }
            if (!moved && resized) apply(f, 1);
        }
    }

    /** ServerTickEndEvent (Roll 이 부른다, 엔티티 추적 단계 뒤): 이 틱에 몸을 감춘 구르기의 장비를 바꾼다. */
    public void tickEnd() {
        if (live.isEmpty()) return;
        for (UUID id : List.copyOf(live.keySet())) {
            Player p = Bukkit.getPlayer(id);
            Fig f = live.get(id);
            if (p == null || f == null) {
                drop(id);
                continue;
            }
            if (f.equipPending) {
                f.equipPending = false;
                hideEquipment(p, f);
            }
        }
    }

    /** 대역을 거두고 진짜 몸과 장비를 되돌린다 (곧바로). 없으면 아무것도 하지 않는다. */
    public void stop(Player p) {
        Fig f = live.remove(p.getUniqueId());
        if (f == null) return;
        for (ItemDisplay d : f.parts()) {
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
     * 진짜 몸을 감춘다 (투명 깃발은 이 틱의 추적 단계에서 나가고, 장비는 그 뒤 틱 끝에 바꿔 보낸다). 원래 투명했으면 깃발은
     * 건드리지 않는다 (물약 등).
     */
    private static void hide(Player p, Fig f) {
        f.hideAt = -1;
        f.ownInvis = !p.isInvisible();
        if (f.ownInvis) p.setInvisible(true);
        f.equipPending = true;
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
        sides.remove(id);
        if (f == null) return;
        for (ItemDisplay d : f.parts()) if (d.isValid()) d.remove();
    }

    /** 나가기: 대역을 거두고 그 사람 기록을 지운다. */
    public void forget(Player p) {
        stop(p);
        sides.remove(p.getUniqueId());
        tint.forget(p.getUniqueId());
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
     * 기울기 없이 (곧은 옆 축). 그 사람의 색·머리·투구로. 실제 클라이언트에서 미리보기 (pack/preview/roll_figure.png) 와 견주어 본다.
     */
    public void pose(Player p, Location at, Vector dir, Pose pose, float angle, int ticks) {
        Location l = at.clone();
        l.setYaw(0f);
        l.setPitch(0f);
        Quaternionf q = new Quaternionf().rotationY((float) Math.atan2(dir.getX(), dir.getZ())).rotateX((float) Math.toRadians(angle));
        Config.TumbleCfg c = cfg();
        Transformation tf = new Transformation(new Vector3f(0f, (float) c.pivot(), 0f), q, new Vector3f(c.scale()), new Quaternionf());
        List<ItemDisplay> ds = new ArrayList<>(List.of(display(p, l, body(pose, tint.body(p)), tf), display(p, l, head(p, pose), tf)));
        Color hc = tint.helm(p);
        if (hc != null) ds.add(display(p, l, helm(pose, hc), tf));
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
        f.body = display(p, at, body(f.pose, f.colors), tf);
        f.head = display(p, at, head(p, f.pose), tf);
        if (f.helmColor != null) f.helm = display(p, at, helm(f.pose, f.helmColor), tf);
        for (ItemDisplay d : f.parts()) p.addPassenger(d);
    }

    /** 지금 자세 (f.pose) 의 아이템을 입힌다 (같은 틱에 보내는 변환과 한 패킷에 실린다). */
    private void dress(Player p, Fig f) {
        if (f.body != null && f.body.isValid()) f.body.setItemStack(body(f.pose, f.colors));
        if (f.head != null && f.head.isValid()) f.head.setItemStack(head(p, f.pose));
        if (f.helm != null && f.helm.isValid()) f.helm.setItemStack(helm(f.pose, f.helmColor));
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

    private static ItemStack body(Pose pose, List<Color> colors) {
        ItemStack it = ItemStack.of(Material.FLINT);
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "roll_" + pose.id));
        if (colors != null) it.setData(DataComponentTypes.CUSTOM_MODEL_DATA, CustomModelData.customModelData().addColors(colors).build());
        return it;
    }

    private static ItemStack head(Player p, Pose pose) {
        ItemStack it = ItemStack.of(Material.PLAYER_HEAD);
        it.setData(DataComponentTypes.PROFILE, ResolvableProfile.resolvableProfile(p.getPlayerProfile()));
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "roll_head_" + pose.id));
        return it;
    }

    private static ItemStack helm(Pose pose, Color color) {
        ItemStack it = ItemStack.of(Material.FLINT);
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "roll_helm_" + pose.id));
        it.setData(DataComponentTypes.CUSTOM_MODEL_DATA, CustomModelData.customModelData().addColor(color).build());
        return it;
    }

    /** 대역이 아직 그 사람 위에 타 있는가 (누가 내리게 했거나 지웠으면 거둔다). */
    private static boolean intact(Player p, Fig f) {
        for (ItemDisplay d : f.parts()) {
            if (!d.isValid()) return false;
            Entity v = d.getVehicle();
            if (v == null || !v.getUniqueId().equals(p.getUniqueId())) return false;
        }
        return true;
    }

    /**
     * 지금 각의 변환: 탑승 자리에서 pivot 높이로 내리고, 구르는 쪽으로 돌린 뒤 어깨 쪽으로 기운 옆 축으로 앞으로 angle
     * (Ry(yaw)·Rz(tilt)·Rx(angle)·Rz(-tilt): angle 이 0·360° 이면 곧게 선다).
     */
    private Transformation transform(Fig f) {
        Config.TumbleCfg c = cfg();
        float tilt = (float) Math.toRadians(f.tilt);
        Quaternionf q = new Quaternionf().rotationY(f.yaw).rotateZ(tilt).rotateX((float) Math.toRadians(f.angle)).rotateZ(-tilt);
        Vector3f move = new Vector3f(0f, (float) (c.pivot() - f.attach), 0f);
        return new Transformation(move, q, new Vector3f(c.scale()), new Quaternionf());
    }

    /** 지금 각 (f.angle) 으로 변환을 보낸다. duration 틱 동안 보간 (0 이면 곧바로). */
    private void apply(Fig f, int duration) {
        Transformation tf = transform(f);
        for (ItemDisplay d : f.parts()) {
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
