package kr.labyrinth.titles;

import java.util.Locale;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.Difficulty;

/**
 * 이벤트 → 업적 카운터 갱신 (순수 로직, 단위 테스트 대상). 키 규칙은 {@link AchievementRules} 문서 참고.
 */
public final class TitleCounters {

    /** 카운터 저장소 (PlayerData 어댑터 / 테스트용 맵). */
    public interface Store {
        long get(String key);

        void set(String key, long value);

        default void add(String key, long by) { set(key, get(key) + by); }

        default void max(String key, long value) { if (value > get(key)) set(key, value); }
    }

    private static final String P = AchievementRules.P;

    private TitleCounters() {}

    /** 층 클리어 (FloorClearEvent). externalClears = 다른 모듈이 센 그 층 클리어 수(이번 포함, 모르면 0). */
    public static void onClear(Store s, int floor, int partySize, int deaths, double seconds, String difficultyId,
                               long externalClears) {
        long clears = Math.max(s.get(P + "clear." + floor) + 1, externalClears);
        s.set(P + "clear." + floor, clears);
        if (partySize <= 1) s.add(P + "solo_clear." + floor, 1);
        if (deaths <= 0) s.max(P + "nodeath_party." + floor, Math.max(1, partySize));
        s.max(P + "diff_clear." + floor, Difficulty.rank(difficultyId) + 1L);
        long secs = (long) Math.ceil(Math.max(1.0, seconds));
        long best = s.get(P + "best_time." + floor);
        if (best <= 0 || secs < best) s.set(P + "best_time." + floor, secs);
    }

    /** 몹/보스 처치 기여 (MobKillEvent 참가자 각자). rank = normal|elite|add (보스면 무시). */
    public static void onKill(Store s, String mobId, String rank, boolean boss) {
        if (boss) {
            s.add(P + "boss_kills", 1);
            if (mobId != null) s.add(P + "boss_kill." + mobId, 1);
            return;
        }
        s.add(P + "kills", 1);
        if (mobId != null) s.add(P + "kill." + mobId, 1);
        s.add(P + "kill_rank." + (rank == null || rank.isBlank() ? "normal" : rank.toLowerCase(Locale.ROOT)), 1);
    }

    /** 장비 획득 (ItemObtainEvent, 장비만). */
    public static void onObtain(Store s, Rarity rarity, int amount) {
        if (rarity == null) return;
        s.add(P + "obtain." + rarity.id(), Math.max(1, amount));
    }

    /** 제작 완료 (CraftEvent). 그 희귀도 이하 모든 단계의 "이상" 카운터를 올린다. */
    public static void onCraft(Store s, Rarity rarity) {
        s.add(P + "crafts", 1);
        if (rarity == null) return;
        for (Rarity r : Rarity.values()) {
            if (r.ordinal() <= rarity.ordinal()) s.add(P + "craft_min." + r.id(), 1);
        }
    }

    /** 강화 (EnhanceEvent). 성공했을 때만 최고 단계·성공 횟수를 올린다(하락으로 내려가도 기록은 남는다). */
    public static void onEnhance(Store s, boolean success, int level) {
        if (!success) return;
        s.add(P + "enhance_success", 1);
        s.max(P + "enhance_best", Math.max(0, level));
    }
}
