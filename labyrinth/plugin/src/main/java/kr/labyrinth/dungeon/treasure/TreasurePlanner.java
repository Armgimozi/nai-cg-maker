package kr.labyrinth.dungeon.treasure;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.SplittableRandom;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.gen.HallStyle;

/**
 * 미로 보물 배치 (순수 로직 — Bukkit 무관, 단위 테스트 대상, GDD §5.6). 같은 층·같은 시드 → 같은 결과.
 * <ol>
 *   <li>열쇠 금고: 막다른 구석(NOOK) 중 시작에서 먼 쪽 하나 — 끝 5×5 칸 앞 복도 줄을 잠긴 문으로 막는다.</li>
 *   <li>막다른 길 끝: {@code dead_end} 확률로 상자 (금 {@code gold} · 철 {@code iron} · 나머지 나무). 미로 굴 안 작은 막다른 길은 {@code minor}.</li>
 *   <li>비밀방 가운데: 금 상자. 금고 안: 금 상자 2~3개.</li>
 *   <li>미믹: 막다른 길 상자(금 제외)의 {@code mimic}. 열쇠: 정예 처치({@code key_from_elite}) 아니면 막다른 길 철 상자 하나.</li>
 *   <li>{@link #upgradeBehindTraps}: 함정을 놓은 뒤, 앞 복도에 함정이 있는 상자는 {@code gold_behind_trap} 확률로 금 상자.</li>
 * </ol>
 */
public final class TreasurePlanner {

    private TreasurePlanner() {}

    public static TreasurePlan plan(FloorLayout l, ChestSettings s, long seed, boolean hasElite) {
        SplittableRandom rng = new SplittableRandom(seed ^ 0x2C1B3C6DL);
        List<FloorLayout.DeadEnd> des = l.deadEnds();
        List<TreasurePlan.Chest> chests = new ArrayList<>();

        // 1. 금고 자리 (먼 막다른 구석 중 앞쪽 절반에서 무작위)
        int vaultDe = -1;
        if (s.vault()) {
            List<Integer> cands = new ArrayList<>();
            for (int i = 0; i < des.size(); i++) {
                FloorLayout.DeadEnd de = des.get(i);
                if (de.secret() >= 0 || de.minor() || l.hallStyle(de.cell()) != HallStyle.NOOK) continue;
                if (l.distance(de.cell()) < 2 || vaultGeometry(l, de) == null) continue;
                cands.add(i);
            }
            if (!cands.isEmpty()) {
                cands.sort((a, b) -> Integer.compare(l.distance(des.get(b).cell()), l.distance(des.get(a).cell())));
                vaultDe = cands.get(rng.nextInt(Math.max(1, (cands.size() + 1) / 2)));
            }
        }

        // 2. 막다른 길 끝
        for (int i = 0; i < des.size(); i++) {
            if (i == vaultDe) continue;
            FloorLayout.DeadEnd de = des.get(i);
            if (de.secret() >= 0) continue; // 금 간 벽 앞은 비워 둔다 (비밀방 안에 금 상자)
            if (l.kind(de.tipX(), de.tipZ()) != FloorLayout.FLOOR || l.elevation(de.tipX(), de.tipZ()) != 0) continue;
            ChestTier tier;
            TreasurePlan.Source src;
            if (de.minor()) {
                if (rng.nextDouble() >= s.minor()) continue;
                tier = rng.nextDouble() < s.iron() * 0.5 ? ChestTier.IRON : ChestTier.WOOD;
                src = TreasurePlan.Source.MINOR;
            } else {
                if (rng.nextDouble() >= s.deadEnd()) continue;
                double r = rng.nextDouble();
                tier = r < s.gold() ? ChestTier.GOLD : r < s.gold() + s.iron() ? ChestTier.IRON : ChestTier.WOOD;
                src = TreasurePlan.Source.DEAD_END;
            }
            chests.add(new TreasurePlan.Chest(chests.size(), de.tipX(), de.tipZ(), de.dirX(), de.dirZ(), tier, src, false, i));
        }

        // 3. 비밀방 가운데 금 상자 (금 간 벽 쪽을 바라봄)
        for (FloorLayout.SecretRoom sr : l.secretRooms()) {
            if (l.kind(sr.centerX(), sr.centerZ()) != FloorLayout.FLOOR) continue;
            FloorLayout.DeadEnd de = sr.deadEnd() >= 0 && sr.deadEnd() < des.size() ? des.get(sr.deadEnd()) : null;
            int dx = de == null ? 0 : de.dirX(), dz = de == null ? -1 : de.dirZ();
            chests.add(new TreasurePlan.Chest(chests.size(), sr.centerX(), sr.centerZ(), dx, dz, ChestTier.GOLD,
                    TreasurePlan.Source.SECRET, false, sr.index()));
        }

        // 4. 미믹 (막다른 길 상자, 금 제외)
        for (int i = 0; i < chests.size(); i++) {
            TreasurePlan.Chest c = chests.get(i);
            boolean deadEnd = c.source() == TreasurePlan.Source.DEAD_END || c.source() == TreasurePlan.Source.MINOR;
            if (deadEnd && c.tier() != ChestTier.GOLD && rng.nextDouble() < s.mimic()) chests.set(i, c.withMimic(true));
        }

        // 5. 열쇠 (정예 아니면 막다른 길 철 상자 하나) → 금고 확정
        TreasurePlan.Vault vault = null;
        int keyChest = -1;
        boolean keyFromElite = false;
        if (vaultDe >= 0) {
            keyFromElite = hasElite && rng.nextDouble() < s.keyFromElite();
            if (!keyFromElite) {
                List<Integer> cands = new ArrayList<>();
                for (TreasurePlan.Chest c : chests) {
                    if (c.source() == TreasurePlan.Source.DEAD_END && !c.mimic()) cands.add(c.index());
                }
                if (!cands.isEmpty()) {
                    keyChest = cands.get(rng.nextInt(cands.size()));
                    TreasurePlan.Chest k = chests.get(keyChest);
                    if (k.tier() == ChestTier.WOOD) chests.set(keyChest, k.withTier(ChestTier.IRON));
                } else {
                    keyFromElite = hasElite;
                }
            }
            if (keyFromElite || keyChest >= 0) {
                int n = 2 + (rng.nextDouble() < 0.5 ? 1 : 0);
                vault = vaultGeometry(l, des.get(vaultDe));
                List<Integer> inside = new ArrayList<>();
                for (int[] at : vaultChestTiles(des.get(vaultDe), n)) {
                    FloorLayout.DeadEnd de = des.get(vaultDe);
                    inside.add(chests.size());
                    chests.add(new TreasurePlan.Chest(chests.size(), at[0], at[1], de.dirX(), de.dirZ(), ChestTier.GOLD,
                            TreasurePlan.Source.VAULT, false, -1));
                }
                vault = new TreasurePlan.Vault(vault.deadEnd(), vault.doorX(), vault.doorZ(), vault.door(), vault.minX(), vault.minZ(),
                        vault.maxX(), vault.maxZ(), vault.dirX(), vault.dirZ(), inside);
            } else {
                keyFromElite = false;
            }
        }
        return new TreasurePlan(chests, vault, keyChest, keyFromElite);
    }

    /** 복도를 가로지르는 단위 방향 (dir 에 수직, 양수 축). */
    static int[] perp(int dx, int dz) { return new int[] {dz != 0 ? 1 : 0, dx != 0 ? 1 : 0}; }

    /**
     * NOOK 막다른 길 끝을 금고로 쓸 수 있으면 문·범위 (상자 목록은 비움), 아니면 null.
     * 조건: 끝 칸 ±2 (5×5) 가 모두 평평한 복도 바닥, 끝에서 복도 쪽 3칸 줄의 가운데 ±1 이 바닥이고 ±2 는 걸을 수 없음(벽·도랑).
     */
    static TreasurePlan.Vault vaultGeometry(FloorLayout l, FloorLayout.DeadEnd de) {
        int tx = de.tipX(), tz = de.tipZ(), dx = de.dirX(), dz = de.dirZ();
        if (Math.abs(dx) + Math.abs(dz) != 1) return null;
        for (int z = tz - 2; z <= tz + 2; z++) {
            for (int x = tx - 2; x <= tx + 2; x++) {
                if (l.kind(x, z) != FloorLayout.FLOOR || l.region(x, z) >= 0 || l.elevation(x, z) != 0) return null;
            }
        }
        int[] p = perp(dx, dz);
        int cx = tx + 3 * dx, cz = tz + 3 * dz;
        for (int k = -1; k <= 1; k++) {
            int x = cx + k * p[0], z = cz + k * p[1];
            if (l.kind(x, z) != FloorLayout.FLOOR || l.region(x, z) >= 0 || l.elevation(x, z) != 0) return null;
        }
        for (int k : new int[] {-2, 2}) {
            if (l.walkable(cx + k * p[0], cz + k * p[1])) return null;
        }
        List<Integer> door = new ArrayList<>();
        for (int k = -2; k <= 2; k++) {
            int x = cx + k * p[0], z = cz + k * p[1];
            byte kind = l.kind(x, z);
            if (kind == FloorLayout.FLOOR || kind == FloorLayout.GUTTER) door.add(FloorLayout.pack(x, z));
        }
        return new TreasurePlan.Vault(-1, cx, cz, door.stream().mapToInt(Integer::intValue).toArray(), tx - 2, tz - 2, tx + 2, tz + 2,
                dx, dz, List.of());
    }

    /** 금고 안 금 상자 칸: 안쪽 벽 줄(끝 칸에서 복도 반대쪽 2칸) 위 n 개. */
    static List<int[]> vaultChestTiles(FloorLayout.DeadEnd de, int n) {
        int[] p = perp(de.dirX(), de.dirZ());
        int bx = de.tipX() - 2 * de.dirX(), bz = de.tipZ() - 2 * de.dirZ();
        int[] ks = n >= 3 ? new int[] {-2, 0, 2} : new int[] {-1, 1};
        List<int[]> out = new ArrayList<>();
        for (int k : ks) out.add(new int[] {bx + k * p[0], bz + k * p[1]});
        return out;
    }

    /**
     * 함정 배치 뒤: 막다른 길 상자(금·미믹 제외)의 앞 복도(끝에서 2~8칸, 폭 ±1)에 함정 칸이 있으면 gold_behind_trap 확률로 금 상자.
     * trapTiles = 함정 칸 (packed).
     */
    public static TreasurePlan upgradeBehindTraps(TreasurePlan p, Set<Integer> trapTiles, ChestSettings s, long seed) {
        if (trapTiles.isEmpty() || s.goldBehindTrap() <= 0) return p;
        SplittableRandom rng = new SplittableRandom(seed ^ 0x51ED270BL);
        List<TreasurePlan.Chest> out = new ArrayList<>(p.chests());
        for (int i = 0; i < out.size(); i++) {
            TreasurePlan.Chest c = out.get(i);
            if (c.source() != TreasurePlan.Source.DEAD_END || c.mimic() || c.tier() == ChestTier.GOLD) continue;
            if (behindTrap(c, trapTiles) && rng.nextDouble() < s.goldBehindTrap()) out.set(i, c.withTier(ChestTier.GOLD));
        }
        return new TreasurePlan(out, p.vault(), p.keyChest(), p.keyFromElite());
    }

    /** 상자 앞 복도(2~8칸, 폭 ±1)에 함정 칸이 있나. */
    public static boolean behindTrap(TreasurePlan.Chest c, Set<Integer> trapTiles) {
        int[] pp = perp(c.dirX(), c.dirZ());
        for (int k = 2; k <= 8; k++) {
            for (int w = -1; w <= 1; w++) {
                int x = c.x() + k * c.dirX() + w * pp[0], z = c.z() + k * c.dirZ() + w * pp[1];
                if (trapTiles.contains(FloorLayout.pack(x, z))) return true;
            }
        }
        return false;
    }
}
