package kr.labyrinth.items.sell;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;
import kr.labyrinth.items.sell.SellBasket.Press;
import org.junit.jupiter.api.Test;

/** 판매 대기 칸: 합치기·자리·돌려받기·닫힌 뒤 거부·골드 한 번·두 번 확인 + 무작위 조작에서 물건 수가 보존되는지. */
class SellBasketTest {

    /** 테스트용 묶음: id + 개수 (최대 묶음 = id 가 gear 로 시작하면 1, 아니면 64). */
    record Stack(String id, int amount) {}

    static final SellBasket.Stacks<Stack> STACKS = new SellBasket.Stacks<>() {
        @Override
        public int amount(Stack s) { return s.amount(); }

        @Override
        public Stack withAmount(Stack s, int amount) { return new Stack(s.id(), amount); }

        @Override
        public boolean similar(Stack a, Stack b) { return a.id().equals(b.id()); }

        @Override
        public int maxStack(Stack s) { return s.id().startsWith("gear") ? 1 : 64; }
    };

    /** 두 번째 누름은 600ms 뒤부터, 5초 안에 (실제 창은 600ms · 8초). */
    private static SellBasket<Stack> basket(int capacity) { return new SellBasket<>(STACKS, capacity, 600, 5_000); }

    @Test
    void mergesSimilarStacksUpToMaxStack() {
        SellBasket<Stack> b = basket(3);
        assertEquals(40, b.add(new Stack("silk", 40), 3, false));
        assertEquals(30, b.add(new Stack("silk", 30), 3, false));
        assertEquals(2, b.size(), "64 + 6 로 나뉨");
        assertEquals(64, b.entries().get(0).stack().amount());
        assertEquals(6, b.entries().get(1).stack().amount());
        assertEquals(70 * 3, b.total());
        assertEquals(70, b.count());
        // 값이 다르면 합치지 않는다
        assertEquals(1, b.add(new Stack("silk", 1), 4, false));
        assertEquals(3, b.size());
    }

    @Test
    void roomAndAllOrNothingAdd() {
        SellBasket<Stack> b = basket(2);
        assertEquals(128, b.room(new Stack("silk", 1), 2));
        assertEquals(1, b.add(new Stack("gear_a", 1), 100, true));
        assertEquals(64, b.room(new Stack("silk", 1), 2));
        assertEquals(0, b.add(new Stack("silk", 65), 2, false), "다 못 받으면 하나도 안 받는다");
        assertEquals(1, b.size());
        assertEquals(64, b.add(new Stack("silk", 64), 2, false));
        assertEquals(0, b.room(new Stack("gear_b", 1), 100));
        assertEquals(0, b.add(new Stack("gear_b", 1), 100, true));
    }

    @Test
    void removeAndTakeAllReturnEverythingOnce() {
        SellBasket<Stack> b = basket(5);
        b.add(new Stack("silk", 10), 3, false);
        b.add(new Stack("gear_a", 1), 100, true);
        assertEquals(new Stack("gear_a", 1), b.remove(1));
        assertNull(b.remove(1));
        assertNull(b.remove(-1));
        b.add(new Stack("bone", 5), 1, false);
        List<Stack> back = b.takeAll();
        assertEquals(List.of(new Stack("silk", 10), new Stack("bone", 5)), back);
        assertTrue(b.isEmpty());
        assertTrue(b.takeAll().isEmpty());
    }

    @Test
    void closedBasketRefusesEverything() {
        SellBasket<Stack> b = basket(5);
        b.add(new Stack("silk", 10), 3, false);
        assertEquals(List.of(new Stack("silk", 10)), b.close());
        assertTrue(b.close().isEmpty(), "두 번 닫아도 두 번 돌려주지 않는다");
        assertTrue(b.closed());
        assertEquals(0, b.room(new Stack("silk", 1), 3));
        assertEquals(0, b.add(new Stack("silk", 1), 3, false));
        assertEquals(Press.EMPTY, b.press(0));
        assertNull(b.sell());
    }

    @Test
    void sellPaysOnceAndEmpties() {
        SellBasket<Stack> b = basket(5);
        b.add(new Stack("silk", 10), 3, false);
        b.add(new Stack("bone", 4), 5, false);
        assertEquals(Press.SELL, b.press(0));
        SellBasket.Sale<Stack> s = b.sell();
        assertEquals(50, s.total());
        assertEquals(14, s.count());
        assertTrue(b.isEmpty());
        assertNull(b.sell(), "두 번째 판매는 없음 (골드 한 번)");
        assertEquals(Press.EMPTY, b.press(1));
    }

    @Test
    void riskyItemsNeedSecondPressWithinWindow() {
        SellBasket<Stack> b = basket(5);
        b.add(new Stack("silk", 10), 3, false);
        assertFalse(b.needsConfirm());
        b.add(new Stack("gear_epic", 1), 150, true);
        assertTrue(b.needsConfirm());
        assertEquals(Press.ARMED, b.press(1_000));
        assertTrue(b.armed(1_500));
        assertEquals(Press.SELL, b.press(2_000));
        // 시간이 지나면 다시 처음부터
        assertEquals(Press.ARMED, b.press(10_000));
        assertEquals(Press.ARMED, b.press(16_000));
        // 칸이 바뀌면 확인이 풀린다
        b.add(new Stack("silk", 1), 3, false);
        assertFalse(b.armed(16_001));
        assertEquals(Press.ARMED, b.press(16_002));
        b.remove(0);
        assertEquals(Press.ARMED, b.press(16_003));
        assertEquals(Press.SELL, b.press(16_700));
        // 귀한 물건을 빼면 바로 판다
        SellBasket<Stack> c = basket(5);
        c.add(new Stack("gear_epic", 1), 150, true);
        c.add(new Stack("silk", 2), 3, false);
        assertEquals(Press.ARMED, c.press(0));
        c.remove(0);
        assertEquals(Press.SELL, c.press(1));
    }

    /** 빠른 두 번째 누름(연타·더블클릭)은 확인이 아니다 — 대기 시작 시각도 늘리지 않는다. */
    @Test
    void fastSecondPressDoesNotSell() {
        SellBasket<Stack> b = basket(5);
        b.add(new Stack("gear_epic", 1), 150, true);
        assertEquals(Press.ARMED, b.press(1_000));
        assertEquals(Press.ARMED, b.press(1_001), "1ms 뒤 누름 → 팔지 않음");
        assertEquals(Press.ARMED, b.press(1_250), "더블클릭 간격(120~250ms)도 팔지 않음");
        assertEquals(Press.ARMED, b.press(1_599));
        assertFalse(b.isEmpty());
        assertEquals(Press.SELL, b.press(1_600), "첫 누름 뒤 600ms — 연타가 대기 시작을 미루지 않음");
        assertEquals(1, b.sell().count());

        // 연타가 확인 창(5초)을 늘리지도 않는다
        SellBasket<Stack> c = basket(5);
        c.add(new Stack("gear_epic", 1), 150, true);
        assertEquals(Press.ARMED, c.press(0));
        for (long t = 100; t < 600; t += 100) assertEquals(Press.ARMED, c.press(t));
        assertEquals(Press.ARMED, c.press(5_001), "첫 누름 기준 5초가 지나면 다시 처음부터");
        assertEquals(Press.ARMED, c.press(5_002));
        assertEquals(Press.SELL, c.press(5_601));

        // 확인 창이 최소 간격보다 짧게 잡혀도 최소 간격까지는 기다릴 수 있다
        SellBasket<Stack> d = new SellBasket<>(STACKS, 5, 600, 100);
        d.add(new Stack("gear_epic", 1), 150, true);
        assertEquals(Press.ARMED, d.press(0));
        assertEquals(Press.ARMED, d.press(300));
        assertEquals(Press.SELL, d.press(600));

        // 확인이 필요 없으면 바로 판다 (최소 간격과 무관)
        SellBasket<Stack> e = basket(5);
        e.add(new Stack("silk", 3), 2, false);
        assertEquals(Press.SELL, e.press(0));
    }

    /** 무작위로 올리기·빼기·전부 돌려받기·판매를 섞어도 (가방 + 바구니 + 판 것) 개수가 그대로이고 골드 = 판 값 합. */
    @Test
    void randomOperationsConserveItemsAndGold() {
        SplittableRandom rnd = new SplittableRandom(20261015L);
        String[] ids = {"silk", "bone", "gear_a", "gear_b", "ore"};
        Map<String, Integer> price = Map.of("silk", 3, "bone", 5, "gear_a", 100, "gear_b", 250, "ore", 7);
        for (int round = 0; round < 200; round++) {
            Map<String, Integer> bag = new HashMap<>();
            for (String id : ids) bag.put(id, 50 + rnd.nextInt(100));
            Map<String, Integer> start = Map.copyOf(bag);
            Map<String, Integer> sold = new HashMap<>();
            long gold = 0, expectGold = 0;
            SellBasket<Stack> b = basket(1 + rnd.nextInt(6));
            for (int step = 0; step < 80; step++) {
                int op = rnd.nextInt(10);
                if (op < 5) {
                    String id = ids[rnd.nextInt(ids.length)];
                    int have = bag.get(id);
                    if (have <= 0) continue;
                    Stack want = new Stack(id, Math.min(have, 1 + rnd.nextInt(70)));
                    int n = Math.min(want.amount(), b.room(want, price.get(id)));
                    if (n <= 0) continue;
                    bag.merge(id, -n, Integer::sum); // 가방에서 먼저 뺀다
                    int got = b.add(new Stack(id, n), price.get(id), id.startsWith("gear"));
                    assertEquals(n, got);
                } else if (op < 7) {
                    Stack s = b.remove(rnd.nextInt(Math.max(1, b.size() + 1)));
                    if (s != null) bag.merge(s.id(), s.amount(), Integer::sum);
                } else if (op < 8) {
                    for (Stack s : b.takeAll()) bag.merge(s.id(), s.amount(), Integer::sum);
                } else {
                    long expect = b.total();
                    long t = step * 10_000L; // 걸음마다 확인 창(5초)보다 멀리
                    Press p = b.press(t);
                    if (p == Press.ARMED) {
                        assertEquals(Press.ARMED, b.press(t + 1), "1ms 뒤 누름은 확인이 아니다");
                        p = b.press(t + 700);
                    }
                    if (p != Press.SELL) continue;
                    SellBasket.Sale<Stack> sale = b.sell();
                    assertEquals(expect, sale.total());
                    gold += sale.total();
                    expectGold += expect;
                    for (SellBasket.Entry<Stack> e : sale.entries()) sold.merge(e.stack().id(), e.stack().amount(), Integer::sum);
                    assertNull(b.sell());
                }
            }
            for (Stack s : b.close()) bag.merge(s.id(), s.amount(), Integer::sum); // 창 닫기
            assertTrue(b.close().isEmpty());
            long check = 0;
            for (String id : ids) {
                assertEquals((int) start.get(id), bag.get(id) + sold.getOrDefault(id, 0), "round " + round + " " + id);
                check += (long) sold.getOrDefault(id, 0) * price.get(id);
            }
            assertEquals(expectGold, gold);
            assertEquals(check, gold);
        }
    }
}
