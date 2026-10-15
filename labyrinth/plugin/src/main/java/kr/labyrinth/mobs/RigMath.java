package kr.labyrinth.mobs;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.content.ModelDef;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 모델 리그 절차적 애니메이션 수학 (GDD §14.3 anim 표 + §14.6 좌표·관절 규칙). Bukkit 무관 — 단위 테스트 대상.
 * <p>
 * 몹 로컬 좌표: +Z = 앞, +Y = 위, +X = 몹의 왼쪽. 파트 피벗(블록, scale 1 기준)은 모델 원점(8,8,8)에 대응하고,
 * 회전은 파트의 관절({@code joint}, 없으면 피벗)을 중심으로 한다. {@link #compose} 가 몹 yaw·scale 을 곱해 Display
 * Transformation(앵커 = 몹 발 위치 기준)을 만든다.
 * <p>
 * 파트끼리 붙어 움직이는 규칙은 {@link Skeleton}: 다리마다 걸음 위상(두 발 좌우 교대 · 네 발 대각 짝 · 여섯 발 삼각 교대 ·
 * 여덟 발 교대 + 물결), 이동 거리만큼 진행하는 걸음 박자({@link Gait}), 발바닥 땅 보정, 목 사슬 → 머리 → 머리 무리,
 * 꼬리 사슬, 다리를 뺀 윗몸 한 덩어리 흔들림, 몸 전체(피격·사망·급강하·솟구침·보스 오버레이) 변환.
 */
public final class RigMath {

    private RigMath() {}

    /** {@link AnimState#motion} 값: 보통 · 급강하 · 날아오름(급강하 전 상승). */
    public static final int MOTION_NONE = 0;
    public static final int MOTION_DIVE = 1;
    public static final int MOTION_RISE = 2;
    /** {@link AnimState#attackArm} 값: 0 = 오른팔, 1 = 왼팔, 2 = 양팔, 3 = 꼬리 휩쓸기(팔은 안 움직임). */
    public static final int ATTACK_TAIL = 3;
    /** 땅속에서 솟구칠 때 모델이 바닥 아래에서 올라오는 시간. */
    public static final int EMERGE_TICKS = 8;

    /**
     * 애니메이션 입력 (틱 단위). -1 = 해당 없음.
     * moveSpeed = 수평 이동 속도(블록/틱, 월드 단위), airborne = 날거나 공중에 뜸(날개 퍼덕임·다리 접기),
     * motion = {@link #MOTION_NONE}…, bodyPitch = 몸 전체 앞숙임(도, + = 머리 아래), emergeTicks = 땅속에서 솟구친 뒤 지난 틱.
     */
    public record AnimState(long tick, double moveSpeed, int attackTicks, int attackArm, int castTicks, int hurtTicks,
                            float headYaw, float headPitch, int deathTicks, boolean hasTarget, long seed,
                            boolean airborne, int motion, float bodyPitch, int emergeTicks) {

        /** 예전 11인자 생성자 (보스 리그·테스트 호환): 땅 위·보통 동작. */
        public AnimState(long tick, double moveSpeed, int attackTicks, int attackArm, int castTicks, int hurtTicks,
                         float headYaw, float headPitch, int deathTicks, boolean hasTarget, long seed) {
            this(tick, moveSpeed, attackTicks, attackArm, castTicks, hurtTicks, headYaw, headPitch, deathTicks, hasTarget, seed,
                    false, MOTION_NONE, 0f, -1);
        }

        /** 머리 회전만 바꾼 사본 (목이 머리 회전을 나눠 가질 때). */
        public AnimState withHead(float yaw, float pitch) {
            return new AnimState(tick, moveSpeed, attackTicks, attackArm, castTicks, hurtTicks, yaw, pitch, deathTicks,
                    hasTarget, seed, airborne, motion, bodyPitch, emergeTicks);
        }
    }

    /** 파트 하나의 로컬 자세: 피벗 기준 이동(블록, scale 1), 회전, 크기 배율. */
    public record Pose(Vector3f offset, Quaternionf rotation, float scale) {
        public static Pose identity() { return new Pose(new Vector3f(), new Quaternionf(), 1f); }
    }

    public static final int ATTACK_TICKS = 6;   // 내려치기 0.3초
    public static final int DEATH_TICKS = 12;   // 사망 0.6초
    public static final int HURT_TICKS = 4;

    // ── 걸음 상수 (GDD §14.3 legs_walk) ──
    /** 매달린 다리(두 발 · 네 발)의 기본 흔들 각(도). 한 주기 이동 거리 = 4 · 엉덩이 높이 · sin(각). */
    static final double SWING_BIPED = 26, SWING_QUAD = 22, SWING_MAX = 50;
    /** 펼친 다리(여섯 · 여덟 발)의 앞뒤 휘두름 각 · 최대 · 앞으로 갈 때 들어 올리는 각(도). */
    static final double SWEEP = 22, SWEEP_MAX = 40, SPLAY_LIFT = 15;
    /** 한 주기 중 발이 땅을 딛는 비율: 두 발·네 발 0.6(두 발 모두 딛는 순간이 있음), 여섯·여덟 발 0.55. */
    static final double DUTY_HANG = 0.6, DUTY_SPLAY = 0.55;
    /** 공중에서 접는 각(도): 매달린 다리는 뒤로, 펼친 다리는 위로 웅크림. */
    static final double TUCK = 35, SPLAY_TUCK = 25;
    /** 걸음 한 주기 길이(틱) 범위 — 짧은 쪽은 갱신 간격의 4배 이상(깜빡임 방지), 긴 쪽은 느릴 때 보폭을 줄이는 기준. */
    static final double CYCLE_MIN = 10, CYCLE_MAX = 24;
    static final double ARM_SWING = 20;
    /** 피격 때 몸 전체가 젖혀지는 각(도) · 옆 밀림(블록). */
    static final double HURT_TILT = 5, HURT_SHIFT = 0.03;

    private static float rad(double deg) { return (float) Math.toRadians(deg); }

    private static double wave(long tick, double periodTicks, double phase) {
        return Math.sin(2 * Math.PI * (tick / periodTicks) + phase);
    }

    private static double frac(double v) { return v - Math.floor(v); }

    private static double clamp(double v, double lo, double hi) { return Math.max(lo, Math.min(hi, v)); }

    private static double seedPhase(AnimState s) { return (s.seed() & 0xFF) / 255.0 * Math.PI * 2; }

    /** 걷기 비율 0~1 (블록/틱 → 0.18 이상이면 최대) — 다리가 없는 몹의 예전 흔들기용. */
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

    /** 보폭 배율 k → 각(도): sin(각) = k·sin(기본각), 최대각에서 멈춤. */
    static double strideAngle(double k, double base, double max) {
        double s = Math.min(Math.sin(Math.toRadians(max)), k * Math.sin(Math.toRadians(base)));
        return Math.toDegrees(Math.asin(Math.max(0, s)));
    }

    /**
     * 파트 하나만의 자세 (관절 계층 없이 — 단일 파트 확인용). 다리는 틱 14 주기로 통째 흔들고 몸은 자기 자리에서
     * 흔들린다. 몹·보스 리그는 {@link Skeleton#solve} 를 쓴다.
     * @param anim body | head | legs_walk | arm_left | arm_right | wings | wings_flap | tail | tail_chain | neck | jaw |
     *             spin | orbit | float | pulse | static
     * @param form 파트 form (다리 종류에 따라 걷기 모양을 다르게)
     */
    public static Pose pose(String anim, String form, AnimState s) {
        return pose(anim, form, s, 0, 0);
    }

    /**
     * @param side  파트 X 부호 (+1 = 몹의 왼쪽, −1 = 오른쪽, 0 = 가운데) — wings_flap·다리의 좌우
     * @param chain 사슬 안 순서 (0 = 뿌리) — tail_chain·neck 의 물결 지연
     */
    public static Pose pose(String anim, String form, AnimState s, int side, int chain) {
        Vector3f off = new Vector3f();
        Quaternionf rot = new Quaternionf();
        float[] sc = {1f};
        long t = s.tick();
        double walk = walkFactor(s.moveSpeed());
        double ph = seedPhase(s);
        String a = anim == null ? "static" : anim;
        switch (a) {
            case "body" -> {
                off.y = (float) (0.02 * wave(t, 40, ph));
                if (walk > 0) rot.rotateZ(rad(3 * walk * wave(t, 12, ph)));
            }
            case "legs_walk" -> {
                double p = t / 14.0;
                double air = s.airborne() ? 1 : 0;
                if ("leg_six".equals(form) || "leg_eight".equals(form)) {
                    legSplay(side, SWEEP * walk, SPLAY_LIFT * walk, p, DUTY_SPLAY, air, t, ph, rot);
                } else if ("leg_pair".equals(form) || "leg_quad".equals(form)) {
                    legHang(SWING_BIPED * walk, p, DUTY_HANG, 0, air, t, ph, rot, off);
                } else {
                    crawl(walk, p, rot, off);
                }
            }
            default -> common(a, s, side, chain, walk, ph, Double.NaN, false, false, rot, off, sc);
        }
        return new Pose(off, rot, sc[0]);
    }

    /** body·legs_walk 를 뺀 anim 키 공통 자세. armSwing = 걸음 위상에 묶인 팔 흔들기(도), NaN = 예전 틱 흔들기. */
    private static void common(String a, AnimState s, int side, int chain, double walk, double ph, double armSwing,
                               boolean lowerJaw, boolean pendulum, Quaternionf rot, Vector3f off, float[] sc) {
        long t = s.tick();
        switch (a) {
            case "head" -> {
                double yaw = Math.max(-45, Math.min(45, s.headYaw()));
                double pitch = Math.max(-20, Math.min(20, s.headPitch()));
                double tilt = s.hasTarget() ? 0 : 7 * wave(t, 70, ph);
                rot.rotateY(rad(-yaw)).rotateX(rad(pitch)).rotateZ(rad(tilt));
            }
            case "arm_left", "arm_right" -> {
                boolean right = a.equals("arm_right");
                double swing = Double.isNaN(armSwing) ? 20 * walk * wave(t, 14, ph + (right ? 0 : Math.PI)) : armSwing;
                double atk = 0;
                if (s.attackTicks() >= 0 && (s.attackArm() == 2 || (s.attackArm() <= 1 && (s.attackArm() == 0) == right))) {
                    atk = attackSwing(s.attackTicks());
                }
                if (s.castTicks() >= 0 && s.castTicks() < 14) atk = Math.min(atk, -70 * Math.sin(Math.PI * s.castTicks() / 14.0));
                rot.rotateX(rad(atk != 0 ? atk : swing));
                if (!s.hasTarget() && walk == 0) rot.rotateZ(rad((right ? -1 : 1) * 3 * wave(t, 50, ph)));
            }
            case "wings" -> {
                double flap = wave(t, 8, ph);
                rot.rotateX(rad(20 * flap));
                off.y = (float) (0.04 * flap);
            }
            case "tail" -> {
                if (pendulum) {
                    // 아래로 매달린 꼬리·진자: 제자리 빙글 대신 좌우·앞뒤로 흔들림
                    rot.rotateZ(rad(12 * wave(t, 40, ph)))
                            .rotateX(rad(5 * wave(t, 40, ph + Math.PI / 2) + (walk > 0 ? 6 * walk * wave(t, 10, ph) : 0)));
                } else {
                    rot.rotateY(rad(20 * wave(t, 30, ph) + (walk > 0 ? 8 * wave(t, 10, ph) : 0)));
                }
            }
            case "wings_flap" -> wingsFlap(s, side, walk, ph, rot, off);
            case "tail_chain" -> {
                // 마디마다 같은 물결을 늦게(뒤로 갈수록 크게) — 사슬로 쌓이므로 끝은 마디 각도의 합만큼 휜다
                double moving = walk;
                double period = moving > 0.2 ? 16 : 44;
                double amp = (moving > 0.2 ? 9 + 6 * moving : 6) * (0.7 + 0.2 * chain);
                double sw = wave(t, period, ph - 0.9 * (chain + 1));
                double swipe = 0;
                if (s.attackArm() == ATTACK_TAIL && s.attackTicks() >= 0 && s.attackTicks() <= ATTACK_TICKS + 4) {
                    swipe = (chain == 0 ? 45 : 22) * Math.sin(Math.PI * Math.min(1.0, s.attackTicks() / (double) (ATTACK_TICKS + 4)));
                }
                double curl = chain == 0 ? -4 : 2 + 3 * wave(t, 60, ph - chain);
                rot.rotateY(rad(amp * sw + swipe)).rotateX(rad(curl));
            }
            case "neck" -> {
                // 머리 회전의 일부(Skeleton 이 나눠 줌) + 느린 흔들림, 공격 때 앞으로 내밀고 브레스·시전 때 앞으로 뻗기
                double yaw = Math.max(-45, Math.min(45, s.headYaw()));
                double pitch = Math.max(-20, Math.min(20, s.headPitch()));
                double sway = 4 * wave(t, 90, ph - chain);
                double lunge = 0;
                if (s.attackTicks() >= 0 && s.attackTicks() <= ATTACK_TICKS + 2 && s.attackArm() != ATTACK_TAIL) {
                    lunge = 18 * Math.sin(Math.PI * Math.min(1.0, s.attackTicks() / (double) (ATTACK_TICKS + 2)));
                }
                if (s.castTicks() >= 0 && s.castTicks() < 16) lunge = Math.max(lunge, 12);
                if (s.motion() == MOTION_DIVE) lunge = Math.max(lunge, 10);
                rot.rotateY(rad(-yaw + sway)).rotateX(rad(pitch + lunge));
            }
            case "jaw" -> {
                // 아래턱(머리 밑 claw)은 경첩(뒤 끝 위)에서 앞 끝이 아래로 벌어지고, 뚜껑·덮개는 위로 열린다
                boolean open = (s.attackTicks() >= 0 && s.attackTicks() <= ATTACK_TICKS) || (s.castTicks() >= 0 && s.castTicks() < 16);
                double deg = open ? 30 : 3 * Math.max(0, wave(t, 60, ph));
                rot.rotateX(rad(lowerJaw ? deg : -deg));
            }
            case "spin" -> rot.rotateY(rad((t * 4.5) % 360.0));
            case "orbit" -> rot.rotateX(rad(15)).rotateY(rad((-t * 2.25) % 360.0));
            case "float" -> off.y = (float) (0.1 * wave(t, 60, ph));
            case "pulse" -> sc[0] = (float) (1.03 + 0.03 * wave(t, 24, ph));
            default -> { }
        }
    }

    /**
     * 걸음 위상 p(주기) → 발 앞뒤 위치 u (+1 = 가장 앞, −1 = 가장 뒤). 딛는 동안(p < duty) 일정한 빠르기로 앞 → 뒤
     * (몸이 가는 속도와 같아 디딘 발이 미끄러지지 않음), 나머지 동안 부드럽게 뒤 → 앞.
     */
    static double footU(double p, double duty) {
        double q = frac(p);
        if (q < duty) return 1 - 2 * q / duty;
        double r = (q - duty) / (1 - duty);
        return -1 + 2 * r * r * (3 - 2 * r);
    }

    /** 발을 드는 정도 0~1: 앞으로 옮기는 동안만 (가운데에서 가장 높이). */
    static double footLift(double p, double duty) {
        double q = frac(p);
        return q < duty ? 0 : Math.sin(Math.PI * (q - duty) / (1 - duty));
    }

    /** 딛는 정도 0~1 (땅 보정 가중치): 딛는 반 주기 가운데에서 1. */
    static double footStance(double p, double duty) {
        double q = frac(p);
        return q < duty ? Math.sin(Math.PI * q / duty) : 0;
    }

    /**
     * 매달린 다리(leg_pair · leg_quad): 관절에서 rotX(θ), 발 앞뒤 = 엉덩이 높이·sin(−θ) = u·sin(각) (+θ = 발이 뒤로).
     * 발을 앞으로 옮기는 동안 lift(블록)만큼 들어 올린다. 공중(air 1)에서는 뒤로 접는다.
     */
    static void legHang(double ampDeg, double p, double duty, double lift, double air, long t, double ph, Quaternionf rot,
                        Vector3f off) {
        double theta = -Math.toDegrees(Math.asin(clamp(footU(p, duty) * Math.sin(Math.toRadians(ampDeg)), -1, 1)));
        double tuck = TUCK + 3 * wave(t, 30, ph);
        rot.rotateX(rad(theta * (1 - air) + tuck * air));
        off.y += (float) (lift * footLift(p, duty) * (1 - air));
    }

    /**
     * 펼친 다리(leg_six · leg_eight): 관절에서 앞뒤 rotY(side·β) (+β = 발이 뒤로, 발 앞뒤 = 옆 뻗음·sin(−β) = u·sin(각))와,
     * 발을 앞으로 옮길 때 들어 올리는 rotZ(side·φ). 공중에서는 위로 웅크린다.
     */
    static void legSplay(int side, double sweepDeg, double liftDeg, double p, double duty, double air, long t, double ph,
                         Quaternionf rot) {
        double sg = side >= 0 ? 1 : -1;
        double beta = -Math.toDegrees(Math.asin(clamp(footU(p, duty) * Math.sin(Math.toRadians(sweepDeg)), -1, 1))) * (1 - air);
        double phi = liftDeg * footLift(p, duty) * (1 - air) + (SPLAY_TUCK + 3 * wave(t, 30, ph)) * air;
        rot.rotateY(rad(sg * beta)).rotateZ(rad(sg * phi));
    }

    /** 다리가 아닌 덩어리(촉수 뭉치·발판)에 걸린 legs_walk: 통째 기울기 대신 작게 꿈틀거리며 기어가기. */
    static void crawl(double k, double p, Quaternionf rot, Vector3f off) {
        double c = 2 * Math.PI * p;
        rot.rotateY(rad(4 * k * Math.sin(c)));
        off.y += (float) (0.02 * k * Math.abs(Math.sin(c)));
    }

    /**
     * 한쪽 날개(wings_flap): side = 관절 X 부호. 날 때 위아래 퍼덕임, 날아오를 때 크고 빠르게, 급강하 때 뒤로 접음,
     * 브레스·포효(시전) 때 활짝 펼침, 땅 위에서는 등 뒤로 반쯤 접고 가끔 들썩. side 0(날개 한 쌍 파트)은 앞뒤로 크게.
     */
    private static void wingsFlap(AnimState s, int side, double walk, double ph, Quaternionf rot, Vector3f off) {
        long t = s.tick();
        double sg = side > 0 ? 1 : side < 0 ? -1 : 0;
        boolean casting = s.castTicks() >= 0 && s.castTicks() < 16;
        if (s.motion() == MOTION_DIVE) {
            double tremble = 3 * wave(t, 3, ph);
            if (sg == 0) rot.rotateX(rad(-45 + tremble));
            else rot.rotateY(rad(sg * 55)).rotateZ(rad(sg * (14 + tremble)));
        } else if (s.airborne() || s.motion() == MOTION_RISE) {
            boolean rise = s.motion() == MOTION_RISE;
            double flap = wave(t, rise ? 7 : 10, ph);
            double amp = rise ? 48 : 36;
            if (sg == 0) {
                rot.rotateX(rad(amp * 0.7 * flap));
                off.y = (float) (0.05 * flap);
            } else {
                // 내려칠 때(flap < 0) 날개 끝이 살짝 앞으로
                rot.rotateY(rad(sg * -6 * Math.max(0, -flap))).rotateZ(rad(sg * (8 + amp * flap)));
            }
        } else if (casting) {
            double f = 4 * wave(t, 4, ph);
            if (sg == 0) rot.rotateX(rad(-15 + f));
            else rot.rotateY(rad(sg * 10)).rotateZ(rad(sg * (22 + f)));
        } else {
            double w = Math.max(0, wave(t, 110, ph));
            double twitch = w > 0.96 ? (w - 0.96) / 0.04 : 0;
            double bob = 4 * walk * wave(t, 14, ph);
            if (sg == 0) rot.rotateX(rad(-25 + bob - 10 * twitch));
            else rot.rotateY(rad(sg * (50 - 20 * twitch))).rotateZ(rad(sg * (28 + 22 * twitch + bob)));
        }
    }

    // ── 걸음 박자 ─────────────────────────────────────────────────────

    /**
     * 걸음 위상 누적기 (리그마다 하나, 갱신 때마다 {@link #advance}). 위상(주기 단위)은 이동한 거리 ÷ 한 주기 이동 거리만큼
     * 진행한다 → 디딘 발이 몸 속도로 뒤로 밀려 미끄러지지 않고, 멈추면 진행도 멈춘다. air = 공중 비율(0~1, 몇 틱에 걸쳐
     * 바뀜 — 계단 한 칸 뛰어오를 때 다리가 확 접히지 않게).
     */
    public static final class Gait {
        private double phase;
        private double air = -1;
        private long last = Long.MIN_VALUE;
        private int interval = 2;

        /** 지금 상태로 위상 진행. interval = 다음 갱신까지 틱(박자 하한·보간). */
        public void advance(Skeleton sk, AnimState s, int interval) {
            this.interval = Math.max(1, interval);
            long dt = last == Long.MIN_VALUE ? 0 : Math.max(0, Math.min(10, s.tick() - last));
            last = s.tick();
            Skeleton.Cadence c = sk.cadence(s.moveSpeed(), this.interval);
            if (c.amp() > 0 && dt > 0) phase = frac(phase + dt / c.ticksPerCycle());
            double target = s.airborne() ? 1 : 0;
            air = air < 0 || dt == 0 ? target : air + (target - air) * Math.min(1, 0.4 * dt);
        }

        /** 미리보기·테스트: 위상·공중 비율·갱신 간격을 직접 정한다. */
        public Gait set(double phase, double air, int interval) {
            this.phase = frac(phase);
            this.air = air;
            this.interval = Math.max(1, interval);
            return this;
        }

        public double phase() { return phase; }

        public double air() { return air; }

        public int interval() { return interval; }
    }

    /**
     * 보스 시전 애니메이션처럼 리그 위에 덧입히는 자세 (bosses.BossAnim 이 만든다). 파트 로컬: 리그 자세를 baseWeight 만큼만
     * 남기고 그 위에 회전·이동을 얹는다(사슬 붙이기 전). 몸 전체: 발 위치 기준 회전·이동·크기(마지막).
     */
    public interface Overlay {
        /** 파트 하나: rot·off 에 덧입힐 회전·이동을 쓰고, 리그 자세를 남길 비율(0~1)을 돌려준다. */
        float local(ModelDef.Part part, Quaternionf rot, Vector3f off);

        /** 몸 전체: rot·off 에 발 기준 회전·이동을 쓰고, 균일 크기를 돌려준다. */
        float global(Quaternionf rot, Vector3f off);

        /** 윗몸 숨쉬기·걷기 흔들림을 남길 비율. */
        default float baseWeight() { return 1f; }
    }

    // ── 파트 계층 (관절·다리·목·머리·꼬리 사슬) ────────────────────────────

    /** 파트 하나의 풀이 결과: 모델 원점 위치(블록, scale 1, 몹 로컬)·회전·크기·이동(항상 0 — 위치에 합쳐 있음). */
    public record Solved(Vector3f pivot, Quaternionf rotation, float scale, Vector3f offset) {}

    /**
     * 모델 파트의 관절·붙음 관계 (리그 생성 때 한 번 만들고 매 갱신 {@link #solve}).
     * <ul>
     *   <li>파트마다 회전 중심 = {@code joint}(없으면 pivot). 화면 위치 = J′ + R·(pivot − joint).</li>
     *   <li>다리(anim legs_walk + leg_pair/leg_quad = 매달린 다리, leg_six/leg_eight = 펼친 다리)는 다리마다 위상 φ0 를
     *       관절 위치로 정한다: 옆 = joint X 부호, k = 같은 쪽 앞→뒤 순번, φ0 = ½·((k + 오른쪽?1:0) mod 2)
     *       (같은 쪽 넷 이상이면 + 0.06·k 물결) → 두 발 좌우 교대 · 네 발 대각 짝 · 여섯 발 삼각 교대 · 여덟 발 교대 + 물결.
     *       발바닥이 다른 다리보다 높이 든 다리(치켜든 앞다리)는 걷지 않고 살랑인다.</li>
     *   <li>땅 보정: 땅 위에서는 디딘 발바닥 양 끝 중 가장 낮은 점이 서 있을 때 높이에 오도록 몸 전체를 올리고 내린다.</li>
     *   <li>팔은 반대쪽 앞다리와 같은 위상으로 흔든다(오른팔 = 왼다리).</li>
     *   <li>anim {@code neck} 파트들 = YAML 순서대로 사슬(뿌리 → 머리 쪽). 머리 yaw/pitch 의 절반을 목 마디가 나눠 돈다.</li>
     *   <li>머리 = 이름 head + anim head (없으면 anim head 중 가장 큰 파트). 목이 있으면 마지막 목 마디 끝에 붙는다.</li>
     *   <li>머리 무리: anim head 인 다른 파트(뿔·가면·왕관 — 머리와 같은 회전)와 jaw(머리 회전 + 벌림)는 머리 관절을 따라 돈다.</li>
     *   <li>anim {@code tail_chain} 파트들 = YAML 순서대로 사슬(뿌리 → 끝).</li>
     *   <li>윗몸 무리: 다리를 뺀 모든 파트가 숨쉬기·걷기 좌우 기울기를 함께 받는다(중심 = 엉덩이 관절 가운데).</li>
     *   <li>몸 전체: 몸급 float 부유 · 땅 보정 · 보스 오버레이 · 피격 젖힘 · 급강하 앞숙임 · 솟구침 · 사망(가라앉으며 한 덩어리로 축소).</li>
     * </ul>
     */
    public static final class Skeleton {
        private static final int OTHER = 0, HANG = 1, SPLAY = 2, CRAWL = 3;

        /** 걸음 박자: 한 주기 길이(틱)와 보폭 배율(1 = 기본 각, 0 = 서 있음). */
        public record Cadence(double ticksPerCycle, double amp) {}

        private final List<ModelDef.Part> parts;
        private final int n;
        private final float scale;
        private final Vector3f[] joint;
        private final Vector3f[] toOrigin;
        private final int[] kind;
        private final int[] side;
        private final int[] chainIndex;
        private final double[] phase0;
        private final double[] reachMul;
        private final boolean[] walking;
        private final boolean[] headGroup;
        private final boolean[] lowerJaw;
        private final boolean[] pendulum;
        private final ModelDef.Foot[] foot;
        private final int head;
        private final int floatGlobal;
        private final int[] neck;
        private final int[] tail;
        private final float height;
        private final Vector3f centre;
        private final boolean breathes;
        private final int walkLegs;
        private final boolean hangGait;
        private final double swing;
        private final double stride;
        private final double duty;
        private final double hip;
        private final double restLow;
        private final double armPhaseLeft;
        private final double armPhaseRight;
        private final boolean biped;
        private final double phaseLeft;

        public Skeleton(List<ModelDef.Part> parts) {
            this(parts, 1.0);
        }

        /** @param scale 몹 scale (보폭을 월드 거리로 — 정예 변형의 크기도 포함) */
        public Skeleton(List<ModelDef.Part> parts, double scale) {
            this.parts = List.copyOf(parts);
            this.scale = (float) Math.max(0.05, scale);
            n = this.parts.size();
            joint = new Vector3f[n];
            toOrigin = new Vector3f[n];
            kind = new int[n];
            side = new int[n];
            chainIndex = new int[n];
            phase0 = new double[n];
            reachMul = new double[n];
            walking = new boolean[n];
            headGroup = new boolean[n];
            lowerJaw = new boolean[n];
            pendulum = new boolean[n];
            foot = new ModelDef.Foot[n];
            int h = -1;
            List<Integer> nk = new ArrayList<>();
            List<Integer> tl = new ArrayList<>();
            float top = 0;
            double maxVol = 0;
            boolean br = false;
            for (int i = 0; i < n; i++) {
                ModelDef.Part p = this.parts.get(i);
                joint[i] = new Vector3f((float) p.jointX(), (float) p.jointY(), (float) p.jointZ());
                toOrigin[i] = new Vector3f((float) (p.pivotX() - p.jointX()), (float) (p.pivotY() - p.jointY()),
                        (float) (p.pivotZ() - p.jointZ()));
                side[i] = p.jointX() > 1e-4 ? 1 : p.jointX() < -1e-4 ? -1 : 0;
                String a = p.anim();
                if ("neck".equals(a)) {
                    chainIndex[i] = nk.size();
                    nk.add(i);
                }
                if ("tail_chain".equals(a)) {
                    chainIndex[i] = tl.size();
                    tl.add(i);
                }
                if ("body".equals(a)) br = true;
                if (h < 0 && "head".equals(p.name()) && "head".equals(a)) h = i;
                top = Math.max(top, (float) (p.pivotY() + p.sizeY() / 32.0));
                maxVol = Math.max(maxVol, p.sizeX() * p.sizeY() * p.sizeZ());
                if ("legs_walk".equals(a)) {
                    String f = p.form();
                    kind[i] = "leg_pair".equals(f) || "leg_quad".equals(f) ? HANG
                            : "leg_six".equals(f) || "leg_eight".equals(f) ? SPLAY : CRAWL;
                }
                pendulum[i] = "tail".equals(a) && p.sizeY() > 1.4 * p.sizeZ();
                if (kind[i] == HANG || kind[i] == SPLAY) foot[i] = p.foot() != null ? p.foot() : guessFoot(p, kind[i], side[i]);
            }
            if (h < 0) {    // 이름이 head 인 파트가 없으면 anim head 중 가장 큰 파트 (포탑 + 포신)
                double best = -1;
                for (int i = 0; i < n; i++) {
                    ModelDef.Part p = this.parts.get(i);
                    double v = p.sizeX() * p.sizeY() * p.sizeZ();
                    if ("head".equals(p.anim()) && v > best) {
                        best = v;
                        h = i;
                    }
                }
            }
            head = h;
            int fg = -1;
            for (int i = 0; i < n; i++) {
                ModelDef.Part p = this.parts.get(i);
                String a = p.anim();
                if (h >= 0 && i != h && ("head".equals(a) || "jaw".equals(a))) headGroup[i] = true;
                lowerJaw[i] = "jaw".equals(a) && "claw".equals(p.form()) && h >= 0 && p.pivotY() < this.parts.get(h).pivotY();
                if (fg < 0 && "float".equals(a) && p.sizeX() * p.sizeY() * p.sizeZ() >= 0.4 * maxVol) fg = i;
            }
            floatGlobal = fg;
            neck = nk.stream().mapToInt(Integer::intValue).toArray();
            tail = tl.stream().mapToInt(Integer::intValue).toArray();
            height = Math.max(0.5f, top);
            breathes = br;
            // 다리: 디딘 발 높이 · 치켜든 다리 · 위상
            double low = Double.MAX_VALUE;
            for (int i = 0; i < n; i++) if (foot[i] != null) low = Math.min(low, joint[i].y + foot[i].dy());
            int legs = 0, hangs = 0;
            double hipSum = 0, reachSum = 0;
            Vector3f c = new Vector3f();
            for (int i = 0; i < n; i++) {
                if (foot[i] == null) continue;
                walking[i] = joint[i].y + foot[i].dy() <= low + Math.max(0.15, 0.12 * height);
                if (!walking[i]) continue;
                legs++;
                c.add(joint[i]);
                if (kind[i] == HANG) {
                    hangs++;
                    hipSum += Math.abs(foot[i].dy());
                } else {
                    reachSum += Math.max(0.08, Math.abs(foot[i].dx()));
                }
            }
            walkLegs = legs;
            restLow = legs > 0 ? low : 0;
            hangGait = hangs > 0;
            swing = hangs <= 2 ? SWING_BIPED : SWING_QUAD;
            hip = hangs > 0 ? hipSum / hangs : 0;
            // 한 주기에 몸이 가는 거리 = 딛는 동안 발이 뒤로 밀리는 거리(2·길이·sin 각) ÷ 딛는 비율
            duty = hangs > 0 ? DUTY_HANG : DUTY_SPLAY;
            double st = hangs > 0 ? 2 * hip * Math.sin(Math.toRadians(swing)) / duty
                    : legs > 0 ? 2 * (reachSum / legs) * Math.sin(Math.toRadians(SWEEP)) / duty : 0;
            stride = Math.max(0.05, st);
            // 다리마다 길이(엉덩이 높이 · 옆 뻗음)가 달라도 발이 같은 거리를 가도록 각 배율
            for (int i = 0; i < n; i++) {
                if (!walking[i]) continue;
                double len = kind[i] == HANG ? Math.abs(foot[i].dy()) : Math.max(0.08, Math.abs(foot[i].dx()));
                double mean = kind[i] == HANG ? hip : reachSum / Math.max(1, legs - hangs);
                reachMul[i] = clamp(mean / Math.max(0.05, len), 0.5, 2.0);
            }
            double pl = Double.NaN, pr = Double.NaN;
            double zl = -1e9, zr = -1e9;
            for (int sd : new int[] {1, -1}) {
                List<Integer> same = new ArrayList<>();
                for (int i = 0; i < n; i++) if (walking[i] && side[i] == sd) same.add(i);
                same.sort((x, y) -> Float.compare(joint[y].z, joint[x].z));
                for (int k = 0; k < same.size(); k++) {
                    int i = same.get(k);
                    phase0[i] = 0.5 * ((k + (sd < 0 ? 1 : 0)) % 2) + (same.size() >= 4 ? 0.06 * k : 0);
                    if (sd > 0 && joint[i].z > zl) {
                        zl = joint[i].z;
                        pl = phase0[i];
                    }
                    if (sd < 0 && joint[i].z > zr) {
                        zr = joint[i].z;
                        pr = phase0[i];
                    }
                }
            }
            // 오른팔은 왼쪽 앞다리와, 왼팔은 오른쪽 앞다리와 같은 위상 (반대 팔·다리 교차)
            armPhaseRight = pl;
            armPhaseLeft = pr;
            biped = hangs == 2 && legs == 2 && !Double.isNaN(pl) && !Double.isNaN(pr);
            phaseLeft = Double.isNaN(pl) ? 0 : pl;
            if (legs > 0) {
                centre = c.div(legs);
            } else {
                Vector3f b = null;
                for (int i = 0; i < n; i++) {
                    if ("body".equals(this.parts.get(i).anim())) {
                        b = new Vector3f(joint[i]);
                        break;
                    }
                }
                centre = b != null ? b : new Vector3f(0, height * 0.4f, 0);
            }
        }

        /** foot 가 없을 때: form·size 로 어림 (매달린 다리 = 관절에서 바로 아래 땅, 펼친 다리 = 옆으로 size 절반). */
        private static ModelDef.Foot guessFoot(ModelDef.Part p, int kind, int side) {
            double down = -Math.max(0.05, p.jointY());
            if (kind == HANG) return new ModelDef.Foot(0, down, 0, p.sizeZ() / ("leg_quad".equals(p.form()) ? 64.0 : 32.0));
            double reach = Math.max(0.1, p.sizeX() / 32.0 - Math.abs(p.jointX() - p.pivotX()));
            return new ModelDef.Foot((side >= 0 ? 1 : -1) * reach, down, 0, 0);
        }

        public int size() { return parts.size(); }

        public ModelDef.Part part(int i) { return parts.get(i); }

        /** 모델 높이(블록, scale 1) — 솟구침·앞숙임 기준. */
        public float height() { return height; }

        /** 걷는 다리 수 (0 = 다리 없음 · 걸음 위상 없이 예전 틱 흔들기). */
        public int walkingLegs() { return walkLegs; }

        /** 다리 i 의 위상 φ0 (주기, 걷는 다리가 아니면 0). */
        public double phase0(int i) { return phase0[i]; }

        /** 다리 i 가 걷는 다리인가 (치켜든 다리·다리 아님 = false). */
        public boolean walking(int i) { return walking[i]; }

        /** 기본 보폭에서 한 주기 동안 가는 거리(블록, scale 1). */
        public double stride() { return stride; }

        private double kMax() {
            return hangGait ? Math.sin(Math.toRadians(SWING_MAX)) / Math.sin(Math.toRadians(swing))
                    : Math.sin(Math.toRadians(SWEEP_MAX)) / Math.sin(Math.toRadians(SWEEP));
        }

        /**
         * 걸음 박자: 이동 속도(블록/틱, 월드)와 갱신 간격(틱) → 한 주기 길이와 보폭 배율.
         * 한 주기 = 보폭 거리 ÷ 속도 (디딘 발이 미끄러지지 않음), 범위 [max(10, 4·간격), 24]틱. 24틱보다 느리면 박자는 두고
         * 보폭을 줄이고(멈추면 0), 10틱보다 빠르면 보폭을 키운다(최대 각까지 — 그 너머는 미끄러짐).
         */
        public Cadence cadence(double speed, int interval) {
            if (walkLegs == 0) return new Cadence(14, walkFactor(speed));
            if (speed < 0.004) return new Cadence(CYCLE_MAX, 0);
            double d1 = stride * scale;
            double tmin = Math.max(CYCLE_MIN, 4.0 * Math.max(1, interval));
            double tt = clamp(d1 / speed, tmin, Math.max(tmin, CYCLE_MAX));
            return new Cadence(tt, Math.min(speed * tt / d1, kMax()));
        }

        /** 지금 상태의 모든 파트 자세 (걸음 위상 = 틱 ÷ 지금 속도의 주기 — 속도가 일정할 때와 같다). */
        public Solved[] solve(AnimState s) {
            return solve(s, null, null);
        }

        public Solved[] solve(AnimState s, Gait g) {
            return solve(s, g, null);
        }

        /** @param g 걸음 위상 누적기 (null = 틱으로 계산) · ov 보스 오버레이 (null = 없음) */
        public Solved[] solve(AnimState s, Gait g, Overlay ov) {
            long t = s.tick();
            int interval = g == null ? 2 : g.interval();
            Cadence cad = cadence(s.moveSpeed(), interval);
            double gp = g == null ? frac(t / cad.ticksPerCycle()) : g.phase();
            double air = g == null || g.air() < 0 ? (s.airborne() ? 1 : 0) : g.air();
            double k = s.deathTicks() >= 0 ? 0 : cad.amp();
            double walk = walkFactor(s.moveSpeed());
            double ph = seedPhase(s);
            double gw = ov == null ? 1 : clamp(ov.baseWeight(), 0, 1);
            double km = Math.min(1, k);
            double liftC = SPLAY_LIFT * km;
            double liftH = Math.min(0.04, 0.06 * hip) * km;
            double ke = km * (1 - air);
            double armAmp = ARM_SWING * Math.min(1.3, k) * (1 - air);
            AnimState headState = s;
            AnimState neckState = s;
            if (neck.length > 0 && head >= 0) {
                float share = 0.5f / neck.length;
                neckState = s.withHead(s.headYaw() * share, s.headPitch() * share);
                headState = s.withHead(s.headYaw() * 0.5f, s.headPitch() * 0.5f);
            }
            Vector3f[] jw = new Vector3f[n];
            Quaternionf[] rw = new Quaternionf[n];
            float[] sw = new float[n];
            Quaternionf ovRot = new Quaternionf();
            Vector3f ovOff = new Vector3f();
            float[] sc = new float[1];
            for (int i = 0; i < n; i++) {
                ModelDef.Part p = parts.get(i);
                String a = p.anim() == null ? "static" : p.anim();
                Quaternionf rot = new Quaternionf();
                Vector3f off = new Vector3f();
                sc[0] = 1f;
                switch (kind[i]) {
                    case HANG -> {
                        if (walking[i]) legHang(strideAngle(k * reachMul[i], swing, SWING_MAX + 5), gp + phase0[i], duty, liftH,
                                air, t, ph, rot, off);
                        else rot.rotateX(rad(4 * wave(t, 50, ph + i) + TUCK * air));
                    }
                    case SPLAY -> {
                        if (walking[i]) legSplay(side[i], strideAngle(k * reachMul[i], SWEEP, SWEEP_MAX + 10), liftC, gp + phase0[i],
                                duty, air, t, ph, rot);
                        else rot.rotateZ(rad((side[i] >= 0 ? 1 : -1) * (6 * wave(t, 36, ph + i) + SPLAY_TUCK * air)));
                    }
                    case CRAWL -> crawl(walkLegs > 0 ? ke : walk * (1 - air), walkLegs > 0 ? gp : t / 14.0, rot, off);
                    default -> {
                        if ("body".equals(a) || i == floatGlobal) break;     // 윗몸 무리 · 몸 전체 부유가 맡음
                        double arm = Double.NaN;
                        if (walkLegs > 0 && ("arm_left".equals(a) || "arm_right".equals(a))) {
                            double ap = "arm_right".equals(a) ? armPhaseRight : armPhaseLeft;
                            // 다리가 앞(u = +1)일 때 짝 팔도 앞(−각) — 진자처럼 부드럽게
                            if (!Double.isNaN(ap)) arm = -armAmp * Math.cos(2 * Math.PI * (gp + ap));
                        }
                        AnimState st = "neck".equals(a) ? neckState : headGroup[i] || i == head ? headState : s;
                        common(a, st, side[i], chainIndex[i], walk, ph, arm, lowerJaw[i], pendulum[i], rot, off, sc);
                    }
                }
                if (ov != null) {
                    ovRot.identity();
                    ovOff.zero();
                    float bw = (float) clamp(ov.local(p, ovRot, ovOff), 0, 1);
                    Quaternionf base = new Quaternionf().slerp(rot, bw);
                    rot = new Quaternionf(ovRot).mul(base);
                    off.mul(bw).add(ovOff);
                }
                jw[i] = new Vector3f(joint[i]).add(off);
                rw[i] = rot;
                sw[i] = sc[0];
            }
            chain(jw, rw, neck);
            if (head >= 0) {
                if (neck.length > 0) attach(jw, rw, neck[neck.length - 1], head, false);
                for (int i = 0; i < n; i++) {
                    if (!headGroup[i]) continue;
                    // anim head 인 장식은 머리와 같은 회전(자기 회전은 버림), 턱은 머리 회전 위에 벌림
                    attach(jw, rw, head, i, "head".equals(parts.get(i).anim()));
                }
            }
            chain(jw, rw, tail);
            // 땅 보정: 발바닥 양 끝 중 가장 낮은 점 = 서 있을 때 높이. 앞으로 옮기는 발은 드는 만큼(clear·들기) 높다고
            // 치므로 몸 높이는 디딘 발이 정하고, 내려오는 발은 착지 직전부터 이어서 끼어든다(몸이 튀지 않음). 그래도 땅보다
            // 낮은 발(발이 긴 다리가 기울 때 뒤꿈치)은 그 다리만 땅 위로 들어 올린다 — 끌리거나 바닥에 묻히지 않게.
            float lift = 0;
            if (walkLegs > 0 && air < 1) {
                double[] low = new double[n];
                double lowNow = Double.MAX_VALUE;
                double clear = Math.max(0.06, 0.2 * hip);
                Vector3f v = new Vector3f();
                for (int i = 0; i < n; i++) {
                    if (!walking[i]) continue;
                    ModelDef.Foot f = foot[i];
                    double lo = Double.MAX_VALUE;
                    for (int e = -1; e <= 1; e += 2) {
                        v.set((float) f.dx(), (float) f.dy(), (float) (f.dz() + e * f.half()));
                        rw[i].transform(v);
                        lo = Math.min(lo, jw[i].y + v.y * sw[i]);
                    }
                    low[i] = lo;
                    lowNow = Math.min(lowNow, lo + clear * footLift(gp + phase0[i], duty) * km);
                }
                lift = (float) ((restLow - lowNow) * (1 - air));
                for (int i = 0; i < n; i++) {
                    if (!walking[i]) continue;
                    double need = restLow - (low[i] + lift);
                    if (need > 0) jw[i].y += (float) (need * (1 - air));
                }
            }
            // 윗몸 무리 (다리 아닌 모든 파트): 숨쉬기 + 두 발 몹은 디딘 다리 쪽으로 기울기
            Quaternionf rb = new Quaternionf();
            Vector3f ob = new Vector3f();
            if (breathes) ob.y = (float) (0.02 * wave(t, 40, ph) * gw);
            if (biped) rb.rotateZ(rad(-2.5 * ke * footStance(gp + phaseLeft, duty) * gw
                    + 2.5 * ke * footStance(gp + phaseLeft + 0.5, duty) * gw));
            else if (walkLegs == 0 && breathes && walk > 0) rb.rotateZ(rad(3 * walk * wave(t, 12, ph) * gw));
            for (int i = 0; i < n; i++) {
                if (kind[i] != OTHER) continue;
                place(jw[i], rw[i], rb, centre, 1f, ob);
            }
            // 몸 전체
            Vector3f zero = new Vector3f();
            Vector3f o = new Vector3f(0, lift, 0);
            if (floatGlobal >= 0) o.y += (float) (0.1 * wave(t, 60, ph));
            all(jw, rw, sw, new Quaternionf(), zero, 1f, o);
            if (ov != null) {
                Quaternionf gr = new Quaternionf();
                Vector3f go = new Vector3f();
                float gs = ov.global(gr, go);
                all(jw, rw, sw, gr, zero, gs, go);
            }
            if (s.hurtTicks() >= 0 && s.hurtTicks() < HURT_TICKS) {
                double kh = 1.0 - s.hurtTicks() / (double) HURT_TICKS;
                double sg = ((s.seed() + t - s.hurtTicks()) & 1) == 0 ? 1 : -1;
                all(jw, rw, sw, new Quaternionf().rotationZ(rad(HURT_TILT * kh * sg)), zero, 1f,
                        new Vector3f((float) (HURT_SHIFT * kh * sg), 0, 0));
            }
            float pitch = s.bodyPitch();
            float rise = 0;
            if (s.emergeTicks() >= 0 && s.emergeTicks() < EMERGE_TICKS) {
                rise = -(1f - s.emergeTicks() / (float) EMERGE_TICKS) * (height + 0.2f);
            }
            if (Math.abs(pitch) > 0.01f || rise != 0) {
                all(jw, rw, sw, new Quaternionf().rotationX(rad(pitch)), new Vector3f(0, height * 0.5f, 0), 1f,
                        new Vector3f(0, rise, 0));
            }
            if (s.deathTicks() >= 0) {
                // 사망: 0.6초간 한 덩어리로 기울며 가라앉고 작아짐 (파트 위치도 같은 비율로 → 조각나지 않음)
                double p = Math.min(1.0, s.deathTicks() / (double) DEATH_TICKS);
                float ds = (float) Math.max(0.05, 1 - 0.85 * p);
                all(jw, rw, sw, new Quaternionf().rotationZ(rad(25 * p)), zero, ds, new Vector3f(0, (float) (-0.6 * p), 0));
            }
            Solved[] out = new Solved[n];
            for (int i = 0; i < n; i++) {
                Vector3f origin = rw[i].transform(new Vector3f(toOrigin[i])).mul(sw[i]).add(jw[i]);
                out[i] = new Solved(origin, rw[i], sw[i], new Vector3f());
            }
            return out;
        }

        /** 강체 변환 하나: 관절 위치 J = c + s·q·(J − c) + o, 회전 = q·R. */
        private static void place(Vector3f j, Quaternionf r, Quaternionf q, Vector3f c, float s, Vector3f o) {
            j.sub(c);
            q.transform(j);
            j.mul(s).add(c).add(o);
            r.premul(q);
        }

        private void all(Vector3f[] jw, Quaternionf[] rw, float[] sw, Quaternionf q, Vector3f c, float s, Vector3f o) {
            for (int i = 0; i < n; i++) {
                place(jw[i], rw[i], q, c, s, o);
                sw[i] *= s;
            }
        }

        /** 사슬: 마디 k 의 관절 = 마디 k−1 관절 + (k−1 의 누적 회전)·(원래 관절 차), 회전 = 누적 회전·자기 회전. */
        private void chain(Vector3f[] jw, Quaternionf[] rw, int[] idx) {
            for (int k = 1; k < idx.length; k++) attach(jw, rw, idx[k - 1], idx[k], false);
        }

        private void attach(Vector3f[] jw, Quaternionf[] rw, int parent, int child, boolean rigid) {
            Vector3f rel = new Vector3f(joint[child]).sub(joint[parent]);
            rw[parent].transform(rel);
            jw[child].set(jw[parent]).add(rel);
            if (rigid) rw[child].set(rw[parent]);
            else rw[child].premul(rw[parent]);
        }
    }

    /**
     * Display Transformation 성분 계산.
     * @param yawDeg     몹 yaw (마인크래프트 규칙)
     * @param modelScale 몹 scale (파트 크기 배율)
     * @param pivotX/Y/Z 파트 모델 원점 (블록, scale 1 기준, 몹 로컬)
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
