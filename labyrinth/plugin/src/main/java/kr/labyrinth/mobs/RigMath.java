package kr.labyrinth.mobs;

import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 모델 리그 절차적 애니메이션 수학 (GDD §14.3 anim 표 + §14.6 좌표 규칙). Bukkit 무관 — 단위 테스트 대상.
 * <p>
 * 몹 로컬 좌표: +Z = 앞, +Y = 위, +X = 몹의 왼쪽. 파트 피벗(블록, scale 1 기준)은 모델 중심(8,8,8)에 대응하고,
 * {@link #compose} 가 몹 yaw·scale 을 곱해 Display Transformation(앵커 = 몹 발 위치 기준)을 만든다.
 */
public final class RigMath {

    private RigMath() {}

    /** 애니메이션 입력 (틱 단위). -1 = 해당 없음. */
    public record AnimState(long tick, double moveSpeed, int attackTicks, int attackArm, int castTicks, int hurtTicks,
                            float headYaw, float headPitch, int deathTicks, boolean hasTarget, long seed) {}

    /** 파트 하나의 로컬 자세: 피벗 기준 이동(블록, scale 1), 회전, 크기 배율. */
    public record Pose(Vector3f offset, Quaternionf rotation, float scale) {
        public static Pose identity() { return new Pose(new Vector3f(), new Quaternionf(), 1f); }
    }

    public static final int ATTACK_TICKS = 6;   // 내려치기 0.3초
    public static final int DEATH_TICKS = 12;   // 사망 0.6초
    public static final int HURT_TICKS = 4;

    private static float rad(double deg) { return (float) Math.toRadians(deg); }

    private static double wave(long tick, double periodTicks, double phase) {
        return Math.sin(2 * Math.PI * (tick / periodTicks) + phase);
    }

    /** 걷기 비율 0~1 (블록/틱 → 0.18 이상이면 최대). */
    static double walkFactor(double speed) {
        return Math.max(0, Math.min(1, speed / 0.18));
    }

    /** 공격 팔 각도(도): 0~30% 들어 올림 0 → −110, 30~100% 내려치기 −110 → 0. */
    static double attackSwing(int attackTicks) {
        if (attackTicks < 0 || attackTicks > ATTACK_TICKS + 2) return 0;
        double p = Math.min(1.0, attackTicks / (double) ATTACK_TICKS);
        if (p < 0.3) return -110 * (p / 0.3);
        return -110 * (1 - (p - 0.3) / 0.7);
    }

    /**
     * anim 키별 자세 계산.
     * @param anim body | head | legs_walk | arm_left | arm_right | wings | tail | jaw | spin | orbit | float | pulse | static
     * @param form 파트 form (다리 종류에 따라 걷기 모양을 다르게)
     */
    public static Pose pose(String anim, String form, AnimState s) {
        Vector3f off = new Vector3f();
        Quaternionf rot = new Quaternionf();
        float scale = 1f;
        long t = s.tick();
        double walk = walkFactor(s.moveSpeed());
        double ph = (s.seed() & 0xFF) / 255.0 * Math.PI * 2; // 몹마다 위상 다르게
        String a = anim == null ? "static" : anim;
        switch (a) {
            case "body" -> {
                off.y = (float) (0.02 * wave(t, 40, ph));
                if (walk > 0) rot.rotateZ(rad(3 * walk * wave(t, 12, ph)));
            }
            case "head" -> {
                double yaw = Math.max(-45, Math.min(45, s.headYaw()));
                double pitch = Math.max(-20, Math.min(20, s.headPitch()));
                double tilt = s.hasTarget() ? 0 : 7 * wave(t, 70, ph);
                rot.rotateY(rad(-yaw)).rotateX(rad(pitch)).rotateZ(rad(tilt));
            }
            case "legs_walk" -> {
                if (form != null && (form.equals("leg_six") || form.equals("leg_eight") || form.equals("leg_quad"))) {
                    rot.rotateY(rad(10 * walk * wave(t, 6, ph)));
                    off.y = (float) (0.03 * walk * Math.abs(wave(t, 6, ph)));
                } else {
                    rot.rotateX(rad(25 * walk * wave(t, 14, ph)));
                }
            }
            case "arm_left", "arm_right" -> {
                boolean right = a.equals("arm_right");
                double swing = 20 * walk * wave(t, 14, ph + (right ? 0 : Math.PI));
                double atk = 0;
                if (s.attackTicks() >= 0 && (s.attackArm() == 2 || (s.attackArm() == 0) == right)) atk = attackSwing(s.attackTicks());
                if (s.castTicks() >= 0 && s.castTicks() < 14) atk = Math.min(atk, -70 * Math.sin(Math.PI * s.castTicks() / 14.0));
                rot.rotateX(rad(atk != 0 ? atk : swing));
                if (!s.hasTarget() && walk == 0) rot.rotateZ(rad((right ? -1 : 1) * 3 * wave(t, 50, ph)));
            }
            case "wings" -> {
                double flap = wave(t, 8, ph);
                rot.rotateX(rad(20 * flap));
                scale = 1f;
                off.y = (float) (0.04 * flap);
            }
            case "tail" -> rot.rotateY(rad(20 * wave(t, 30, ph) + (walk > 0 ? 8 * wave(t, 10, ph) : 0)));
            case "jaw" -> {
                boolean open = (s.attackTicks() >= 0 && s.attackTicks() <= ATTACK_TICKS) || (s.castTicks() >= 0 && s.castTicks() < 16);
                rot.rotateX(rad(open ? -30 : -3 * Math.max(0, wave(t, 60, ph))));
            }
            case "spin" -> rot.rotateY(rad((t * 4.5) % 360.0));
            case "orbit" -> rot.rotateX(rad(15)).rotateY(rad((-t * 2.25) % 360.0));
            case "float" -> off.y = (float) (0.1 * wave(t, 60, ph));
            case "pulse" -> scale = (float) (1.03 + 0.03 * wave(t, 24, ph));
            default -> { }
        }
        // 피격 흔들림 (GDD: 붉은 밝기 대신 파트 흔들기)
        if (s.hurtTicks() >= 0 && s.hurtTicks() < HURT_TICKS) {
            double k = 1.0 - s.hurtTicks() / (double) HURT_TICKS;
            double j = ((s.seed() * 31 + a.hashCode() + s.hurtTicks() * 17L) % 7) - 3;
            rot.rotateZ(rad(6 * k * Math.signum(j == 0 ? 1 : j)));
            off.x += (float) (0.03 * k * Math.signum(j));
        }
        // 사망: 0.6초간 가라앉으며 작아짐
        if (s.deathTicks() >= 0) {
            double p = Math.min(1.0, s.deathTicks() / (double) DEATH_TICKS);
            off.y -= (float) (0.6 * p);
            scale *= (float) Math.max(0.05, 1 - 0.85 * p);
            rot.rotateZ(rad(25 * p));
        }
        return new Pose(off, rot, scale);
    }

    /**
     * Display Transformation 성분 계산.
     * @param yawDeg     몹 yaw (마인크래프트 규칙)
     * @param modelScale 몹 scale (파트 크기 배율)
     * @param pivotX/Y/Z 파트 피벗 (블록, scale 1 기준, 몹 로컬)
     * @param yawOffsetDeg 모델 방향 보정 (리소스팩이 FIXED 180° 뒤집힘을 보정하지 않았을 때 180)
     * @param outTranslation 결과: 앵커(몹 발) 기준 이동
     * @param outLeft 결과: 왼쪽 회전
     * @return 크기(균일)
     */
    public static float compose(float yawDeg, float modelScale, float pivotX, float pivotY, float pivotZ, Pose pose,
                                float yawOffsetDeg, Vector3f outTranslation, Quaternionf outLeft) {
        Quaternionf yaw = new Quaternionf().rotationY(rad(-yawDeg));
        Vector3f local = new Vector3f(pivotX, pivotY, pivotZ).add(pose.offset()).mul(modelScale);
        yaw.transform(local, outTranslation);
        outLeft.set(yaw).mul(pose.rotation());
        if (yawOffsetDeg != 0) outLeft.rotateY(rad(yawOffsetDeg));
        return modelScale * pose.scale();
    }
}
