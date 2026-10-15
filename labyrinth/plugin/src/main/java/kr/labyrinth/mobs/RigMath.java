package kr.labyrinth.mobs;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.content.ModelDef;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 모델 리그 절차적 애니메이션 수학 (GDD §14.3 anim 표 + §14.6 좌표 규칙). Bukkit 무관 — 단위 테스트 대상.
 * <p>
 * 몹 로컬 좌표: +Z = 앞, +Y = 위, +X = 몹의 왼쪽. 파트 피벗(블록, scale 1 기준)은 모델 중심(8,8,8)에 대응하고,
 * {@link #compose} 가 몹 yaw·scale 을 곱해 Display Transformation(앵커 = 몹 발 위치 기준)을 만든다.
 * <p>
 * 파트끼리 붙어 움직이는 규칙({@link Skeleton}): 목(neck) 사슬 → 머리(head) → 머리 무리(anim head 인 다른 파트·턱 jaw),
 * 꼬리 사슬(tail_chain). 나머지 파트는 자기 피벗에서 따로 돈다.
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
     * airborne = 날거나 공중에 뜸(날개 퍼덕임), motion = {@link #MOTION_NONE}…, bodyPitch = 몸 전체 앞숙임(도, + = 머리 아래),
     * emergeTicks = 땅속에서 솟구친 뒤 지난 틱(-1 = 없음).
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
     * anim 키별 자세 계산 (side·사슬 순서가 필요 없는 호출 — 보스 리그).
     * @param anim body | head | legs_walk | arm_left | arm_right | wings | wings_flap | tail | tail_chain | neck | jaw |
     *             spin | orbit | float | pulse | static
     * @param form 파트 form (다리 종류에 따라 걷기 모양을 다르게)
     */
    public static Pose pose(String anim, String form, AnimState s) {
        return pose(anim, form, s, 0, 0);
    }

    /**
     * @param side  파트 피벗 X 부호 (+1 = 몹의 왼쪽, −1 = 오른쪽, 0 = 가운데) — wings_flap 의 좌우
     * @param chain 사슬 안 순서 (0 = 뿌리) — tail_chain·neck 의 물결 지연
     */
    public static Pose pose(String anim, String form, AnimState s, int side, int chain) {
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
                scale = 1f;
                off.y = (float) (0.04 * flap);
            }
            case "tail" -> rot.rotateY(rad(20 * wave(t, 30, ph) + (walk > 0 ? 8 * wave(t, 10, ph) : 0)));
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
     * 한쪽 날개(wings_flap): side = 피벗 X 부호. 날 때 위아래 퍼덕임, 날아오를 때 크고 빠르게, 급강하 때 뒤로 접음,
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

    // ── 파트 계층 (목·머리·꼬리 사슬) ─────────────────────────────────────

    /** 파트 하나의 풀이 결과: 피벗 위치(블록, scale 1, 몹 로컬)·회전·크기·이동. */
    public record Solved(Vector3f pivot, Quaternionf rotation, float scale, Vector3f offset) {}

    /**
     * 모델 파트의 붙음 관계 (리그 생성 때 한 번 만들고 매 갱신 {@link #solve}).
     * <ul>
     *   <li>anim {@code neck} 파트들 = YAML 순서대로 사슬(뿌리 → 머리 쪽). 머리 yaw/pitch 의 절반을 목 마디가 나눠 돈다.</li>
     *   <li>이름이 {@code head} 이고 anim 이 head 인 파트 = 머리. 목이 있으면 마지막 목 마디 끝에 붙는다.</li>
     *   <li>머리 무리: 머리가 있을 때 anim 이 head 인 다른 파트(뿔·가면·등불 — 머리와 같은 회전)와 jaw 파트(머리 회전 + 벌림)는
     *       머리 피벗을 중심으로 함께 돈다.</li>
     *   <li>anim {@code tail_chain} 파트들 = YAML 순서대로 사슬(뿌리 → 끝). 마디마다 앞 마디 끝에 붙어 휜다.</li>
     *   <li>몸 전체: bodyPitch(급강하 앞숙임)는 모델 높이 중간을 중심으로, emerge(솟구침)는 바닥 아래에서 올라오는 이동.</li>
     * </ul>
     */
    public static final class Skeleton {
        private final List<ModelDef.Part> parts;
        private final int head;
        private final int[] neck;
        private final int[] tail;
        private final int[] side;
        private final int[] chainIndex;
        private final boolean[] headGroup;
        private final float height;

        public Skeleton(List<ModelDef.Part> parts) {
            this.parts = List.copyOf(parts);
            int n = this.parts.size();
            side = new int[n];
            chainIndex = new int[n];
            headGroup = new boolean[n];
            int h = -1;
            List<Integer> nk = new ArrayList<>();
            List<Integer> tl = new ArrayList<>();
            float top = 0;
            for (int i = 0; i < n; i++) {
                ModelDef.Part p = this.parts.get(i);
                side[i] = p.pivotX() > 1e-4 ? 1 : p.pivotX() < -1e-4 ? -1 : 0;
                if ("neck".equals(p.anim())) {
                    chainIndex[i] = nk.size();
                    nk.add(i);
                }
                if ("tail_chain".equals(p.anim())) {
                    chainIndex[i] = tl.size();
                    tl.add(i);
                }
                if (h < 0 && "head".equals(p.name()) && "head".equals(p.anim())) h = i;
                top = Math.max(top, (float) (p.pivotY() + p.sizeY() / 32.0));
            }
            head = h;
            if (h >= 0) {
                for (int i = 0; i < n; i++) {
                    String a = this.parts.get(i).anim();
                    if (i != h && ("head".equals(a) || "jaw".equals(a))) headGroup[i] = true;
                }
            }
            neck = nk.stream().mapToInt(Integer::intValue).toArray();
            tail = tl.stream().mapToInt(Integer::intValue).toArray();
            height = Math.max(0.5f, top);
        }

        public int size() { return parts.size(); }

        public ModelDef.Part part(int i) { return parts.get(i); }

        /** 모델 높이(블록, scale 1) — 솟구침·앞숙임 기준. */
        public float height() { return height; }

        /** 지금 상태의 모든 파트 자세. */
        public Solved[] solve(AnimState s) {
            int n = parts.size();
            Solved[] out = new Solved[n];
            AnimState headState = s;
            AnimState neckState = s;
            if (neck.length > 0 && head >= 0) {
                float share = 0.5f / neck.length;
                neckState = s.withHead(s.headYaw() * share, s.headPitch() * share);
                headState = s.withHead(s.headYaw() * 0.5f, s.headPitch() * 0.5f);
            }
            for (int i = 0; i < n; i++) {
                ModelDef.Part p = parts.get(i);
                AnimState st = "neck".equals(p.anim()) ? neckState : headGroup[i] || i == head ? headState : s;
                Pose pose = pose(p.anim(), p.form(), st, side[i], chainIndex[i]);
                out[i] = new Solved(new Vector3f((float) p.pivotX(), (float) p.pivotY(), (float) p.pivotZ()),
                        new Quaternionf(pose.rotation()), pose.scale(), new Vector3f(pose.offset()));
            }
            chain(out, neck);
            if (head >= 0) {
                if (neck.length > 0) attach(out, neck[neck.length - 1], head, false);
                for (int i = 0; i < n; i++) {
                    if (!headGroup[i]) continue;
                    // anim head 인 장식은 머리와 같은 회전(자기 회전은 버림), 턱은 머리 회전 위에 벌림
                    attach(out, head, i, "head".equals(parts.get(i).anim()));
                }
            }
            chain(out, tail);
            float pitch = s.bodyPitch();
            float lift = 0;
            if (s.emergeTicks() >= 0 && s.emergeTicks() < EMERGE_TICKS) {
                lift = -(1f - s.emergeTicks() / (float) EMERGE_TICKS) * (height + 0.2f);
            }
            if (Math.abs(pitch) > 0.01f || lift != 0) {
                Quaternionf q = new Quaternionf().rotationX(rad(pitch));
                Vector3f c = new Vector3f(0, height * 0.5f, 0);
                for (Solved o : out) {
                    Vector3f rel = new Vector3f(o.pivot()).sub(c);
                    q.transform(rel);
                    o.pivot().set(rel.add(c)).add(0, lift, 0);
                    o.rotation().premul(q);
                }
            }
            return out;
        }

        /** 사슬: 마디 k 의 피벗 = 마디 k−1 피벗 + (k−1 의 누적 회전)·(원래 피벗 차), 회전 = 누적 회전·자기 회전. */
        private void chain(Solved[] out, int[] idx) {
            for (int k = 1; k < idx.length; k++) attach(out, idx[k - 1], idx[k], false);
        }

        private void attach(Solved[] out, int parent, int child, boolean rigid) {
            ModelDef.Part pp = parts.get(parent), cp = parts.get(child);
            Vector3f rel = new Vector3f((float) (cp.pivotX() - pp.pivotX()), (float) (cp.pivotY() - pp.pivotY()),
                    (float) (cp.pivotZ() - pp.pivotZ()));
            out[parent].rotation().transform(rel);
            out[child].pivot().set(out[parent].pivot()).add(rel);
            if (rigid) out[child].rotation().set(out[parent].rotation());
            else out[child].rotation().premul(out[parent].rotation());
        }
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
