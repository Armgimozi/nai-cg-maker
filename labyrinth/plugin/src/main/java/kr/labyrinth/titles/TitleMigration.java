package kr.labyrinth.titles;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.data.PlayerData;

/**
 * 칭호 데이터 정리 (순수 로직 — PlayerData 만 만진다, 단위 테스트 대상).
 * <ul>
 *   <li>{@link #reset034}: 0.3.4 새 칭호로 바꿀 때 한 번 — 새 titles.yml 에 없는 칭호를 모두 회수하고, 없어진 장착 칭호를 뗀다.
 *       이미 받은 골드·아이템과 카운터(처치·돌파 수 …)는 그대로. 칭호를 새로 주지는 않는다.</li>
 *   <li>{@link #sync}: 매 접속 — records.yml(칭호의 주인)이 기준. 주인이 아닌데 가진 칭호는 회수, 주인인데 데이터에 없으면
 *       (저장 전에 서버가 꺼진 경우) 되돌려 놓는다(보상은 다시 주지 않음).</li>
 * </ul>
 */
public final class TitleMigration {

    /** PlayerData ext: 0.3.4 칭호 초기화를 이미 했는지. */
    public static final String FLAG = "titles.reset_034";

    public static final String NOTICE = "<#ffd36b>칭호가 새로 바뀌었습니다</#ffd36b> <gray>— 칭호마다 서버에서 단 한 명만 가질 수 있고, "
            + "조건은 주인이 생기기 전까지 비밀입니다. <white>/칭호";

    private TitleMigration() {}

    /** @param ran 이번에 처음 돌았나 · announce 안내를 보낼 만한 기존 플레이어인가(예전 칭호·기록이 있었음) */
    public record Result(boolean ran, List<String> revoked, boolean clearedEquipped, boolean announce) {}

    public record Sync(List<String> restored, List<String> revoked, boolean clearedEquipped) {
        public boolean changed() { return !restored.isEmpty() || !revoked.isEmpty() || clearedEquipped; }
    }

    public static Result reset034(PlayerData d, Set<String> validIds) {
        if (Boolean.TRUE.equals(d.ext().get(FLAG))) return new Result(false, List.of(), false, false);
        d.ext().put(FLAG, true);
        d.markDirty();
        boolean veteran = !d.achievements().isEmpty() || !d.counters().isEmpty() || d.equippedTitle() != null;
        List<String> revoked = new ArrayList<>();
        for (String id : new ArrayList<>(d.achievements().keySet())) {
            if (!validIds.contains(id)) {
                d.revokeAchievement(id);
                revoked.add(id);
            }
        }
        boolean cleared = false;
        String eq = d.equippedTitle();
        if (eq != null && (!validIds.contains(eq) || !d.hasAchievement(eq))) {
            d.equippedTitle(null);
            cleared = true;
        }
        return new Result(true, List.copyOf(revoked), cleared, veteran);
    }

    /**
     * @param ids    titles.yml 의 칭호 id 전부
     * @param owners 칭호 id → 주인 UUID 목록 (records.yml, 주인 없으면 키 없음)
     */
    public static Sync sync(PlayerData d, Collection<String> ids, Map<String, List<UUID>> owners) {
        List<String> restored = new ArrayList<>();
        List<String> revoked = new ArrayList<>();
        for (String id : ids) {
            List<UUID> who = owners.get(id);
            boolean mine = who != null && who.contains(d.uuid());
            boolean has = d.hasAchievement(id);
            if (mine && !has) {
                d.grantAchievement(id);
                restored.add(id);
            } else if (!mine && has) {
                d.revokeAchievement(id);
                revoked.add(id);
            }
        }
        boolean cleared = false;
        String eq = d.equippedTitle();
        if (eq != null && !d.hasAchievement(eq)) {
            d.equippedTitle(null);
            cleared = true;
        }
        return new Sync(List.copyOf(restored), List.copyOf(revoked), cleared);
    }
}
