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
 * 0.3.6.1 죽음 페널티 — 순수 규칙 (서버 없이 시험). 실제 적용은 {@link DeathPenalty}.
 * <ul>
 *   <li>어디서 죽든(미궁·야생·마을·네더·엔드·PvP) 지금 레벨에서 모은 경험치가 0 이 된다. 레벨은 내려가지 않고, 최고 레벨이면 아무것도 없다.</li>
 *   <li>미궁 공략 중 쓰러졌을 때만 가방 칸 slotsMin ~ slotsMax 개(고르게)를 통째로 잃는다. 단축 칸 + 가방 36칸 중
 *       손에 든 칸은 빼고, 입은 갑옷·보조손·장신구(가방 밖)는 애초에 후보가 아니다. 빈 칸은 세지 않고, 후보가 모자라면 있는 만큼.
 *       잃은 물건은 지워진다 (떨구지 않음).</li>
 *   <li>열쇠·문장(items.yml type key), 미궁 활의 무한 화살, config safe_items 는 언제나 안전.</li>
 * </ul>
 * config: {@code death.penalty} (키가 없으면 {@link Config#DEFAULT} — 예전 config.yml 도 jar 만 바꾸면 켜진다).
 */
public final class DeathPenaltyRules {

    private DeathPenaltyRules() {}

    /** 단축 칸 0~8 + 가방 9~35 ({@code PlayerInventory#getStorageContents}). 갑옷 36~39 · 보조손 40 은 넣지 않는다. */
    public static final int STORAGE_SLOTS = 36;

    /**
     * config.yml {@code death.penalty}. 끄기: {@code penalty: false} (전부) · {@code dungeon_item_loss: false} (물건만).
     *
     * @param safeItems 잃지 않는 아이템 — items.yml id 또는 바닐라 이름(diamond 처럼), 소문자
     */
    public record Config(boolean xpProgressReset, boolean itemLoss, int slotsMin, int slotsMax, Set<String> safeItems) {
        public static final Config DEFAULT = new Config(true, true, 2, 3, Set.of());
        public static final Config OFF = new Config(false, false, 2, 3, Set.of());

        public Config {
            safeItems = safeItems == null ? Set.of() : Set.copyOf(safeItems);
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
            boolean on = d.itemLoss();
            int min = d.slotsMin(), max = d.slotsMax();
            Set<String> safe = d.safeItems();
            Object loss = p.get("dungeon_item_loss");
            if (Boolean.FALSE.equals(loss)) {
                on = false;
            } else if (loss instanceof ConfigurationSection l) {
                on = l.getBoolean("enabled", on);
                min = l.getInt("slots_min", min);
                max = l.getInt("slots_max", max);
                safe = l.getStringList("safe_items").stream().filter(s -> s != null && !s.isBlank())
                        .map(s -> s.trim().toLowerCase(Locale.ROOT)).collect(Collectors.toSet());
            }
            min = Math.max(0, Math.min(STORAGE_SLOTS, min));
            max = Math.max(min, Math.min(STORAGE_SLOTS, max));
            return new Config(xp, on, min, max, safe);
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
    public record Plan(boolean resetXp, boolean destroySlots) {
        public static final Plan NONE = new Plan(false, false);
        public boolean any() { return resetXp || destroySlots; }
    }

    /**
     * 경험치는 어디서든, 물건은 미궁 공략 중 쓰러졌을 때만. 미궁 밖에서는 keep_inventory 와 상관없이 물건을 지우지 않는다 —
     * keep_inventory: false 서버는 바닐라처럼 그 자리에 떨어지고(주울 수 있음) 그 위에 더 빼앗지 않는다.
     * 관리자 시험 입장({@code /labadmin tpfloor})은 물건을 잃지 않는다.
     */
    public static Plan plan(Config c, Where where, boolean adminTest) {
        if (c == null) return Plan.NONE;
        boolean items = c.itemLoss() && c.slotsMax() > 0 && where == Where.DUNGEON_RUN && !adminTest;
        return new Plan(c.xpProgressReset(), items);
    }

    /**
     * 언제나 안전한 물건인가. 열쇠·문장(type key: 직업 문장 · 층 금고 열쇠 — 금고는 파티 모두의 몫이라 한 사람이 쓰러져 잃으면
     * 남은 파티원까지 막힌다), 미궁 활이 넣어 주는 무한 화살(진짜 물건이 아니고 다시 생김), config safe_items.
     *
     * @param type   미궁 아이템 종류 (바닐라 아이템이면 null)
     * @param itemId items.yml id 또는 바닐라 이름 (소문자)
     */
    public static boolean alwaysSafe(ItemType type, String itemId, boolean labArrow, Set<String> safeItems) {
        if (labArrow || type == ItemType.KEY) return true;
        return itemId != null && safeItems != null && safeItems.contains(itemId.toLowerCase(Locale.ROOT));
    }

    /** 잃을 칸 수: min ~ max 고르게 (max ≤ min 이면 min). */
    public static int rollCount(int min, int max, RandomGenerator rng) {
        int lo = Math.max(0, min), hi = Math.max(lo, max);
        return hi == lo ? lo : lo + rng.nextInt(hi - lo + 1);
    }

    /**
     * 잃을 칸 고르기. eligible[i] = 그 칸에 물건이 있고 안전하지 않음. heldSlot(손에 든 단축 칸)과 36 이상은 언제나 뺀다.
     * 칸 수를 먼저 굴리고(min ~ max), 후보 가운데서 겹치지 않게 고르게 뽑는다. 후보가 모자라면 후보 전부.
     *
     * @return 고른 칸 번호 (오름차순)
     */
    public static int[] pickSlots(boolean[] eligible, int heldSlot, int min, int max, RandomGenerator rng) {
        List<Integer> pool = new ArrayList<>();
        int n = eligible == null ? 0 : Math.min(STORAGE_SLOTS, eligible.length);
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

    /** 잃을 경험치 = 지금 레벨에서 모은 만큼. 최고 레벨(또는 그 위)이면 0. */
    public static long xpLost(int level, long xp, int maxLevel) {
        if (level >= maxLevel) return 0;
        return Math.max(0, xp);
    }

    /** 잃은 물건 한 칸. name = 채팅에 그대로 넣을 MiniMessage 조각 (이미 이스케이프했거나 {@code <lang:…>}). */
    public record Lost(String name, int count) {}

    /**
     * 채팅 줄 (Text.send 로 보냄). 같은 이름은 합친다. 1개짜리는 개수를 적지 않는다. 잃은 것이 없으면 빈 목록.
     * 예: "죽어서 잃었습니다: 철 주괴 ×13, 하급 치유 물약 ×5" · "이번 레벨 경험치가 처음으로 돌아갔습니다. (-1,234 XP)"
     */
    public static List<String> lines(List<Lost> lost, long xpLost) {
        List<String> out = new ArrayList<>(2);
        if (lost != null && !lost.isEmpty()) {
            Map<String, Integer> merged = new LinkedHashMap<>();
            for (Lost l : lost) merged.merge(l.name(), Math.max(1, l.count()), Integer::sum);
            StringBuilder sb = new StringBuilder("<#ff8a80>죽어서 잃었습니다:</#ff8a80> ");
            boolean first = true;
            for (var e : merged.entrySet()) {
                if (!first) sb.append("<gray>, </gray>");
                first = false;
                sb.append("<white>").append(e.getKey()).append("</white>");
                if (e.getValue() > 1) sb.append(" <gray>×").append(e.getValue()).append("</gray>");
            }
            out.add(sb.toString());
        }
        if (xpLost > 0) {
            out.add("<gray>이번 레벨 경험치가 처음으로 돌아갔습니다. <dark_gray>(-" + Text.num(xpLost) + " XP)");
        }
        return out;
    }

    /** 메인 메뉴 PvP 설명 한 줄 (페널티가 모두 꺼져 있으면 null). */
    public static String menuLine(Config c) {
        if (c == null) return null;
        boolean items = c.itemLoss() && c.slotsMax() > 0;
        String slots = slotsText(c);
        if (c.xpProgressReset() && items) return "쓰러지면 이번 레벨 경험치를 잃고, 미궁 안이면 가방 물건 " + slots + "도 잃습니다.";
        if (c.xpProgressReset()) return "쓰러지면 이번 레벨 경험치를 잃습니다.";
        if (items) return "미궁 안에서 쓰러지면 가방 물건 " + slots + "을 잃습니다.";
        return null;
    }

    private static String slotsText(Config c) {
        return c.slotsMin() == c.slotsMax() ? c.slotsMax() + "칸" : c.slotsMin() + "~" + c.slotsMax() + "칸";
    }

    /** 미궁에 처음 들어갈 때 한 번 보여 주는 안내 (물건 잃기가 꺼져 있으면 null). */
    public static String notice(Config c) {
        if (c == null || !c.itemLoss() || c.slotsMax() <= 0) return null;
        String slots = slotsText(c);
        String xp = c.xpProgressReset() ? "사라지고, 이번 레벨 경험치도 처음으로 돌아갑니다." : "사라집니다.";
        return "<#ffb27a>미궁 안에서 쓰러지면 가방 속 물건 " + slots + "이 " + xp
                + "</#ffb27a> <gray>손에 든 것·입은 장비·장신구·보조손은 안전합니다.";
    }
}
