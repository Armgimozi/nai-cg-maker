package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

/** 옛 건물 조사 묶기 (R14): 8칸 안끼리 한 무리 · 큰 것부터 · 20곳까지. */
class LegacyClustersTest {

    @Test
    void groupsWithinEight() {
        List<LegacyClusters.Column> cols = new ArrayList<>();
        // 집 A: x 0..4 · z 0..4 (25열 × 4)
        for (int x = 0; x <= 4; x++) for (int z = 0; z <= 4; z++) cols.add(new LegacyClusters.Column(x, z, 4, 70));
        // 8칸 떨어진 헛간 → 같은 무리
        cols.add(new LegacyClusters.Column(12, 0, 10, 70));
        // 멀리 떨어진 탑 (작음)
        cols.add(new LegacyClusters.Column(-100, -100, 3, 80));
        List<LegacyClusters.Cluster> out = LegacyClusters.cluster(cols, 8, 20);
        assertEquals(2, out.size());
        LegacyClusters.Cluster big = out.get(0);
        assertEquals(110, big.blocks());
        assertEquals(26, big.columns());
        assertEquals(0, big.x0());
        assertEquals(12, big.x1());
        assertEquals(3, out.get(1).blocks());
    }

    @Test
    void limitAndEmpty() {
        List<LegacyClusters.Column> cols = new ArrayList<>();
        for (int i = 0; i < 30; i++) cols.add(new LegacyClusters.Column(i * 100, 0, i + 1, 64));
        List<LegacyClusters.Cluster> out = LegacyClusters.cluster(cols, 8, 20);
        assertEquals(20, out.size());
        assertEquals(30, out.get(0).blocks(), "큰 것부터");
        assertEquals(0, LegacyClusters.cluster(List.of(), 8, 20).size());
    }
}
