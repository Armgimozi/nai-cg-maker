package kr.labyrinth.core;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import kr.labyrinth.Services;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.data.PlayerData;
import org.bukkit.entity.Player;

/**
 * 점진 힌트 (GDD "보스 문구 규칙 · 점진 힌트"). 보스·기믹은 글로 정답을 알려 주지 않고, 같은 보스/기믹에서 실패가
 * 쌓일수록 다음 도전 시작 때 보여 주는 단서가 한 단계씩 또렷해진다.
 * <ul>
 *   <li>실패 횟수: 플레이어마다 {@link PlayerData#ext()} 의 {@code hints.<key>} (key = {@code boss.<보스 id>} /
 *       {@code gimmick.<기믹 구현 키>}). 보스전 중 전멸·기믹 실패 때 그 자리의 파티원 전원 +1.</li>
 *   <li>단계: <b>파티 기준</b> — 지금 함께 있는 파티원 중 가장 많이 실패한 사람의 횟수로 정한다.</li>
 *   <li>config.yml {@code hints: {mode: progressive | none | full, thresholds: [2, 4, 6]}} — thresholds 의 k 번째 값 이상이면
 *       k 단계 (0 = 단서 없음). full = 처음부터 마지막 단서, none = 단서 없음.</li>
 *   <li>단서 문장: 보스 = bosses.yml 각 보스의 {@code hints: [단서1, 단서2, 단서3]}, 기믹 = 기믹방 구현의 hints().</li>
 * </ul>
 * 순수 계산({@link #level}, {@link #clue}, {@link #failures(Map, String)})은 단위 테스트 대상.
 */
public final class Hints {

    private Hints() {}

    public enum Mode {
        /** 실패가 쌓일수록 단계별 단서 (기본). */
        PROGRESSIVE,
        /** 단서를 전혀 보여 주지 않는다. */
        NONE,
        /** 처음부터 마지막(가장 분명한) 단서. */
        FULL;

        public static Mode parse(String s) {
            if (s == null) return PROGRESSIVE;
            try {
                return valueOf(s.trim().toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                return PROGRESSIVE;
            }
        }
    }

    /** 힌트 설정. thresholds 는 오름차순 정렬된 양수. */
    public record Config(Mode mode, int[] thresholds) {
        public static final Config DEFAULT = new Config(Mode.PROGRESSIVE, new int[] {2, 4, 6});

        public Config {
            mode = mode == null ? Mode.PROGRESSIVE : mode;
            int[] t = thresholds == null || thresholds.length == 0 ? new int[] {2, 4, 6} : thresholds.clone();
            for (int i = 0; i < t.length; i++) t[i] = Math.max(1, t[i]);
            Arrays.sort(t);
            thresholds = t;
        }

        /** 가장 높은 단계 (= thresholds 개수). */
        public int maxLevel() { return thresholds.length; }

        public static Config of(String mode, List<Integer> thresholds) {
            int[] t = thresholds == null ? null : thresholds.stream().filter(java.util.Objects::nonNull).mapToInt(Integer::intValue).toArray();
            return new Config(Mode.parse(mode), t);
        }

        @Override
        public boolean equals(Object o) {
            return o instanceof Config c && c.mode == mode && Arrays.equals(c.thresholds, thresholds);
        }

        @Override
        public int hashCode() { return mode.hashCode() * 31 + Arrays.hashCode(thresholds); }

        @Override
        public String toString() { return "Hints.Config[" + mode + ", " + Arrays.toString(thresholds) + "]"; }
    }

    // ── 순수 계산 ────────────────────────────────────────────────────────

    /** 실패 횟수 → 단서 단계 (0 = 없음 … maxLevel). */
    public static int level(Config cfg, int failures) {
        Config c = cfg == null ? Config.DEFAULT : cfg;
        return switch (c.mode()) {
            case NONE -> 0;
            case FULL -> c.maxLevel();
            case PROGRESSIVE -> {
                int lv = 0;
                for (int t : c.thresholds()) if (failures >= t) lv++;
                yield lv;
            }
        };
    }

    /** 단계 → 단서 문장. 단서가 단계보다 적으면 가장 분명한(마지막) 것. 단계 0·단서 없음 = null. */
    public static String clue(List<String> clues, int level) {
        if (level <= 0 || clues == null || clues.isEmpty()) return null;
        String s = clues.get(Math.min(level, clues.size()) - 1);
        return s == null || s.isBlank() ? null : s;
    }

    /** ext 맵에 저장할 키. */
    public static String extKey(String key) { return "hints." + key; }

    public static String bossKey(String bossId) { return "boss." + bossId; }

    public static String gimmickKey(String gimmickId) { return "gimmick." + gimmickId; }

    /** ext 맵에서 실패 횟수 읽기 (없거나 잘못된 값 = 0). */
    public static int failures(Map<String, Object> ext, String key) {
        if (ext == null) return 0;
        Object v = ext.get(extKey(key));
        if (v instanceof Number n) return Math.max(0, n.intValue());
        if (v instanceof String s) {
            try {
                return Math.max(0, Integer.parseInt(s.trim()));
            } catch (NumberFormatException ignored) {
                return 0;
            }
        }
        return 0;
    }

    /** 여러 명의 실패 횟수 중 최댓값 (파티 기준). */
    public static int partyFailures(Collection<Map<String, Object>> exts, String key) {
        int max = 0;
        if (exts != null) for (Map<String, Object> e : exts) max = Math.max(max, failures(e, key));
        return max;
    }

    // ── 런타임 ───────────────────────────────────────────────────────────

    /** config.yml hints 섹션 (없으면 기본: progressive, [2, 4, 6]). */
    public static Config config(Services s) {
        try {
            var c = s.plugin().getConfig(); // 서버 config.yml 에 없으면 jar 기본값(defaults)
            return Config.of(c.getString("hints.mode"), c.getIntegerList("hints.thresholds"));
        } catch (Throwable t) {
            return Config.DEFAULT;
        }
    }

    public static int failures(Services s, Player p, String key) {
        return failures(s.data().get(p).ext(), key);
    }

    /** 실패 1회 기록 (그 자리의 파티원 전원). */
    public static void recordFailure(Services s, Collection<Player> players, String key) {
        if (players == null || key == null) return;
        for (Player p : players) {
            if (p == null) continue;
            PlayerData d = s.data().get(p);
            d.ext().put(extKey(key), failures(d.ext(), key) + 1);
            d.markDirty();
        }
    }

    /** 파티(지금 함께 있는 사람들) 기준 단계. */
    public static int partyLevel(Services s, Collection<Player> players, String key) {
        List<Map<String, Object>> exts = new ArrayList<>();
        if (players != null) for (Player p : players) if (p != null) exts.add(s.data().get(p).ext());
        return level(config(s), partyFailures(exts, key));
    }

    /** 파티 기준 단서 (없으면 null). */
    public static String partyClue(Services s, Collection<Player> players, String key, List<String> clues) {
        return clue(clues, partyLevel(s, players, key));
    }

    /** 보스 단서 목록 (bosses.yml 의 hints). */
    public static List<String> bossClues(BossDef def) {
        if (def == null || def.raw() == null) return List.of();
        return def.raw().strings("hints");
    }

    /** 이 플레이어와 함께 공략 중인 파티원 (인스턴스 밖이면 자기 자신). */
    public static List<Player> partyOf(Services s, Player p) {
        try {
            var ctx = s.dungeon().currentInstance(p);
            if (ctx.isPresent()) {
                List<Player> out = new ArrayList<>(ctx.get().onlineMembers());
                if (!out.contains(p)) out.add(p);
                return out;
            }
        } catch (Throwable ignored) {
            // 던전 서비스 없음
        }
        return List.of(p);
    }

    /** 단서 한 줄을 화면 문구로 (MiniMessage). */
    public static String format(String clue) {
        return "<dark_gray>✧</dark_gray> <gray><i>" + clue + "</i></gray>";
    }
}
