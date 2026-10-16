package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 손맛 검토 1 — 근접 한 대 뒤의 활 당김: 화면과 서버가 같은가.
 * <p>새 시계({@link AttackTiming})는 근접 한 대 뒤 그 무기 간격이 끝나야 당김을 센다. 예전(검토 전)에는 그사이 당긴 것을 조용히 세지 않아,
 * 활로 직접 치고 곧바로 1초 당겨 놓으면 화면에는 끝까지 당겨졌는데 세기 0.00~0.17 화살이 나갔다 (라이브 3/3 과녁에 못 닿음).
 * 고침: 그 시간만큼 활에 바닐라 재사용 대기(하얀 막대)를 걸어 당기기를 막는다 ({@code AttackClock.gateBow}) — 대기가 끝나야 손님이
 * 당기기 시작할 수 있으므로, 당기기 시작한 때부터 끝까지 당기는 시간이 지나면 서버도 끝까지 센다.
 * <p>아래 시험의 '손님': 재사용 대기 틱이 끝나기 전에는 당길 수 없고(바닐라 클라이언트), 끝나면 곧바로 당기기 시작한다.
 */
class BowGateTest {

    private static final long TOL = 50;
    private static final long NOCK = Math.round(CombatMath.BOW_NOCK * 1000);
    private static final double MIN = CombatMath.MIN_INTERVAL;
    private static final UUID A = UUID.randomUUID();

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    private static long ms(double s) { return Math.max(1, Math.round(s * 1000.0)); }

    /** 활의 끝까지 당김(ms)·한 발 주기(ms), 근접 무기의 간격(ms). */
    private static long full(ItemDef bow, double as) { return ms(CombatMath.bowDraw(WeaponAttack.of(bow).interval(), as, MIN)); }

    private static long cycle(ItemDef def, double as) { return ms(CombatMath.cycle(WeaponAttack.of(def), as, MIN)); }

    /** 이 때 건 재사용 대기가 끝나는 때 (손님이 당기기 시작할 수 있는 가장 이른 때). 대기를 안 걸면 지금. */
    private static long gateEnd(AttackTiming t, long now) {
        return now + 50L * AttackClock.gateTicks(t.drawBlockedMs(now, TOL));
    }

    /** 당기기 시작한 때부터 끝까지 당기는 시간이 지났을 때 서버가 센 당김 (ms). */
    private static long serverDrawnAtVisualFull(AttackTiming t, long drawStart, long full) {
        return Math.min(full, t.bowDrawnMs(drawStart + full, full, TOL));
    }

    @Test
    void gateTicksRoundUpAndSkipTinyWaits() {
        assertEquals(0, AttackClock.gateTicks(0));
        assertEquals(0, AttackClock.gateTicks(-300));
        assertEquals(0, AttackClock.gateTicks(AttackClock.GATE_MIN_MS), "한 틱 이하는 걸지 않음 (잃는 당김 ≤ 50ms)");
        assertEquals(2, AttackClock.gateTicks(51), "올림 — 대기가 끝난 뒤 당기면 다 센다");
        assertEquals(2, AttackClock.gateTicks(100));
        assertEquals(22, AttackClock.gateTicks(1_100));
    }

    @Test
    void afterHittingWithTheBowTheBowWaitsVisiblyThenDrawsFully() {
        // 회랑 장궁 (시작 활), Lv1 사냥꾼 민첩 5
        double as = CombatMath.attackSpeed(5, 0);
        ItemDef bow = content.item("corridor_longbow");
        long full = full(bow, as), bowCycle = cycle(bow, as);
        AttackTiming t = new AttackTiming();
        long hit = 10_000;
        assertEquals(AttackTiming.Result.ACCEPT, t.click(hit, bowCycle, TOL, 0, A, "bow"));
        long blocked = t.drawBlockedMs(hit, TOL);
        assertEquals(bowCycle - TOL, blocked, "활로 친 뒤 = 활 한 발 주기 − 허용 오차 동안 당김을 못 셈");
        long start = gateEnd(t, hit);
        assertTrue(start - hit >= blocked && start - hit < blocked + 50, "하얀 막대 = 그 시간 (틱 올림)");
        assertEquals(full, serverDrawnAtVisualFull(t, start, full), "막대가 끝난 뒤 당기면 화면의 끝까지 = 서버의 끝까지");
        assertEquals(1.0, CombatMath.bowForce(serverDrawnAtVisualFull(t, start, full) / 1000.0, full / 1000.0), 1e-9);
        // 검토가 잰 경우: 막지 않으면 치고 곧바로(0.05초) 당겨 1.0초에 놓은 화살 = 세기 0.17 이하
        long early = hit + 50, release = early + 1_000;
        double weak = CombatMath.bowForce(t.bowDrawnMs(release, 1_000, TOL) / 1000.0, full / 1000.0);
        assertTrue(weak < 0.2, "막지 않았다면 세기 " + weak);
        assertTrue(early < start, "그래서 그때는 당기기를 막는다");
    }

    @Test
    void afterAStabThenSwapTheBowDrawsFullyFromTheMomentItCanBeDrawn() {
        // 단도로 찌르고 0~간격 사이 아무 때나 활로 바꿈 → 바꾼 때 건 대기가 끝난 뒤 당기면 언제나 끝까지
        double as = CombatMath.attackSpeed(7, 0);
        for (String bowId : List.of("corridor_longbow", "grove_rootstring_bow", "prismstring_longbow")) {
            ItemDef bow = content.item(bowId);
            long full = full(bow, as), bowCycle = cycle(bow, as);
            for (String meleeId : List.of("moss_dirk", "corridor_longbow")) {
                ItemDef melee = content.item(meleeId);
                long interval = cycle(melee, as);
                for (long delay = 0; delay <= interval + 100; delay += 10) {
                    AttackTiming t = new AttackTiming();
                    long hit = 20_000;
                    assertEquals(AttackTiming.Result.ACCEPT, t.click(hit, interval, TOL, 0, A, meleeId));
                    long swapAt = hit + delay;
                    t.swap(swapAt, bowCycle, AttackClock.SWAP_DELAY_FRACTION, full);
                    long start = gateEnd(t, swapAt);
                    long drawn = serverDrawnAtVisualFull(t, start, full);
                    if (AttackClock.gateTicks(t.drawBlockedMs(swapAt, TOL)) > 0) {
                        assertEquals(full, drawn, bowId + " ← " + meleeId + " " + delay + "ms 뒤 바꿈: 막대 뒤 당김 = 끝까지");
                    } else {
                        assertTrue(drawn >= full - AttackClock.GATE_MIN_MS, "대기를 안 걸 만큼 짧으면 잃는 당김 ≤ 한 틱: " + drawn);
                    }
                    // 당기기 시작한 때 → 서버가 끝까지 센 때 (검토 제안 시험): 언제나 ≥ 끝까지 당기는 시간, 대기를 걸었으면 정확히 그만큼
                    long serverFull = Math.max(start + full, t.nextReady() - TOL + full);
                    assertTrue(t.bowDrawnMs(serverFull, serverFull - start, TOL) >= full);
                    assertTrue(t.bowDrawnMs(serverFull - 1, serverFull - 1 - start, TOL) < full);
                    assertTrue(serverFull - start >= full);
                    assertTrue(serverFull - start <= full + AttackClock.GATE_MIN_MS, bowId + " ← " + meleeId + ": " + (serverFull - start));
                }
            }
        }
    }

    @Test
    void afterAShotNothingIsGatedSoTheBowRhythmIsUnchanged() {
        // 쏜 직후 다시 메기기 0.15초는 예전처럼 막지 않는다 (사람 손으로 다시 누르는 데 걸리는 시간 안) — 활만 쓸 때 하얀 막대가 깜빡이지 않게
        AttackTiming t = new AttackTiming();
        long full = 1_000;
        t.shot(5_000, full, full, TOL, NOCK);
        assertEquals(NOCK - TOL, t.drawBlockedMs(5_000, TOL));
        assertEquals(2, AttackClock.gateTicks(t.drawBlockedMs(5_000, TOL)),
                "값으로는 2틱이지만 AttackClock 은 쏜 뒤에는 대기를 걸지 않는다 (근접 한 대·무기 바꿈 뒤에만)");
        // 0.15초 뒤 당기기 시작 → 끝까지
        assertEquals(full, serverDrawnAtVisualFull(t, 5_000 + NOCK - TOL, full));
    }

    @Test
    void theGateNeverOpensAFasterBowAndMeleeCycle() {
        // 막대는 보여 주기·막기일 뿐 시계는 그대로 — 활로 치기 + 끝까지 당긴 화살 한 바퀴 = 활 주기 × 2 (예전과 같음)
        double as = CombatMath.attackSpeed(5, 0);
        ItemDef bow = content.item("corridor_longbow");
        long full = full(bow, as), bowCycle = cycle(bow, as);
        AttackTiming t = new AttackTiming();
        long hit = 30_000;
        assertEquals(AttackTiming.Result.ACCEPT, t.click(hit, bowCycle, TOL, 0, A, "bow"));
        long start = gateEnd(t, hit);
        long release = start + full;
        t.shot(release, full, full, TOL, NOCK);
        long next = t.nextReady() - TOL; // 다음 근접이 되는 가장 이른 때
        assertTrue(next - hit >= 2 * bowCycle - 2 * TOL - 1, "한 바퀴 " + (next - hit) + "ms ≥ 활 주기 × 2");
    }
}
