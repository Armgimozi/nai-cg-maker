package kr.labyrinth.titles;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.function.ToLongFunction;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Text;

/**
 * 칭호 조건 판정 (순수 로직 — Bukkit 무관, 단위 테스트 대상).
 * <p>
 * <b>0.3.4 규칙</b>: 칭호마다 서버에서 단 한 명만 가진다 — 조건을 처음 채운 사람이 주인. 판정은 사건({@link TitleTrigger})이
 * 일어난 그 순간에만 하고({@link #qualifies}), 주인이 생긴 칭호는 다시 판정하지 않는다(서비스가 records.yml 로 확인).
 * 조건 설명({@link #conditionText})은 주인이 생긴 칭호와 관리자 명령에서만 보여 준다.
 * <p>
 * 카운터 키 (PlayerData counters, 이 클래스가 원본 — 예전 판에서 쌓인 값도 그대로 이어진다):
 * <ul>
 *   <li>{@code titles.clear.<층>} 클리어 횟수 · {@code titles.solo_clear.<층>} 솔로 클리어 횟수</li>
 *   <li>{@code titles.nodeath_party.<층>} · {@code titles.diff_clear.<층>} · {@code titles.best_time.<층>} (기록용 — 판정은 사건으로)</li>
 *   <li>{@code titles.kills} · {@code titles.kill.<몹>} · {@code titles.kill_rank.<rank>} 처치 수(기여자 전원)</li>
 *   <li>{@code titles.boss_kills} · {@code titles.boss_kill.<보스>}</li>
 *   <li>{@code titles.obtain.<희귀도>} 그 희귀도 장비 획득 수(정확히 일치)</li>
 *   <li>{@code titles.crafts} · {@code titles.craft_min.<희귀도>} 그 희귀도 이상 제작 수</li>
 *   <li>{@code titles.enhance_best} · {@code titles.enhance_success}</li>
 *   <li>{@code titles.treasure.<chest|gold_chest|vault|mimic>} 미로 보물</li>
 *   <li>{@code level} 현재 레벨 (조회 함수가 PlayerData.level 로 답한다)</li>
 * </ul>
 */
public final class AchievementRules {

    public static final String P = "titles.";

    /** 층 돌파 계열 조건. */
    public static final List<String> CLEAR_TYPES = List.of("FIRST_CLEAR", "CLEAR", "SOLO_CLEAR", "NO_DEATH_CLEAR",
            "DIFFICULTY_CLEAR", "SPEED_CLEAR");

    private AchievementRules() {}

    // ── 사건 판정 ─────────────────────────────────────────────────────────

    /**
     * 이 사건이 이 칭호의 조건을 채우는가. v = 그 플레이어의 카운터 조회 (사건이 반영된 뒤의 값).
     * 사건 종류가 다르면(예: 강화 칭호에 몹 처치 사건) 언제나 false — 접속·다른 일로는 받지 않는다.
     */
    public static boolean qualifies(AchievementDef def, TitleTrigger t, ToLongFunction<String> v) {
        if (def == null || t == null || def.conditionType() == null) return false;
        Params c = def.condition() == null ? Params.EMPTY : def.condition();
        String type = def.conditionType().toUpperCase(Locale.ROOT);
        if (CLEAR_TYPES.contains(type)) return t.kind() == TitleTrigger.Kind.CLEAR && clearQualifies(type, c, t, v);
        return switch (type) {
            case "KILL" -> t.kind() == TitleTrigger.Kind.KILL && !t.boss() && killMatches(c, t) && baseMet(type, c, v);
            case "BOSS_KILL" -> {
                if (t.kind() != TitleTrigger.Kind.KILL || !t.boss()) yield false;
                String boss = c.str("boss");
                yield (boss == null || boss.isBlank() || boss.equals(t.mobId())) && baseMet(type, c, v);
            }
            case "LEVEL" -> {
                int need = Math.max(1, c.integer("level", 1));
                yield t.kind() == TitleTrigger.Kind.LEVEL && t.fromLevel() < need && t.level() >= need; // 그 레벨을 넘는 순간만
            }
            case "OBTAIN_RARITY" -> {
                Rarity r = Rarity.byId(c.str("rarity"));
                yield t.kind() == TitleTrigger.Kind.OBTAIN && r != null && r == t.rarity() && baseMet(type, c, v);
            }
            case "CRAFT" -> {
                Rarity r = Rarity.byId(c.str("rarity"));
                yield t.kind() == TitleTrigger.Kind.CRAFT
                        && (r == null || (t.rarity() != null && t.rarity().ordinal() >= r.ordinal())) && baseMet(type, c, v);
            }
            case "ENHANCE" -> t.kind() == TitleTrigger.Kind.ENHANCE && t.level() >= Math.max(1, c.integer("level", 1));
            case "TREASURE" -> t.kind() == TitleTrigger.Kind.TREASURE && treasureKind(c).equals(t.treasure()) && baseMet(type, c, v);
            default -> false;
        };
    }

    /**
     * 층 돌파 사건 판정. 조건 종류가 정하는 것 + 어느 돌파 조건에나 붙일 수 있는 선택 키
     * ({@code solo: true} · {@code no_death: true} · {@code party_min} · {@code difficulty} · {@code seconds}).
     */
    private static boolean clearQualifies(String type, Params c, TitleTrigger t, ToLongFunction<String> v) {
        int floor = c.integer("floor", 0);
        if (floor <= 0 || t.floor() != floor) return false;
        if (needsSolo(type, c) && t.partySize() > 1) return false;
        if (needsNoDeath(type, c) && t.deaths() > 0) return false;
        int partyMin = c.integer("party_min", 1);
        if (partyMin > 1 && t.partySize() < partyMin) return false;
        String diff = difficultyOf(type, c);
        if (diff != null && Difficulty.rank(t.difficulty()) < Difficulty.rank(diff)) return false;
        int limit = c.integer("seconds", 0);
        if ("SPEED_CLEAR".equals(type) && limit <= 0) return false;
        if (limit > 0 && (t.seconds() <= 0 || Math.ceil(t.seconds()) > limit)) return false;
        return switch (type) {
            case "FIRST_CLEAR" -> t.firstClear();
            case "CLEAR" -> v.applyAsLong(P + "clear." + floor) >= Math.max(1, c.integer("count", 1));
            case "SOLO_CLEAR" -> v.applyAsLong(P + "solo_clear." + floor) >= Math.max(1, c.integer("count", 1));
            default -> true;
        };
    }

    private static boolean needsSolo(String type, Params c) { return "SOLO_CLEAR".equals(type) || c.bool("solo", false); }

    private static boolean needsNoDeath(String type, Params c) { return "NO_DEATH_CLEAR".equals(type) || c.bool("no_death", false); }

    private static String difficultyOf(String type, Params c) {
        String d = c.str("difficulty");
        if (d != null && !d.isBlank()) return d;
        return "DIFFICULTY_CLEAR".equals(type) ? "normal" : null;
    }

    private static boolean killMatches(Params c, TitleTrigger t) {
        if (!c.strings("mobs").isEmpty()) return c.strings("mobs").contains(t.mobId());
        String mob = c.str("mob");
        if (mob != null && !mob.isBlank()) return mob.equals(t.mobId());
        String rank = c.str("rank");
        if (rank != null && !rank.isBlank()) {
            return rank.toLowerCase(Locale.ROOT).equals(t.rank() == null ? "normal" : t.rank().toLowerCase(Locale.ROOT));
        }
        return true;
    }

    // ── 누적 카운터 판정 ──────────────────────────────────────────────────

    /** 누적 카운터가 조건 수치에 닿았는가 (사건 판정의 누적 부분). */
    public static boolean met(AchievementDef def, ToLongFunction<String> lookup) {
        return met(def.id(), def.conditionType(), def.condition(), lookup);
    }

    public static boolean met(String id, String type, Params c, ToLongFunction<String> v) {
        if (type == null) return false;
        return baseMet(type, c, v);
    }

    /** 카운터만으로 본 조건 (예전 키 {@code server_first} 는 무시 — 이제 모든 칭호가 한 명만). */
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
                if (!c.strings("mobs").isEmpty()) return killSum(c, v) >= need;
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
            case "ENHANCE":
                return v.applyAsLong(P + "enhance_best") >= Math.max(1, c.integer("level", 1));
            case "TREASURE":
                return v.applyAsLong(P + "treasure." + treasureKind(c)) >= Math.max(1, c.integer("count", 1));
            default:
                return false;
        }
    }

    /** KILL {@code mobs: [..]} — 나열한 몹들의 처치 수 합. */
    private static long killSum(Params c, ToLongFunction<String> v) {
        long sum = 0;
        for (String id : c.strings("mobs")) sum += v.applyAsLong(P + "kill." + id);
        return sum;
    }

    // ── 조건 설명 (주인이 생긴 칭호 · 관리자 전용) ────────────────────────

    /**
     * 조건 한 줄 ("서버 최초로 혼자서 지하 5층 돌파"). <b>주인이 없는 칭호에는 플레이어 화면에서 절대 쓰지 않는다</b> —
     * {@link TitleView} 가 주인이 있을 때만 부르고, 그 밖에는 관리자 명령(/labadmin title list)만 쓴다.
     * content 가 있으면 보스·몬스터 이름을 넣는다 (null 이면 id 그대로).
     */
    public static String conditionText(AchievementDef def, Content content) {
        String body = conditionBody(def, content);
        return body.isEmpty() ? "" : "서버 최초로 " + body;
    }

    /** "서버 최초로" 없이 조건 본문만. */
    static String conditionBody(AchievementDef def, Content content) {
        Params c = def.condition() == null ? Params.EMPTY : def.condition();
        String type = def.conditionType() == null ? "" : def.conditionType().toUpperCase(Locale.ROOT);
        int count = Math.max(1, c.integer("count", 1));
        if (CLEAR_TYPES.contains(type)) {
            int floor = c.integer("floor", 0);
            List<String> pre = new ArrayList<>();
            if (needsSolo(type, c)) pre.add("혼자서");
            int partyMin = c.integer("party_min", 1);
            if (partyMin > 1) pre.add(partyMin + "명 이상 파티로");
            if (needsNoDeath(type, c)) pre.add("아무도 쓰러지지 않고");
            String diff = difficultyOf(type, c);
            if (diff != null) pre.add("nightmare".equals(diff) ? "'악몽' 난이도로" : "'" + difficultyName(diff) + "' 이상 난이도로");
            int secs = c.integer("seconds", 0);
            boolean many = count > 1 && ("CLEAR".equals(type) || "SOLO_CLEAR".equals(type));
            StringBuilder sb = new StringBuilder(String.join(" ", pre));
            if (sb.length() > 0) sb.append(' ');
            sb.append("지하 ").append(floor).append("층");
            if (secs > 0 || many) {
                sb.append("을");
                if (secs > 0) sb.append(' ').append(timeText(secs)).append(" 안에");
                if (many) sb.append(' ').append(count).append("번");
            }
            sb.append(" 돌파");
            return sb.toString();
        }
        return switch (type) {
            case "KILL" -> {
                String what;
                if (!c.strings("mobs").isEmpty()) {
                    List<String> names = new ArrayList<>();
                    for (String id : c.strings("mobs")) names.add(mobName(content, id));
                    what = String.join("·", names) + " 합쳐";
                } else if (c.str("mob") != null) {
                    what = mobName(content, c.str("mob"));
                } else if (c.str("rank") != null) {
                    what = rankName(c.str("rank"));
                } else {
                    what = "몬스터";
                }
                yield what + " " + Text.num(count) + "마리 처치";
            }
            case "BOSS_KILL" -> {
                String boss = c.str("boss");
                String who = boss == null || boss.isBlank() ? "보스" : bossName(content, boss);
                yield who + (count > 1 ? " " + count + "번" : "") + " 처치";
            }
            case "LEVEL" -> "레벨 " + Math.max(1, c.integer("level", 1)) + " 달성";
            case "OBTAIN_RARITY" -> {
                Rarity r = Rarity.byId(c.str("rarity"));
                yield (r == null ? "?" : r.displayName()) + " 장비 " + (count > 1 ? count + "개 " : "") + "획득";
            }
            case "CRAFT" -> {
                Rarity r = Rarity.byId(c.str("rarity"));
                yield "대장간에서 " + (r == null ? "" : r.displayName() + " 이상 ") + "장비 " + (count > 1 ? count + "번 " : "") + "제작";
            }
            case "ENHANCE" -> "장비를 +" + Math.max(1, c.integer("level", 1)) + " 까지 강화";
            case "TREASURE" -> switch (treasureKind(c)) {
                case "gold_chest" -> "미로의 금 상자 " + count + "개 열기";
                case "vault" -> count == 1 ? "미로의 열쇠 금고 열기" : "미로의 열쇠 금고 " + count + "번 열기";
                case "mimic" -> count == 1 ? "미믹 길들이기" : "미믹 " + count + "마리 길들이기";
                default -> "미로의 보물 상자 " + count + "개 열기";
            };
            default -> "";
        };
    }

    private static String bossName(Content content, String id) {
        BossDef b = content == null ? null : content.boss(id);
        if (b == null) return id;
        return "지하 " + b.floor() + "층 보스 " + Text.strip(b.name());
    }

    private static String mobName(Content content, String id) {
        MobDef m = content == null ? null : content.mob(id);
        return m == null ? id : Text.strip(m.name());
    }

    /** TREASURE 조건의 kind (chest | gold_chest | vault | mimic, 기본 chest). */
    public static String treasureKind(Params c) {
        String k = c.str("kind", "chest");
        return k == null ? "chest" : k.toLowerCase(Locale.ROOT);
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
