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
import java.util.List;
import java.util.Locale;
import java.util.Map;
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
 *   <li>1인칭: 바닐라는 1인칭에서 제 몸을 그리지 않지만 대역은 그린다. 서버는 그 사람이 1인칭인지 F5 인지 모르므로 (예전 판은
 *       35° 넘게 내려다보면 감추어 F5 로 내려다볼 때 아무것도 보이지 않았다) 카메라를 아는 클라이언트가 가른다: 대역을 두 벌 띄우고
 *       (그 사람에게만 보이는 own, 그 사람만 빼고 모두에게 보이는 seen. 둘 다 같은 자세·같은 자리), own 의 그림은 모두 팩의 표시 알파
 *       그림 (몸 부위 souls:roll_&lt;부위&gt;_m, 투구 roll_helm_m, 머리는 스킨 픽셀 머리 roll_headpx, 손에 든 souls 아이템은
 *       custom_model_data 깃발 {@link #MARK_FLAG} 의 표시판) 이다. 팩의 아이템 셰이더가 표시 알파의 삼각형을 그 세 꼭짓점이 모두
 *       카메라에서 반지름 안이면 버린다. 반지름은 열쇠 자세마다 부위마다 그 자세 동안 그 부위가 1인칭 카메라에서 가장 멀어지는 거리
 *       (자원 roll_anim.yml radius, pack/roll_figure.py radius_table) 이고, 열쇠 자세를 보낼 때 own 벌의 물들이는 색의 낮은 비트에
 *       실어 보낸다 ({@link #encode}). 1인칭 카메라는 대역 곁이라 하나도 그려지지 않고, F5 카메라는 4 블록 떨어져 있어 그대로 그려진다.
 *       자세·내려다보는 각과 상관없다. 손에 든 것은 물들이지 않아 그림의 표시 알파가 정한 (모든 자세의) 반지름을 쓴다. 표시판이 없는
 *       바닐라 아이템은 own 에 들리지 않는다 (게임 아이템은 모두 souls 아이템이다). seen 은 바닐라 머리와 진짜 아이템 그대로다.</li>
 *   <li>벽 곁: 몸이 오른쪽으로 1.2 블록 가까이 넘어가므로 (옆 끝 표 roll_anim.yml side) 구르는 길 옆이 막혔으면 반대 어깨로 (표를
 *       거울로, 든 것은 제 손에 그대로) 구르고, 그래도 닿으면 그 자세 동안 대역을 벽 반대쪽으로 옮긴다 ({@link #MAX_SHIFT} 까지).</li>
 *   <li>진짜 몸 감추기: 투명 깃발 (Bukkit setInvisible: 효과가 아니라 아이콘·입자·효과 이벤트가 없고, F 를 받은 그 틱의 추적 단계에서
 *       곧바로 나간다). 투명해도 바닐라는 든 것과 입은 것을 그리므로, 그 사람 화면과 보는 사람에게만 장비를 바꿔 보낸다
 *       (sendEquipmentChange, 서버의 진짜 아이템은 그대로). 손: souls 아이템이면 custom_model_data 깃발 {@link #HIDE_FLAG} 를 켠 사본
 *       (팩이 손·머리 자세 (1·3인칭) 에서 비운다. 단축 슬롯 그림과 이름은 그대로라 바닐라가 아이템 이름을 다시 띄우지 않는다), 아니면
 *       공기. 갑옷 칸: 공기 (대역이 그 색을 입는다). 든 것은 대역의 손에 따로 그린다. 그 사람 화면에는 감춘 사본을 틱마다 조금씩 다른
 *       사본 ({@link #HOLD_TAG}) 으로 다시 보내 바닐라 1인칭 손이 내려간 채 머문다 (같은 아이템이면 손이 다시 올라온다. 그러면 돌려줄
 *       때 내려갔다가 올라와 세 틱이 늦었다). hand-back 틱에 그 사람 화면에만 두 손을 진짜로 돌려주고 (1인칭 무기가 구르기 공격 창
 *       9틱에 올라와 있게: 손이 바닥에서 곧바로 올라온다) 대역 손의 든 것은 그 사람 화면에서 감춘다 (F5 에서 둘로 보이지 않게).</li>
 *   <li>때 (2026-10-08 비평: 늦게 시작하고, 다른 사람에게는 진짜 몸과 대역이 나란히 둘로 보였다): 대역은 F 를 받자마자 띄우고
 *       (생성 패킷은 곧바로 나간다), 투명 깃발은 hide-delay (1) 틱 뒤에 건다 (F 를 받은 다음다음 틱의 추적 단계에 나간다. 0 이면
 *       다음 틱: 클라이언트가 새 대역을 한 번도 다루기 전에 깃발이 닿으면 대역이 처음 그려지기까지 0~1틱 빈 바닥이 생겼다 [확인
 *       (클라)]). 두 벌 (seen 과 own) 모두 보기 거리 (view_range) 0 으로 띄워 그려지지 않다가 깃발이 나가는 틱 ({@link #REVEAL} +
 *       hide-delay) 에 보기 거리를 1 로 돌린다: 보기 거리와 투명 깃발은 클라이언트가 받자마자 (다음 틱을 기다리지 않고) 그리므로 같은
 *       추적 단계에 나가면 그 사람의 F5 화면에서도 남의 화면에서도 몸과 대역이 같은 그림에서 바뀐다. 자세 (변환) 는 띄울 때부터 보내 둔다.
 *       예전에는 own 을 띄우자마자 보여 깃발이 닿기 전 0~1틱 둘로 보였고 (그 사람의 F5 화면 [확인 (클라): 2026-10-08 비평의
 *       tumble_back_p30 #4]), 크기 0 으로 띄웠다가 키우는 판은 변환을 다음 틱에야 그려 0~1틱 빈 바닥이 생겼고, 키우는 변환과 다음
 *       자세가 클라이언트의 한 틱에 겹쳐 닿으면 크기 0 에서 보간해 팔다리가 점에서 자라났다 [확인 (클라): 1칸 틈 앞 구르기].
 *       서버가 밀린 틱을 따라잡는 중이면 (생성 패킷이 나간 틱 끝에서 틱 간격의 반이 지나지 않았으면) 깃발과 보기 거리를 한 틱씩
 *       늦춘다 ({@link #MAX_LATE}). 장비 바꾸기는 깃발을 건 틱 끝 (ServerTickEndEvent). 거둘 때는 reveal 틱 처음에 투명을 걷고
 *       대역을 곧바로 지운다.</li>
 *   <li>기어가기 (Roll 의 crawl): 구르는 동안 그 사람 화면에만 머리 위 막힘을 깔아 클라이언트가 기어가기 자세 (몸 상자 0.6, 눈 0.4) 로
 *       구르면 1인칭 시야가 바닥까지 내려갔다 올라온다. 탑승 자리는 클라이언트가 자기 자세의 몸 상자 꼭대기로 정하므로 own 벌은 그
 *       사람 화면의 기어가기 상자 (0.6) 에 맞춰 내리고 ({@link #CRAWL_HEIGHT}, 띄우는 자리도 그 높이), seen 벌은 서버 자세 (서기 1.8)
 *       그대로다. 막힘은 대역과 같은 틱에 거둔다 (Roll).</li>
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
    /** 두 벌을 보이게 하는 구르기 틱 (+ hide-delay): 진짜 몸을 감추는 깃발과 같은 틱 (클래스 머리말 "때") */
    private static final int REVEAL = 1;
    /**
     * 깃발·보기 거리를 늦추는 틱 수의 끝: 생성 패킷이 나간 틱 끝에서 이 틱 처음까지 틱 간격의 반이 지나지 않았으면 (서버가 밀린
     * 틱을 쉬지 않고 따라잡는 중: 첫 구르기의 차가운 코드, 렉) 한 틱씩 늦춘다. 두 패킷이 붙어 닿으면 클라이언트가 대역을 한 틱도
     * 다루지 못해 (그리기 상태가 없다) 한 틱 빈 바닥이 생겼다 [확인 (클라): 들어와서 첫 구르기]
     */
    private static final int MAX_LATE = 3;
    /** own 벌이 손에 든 souls 아이템의 custom_model_data 깃발: 팩이 표시판 (1인칭에서 버리는 표시 알파 그림) 으로 그린다 (pack/roll_figure.py MARK_FLAG) */
    public static final int MARK_FLAG = 1;
    /** 기어가기 자세의 몸 상자 높이 (바닐라 Pose.SWIMMING): 그 사람 화면에서 탑승 자리가 여기다 */
    public static final double CRAWL_HEIGHT = 0.6;
    /** 반지름 code (물들이는 색 R·G·B 의 낮은 두 비트 = 6 비트): 1..62 만 쓴다. 0 과 63 (흰 면) 은 셰이더가 표시 알파 반지름으로 돌아간다 */
    private static final int CODE_MIN = 1, CODE_MAX = 62;
    /** 벽 곁에서 대역을 옆으로 옮기는 가장 큰 몫 (블록). 처음·끝 자세 (진짜 몸과 바뀌는 때) 는 {@link #EDGE_SHIFT} 까지 */
    private static final double MAX_SHIFT = 0.6, EDGE_SHIFT = 0.15;
    /** 구르는 길 옆의 벽을 보는 높이 (발 위, 블록: 넘어가는 머리·어깨·엉덩이) 와 길을 따라 보는 마디·길이 */
    private static final double[] WALL_HEIGHTS = {0.15, 0.55, 0.95};
    private static final double WALL_STEP = 0.6, WALL_PATH = 3.6, WALL_REACH = 1.6;
    /** 그 사람 화면에 감춘 손 사본을 틱마다 바꿔 보내는 custom_model_data 글 (팩은 읽지 않는다: 바닐라 1인칭 손이 내려간 채 머물게) */
    static final String HOLD_TAG = "roll_hold";

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

    /**
     * 열쇠 자세 하나: 보낼 틱, 보간 틱, 부위마다 [x, y, z, qx, qy, qz, qw], 부위마다 1인칭 반지름 (블록: stand = 기어가기 막힘이
     * 없을 때, crawl = 막힘을 깔았을 때. 표가 없으면 null), 몸의 옆 끝 [가장 오른쪽 x, 가장 왼쪽 x] (블록, 없으면 null).
     */
    record Frame(int tick, int dur, float[][] parts, float[] stand, float[] crawl, float[] side) {}

    /**
     * 표 전체: 픽셀 → 블록 배율의 크기 (scale, 블록 = 픽셀 × scale / 16), 반지름 표가 셈한 막힘 틱 수 (duck, 없으면 -1),
     * code 한 칸 (블록), 반지름에 더하는 여유 (블록).
     */
    record Anim(float scale, List<Frame> frames, int duck, double codeStep, double margin) {}

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
     * 한 사람의 대역: 두 벌, 같은 자세. own 은 그 사람에게만 보이고 표시 알파 그림이라 그 사람의 1인칭 카메라 곁에서 셰이더가 버린다.
     * seen 은 그 사람만 빼고 모두에게 보인다 (바닐라 머리, 진짜 아이템).
     */
    private static final class Fig {
        final Rig own = new Rig(), seen = new Rig();
        /** 열쇠 자세와 reveal 을 세는 기준 틱 (구르기 시작 틱) */
        long base;
        /** 구르는 쪽 (라디안, 대역 공간 +Z 가 이쪽을 보게 Y 로 돌린다) 과 지금 보낸 자세의 Y */
        float rollYaw, yaw;
        /** 다음에 보낼 자세 (표의 차례), 지금 보낸 자세 */
        int next, shown;
        /** 표를 거울로 (왼손잡이 XOR 반대 어깨로 구르기 flip) / 왼손잡이 (든 것이 놓이는 손) / 벽 때문에 반대 어깨로 */
        boolean mirror, leftHanded, flip;
        /** 자세마다 대역을 옆으로 옮기는 몫 (블록, 구르는 쪽 기준 +는 그 사람의 왼쪽. 없으면 null) */
        double[] shift;
        /** 반지름 표: 기어가기 막힘을 깐 구르기 (crawl 표). 표의 duck 이 설정과 다르면 code 를 보내지 않는다 (codes false) */
        boolean crawlTable, codes;
        /** own 벌에 지금 보낸 부위마다의 code (0: 아직) */
        final EnumMap<Part, Integer> sentCode = new EnumMap<>(Part.class);
        /** 그 사람 화면에 감춘 손 사본을 바꿔 보낸 횟수 ({@link #HOLD_TAG}) */
        int hold;
        List<Color> colors;
        /** own 벌의 픽셀 머리 색 384 개 (모르면 null: 팩 기본 얼굴) */
        List<Color> headColors;
        Color helmColor;
        /** 이 틱이 끝날 때 장비를 바꿔 보낸다 (ServerTickEndEvent) / 그 사람 화면에 주손을 돌려주었다 */
        boolean equipPending, handBack;
        /** 이 틱에 진짜 몸을 감춘다 (hide-delay, 감춘 뒤 -1) */
        long hideAt = -1;
        /** 대역의 생성 패킷이 나간 틱 끝의 System.nanoTime (0 은 아직, {@link #MAX_LATE}) */
        long sentNanos;
        /** 지금 변환이 맞춘 탑승 높이 (몸 상자 높이: 서기 1.8, 웅크리기 1.5). seen 벌 = 서버의 자세 */
        double attach;
        /** own 벌의 탑승 높이 (그 사람 클라이언트의 자세: 기어가기면 {@link #CRAWL_HEIGHT}, 아니면 attach) */
        double ownAttach;
        /** 그 사람 화면에 기어가기 막힘이 깔렸다 (own 벌은 기어가기 상자 높이에 붙는다) */
        boolean crawl;
        /** 구르기가 몸을 투명하게 했는가 (원래 투명했으면 (물약 등) 건드리지 않는다) */
        boolean ownInvis;
        /** 바꿔 보낸 장비 칸 */
        final List<EquipmentSlot> faked = new ArrayList<>();
        /** own 벌의 든 것을 그 사람 화면에서 감추었다 (hand-back 뒤: 진짜 손에 든 것과 둘로 보이지 않게) */
        boolean ownHeldHidden;
        /** 두 벌을 보이게 했다 (그 전에는 보기 거리 0) */
        boolean revealed;
        /** 보이게 하는 틱 (구르기 틱: REVEAL + hide-delay) */
        int revealAt = REVEAL;
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
     * 구르기 시작 (F 를 받은 때). dir 은 구르는 쪽 (수평, 길이 1). crawl 이면 그 사람 화면에 기어가기 막힘이 깔린다 (Roll 이 먼저 깐다):
     * own 벌을 기어가기 상자 높이에 붙인다.
     * 처음이면 대역을 첫 자세로 곧바로 띄우고, 진짜 몸은 hide-delay 틱 뒤에 감춘다 (클래스 머리말 "때").
     * 이어 구르면 (앞 대역이 아직 있으면) 대역을 그대로 쓰고 첫 자세부터 다시 (1틱 보간).
     */
    public void start(Player p, Vector dir, long now, boolean crawl) {
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
        int prevShown = f.shown;
        f.handBack = false;
        f.hold = 0;
        f.base = now;
        f.next = 1;
        f.shown = 0;
        f.rollYaw = (float) Math.atan2(dir.getX(), dir.getZ());
        f.yaw = f.rollYaw;
        f.leftHanded = p.getMainHand() == MainHand.LEFT;
        f.attach = p.getHeight();
        f.crawl = crawl;
        f.crawlTable = crawl;
        f.codes = !crawl || anim.duck() == c.duck();
        f.ownAttach = crawl ? CRAWL_HEIGHT : f.attach;
        f.colors = tint.body(p);
        f.helmColor = tint.helm(p);
        f.headColors = tint.head(p);
        sides(p, dir, f);
        if (fresh) {
            spawn(p, f);
            // F 는 틱 사이에 오고 (now 는 지난 틱의 번호), 새 표시 물체는 다음 틱 (now + 1) 부터 그려진다.
            // 그 틱에 깃발을 걸면 둘이 한 번에 나간다 (hide-delay 0: 곧바로 건다). hide-delay 틱 더 늦춘다 (기본 1: 클라이언트가 대역을 한 틱 다룬 뒤).
            // 두 벌은 보기 거리 0 으로 띄웠다가 깃발이 나가는 틱에 보이게 한다 (클래스 머리말 "때")
            f.hideAt = now + 1 + c.hideDelay();
            f.revealAt = REVEAL + c.hideDelay();
            if (c.hideDelay() == 0) hide(p, f);
        } else {
            // 거두려던 틱에 다시 구르면 (투명을 이미 걷었으면) 다시 감춘다
            if (!f.ownInvis && !p.isInvisible()) {
                f.ownInvis = true;
                p.setInvisible(true);
            }
            // 손을 먼저 돌려주었으면 다시 감춘다
            for (EquipmentSlot s : new EquipmentSlot[]{EquipmentSlot.HAND, EquipmentSlot.OFF_HAND}) {
                if (f.faked.contains(s)) p.sendEquipmentChange(p, s, hiddenCopy(p.getEquipment().getItem(s), s, 0));
            }
            if (f.ownHeldHidden) {
                for (ItemDisplay d : new ItemDisplay[]{f.own.mainItem, f.own.offItem}) {
                    if (d != null && d.isValid()) p.showEntity(plugin, d);
                }
                f.ownHeldHidden = false;
            }
            dress(p, f);
            // 앞 자세에서 처음 자세로 1틱 보간: 반지름은 두 자세 가운데 큰 것
            apply(p, f, 0, 1, prevShown);
        }
    }

    /**
     * 구르는 길 옆의 벽 (Tumble 클래스 머리말 "벽 곁"): 길을 따라 WALL_STEP 마다 (앞이 막히면 거기까지) WALL_HEIGHTS 높이에서 왼쪽·
     * 오른쪽으로 빈 거리를 재고, 몸이 넘어가는 쪽 (옆 끝 표) 이 모자라면 반대 어깨로 구른다 (f.flip). 그래도 닿는 자세는 벽 반대쪽으로
     * 옮긴다 (f.shift). 표에 옆 끝이 없으면 아무것도 하지 않는다.
     */
    private void sides(Player p, Vector dir, Fig f) {
        f.flip = false;
        f.shift = null;
        f.mirror = f.leftHanded;
        List<Frame> fs = anim.frames();
        if (fs.get(0).side() == null) return;
        Vector left = new Vector(dir.getZ(), 0, -dir.getX());
        double freeL = WALL_REACH, freeR = WALL_REACH;
        org.bukkit.World w = p.getWorld();
        Location feet = p.getLocation();
        path:
        for (double d = 0; d <= WALL_PATH + 1e-6; d += WALL_STEP) {
            for (double h : WALL_HEIGHTS) {
                Location o = feet.clone().add(dir.clone().multiply(d)).add(0, h, 0);
                // 앞이 막힌 곳 너머는 구르지 않는다
                if (!o.getBlock().isPassable() && o.getBlock().getBoundingBox().contains(o.toVector())) break path;
                freeL = Math.min(freeL, free(w, o, left));
                freeR = Math.min(freeR, free(w, o, left.clone().multiply(-1)));
            }
        }
        double keep = clip(fs, false, freeR, freeL), other = clip(fs, true, freeR, freeL);
        f.flip = other + 0.05 < keep;
        f.mirror = f.leftHanded ^ f.flip;
        double[] shift = new double[fs.size()];
        boolean any = false;
        for (int i = 0; i < fs.size(); i++) {
            float[] s = fs.get(i).side();
            double extR = f.mirror ? s[1] : -s[0], extL = f.mirror ? -s[0] : s[1];
            double over = Math.max(0, extR - freeR + 0.02) - Math.max(0, extL - freeL + 0.02);
            double cap = i <= 1 || i >= fs.size() - 2 ? EDGE_SHIFT : MAX_SHIFT;
            shift[i] = Math.max(-cap, Math.min(cap, over));
            any |= Math.abs(shift[i]) > 1e-3;
        }
        if (any) f.shift = shift;
        if (f.flip || any) {
            plugin.test(p, String.format(Locale.ROOT, "TUMBLE_WALL right=%.2f left=%.2f flip=%s shift=%.2f", freeR, freeL, f.flip,
                    any ? java.util.Arrays.stream(shift).map(Math::abs).max().orElse(0) : 0.0));
        }
    }

    /** 몸이 벽에 드는 가장 큰 몫 (블록): 표를 거울로 (mirror) 볼 때. */
    private static double clip(List<Frame> fs, boolean mirror, double freeR, double freeL) {
        double worst = 0;
        for (Frame fr : fs) {
            float[] s = fr.side();
            double extR = mirror ? s[1] : -s[0], extL = mirror ? -s[0] : s[1];
            worst = Math.max(worst, Math.max(0, extR - freeR) + Math.max(0, extL - freeL));
        }
        return worst;
    }

    /** o 에서 dir 쪽으로 막힌 곳까지의 거리 (WALL_REACH 까지, 지나갈 수 있는 블록은 보지 않는다). */
    private static double free(org.bukkit.World w, Location o, Vector dir) {
        org.bukkit.util.RayTraceResult r = w.rayTraceBlocks(o, dir, WALL_REACH, org.bukkit.FluidCollisionMode.NEVER, true);
        return r == null ? WALL_REACH : r.getHitPosition().distance(o.toVector());
    }

    /**
     * Ticker 에서 Roll 이 부른다 (틱 처음): hide-delay 틱에 몸을 감추고, 열쇠 자세를 그 틱에 보내고, 몸 높이(자세)가 바뀌면 이동을
     * 맞추고, reveal 틱에 거둔다.
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
            if (f.hideAt >= 0 && now >= f.hideAt) {
                // 생성 패킷이 나간 뒤 틱 간격의 반이 지나야 감추고 보이게 한다 (MAX_LATE). 시험 줄은 늦춘 틱에
                long gap = f.sentNanos == 0 ? 0 : System.nanoTime() - f.sentNanos;
                double half = 5e8 / Math.max(1f, Bukkit.getServerTickManager().getTickRate());
                if (gap >= half || now >= f.hideAt + MAX_LATE) hide(p, f);
                else plugin.test(p, String.format(Locale.ROOT, "TUMBLE_LATE gap=%.1fms t=%d", gap / 1e6, now));
            }
            if (t >= c.reveal()) {
                // 투명을 걷고 (깃발은 이 틱의 추적 단계에서 나간다) 대역을 곧바로 지운다. 틱 끝에 지우면 지우기 패킷이 다음 틱에야
                // 나가 일어서는 대역과 진짜 몸이 한 틱 겹쳐 보였다 [확인 (클라): 느린 화면]
                stop(p);
                continue;
            }
            boolean hands = f.faked.contains(EquipmentSlot.HAND) || f.faked.contains(EquipmentSlot.OFF_HAND);
            if (!f.handBack && c.handBack() > 0 && t >= c.handBack() && hands) {
                // 그 사람 화면에만 두 손을 돌려준다 (보는 사람은 reveal 까지 감춘 사본). 대역 손의 든 것은 그 사람 화면에서 감춘다
                // (F5 에서 진짜 손에 든 것과 둘로 보이지 않게)
                f.handBack = true;
                for (EquipmentSlot s : new EquipmentSlot[]{EquipmentSlot.HAND, EquipmentSlot.OFF_HAND}) {
                    if (f.faked.contains(s)) p.sendEquipmentChange(p, s, p.getEquipment().getItem(s));
                }
                for (ItemDisplay d : new ItemDisplay[]{f.own.mainItem, f.own.offItem}) {
                    if (d != null && d.isValid()) p.hideEntity(plugin, d);
                }
                f.ownHeldHidden = true;
            } else if (!f.handBack && hands && f.hideAt < 0 && !f.equipPending) {
                // 감춘 손 사본을 조금씩 바꿔 다시 보낸다: 바닐라 1인칭 손이 내려간 채 머물러 돌려줄 때 곧바로 올라온다 (HOLD_TAG)
                f.hold++;
                for (EquipmentSlot s : new EquipmentSlot[]{EquipmentSlot.HAND, EquipmentSlot.OFF_HAND}) {
                    if (!f.faked.contains(s)) continue;
                    ItemStack copy = hiddenCopy(p.getEquipment().getItem(s), s, f.hold);
                    if (copy != null) p.sendEquipmentChange(p, s, copy);
                }
            }
            // 자세가 바뀌면 (웅크리기) 탑승 자리가 바뀐다: 이동을 다시 맞춘다 (기어가기 막힘 아래의 own 벌은 기어가기 상자 그대로)
            double h = p.getHeight();
            boolean resized = Math.abs(h - f.attach) > 1e-3;
            f.attach = h;
            if (!f.crawl) f.ownAttach = h;
            boolean moved = false;
            List<Frame> fs = anim.frames();
            while (f.next < fs.size() && fs.get(f.next).tick() <= t) {
                Frame fr = fs.get(f.next);
                apply(p, f, f.next++, fr.dur(), -1);
                moved = true;
            }
            if (!moved && resized) apply(p, f, f.shown, 1, -1);
            if (!f.revealed && f.hideAt < 0 && t >= f.revealAt) {
                // 두 벌을 보이게 한다 (보기 거리: 클라이언트가 받자마자 그린다. 깃발과 같은 추적 단계)
                f.revealed = true;
                for (ItemDisplay d : f.parts()) if (d.isValid()) d.setViewRange(1f);
            }
            light(p, f);
        }
    }

    /**
     * 기어가기 막힘을 거두는 틱 (Roll 이 부른다, 틱 처음): own 벌을 서는 몸 상자 높이에 붙도록 지금 자세를 다시 보낸다 (1틱 보간).
     * 막힘은 Roll 이 이 틱 끝 (추적 단계 뒤) 에 거둔다: 클라이언트는 변환을 받은 같은 틱에 막힘이 걷혀 서므로, 탑승 자리가 1틱 동안
     * 기어가기 상자에서 서는 상자로 올라가는 것과 변환이 1틱 동안 그만큼 내려가는 것이 서로 지운다. 두 패킷이 클라이언트 틱 하나를
     * 사이에 두고 갈리면 (드물다) 그 1틱 동안 대역이 바닥으로 1.2 가라앉는다 (뜨는 것보다 덜 보인다).
     */
    public void unduck(Player p) {
        Fig f = live.get(p.getUniqueId());
        if (f == null || !f.crawl || anim == null) return;
        f.crawl = false;
        f.ownAttach = f.attach;
        sendRig(f, f.own, f.shown, 1f, (float) -f.ownAttach, 1);
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
            if (f.sentNanos == 0) f.sentNanos = System.nanoTime();
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
     * 시험 (/soulstest tumble): 대역을 at 에 세운다 (탑승하지 않는다). dir 쪽으로 구르는 frame 번째 열쇠 자세. own 이면 그 사람 화면의 벌
     * (표시 알파 그림, 픽셀 머리: 그 사람에게 1인칭 거리에서는 셰이더가 버린다), 아니면 남에게 보이는 벌 (바닐라 머리, 진짜 아이템).
     * ticks 뒤에 지운다. 그 사람의 색·머리·투구·든 것으로. 미리보기 (pack/preview/roll_figure.png) 와 견주어 본다.
     */
    public void pose(Player p, Location at, Vector dir, int frame, int ticks, boolean own) {
        if (anim == null) return;
        Fig f = new Fig();
        f.rollYaw = f.yaw = (float) Math.atan2(dir.getX(), dir.getZ());
        f.leftHanded = f.mirror = p.getMainHand() == MainHand.LEFT;
        f.colors = tint.body(p);
        f.helmColor = tint.helm(p);
        f.headColors = tint.head(p);
        Location l = at.clone();
        l.setYaw(0f);
        l.setPitch(0f);
        int i = Math.max(0, Math.min(frame, anim.frames().size() - 1));
        List<ItemDisplay> ds = new ArrayList<>();
        for (Part part : Part.values()) {
            if (part.model == null && part != Part.HEAD) continue;
            ds.add(display(p, l, bodyItem(p, part, f, own, 0), transform(i, part, f, 1f, 0), null, null));
        }
        if (f.helmColor != null) ds.add(display(p, l, helm(f.helmColor, own, 0), transform(i, Part.HEAD, f, 1f, 0), null, null));
        EntityEquipment eq = p.getEquipment();
        for (boolean main : new boolean[]{true, false}) {
            ItemStack it = held(main ? eq.getItemInMainHand() : eq.getItemInOffHand(), own);
            if (it == null) continue;
            ds.add(display(p, l, it, transform(i, handPart(f, main), f, 1f, 0), handContext(f, main), null));
        }
        Bukkit.getScheduler().runTaskLater(plugin, () -> ds.forEach(Entity::remove), ticks);
    }

    // ───────────────────────── 대역 ─────────────────────────

    private void spawn(Player p, Fig f) {
        // 탑승 자리 (몸 상자 꼭대기) 에 띄운다: 첫 그림부터 탑승한 자리와 같다. 변환도 만들 때 넣는다 (생성 패킷에 실려
        // 나간다. 만든 뒤에 바꾸면 클라이언트가 한 틱 동안 변환 없이 머리 위에 그렸다). own 벌은 그 사람 클라이언트의 탑승 자리
        // (기어가기면 기어가기 상자 꼭대기) 에 띄운다: 새 탑승물이 처음 그리는 틱에 생성 자리에서 탑승 자리로 미끄러지지 않게
        // 두 벌 모두 보기 거리 0 으로 (revealAt 틱에 보이게 한다: 클래스 머리말 "때")
        f.revealed = false;
        f.sentNanos = 0;
        f.sentCode.clear();
        fill(p, f, f.seen, at(p, f.attach), 0, 1f, (float) -f.attach, false);
        fill(p, f, f.own, at(p, f.ownAttach), 0, 1f, (float) -f.ownAttach, true);
        for (ItemDisplay d : f.parts()) p.addPassenger(d);
        // own 벌은 아무에게도 보이지 않게 만들었다: 그 사람에게만 보인다
        for (ItemDisplay d : f.own.all()) p.showEntity(plugin, d);
        light(p, f);
    }

    private static Location at(Player p, double attach) {
        Location at = p.getLocation().add(0, attach, 0);
        at.setYaw(0f);
        at.setPitch(0f);
        return at;
    }

    /** 한 벌을 띄운다. own 이면 아무에게도 보이지 않게 (그 사람에게는 spawn 이 보인다), 아니면 그 사람에게만 감춘다. */
    private void fill(Player p, Fig f, Rig r, Location at, int fr, float size, float down, boolean own) {
        for (Part part : Part.values()) {
            if (part.model == null && part != Part.HEAD) continue;
            r.body.put(part, display(p, at, bodyItem(p, part, f, own, 0), transform(fr, part, f, size, down), null, own));
        }
        if (f.helmColor != null) r.helm = display(p, at, helm(f.helmColor, own, 0), transform(fr, Part.HEAD, f, size, down), null, own);
        EntityEquipment eq = p.getEquipment();
        ItemStack main = held(eq.getItemInMainHand(), own), off = held(eq.getItemInOffHand(), own);
        if (main != null) {
            r.mainItem = display(p, at, main, transform(fr, handPart(f, true), f, size, down), handContext(f, true), own);
        }
        if (off != null) {
            r.offItem = display(p, at, off, transform(fr, handPart(f, false), f, size, down), handContext(f, false), own);
        }
    }

    /**
     * 대역이 손에 들 아이템 (없으면 null). seen: 진짜 아이템의 사본. own: souls 아이템이면 깃발 {@link #MARK_FLAG} 를 켠 사본 (팩이
     * 표시판으로 그린다: 1인칭에서 버린다), 그 밖 (바닐라 모형) 은 표시판이 없어 1인칭에서 보이므로 들지 않는다.
     */
    static ItemStack held(ItemStack real, boolean own) {
        if (real == null || real.isEmpty()) return null;
        if (!own) return real.clone();
        Key model = real.getData(DataComponentTypes.ITEM_MODEL);
        if (model == null || !Keys.NS.equals(model.namespace())) return null;
        return withFlag(real, MARK_FLAG);
    }

    /** 이어 구를 때: 색·투구를 다시 입힌다 (갑옷을 바꿨을 수 있다). 든 것은 그대로. */
    private void dress(Player p, Fig f) {
        f.headColors = tint.head(p);
        for (Rig r : List.of(f.own, f.seen)) {
            boolean own = r == f.own;
            for (Map.Entry<Part, ItemDisplay> e : r.body.entrySet()) {
                if (e.getValue().isValid() && (e.getKey().model != null || own)) {
                    e.getValue().setItemStack(bodyItem(p, e.getKey(), f, own, own ? f.sentCode.getOrDefault(e.getKey(), 0) : 0));
                }
            }
            if (r.helm != null && f.helmColor == null) {
                // 이어 구르기 전에 투구를 벗었다
                r.helm.leaveVehicle();
                r.helm.remove();
                r.helm = null;
            }
            if (r.helm != null && r.helm.isValid()) r.helm.setItemStack(helm(f.helmColor, own, own ? f.sentCode.getOrDefault(Part.HEAD, 0) : 0));
        }
    }

    /** own: 아무에게도 보이지 않게 만든다 (그 사람에게는 spawn 이 보인다). 아니면 그 사람에게만 감춘다. pose 는 null (모두에게). */
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
            // 보기 거리 0: 그려지지 않는다 (revealAt 틱에 1 로: 클래스 머리말 "때")
            d.setViewRange(0f);
            if (own) d.setVisibleByDefault(false);
            else p.hideEntity(plugin, d);
        });
    }

    /**
     * 몸 부위 아이템. seen: 머리는 그 사람 프로필의 player_head (souls:roll_head), 몸은 souls:roll_&lt;부위&gt;. own: 머리는 스킨 픽셀
     * 머리 souls:roll_headpx (색 384 개), 몸은 표시판 souls:roll_&lt;부위&gt;_m. own 의 물들이는 색에는 반지름 code 를 싣는다 ({@link #encode}.
     * 0 이면 낮은 비트를 비운다: 셰이더가 표시 알파 반지름으로 돌아간다).
     */
    private static ItemStack bodyItem(Player p, Part part, Fig f, boolean own, int code) {
        if (part == Part.HEAD && own) {
            ItemStack it = ItemStack.of(Material.FLINT);
            it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "roll_headpx"));
            if (f.headColors != null) it.setData(DataComponentTypes.CUSTOM_MODEL_DATA, CustomModelData.customModelData().addColors(encode(f.headColors, code)).build());
            return it;
        }
        if (part == Part.HEAD) {
            ItemStack it = ItemStack.of(Material.PLAYER_HEAD);
            it.setData(DataComponentTypes.PROFILE, ResolvableProfile.resolvableProfile(p.getPlayerProfile()));
            it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "roll_head"));
            return it;
        }
        ItemStack it = ItemStack.of(Material.FLINT);
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "roll_" + part.model + (own ? "_m" : "")));
        if (f.colors != null) {
            it.setData(DataComponentTypes.CUSTOM_MODEL_DATA, CustomModelData.customModelData().addColors(own ? encode(f.colors, code) : f.colors).build());
        }
        return it;
    }

    private static ItemStack helm(Color color, boolean own, int code) {
        ItemStack it = ItemStack.of(Material.FLINT);
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, own ? "roll_helm_m" : "roll_helm"));
        it.setData(DataComponentTypes.CUSTOM_MODEL_DATA, CustomModelData.customModelData().addColor(own ? encode(color, code) : color).build());
        return it;
    }

    /**
     * 반지름 code (0..63) 를 색의 낮은 비트에 싣는다: R 의 낮은 두 비트 = code 의 0·1 비트, G = 2·3, B = 4·5 (팩의 아이템 셰이더
     * rendertype_item_entity_translucent_cull.vsh 가 읽는다, pack/roll_figure.py "틱마다 부위마다의 반지름"). 색은 채널마다 3/255 안.
     */
    static Color encode(Color c, int code) {
        return Color.fromRGB((c.getRed() & ~3) | (code & 3), (c.getGreen() & ~3) | ((code >> 2) & 3), (c.getBlue() & ~3) | ((code >> 4) & 3));
    }

    static List<Color> encode(List<Color> cs, int code) {
        List<Color> out = new ArrayList<>(cs.size());
        for (Color c : cs) out.add(encode(c, code));
        return out;
    }

    /**
     * own 벌 부위마다 i 번째 자세의 반지름 code 를 보낸다 (바뀐 부위만: 아이템을 다시 보낸다. 투구는 머리와 같은 code). prev 가 0 이상이면
     * 그 자세에서 i 로 오는 보간 (이어 구르기) 도 덮는다.
     */
    private void sendCodes(Player p, Fig f, int i, int prev) {
        if (!f.codes) return;
        for (Map.Entry<Part, ItemDisplay> e : f.own.body.entrySet()) {
            Part part = e.getKey();
            int code = code(f, part, i, prev);
            if (code == 0 || f.sentCode.getOrDefault(part, 0) == code) continue;
            f.sentCode.put(part, code);
            if (e.getValue().isValid()) e.getValue().setItemStack(bodyItem(p, part, f, true, code));
            if (part == Part.HEAD && f.own.helm != null && f.own.helm.isValid() && f.helmColor != null) {
                f.own.helm.setItemStack(helm(f.helmColor, true, code));
            }
        }
    }

    /**
     * 부위 (그려지는 부위) 의 i 번째 자세 반지름 code: 표 (stand 또는 crawl) 의 반지름 + 여유 + 그 자세와 앞 자세에서 옆으로 옮긴 몫을
     * code 한 칸으로 올림 (CODE_MIN..CODE_MAX). 표가 없으면 0.
     */
    private int code(Fig f, Part part, int i, int prev) {
        List<Frame> fs = anim.frames();
        Part src = f.mirror ? part.mirror() : part;
        double r = radius(fs.get(i), f, src);
        if (r < 0) return 0;
        double sh = Math.abs(shiftAt(f, i));
        if (i > 0) sh = Math.max(sh, Math.abs(shiftAt(f, i - 1)));
        if (prev >= 0 && prev != i) {
            r = Math.max(r, radius(fs.get(prev), f, src));
            sh = Math.max(sh, Math.abs(shiftAt(f, prev)));
        }
        int c = (int) Math.ceil((r + anim.margin() + sh) / anim.codeStep() - 1e-9);
        return Math.max(CODE_MIN, Math.min(CODE_MAX, c));
    }

    private static double radius(Frame fr, Fig f, Part src) {
        float[] row = f.crawlTable ? fr.crawl() : fr.stand();
        return row == null ? -1 : row[src.ordinal()];
    }

    private static double shiftAt(Fig f, int i) {
        return f.shift == null ? 0 : f.shift[i];
    }

    /**
     * 든 것이 놓이는 손 (그려지는 부위, 그 사람 기준). 주손은 무기 든 팔 = 표의 오른팔이고, 왼손잡이는 거울로 그 팔이 왼쪽이 된다
     * ({@link #transform} 이 거울일 때 반대쪽 표를 읽으므로 왼손잡이의 주손은 HAND_L 자리에 표의 HAND_R 이 온다).
     */
    private static Part handPart(Fig f, boolean main) {
        return main != f.leftHanded ? Part.HAND_R : Part.HAND_L;
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
    private void apply(Player p, Fig f, int i, int duration, int prev) {
        Config.TumbleCfg c = cfg();
        Frame fr = anim.frames().get(i);
        f.shown = i;
        int reach = fr.tick() + fr.dur();
        float turn = c.riseTurn() <= 0 ? (reach > c.riseAt() ? 1f : 0f)
                : Math.max(0f, Math.min(1f, (reach - c.riseAt()) / (float) c.riseTurn()));
        float body = (float) Math.toRadians(-p.getBodyYaw());
        f.yaw = f.rollYaw + turn * wrap(body - f.rollYaw);
        sendCodes(p, f, i, prev);
        sendRig(f, f.own, i, 1f, (float) -f.ownAttach, duration);
        sendRig(f, f.seen, i, 1f, (float) -f.attach, duration);
    }

    private void sendRig(Fig f, Rig r, int fr, float size, float down, int duration) {
        for (Map.Entry<Part, ItemDisplay> e : r.body.entrySet()) send(e.getValue(), transform(fr, e.getKey(), f, size, down), duration);
        if (r.helm != null) send(r.helm, transform(fr, Part.HEAD, f, size, down), duration);
        if (r.mainItem != null) send(r.mainItem, transform(fr, handPart(f, true), f, size, down), duration);
        if (r.offItem != null) send(r.offItem, transform(fr, handPart(f, false), f, size, down), duration);
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
     * 표의 부위 자리 (대역 공간 D 픽셀) 와 방향을 변환으로: 이동 = Y(yaw) · 자리 × scale/16 + (0, down, 0), 왼쪽 회전 = Y(yaw) · 방향,
     * 크기 scale × size (size 0 이면 보이지 않는다: 두 벌을 띄울 때). 거울 (왼손잡이, 반대 어깨로 구르기) 은 표에서 반대쪽 부위를 X 를
     * 뒤집어 (x → -x, 사원수 (x, -y, -z, w)) 쓴다. 표의 이름이 그 사람 기준의 오른쪽·왼쪽이므로 그려지는 부위 part 에 대해 표의
     * part.mirror() 를 읽는다. 벽 곁이면 구르는 쪽 기준 옆으로 f.shift[i] 만큼 더 옮긴다.
     */
    private Transformation transform(int i, Part part, Fig f, float size, float down) {
        Frame fr = anim.frames().get(i);
        float[] v = fr.parts()[(f.mirror ? part.mirror() : part).ordinal()];
        float m = f.mirror ? -1f : 1f;
        float k = anim.scale() / 16f;
        Quaternionf qy = new Quaternionf().rotationY(f.yaw);
        Vector3f pos = qy.transform(new Vector3f(m * v[0] * k, v[1] * k, v[2] * k)).mul(size).add(0f, down, 0f);
        if (f.shift != null) pos.add(new Quaternionf().rotationY(f.rollYaw).transform(new Vector3f((float) f.shift[i] * size, 0f, 0f)));
        Quaternionf rot = new Quaternionf(qy).mul(new Quaternionf(v[3], m * v[4], m * v[5], v[6]));
        return new Transformation(pos, rot, new Vector3f(anim.scale() * size), new Quaternionf());
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
            List<?> stand = y.getList("radius.stand"), crawl = y.getList("radius.crawl"), side = y.getList("side");
            for (Map<?, ?> m : y.getMapList("frames")) {
                List<?> rows = (List<?>) m.get("p");
                if (rows == null || rows.size() != slot.length) throw new IllegalStateException("bad frame rows");
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
                int n = frames.size();
                frames.add(new Frame(((Number) m.get("tick")).intValue(), ((Number) m.get("dur")).intValue(), parts,
                        row(stand, n, slot), row(crawl, n, slot), side == null || n >= side.size() ? null : floats(side.get(n), 2)));
            }
            if (frames.isEmpty()) throw new IllegalStateException("no frames");
            boolean radius = frames.stream().allMatch(fr -> fr.stand() != null && fr.crawl() != null);
            boolean sides = frames.stream().allMatch(fr -> fr.side() != null);
            if (!radius || !sides) {
                plugin.getLogger().warning("roll_anim.yml 에 " + (radius ? "" : "1인칭 반지름 표 ") + (sides ? "" : "옆 끝 표 ")
                        + "가 없거나 틀려 그것 없이 구릅니다 (팩의 표시 알파 반지름, 벽 곁 그대로)");
                List<Frame> plain = new ArrayList<>();
                for (Frame fr : frames) {
                    plain.add(new Frame(fr.tick(), fr.dur(), fr.parts(), radius ? fr.stand() : null, radius ? fr.crawl() : null,
                            sides ? fr.side() : null));
                }
                frames = plain;
            }
            return new Anim((float) y.getDouble("scale", 0.9375), List.copyOf(frames), radius ? y.getInt("radius.duck", -1) : -1,
                    y.getDouble("radius.code-step", 0.05), y.getDouble("radius.margin", 0.1));
        } catch (Exception e) {
            plugin.getLogger().warning("roll_anim.yml 을 읽지 못해 구르기 대역 없이 구릅니다: " + e);
            return null;
        }
    }

    /** 표의 n 번째 줄 (부위마다 반지름, parts 차례) → Part 차례. 없거나 틀리면 null. */
    private static float[] row(List<?> rows, int n, int[] slot) {
        if (rows == null || n >= rows.size()) return null;
        float[] v = floats(rows.get(n), slot.length);
        if (v == null) return null;
        float[] out = new float[Part.values().length];
        for (int i = 0; i < slot.length; i++) out[slot[i]] = v[i];
        return out;
    }

    private static float[] floats(Object o, int len) {
        if (!(o instanceof List<?> l) || l.size() != len) return null;
        float[] v = new float[len];
        for (int i = 0; i < len; i++) {
            if (!(l.get(i) instanceof Number x)) return null;
            v[i] = x.floatValue();
        }
        return v;
    }

    // ───────────────────────── 진짜 몸 감추기 ─────────────────────────

    private void hideEquipment(Player p, Fig f) {
        EntityEquipment eq = p.getEquipment();
        Map<EquipmentSlot, ItemStack> fake = new EnumMap<>(EquipmentSlot.class);
        for (EquipmentSlot s : SLOTS) {
            ItemStack real = eq.getItem(s);
            if (real.isEmpty()) continue;
            fake.put(s, hiddenCopy(real, s, 0));
            f.faked.add(s);
        }
        if (fake.isEmpty()) return;
        p.sendEquipmentChange(p, fake);
        for (Player v : p.getTrackedBy()) v.sendEquipmentChange(p, fake);
    }

    /**
     * 손에 든 souls 아이템: 깃발을 켠 사본 (팩이 1·3인칭 손에서 비운다, 단축 슬롯 그림과 이름은 그대로). hold 가 0 이 아니면
     * custom_model_data 글 {@link #HOLD_TAG}hold 를 더한다 (그 사람 화면에 틱마다 다른 사본: 1인칭 손이 내려간 채 머문다).
     * 그 밖 (바닐라 모형의 아이템, 갑옷 칸): 공기 (null).
     */
    static ItemStack hiddenCopy(ItemStack real, EquipmentSlot slot, int hold) {
        if (slot != EquipmentSlot.HAND && slot != EquipmentSlot.OFF_HAND) return null;
        Key model = real.getData(DataComponentTypes.ITEM_MODEL);
        if (model == null || !Keys.NS.equals(model.namespace())) return null;
        return withFlag(real, HIDE_FLAG, hold == 0 ? null : HOLD_TAG + hold);
    }

    /** custom_model_data 깃발 flag 를 켠 사본 (다른 값은 그대로). */
    static ItemStack withFlag(ItemStack real, int flag) {
        return withFlag(real, flag, null);
    }

    /** custom_model_data 깃발 flag 를 켜고 글 tag 를 더한 사본 (다른 값은 그대로, tag 가 null 이면 글은 그대로). */
    static ItemStack withFlag(ItemStack real, int flag, String tag) {
        ItemStack copy = real.clone();
        CustomModelData old = real.getData(DataComponentTypes.CUSTOM_MODEL_DATA);
        List<Boolean> flags = new ArrayList<>(old == null ? List.of() : old.flags());
        while (flags.size() <= flag) flags.add(false);
        flags.set(flag, true);
        CustomModelData.Builder b = CustomModelData.customModelData().addFlags(flags);
        if (old != null) b.addFloats(old.floats()).addStrings(old.strings()).addColors(old.colors());
        if (tag != null) b.addString(tag);
        copy.setData(DataComponentTypes.CUSTOM_MODEL_DATA, b.build());
        return copy;
    }
}
