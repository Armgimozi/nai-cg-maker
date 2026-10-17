package kr.labyrinth.core;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.random.RandomGenerator;
import java.util.stream.Collectors;
import kr.labyrinth.content.ItemType;
import org.bukkit.configuration.ConfigurationSection;

/**
 * 죽음 페널티 — 순수 규칙 (서버 없이 시험). 실제 적용은 {@link DeathPenalty}. 0.3.6.1 에 생기고 0.3.6.2 에 고침 (스타듀밸리 광산 참고).
 * <ul>
 *   <li>어디서 죽든(미궁·야생·마을·네더·엔드·PvP) 지금 레벨에서 모은 경험치가 0 이 된다. 레벨은 내려가지 않고, 최고 레벨이면 아무것도 없다.</li>
 *   <li>미궁 공략 중 쓰러졌을 때만 가방 칸 slotsMin ~ slotsMax 개(고르게)를 잃는다. 단축 칸 + 가방 36칸 중
 *       손에 든 칸은 빼고, 입은 갑옷·장신구 칸(가방 밖)은 애초에 후보가 아니다. 빈 칸은 세지 않고, 후보가 모자라면 있는 만큼.
 *       잃은 물건은 지워진다 (떨구지 않음).</li>
 *   <li>0.3.6.2: 손에 든 칸 · 보조손은 셜커 상자·꾸러미일 때만 후보 ({@link #eligible}) — 상자를 손에 들어 재료를 지키지 못하게.
 *       그 밖의 것은 손·보조손에 있으면 언제나 안전.</li>
 *   <li>0.3.6.2: 장비(무기·방어구·방패·장신구, 바닐라 칼·갑옷·방패·활 등도)는 가방에 있어도 잃지 않는다 ({@link #alwaysSafe}).
 *       열쇠·문장, 광산 곡괭이, 미궁 활의 무한 화살, config safe_items 도 언제나 안전.</li>
 *   <li>0.3.6.2: 셜커 상자·꾸러미는 상자 자체를 잃지 않는다. 뽑히면 안에 든 것 중 안전하지 않은 것만 사라지고 장비는 남는다
 *       ({@link #losable} · {@link #strip}). 빈 상자나 장비만 든 상자는 뽑히지 않는다.</li>
 *   <li>0.3.6.2: 같은 쓰러짐에 지닌 골드의 minPercent ~ maxPercent %(고르게, 내림)를 잃는다. 한 번에 최대 {@code max} G (0 = 상한 없음)
 *       ({@link #goldLost}). 골드는 플레이어 몸에만 있다 (은행·파티 금고·우편 없음).</li>
 *   <li>공략 중 살아 있고 전투 중(10초 안에 피해 — 귀환 주문서와 같은 판정)이면 /미궁 퇴장·입구 메뉴 '귀환' 도
 *       {@code combat_exit_seconds}초 시전, 맞으면 끊김 ({@link #exitCastSeconds}) — 죽기 직전 퇴장으로 페널티를 피하지 못하게.</li>
 *   <li>0.3.6.2: 같은 때(전투 중 · 시전 중)에 접속을 끊으면 쓰러진 것으로 친다 ({@link #combatQuit}) — 서버 종료·재시작·관리자가 내보냄(/kick·/ban) 은 빼고.</li>
 * </ul>
 * config: {@code death.penalty} (키가 없으면 {@link Config#DEFAULT} — 예전 config.yml 도 jar 만 바꾸면 켜진다).
 */
public final class DeathPenaltyRules {

    private DeathPenaltyRules() {}

    /** 단축 칸 0~8 + 가방 9~35 ({@code PlayerInventory#getStorageContents}). 잃는 칸 수의 상한. */
    public static final int STORAGE_SLOTS = 36;
    /** 후보 배열에서 보조손 자리 (= 인벤토리 40번 칸). 갑옷 36~39 · 장신구는 넣지 않는다. */
    public static final int OFFHAND = 36;
    /** 후보 배열 길이: 단축 칸 + 가방 36 + 보조손 1. */
    public static final int CANDIDATE_SLOTS = 37;
    /** 전투 중 퇴장 시전 기본값 (초) = 귀환 주문서 cast_time. */
    public static final double COMBAT_EXIT_SECONDS = 5;
    /** 전투 중 판정: 마지막 피해에서 이만큼 안 (= 귀환 주문서 ConsumableListener 와 같은 10초). */
    public static final long COMBAT_MS = 10_000;
    /** 상자 속 상자(꾸러미 속 꾸러미) 를 이 깊이까지만 본다. 더 깊은 것은 건드리지 않는다 (안전). */
    static final int MAX_DEPTH = 8;

    /**
     * 0.3.6.2 골드 잃기 ({@code death.penalty.gold_loss}). 미궁 공략 중 쓰러지면 지닌 골드의 minPercent ~ maxPercent %
     * (고르게, 내림), 한 번에 최대 {@code max} G (0 = 상한 없음). 끄기: {@code gold_loss: false} · {@code enabled: false} ·
     * {@code max_percent: 0}.
     * 값은 0 ~ 100 %, max &lt; min 이면 min, 상한은 0 이상으로 자른다.
     */
    public record GoldLoss(boolean enabled, double minPercent, double maxPercent, long max) {
        public static final GoldLoss DEFAULT = new GoldLoss(true, 5, 25, 15_000);
        public static final GoldLoss OFF = new GoldLoss(false, 5, 25, 15_000);

        public GoldLoss {
            minPercent = clampPercent(minPercent);
            maxPercent = Math.max(minPercent, clampPercent(maxPercent));
            max = Math.max(0, max);
        }

        /** 켜져 있고 잃을 수 있는 비율이 있는가. */
        public boolean on() { return enabled && maxPercent > 0; }

        /**
         * config {@code gold_loss} 값 (섹션 · true · false · 없음). 빠진 키는 d 의 값. max_percent 만 적으면 그 값이 상한이라
         * min 도 거기까지 내려온다 (slots_max 와 같음 — 기본 min 5 가 끌어올리지 않게). max_percent 0 (이하) = 끔.
         */
        static GoldLoss read(Object raw, GoldLoss d) {
            if (Boolean.FALSE.equals(raw)) return new GoldLoss(false, d.minPercent(), d.maxPercent(), d.max());
            if (!(raw instanceof ConfigurationSection g)) return d;
            boolean on = g.getBoolean("enabled", d.enabled());
            double max = g.getDouble("max_percent", d.maxPercent());
            double min = g.getDouble("min_percent", Math.min(d.minPercent(), max));
            long cap = g.getLong("max", d.max());
            // max_percent: 0 이면 끔 — jar config 에 min_percent: 5 가 있어도 5% 로 끌어올리지 않게
            return new GoldLoss(on && max > 0, min, max, cap);
        }

        private static double clampPercent(double v) {
            return Double.isFinite(v) ? Math.max(0, Math.min(100, v)) : 0;
        }
    }

    /**
     * config.yml {@code death.penalty}. 끄기: {@code penalty: false} (전부) · {@code dungeon_item_loss: false} (물건만) ·
     * {@code gold_loss: false} (골드만).
     *
     * @param safeItems 잃지 않는 아이템 — items.yml id 또는 바닐라 이름(diamond 처럼), 소문자
     * @param combatExitSeconds 공략 중 전투 중에 스스로 나갈 때 시전 시간 (0 = 0.3.6 처럼 바로)
     * @param gold 골드 잃기 (0.3.6.2)
     */
    public record Config(boolean xpProgressReset, boolean itemLoss, int slotsMin, int slotsMax, Set<String> safeItems,
                         double combatExitSeconds, GoldLoss gold) {
        public static final Config DEFAULT = new Config(true, true, 2, 3, Set.of(), COMBAT_EXIT_SECONDS, GoldLoss.DEFAULT);
        public static final Config OFF = new Config(false, false, 2, 3, Set.of(), 0, GoldLoss.OFF);

        public Config {
            safeItems = safeItems == null ? Set.of() : Set.copyOf(safeItems);
            combatExitSeconds = Double.isFinite(combatExitSeconds) ? Math.max(0, Math.min(30, combatExitSeconds)) : 0;
            gold = gold == null ? GoldLoss.OFF : gold;
        }

        /** 골드는 기본값 ({@link GoldLoss#DEFAULT}). */
        public Config(boolean xpProgressReset, boolean itemLoss, int slotsMin, int slotsMax, Set<String> safeItems,
                      double combatExitSeconds) {
            this(xpProgressReset, itemLoss, slotsMin, slotsMax, safeItems, combatExitSeconds, GoldLoss.DEFAULT);
        }

        /** 퇴장 시전·골드는 기본값. */
        public Config(boolean xpProgressReset, boolean itemLoss, int slotsMin, int slotsMax, Set<String> safeItems) {
            this(xpProgressReset, itemLoss, slotsMin, slotsMax, safeItems, COMBAT_EXIT_SECONDS, GoldLoss.DEFAULT);
        }

        /** 골드만 바꾼 사본. */
        public Config withGold(GoldLoss g) {
            return new Config(xpProgressReset, itemLoss, slotsMin, slotsMax, safeItems, combatExitSeconds, g);
        }

        /**
         * config 루트에서 읽는다. 섹션은 {@code get} 으로 읽어 (getConfigurationSection 은 jar 기본값만 있는 섹션을
         * 서버 config 에 빈 섹션으로 만든다) 빠진 키는 기본값, 칸 수는 0 ~ 36 · max ≥ min 으로 자른다.
         */
        public static Config read(ConfigurationSection root) {
            Object raw = root == null ? null : root.get("death.penalty");
            if (Boolean.FALSE.equals(raw)) return OFF;
            if (!(raw instanceof ConfigurationSection p)) return DEFAULT;
            Config d = DEFAULT;
            boolean xp = p.getBoolean("xp_progress_reset", d.xpProgressReset());
            double exit = p.getDouble("combat_exit_seconds", d.combatExitSeconds());
            boolean on = d.itemLoss();
            int min = d.slotsMin(), max = d.slotsMax();
            Set<String> safe = d.safeItems();
            Object loss = p.get("dungeon_item_loss");
            if (Boolean.FALSE.equals(loss)) {
                on = false;
            } else if (loss instanceof ConfigurationSection l) {
                on = l.getBoolean("enabled", on);
                min = l.getInt("slots_min", Math.min(min, l.getInt("slots_max", max))); // slots_max: 1 만 적으면 1칸 (min 기본 2 가 끌어올리지 않게)
                max = l.getInt("slots_max", max);
                safe = l.getStringList("safe_items").stream().filter(s -> s != null && !s.isBlank())
                        .map(s -> s.trim().toLowerCase(Locale.ROOT)).collect(Collectors.toSet());
            }
            min = Math.max(0, Math.min(STORAGE_SLOTS, min));
            max = Math.max(min, Math.min(STORAGE_SLOTS, max));
            GoldLoss gold = GoldLoss.read(p.get("gold_loss"), d.gold());
            return new Config(xp, on, min, max, safe, exit, gold);
        }
    }

    /** 어디서 죽었나. */
    public enum Where {
        /** 미궁 공략 중 쓰러짐 (죽음이 취소되고 관전 — {@code dungeon.Run#onMemberDeath}). */
        DUNGEON_RUN,
        /** 미궁 월드지만 공략 밖 (이미 쓰러져 관전 중 · 공략이 끝나는 중 · 닫힌 미궁에 남음) — 진짜 죽음, 소지품은 언제나 보존. */
        LABYRINTH_WORLD,
        /** 미궁 밖 (야생·마을·광산·네더·엔드, PvP 포함) — 소지품은 config death.keep_inventory 대로. */
        OUTSIDE
    }

    /** 이번 죽음에 할 일. */
    public record Plan(boolean resetXp, boolean destroySlots, boolean loseGold) {
        public static final Plan NONE = new Plan(false, false, false);
        public boolean any() { return resetXp || destroySlots || loseGold; }
    }

    /**
     * 경험치는 어디서든, 물건·골드는 미궁 공략 중 쓰러졌을 때만. 미궁 밖에서는 keep_inventory 와 상관없이 물건을 지우지 않는다 —
     * keep_inventory: false 서버는 바닐라처럼 그 자리에 떨어지고(주울 수 있음) 그 위에 더 빼앗지 않는다.
     * 관리자 시험 입장({@code /labadmin tpfloor})은 물건·골드를 잃지 않는다.
     */
    public static Plan plan(Config c, Where where, boolean adminTest) {
        if (c == null) return Plan.NONE;
        boolean run = where == Where.DUNGEON_RUN && !adminTest;
        boolean items = run && c.itemLoss() && c.slotsMax() > 0;
        boolean gold = run && c.gold().on();
        return new Plan(c.xpProgressReset(), items, gold);
    }

    /**
     * 언제나 안전한 물건인가.
     * <ul>
     *   <li>장비 (0.3.6.2): 미궁 무기·방어구(방패 포함)·장신구 ({@link ItemType#isGear}), 바닐라 장비 ({@link #vanillaGear}) — 가방에 있어도.</li>
     *   <li>열쇠·문장 (type key: 직업 문장 · 층 금고 열쇠 — 금고는 파티 모두의 몫이라 한 사람이 쓰러져 잃으면 남은 파티원까지 막힌다)</li>
     *   <li>광산 곡괭이 (type tool: 미궁에서 쓸 데가 없고 팔 수도 없는 광산 성장)</li>
     *   <li>미궁 활이 넣어 주는 무한 화살 (진짜 물건이 아니고 다시 생김) · config safe_items</li>
     * </ul>
     *
     * @param type   미궁 아이템 종류 (바닐라 아이템이면 null)
     * @param itemId items.yml id 또는 바닐라 이름 (소문자)
     */
    public static boolean alwaysSafe(ItemType type, String itemId, boolean labArrow, Set<String> safeItems) {
        if (labArrow || type == ItemType.KEY || type == ItemType.TOOL) return true;
        if (type != null && type.isGear()) return true;
        if (type == null && vanillaGear(itemId)) return true;
        return itemId != null && safeItems != null && safeItems.contains(itemId.toLowerCase(Locale.ROOT));
    }

    /** 바닐라 장비 중 이름으로 알아보는 것 (무기·갑옷·방패·겉날개). 곡괭이·삽·괭이 같은 도구는 아니다. */
    private static final Set<String> VANILLA_GEAR = Set.of("shield", "elytra", "trident", "mace", "bow", "crossbow");
    private static final List<String> VANILLA_GEAR_SUFFIX = List.of("_sword", "_axe", "_spear", "_helmet", "_chestplate",
            "_leggings", "_boots");

    /**
     * 바닐라 장비인가 (바닐라 이름, 소문자): 칼·도끼·창·삼지창·철퇴·활·쇠뇌 (스탯이 바닐라 무기로 쳐 준다), 투구·흉갑·각반·장화
     * (거북 등딱지 포함), 방패, 겉날개. 곡괭이(_pickaxe 는 _axe 로 끝나지 않음)·삽·괭이·낚싯대는 보통 물건.
     */
    public static boolean vanillaGear(String id) {
        if (id == null) return false;
        String k = id.toLowerCase(Locale.ROOT);
        int colon = k.indexOf(':');
        if (colon >= 0) k = k.substring(colon + 1);
        if (VANILLA_GEAR.contains(k)) return true;
        for (String s : VANILLA_GEAR_SUFFIX) if (k.endsWith(s)) return true;
        return false;
    }

    // ── 셜커 상자·꾸러미 (0.3.6.2) ──────────────────────────────────────

    /** 상자 규칙이 물건을 보는 법 (런타임 = ItemStack, 시험 = 가짜 물건). */
    public interface Box<S> {
        /** 빈 칸인가 (null 포함). */
        boolean empty(S stack);

        /** 언제나 안전한가 ({@link #alwaysSafe} — 장비·열쇠·광산 곡괭이·무한 화살·safe_items). */
        boolean keep(S stack);

        /** 셜커 상자·꾸러미처럼 담는 물건이면 안에 든 것 (자리 그대로, 빈 칸은 null 가능, 비었으면 빈 목록), 아니면 null. */
        List<S> contents(S stack);

        /** 안에 든 것만 바꾼 사본 (지운 자리는 null). */
        S withContents(S stack, List<S> contents);
    }

    /**
     * 이 칸을 뽑을 수 있나 (잃을 것이 있나). 빈 칸·안전한 물건은 아니다. 보통 물건이면 그렇다.
     * 상자·꾸러미는 상자 자체를 잃지 않으므로, 안에 잃을 것이 하나라도 있을 때만 (빈 상자 · 장비만 든 상자는 아니다).
     */
    public static <S> boolean losable(S stack, Box<S> a) { return losable(stack, a, 0); }

    private static <S> boolean losable(S stack, Box<S> a, int depth) {
        if (stack == null || a.empty(stack) || a.keep(stack)) return false;
        List<S> in = a.contents(stack);
        if (in == null) return true;
        if (depth >= MAX_DEPTH) return false;
        for (S c : in) if (losable(c, a, depth + 1)) return true;
        return false;
    }

    /**
     * 커서·제작 칸에서 떼어 둔 물건 가운데 꼭 돌려줄 것 — 언제나 안전한 것(장비 등)과 셜커 상자·꾸러미 (상자 자체는 잃지 않음).
     * 가방이 꽉 찼을 때 이것부터 넣는다 ({@code DeathPenalty#settleLoose}).
     */
    public static <S> boolean mustReturn(S stack, Box<S> a) {
        if (stack == null || a.empty(stack)) return false;
        return !losable(stack, a) || a.contents(stack) != null;
    }

    /**
     * 뽑힌 칸 처리. 보통 물건이면 통째로 잃는다 (null = 칸이 빈다). 상자·꾸러미면 상자는 남기고 안에서 잃을 것만 지운 사본
     * (장비·열쇠 같은 안전한 것과 그 자리는 그대로, 상자 속 꾸러미도 같은 규칙). 잃은 것은 {@code lost} 에 담는다.
     * 잃을 것이 없으면 그대로 돌려준다.
     */
    public static <S> S strip(S stack, Box<S> a, List<S> lost) { return strip(stack, a, lost, 0); }

    private static <S> S strip(S stack, Box<S> a, List<S> lost, int depth) {
        if (!losable(stack, a, depth)) return stack;
        List<S> in = a.contents(stack);
        if (in == null) {
            lost.add(stack);
            return null;
        }
        List<S> out = new ArrayList<>(in.size());
        for (S c : in) {
            if (!losable(c, a, depth + 1)) out.add(c);
            else if (a.contents(c) == null) {
                lost.add(c);
                out.add(null);
            } else {
                out.add(strip(c, a, lost, depth + 1));
            }
        }
        return a.withContents(stack, out);
    }

    // ── 퇴장 시전 ────────────────────────────────────────────────────────

    /**
     * 공략 중 스스로 나갈 때(/미궁 퇴장·귀환, 입구 메뉴 '귀환') 기다릴 초. 0 = 바로 나감.
     * 페널티가 하나라도 켜져 있고, 관리자 시험 입장이 아니고, 살아 있고(쓰러져 관전 중이면 바로), 전투 중일 때만.
     * 골드도 지켜 준다 (골드만 켜 두어도 시전).
     *
     * @param sinceHurtMs 마지막으로 피해를 받은 뒤 지난 ms (받은 적 없으면 음수)
     */
    public static double exitCastSeconds(Config c, boolean adminTest, boolean alive, long sinceHurtMs) {
        if (c == null || adminTest || !alive || c.combatExitSeconds() <= 0) return 0;
        if (!plan(c, Where.DUNGEON_RUN, false).any()) return 0;
        return inCombat(sinceHurtMs) ? c.combatExitSeconds() : 0;
    }

    /** 싸우는 중인가: 마지막 피해에서 {@link #COMBAT_MS} 안 (받은 적 없으면 음수 → 아님). 퇴장 시전·귀환 주문서와 같은 판정. */
    public static boolean inCombat(long sinceHurtMs) {
        return sinceHurtMs >= 0 && sinceHurtMs < COMBAT_MS;
    }

    // ── 싸우는 중 접속 끊기 (0.3.6.2 주인 결정) ─────────────────────────

    /** 공략 중 접속을 끊었을 때: 쓰러진 것으로 치고 페널티 (APPLY) · 지금처럼 공략에 남음 (NONE). */
    public enum QuitVerdict { APPLY, NONE }

    /**
     * 접속을 끊은 순간의 형편 ({@code dungeon.DungeonManager} 가 채움).
     *
     * @param inRun          공략 참가자 (떠나지 않음)
     * @param labyrinthWorld 미궁 월드에 있음 (입장 준비 중 마을 · 야생 · 광산이면 false)
     * @param adminTest      관리자 시험 입장 ({@code /labadmin tpfloor})
     * @param alive          살아 있음 (이미 쓰러져 관전 중이면 false)
     * @param ending         공략이 끝나는 중 (전멸 · 정복 · 관리자 종료)
     * @param sinceHurtMs    마지막 피해에서 지난 ms (받은 적 없으면 음수)
     * @param casting        싸우는 중이라 시작한 퇴장 시전(/미궁 퇴장 5초) · 귀환 주문서 시전 중
     * @param serverSide     서버 종료 · 재시작 · 플러그인 끄기 · 관리자가 내보냄(/kick · /ban) (플레이어가 끊은 것이 아님)
     */
    public record Quit(boolean inRun, boolean labyrinthWorld, boolean adminTest, boolean alive, boolean ending,
                       long sinceHurtMs, boolean casting, boolean serverSide) {}

    /**
     * 싸우는 중(10초 안에 맞음, 또는 싸우는 중에 시작한 퇴장·귀환 시전 중)에 접속을 끊으면 쓰러진 것으로 친다 — 쓰러지기 직전에 끊어
     * 페널티를 피하는 틈을 막는다. 진짜로 튕겨도 같다 (주인 결정). 퇴장 시전과 같은 조건에서만:
     * 공략 중 · 미궁 월드 · 살아 있음 · 공략이 끝나는 중이 아님 · 관리자 시험 입장이 아님 · {@code combat_exit_seconds} &gt; 0 ·
     * 페널티가 하나라도 켜짐. 무엇을 잃는지는 쓰러짐과 같이 {@link #plan} 이 정한다 (스위치마다 따로). 서버 쪽에서 끊은 것은 아니다.
     */
    public static QuitVerdict combatQuit(Config c, Quit q) {
        if (c == null || q == null || q.serverSide()) return QuitVerdict.NONE;
        if (!q.inRun() || !q.labyrinthWorld() || q.adminTest() || !q.alive() || q.ending()) return QuitVerdict.NONE;
        if (c.combatExitSeconds() <= 0 || !plan(c, Where.DUNGEON_RUN, false).any()) return QuitVerdict.NONE;
        return q.casting() || inCombat(q.sinceHurtMs()) ? QuitVerdict.APPLY : QuitVerdict.NONE;
    }

    /**
     * 서버 쪽에서 내보낸 것인가 ({@code PlayerKickEvent.Cause} 이름): {@code RESTART_COMMAND} = {@code /restart}(서버 재시작 —
     * 플러그인을 끄기 전에 모두 내보냄) · 관리자가 내보냄 = {@code KICKED} {@code /kick} (Paper 26.3 KickCommand, 예전 이름
     * KICK_COMMAND 는 그 별칭) · {@code BANNED} {@code /ban} · {@code IP_BANNED} {@code /ban-ip} · {@code WHITELIST}
     * ({@code /whitelist on}·{@code remove} 로 명단 밖이 됨). 관리자 /kick 을 벌하지 않으므로 /ban 도 같게.
     * 도배·이상한 움직임·시간 초과·같은 계정 접속 같은 것은 플레이어 쪽이라 보통 끊김과 같다.
     */
    public static boolean serverKick(String cause) {
        return cause != null && SERVER_KICKS.contains(cause);
    }

    private static final Set<String> SERVER_KICKS = Set.of("RESTART_COMMAND", "KICKED", "KICK_COMMAND", "BANNED", "IP_BANNED", "WHITELIST");

    /** 다시 접속했을 때 보여 줄 까닭 한 줄. */
    public static final String QUIT_DOWN_TEXT = "<#ff8a80>싸우는 중에 접속을 끊어 쓰러진 것으로 쳤습니다.</#ff8a80>";

    /** 남은 파티원에게. name 은 이미 이스케이프한 이름. */
    public static String quitDownPartyText(String name) {
        return "<red>" + name + "</red><gray> 님이 싸우는 중에 접속을 끊어 쓰러졌습니다.";
    }

    /** 5 → "5", 2.5 → "2.5". */
    public static String seconds(double s) {
        return s == Math.rint(s) ? Long.toString(Math.round(s)) : String.format(Locale.ROOT, "%.1f", s);
    }

    // ── 칸 고르기 ────────────────────────────────────────────────────────

    /** 잃을 칸 수: min ~ max 고르게 (max ≤ min 이면 min). */
    public static int rollCount(int min, int max, RandomGenerator rng) {
        int lo = Math.max(0, min), hi = Math.max(lo, max);
        return hi == lo ? lo : lo + rng.nextInt(hi - lo + 1);
    }

    /**
     * 칸마다 뽑을 수 있나. slots = 단축 칸 0~8 · 가방 9~35 · (있으면) {@link #OFFHAND} = 보조손.
     * 가방 칸은 {@link #losable}. 손에 든 칸(heldSlot)과 보조손은 셜커 상자·꾸러미이고 안에 잃을 것이 있을 때만 —
     * 상자는 남고 안의 장비 아닌 것만 사라진다 (가방 상자와 같음). 그 밖의 것은 손·보조손에 있으면 안전.
     */
    public static <S> boolean[] eligible(S[] slots, int heldSlot, Box<S> a) {
        int n = slots == null ? 0 : Math.min(CANDIDATE_SLOTS, slots.length);
        boolean[] out = new boolean[n];
        for (int i = 0; i < n; i++) {
            S it = slots[i];
            boolean hand = i == heldSlot || i == OFFHAND;
            out[i] = losable(it, a) && (!hand || a.contents(it) != null);
        }
        return out;
    }

    /**
     * 잃을 칸 고르기. eligible[i] = 그 칸에 잃을 것이 있음 ({@link #eligible}). heldSlot 은 언제나 뺀다
     * (-1 = 빼지 않음 — {@link #eligible} 이 손 칸을 이미 걸렀을 때). {@link #CANDIDATE_SLOTS} 이상은 보지 않는다.
     * 칸 수를 먼저 굴리고(min ~ max), 후보 가운데서 겹치지 않게 고르게 뽑는다. 후보가 모자라면 후보 전부.
     *
     * @return 고른 칸 번호 (오름차순, {@link #OFFHAND} = 보조손)
     */
    public static int[] pickSlots(boolean[] eligible, int heldSlot, int min, int max, RandomGenerator rng) {
        List<Integer> pool = new ArrayList<>();
        int n = eligible == null ? 0 : Math.min(CANDIDATE_SLOTS, eligible.length);
        for (int i = 0; i < n; i++) if (eligible[i] && i != heldSlot) pool.add(i);
        int want = Math.min(pool.size(), rollCount(min, max, rng));
        // 앞에서부터 부분 피셔-예이츠: 칸마다 뽑힐 확률이 같다
        for (int k = 0; k < want; k++) {
            int j = k + rng.nextInt(pool.size() - k);
            Integer t = pool.get(k);
            pool.set(k, pool.get(j));
            pool.set(j, t);
        }
        int[] out = new int[want];
        for (int k = 0; k < want; k++) out[k] = pool.get(k);
        Arrays.sort(out);
        return out;
    }

    // ── 경험치·골드 ──────────────────────────────────────────────────────

    /** 잃을 경험치 = 지금 레벨에서 모은 만큼. 최고 레벨(또는 그 위)이면 0. */
    public static long xpLost(int level, long xp, int maxLevel) {
        if (level >= maxLevel) return 0;
        return Math.max(0, xp);
    }

    /** 잃을 비율(%) 굴리기: min ~ max 고르게 (같으면 그 값). */
    public static double rollPercent(GoldLoss g, RandomGenerator rng) {
        if (g == null) return 0;
        double lo = g.minPercent(), hi = g.maxPercent();
        return hi <= lo ? lo : lo + rng.nextDouble() * (hi - lo);
    }

    /**
     * 잃을 골드 = 내림(지닌 골드 × percent / 100), cap 이 0 보다 크면 그 이하. 0 ~ 지닌 골드 (골드가 0 이하면 0).
     *
     * @param percent 0 ~ 100 ({@link #rollPercent})
     * @param cap     한 번에 잃는 상한 (0 이하 = 상한 없음)
     */
    public static long goldLost(long gold, double percent, long cap) {
        if (gold <= 0 || !(percent > 0)) return 0;
        double p = Math.min(100, percent);
        long lose = (long) Math.floor(gold * p / 100.0);
        if (cap > 0) lose = Math.min(lose, cap);
        return Math.max(0, Math.min(gold, lose));
    }

    /** 이번 쓰러짐에 잃을 골드 (꺼져 있으면 0). */
    public static long goldLost(long gold, GoldLoss g, RandomGenerator rng) {
        if (g == null || !g.on()) return 0;
        return goldLost(gold, rollPercent(g, rng), g.max());
    }

    // ── 안내 문구 ────────────────────────────────────────────────────────

    /**
     * 잃은 물건 하나. name = 채팅에 그대로 넣을 MiniMessage 조각 (이미 이스케이프했거나 {@code <lang:…>}).
     * box = 셜커 상자·꾸러미 안에서 잃었으면 그 상자 이름 (같은 꼴), 가방 칸이면 null.
     */
    public record Lost(String name, int count, String box) {
        public Lost(String name, int count) { this(name, count, null); }
    }

    /** 경험치만 (미궁 밖 죽음). */
    public static List<String> lines(List<Lost> lost, long xpLost) { return lines(lost, 0, xpLost); }

    /**
     * 채팅 줄 (Text.send 로 보냄). 같은 이름은 합친다. 1개짜리는 개수를 적지 않는다. 잃은 것이 없으면 빈 목록.
     * 예: "죽어서 잃었습니다: 철 주괴 ×13 · 셜커 상자 속: 빵 ×5" · "골드를 잃었습니다: 1,234G" ·
     * "이번 레벨 경험치가 처음으로 돌아갔습니다. (-1,234 XP)"
     */
    public static List<String> lines(List<Lost> lost, long goldLost, long xpLost) {
        List<String> out = new ArrayList<>(3);
        if (lost != null && !lost.isEmpty()) {
            Map<String, Map<String, Integer>> groups = new LinkedHashMap<>();
            groups.put("", new LinkedHashMap<>()); // 가방 칸 먼저
            for (Lost l : lost) {
                groups.computeIfAbsent(l.box() == null ? "" : l.box(), k -> new LinkedHashMap<>())
                        .merge(l.name(), Math.max(1, l.count()), Integer::sum);
            }
            StringBuilder sb = new StringBuilder("<#ff8a80>죽어서 잃었습니다:</#ff8a80> ");
            boolean firstGroup = true;
            for (var g : groups.entrySet()) {
                if (g.getValue().isEmpty()) continue;
                if (!firstGroup) sb.append("<gray> · </gray>");
                firstGroup = false;
                if (!g.getKey().isEmpty()) sb.append("<gray>").append(g.getKey()).append(" 속:</gray> ");
                boolean first = true;
                for (var e : g.getValue().entrySet()) {
                    if (!first) sb.append("<gray>, </gray>");
                    first = false;
                    sb.append("<white>").append(e.getKey()).append("</white>");
                    if (e.getValue() > 1) sb.append(" <gray>×").append(e.getValue()).append("</gray>");
                }
            }
            out.add(sb.toString());
        }
        if (goldLost > 0) {
            out.add("<#ff8a80>골드를 잃었습니다:</#ff8a80> <#f2c14e>" + Text.num(goldLost) + "G</#f2c14e>");
        }
        if (xpLost > 0) {
            out.add("<gray>이번 레벨 경험치가 처음으로 돌아갔습니다. <dark_gray>(-" + Text.num(xpLost) + " XP)");
        }
        return out;
    }

    /** 5 → "5", 12.5 → "12.5" (비율 글). */
    static String percent(double v) { return seconds(v); }

    /** "골드 5~25%(최대 15,000G)" — 비율이 같으면 하나, 상한이 없으면 괄호 없이. */
    static String goldText(GoldLoss g) {
        String pct = g.minPercent() == g.maxPercent() ? percent(g.maxPercent()) + "%"
                : percent(g.minPercent()) + "~" + percent(g.maxPercent()) + "%";
        return "골드 " + pct + (g.max() > 0 ? "(최대 " + Text.num(g.max()) + "G)" : "");
    }

    private static boolean items(Config c) { return c.itemLoss() && c.slotsMax() > 0; }

    private static String slotsText(Config c) {
        return c.slotsMin() == c.slotsMax() ? c.slotsMax() + "칸" : c.slotsMin() + "~" + c.slotsMax() + "칸";
    }

    /** 미궁에서 잃는 것 "물건 2~3칸과 골드 5~25%(최대 15,000G)" + 알맞은 조사 (을/를). 없으면 null. */
    private static String dungeonLoss(Config c, String bag) {
        boolean items = items(c), gold = c.gold().on();
        if (items && gold) return bag + slotsText(c) + "과 " + goldText(c.gold()) + "를";
        if (items) return bag + slotsText(c) + "을";
        if (gold) return goldText(c.gold()) + "를";
        return null;
    }

    /** 메인 메뉴 'PvP 규칙' 설명 줄 — PvP 를 꺼도 나온다 (페널티가 모두 꺼져 있으면 빈 목록). */
    public static List<String> menuLines(Config c) {
        List<String> out = new ArrayList<>(3);
        if (c == null) return out;
        if (c.xpProgressReset()) out.add("쓰러지면 이번 레벨 경험치를 잃습니다.");
        String loss = dungeonLoss(c, "물건 ");
        if (loss != null) out.add("미궁 안에서 쓰러지면 " + loss + (c.xpProgressReset() ? " 더 잃습니다." : " 잃습니다."));
        if (items(c)) out.add("장비·열쇠·광산 곡괭이는 잃지 않습니다.");
        return out;
    }

    /** 미궁에 처음 들어갈 때 한 번 보여 주는 안내 (페널티가 모두 꺼져 있으면 null). */
    public static String notice(Config c) {
        if (c == null) return null;
        String loss = dungeonLoss(c, "가방 속 물건 ");
        if (loss == null) {
            return c.xpProgressReset() ? "<#ffb27a>쓰러지면 이번 레벨 경험치가 처음으로 돌아갑니다.</#ffb27a> <gray>미궁 밖에서도 같습니다."
                    + quitText(c) : null;
        }
        String xp = c.xpProgressReset() ? " 잃고, 이번 레벨 경험치도 처음으로 돌아갑니다." : " 잃습니다.";
        // 곡괭이: 광산 곡괭이(type tool)만 안전 — 바닐라 곡괭이·삽 같은 도구는 보통 물건 ({@link #vanillaGear})
        String safe = items(c) ? " <gray>장비·열쇠·광산 곡괭이와 손에 든 물건은 안전합니다 (손에 든 상자 속 물건은 빼고)." : "";
        return "<#ffb27a>미궁 안에서 쓰러지면 " + loss + xp + "</#ffb27a>" + safe + quitText(c);
    }

    /** 안내 끝 한 마디: 싸우는 중 접속 끊김도 쓰러짐 ({@link #combatQuit} 이 켜질 때만 — 친구들은 README 를 읽지 않으므로). */
    private static String quitText(Config c) {
        return c.combatExitSeconds() > 0 && plan(c, Where.DUNGEON_RUN, false).any()
                ? " <gray>싸우는 중에 접속을 끊어도 쓰러진 것으로 칩니다." : "";
    }

    /** 전투 중에 나가려 할 때 (시전 시작). */
    public static String exitCastText(double seconds) {
        return "<gray>싸우는 중이라 <white>" + seconds(seconds) + "초</white> 뒤에 나갑니다. 그동안 맞으면 끊깁니다.";
    }
}
