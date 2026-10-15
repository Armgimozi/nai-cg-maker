package kr.labyrinth.items;

import java.util.EnumMap;
import java.util.Locale;
import java.util.Map;

/**
 * 어깨·등 3D 장식 배치 — 순수 계산 (Bukkit 없음, 단위 테스트 대상). {@link ArmorCosmetics} 와 리소스팩 미리보기
 * ({@code resourcepack/src/armor_pieces.py}) 가 이 표 하나만 믿는다.
 * <p>
 * <b>좌표계</b> = 착용자 몸 기준 디스플레이 로컬 좌표 (ItemDisplay 의 yaw = 플레이어 몸 yaw — {@link BodyYaw} 로 직접 계산, 블록 단위):
 * 원점 = 탑승 좌석 = 플레이어 위치 + (0, 자세 높이, 0) — 서 있을 때 1.8, 웅크릴 때 1.5 (26.3 Avatar 치수, 클라이언트도
 * 같은 값으로 탑승물을 붙인다). +X = 착용자 왼쪽, +Y = 위, +Z = 앞.
 * <p>
 * <b>모델 계약</b>: 부위 모델은 피벗 (8,8,8) = 부위 기준점, 모델 1단위 = 플레이어 스킨 1px 로 만든다
 * (ItemDisplay 가 모델을 Y축 180° 돌려 그리므로 모델 −Z = 착용자 앞, 모델 −X = 착용자 왼쪽 — ARCHITECTURE §2).
 * Java 는 Transformation(translation = 기준점, left rotation = X축 앞숙임, scale = {@link #PIXEL} × 몸 배율) 만 준다.
 * <ul>
 *   <li>어깨: 기준점 = 팔 회전축 높이(스킨 y 22px)의 팔 중심(x ±6px). 웅크리면 팔처럼 0.4 rad 뒤로 젖힌다.</li>
 *   <li>등: 기준점 = 몸통 위 가운데(목, y 24px). 웅크리면 몸통처럼 0.5 rad 앞으로 숙인다(지오메트리는 피벗 뒤 2px 부터).</li>
 *   <li>웅크리기 = HumanoidModel 값 (몸·팔 피벗 3.2px 내려감 + 렌더 오프셋 −2/16 블록, 몸 xRot 0.5, 팔 xRot +0.4).</li>
 * </ul>
 */
public final class ArmorPieceLayout {

    private ArmorPieceLayout() {}

    /** 모델 1단위 = 스킨 1px 가 되게 하는 배율 (플레이어 모델은 0.9375 배로 그려진다). */
    public static final float PIXEL = 0.9375f;
    /** 스킨 1px 의 월드 크기(블록) = 0.9375 / 16. */
    public static final double PX = PIXEL / 16.0;
    /** 탑승 좌석 높이 (블록) — 서기 / 웅크리기. */
    public static final double SEAT_STAND = 1.8;
    public static final double SEAT_SNEAK = 1.5;
    /** 웅크리기 때 몸통·팔이 내려가는 양 (스킨 px) + 렌더 오프셋 (블록). */
    public static final double CROUCH_DROP_PX = 3.2;
    public static final double CROUCH_RENDER_OFFSET = -2.0 / 16.0;
    /** 웅크리기 앞숙임 (rad): 몸통 0.5, 팔 0.4 (HumanoidModel). */
    public static final float CROUCH_BODY_PITCH = 0.5f;
    public static final float CROUCH_ARM_PITCH = 0.4f;
    /** 자세가 바뀔 때 Transformation 보간 틱. */
    public static final int STANCE_INTERPOLATION = 3;

    /** 장식 부위. id = 아이템 모델 경로 끝 (labyrinth:armor_piece/&lt;세트&gt;/&lt;id&gt;). */
    public enum Part {
        SHOULDER_L("shoulder_l"), SHOULDER_R("shoulder_r"), BACK("back");

        private final String id;

        Part(String id) { this.id = id; }

        public String id() { return id; }
    }

    /** STAND/SNEAK = 보임, HIDDEN = 디스플레이는 두고 크기 0 (헤엄·활공·잠·탈것·투명), NONE = 디스플레이 제거 (사망·관전). */
    public enum Stance { STAND, SNEAK, HIDDEN, NONE }

    /** 디스플레이 Transformation 한 벌: translation (x, y, z) 블록 · X축 회전 pitch (rad) · 균일 배율. */
    public record Placement(float x, float y, float z, float pitch, float scale) {
        public boolean visible() { return scale > 0f; }
    }

    /**
     * 몸 상태 (Bukkit 에서 읽은 값). crouching = Pose.CROUCHING, otherPose = 서기·웅크리기가 아닌 자세
     * (SWIMMING·FALL_FLYING·SPIN_ATTACK·SLEEPING·DYING …).
     */
    public record BodyState(boolean dead, boolean spectator, boolean invisible, boolean inVehicle, boolean sleeping,
                            boolean gliding, boolean swimming, boolean riptide, boolean crouching, boolean otherPose) {
        public static final BodyState STANDING = new BodyState(false, false, false, false, false, false, false, false, false, false);
    }

    private record Row(Part part, Stance stance, float x, float y, float z, float pitch) {}

    private static Row row(Part part, Stance stance, float x, float y, float z, float pitch) {
        return new Row(part, stance, x, y, z, pitch);
    }

    // @layout-table — resourcepack/src/armor_pieces.py 가 이 줄들을 정규식으로 그대로 읽는다 (row(...) 형식 유지).
    //   x·y·z = 좌석 기준 블록, pitch = rad. 값의 유도: 어깨 y = 22px·PX − 좌석, 등 y = 24px·PX − 좌석,
    //   웅크리기 = (같은 px − 3.2px)·PX − 2/16 − 1.5 (ArmorPieceLayoutTest 가 이 유도와 표가 같은지 확인).
    private static final Row[] TABLE = {
            row(Part.SHOULDER_L, Stance.STAND, 0.3515625f, -0.5109375f, 0f, 0f),
            row(Part.SHOULDER_R, Stance.STAND, -0.3515625f, -0.5109375f, 0f, 0f),
            row(Part.BACK, Stance.STAND, 0f, -0.39375f, 0f, 0f),
            row(Part.SHOULDER_L, Stance.SNEAK, 0.3515625f, -0.5234375f, 0f, 0.4f),
            row(Part.SHOULDER_R, Stance.SNEAK, -0.3515625f, -0.5234375f, 0f, 0.4f),
            row(Part.BACK, Stance.SNEAK, 0f, -0.40625f, 0f, 0.5f),
    };
    // @layout-end

    private static final Map<Part, Map<Stance, Row>> BY_PART = new EnumMap<>(Part.class);

    static {
        for (Row r : TABLE) BY_PART.computeIfAbsent(r.part(), k -> new EnumMap<>(Stance.class)).put(r.stance(), r);
    }

    /** 몸 상태 → 자세. 사망·관전은 NONE(제거), 투명·탈것·잠·활공·헤엄·급류 돌진·그 밖의 누운 자세는 HIDDEN. */
    public static Stance stance(BodyState s) {
        if (s == null) return Stance.NONE;
        if (s.dead() || s.spectator()) return Stance.NONE;
        if (s.invisible() || s.inVehicle() || s.sleeping() || s.gliding() || s.swimming() || s.riptide() || s.otherPose()) {
            return Stance.HIDDEN;
        }
        return s.crouching() ? Stance.SNEAK : Stance.STAND;
    }

    /**
     * 부위·자세 → Transformation 값. bodyScale = 플레이어 SCALE 속성 (보통 1 — 좌석 높이도 같은 배율로 커진다).
     * HIDDEN·NONE = 서 있을 때 자리에 배율 0.
     */
    public static Placement place(Part part, Stance stance, double bodyScale) {
        double k = bodyScale > 0 && Double.isFinite(bodyScale) ? bodyScale : 1.0;
        Stance key = stance == Stance.SNEAK ? Stance.SNEAK : Stance.STAND;
        Row r = BY_PART.get(part).get(key);
        boolean shown = stance == Stance.STAND || stance == Stance.SNEAK;
        return new Placement((float) (r.x() * k), (float) (r.y() * k), (float) (r.z() * k), shown ? r.pitch() : 0f,
                shown ? (float) (PIXEL * k) : 0f);
    }

    /** 아이템 모델 경로 (네임스페이스 labyrinth 뒤): armor_piece/&lt;세트&gt;/&lt;부위&gt;. */
    public static String modelPath(String set, Part part) {
        return "armor_piece/" + set.toLowerCase(Locale.ROOT) + "/" + part.id();
    }

    /** 두 yaw(도)의 차이 −180..180 (감김 포함). */
    public static float yawDelta(float from, float to) {
        float d = (to - from) % 360f;
        if (d > 180f) d -= 360f;
        if (d < -180f) d += 360f;
        return d;
    }

    /** 몸 yaw 를 다시 보낼 만큼 바뀌었나 (패킷 각도 단위 360/256 ≈ 1.4° 보다 작은 흔들림은 무시). */
    public static boolean yawChanged(float sent, float now) {
        return Math.abs(yawDelta(sent, now)) >= 0.7f;
    }

    /**
     * 몸 yaw (도) — 다른 사람의 클라이언트가 이 플레이어의 몸통을 돌리는 계산을 그대로 따라 한다
     * (26.3 {@code LivingEntity.tick} 의 이동 방향 → {@code tickHeadTurn}). 서버의 {@code Player#getBodyYaw} 는 쓰지 않는다:
     * Paper 26.3 은 {@code ServerGamePacketListenerImpl.tickPlayer} 가 {@code doTick} 바로 전에 xo/zo 를 현재 위치로 맞추므로
     * 서버에서는 이동량이 늘 0 → 몸이 이동 방향을 안 따라가고 머리 ±50° 제한과 팔 휘두르기에만 반응한다
     * (머리를 돌린 채 걷거나 옆걸음하면 장식이 몸통보다 최대 50° 틀어졌다).
     * <p>
     * 매 틱 한 번 {@link #tick} (플레이어 위치 x·z, 보는 방향 yaw, 막는 중인가). 팔을 휘두르면 {@link #swing}.
     * <ol>
     *   <li>지난 틱 위치와의 dx·dz 가 0.05블록/틱보다 크면 목표 = 이동 방향 (뒷걸음이면 반대 방향 — 몸은 앞을 본다), 아니면 지금 몸.</li>
     *   <li>팔을 휘두르는 중({@value #SWING_TICKS}틱)이면 목표 = 보는 방향.</li>
     *   <li>몸 += (목표 − 몸) × 0.3.</li>
     *   <li>보는 방향과 몸 차이가 50°(막는 중 15°)를 넘으면 그만큼만 남기고 몸을 끌어온다.</li>
     *   <li>한 틱에 4블록 넘게 움직이면(순간이동) 몸 = 보는 방향.</li>
     * </ol>
     */
    public static final class BodyYaw {
        /** LivingEntity.tick 의 이동 판정 (0.05블록/틱)². */
        public static final float MIN_MOVE_SQ = 0.0025000002f;
        /** 이보다 멀리 한 틱에 움직이면 순간이동으로 보고 몸 = 보는 방향 (4블록)². */
        public static final double TELEPORT_SQ = 16.0;
        public static final float MAX_HEAD = 50f;
        public static final float MAX_HEAD_BLOCKING = 15f;
        /** 팔 휘두르기 = 6틱 (바닐라 기본 휘두르기 길이). */
        public static final int SWING_TICKS = 6;
        private static final float TURN = 0.3f;

        private float body;
        private double lastX;
        private double lastZ;
        private boolean hasLast;
        private int swing;

        public BodyYaw(float initial) { this.body = wrap(initial); }

        public float body() { return body; }

        /** 팔 휘두르기 시작 (PlayerArmSwingEvent — 주손·보조손) — 다음 {@value #SWING_TICKS}틱 동안 몸이 보는 방향을 따라간다. */
        public void swing() { swing = SWING_TICKS; }

        /** 한 틱 진행 → 새 몸 yaw (−180..180). */
        public float tick(double x, double z, float yaw, boolean blocking) {
            float target = body;
            if (hasLast) {
                double dx = x - lastX;
                double dz = z - lastZ;
                double d2 = dx * dx + dz * dz;
                if (d2 > TELEPORT_SQ || !Double.isFinite(d2)) {
                    lastX = x;
                    lastZ = z;
                    swing = 0;
                    body = wrap(yaw);
                    return body;
                }
                if ((float) d2 > MIN_MOVE_SQ) {
                    float move = (float) Math.toDegrees(Math.atan2(dz, dx)) - 90f;
                    float off = Math.abs(wrap(yaw) - move);
                    target = 95f < off && off < 265f ? move - 180f : move;
                }
            }
            lastX = x;
            lastZ = z;
            hasLast = true;
            if (swing > 0) {
                swing--;
                target = yaw;
            }
            body += wrap(target - body) * TURN;
            float d = wrap(yaw - body);
            float max = blocking ? MAX_HEAD_BLOCKING : MAX_HEAD;
            if (Math.abs(d) > max) body += d - Math.signum(d) * max;
            body = wrap(body);
            return body;
        }

        /** Mth.wrapDegrees: −180..180. */
        static float wrap(float deg) {
            float d = deg % 360f;
            if (d >= 180f) d -= 360f;
            if (d < -180f) d += 360f;
            return d;
        }
    }

    /** "/미궁 장식 켜기|끄기" 인자 → true/false, 모르는 값이면 null. */
    public static Boolean parseToggle(String arg) {
        if (arg == null) return null;
        return switch (arg.trim().toLowerCase(Locale.ROOT)) {
            case "켜기", "켬", "on", "true", "show" -> Boolean.TRUE;
            case "끄기", "끔", "off", "false", "hide" -> Boolean.FALSE;
            default -> null;
        };
    }

    /** PlayerData ext 값 → 장식 켜짐 여부 (없으면 켜짐). */
    public static boolean enabledFor(Object extValue) {
        if (extValue instanceof Boolean b) return b;
        if (extValue instanceof String s) return !"false".equalsIgnoreCase(s.trim()) && !"off".equalsIgnoreCase(s.trim());
        return true;
    }

    /** PlayerData ext 값 → 내 화면에도 내 장식을 보일까 (없으면 꺼짐 — 1인칭 화면 가장자리에 걸리지 않게). */
    public static boolean selfViewFor(Object extValue) {
        if (extValue instanceof Boolean b) return b;
        if (extValue instanceof String s) return "true".equalsIgnoreCase(s.trim()) || "on".equalsIgnoreCase(s.trim());
        return false;
    }
}
