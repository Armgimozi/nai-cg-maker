package kr.labyrinth.items;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

/**
 * 0.3.5 → 0.3.6 옛 광물 재료 바꾸기 (순수 — 단위 테스트 대상). 계약 tools/data/036/materials.json {@code conversion}
 * (§0 주인 늦은 결정 4 반영 — 불씨 조각은 불씨 혼으로).
 * <ul>
 *   <li>1:1, 그 자리에서 id 만 바꾼다 (칸·개수 그대로). 주괴 칸 옛 재료 → 그 층 장비 레시피가 가장 많이 쓰는 금속의 광석,
 *       몬스터 칸 옛 재료 → 새 몬스터 재료 ({@link #MAP}). 배포 전 시험 서버에만 있던 잿불 가죽도 잿불 비늘로 ({@link #PRE_RELEASE}).</li>
 *   <li>PDC 의 원래 {@code item_id} 를 먼저 본다 — 지금 content 의 {@code defOf()} 로 거르지 않는다 (옛 id 는 content 에 없다, R §2-7).</li>
 *   <li>결과는 ItemService 로 새로 만든 아이템 그대로다 ({@link Access#fresh}) — 원래 있던 광석과 겹쳐진다 (isSimilar).</li>
 *   <li>셜커 상자·꾸러미 안도 (안의 안까지) 바꾼다. 모르는 id·미궁 아이템이 아닌 것은 그대로, 두 번 해도 같다.</li>
 *   <li>새 id 가 지금 content 에 없으면(손으로 고친 items.yml) 바꾸지 않는다 — 시작 때 {@link #missingTargets} 로 경고 1줄.</li>
 * </ul>
 * 입구(접속 때 가방·엔더 상자 · 보관함 열 때 · 줍기·손에 들기 · 창 닫을 때 · 액자·갑옷 거치대·바닥 아이템)는 {@link ItemMigration036Listener}.
 */
public final class ItemMigration036 {

    /** 옛 id → 새 id (materials.json conversion.map). */
    public static final Map<String, String> MAP = orderedMap(
            "rusted_iron", "iron_ore",
            "slag_ingot", "gold_ore",
            "ember_shard", "ember_soul",
            "rime_crystal", "gold_ore",
            "amethyst_shard", "gold_ore",
            "prism_dust", "resonant_sinew",
            "brass_gear", "orichalcum_ore",
            "mainspring", "clock_oil");
    /** 배포 전 시험 서버에만 있던 id (materials.json conversion.pre_release). */
    public static final Map<String, String> PRE_RELEASE = orderedMap("cinder_hide", "cinder_scale");

    /** 첫 접속 안내 (ext {@code mat036.notice} — kr.labyrinth.mine.MineNames.EXT_MAT036_NOTICE). */
    public static final String NOTICE = "<gray>광산이 열렸습니다. 녹슨 철괴·슬래그 주괴 같은 광물 재료는 광석으로, 불씨 조각·프리즘 가루·태엽 용수철은 "
            + "새 몬스터 재료로 바뀌었습니다. 광석은 제련소나 광산 관리소에서 주괴로 녹이세요.</gray>";

    private ItemMigration036() {}

    /** 아이템 한 묶음을 보는 법 — 서버에서는 ItemStack, 시험에서는 가짜. */
    public interface Access<S> {
        /** PDC 의 원래 item_id (미궁 아이템이 아니면 null). */
        String itemId(S stack);

        int amount(S stack);

        /** 셜커 상자·꾸러미처럼 안에 든 것이 있으면 그 목록 (빈 칸은 null 가능), 아니면 null. */
        List<S> contents(S stack);

        /** 안에 든 것만 바꾼 사본. */
        S withContents(S stack, List<S> contents);

        /** ItemService 로 새로 만든 아이템 (그 id · 개수). 만들 수 없으면 null. */
        S fresh(String id, int amount);
    }

    /** 바꿀 새 id — 옛 id 가 아니거나 새 id 가 지금 content 에 없으면 null. */
    public static String target(String oldId, Predicate<String> exists) {
        if (oldId == null) return null;
        String to = MAP.get(oldId);
        if (to == null) to = PRE_RELEASE.get(oldId);
        return to != null && exists.test(to) ? to : null;
    }

    /** 옛 id 인가 (바꿀 수 있든 없든). */
    public static boolean retired(String id) { return id != null && (MAP.containsKey(id) || PRE_RELEASE.containsKey(id)); }

    /** 지금 content 에 없는 새 id (손으로 고친 items.yml) — 시작 때 경고. 모두 있으면 빈 목록. */
    public static List<String> missingTargets(Predicate<String> exists) {
        List<String> out = new ArrayList<>();
        for (String to : MAP.values()) if (!exists.test(to) && !out.contains(to)) out.add(to);
        for (String to : PRE_RELEASE.values()) if (!exists.test(to) && !out.contains(to)) out.add(to);
        return out;
    }

    /**
     * 한 묶음 바꾸기. 바꿀 것이 없으면 <b>같은 객체</b>를 돌려준다 (부르는 쪽이 == 로 바뀌었는지 본다).
     * 안에 든 것이 있는 아이템은 안을 (안의 안까지) 바꾼다.
     */
    public static <S> S convert(S stack, Access<S> a, Predicate<String> exists) {
        return convert(stack, a, exists, 0);
    }

    private static <S> S convert(S stack, Access<S> a, Predicate<String> exists, int depth) {
        if (stack == null || depth > 8) return stack;
        String to = target(a.itemId(stack), exists);
        if (to != null) {
            S fresh = a.fresh(to, Math.max(1, a.amount(stack)));
            return fresh == null ? stack : fresh;
        }
        List<S> in = a.contents(stack);
        if (in == null || in.isEmpty()) return stack;
        List<S> out = new ArrayList<>(in.size());
        boolean changed = false;
        for (S s : in) {
            S c = convert(s, a, exists, depth + 1);
            changed |= c != s;
            out.add(c);
        }
        return changed ? a.withContents(stack, out) : stack;
    }

    /** 칸 목록 바꾸기 (가방·엔더 상자·상자). 바꾼 칸 수. 칸 배열을 그 자리에서 고친다. */
    public static <S> int convertAll(S[] slots, Access<S> a, Predicate<String> exists) {
        int n = 0;
        for (int i = 0; i < slots.length; i++) {
            S c = convert(slots[i], a, exists);
            if (c != slots[i]) {
                slots[i] = c;
                n++;
            }
        }
        return n;
    }

    private static Map<String, String> orderedMap(String... kv) {
        Map<String, String> m = new LinkedHashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) m.put(kv[i], kv[i + 1]);
        return java.util.Collections.unmodifiableMap(m);
    }
}
