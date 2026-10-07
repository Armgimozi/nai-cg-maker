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
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.MainHand;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 구르기 대역 (3.3 "보이는 모습", combat.roll.visual: tumble). 바닐라에는 앞구르기 몸짓이 없고, 서버는 플레이어 모형을 마음대로
 * 돌릴 수 없다. 그래서 구르는 동안 진짜 몸을 감추고 그 자리에 관절이 있는 사람 꼴의 대역을 띄워 어깨 구르기를 보인다
 * (사용자가 고른 본보기: 뛰어들어 왼어깨로 땅에 닿고 비스듬히 등을 굴러 다리가 넘어온 뒤 쪼그려 일어선다. 무기는 내내 손에 쥔다).
 *
 * <ul>
 *   <li>대역: 부위마다 ItemDisplay 하나 (머리, 가슴, 배, 윗팔·아랫팔 둘씩, 허벅지·정강이 둘씩 = 열하나), 투구를 썼으면 투구 껍데기,
 *       손에 든 것이 있으면 그 아이템 (주손, 왼손). 몸 부위는 팩의 souls:roll_&lt;부위&gt; (관절이 원점인 상자, 다섯 칸을 물들인다:
 *       {@link SkinTint} 가 그 사람 스킨·갑옷에서 고른 색을 custom_model_data colors 로), 머리는 그 사람 프로필의 player_head
 *       (팩 souls:roll_head 가 목을 원점에 둔다), 투구는 souls:roll_helm. 든 것은 진짜 아이템을 THIRDPERSON_RIGHTHAND / LEFTHAND
 *       자세로 그 아랫팔 끝에 둔다 (바닐라가 손에 든 것을 그리는 자리와 방향, pack/roll_figure.py). 모두 그 사람의 <b>탑승물</b>로
 *       태운다: 클라이언트가 탈것(자기 몸)의 위치에 틱마다 붙이므로 자기 화면에서도 미리 움직인 몸과 어긋나지 않는다.
 *       탑승 자리는 몸 상자 꼭대기 (서 있으면 1.8) 라 변환의 이동으로 발밑까지 내린다.</li>
 *   <li>움직임: 열쇠 자세 표 (자원 roll_anim.yml, pack/roll_figure.py 가 뼈대에서 셈해 쓴다). 자세마다 부위의 관절 자리와 방향이
 *       있고, 표의 tick 틱에 dur 틱 보간으로 보낸다 (변환의 이동 + 왼쪽 회전 = 구르는 쪽 Y 회전 · 부위 방향). 클라이언트는 부위마다
 *       자리는 직선, 방향은 구면 보간한다 (마디가 짧아 관절이 벌어지지 않는다). 처음 자세는 띄울 때 함께 보내고 (생성 패킷),
 *       다음 자세는 2틱부터 (그 전에 바꾸면 생성 패킷과 한 번에 나가 보간 없이 바뀐다). 표는 오른손잡이로 만들었다: 왼손잡이
 *       (주손이 왼쪽) 는 X 를 뒤집고 좌우 부위를 바꾼다. 일어서는 rise-at 틱부터 rise-turn 틱 동안 구르는 쪽에서 몸 방향으로 돈다.</li>
 *   <li>1인칭: 바닐라는 1인칭에서 제 몸을 그리지 않지만 대역은 그린다. 그래서 대역을 두 벌 띄운다: 그 사람에게만 보이는 벌 (own)
 *       과 그 사람만 빼고 모두에게 보이는 벌 (seen, 진짜 자리 그대로). own 은 (1) 표의 hide-pitch (35°) 보다 내려다보면 감추고
 *       (Player#hideEntity/showEntity, 틱마다 보고 바뀔 때만), (2) 덜 내려다보는 동안에도 화면에 들지 않게 자세마다 F5 카메라 자리
 *       (눈에서 보는 쪽 반대로 4 블록, 벽에 막히면 그만큼) 를 가운데로 줄여 눈 뒤로 물린다 (표의 back: 보는 쪽마다 셈한 몫).
 *       F5 카메라에서는 같은 빛줄기 위라 그림이 그대로이고 (그냥 물리면 대역이 카메라 쪽으로 다가와 커 보였다), 1인칭 카메라는
 *       움직이지 않는다. 한 벌로 하면 옆에서 보는 사람에게 대역이 작아지고 뒤로 밀려 보였다 [확인 (클라, 둘째 클라이언트)].</li>
 *   <li>진짜 몸 감추기: 투명 깃발 (Bukkit setInvisible: 효과가 아니라 아이콘·입자·효과 이벤트가 없고, F 를 받은 그 틱의 추적 단계에서
 *       곧바로 나간다). 투명해도 바닐라는 든 것과 입은 것을 그리므로, 그 사람 화면과 보는 사람에게만 장비를 바꿔 보낸다
 *       (sendEquipmentChange, 서버의 진짜 아이템은 그대로). 손: souls 아이템이면 custom_model_data 깃발 {@link #HIDE_FLAG} 를 켠 사본
 *       (팩이 손·머리 자세 (1·3인칭) 에서 비운다. 단축 슬롯 그림과 이름은 그대로라 바닐라가 아이템 이름을 다시 띄우지 않는다), 아니면
 *       공기. 갑옷 칸: 공기 (대역이 그 색을 입는다). 든 것은 대역의 손에 따로 그린다. hand-back 틱에 그 사람 화면에만 주손을 진짜로
 *       돌려주고 (1인칭 무기가 구르기 공격 창 전에 올라오게) 대역 손의 주손 아이템은 그 사람 화면에서 감춘다 (F5 에서 둘로 보이지 않게).</li>
 *   <li>때 (2026-10-08 비평: 늦게 시작하고, 다른 사람에게는 진짜 몸과 대역이 나란히 둘로 보였다): 대역은 F 를 받자마자 띄우고
 *       (생성 패킷은 곧바로 나간다), 투명 깃발은 hide-delay (0) 틱 뒤 = 곧바로 건다 (그다음 틱 끝, 첫 자세 보간과 같은 추적 단계에
 *       나간다). 클라이언트는 새 표시 물체를 받은 뒤 첫 틱에야 그리므로 그 사람 화면에서는 0~1틱 빈 바닥이나 겹침이 있을 수 있다.
 *       다른 사람에게 보이는 벌 (seen) 은 크기 0 으로 띄웠다가 {@link #SEEN_REVEAL} (1) 틱에 그때 자세로 곧바로 (보간 없이) 키운다:
 *       진짜 몸을 감추는 깃발과 같은 추적 단계에 나가서 다른 사람 화면에서 몸과 대역이 바뀐다. 예전에는 대역을 띄우자마자 보이고 깃발이
 *       한 틱 뒤에 나가, 그 한 틱 동안 대역이 (생성 자리 = 서버의 진짜 자리라 남의 화면에서 보간되는 몸보다 앞에서 몸 자리로 미끄러지며)
 *       진짜 몸 옆에 둘로 보였다 [확인 (클라, 둘째 클라이언트): 겹침도 빈틈도 없다].
 *       장비 바꾸기는 깃발을 건 틱 끝 (ServerTickEndEvent). 거둘 때는 reveal 틱 처음에 투명을 걷고 대역을 곧바로 지운다.</li>
 *   <li>밝기: 표시 물체는 제 자리 (탑승 자리) 의 빛으로 그려진다. 진짜 몸처럼 그 사람 눈 자리의 블록 빛·하늘 빛을 틱마다 밝기로 준다
 *       (바뀔 때만).</li>
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
    /** 다른 사람에게 보이는 벌 (seen) 을 크기 0 에서 키우는 구르기 틱: 진짜 몸을 감추는 깃발과 같은 틱 (클래스 머리말 "때") */
    private static final int SEEN_REVEAL = 1;

    /** 대역 부위 (표 roll_anim.yml 의 parts 이름, 팩 모형 souls:roll_&lt;model&gt;). HAND_* 는 든 것의 자리 (모형 없음). */
    enum Part {
        BELLY("belly"), CHEST("chest"), HEAD(null), UARM_R("uarm"), FARM_R("farm"), UARM_L("uarm"), FARM_L("farm"),
        THIGH_R("thigh"), SHIN_R("shin"), THIGH_L("thigh"), SHIN_L("shin"), HAND_R(null), HAND_L(null);

        final String key = name().toLowerCase(Locale.ROOT);
        final String model;

        Part(String model) {
            this.model = model;
        }

        /** 좌우를 바꾼 부위 (왼손잡이) */
        Part mirror() {
            String n = name();
            if (n.endsWith("_R")) return valueOf(n.substring(0, n.length() - 1) + "L");
            if (n.endsWith("_L")) return valueOf(n.substring(0, n.length() - 1) + "R");
            return this;
        }
    }

    /** 열쇠 자세 하나: 보낼 틱, 보간 틱, 보는 쪽 (구르는 쪽에서 30° 마다) 별 물릴 몫 (픽셀), 부위마다 [x, y, z, qx, qy, qz, qw]. */
    record Frame(int tick, int dur, float[] back, float[][] parts) {}

    /** 표 전체: 픽셀 → 블록 배율의 크기 (scale, 블록 = 픽셀 × scale / 16), 감추는 내려다보기 각, F5 카메라 거리 (블록). */
    record Anim(float scale, float hidePitch, float f5Dist, List<Frame> frames) {}

    /** 1인칭에서 비키는 닮음 변환: center (그 사람 발밑 기준, 블록) 를 가운데로 s 배. */
    private record Shrink(Vector3f center, float s) {
        static final Shrink NONE = new Shrink(new Vector3f(), 1f);
        /** 크기 0 (보이지 않는다): seen 벌을 띄울 때 */
        static final Shrink HIDDEN = new Shrink(new Vector3f(), 0f);
    }

    private final Souls plugin;
    private final SkinTint tint;
    private final Anim anim;
    private final Map<UUID, Fig> live = new HashMap<>();

    /** 대역 한 벌의 표시 물체. */
    private static final class Rig {
        final EnumMap<Part, ItemDisplay> body = new EnumMap<>(Part.class);
        ItemDisplay helm, mainItem, offItem;

        List<ItemDisplay> all() {
            List<ItemDisplay> out = new ArrayList<>(body.values());
            if (helm != null) out.add(helm);
            if (mainItem != null) out.add(mainItem);
            if (offItem != null) out.add(offItem);
            return out;
        }
    }

    /**
     * 한 사람의 대역: 두 벌. own 은 그 사람에게만 보이고 (1인칭에서 비키려고 F5 카메라 자리를 가운데로 줄인다), seen 은 그 사람만 빼고
     * 모두에게 보인다 (진짜 자리 그대로). 한 벌을 줄이면 옆에서 보는 사람에게는 대역이 작아지고 뒤로 밀려 보였다 [확인 (클라)].
     */
    private static final class Fig {
        final Rig own = new Rig(), seen = new Rig();
        /** 열쇠 자세와 reveal 을 세는 기준 틱 (구르기 시작 틱) */
        long base;
        /** 구르는 쪽 (라디안, 대역 공간 +Z 가 이쪽을 보게 Y 로 돌린다) 과 지금 보낸 자세의 Y */
        float rollYaw, yaw;
        /** 다음에 보낼 자세 (표의 차례), 지금 보낸 자세 */
        int next, shown;
        /** 왼손잡이: 표를 거울로 */
        boolean mirror;
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
        /** own 벌 가운데 지금 그 사람에게 보이는 것 (내려다보면 감춘다) */
        final Set<UUID> shownOwn = new HashSet<>();
        /** seen 벌을 키웠다 (그 전에는 크기 0) */
        boolean seenShown;
        /** 지금 준 밝기 (블록 빛 << 4 | 하늘 빛, -1 은 아직) */
        int light = -1;

        List<ItemDisplay> parts() {
            List<ItemDisplay> out = own.all();
            out.addAll(seen.all());
            return out;
        }
    }

    public Tumble(Souls plugin) {
        this.plugin = plugin;
        this.tint = new SkinTint(plugin);
        this.anim = load(plugin);
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

    /** 열쇠 자세 수 (시험 명령). 표가 없으면 0. */
    public int frames() {
        return anim == null ? 0 : anim.frames().size();
    }

    /**
     * 구르기 시작 (F 를 받은 때). dir 은 구르는 쪽 (수평, 길이 1).
     * 처음이면 대역을 첫 자세로 곧바로 띄우고, 진짜 몸은 hide-delay 틱 뒤에 감춘다 (클래스 머리말 "때").
     * 이어 구르면 (앞 대역이 아직 있으면) 대역을 그대로 쓰고 첫 자세부터 다시 (1틱 보간).
     */
    public void start(Player p, Vector dir, long now) {
        if (anim == null) return;
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
        f.handBack = false;
        f.base = now;
        f.next = 1;
        f.shown = 0;
        f.rollYaw = (float) Math.atan2(dir.getX(), dir.getZ());
        f.yaw = f.rollYaw;
        f.mirror = p.getMainHand() == MainHand.LEFT;
        f.attach = p.getHeight();
        f.colors = tint.body(p);
        f.helmColor = tint.helm(p);
        if (fresh) {
            spawn(p, f);
            // F 는 틱 사이에 오고 (now 는 지난 틱의 번호), 새 표시 물체는 다음 틱 (now + 1) 부터 그려진다.
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
                p.sendEquipmentChange(p, EquipmentSlot.HAND, hiddenCopy(real, EquipmentSlot.HAND));
            }
            dress(p, f);
            apply(p, f, 0, 1);
            lookDown(p, f);
        }
    }

    /**
     * Ticker 에서 Roll 이 부른다 (틱 처음): hide-delay 틱에 몸을 감추고, 열쇠 자세를 그 틱에 보내고, 내려다보면 그 사람 화면에서
     * 감추고, 몸 높이(자세)가 바뀌면 이동을 맞추고, reveal 틱에 거둔다.
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
            if (p.isDead() || !intact(p, f)) {
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
                // 그 사람 화면에만 주손을 돌려준다 (보는 사람은 reveal 까지 감춘 사본). 대역 손의 주손은 그 사람 화면에서 감춘다
                f.handBack = true;
                p.sendEquipmentChange(p, EquipmentSlot.HAND, p.getEquipment().getItemInMainHand());
            }
            // 자세가 바뀌면 (웅크리기) 탑승 자리가 바뀐다: 이동을 다시 맞춘다
            double h = p.getHeight();
            boolean resized = Math.abs(h - f.attach) > 1e-3;
            f.attach = h;
            boolean moved = false;
            List<Frame> fs = anim.frames();
            while (f.next < fs.size() && fs.get(f.next).tick() <= t) {
                Frame fr = fs.get(f.next);
                apply(p, f, f.next++, fr.dur());
                moved = true;
            }
            if (!moved && resized) apply(p, f, f.shown, 1);
            if (!f.seenShown && t >= SEEN_REVEAL) {
                f.seenShown = true;
                sendRig(f, f.seen, fs.get(f.shown), Shrink.NONE, (float) -f.attach, 0);
            }
            light(p, f);
            lookDown(p, f);
        }
    }

    /** 대역의 밝기를 진짜 몸처럼 그 사람 눈 자리의 블록 빛·하늘 빛으로 (바뀔 때만). */
    private static void light(Player p, Fig f) {
        org.bukkit.block.Block b = p.getEyeLocation().getBlock();
        int block = b.getLightFromBlocks(), sky = b.getLightFromSky();
        int key = block << 4 | sky;
        if (key == f.light) return;
        f.light = key;
        Display.Brightness br = new Display.Brightness(block, sky);
        for (ItemDisplay d : f.parts()) if (d.isValid()) d.setBrightness(br);
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
        // 지운 물체는 Paper 가 그 사람의 감춘 목록에서도 지운다 (CraftPlayer.onEntityRemove)
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
        if (f == null) return;
        for (ItemDisplay d : f.parts()) if (d.isValid()) d.remove();
    }

    /** 나가기: 대역을 거두고 그 사람 기록을 지운다. */
    public void forget(Player p) {
        stop(p);
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
     * 시험 (/soulstest tumble): 대역을 at 에 세운다 (탑승하지 않는다). dir 쪽으로 구르는 frame 번째 열쇠 자세 (물리지 않는다).
     * ticks 뒤에 지운다. 그 사람의 색·머리·투구·든 것으로. 미리보기 (pack/preview/roll_figure.png) 와 견주어 본다.
     */
    public void pose(Player p, Location at, Vector dir, int frame, int ticks) {
        if (anim == null) return;
        Fig f = new Fig();
        f.rollYaw = f.yaw = (float) Math.atan2(dir.getX(), dir.getZ());
        f.mirror = p.getMainHand() == MainHand.LEFT;
        f.colors = tint.body(p);
        f.helmColor = tint.helm(p);
        Location l = at.clone();
        l.setYaw(0f);
        l.setPitch(0f);
        int i = Math.max(0, Math.min(frame, anim.frames().size() - 1));
        Frame fr = anim.frames().get(i);
                List<ItemDisplay> ds = new ArrayList<>();
        for (Part part : Part.values()) {
            if (part.model == null && part != Part.HEAD) continue;
            ds.add(display(p, l, bodyItem(p, part, f), transform(fr, part, f, Shrink.NONE, 0), null, null));
        }
        if (f.helmColor != null) ds.add(display(p, l, helm(f.helmColor), transform(fr, Part.HEAD, f, Shrink.NONE, 0), null, null));
        EntityEquipment eq = p.getEquipment();
        for (boolean main : new boolean[]{true, false}) {
            ItemStack it = main ? eq.getItemInMainHand() : eq.getItemInOffHand();
            if (it.isEmpty()) continue;
            ds.add(display(p, l, it.clone(), transform(fr, handPart(f, main), f, Shrink.NONE, 0), handContext(f, main), null));
        }
        Bukkit.getScheduler().runTaskLater(plugin, () -> ds.forEach(Entity::remove), ticks);
    }

    // ───────────────────────── 대역 ─────────────────────────

    private void spawn(Player p, Fig f) {
        // 탑승 자리 (몸 상자 꼭대기) 에 띄운다: 첫 그림부터 탑승한 자리와 같다. 변환도 만들 때 넣는다 (생성 패킷에 실려
        // 나간다. 만든 뒤에 바꾸면 클라이언트가 한 틱 동안 변환 없이 머리 위에 그렸다)
        Location at = p.getLocation().add(0, f.attach, 0);
        at.setYaw(0f);
        at.setPitch(0f);
        Frame fr = anim.frames().get(0);
        float down = (float) -f.attach;
        // seen 은 크기 0 으로 (SEEN_REVEAL 틱에 키운다: 클래스 머리말 "때")
        fill(p, f, f.seen, at, fr, Shrink.HIDDEN, down, false);
        fill(p, f, f.own, at, fr, shrink(p, f, fr), down, true);
        for (ItemDisplay d : f.parts()) p.addPassenger(d);
        light(p, f);
        // own 벌은 아무에게도 보이지 않게 만들었다: 그 사람이 내려다보고 있지 않으면 그 사람에게 보인다
        lookDown(p, f);
    }

    /** 한 벌을 띄운다. own 이면 아무에게도 보이지 않게 (그 사람에게는 lookDown 이 보인다), 아니면 그 사람에게만 감춘다. */
    private void fill(Player p, Fig f, Rig r, Location at, Frame fr, Shrink sh, float down, boolean own) {
        for (Part part : Part.values()) {
            if (part.model == null && part != Part.HEAD) continue;
            r.body.put(part, display(p, at, bodyItem(p, part, f), transform(fr, part, f, sh, down), null, own));
        }
        if (f.helmColor != null) r.helm = display(p, at, helm(f.helmColor), transform(fr, Part.HEAD, f, sh, down), null, own);
        EntityEquipment eq = p.getEquipment();
        ItemStack main = eq.getItemInMainHand(), off = eq.getItemInOffHand();
        if (!main.isEmpty()) {
            r.mainItem = display(p, at, main.clone(), transform(fr, handPart(f, true), f, sh, down), handContext(f, true), own);
        }
        if (!off.isEmpty()) {
            r.offItem = display(p, at, off.clone(), transform(fr, handPart(f, false), f, sh, down), handContext(f, false), own);
        }
    }

    /** 이어 구를 때: 색·투구를 다시 입힌다 (갑옷을 바꿨을 수 있다). 든 것은 그대로. */
    private void dress(Player p, Fig f) {
        for (Rig r : List.of(f.own, f.seen)) {
            for (Map.Entry<Part, ItemDisplay> e : r.body.entrySet()) {
                if (e.getKey().model != null && e.getValue().isValid()) e.getValue().setItemStack(bodyItem(p, e.getKey(), f));
            }
            if (r.helm != null && f.helmColor == null) {
                // 이어 구르기 전에 투구를 벗었다
                r.helm.leaveVehicle();
                r.helm.remove();
                r.helm = null;
            }
            if (r.helm != null && r.helm.isValid()) r.helm.setItemStack(helm(f.helmColor));
        }
    }

    /** own: 아무에게도 보이지 않게 만든다 (그 사람에게는 lookDown 이 보인다). 아니면 그 사람에게만 감춘다. pose 는 null (모두에게). */
    private ItemDisplay display(Player p, Location at, ItemStack item, Transformation tf, ItemDisplay.ItemDisplayTransform ctx,
                                Boolean own) {
        return p.getWorld().spawn(at, ItemDisplay.class, d -> {
            d.setTransformation(tf);
            d.setItemStack(item);
            d.setItemDisplayTransform(ctx == null ? ItemDisplay.ItemDisplayTransform.FIXED : ctx);
            d.setBillboard(Display.Billboard.FIXED);
            d.setPersistent(false);
            d.addScoreboardTag(Mechanics.FX_TAG);
            d.setTeleportDuration(0);
            d.setInterpolationDuration(0);
            d.setShadowRadius(0f);
            // 만들기 전에 감추면 생성 패킷이 가지 않는다
            if (own == null) return;
            if (own) d.setVisibleByDefault(false);
            else p.hideEntity(plugin, d);
        });
    }

    private static ItemStack bodyItem(Player p, Part part, Fig f) {
        if (part == Part.HEAD) {
            ItemStack it = ItemStack.of(Material.PLAYER_HEAD);
            it.setData(DataComponentTypes.PROFILE, ResolvableProfile.resolvableProfile(p.getPlayerProfile()));
            it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "roll_head"));
            return it;
        }
        ItemStack it = ItemStack.of(Material.FLINT);
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "roll_" + part.model));
        if (f.colors != null) it.setData(DataComponentTypes.CUSTOM_MODEL_DATA, CustomModelData.customModelData().addColors(f.colors).build());
        return it;
    }

    private static ItemStack helm(Color color) {
        ItemStack it = ItemStack.of(Material.FLINT);
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "roll_helm"));
        it.setData(DataComponentTypes.CUSTOM_MODEL_DATA, CustomModelData.customModelData().addColor(color).build());
        return it;
    }

    /**
     * 든 것이 놓이는 손 (그려지는 부위, 그 사람 기준). 주손은 무기 든 팔 = 표의 오른팔이고, 왼손잡이는 거울로 그 팔이 왼쪽이 된다
     * ({@link #transform} 이 거울일 때 반대쪽 표를 읽으므로 왼손잡이의 주손은 HAND_L 자리에 표의 HAND_R 이 온다).
     */
    private static Part handPart(Fig f, boolean main) {
        return main != f.mirror ? Part.HAND_R : Part.HAND_L;
    }

    /** 든 것의 그리는 자세: 그 아이템이 실제로 놓인 손 (바닐라와 같다: 오른손이면 THIRDPERSON_RIGHTHAND). */
    private static ItemDisplay.ItemDisplayTransform handContext(Fig f, boolean main) {
        return handPart(f, main) == Part.HAND_R ? ItemDisplay.ItemDisplayTransform.THIRDPERSON_RIGHTHAND
                : ItemDisplay.ItemDisplayTransform.THIRDPERSON_LEFTHAND;
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
     * 표의 i 번째 자세를 duration 틱 보간으로 보낸다 (0 이면 곧바로). 일어서는 자세 (rise-at 틱 뒤에 닿는 자세) 는 구르는 쪽에서
     * 몸 방향 (getBodyYaw) 으로 rise-turn 틱에 걸쳐 돈다 (옆으로 구른 뒤 진짜 몸이 돌아올 때 90° 튀지 않게).
     */
    private void apply(Player p, Fig f, int i, int duration) {
        Config.TumbleCfg c = cfg();
        Frame fr = anim.frames().get(i);
        f.shown = i;
        int reach = fr.tick() + fr.dur();
        float turn = c.riseTurn() <= 0 ? (reach > c.riseAt() ? 1f : 0f)
                : Math.max(0f, Math.min(1f, (reach - c.riseAt()) / (float) c.riseTurn()));
        float body = (float) Math.toRadians(-p.getBodyYaw());
        f.yaw = f.rollYaw + turn * wrap(body - f.rollYaw);
        float down = (float) -f.attach;
        sendRig(f, f.own, fr, shrink(p, f, fr), down, duration);
        if (f.seenShown) sendRig(f, f.seen, fr, Shrink.NONE, down, duration);
    }

    private void sendRig(Fig f, Rig r, Frame fr, Shrink sh, float down, int duration) {
        for (Map.Entry<Part, ItemDisplay> e : r.body.entrySet()) send(e.getValue(), transform(fr, e.getKey(), f, sh, down), duration);
        if (r.helm != null) send(r.helm, transform(fr, Part.HEAD, f, sh, down), duration);
        if (r.mainItem != null) send(r.mainItem, transform(fr, handPart(f, true), f, sh, down), duration);
        if (r.offItem != null) send(r.offItem, transform(fr, handPart(f, false), f, sh, down), duration);
    }

    private static void send(ItemDisplay d, Transformation tf, int duration) {
        if (!d.isValid()) return;
        d.setInterpolationDelay(0);
        d.setInterpolationDuration(duration);
        d.setTransformation(tf);
    }

    /** -π..π 로 */
    private static float wrap(float a) {
        double r = Math.IEEEremainder(a, Math.PI * 2);
        return (float) r;
    }

    /**
     * 표의 부위 자리 (대역 공간 D 픽셀) 와 방향을 변환으로: 이동 = Y(yaw) · 자리 × scale/16 + 물림 + (0, down, 0),
     * 왼쪽 회전 = Y(yaw) · 방향, 크기 scale. 왼손잡이는 표에서 반대쪽 부위를 X 를 뒤집어 (x → -x, 사원수 (x, -y, -z, w)) 쓴다.
     * 표의 이름이 그 사람 기준의 오른쪽·왼쪽이므로 그려지는 부위 part 에 대해 표의 part.mirror() 를 읽는다.
     */
    private Transformation transform(Frame fr, Part part, Fig f, Shrink sh, float down) {
        float[] v = fr.parts()[(f.mirror ? part.mirror() : part).ordinal()];
        float m = f.mirror ? -1f : 1f;
        float k = anim.scale() / 16f;
        Quaternionf qy = new Quaternionf().rotationY(f.yaw);
        Vector3f pos = qy.transform(new Vector3f(m * v[0] * k, v[1] * k, v[2] * k));
        // F5 카메라 자리를 가운데로 줄인다 (1인칭에서 비키기): c + s (p - c)
        pos.sub(sh.center()).mul(sh.s()).add(sh.center()).add(0f, down, 0f);
        Quaternionf rot = new Quaternionf(qy).mul(new Quaternionf(v[3], m * v[4], m * v[5], v[6]));
        return new Transformation(pos, rot, new Vector3f(anim.scale() * sh.s()), new Quaternionf());
    }

    /**
     * 1인칭에서 비키는 닮음 변환 (세계 축, 그 사람 발밑 기준): 가운데는 F5 카메라 자리 (눈에서 보는 쪽 (내려다보는 각 포함) 의 반대로
     * f5-dist 블록, 바닐라처럼 블록에 막히면 그만큼 가까이), 배율 s = 1 - k / 거리 라 눈 자리의 점이 k 만큼 보는 쪽 반대로 물러난다.
     * k 는 표의 back 에서 보는 쪽 (수평으로, 대역이 구르는 쪽에서 잰 각, 대역 공간 +X 쪽으로 +) 에 맞는 몫을 직선으로 읽는다
     * (왼손잡이는 각을 거울로). F5 카메라에서는 같은 빛줄기 위라 그림이 그대로다.
     */
    private Shrink shrink(Player p, Fig f, Frame fr) {
        Location eye = p.getEyeLocation();
        double yawMc = Math.toRadians(eye.getYaw());
        double lx = -Math.sin(yawMc), lz = Math.cos(yawMc);
        // 세계 → 대역 공간 (Y(-yaw))
        double cy = Math.cos(f.yaw), sy = Math.sin(f.yaw);
        double dx = lx * cy - lz * sy, dz = lx * sy + lz * cy;
        double a = Math.toDegrees(Math.atan2(dx, dz));
        if (f.mirror) a = -a;
        float[] back = fr.back();
        double idx = ((a % 360) + 360) % 360 / (360.0 / back.length);
        int i0 = (int) Math.floor(idx) % back.length, i1 = (i0 + 1) % back.length;
        double w = idx - Math.floor(idx);
        double kb = (back[i0] * (1 - w) + back[i1] * w) * anim.scale() / 16.0;
        Vector look = eye.getDirection();
        double dist = f5Distance(p, eye, look);
        Vector3f c = new Vector3f((float) (-look.getX() * dist), (float) (p.getEyeHeight() - look.getY() * dist), (float) (-look.getZ() * dist));
        return new Shrink(c, (float) Math.max(0.05, 1 - kb / dist));
    }

    /**
     * F5 카메라가 눈 뒤로 떨어진 거리: f5-dist, 눈 뒤로 블록이 있으면 그 앞까지 (바닐라 Camera.getMaxZoom 은 눈 둘레 0.1 의 여덟 줄로
     * 막힘을 본다. 여기는 한 줄에서 0.1 을 뺀다).
     */
    private double f5Distance(Player p, Location eye, Vector look) {
        double max = anim.f5Dist();
        RayTraceResult hit = p.getWorld().rayTraceBlocks(eye, look.clone().multiply(-1), max, FluidCollisionMode.NEVER, true);
        if (hit == null) return max;
        return Math.max(0.3, Math.min(max, hit.getHitPosition().distance(eye.toVector()) - 0.1));
    }

    /**
     * 그 사람에게 보이는 벌 (own): 표의 hide-pitch 보다 내려다보면 감추고, 아니면 보인다 (바뀔 때만). 주손을 돌려준 뒤에는 대역 손의
     * 주손 아이템을 감춘다 (진짜 손에 든 것과 둘로 보이지 않게). 다른 사람에게 보이는 벌 (seen) 은 그 사람에게 늘 감춰져 있다.
     */
    private void lookDown(Player p, Fig f) {
        boolean down = p.getLocation().getPitch() > anim.hidePitch();
        for (ItemDisplay d : f.own.all()) {
            boolean want = !down && !(d == f.own.mainItem && f.handBack);
            boolean is = f.shownOwn.contains(d.getUniqueId());
            if (want == is || !d.isValid()) continue;
            if (want) {
                p.showEntity(plugin, d);
                f.shownOwn.add(d.getUniqueId());
            } else {
                p.hideEntity(plugin, d);
                f.shownOwn.remove(d.getUniqueId());
            }
        }
    }

    // ───────────────────────── 표 읽기 ─────────────────────────

    /** 자원 roll_anim.yml (pack/roll_figure.py anim_table). 없거나 틀리면 null (구르기는 대역 없이 진짜 몸으로). */
    private static Anim load(Souls plugin) {
        try (InputStream in = plugin.getResource("roll_anim.yml")) {
            if (in == null) throw new IllegalStateException("no resource");
            YamlConfiguration y = YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8));
            List<String> names = y.getStringList("parts");
            int[] slot = new int[names.size()];
            for (int i = 0; i < slot.length; i++) slot[i] = Part.valueOf(names.get(i).toUpperCase(Locale.ROOT)).ordinal();
            List<Frame> frames = new ArrayList<>();
            for (Map<?, ?> m : y.getMapList("frames")) {
                List<?> rows = (List<?>) m.get("p");
                List<?> backs = (List<?>) m.get("back");
                if (rows == null || rows.size() != slot.length || backs == null || backs.isEmpty()) {
                    throw new IllegalStateException("bad frame rows");
                }
                float[][] parts = new float[Part.values().length][];
                for (int i = 0; i < slot.length; i++) {
                    List<?> r = (List<?>) rows.get(i);
                    float[] v = new float[7];
                    for (int j = 0; j < 7; j++) v[j] = ((Number) r.get(j)).floatValue();
                    parts[slot[i]] = v;
                }
                for (Part part : Part.values()) {
                    if (parts[part.ordinal()] == null) throw new IllegalStateException("missing part " + part.key);
                }
                float[] back = new float[backs.size()];
                for (int i = 0; i < back.length; i++) back[i] = ((Number) backs.get(i)).floatValue();
                frames.add(new Frame(((Number) m.get("tick")).intValue(), ((Number) m.get("dur")).intValue(), back, parts));
            }
            if (frames.isEmpty()) throw new IllegalStateException("no frames");
            return new Anim((float) y.getDouble("scale", 0.9375), (float) y.getDouble("hide-pitch", 35),
                    (float) Math.max(1, y.getDouble("f5-dist", 4)), List.copyOf(frames));
        } catch (Exception e) {
            plugin.getLogger().warning("roll_anim.yml 을 읽지 못해 구르기 대역 없이 구릅니다: " + e);
            return null;
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
