package kr.labyrinth.titles;

import java.util.Locale;
import java.util.function.ToLongFunction;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.Difficulty;

/**
 * 업적 조건 판정 (순수 로직 — Bukkit 무관, 단위 테스트 대상). titles.yml 의 모든 condition.type 을
 * 플레이어 카운터(PlayerData counters, 접두어 {@code titles.})만으로 판정한다. 이벤트 리스너는 먼저 카운터를 갱신하고
 * 그다음 이 판정을 돌리므로, 접속 시 재검사·콘텐츠 추가 후 소급 지급이 같은 코드로 된다.
 * <p>
 * 카운터 키 (이 클래스가 원본):
 * <ul>
 *   <li>{@code titles.clear.<층>} 클리어 횟수 · {@code titles.solo_clear.<층>} 솔로 클리어 횟수</li>
 *   <li>{@code titles.nodeath_party.<층>} 무사망 클리어 때 가장 큰 입장 인원 (0 = 없음)</li>
 *   <li>{@code titles.diff_clear.<층>} 클리어한 가장 높은 난이도 순위+1 (쉬움 1 … 악몽 4, 0 = 없음)</li>
 *   <li>{@code titles.best_time.<층>} 최단 클리어 초(올림, 0 = 없음)</li>
 *   <li>{@code titles.first_clear.<층>} 서버 최초 돌파 파티 일원이면 1</li>
 *   <li>{@code titles.kills} · {@code titles.kill.<몹>} · {@code titles.kill_rank.<rank>} 처치 수(기여자 전원)</li>
 *   <li>{@code titles.boss_kills} · {@code titles.boss_kill.<보스>}</li>
 *   <li>{@code titles.obtain.<희귀도>} 그 희귀도 장비 획득 수(정확히 일치)</li>
 *   <li>{@code titles.crafts} · {@code titles.craft_min.<희귀도>} 그 희귀도 이상 제작 수</li>
 *   <li>{@code titles.pvp_wins} · {@code titles.pvp_streak}(현재) · {@code titles.pvp_best_streak} ·
 *       {@code titles.pvp_rating}(현재) · {@code titles.pvp_best_rating}</li>
 *   <li>{@code titles.server_first.<업적 id>} {@code server_first: true} 업적의 서버 최초 기록 보유자면 1</li>
 *   <li>{@code level} 현재 레벨 (카운터가 아니라 조회 함수가 PlayerData.level 로 답한다)</li>
 * </ul>
 */
public final class AchievementRules {

    public static final String P = "titles.";

    private AchievementRules() {}

    /** 이 업적의 조건을 지금 만족하는가. lookup = 카운터 조회 (없으면 0). */
    public static boolean met(AchievementDef def, ToLongFunction<String> lookup) {
        return met(def.id(), def.conditionType(), def.condition(), lookup);
    }

    public static boolean met(String id, String type, Params c, ToLongFunction<String> v) {
        if (type == null) return false;
        if (c == null) c = Params.EMPTY;
        if (c.bool("server_first", false)) {
            return v.applyAsLong(P + "server_first." + id) > 0;
        }
        return baseMet(type, c, v);
    }

    /** server_first 를 무시한 기본 조건 (서버 최초 기록을 시도할 자격 판정에도 쓴다). */
    public static boolean baseMet(String type, Params c, ToLongFunction<String> v) {
        if (c == null) c = Params.EMPTY;
        int floor = c.integer("floor", 0);
        switch (type.toUpperCase(Locale.ROOT)) {
            case "FIRST_CLEAR":
                return floor > 0 && v.applyAsLong(P + "first_clear." + floor) > 0;
            case "CLEAR":
                return floor > 0 && v.applyAsLong(P + "clear." + floor) >= Math.max(1, c.integer("count", 1));
            case "SOLO_CLEAR":
                return floor > 0 && v.applyAsLong(P + "solo_clear." + floor) >= Math.max(1, c.integer("count", 1));
            case "NO_DEATH_CLEAR":
                return floor > 0 && v.applyAsLong(P + "nodeath_party." + floor) >= Math.max(1, c.integer("party_min", 1));
            case "DIFFICULTY_CLEAR":
                return floor > 0 && v.applyAsLong(P + "diff_clear." + floor) >= Difficulty.rank(c.str("difficulty", "normal")) + 1;
            case "SPEED_CLEAR": {
                long best = v.applyAsLong(P + "best_time." + floor);
                return floor > 0 && best > 0 && best <= c.integer("seconds", 0);
            }
            case "KILL": {
                long need = Math.max(1, c.integer("count", 1));
                String mob = c.str("mob");
                String rank = c.str("rank");
                if (mob != null && !mob.isBlank()) return v.applyAsLong(P + "kill." + mob) >= need;
                if (rank != null && !rank.isBlank()) return v.applyAsLong(P + "kill_rank." + rank.toLowerCase(Locale.ROOT)) >= need;
                return v.applyAsLong(P + "kills") >= need;
            }
            case "BOSS_KILL": {
                long need = Math.max(1, c.integer("count", 1));
                String boss = c.str("boss");
                if (boss != null && !boss.isBlank()) return v.applyAsLong(P + "boss_kill." + boss) >= need;
                return v.applyAsLong(P + "boss_kills") >= need;
            }
            case "LEVEL":
                return v.applyAsLong("level") >= Math.max(1, c.integer("level", 1));
            case "OBTAIN_RARITY": {
                Rarity r = Rarity.byId(c.str("rarity"));
                return r != null && v.applyAsLong(P + "obtain." + r.id()) >= Math.max(1, c.integer("count", 1));
            }
            case "CRAFT": {
                long need = Math.max(1, c.integer("count", 1));
                Rarity r = Rarity.byId(c.str("rarity"));
                return r == null ? v.applyAsLong(P + "crafts") >= need : v.applyAsLong(P + "craft_min." + r.id()) >= need;
            }
            case "PVP_FIRST_WIN":
                return v.applyAsLong(P + "pvp_wins") >= 1;
            case "PVP_WIN":
                return v.applyAsLong(P + "pvp_wins") >= Math.max(1, c.integer("count", 1));
            case "PVP_STREAK":
                return v.applyAsLong(P + "pvp_best_streak") >= Math.max(1, c.integer("count", 1));
            case "PVP_RATING":
                return v.applyAsLong(P + "pvp_best_rating") >= c.integer("min", Integer.MAX_VALUE);
            default:
                return false;
        }
    }

    /**
     * 진행도 (UI 표시용): [현재, 목표]. 수치형이 아닌 조건(최초 돌파·무사망 등)은 달성 여부 0/1.
     */
    public static long[] progress(AchievementDef def, ToLongFunction<String> v) {
        Params c = def.condition() == null ? Params.EMPTY : def.condition();
        String type = def.conditionType() == null ? "" : def.conditionType().toUpperCase(Locale.ROOT);
        int floor = c.integer("floor", 0);
        long cur;
        long goal;
        switch (type) {
            case "CLEAR" -> { cur = v.applyAsLong(P + "clear." + floor); goal = Math.max(1, c.integer("count", 1)); }
            case "KILL" -> {
                goal = Math.max(1, c.integer("count", 1));
                String mob = c.str("mob");
                String rank = c.str("rank");
                if (mob != null && !mob.isBlank()) cur = v.applyAsLong(P + "kill." + mob);
                else if (rank != null && !rank.isBlank()) cur = v.applyAsLong(P + "kill_rank." + rank.toLowerCase(Locale.ROOT));
                else cur = v.applyAsLong(P + "kills");
            }
            case "BOSS_KILL" -> {
                goal = Math.max(1, c.integer("count", 1));
                String boss = c.str("boss");
                cur = boss != null && !boss.isBlank() ? v.applyAsLong(P + "boss_kill." + boss) : v.applyAsLong(P + "boss_kills");
            }
            case "LEVEL" -> { cur = v.applyAsLong("level"); goal = Math.max(1, c.integer("level", 1)); }
            case "OBTAIN_RARITY" -> {
                Rarity r = Rarity.byId(c.str("rarity"));
                cur = r == null ? 0 : v.applyAsLong(P + "obtain." + r.id());
                goal = Math.max(1, c.integer("count", 1));
            }
            case "CRAFT" -> {
                Rarity r = Rarity.byId(c.str("rarity"));
                cur = r == null ? v.applyAsLong(P + "crafts") : v.applyAsLong(P + "craft_min." + r.id());
                goal = Math.max(1, c.integer("count", 1));
            }
            case "PVP_WIN" -> { cur = v.applyAsLong(P + "pvp_wins"); goal = Math.max(1, c.integer("count", 1)); }
            case "PVP_STREAK" -> { cur = v.applyAsLong(P + "pvp_best_streak"); goal = Math.max(1, c.integer("count", 1)); }
            case "PVP_RATING" -> { cur = v.applyAsLong(P + "pvp_best_rating"); goal = c.integer("min", 1); }
            default -> { cur = met(def, v) ? 1 : 0; goal = 1; }
        }
        return new long[] {Math.min(cur, goal), goal};
    }

    /** 조건 설명 한 줄 (UI: 숨김 업적이 아니면 description 아래에 보여 준다). */
    public static String conditionText(AchievementDef def) {
        Params c = def.condition() == null ? Params.EMPTY : def.condition();
        String type = def.conditionType() == null ? "" : def.conditionType().toUpperCase(Locale.ROOT);
        int floor = c.integer("floor", 0);
        String sf = c.bool("server_first", false) ? " (서버 최초 1회)" : "";
        return switch (type) {
            case "FIRST_CLEAR" -> "지하 " + floor + "층 서버 최초 돌파";
            case "CLEAR" -> "지하 " + floor + "층 클리어 " + Math.max(1, c.integer("count", 1)) + "회";
            case "SOLO_CLEAR" -> "지하 " + floor + "층 혼자 클리어";
            case "NO_DEATH_CLEAR" -> "지하 " + floor + "층 무사망 클리어" + (c.integer("party_min", 1) > 1 ? " (" + c.integer("party_min", 1) + "인 이상)" : "");
            case "DIFFICULTY_CLEAR" -> "지하 " + floor + "층을 '" + difficultyName(c.str("difficulty", "normal")) + "' 이상으로 클리어";
            case "SPEED_CLEAR" -> "지하 " + floor + "층을 " + timeText(c.integer("seconds", 0)) + " 안에 클리어";
            case "KILL" -> {
                String what = c.str("mob") != null ? "지정 몬스터" : c.str("rank") != null ? rankName(c.str("rank")) : "몬스터";
                yield what + " " + c.integer("count", 1) + "마리 처치";
            }
            case "BOSS_KILL" -> (c.str("boss") != null ? "지정 보스" : "보스") + " " + c.integer("count", 1) + "회 처치";
            case "LEVEL" -> "레벨 " + c.integer("level", 1) + " 달성";
            case "OBTAIN_RARITY" -> {
                Rarity r = Rarity.byId(c.str("rarity"));
                yield (r == null ? "?" : r.displayName()) + " 장비 " + Math.max(1, c.integer("count", 1)) + "개 획득";
            }
            case "CRAFT" -> {
                Rarity r = Rarity.byId(c.str("rarity"));
                yield (r == null ? "" : r.displayName() + " 이상 ") + "장비 제작 " + c.integer("count", 1) + "회";
            }
            case "PVP_FIRST_WIN" -> "파티 대전 첫 승리" + sf;
            case "PVP_WIN" -> "파티 대전 " + c.integer("count", 1) + "승";
            case "PVP_STREAK" -> "파티 대전 " + c.integer("count", 1) + "연승";
            case "PVP_RATING" -> "대전 레이팅 " + c.integer("min", 0) + " 달성" + sf;
            default -> "";
        };
    }

    static String difficultyName(String id) {
        return switch (id == null ? "" : id) {
            case "easy" -> "쉬움";
            case "hard" -> "어려움";
            case "nightmare" -> "악몽";
            default -> "보통";
        };
    }

    static String rankName(String rank) {
        return switch (rank == null ? "" : rank) {
            case "elite" -> "정예 몬스터";
            case "add" -> "소환물";
            default -> "일반 몬스터";
        };
    }

    public static String timeText(long seconds) {
        long m = seconds / 60;
        long s = seconds % 60;
        return m > 0 ? (s > 0 ? m + "분 " + s + "초" : m + "분") : s + "초";
    }
}
