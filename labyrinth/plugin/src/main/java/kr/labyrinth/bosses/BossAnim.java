package kr.labyrinth.bosses;

import kr.labyrinth.content.ModelDef;
import kr.labyrinth.mobs.RigMath;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 보스 시전 애니메이션 (ModelRig 의 기본 anim 위에 덧입히는 오버레이). Bukkit 무관.
 * <p>
 * 몹 로컬 좌표(GDD §14.6): +Z = 앞, +Y = 위, +X = 몹의 왼쪽. 팔은 피벗에서 아래로 매달려 있으므로
 * rotateX(음수) = 팔을 앞·위로 들기, rotateZ(+) = 왼팔을 바깥(+X)으로 벌리기. 몸 전체(global) 회전은 발 위치 기준.
 * 진행도 p = 0~1 (애니메이션 길이 대비), windup 비율 w 까지 "준비", 이후 "타격".
 */
public enum BossAnim {
    /** 없음. */
    NONE,
    /** 두 팔 머리 위로 → 내려찍기 (원형 장판·진동). */
    SLAM,
    /** 오른팔 가로 휩쓸기 (부채꼴). */
    SWEEP,
    /** 앞으로 숙이고 팔 뒤로 (돌진). */
    CHARGE,
    /** 고개 젖히고 팔 벌려 포효 (페이즈 전환·소환). */
    ROAR,
    /** 오른팔 뒤로 젖혔다 던지기 (투사체). */
    THROW,
    /** 두 팔 앞으로 들고 기 모으기 (표식·시스템 기믹). */
    CAST,
    /** 몸을 숙여 무언가를 쏟기 (쇳물·독). */
    POUR,
    /** 펄쩍 뛰어올라 사라짐 (천장 매복). */
    LEAP,
    /** 위에서 떨어져 착지. */
    DROP,
    /** 제자리 회전 (소용돌이·휩쓸기). */
    SPIN,
    /** 기절: 축 늘어져 비틀거림. */
    STUN,
    /** 사망: 무너지며 가라앉음. */
    DEATH;

    /** 오버레이 결과: 파트 로컬 이동·회전·크기, 몸 전체(global) 이동·회전. */
    public static final class Pose {
        public final Vector3f offset = new Vector3f();
        public final Quaternionf rotation = new Quaternionf();
        public float scale = 1f;
        public final Vector3f globalOffset = new Vector3f();
        public final Quaternionf globalRotation = new Quaternionf();
        /** 기본 걷기·숨쉬기 anim 을 줄이는 정도 0~1 (시전 중엔 팔 흔들기 대신 시전 자세). */
        public float baseWeight = 1f;
    }

    private static float rad(double deg) { return (float) Math.toRadians(deg); }

    private static double ease(double x) {
        x = Math.max(0, Math.min(1, x));
        return x * x * (3 - 2 * x);
    }

    /** 준비 구간 0→1, 타격 구간 1→0 처럼 쓰는 두 단계 곡선. */
    private static double windup(double p, double w) { return p < w ? ease(p / w) : 1.0; }

    private static double strike(double p, double w) { return p < w ? 0.0 : ease((p - w) / Math.max(1e-6, 1 - w) * 2.5); }

    /**
     * 오버레이 계산.
     * @param anim     현재 시전 애니메이션
     * @param partAnim 파트의 YAML anim 키 (body/head/arm_left/arm_right/legs_walk/…)
     * @param part     파트 이름 (hammer·blade 처럼 팔에 쥔 파트는 팔과 같은 anim 키라 자동으로 따라온다)
     * @param p        진행도 0~1
     * @param w        windup 비율 (0~1, 보통 0.6~0.8)
     * @param tick     전역 틱 (흔들림용)
     */
    public static Pose overlay(BossAnim anim, String partAnim, String part, double p, double w, long tick, Pose out) {
        Pose o = out == null ? new Pose() : out;
        o.offset.set(0, 0, 0);
        o.rotation.identity();
        o.scale = 1f;
        o.globalOffset.set(0, 0, 0);
        o.globalRotation.identity();
        o.baseWeight = 1f;
        if (anim == null || anim == NONE) return o;
        String a = partAnim == null ? "static" : partAnim;
        boolean armL = a.equals("arm_left");
        boolean armR = a.equals("arm_right");
        boolean head = a.equals("head");
        double wu = windup(p, w), st = strike(p, w);
        switch (anim) {
            case SLAM -> {
                o.baseWeight = 0.2f;
                double lift = -165 * wu + 150 * st;           // 머리 위로 → 앞으로 내려찍기
                if (armL || armR) o.rotation.rotateX(rad(lift)).rotateZ(rad((armL ? 1 : -1) * 12 * wu * (1 - st)));
                o.globalRotation.rotateX(rad(-8 * wu * (1 - st) + 14 * st));
                o.globalOffset.y = (float) (0.12 * wu * (1 - st) - 0.1 * st);
                if (head) o.rotation.rotateX(rad(-18 * wu + 28 * st));
            }
            case SWEEP -> {
                o.baseWeight = 0.3f;
                if (armR) o.rotation.rotateY(rad(70 * wu - 150 * st)).rotateX(rad(-95 * Math.max(wu, 0.6)));
                if (armL) o.rotation.rotateX(rad(-25 * wu));
                o.globalRotation.rotateY(rad(25 * wu - 55 * st));
            }
            case CHARGE -> {
                o.baseWeight = 0.5f;
                o.globalRotation.rotateX(rad(16 * wu));
                if (armL || armR) o.rotation.rotateX(rad(45 * wu)).rotateZ(rad((armL ? 1 : -1) * 15 * wu));
                if (head) o.rotation.rotateX(rad(-20 * wu));
            }
            case ROAR -> {
                o.baseWeight = 0.15f;
                double k = Math.sin(Math.PI * Math.min(1, p * 1.15));
                if (armL || armR) o.rotation.rotateZ(rad((armL ? 1 : -1) * 75 * k)).rotateX(rad(-30 * k));
                if (head) o.rotation.rotateX(rad(-35 * k)).rotateZ(rad(4 * Math.sin(tick * 1.7) * k));
                o.globalRotation.rotateX(rad(-10 * k));
                o.globalOffset.y = (float) (0.08 * k);
            }
            case THROW -> {
                o.baseWeight = 0.3f;
                if (armR) o.rotation.rotateX(rad(70 * wu - 200 * st));
                if (armL) o.rotation.rotateX(rad(-40 * wu)).rotateZ(rad(25 * wu));
                o.globalRotation.rotateY(rad(-20 * wu + 35 * st)).rotateX(rad(-6 * wu + 10 * st));
            }
            case CAST -> {
                o.baseWeight = 0.2f;
                double hold = Math.min(1, p / Math.max(0.05, w * 0.5));
                double pulse = 0.06 * Math.sin(tick * 0.6);
                if (armL || armR) o.rotation.rotateX(rad(-100 * ease(hold))).rotateZ(rad((armL ? 1 : -1) * (20 + 8 * Math.sin(tick * 0.4))));
                if (head) o.rotation.rotateX(rad(-12 * ease(hold)));
                o.globalOffset.y = (float) ((0.15 + pulse) * ease(hold) * (1 - st));
                o.scale = (float) (1 + 0.04 * ease(hold) * (1 - st));
            }
            case POUR -> {
                o.baseWeight = 0.25f;
                if (armL || armR) o.rotation.rotateX(rad(-80 * wu - 20 * st));
                o.globalRotation.rotateX(rad(22 * wu));
                if (head) o.rotation.rotateX(rad(18 * wu));
            }
            case LEAP -> {
                o.baseWeight = 0.2f;
                double crouch = p < 0.3 ? ease(p / 0.3) : 1 - ease((p - 0.3) / 0.2);
                double up = p < 0.3 ? 0 : ease((p - 0.3) / 0.7);
                o.globalOffset.y = (float) (-0.25 * crouch + 9 * up * up);
                if (armL || armR) o.rotation.rotateX(rad(60 * crouch - 150 * up));
                o.globalRotation.rotateX(rad(18 * crouch));
            }
            case DROP -> {
                o.baseWeight = 0.2f;
                double fall = 1 - ease(Math.min(1, p / 0.35));
                double squash = p < 0.35 ? 0 : Math.sin(Math.PI * Math.min(1, (p - 0.35) / 0.4));
                o.globalOffset.y = (float) (8 * fall * fall - 0.2 * squash);
                if (armL || armR) o.rotation.rotateX(rad(-140 * fall + 40 * squash)).rotateZ(rad((armL ? 1 : -1) * 40 * squash));
                o.globalRotation.rotateX(rad(12 * squash));
            }
            case SPIN -> {
                o.baseWeight = 0.4f;
                double turns = 2.0;
                o.globalRotation.rotateY(rad(360 * turns * ease(p)));
                if (armL || armR) o.rotation.rotateZ(rad((armL ? 1 : -1) * 80 * Math.sin(Math.PI * p))).rotateX(rad(-30 * Math.sin(Math.PI * p)));
            }
            case STUN -> {
                o.baseWeight = 0.1f;
                double sway = Math.sin(tick * 0.25);
                o.globalRotation.rotateX(rad(12)).rotateZ(rad(5 * sway));
                o.globalOffset.y = -0.12f;
                if (armL || armR) o.rotation.rotateX(rad(12)).rotateZ(rad((armL ? 1 : -1) * (6 + 4 * sway)));
                if (head) o.rotation.rotateX(rad(28)).rotateZ(rad(10 * sway));
            }
            case DEATH -> {
                o.baseWeight = 0f;
                double k = ease(p);
                o.globalRotation.rotateX(rad(20 * k)).rotateZ(rad(28 * k));
                o.globalOffset.y = (float) (-1.1 * k * k);
                if (armL || armR) o.rotation.rotateX(rad(25 * k)).rotateZ(rad((armL ? 1 : -1) * 35 * k));
                if (head) o.rotation.rotateX(rad(40 * k));
                o.scale = (float) Math.max(0.05, 1 - 0.7 * Math.max(0, (p - 0.5) * 2));
            }
            default -> { }
        }
        return o;
    }

    /**
     * 리그({@link RigMath.Skeleton#solve})에 끼울 오버레이: 파트 로컬 회전·이동·baseWeight 는 사슬·머리 무리 붙이기 전에,
     * 몸 전체 회전·이동·크기는 마지막에 (발 위치 기준 — 크기는 파트 위치까지 함께 줄어 한 덩어리로). NONE = null.
     */
    public static RigMath.Overlay rig(BossAnim anim, double p, double w, long tick) {
        if (anim == null || anim == NONE) return null;
        Pose scratch = new Pose();
        Pose whole = overlay(anim, "static", "", p, w, tick, new Pose());
        return new RigMath.Overlay() {
            @Override
            public float local(ModelDef.Part part, Quaternionf rot, Vector3f off) {
                Pose o = overlay(anim, part.anim(), part.name(), p, w, tick, scratch);
                rot.set(o.rotation);
                off.set(o.offset);
                return o.baseWeight;
            }

            @Override
            public float global(Quaternionf rot, Vector3f off) {
                rot.set(whole.globalRotation);
                off.set(whole.globalOffset);
                return whole.scale;
            }

            @Override
            public float baseWeight() {
                return whole.baseWeight;
            }
        };
    }

    /** 이 애니메이션의 기본 windup 비율. */
    public double defaultWindup() {
        return switch (this) {
            case SLAM, SWEEP, THROW -> 0.75;
            case POUR, CAST -> 0.8;
            case CHARGE -> 0.9;
            default -> 0.5;
        };
    }
}
