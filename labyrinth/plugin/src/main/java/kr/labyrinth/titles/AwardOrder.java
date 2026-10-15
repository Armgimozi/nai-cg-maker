package kr.labyrinth.titles;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 파티 사건(층 돌파 · 보스 처치)에서 칭호를 받을 한 사람을 고르는 순서 (순수 로직, 단위 테스트 대상).
 * 그 보스에게 가장 많은 피해를 준 사람 먼저 → 피해가 같으면 막타 친 사람 → 그다음 원래 파티 순서.
 * 피해 기록이 전혀 없으면(대체 보스 등) 막타 → 파티 순서. 칭호마다 이 순서로 조건을 채운 첫 사람이 주인이 된다.
 */
public final class AwardOrder {

    private AwardOrder() {}

    /**
     * @param members 사건에 낀 사람 (원래 순서 — 파티장·입장 순)
     * @param damage  이번 전투에서 그 보스에게 준 피해 (없으면 빈 맵)
     * @param lastHit 막타 (없으면 null)
     * @return members 를 위 규칙으로 줄 세운 새 목록 (중복 없음, members 에 없는 사람은 넣지 않음)
     */
    public static List<UUID> rank(List<UUID> members, Map<UUID, Double> damage, UUID lastHit) {
        Set<UUID> uniq = new LinkedHashSet<>();
        for (UUID u : members) if (u != null) uniq.add(u);
        List<UUID> base = new ArrayList<>(uniq);
        Map<UUID, Double> dmg = damage == null ? Map.of() : damage;
        List<UUID> out = new ArrayList<>(base);
        out.sort((a, b) -> {
            double da = dmg.getOrDefault(a, 0.0);
            double db = dmg.getOrDefault(b, 0.0);
            if (Double.compare(db, da) != 0) return Double.compare(db, da);
            boolean la = a.equals(lastHit);
            boolean lb = b.equals(lastHit);
            if (la != lb) return la ? -1 : 1;
            return Integer.compare(base.indexOf(a), base.indexOf(b));
        });
        return out;
    }
}
