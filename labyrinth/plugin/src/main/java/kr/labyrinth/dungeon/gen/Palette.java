package kr.labyrinth.dungeon.gen;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;
import kr.labyrinth.core.Log;
import org.bukkit.Material;
import org.bukkit.block.data.BlockData;

/**
 * floors.yml palette → 블록. 목록 앞쪽일수록 자주(가중치 1/(i+1)). 알 수 없는 이름은 경고 후 대체 블록.
 * 키: floor · wall · ceiling · accent · light · secret(비밀 통로 금 간 벽) · stairs(계단 복도).
 */
public final class Palette {

    private final Map<String, List<Material>> lists = new java.util.HashMap<>();
    private final Map<String, double[]> cumulative = new java.util.HashMap<>();

    public Palette(Map<String, List<String>> raw) {
        put("floor", raw.get("floor"), Material.STONE_BRICKS);
        put("wall", raw.get("wall"), Material.STONE_BRICKS);
        put("ceiling", raw.get("ceiling"), Material.STONE_BRICKS);
        put("accent", raw.get("accent"), Material.CHISELED_STONE_BRICKS);
        put("light", raw.get("light"), Material.LANTERN);
        // 비밀 통로 금 간 벽 — 그 층 벽과 살짝 다른 블록 (floors.yml palette.secret, 없으면 금 간 석재 벽돌)
        put("secret", raw.get("secret"), Material.CRACKED_STONE_BRICKS);
        // 계단 복도 — 계단 블록 (palette.stairs, 계단이 아니면 석재 벽돌 계단)
        put("stairs", raw.get("stairs"), Material.STONE_BRICK_STAIRS);
    }

    /** 계단 복도에 쓸 계단 블록 (목록 첫 번째가 계단이 아니면 석재 벽돌 계단). */
    public Material stairs() {
        for (Material m : lists.get("stairs")) {
            try {
                if (m.createBlockData() instanceof org.bukkit.block.data.type.Stairs) return m;
            } catch (Throwable ignored) {
                // 서버 없이(단위 테스트) 부를 때
            }
        }
        return Material.STONE_BRICK_STAIRS;
    }

    private void put(String key, List<String> names, Material fallback) {
        List<Material> out = new ArrayList<>();
        if (names != null) {
            for (String n : names) {
                Material m = Material.matchMaterial(n);
                if (m == null || !m.isBlock()) {
                    Log.warnOnce("palette:" + n, "[미궁] floors.yml palette 의 알 수 없는 블록 '" + n + "' → " + fallback + " 로 대체");
                    continue;
                }
                out.add(m);
            }
        }
        if (out.isEmpty()) out.add(fallback);
        lists.put(key, out);
        double[] c = new double[out.size()];
        double sum = 0;
        for (int i = 0; i < out.size(); i++) {
            sum += 1.0 / (i + 1);
            c[i] = sum;
        }
        for (int i = 0; i < c.length; i++) c[i] /= sum;
        cumulative.put(key, c);
    }

    public Material pick(String key, SplittableRandom rng) {
        List<Material> l = lists.get(key);
        double[] c = cumulative.get(key);
        double r = rng.nextDouble();
        for (int i = 0; i < c.length; i++) if (r <= c[i]) return l.get(i);
        return l.get(l.size() - 1);
    }

    public Material first(String key) { return lists.get(key).get(0); }

    public List<Material> all(String key) { return lists.get(key); }

    public BlockData data(String key, SplittableRandom rng) { return pick(key, rng).createBlockData(); }

    /** 천장·벽에 박을 수 있는 꽉 찬 발광 블록 (없으면 null). */
    public Material solidLight() {
        for (Material m : lists.get("light")) if (m.isOccluding()) return m;
        return null;
    }

    /** 매달 수 있는 랜턴류 (없으면 null). */
    public Material hangingLight() {
        for (Material m : lists.get("light")) {
            if (m.createBlockData() instanceof org.bukkit.block.data.Hangable) return m;
        }
        return null;
    }
}
