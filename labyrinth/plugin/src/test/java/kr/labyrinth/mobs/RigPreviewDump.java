package kr.labyrinth.mobs;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import kr.labyrinth.bosses.BossAnim;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.ModelDef;
import kr.labyrinth.core.ContentLoader;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;

/**
 * 오프라인 애니메이션 미리보기용 덤프 (서버 없이 리그 관절 확인). 평소 빌드에서는 돌지 않는다 — 환경 변수 {@code RIG_DUMP} 가
 * 있을 때만:
 * <pre>
 *   RIG_DUMP=/tmp/rig.json RIG_MOBS=floor01_moss_warden,rusted_miner \
 *     ./gradlew test --tests kr.labyrinth.mobs.RigPreviewDump --rerun -q
 * </pre>
 * 몹마다 클립(walk · walk_slow · idle · attack · hurt_death, 보스는 + slam)의 프레임별 파트 Display Transformation(yaw 0, 몹 로컬:
 * +Z 앞 · +Y 위 · +X 몹의 왼쪽) = 이동(블록, 몹 scale 포함) · 왼쪽 회전 쿼터니언 · 균일 크기를 JSON 으로 쓴다.
 * 그림은 {@code tools/rig_preview.py} 가 생성된 파트 모델로 그린다.
 * <p>
 * 일반 몹 = {@link ModelRig#animate} 와 같은 길({@link RigMath.Skeleton#solve} → {@link RigMath#compose}),
 * 보스 = {@code BossRig.animate} 와 같은 계산(기본 anim + {@link BossAnim} 오버레이).
 */
class RigPreviewDump {

    /** 최대 걷기 속도 (블록/틱) — walkFactor 1. */
    static final double FULL_SPEED = 0.18;

    record Frame(String label, RigMath.AnimState state, BossAnim anim, double p, double windup) {}

    /** speed = 이 클립의 이동 속도(블록/틱, 발 미끄럼 계산용), dt = 프레임 사이 틱(GIF 재생 속도). */
    record Clip(String name, List<Frame> frames, double speed, double dt) {}

    @Test
    @EnabledIfEnvironmentVariable(named = "RIG_DUMP", matches = ".+")
    void dump() throws IOException {
        Path out = Path.of(System.getenv("RIG_DUMP"));
        String only = System.getenv().getOrDefault("RIG_MOBS", "");
        Set<String> want = new LinkedHashSet<>();
        for (String s : only.split(",")) if (!s.isBlank()) want.add(s.trim());
        ContentLoader.Result r = ContentLoader.load(Path.of("src/main/resources/content"));
        Content c = r.content();
        StringBuilder sb = new StringBuilder(1 << 20);
        sb.append("{\"meta\":{\"full_speed\":").append(FULL_SPEED)
                .append(",\"frame\":\"mob-local blocks, +Z front, +Y up, +X mob left; t=[tx,ty,tz,qx,qy,qz,qw,s]\"},\"mobs\":{");
        boolean first = true;
        int n = 0;
        for (MobDef m : c.mobs().values()) {
            if (!want.isEmpty() && !want.contains(m.id())) continue;
            if (m.model().parts().isEmpty()) continue;
            first = mob(sb, first, m.id(), false, m.scale(), m.flying(), m.model());
            n++;
        }
        for (BossDef b : c.bosses().values()) {
            if (!want.isEmpty() && !want.contains(b.id())) continue;
            if (b.model().parts().isEmpty()) continue;
            first = mob(sb, first, b.id(), true, b.scale(), b.flying(), b.model());
            n++;
        }
        sb.append("}}\n");
        Files.createDirectories(out.toAbsolutePath().getParent());
        Files.writeString(out, sb.toString(), StandardCharsets.UTF_8);
        System.out.println("rig dump: " + n + " models → " + out);
        assertTrue(n > 0, "덤프할 몹이 없음 (RIG_MOBS 확인)");
    }

    private static RigMath.AnimState st(long tick, double speed, int atk, int arm, int hurt, int death, boolean target,
                                        boolean airborne) {
        return new RigMath.AnimState(tick, speed, atk, arm, -1, hurt, 0f, 0f, death, target, 0L, airborne,
                RigMath.MOTION_NONE, 0f, -1);
    }

    /** 클립 목록 (게임과 같은 입력). 걷기 = 다리 주기 14틱 한 바퀴를 1틱 간격으로 (최대 속도 · 절반 속도). */
    static List<Clip> clips(boolean boss, boolean flying) {
        List<Clip> out = new ArrayList<>();
        int arm = boss ? 2 : 0;
        List<Frame> walk = new ArrayList<>();
        for (int t = 0; t < 14; t++) {
            walk.add(new Frame("t" + t, st(1000 + t, FULL_SPEED, -1, arm, -1, -1, true, flying), BossAnim.NONE, 0, 0));
        }
        out.add(new Clip("walk", walk, FULL_SPEED, 1));
        List<Frame> slow = new ArrayList<>();
        for (int t = 0; t < 14; t++) {
            slow.add(new Frame("t" + t, st(1000 + t, FULL_SPEED * 0.5, -1, arm, -1, -1, true, flying), BossAnim.NONE, 0, 0));
        }
        out.add(new Clip("walk_slow", slow, FULL_SPEED * 0.5, 1));
        List<Frame> idle = new ArrayList<>();
        for (int k = 0; k < 6; k++) {
            idle.add(new Frame("t" + (k * 12), st(1000 + k * 12L, 0, -1, arm, -1, -1, false, flying), BossAnim.NONE, 0, 0));
        }
        out.add(new Clip("idle", idle, 0, 12));
        List<Frame> atk = new ArrayList<>();
        for (int a = 0; a <= RigMath.ATTACK_TICKS + 2; a++) {
            atk.add(new Frame("a" + a, st(1000 + a, 0, a, arm, -1, -1, true, flying), BossAnim.NONE, 0, 0));
        }
        out.add(new Clip("attack", atk, 0, 1));
        List<Frame> hd = new ArrayList<>();
        for (int h = 0; h < RigMath.HURT_TICKS; h++) {
            hd.add(new Frame("h" + h, st(1000 + h, 0, -1, arm, h, -1, true, flying), BossAnim.NONE, 0, 0));
        }
        for (int d = 0; d <= RigMath.DEATH_TICKS; d += 2) {
            hd.add(new Frame("d" + d, st(1010 + d, 0, -1, arm, -1, d, false, flying), BossAnim.NONE, 0, 0));
        }
        out.add(new Clip("hurt_death", hd, 0, 1));
        if (boss) {
            List<Frame> slam = new ArrayList<>();
            for (int k = 0; k <= 10; k++) {
                double p = k / 10.0;
                slam.add(new Frame("p" + k, st(1000 + k * 3L, 0, -1, arm, -1, -1, true, flying), BossAnim.SLAM, p,
                        BossAnim.SLAM.defaultWindup()));
            }
            out.add(new Clip("slam", slam, 0, 3));
        }
        return out;
    }

    private static boolean mob(StringBuilder sb, boolean first, String id, boolean boss, double scale, boolean flying,
                               ModelDef model) {
        if (!first) sb.append(',');
        List<ModelDef.Part> parts = model.parts();
        sb.append('"').append(id).append("\":{\"boss\":").append(boss).append(",\"scale\":").append(f(scale))
                .append(",\"flying\":").append(flying).append(",\"parts\":[");
        for (int i = 0; i < parts.size(); i++) {
            ModelDef.Part p = parts.get(i);
            if (i > 0) sb.append(',');
            sb.append("{\"name\":\"").append(p.name()).append("\",\"form\":\"").append(p.form()).append("\",\"anim\":\"")
                    .append(p.anim()).append("\",\"pivot\":[").append(f(p.pivotX())).append(',').append(f(p.pivotY()))
                    .append(',').append(f(p.pivotZ())).append("],\"size\":[").append(f(p.sizeX())).append(',')
                    .append(f(p.sizeY())).append(',').append(f(p.sizeZ())).append("]}");
        }
        List<Clip> clips = clips(boss, flying);
        sb.append("],\"clip_meta\":{");
        for (int i = 0; i < clips.size(); i++) {
            if (i > 0) sb.append(',');
            sb.append('"').append(clips.get(i).name()).append("\":{\"speed\":").append(f(clips.get(i).speed()))
                    .append(",\"dt\":").append(f(clips.get(i).dt())).append('}');
        }
        sb.append("},\"clips\":{");
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        boolean fc = true;
        for (Clip clip : clips) {
            if (!fc) sb.append(',');
            fc = false;
            sb.append('"').append(clip.name()).append("\":[");
            boolean ff = true;
            for (Frame fr : clip.frames()) {
                if (!ff) sb.append(',');
                ff = false;
                float[][] t = boss ? bossFrame(parts, (float) scale, fr) : mobFrame(sk, (float) scale, fr.state());
                sb.append("{\"label\":\"").append(fr.label()).append("\",\"t\":[");
                for (int i = 0; i < t.length; i++) {
                    if (i > 0) sb.append(',');
                    sb.append('[');
                    for (int k = 0; k < t[i].length; k++) {
                        if (k > 0) sb.append(',');
                        sb.append(f(t[i][k]));
                    }
                    sb.append(']');
                }
                sb.append("]}");
            }
            sb.append(']');
        }
        sb.append("}}");
        return false;
    }

    /** ModelRig.animate 와 같은 계산 (yaw 0, yawOffset 0). */
    static float[][] mobFrame(RigMath.Skeleton sk, float scale, RigMath.AnimState s) {
        RigMath.Solved[] solved = sk.solve(s);
        float[][] out = new float[solved.length][];
        Vector3f tr = new Vector3f();
        Quaternionf left = new Quaternionf();
        for (int i = 0; i < solved.length; i++) {
            RigMath.Solved sp = solved[i];
            RigMath.Pose pose = new RigMath.Pose(sp.offset(), sp.rotation(), sp.scale());
            float k = RigMath.compose(0, scale, sp.pivot().x, sp.pivot().y, sp.pivot().z, pose, 0, tr, left);
            out[i] = new float[] {tr.x, tr.y, tr.z, left.x, left.y, left.z, left.w, k};
        }
        return out;
    }

    /** BossRig.animate 와 같은 계산 (yaw 0, yawOffset 0) — 리그 수학을 고치면 여기도 같이. */
    static float[][] bossFrame(List<ModelDef.Part> parts, float scale, Frame fr) {
        RigMath.AnimState state = fr.state();
        float[][] out = new float[parts.size()][];
        BossAnim.Pose scratch = new BossAnim.Pose();
        for (int i = 0; i < parts.size(); i++) {
            ModelDef.Part part = parts.get(i);
            RigMath.Pose base = RigMath.pose(part.anim(), part.form(), state);
            BossAnim.Pose ov = BossAnim.overlay(fr.anim(), part.anim(), part.name(), fr.p(), fr.windup(), state.tick(), scratch);
            float bw = ov.baseWeight;
            Quaternionf baseRot = new Quaternionf().slerp(base.rotation(), bw);
            Vector3f local = new Vector3f((float) part.pivotX(), (float) part.pivotY(), (float) part.pivotZ())
                    .add(new Vector3f(base.offset()).mul(bw)).add(ov.offset);
            ov.globalRotation.transform(local);
            local.add(ov.globalOffset).mul(scale);
            Quaternionf left = new Quaternionf().mul(ov.globalRotation).mul(ov.rotation).mul(baseRot);
            float s = scale * base.scale() * ov.scale;
            out[i] = new float[] {local.x, local.y, local.z, left.x, left.y, left.z, left.w, s};
        }
        return out;
    }

    private static String f(double v) {
        if (Math.abs(v) < 1e-7) return "0";
        return String.format(Locale.ROOT, "%.5f", v);
    }
}
