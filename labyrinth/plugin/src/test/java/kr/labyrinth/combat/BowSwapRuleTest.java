package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;
import java.util.UUID;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Range;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 주인 결정 3 — 쏜 직후 다른 무기로 바꾸면 0.2초만 기다리고, 그래도 활+근접 번갈아 쓰기가 한 무기만 쓴 것보다 세지지 않는다.
 * <p>규칙 ({@link AttackTiming}): 공격마다 제 시간을 쓰고 겹치지 않는다 — 근접 한 대 = 친 뒤 그 무기 간격, 화살 한 발 = 쏘기 전
 * 끝까지 당기는 시간 + 쏜 뒤 다시 메기기 0.15초, 무기를 바꾸면 새 무기의 첫 공격은 바꾼 때 + 새 주기 × 0.5 뒤부터.
 * <p>증명: 번갈아 쓰는 한 바퀴의 시간 ≥ (당김 + 0.15초) + 근접 간격 = 활 한 발 주기 + 근접 간격 이고, 한 바퀴 피해 = 화살 + 근접.
 * (a + b) ÷ (c + d) 는 a ÷ c 와 b ÷ d 사이에 있으므로 번갈아 쓴 초당 피해는 두 무기 초당 피해 중 큰 쪽을 넘지 못한다.
 * 아래 시험은 실제 {@link AttackTiming} 으로 '될 수 있는 가장 이른 때마다 공격하는' 봇을 돌려 이것을 확인한다.
 */
class BowSwapRuleTest {

    private static final long TOL = 50;
    private static final long NOCK = Math.round(CombatMath.BOW_NOCK * 1000);
    private static final double MIN = CombatMath.MIN_INTERVAL;
    private static final UUID A = UUID.randomUUID();
    /** 사냥꾼 매의 눈 (끝까지 당긴 화살 +30%) — 활에 가장 좋은 경우. */
    private static final double KEEN_EYE = 1.30;

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    /** 무기 하나의 시계 숫자 (ms) 와 한 방 피해. 근접·시전은 full = 0. */
    record W(String id, long cycle, long full, double dmg) {
        double dps() { return dmg / cycle; }
    }

    private static long ms(double s) { return Math.max(1, Math.round(s * 1000.0)); }

    /** AttackClock 과 같은 셈: 근접 = 간격 ÷ (1 + 공속), 활 = 끝까지 당김 + 0.15초. */
    static W weapon(ItemDef def, double attackSpeed, double bowMult) {
        WeaponAttack a = WeaponAttack.of(def);
        Range r = def.stats().get("damage");
        double mid = r == null ? 1 : r.lerp(0.5);
        if (a.ranged()) {
            long full = ms(CombatMath.bowDraw(a.interval(), attackSpeed, MIN));
            return new W(def.id(), full + NOCK, full, mid * bowMult);
        }
        return new W(def.id(), ms(CombatMath.meleeInterval(a.interval(), attackSpeed, MIN)), 0, mid);
    }

    /**
     * 봇: 화살 {@code shots} 발 → 근접 {@code hits} 대 → … 를 되풀이하며, 될 수 있는 가장 이른 때 공격한다 (허용 오차까지 다 씀).
     * 활은 손에 들자마자 당기기 시작하고 끝까지 당겨지는 첫 순간 놓는다. 무기를 바꾸면 react ms 뒤에야 다음 입력을 넣는다.
     * @return 되풀이 {@code reps} 바퀴 (처음 2바퀴는 버림) 의 초당 피해 (피해 / ms)
     */
    static double run(W bow, W melee, int shots, int hits, long react, int reps) {
        AttackTiming t = new AttackTiming();
        boolean holdingBow = true;
        long now = 10_000;
        double dmg = 0;
        long startAt = -1;
        double startDmg = 0;
        for (int rep = 0; rep < reps + 2; rep++) {
            if (rep == 2) {
                startAt = now;
                startDmg = dmg;
            }
            for (int i = 0; i < shots; i++) {
                if (!holdingBow) {
                    t.swap(now, bow.cycle(), AttackClock.SWAP_DELAY_FRACTION, bow.full());
                    holdingBow = true;
                    now += react;
                }
                long drawStart = now;
                // 끝까지 당겨지는 첫 순간 = 바닐라 당긴 시간도, 서버가 센 시간(허용 오차 포함)도 끝까지
                long release = Math.max(drawStart + bow.full(), t.nextReady() + bow.full() - TOL);
                assertTrue(t.bowDrawnMs(release, release - drawStart, TOL) >= bow.full(), "놓는 때 끝까지 당겨짐");
                if (release - 1 >= drawStart) {
                    assertTrue(t.bowDrawnMs(release - 1, release - 1 - drawStart, TOL) < bow.full(), "그보다 1ms 이르면 덜 당겨짐");
                }
                t.shot(release, release - drawStart, bow.full(), TOL, NOCK);
                dmg += bow.dmg();
                now = release;
            }
            for (int j = 0; j < hits; j++) {
                if (holdingBow) {
                    t.swap(now, melee.cycle(), AttackClock.SWAP_DELAY_FRACTION);
                    holdingBow = false;
                    now += react;
                }
                long click = Math.max(now, t.nextReady() - TOL);
                if (click - 1 >= now) {
                    assertNotEquals(AttackTiming.Result.ACCEPT, probe(t, click - 1, melee.cycle()), "그보다 1ms 이르면 막힘");
                }
                assertEquals(AttackTiming.Result.ACCEPT, t.click(click, melee.cycle(), TOL, 0, A, "melee"));
                dmg += melee.dmg();
                now = click;
            }
        }
        return (dmg - startDmg) / (now - startAt);
    }

    /** 클릭이 통과할지 (상태를 바꾸지 않는 사본으로). */
    private static AttackTiming.Result probe(AttackTiming t, long at, long interval) {
        AttackTiming copy = new AttackTiming();
        copy.swap(t.nextReady(), 0, 0); // 빈 시계에 nextReady 만 옮김 (swap 은 max)
        return copy.click(at, interval, TOL, 0, A, "probe");
    }

    // ── 주인 결정 3: 0.2초 ───────────────────────────────────────────────

    @Test
    void afterAShotTheDaggerWaitsAboutPointTwoSeconds() {
        // Lv5 사냥꾼 (민첩 7 → 공속 0.035), 뿌리시위 파수궁 → 이끼 단도
        double as = CombatMath.attackSpeed(7, 0);
        W bow = weapon(content.item("grove_rootstring_bow"), as, KEEN_EYE);
        W dirk = weapon(content.item("moss_dirk"), as, 1);
        AttackTiming t = new AttackTiming();
        long shotAt = 5_000;
        t.shot(shotAt, bow.full(), bow.full(), TOL, NOCK);
        t.swap(shotAt, dirk.cycle(), AttackClock.SWAP_DELAY_FRACTION);
        long wait = t.nextReady() - shotAt;
        assertEquals(Math.round(dirk.cycle() * 0.5), wait, "max(다시 메기기 0.15초, 단도 간격 × 0.5)");
        assertTrue(wait >= 200 && wait <= 230, "약 0.2초: " + wait + "ms");
        assertEquals(AttackTiming.Result.ACCEPT, t.click(shotAt + wait, dirk.cycle(), TOL, 0, A, "dirk"));
        // 예전(0.3.6) 규칙은 활 한 발 주기를 다 기다렸다 (0.81~1.09초)
        assertTrue(bow.cycle() - TOL > 800, "예전 대기 " + (bow.cycle() - TOL) + "ms");
        // 그다음 찌르기들은 단도 박자 그대로 (멈칫 없음)
        assertEquals(shotAt + wait + dirk.cycle(), t.nextReady());
    }

    @Test
    void meleeThenBowDrawCountsAfterTheMeleeInterval() {
        double as = CombatMath.attackSpeed(7, 0);
        W bow = weapon(content.item("grove_rootstring_bow"), as, KEEN_EYE);
        W dirk = weapon(content.item("moss_dirk"), as, 1);
        AttackTiming t = new AttackTiming();
        assertEquals(AttackTiming.Result.ACCEPT, t.click(1_000, dirk.cycle(), TOL, 0, A, "dirk"));
        t.swap(1_050, bow.cycle(), AttackClock.SWAP_DELAY_FRACTION, bow.full());
        assertEquals(1_000 + dirk.cycle(), t.nextReady(), "활로 바꿔도 당김은 단도 간격이 끝난 뒤부터 (바꿈 대기는 당김 안에 든다)");
        long drawStart = 1_060;
        assertEquals(0, t.bowDrawnMs(1_000 + dirk.cycle() - TOL, 1_000 + dirk.cycle() - TOL - drawStart, TOL));
        long full = 1_000 + dirk.cycle() + bow.full();
        assertEquals(bow.full(), t.bowDrawnMs(full, full - drawStart, 0), "끝까지 = 단도 간격 + 당김");
    }

    @Test
    void singleWeaponRhythmIsUnchanged() {
        double as = CombatMath.attackSpeed(7, 0);
        for (String id : List.of("corridor_longbow", "mossvine_hornbow", "grove_rootstring_bow", "moss_bone_bow")) {
            W bow = weapon(content.item(id), as, KEEN_EYE);
            assertEquals(bow.dps(), run(bow, bow, 1, 0, 0, 40), bow.dps() * 1e-9, id + ": 활만 = 한 발 주기마다 한 발 (예전과 같음)");
        }
        W dirk = weapon(content.item("moss_dirk"), as, 1);
        AttackTiming t = new AttackTiming();
        long first = -1, last = 0;
        for (int i = 0; i < 50; i++) {
            long c = Math.max(last, t.nextReady() - TOL);
            assertEquals(AttackTiming.Result.ACCEPT, t.click(c, dirk.cycle(), TOL, 0, A, "d"));
            if (first < 0) first = c;
            last = c;
        }
        assertEquals(49 * dirk.cycle(), last - first, TOL, "단도만 = 간격마다 한 대");
    }

    // ── 번갈아 쓰기가 더 센 무기 하나를 넘지 못함 ─────────────────────────

    @Test
    void alternatingBowAndAnyWeaponNeverBeatsTheBetterWeapon() {
        List<ItemDef> bows = new ArrayList<>(), others = new ArrayList<>();
        for (ItemDef d : content.items().values()) {
            if (!d.isWeapon() || d.stats().get("damage") == null) continue;
            (WeaponAttack.of(d).ranged() ? bows : others).add(d);
        }
        assertTrue(bows.size() >= 30 && others.size() >= 150, "활 " + bows.size() + " · 그 밖 " + others.size());
        int[][] patterns = {{1, 1}, {1, 2}, {2, 1}, {1, 3}, {3, 1}, {2, 3}};
        long[] reacts = {0, 60, 150};
        double[] speeds = {0, CombatMath.attackSpeed(7, 0), 0.30, CombatMath.CAP_ATTACK_SPEED};
        double[] bowMults = {1.0, KEEN_EYE};
        int runs = 0;
        double worst = 0;
        String worstCase = "";
        for (double as : speeds) {
            for (double bm : bowMults) {
                for (ItemDef bd : bows) {
                    W bow = weapon(bd, as, bm);
                    for (ItemDef od : others) {
                        W other = weapon(od, as, 1);
                        double best = Math.max(bow.dps(), other.dps());
                        for (int[] pat : patterns) {
                            for (long react : reacts) {
                                double alt = run(bow, other, pat[0], pat[1], react, 6);
                                runs++;
                                double ratio = alt / best;
                                if (ratio > worst) {
                                    worst = ratio;
                                    worstCase = bd.id() + " " + pat[0] + ":" + pat[1] + " " + od.id() + " 공속 " + as + " 손 " + react + "ms";
                                }
                                if (alt > best * (1 + 1e-9)) {
                                    fail("번갈아 " + bd.id() + "×" + pat[0] + " + " + od.id() + "×" + pat[1]
                                            + " 공속 " + as + " 손 " + react + "ms: " + alt * 1000 + " > " + best * 1000);
                                }
                            }
                        }
                    }
                }
            }
        }
        assertTrue(runs > 100_000, "경우 " + runs);
        assertTrue(worst <= 1 + 1e-9, "가장 가까운 경우 " + worst + " (" + worstCase + ")");
        System.out.println("[BowSwapRuleTest] 번갈아 쓰기 " + runs + "경우, 가장 가까운 경우 = 센 무기의 " + String.format("%.6f", worst)
                + "배 (" + worstCase + ")");
    }

    @Test
    void alternatingCycleIsAtLeastTheSumOfBothCycles() {
        // 피해 숫자와 상관없는 시간 규칙: 서로 다른 간격 값 모두 (활 한 발 주기 + 근접 간격 ≤ 한 바퀴)
        TreeSet<Double> bowIntervals = new TreeSet<>(), meleeIntervals = new TreeSet<>();
        for (ItemDef d : content.items().values()) {
            if (!d.isWeapon()) continue;
            WeaponAttack a = WeaponAttack.of(d);
            (a.ranged() ? bowIntervals : meleeIntervals).add(a.interval());
        }
        meleeIntervals.add(WeaponAttack.UNARMED.interval());
        for (double as : new double[] {-0.5, 0, 0.035, 0.45, 0.75}) {
            for (double bi : bowIntervals) {
                long full = ms(CombatMath.bowDraw(bi, as, MIN));
                W bow = new W("bow" + bi, full + NOCK, full, 1.0);
                for (double mi : meleeIntervals) {
                    W melee = new W("m" + mi, ms(CombatMath.meleeInterval(mi, as, MIN)), 0, 1.0);
                    for (long react : new long[] {0, 50}) {
                        // 피해 1·1 이면 초당 피해 = 2 ÷ 한 바퀴 → 한 바퀴 = 2 ÷ 초당 피해
                        double lap = 2.0 / run(bow, melee, 1, 1, react, 8);
                        assertTrue(lap >= bow.cycle() + melee.cycle() - 1e-6,
                                "활 " + bi + " · 근접 " + mi + " · 공속 " + as + ": 한 바퀴 " + lap + " < " + (bow.cycle() + melee.cycle()));
                    }
                }
            }
        }
    }

    @Test
    void weakArrowsInsideAMeleeIntervalAreNotFree() {
        // 큰 무기로 치고 바로 활로 바꿔, 그 큰 무기 간격 안에 덜 당긴 화살을 마구 쏘기 → 화살마다 다시 메기기 0.15초가 시계를 민다
        AttackTiming t = new AttackTiming();
        long hit = 10_000, interval = 1_050;
        assertEquals(AttackTiming.Result.ACCEPT, t.click(hit, interval, TOL, 0, A, "greatsword"));
        t.swap(hit + 20, 1_150, AttackClock.SWAP_DELAY_FRACTION, 1_000);
        long before = t.nextReady();
        int arrows = 0;
        for (long now = hit + 170; now < hit + interval; now += 150) {
            long drawn = t.bowDrawnMs(now, 150, TOL);
            assertEquals(0, drawn, "근접 간격 안 → 세기 0 (최소 피해 0.1 배)");
            long prev = t.nextReady();
            t.shot(now, 150, 1_000, TOL, NOCK);
            assertEquals(prev + NOCK, t.nextReady(), "약한 화살 한 발 = 시계 +0.15초");
            arrows++;
        }
        assertEquals(before + arrows * NOCK, t.nextReady());
        // 0.1 배 화살이 0.15초씩 = 활 한 방의 초당 0.67배 — 끝까지 당긴 화살(초당 1 ÷ 1.15 = 0.87배, 사냥꾼 1.13배)보다 약하다
        assertTrue(0.1 / NOCK < 1.0 / 1_150);
    }

    @Test
    void randomPlayNeverBeatsTheBetterWeapon() {
        // 아무렇게나 바꾸고·치고·당기고·놓는 봇 (덜 당긴 화살, 근접 간격 안의 화살, 활로 직접 치기, 기억한 클릭 포함):
        // 긴 시간 동안의 피해 ≤ 더 센 무기의 초당 피해 × 시간 (+ 마지막 한 주기 몫)
        double as = CombatMath.attackSpeed(7, 0);
        List<String[]> pairs = List.of(
                new String[] {"grove_rootstring_bow", "moss_dirk"}, new String[] {"corridor_longbow", "moss_dirk"},
                new String[] {"moss_bone_bow", "corridor_katar"}, new String[] {"mossvine_hornbow", "moss_dirk"},
                new String[] {"tempest_bow", "mainspring_dagger"}, new String[] {"frostbone_longbow", "eclipse_blade"});
        java.util.Random rng = new java.util.Random(361);
        double worst = 0;
        for (String[] pair : pairs) {
            ItemDef bd = content.item(pair[0]), md = content.item(pair[1]);
            assertNotNull(bd, pair[0]);
            assertNotNull(md, pair[1]);
            W bow = weapon(bd, as, 1.0), melee = weapon(md, as, 1);
            double rawBow = bow.dmg();
            double best = Math.max(Math.max(rawBow * KEEN_EYE / bow.cycle(), melee.dps()), rawBow * BowMelee.DEFAULT_MULT / bow.cycle());
            for (int ep = 0; ep < 150; ep++) {
                AttackTiming t = new AttackTiming();
                boolean holdingBow = rng.nextBoolean();
                long drawStart = -1, first = -1;
                double dmg = 0;
                long end = 120_000;
                long now = 0;
                while (now < end) {
                    now += 5 + rng.nextInt(rng.nextBoolean() ? 30 : 200);
                    if (t.bufferReady(now)) { // 기억한 근접이 들어감
                        t.fireBuffered(now, holdingBow ? bow.cycle() : melee.cycle(), TOL);
                        dmg += holdingBow ? rawBow * BowMelee.DEFAULT_MULT : melee.dmg();
                        if (first < 0) first = now;
                    }
                    int a = rng.nextInt(12);
                    if (a == 0) { // 바꿈
                        holdingBow = !holdingBow;
                        drawStart = -1;
                        if (holdingBow) t.swap(now, bow.cycle(), AttackClock.SWAP_DELAY_FRACTION, bow.full());
                        else t.swap(now, melee.cycle(), AttackClock.SWAP_DELAY_FRACTION);
                    } else if (holdingBow && drawStart >= 0) {
                        if (a <= 4) { // 놓기 (아무 때나)
                            long used = now - drawStart;
                            long drawn = t.bowDrawnMs(now, used, TOL);
                            double force = CombatMath.bowForce(drawn / 1000.0, bow.full() / 1000.0);
                            t.shot(now, used, bow.full(), TOL, NOCK);
                            dmg += rawBow * Math.max(0.1, force) * (force >= 0.999 ? KEEN_EYE : 1.0);
                            if (first < 0) first = now;
                            drawStart = -1;
                        }
                    } else if (holdingBow) {
                        if (a <= 8) drawStart = now; // 당기기 시작
                        else if (t.click(now, bow.cycle(), TOL, 350, A, "bow") == AttackTiming.Result.ACCEPT) { // 활로 직접 치기
                            dmg += rawBow * BowMelee.DEFAULT_MULT;
                            if (first < 0) first = now;
                        }
                    } else if (t.click(now, melee.cycle(), TOL, 350, A, "melee") == AttackTiming.Result.ACCEPT) {
                        dmg += melee.dmg();
                        if (first < 0) first = now;
                    }
                }
                if (first < 0) continue;
                double cap = best * (now - first + bow.cycle() + melee.cycle()) + Math.max(rawBow * KEEN_EYE, melee.dmg());
                worst = Math.max(worst, dmg / (best * (now - first)));
                assertTrue(dmg <= cap, pair[0] + " + " + pair[1] + " 판 " + ep + ": " + dmg + " > " + cap);
            }
        }
        System.out.println("[BowSwapRuleTest] 아무렇게나 쓰기: 가장 센 판 = 센 무기 초당 피해의 " + String.format("%.3f", worst) + "배");
    }

    @Test
    void shootingThenHittingWithTheSameBowIsWeakerThanShootingOnly() {
        // 활로 직접 치기(주인 결정 2: 피해 절반)는 활 한 발 주기를 쓴다 — 쏘고 바로 치고 다시 당겨도 쏘기만 한 것보다 약하다
        double as = CombatMath.attackSpeed(7, 0);
        for (String id : List.of("corridor_longbow", "grove_rootstring_bow", "moss_bone_bow", "tempest_bow")) {
            ItemDef def = content.item(id);
            W bow = weapon(def, as, KEEN_EYE);
            W poke = new W(id + "_melee", bow.cycle(), 0, def.stats().get("damage").lerp(0.5) * BowMelee.DEFAULT_MULT);
            double alt = runSameBow(bow, poke, 12);
            assertTrue(alt < bow.dps(), id + ": 쏘기+치기 " + alt * 1000 + " ≥ 쏘기만 " + bow.dps() * 1000);
        }
    }

    /** 같은 활로 쏘기 한 발 + 직접 치기 한 대 번갈아 (무기를 바꾸지 않음). */
    private static double runSameBow(W bow, W poke, int reps) {
        AttackTiming t = new AttackTiming();
        long now = 10_000;
        double dmg = 0;
        long startAt = -1;
        double startDmg = 0;
        for (int rep = 0; rep < reps + 2; rep++) {
            if (rep == 2) {
                startAt = now;
                startDmg = dmg;
            }
            long drawStart = now;
            long release = Math.max(drawStart + bow.full(), t.nextReady() + bow.full() - TOL);
            t.shot(release, release - drawStart, bow.full(), TOL, NOCK);
            dmg += bow.dmg();
            now = release;
            long click = Math.max(now, t.nextReady() - TOL);
            assertEquals(AttackTiming.Result.ACCEPT, t.click(click, poke.cycle(), TOL, 0, A, "bow"));
            dmg += poke.dmg();
            now = click;
        }
        return (dmg - startDmg) / (now - startAt);
    }
}
