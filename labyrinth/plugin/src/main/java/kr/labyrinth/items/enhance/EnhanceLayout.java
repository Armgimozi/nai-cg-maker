package kr.labyrinth.items.enhance;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.core.Log;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * 강화 창 비용 줄 배치 (골드 · 강화석 · 장비 재료 · 보호 주문서). 다른 칸(규칙·장비·확률·[강화]·착용 줄…)은 고정.
 * <p>
 * 배경 그림(gui_enhance)에는 소켓이 그려져 있어서 아이콘이 소켓 위에 와야 한다 — 소켓 자리는 glyphs.yml
 * {@code menus.enhance.slots} 가 알려 준다 (리소스 팩과 같이 만들어지는 계약):
 * <ul>
 *   <li>{@code materials: [..]} 까지 있으면 그대로 (재료 소켓이 그려진 배경).</li>
 *   <li>{@code gold · stone · protection} 만 있으면(재료 소켓이 없는 예전 배경 — 29 · 31 · 33) 그 셋은 소켓 위에 두고,
 *       재료는 강화석 줄의 빈 칸 중 강화석에서 가까운 순(30 · 32 · 28)에 둔다.</li>
 *   <li>배경을 쓰지 않으면(글리프 끔) 왼쪽부터 골드 28 · 강화석 29 · 재료 30~32 · 주문서 33.</li>
 * </ul>
 * 값이 틀리면(칸 밖 · 겹침 · 고정 칸과 충돌) 예전 소켓 배치로 돌아간다 — 절대 실패하지 않는다.
 */
record EnhanceLayout(int gold, int stone, int[] materials, int protection) {

    /** 배경 없음(글리프 끔) — 왼쪽부터 골드 · 강화석 · 재료 3칸 · 주문서. */
    static final EnhanceLayout PLAIN = new EnhanceLayout(28, 29, new int[] {30, 31, 32}, 33);
    /** 소켓이 골드 29 · 강화석 31 · 주문서 33 뿐인 배경 (재료는 사이 새김선 위 30 · 32 와 왼쪽 28). */
    static final EnhanceLayout SOCKETS_29_31_33 = new EnhanceLayout(29, 31, new int[] {30, 32, 28}, 33);
    /** 재료 칸 수 (생성된 enhance.yml 은 시도 1번당 최대 3종 — 더 많으면 마지막 칸과 [강화] 버튼 설명에 전부). */
    static final int MATERIAL_SLOTS = 3;
    /** 고정 칸: 규칙 4 · 장비 11 · 확률 13 · [강화] 15 · 실패하면 22 · 착용 37~42 · 도움말 43 · 대장간 45 · 보유 골드 49 · 닫기 53. */
    static final Set<Integer> FIXED = Set.of(4, 11, 13, 15, 22, 37, 38, 39, 40, 41, 42, 43, 45, 49, 53);
    private static final int SIZE = 54;

    EnhanceLayout {
        materials = materials.clone();
    }

    @Override
    public int[] materials() { return materials.clone(); }

    /**
     * glyphs.yml {@code menus.enhance.slots} 원문(없으면 null) → 배치.
     * @param background 강화 창에 전용 배경(gui_enhance)을 깔았는가 — 아니면 소켓이 없으니 {@link #PLAIN}
     */
    static EnhanceLayout of(Map<String, Object> slots, boolean background) {
        if (!background) return PLAIN;
        if (slots == null) return SOCKETS_29_31_33;
        Integer gold = slot(slots.get("gold")), stone = slot(slots.get("stone")), prot = slot(slots.get("protection"));
        if (gold == null || stone == null || prot == null) return SOCKETS_29_31_33;
        List<Integer> mats = new ArrayList<>();
        if (slots.get("materials") instanceof List<?> l) {
            for (Object o : l) {
                Integer s = slot(o);
                if (s != null && mats.size() < MATERIAL_SLOTS) mats.add(s);
            }
        }
        if (mats.isEmpty()) mats = nearStone(stone, new HashSet<>(List.of(gold, stone, prot)));
        EnhanceLayout out = new EnhanceLayout(gold, stone, mats.stream().mapToInt(Integer::intValue).toArray(), prot);
        return out.valid() ? out : SOCKETS_29_31_33;
    }

    /** glyphs.yml 파일 → {@code menus.enhance.slots} 원문 (파일 · 항목이 없거나 못 읽으면 null). */
    static Map<String, Object> readSlots(Path glyphsYml) {
        if (glyphsYml == null || !Files.exists(glyphsYml)) return null;
        try {
            YamlConfiguration y = new YamlConfiguration();
            y.loadFromString(Files.readString(glyphsYml));
            ConfigurationSection s = y.getConfigurationSection("menus.enhance.slots");
            return s == null ? null : Map.copyOf(s.getValues(false));
        } catch (Exception e) {
            Log.warn("[강화] glyphs.yml menus.enhance.slots 읽기 실패 (예전 소켓 배치로 계속): " + e.getMessage());
            return null;
        }
    }

    /** 강화석 줄의 빈 칸을 강화석에서 가까운 순으로 (거리가 같으면 왼쪽 먼저, 테두리 열 제외 — 29·31·33 이면 30 · 32 · 28). */
    private static List<Integer> nearStone(int stone, Set<Integer> used) {
        int row = stone / 9;
        List<Integer> free = new ArrayList<>();
        for (int c = 1; c < 8; c++) {
            int s = row * 9 + c;
            if (!used.contains(s) && !FIXED.contains(s)) free.add(s);
        }
        free.sort(Comparator.comparingInt((Integer s) -> Math.abs(s - stone)).thenComparing(s -> s > stone));
        return new ArrayList<>(free.subList(0, Math.min(MATERIAL_SLOTS, free.size())));
    }

    /** 칸이 모두 창 안이고, 서로 · 고정 칸과 겹치지 않는가. */
    boolean valid() {
        Set<Integer> seen = new HashSet<>();
        List<Integer> all = new ArrayList<>(List.of(gold, stone, protection));
        for (int m : materials) all.add(m);
        if (materials.length == 0) return false;
        for (int s : all) {
            if (s < 0 || s >= SIZE || FIXED.contains(s) || !seen.add(s)) return false;
        }
        return true;
    }

    private static Integer slot(Object o) {
        return o instanceof Number n && n.doubleValue() == Math.rint(n.doubleValue()) ? n.intValue() : null;
    }

    @Override
    public boolean equals(Object o) {
        return o instanceof EnhanceLayout l && l.gold == gold && l.stone == stone && l.protection == protection
                && Arrays.equals(l.materials, materials);
    }

    @Override
    public int hashCode() { return 31 * (31 * (31 * gold + stone) + protection) + Arrays.hashCode(materials); }

    @Override
    public String toString() {
        return "골드 " + gold + " · 강화석 " + stone + " · 재료 " + Arrays.toString(materials) + " · 주문서 " + protection;
    }
}
