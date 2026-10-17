package kr.labyrinth.bosses;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import kr.labyrinth.bosses.impl.Floor08Math;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.Test;

/** 8층 잉크 사서 오르벨: 금서 색인 서열(공개·입력·벌칙·시간), 깃펜 부채, 책장 배치, 분신 자리·소멸, YAML 키. */
class Floor08LogicTest {

    // ── 서열 (Sequence) ──────────────────────────────────────────────────

    @Test
    void sequenceLengthFollowsGddFormula() {
        // 4 + floor((n−1)/3), 최대 7
        assertEquals(4, Sequence.length(4, 3, 7, 1));
        assertEquals(4, Sequence.length(4, 3, 7, 3));
        assertEquals(5, Sequence.length(4, 3, 7, 4));
        assertEquals(6, Sequence.length(4, 3, 7, 7));
        assertEquals(7, Sequence.length(4, 3, 7, 10));
        assertEquals(7, Sequence.length(4, 1, 7, 10)); // 상한
    }

    @Test
    void generatedSequenceUsesDistinctShelvesWhenItFits() {
        Random rng = new Random(8);
        for (int trial = 0; trial < 200; trial++) {
            int[] s = Sequence.generate(8, 7, rng);
            assertEquals(7, s.length);
            Set<Integer> seen = new HashSet<>();
            for (int v : s) {
                assertTrue(v >= 0 && v < 8);
                assertTrue(seen.add(v), "같은 책장이 두 번: " + java.util.Arrays.toString(s));
            }
        }
        // 기호보다 길면 바로 앞과만 다르면 된다
        int[] longer = Sequence.generate(3, 12, rng);
        for (int i = 1; i < longer.length; i++) assertNotEquals(longer[i - 1], longer[i]);
    }

    @Test
    void revealLightsOneRuneAtATimeThenOpensInput() {
        int[] order = {5, 2, 7, 0};
        // 시작 100틱, 대기 50, 간격 20, 빛 15, 제한 400, 벌칙 100
        Sequence q = new Sequence(order, 100, 50, 20, 15, 400, 100);
        assertEquals(150, q.revealStart());
        assertEquals(230, q.inputStart());
        assertEquals(630, q.deadline());
        assertEquals(-1, q.litIndex(149));
        assertEquals(0, q.litIndex(150));
        assertEquals(0, q.revealStep(150));
        assertEquals(-1, q.revealStep(151));
        assertEquals(0, q.litIndex(164));
        assertEquals(-1, q.litIndex(165)); // 꺼진 틈
        assertEquals(1, q.litIndex(170));
        assertEquals(3, q.revealStep(210));
        assertEquals(Sequence.State.REVEAL, q.update(229));
        // 공개 중 입력은 무시 (벌칙 없음)
        assertEquals(Sequence.Result.IGNORED, q.input(5, 200));
        assertEquals(0, q.wrongs());
        assertEquals(Sequence.State.INPUT, q.update(230));
        assertEquals(-1, q.litIndex(230));
    }

    @Test
    void inputAdvancesIgnoresRepeatsAndCompletes() {
        Sequence q = new Sequence(new int[]{3, 1, 4}, 0, 0, 10, 8, 200, 40);
        long t = q.inputStart();
        assertEquals(Sequence.Result.ADVANCE, q.input(3, t));
        // 같은 책장 연타(다단 히트) = 무시
        assertEquals(Sequence.Result.IGNORED, q.input(3, t + 1));
        assertEquals(1, q.progress());
        assertEquals(Sequence.Result.ADVANCE, q.input(1, t + 2));
        assertEquals(Sequence.Result.COMPLETE, q.input(4, t + 3));
        assertEquals(Sequence.State.SUCCESS, q.state());
        assertTrue(q.finished());
        // 끝난 뒤 입력은 무시
        assertEquals(Sequence.Result.IGNORED, q.input(2, t + 4));
    }

    @Test
    void wrongResetsProgressCutsTimeAndHasGrace() {
        Sequence q = new Sequence(new int[]{0, 1, 2, 3}, 0, 0, 10, 8, 400, 100);
        long t = q.inputStart(); // 40
        assertEquals(440, q.deadline());
        q.input(0, t);
        q.input(1, t + 1);
        assertEquals(2, q.progress());
        assertEquals(Sequence.Result.WRONG, q.input(5, t + 2));
        assertEquals(0, q.progress());
        assertEquals(340, q.deadline()); // −5초
        assertEquals(1, q.wrongs());
        // 틀린 직후 0.5초 = 무시 (광역기 한 번에 벌칙 중복 방지)
        assertEquals(Sequence.Result.IGNORED, q.input(6, t + 2 + Sequence.WRONG_GRACE_TICKS - 1));
        assertEquals(1, q.wrongs());
        // 처음부터 다시
        assertEquals(Sequence.Result.ADVANCE, q.input(0, t + 2 + Sequence.WRONG_GRACE_TICKS));
        assertEquals(1, q.progress());
    }

    @Test
    void timeoutAndPenaltyCanFail() {
        Sequence q = new Sequence(new int[]{0, 1}, 0, 0, 10, 8, 100, 60);
        long t = q.inputStart(); // 20, 마감 120
        assertEquals(Sequence.State.INPUT, q.update(119));
        assertEquals(Sequence.State.FAILED, q.update(120));

        Sequence r = new Sequence(new int[]{0, 1}, 0, 0, 10, 8, 100, 60);
        assertEquals(Sequence.Result.WRONG, r.input(1, t + 50)); // 마감 120 → 60, 지금 70 → 실패
        assertEquals(Sequence.State.FAILED, r.state());
        assertEquals(0, r.remaining(t + 50));

        Sequence s = new Sequence(new int[]{0, 1}, 0, 0, 10, 8, 100, 60);
        assertEquals(100, s.remaining(0)); // 입력 전엔 전체
        s.abort();
        assertEquals(Sequence.State.FAILED, s.state());
    }

    // ── 깃펜 부채·책장 배치·분신 ─────────────────────────────────────────

    @Test
    void quillFanIsSymmetricAndSpansSpread() {
        assertArrayEquals(new double[]{-20, -10, 0, 10, 20}, Floor08Math.fanOffsets(5, 40), 1e-9);
        assertArrayEquals(new double[]{-15, 0, 15}, Floor08Math.fanOffsets(3, 30), 1e-9);
        assertArrayEquals(new double[]{0}, Floor08Math.fanOffsets(1, 40), 1e-9);
        double[] r = Floor08Math.rotate(1, 0, 90);
        assertEquals(0, r[0], 1e-9);
        assertEquals(1, r[1], 1e-9);
        // 부채의 바깥 두 갈래 사이 각 = spread
        double[] a = Floor08Math.rotate(0, 1, -20), b = Floor08Math.rotate(0, 1, 20);
        double ang = Math.toDegrees(Math.acos(a[0] * b[0] + a[1] * b[1]));
        assertEquals(40, ang, 1e-6);
        // 깃펜 선 판정: 길이 18 폭 0.9 — 선 위 / 옆으로 0.5 벗어남
        assertTrue(BossMath.inLine(0, 0, r[0], r[1], 18, 0.9, 0, 10));
        assertFalse(BossMath.inLine(0, 0, r[0], r[1], 18, 0.9, 0.5, 10));
    }

    @Test
    void shelvesAvoidEntranceAndStairsAndFaceInward() {
        double[] angs = Floor08Math.shelfAngles(8);
        assertEquals(8, angs.length);
        for (double a : angs) {
            assertTrue(BossMath.angleGap(a, 270) >= Floor08Math.SHELF_MARGIN_DEG, "입구 앞 책장: " + a);
            assertTrue(BossMath.angleGap(a, 90) >= Floor08Math.SHELF_MARGIN_DEG, "계단 앞 책장: " + a);
            int[] in = Floor08Math.inwardCardinal(a);
            assertEquals(1, Math.abs(in[0]) + Math.abs(in[1]));
            // 중심 쪽을 향함: 바깥 방향과 내적 < 0
            assertTrue(in[0] * BossMath.ax(a) + in[1] * BossMath.az(a) < 0, "책장이 바깥을 봄: " + a);
            // 반경 13 책장 + 2칸 앞 히트박스 모두 남쪽 계단 구역 밖
            assertFalse(BossMath.inStairZone(BossMath.ax(a) * 13, BossMath.az(a) * 13, 2.5));
            assertFalse(BossMath.inStairZone(BossMath.ax(a) * 13 + in[0] * 1.5, BossMath.az(a) * 13 + in[1] * 1.5, 2.5));
        }
        for (int i = 1; i < angs.length; i++) assertTrue(BossMath.angleGap(angs[i], angs[i - 1]) > 40);
    }

    @Test
    void doublesSplitEvenlyAndDispelAtFivePercent() {
        double[] s = Floor08Math.splitAngles(3, 10);
        assertArrayEquals(new double[]{10, 100, 190, 280}, s, 1e-9);
        assertEquals(1, Floor08Math.splitAngles(0, 0).length);
        Random rng = new Random(3);
        int[] hits = new int[4];
        for (int i = 0; i < 4000; i++) hits[Floor08Math.realSlot(4, rng)]++;
        for (int h : hits) assertTrue(h > 800, "진짜 자리 편향: " + java.util.Arrays.toString(hits));
        assertFalse(Floor08Math.dispelled(2499, 50_000, 0.05));
        assertTrue(Floor08Math.dispelled(2500, 50_000, 0.05));
        // 분신 수 2 + floor((n−1) × 0.34), 최대 5 (+ 난이도 추가)
        Params p = Params.of(java.util.Map.of("count_base", 2, "count_per_member", 0.34, "max", 5));
        assertEquals(2, new MechanicScaling(1, "normal", 2, false).count(p, "count", 2, 5));
        assertEquals(3, new MechanicScaling(4, "normal", 2, false).count(p, "count", 2, 5));
        assertEquals(5, new MechanicScaling(10, "normal", 2, false).count(p, "count", 2, 5));
        assertEquals(5, new MechanicScaling(10, "nightmare", 2, false).count(p, "count", 2, 5));
        assertEquals(3, new MechanicScaling(1, "nightmare", 2, false).count(p, "count", 2, 5));
    }

    @Test
    void runePitchesAreDistinctAndPlayable() {
        Set<Float> seen = new HashSet<>();
        for (int i = 0; i < 8; i++) {
            float f = Floor08Math.runePitch(i);
            assertTrue(f >= 0.5f && f <= 2.0f, "음 높이 범위: " + f);
            assertTrue(seen.add(f));
            if (i > 0) assertTrue(f > Floor08Math.runePitch(i - 1));
        }
        assertEquals(3, Floor08Math.inkDrops(3, 0, 12));
        assertEquals(1, Floor08Math.inkDrops(0, 0, 12));
        assertEquals(12, Floor08Math.inkDrops(10, 4, 12));
        assertEquals("<g>◆◆<d>◇◇◇", Floor08Math.pips(2, 5, "<g>", "<d>"));
        assertEquals("<d>◇◇◇◇", Floor08Math.pips(0, 4, "<g>", "<d>"));
        assertEquals("<g>◆◆◆", Floor08Math.pips(9, 3, "<g>", "<d>"));
    }

    // ── YAML ─────────────────────────────────────────────────────────────

    @Test
    void floor08YamlMatchesImplementation() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        BossDef d = c.bosses().get("floor08_ink_librarian");
        assertEquals(8, d.floor());
        assertEquals("puzzle_phase", d.core());
        assertEquals(List.of(1.0, 0.7, 0.4), d.phases());
        Set<String> implemented = Set.of("ink_lash", "quill_barrage", "forbidden_index", "ink_doubles", "erasure", "answer");
        for (String k : d.patterns().keySet()) assertTrue(implemented.contains(k), "패턴 미구현: " + k);
        for (List<String> rot : d.rotation().values()) for (String k : rot) assertTrue(d.patterns().containsKey(k), "rotation 키: " + k);
        // 금서 색인 = 페이즈 트리거 (rotation 에 없음, cooldown/interval 없음)
        for (List<String> rot : d.rotation().values()) assertFalse(rot.contains("forbidden_index"));
        Params fi = d.pattern("forbidden_index");
        assertEquals(20, fi.scaled("time_limit", 4, 0), 1e-9);
        assertEquals(25, fi.scaled("time_limit", 1, 0), 1e-9);
        assertEquals(List.of(2, 3), fi.list("trigger_phases"));
        assertTrue(d.rotation().get(3).contains("erasure"));
        assertFalse(d.rotation().get(1).contains("ink_doubles"));
        // fx 모델: 룬 8개 + 그림자·인장·투사체
        for (int i = 1; i <= 8; i++) assertTrue(c.fxModels().containsKey("rune_" + i), "rune_" + i);
        for (String m : List.of("ink_shadow", "index_glyph", "proj_quill", "proj_ink", "telegraph_cone", "telegraph_mechanic")) {
            assertTrue(c.fxModels().containsKey(m), m);
        }
        for (String line : List.of("intro", "phase2", "phase3", "death", "index_wrong", "index_success", "index_fail", "doubles", "doubles_gone")) {
            assertTrue(d.line(line) != null && !d.line(line).isBlank(), "대사 " + line);
        }
    }
}
