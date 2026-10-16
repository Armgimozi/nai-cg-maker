package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

/** 수확은 가방에 바로 — 다 들어갈 자리가 없으면 캐지지도 비워지지도 않는다 (계약 §2.3). */
class BagFitTest {

    static List<BagFit.Slot> bag(int empty, BagFit.Slot... filled) {
        List<BagFit.Slot> s = new ArrayList<>(List.of(filled));
        for (int i = 0; i < empty; i++) s.add(new BagFit.Slot(null, 0, 64));
        return s;
    }

    @Test
    void stacksIntoSameItemFirst() {
        List<BagFit.Slot> full = bag(0, new BagFit.Slot("ore", 63, 64), new BagFit.Slot("x", 64, 64));
        assertTrue(BagFit.fits(full, List.of(new BagFit.Add("ore", 1, 64))));
        assertFalse(BagFit.fits(full, List.of(new BagFit.Add("ore", 2, 64))), "덤 +1 이면 자리 없음");
        assertFalse(BagFit.fits(full, List.of(new BagFit.Add("gem", 1, 64))));
    }

    @Test
    void oreAndGemTogether() {
        List<BagFit.Slot> one = bag(1, new BagFit.Slot("x", 64, 64));
        assertTrue(BagFit.fits(one, List.of(new BagFit.Add("ore", 3, 64))));
        assertFalse(BagFit.fits(one, List.of(new BagFit.Add("ore", 3, 64), new BagFit.Add("gem", 1, 64))), "광석 + 보석 = 두 칸");
        assertTrue(BagFit.fits(bag(2), List.of(new BagFit.Add("ore", 3, 64), new BagFit.Add("gem", 1, 64))));
    }

    @Test
    void emptyBagAndZero() {
        assertTrue(BagFit.fits(bag(36), List.of(new BagFit.Add("ore", 1, 64))));
        assertTrue(BagFit.fits(bag(0), List.of(new BagFit.Add("ore", 0, 64))));
        assertFalse(BagFit.fits(bag(0), List.of(new BagFit.Add("ore", 1, 64))));
    }
}
