package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.List;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.UniqueDef;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 안전 검토 1 (0.3.6 부터) — 짧게 당긴 화살을 빠르게 쏘면 고유 효과가 계속 켜짐.
 * <p>3틱만 당겨 놓아도 화살이 나가고(바닐라는 세기 0.1 미만만 막음), 그 화살도 기본 공격이라 고유 효과가 켜졌다. 화살 피해는 세기 배율(최소 0.1)을
 * 받지만 고유 효과의 덧 피해는 무기 한 방 W 기준이라, 0.2초마다 놓으면 휩쓸기(빛 파편)·연타(풀무 연사)·방패 강타가 끝까지 당길 때의 몇 배였다.
 * 고침: 세기 0.9 미만 화살은 고유 효과 없음 ({@link CombatMath#ARROW_UNIQUE_MIN_FORCE}, {@code CombatListener.arrowHit}).
 * <p>시험: 실제 {@link AttackTiming} 으로 '정해 둔 만큼만 당기고 곧바로 다시 당기는' 봇을 돌려 (화살 피해 + 고유 효과 덧 피해) ÷ 시간을 잰다.
 */
class ArrowUniqueSpamTest {

    private static final long TOL = 50;
    private static final long NOCK = Math.round(CombatMath.BOW_NOCK * 1000);
    /** 놓고 다시 누르기까지 손 (ms). */
    private static final long REPRESS = 50;

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    /** 고유 효과 한 번의 덧 피해 (W 배수, 주 대상 말고 맞는 적 수까지) 와 몇 발마다 켜지는가. */
    record Proc(double perProcW, int every) {}

    static Proc proc(UniqueDef u) {
        return switch (u.id()) {
            case "cleave" -> new Proc(u.num("pct") * u.count("targets"), 1); // 주변 적이 다 있을 때 (가장 센 경우)
            case "flurry" -> new Proc(u.num("pct"), u.count("n"));
            case "bash_stun" -> new Proc(u.num("pct"), u.count("n"));
            default -> throw new IllegalArgumentException(u.id());
        };
    }

    /**
     * 봇: 매번 {@code holdMs} 만큼 당겨 놓는다. waitClock = 서버 시계가 셀 때부터 당김 (세기를 다 받음), 아니면 놓자마자 다시 당김 (검토의 연사).
     * 화살 피해 = 세기 × W (keen = 사냥꾼: 끝까지 당긴 화살 +30%), 고유 효과는 세기가 문턱을 넘은 화살만 (gate = false 면 예전처럼 모든 화살)
     * 세어 {@code every} 발마다 덧 피해. @return 초당 W (W = 1)
     */
    static double run(long full, Proc pr, long holdMs, boolean gate, boolean waitClock, boolean keen, int shots) {
        AttackTiming t = new AttackTiming();
        long now = 10_000, start = -1;
        double dmg = 0, startDmg = 0;
        int procCount = 0;
        for (int i = 0; i < shots + 5; i++) {
            if (i == 5) {
                start = now;
                startDmg = dmg;
            }
            long drawStart = waitClock ? Math.max(now + REPRESS, t.nextReady() - TOL) : now + REPRESS;
            long release = drawStart + holdMs;
            long credited = Math.min(full, t.bowDrawnMs(release, holdMs, TOL));
            double force = Math.max(0.1, CombatMath.bowForce(credited / 1000.0, full / 1000.0));
            t.shot(release, holdMs, full, TOL, NOCK);
            dmg += force * (keen && force >= 0.999 ? 1.30 : 1.0);
            if (!gate || CombatMath.arrowProcsUnique(force)) {
                if (++procCount % pr.every() == 0) dmg += pr.perProcW();
            }
            now = release;
        }
        return (dmg - startDmg) / ((now - start) / 1000.0);
    }

    @Test
    void threshold() {
        assertTrue(CombatMath.arrowProcsUnique(1.0));
        assertTrue(CombatMath.arrowProcsUnique(0.9));
        assertFalse(CombatMath.arrowProcsUnique(0.899));
        assertFalse(CombatMath.arrowProcsUnique(0.1075), "3틱 화살");
        // 0.9 = 끝까지 당기는 시간의 약 92%
        double x = -1 + Math.sqrt(1 + 3 * CombatMath.ARROW_UNIQUE_MIN_FORCE);
        assertEquals(0.9235, x, 1e-3);
    }

    @Test
    void shortDrawSpamNoLongerBeatsFullDrawsForCleaveFlurryAndBash() {
        double as = CombatMath.attackSpeed(7, 0);
        for (String id : List.of("prismstring_longbow", "bellows_composite_bow", "springloaded_bow", "pit_bone_bow")) {
            ItemDef bow = content.item(id);
            Proc pr = proc(bow.unique());
            long full = Math.max(1, Math.round(CombatMath.bowDraw(WeaponAttack.of(bow).interval(), as, CombatMath.MIN_INTERVAL) * 1000));
            double fullDraw = run(full, pr, full, true, true, false, 400);
            double spamBefore = run(full, pr, 150, false, false, false, 400);
            double spamNow = run(full, pr, 150, true, false, false, 400);
            if (pr.every() == 1) {
                assertTrue(spamBefore > 2 * fullDraw, id + ": 예전 짧은 연사 " + spamBefore + " vs 끝까지 " + fullDraw + " (검토가 잰 약 4배)");
            }
            assertTrue(spamNow < 0.5 * fullDraw, id + ": 이제 짧은 연사 " + spamNow + " vs 끝까지 " + fullDraw);
            // 어떤 길이로 당겨도 끝까지 당긴 것의 1.09배를 넘지 못한다 (문턱 바로 위에서 연달아 쏘는 경우가 가장 큼 — 사람 손으로는 못 맞춤)
            double best = 0;
            long bestHold = 0;
            for (long hold = 150; hold <= full; hold += 5) {
                double d = Math.max(run(full, pr, hold, true, true, false, 400), run(full, pr, hold, true, false, false, 400));
                if (d > best) {
                    best = d;
                    bestHold = hold;
                }
            }
            assertTrue(best <= fullDraw * 1.09, id + ": 가장 센 당김 " + bestHold + "ms → " + best + " vs 끝까지 " + fullDraw);
        }
    }

    @Test
    void forTheHunterFullDrawIsAlwaysBest() {
        // 사냥꾼 매의 눈: 끝까지(세기 ≥ 0.999) 당긴 화살 +30% → 문턱 바로 위 연사도 끝까지 당기는 것보다 약하다
        double as = CombatMath.attackSpeed(7, 0);
        for (String id : List.of("prismstring_longbow", "bellows_composite_bow", "springloaded_bow", "pit_bone_bow")) {
            ItemDef bow = content.item(id);
            Proc pr = proc(bow.unique());
            long full = Math.max(1, Math.round(CombatMath.bowDraw(WeaponAttack.of(bow).interval(), as, CombatMath.MIN_INTERVAL) * 1000));
            double fullDraw = run(full, pr, full, true, true, true, 400);
            for (long hold = 150; hold < full; hold += 5) {
                double d = Math.max(run(full, pr, hold, true, true, true, 400), run(full, pr, hold, true, false, true, 400));
                assertTrue(d < fullDraw, id + " 사냥꾼: " + hold + "ms → " + d + " vs 끝까지 " + fullDraw);
            }
        }
    }
}
