package kr.labyrinth.dungeon.rooms;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.SplittableRandom;
import kr.labyrinth.content.Params;
import kr.labyrinth.dungeon.DungeonConfig;

/**
 * 특별 시련 (GDD §10.1, gear_spec §6) — 순수 계산. 층마다 하나 있는 시련방(기믹방)이 확률로 "특별 시련"이 된다.
 * 기믹은 그대로이고 <b>조건 하나</b>가 붙는다. 기믹 성공 + 조건 지킴 → 평소 상자(gimmick_floor_N)에 더해
 * {@code special_trial_fNN} 상자 하나 + 경험치 ×(1 + xp_bonus). 조건이 깨져도 실패가 아니다(평소 상자만).
 * <ul>
 *   <li>{@link #pick}: 시드 고정 굴림 — chance, 같은 층을 pity_visits 번 연속 못 보면 다음은 확정(파티원 중 가장 큰 값).</li>
 *   <li>{@link #rule}: 그 기믹의 조건 후보·서두름 초 (floors.yml {@code special_trial} 덮어쓰기 → 기본표 → 제한 시간 × time_factor).</li>
 *   <li>{@link #kept}: 조건 판정 ({@link Counters} = 방 안에서 센 값).</li>
 * </ul>
 * 조건 값(초·횟수·최소 피해·물약/주문서)은 굴릴 때 dungeon.yml 에서 복사해 둔다 — 도중에 설정을 다시 읽어도 그 방의 약속은 그대로.
 *
 * @param seconds   서두름: 기믹 시작부터 성공까지 이 초 이하 (다른 조건은 0)
 * @param hits      무상: 최대 HP {@code minDamage} 이상 맞은 횟수 상한 (솔로 기준)
 * @param perMember 무상: 파티원 1명 늘 때마다 상한 +
 * @param potions   절제: 물약(마시는 소모품)을 세는가
 * @param scrolls   절제: 주문서(귀환·부활·망각 등 마시지 않는 소모품)를 세는가
 */
public record SpecialTrial(Condition condition, int seconds, int hits, int perMember, double minDamage,
                           boolean potions, boolean scrolls) {

    /** 조건 4종 (닫힌 목록). */
    public enum Condition {
        /** 서두름 — 정해진 초 안에 끝낸다. */
        SWIFT("swift", "서두름"),
        /** 무상 — 큰 상처를 정해진 횟수보다 많이 입지 않는다. */
        UNSCATHED("unscathed", "무상"),
        /** 절제 — 물약·주문서를 쓰지 않는다. */
        ABSTAIN("abstain", "절제"),
        /** 무결 — 기믹의 "실수"(기회를 잃는 일)가 없다. */
        FLAWLESS("flawless", "무결");

        private final String id;
        private final String label;

        Condition(String id, String label) {
            this.id = id;
            this.label = label;
        }

        public String id() { return id; }

        /** 한국어 이름 (보스바). */
        public String label() { return label; }

        /** id → 조건 (모르면 null). */
        public static Condition parse(String s) {
            if (s == null) return null;
            String k = s.trim().toLowerCase(Locale.ROOT);
            for (Condition c : values()) if (c.id.equals(k)) return c;
            return null;
        }
    }

    /** 무결을 쓸 수 있는 기믹 — 실수 자리에서 {@code GimmickRoom.noteMistake()} 를 부른다. */
    public static final Set<String> FLAWLESS_GIMMICKS = Set.of("lever_sequence", "resonance_tune", "book_cipher", "gear_timing");
    /** 서두를 수 없는 기믹 (정해진 시간을 버티는 시련). */
    public static final Set<String> FIXED_DURATION_GIMMICKS = Set.of("torch_relay", "void_trial");
    /** 피해가 기믹 자체에 들어 있어 무상을 쓰지 않는 기믹. */
    public static final Set<String> HURTING_GIMMICKS = Set.of("spore_purge");

    /** 기믹마다 조건 후보 2개 (gear_spec §6.3 — 그 기믹과 겹치지 않게 고름). */
    public static final Map<String, List<Condition>> DEFAULT_CONDITIONS = Map.of(
            "lever_sequence", List.of(Condition.FLAWLESS, Condition.SWIFT),
            "torch_relay", List.of(Condition.UNSCATHED, Condition.ABSTAIN),
            "spore_purge", List.of(Condition.ABSTAIN, Condition.SWIFT),
            "valve_flow", List.of(Condition.SWIFT, Condition.UNSCATHED),
            "forge_bellows", List.of(Condition.SWIFT, Condition.ABSTAIN),
            "lights_out", List.of(Condition.SWIFT, Condition.UNSCATHED),
            "resonance_tune", List.of(Condition.FLAWLESS, Condition.UNSCATHED),
            "book_cipher", List.of(Condition.FLAWLESS, Condition.SWIFT),
            "gear_timing", List.of(Condition.FLAWLESS, Condition.UNSCATHED),
            "void_trial", List.of(Condition.UNSCATHED, Condition.ABSTAIN));

    /** 서두름 초 기본표 = 그 기믹이 보통 걸리는 시간 × 0.7 (제한 시간이 있는 기믹은 제한 × 0.7). */
    public static final Map<String, Integer> DEFAULT_SECONDS = Map.of(
            "lever_sequence", 60, "spore_purge", 90, "valve_flow", 42, "forge_bellows", 70,
            "lights_out", 84, "book_cipher", 126);

    /** 마시는 소모품 action (GearItemService.DRINK_ACTIONS 와 같음) — 나머지 소모품은 주문서로 센다. */
    public static final Set<String> POTION_ACTIONS = Set.of("heal", "mana", "restore", "cleanse", "buff");

    /** 지속 피해 틱(상태이상)은 "맞은" 것으로 세지 않는다 — source "effect:&lt;id&gt;" (단 즉시 피해 effect:damage 는 센다). */
    public static boolean countsAsHit(String sourceId) {
        return sourceId == null || !sourceId.startsWith("effect:") || sourceId.equals("effect:damage");
    }

    public static boolean isPotion(String action) { return action != null && POTION_ACTIONS.contains(action); }

    /** 이 기믹이 그 조건을 쓸 수 있는가. */
    public static boolean supports(String gimmick, Condition c) {
        if (c == null) return false;
        String g = gimmick == null ? "" : gimmick;
        return switch (c) {
            case FLAWLESS -> FLAWLESS_GIMMICKS.contains(g);
            case SWIFT -> !FIXED_DURATION_GIMMICKS.contains(g);
            case UNSCATHED -> !HURTING_GIMMICKS.contains(g);
            case ABSTAIN -> true;
        };
    }

    /** 특별 상자 루팅 표 이름. */
    public static String table(int floor) { return String.format(Locale.ROOT, "special_trial_f%02d", floor); }

    /** 방 하나의 굴림 시드 (층 시드 ^ 방 번호, 섞어서). */
    public static long seed(long floorSeed, int roomIndex) {
        return floorSeed ^ (0x5DEECE66DL * (roomIndex + 1L)) ^ 0x7A1A15L;
    }

    // ── 층 규칙 ───────────────────────────────────────────────────────────

    /** 그 층의 조건 후보 + 서두름 초. 후보가 비면 그 층은 특별 시련이 없다. */
    public record Rule(List<Condition> conditions, int seconds) {
        public Rule {
            conditions = List.copyOf(conditions);
        }

        public boolean isEmpty() { return conditions.isEmpty(); }
    }

    /**
     * 층 규칙. floors.yml {@code special_trial: {conditions: [..], seconds: N}} 가 있으면 그것(그 기믹이 못 쓰는 조건은 뺌,
     * {@code conditions: []} 또는 {@code enabled: false} = 그 층 끔), 없으면 기본표.
     * 서두름 초 = 덮어쓴 seconds → 기본표 → 제한 시간 × time_factor → default_seconds, 그리고 [min_seconds, 제한 시간 − 1].
     *
     * @param timeLimit 그 기믹의 제한 시간(초, 0 = 없음)
     */
    public static Rule rule(String gimmick, Params override, int timeLimit, DungeonConfig.Special cfg) {
        Params o = override == null ? Params.EMPTY : override;
        String g = gimmick == null ? "" : gimmick;
        if (!o.bool("enabled", true)) return new Rule(List.of(), 0);
        List<Condition> cands = new ArrayList<>();
        if (o.has("conditions")) {
            for (String s : o.strings("conditions")) {
                Condition c = Condition.parse(s);
                if (c != null && supports(g, c) && !cands.contains(c)) cands.add(c);
            }
        } else {
            for (Condition c : DEFAULT_CONDITIONS.getOrDefault(g, List.of())) if (supports(g, c)) cands.add(c);
        }
        int seconds = 0;
        if (cands.contains(Condition.SWIFT)) {
            int s = o.integer("seconds", 0);
            if (s <= 0) s = DEFAULT_SECONDS.getOrDefault(g, 0);
            if (s <= 0 && timeLimit > 0) s = (int) Math.round(timeLimit * cfg.swiftTimeFactor());
            if (s <= 0) s = cfg.swiftDefaultSeconds();
            s = Math.max(cfg.swiftMinSeconds(), s);
            if (timeLimit > 0) s = Math.min(s, timeLimit - 1);
            seconds = Math.max(1, s);
        }
        return new Rule(cands, seconds);
    }

    // ── 굴림 ──────────────────────────────────────────────────────────────

    /** 연속으로 못 본 횟수가 pity_visits 이상이면 다음은 확정 (0 = 끔). */
    public static boolean pityForced(int miss, int pityVisits) { return pityVisits > 0 && miss >= pityVisits; }

    /**
     * 특별 시련 굴림 (시드 고정). 끔·후보 없음·굴림 실패 = null.
     *
     * @param pity 이 층을 연속으로 특별 시련 없이 돈 횟수 (파티원 중 가장 큰 값)
     */
    public static SpecialTrial pick(long seed, Rule rule, DungeonConfig.Special cfg, int pity) {
        if (cfg == null || !cfg.enabled() || rule == null || rule.isEmpty()) return null;
        SplittableRandom rng = new SplittableRandom(seed);
        double roll = rng.nextDouble();
        if (!pityForced(pity, cfg.pityVisits()) && roll >= cfg.chance()) return null;
        return of(rule.conditions().get(rng.nextInt(rule.conditions().size())), rule, cfg);
    }

    /** 확정 (자가 진단·관리자): 확률·끔 무시, 후보 중 시드로 하나. 후보 없음 = null. */
    public static SpecialTrial forced(long seed, Rule rule, DungeonConfig.Special cfg) {
        if (rule == null || rule.isEmpty()) return null;
        SplittableRandom rng = new SplittableRandom(seed);
        rng.nextDouble();
        return of(rule.conditions().get(rng.nextInt(rule.conditions().size())), rule, cfg);
    }

    /** 조건 하나로 만든다 (설정 값 복사). */
    public static SpecialTrial of(Condition c, Rule rule, DungeonConfig.Special cfg) {
        int seconds = c == Condition.SWIFT ? Math.max(1, rule == null || rule.seconds() <= 0 ? cfg.swiftDefaultSeconds() : rule.seconds()) : 0;
        return new SpecialTrial(c, seconds, cfg.unscathedHits(), cfg.unscathedPerMember(), cfg.unscathedMinDamage(),
                cfg.abstainPotions(), cfg.abstainScrolls());
    }

    /** 파티 기준 연속 못 본 횟수 = 가장 큰 값. */
    public static int partyMiss(Collection<Integer> misses) {
        int max = 0;
        if (misses != null) for (Integer m : misses) if (m != null) max = Math.max(max, m);
        return max;
    }

    // ── 판정 ──────────────────────────────────────────────────────────────

    /** 방 안에서 센 값 (도전마다 새로). */
    public static final class Counters {
        private int hits;
        private int potions;
        private int scrolls;
        private int mistakes;
        private double elapsed;

        /** 최대 HP 비율 ratio 피해 — minDamage 이상이면 한 번 맞은 것. @return 셌으면 true */
        public boolean hurt(double ratio, double minDamage) {
            if (!(ratio + 1e-9 >= minDamage) || ratio <= 0) return false;
            hits++;
            return true;
        }

        public void consume(boolean potion) {
            if (potion) potions++;
            else scrolls++;
        }

        public void mistake() { mistakes++; }

        public void elapsed(double seconds) { elapsed = Math.max(0, seconds); }

        public int hits() { return hits; }
        public int potions() { return potions; }
        public int scrolls() { return scrolls; }
        public int mistakes() { return mistakes; }
        public double elapsed() { return elapsed; }

        public void reset() {
            hits = potions = scrolls = mistakes = 0;
            elapsed = 0;
        }
    }

    /** 무상: 파티 인원 n 일 때 허용 횟수 = hits + per_member × (n − 1). */
    public int allowedHits(int party) { return Math.max(0, hits + perMember * Math.max(0, party - 1)); }

    /** 조건을 지켰는가 (서두름은 c.elapsed 로 — 성공 순간에 넣는다). */
    public boolean kept(Counters c, int party) {
        return switch (condition) {
            case SWIFT -> c.elapsed() <= seconds + 1e-9;
            case UNSCATHED -> c.hits() <= allowedHits(party);
            case ABSTAIN -> (!potions || c.potions() == 0) && (!scrolls || c.scrolls() == 0);
            case FLAWLESS -> c.mistakes() == 0;
        };
    }

    // ── 보상 ──────────────────────────────────────────────────────────────

    /** 기믹 성공 때 굴릴 표 + 경험치 배율. */
    public record Reward(List<String> tables, double xpMult, boolean special) {}

    /**
     * 기믹 성공 보상. 평소 상자(gimmick_floor_N)는 언제나, 특별 시련이고 조건을 지켰으면 special_trial_fNN 하나 더 + 경험치 ×(1 + xpBonus).
     *
     * @param trial  null = 평소 시련
     * @param broken 도중에 조건이 깨졌는가
     */
    public static Reward reward(int floor, SpecialTrial trial, boolean broken, Counters c, int party, double xpBonus) {
        String base = "gimmick_floor_" + floor;
        if (trial == null || broken || !trial.kept(c, party)) return new Reward(List.of(base), 1.0, false);
        return new Reward(List.of(base, table(floor)), 1.0 + Math.max(0, xpBonus), true);
    }

    // ── 문구 (공략 없이 "무엇을 하지 마라 / 언제까지"만) ─────────────────

    /** 조건 한 줄 (글자판·채팅). */
    public String line(int party) {
        return switch (condition) {
            case SWIFT -> "모래시계가 뒤집혔다. " + seconds + "초 안에 끝내라.";
            case UNSCATHED -> "이 방은 상처를 세고 있다. " + allowedHits(party) + "번 넘게 다치지 마라.";
            case ABSTAIN -> potions && scrolls ? "물약 냄새를 싫어하는 방이다. 물약도 주문서도 쓰지 마라."
                    : scrolls ? "이 방은 주문서를 싫어한다. 주문서를 쓰지 마라." : "물약 냄새를 싫어하는 방이다. 아무것도 마시지 마라.";
            case FLAWLESS -> "한 번의 실수도 기억된다. 틀리지 마라.";
        };
    }

    /** 짧은 조건 (들어갈 때 가운데 글자 아래 줄). */
    public String shortLine(int party) {
        return switch (condition) {
            case SWIFT -> seconds + "초 안에 끝내라";
            case UNSCATHED -> allowedHits(party) + "번 넘게 다치지 마라";
            case ABSTAIN -> potions && scrolls ? "물약도 주문서도 쓰지 마라" : scrolls ? "주문서를 쓰지 마라" : "아무것도 마시지 마라";
            case FLAWLESS -> "틀리지 마라";
        };
    }

    /** 보스바 상태 ("서두름 · 남은 31초"). elapsed = 기믹이 시작된 뒤 초. */
    public String status(Counters c, int party, double elapsed, boolean broken) {
        String head = condition.label() + " · ";
        if (broken) return head + "깨짐";
        return switch (condition) {
            case SWIFT -> head + "남은 " + Math.max(0, (int) Math.ceil(seconds - elapsed)) + "초";
            case UNSCATHED -> head + "상처 " + c.hits() + "/" + allowedHits(party);
            case ABSTAIN -> head + "지키는 중";
            case FLAWLESS -> head + "실수 없음";
        };
    }

    /** 보스바 진행률 0~1. */
    public float progress(Counters c, int party, double elapsed, boolean broken) {
        if (broken) return 0f;
        double v = switch (condition) {
            case SWIFT -> seconds <= 0 ? 0 : 1.0 - elapsed / seconds;
            case UNSCATHED -> 1.0 - c.hits() / (double) (allowedHits(party) + 1);
            case ABSTAIN, FLAWLESS -> 1.0;
        };
        return (float) Math.max(0, Math.min(1, v));
    }
}
