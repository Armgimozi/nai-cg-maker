package kr.labyrinth.content;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * content/enhance.yml — 장비별 강화 재료 (GDD §11.13). 골드·강화석(config.yml {@code enhance:})에 더해 <b>그 장비만</b> 드는 재료.
 * <ul>
 *   <li>구간(bands)은 목표 단계 기준 — 기본 low +1~+3 · mid +4~+6 · high +7~+10. 마지막 구간 너머는 마지막 구간.</li>
 *   <li>개수 목록은 구간 안 목표 단계 순 (모자라면 마지막 값, 0 = 그 단계엔 필요 없음).</li>
 *   <li>파일이 없거나(선택 파일) 장비 항목이 없으면 그 장비는 강화석·골드만 든다.</li>
 * </ul>
 * 순수 데이터 — Bukkit 의존 없음.
 *
 * @param loaded   파일을 읽었는가 (없으면 false)
 * @param items    장비 id → 구간 id → 재료 (YAML 순서 = 표시 순서)
 * @param warnings 읽으면서 무시한 항목 (없는 재료·장비 등) — 강화 서비스가 시작할 때 한 번 경고한다
 */
public record EnhanceDef(boolean loaded, List<Band> bands, Map<String, Map<String, List<Material>>> items, List<String> warnings) {

    /** 단계 구간 (목표 단계 from ~ to). */
    public record Band(String id, int from, int to) {
        public boolean contains(int target) { return target >= from && target <= to; }
    }

    /** 구간 안 재료 한 줄: 목표 단계별 개수. */
    public record Material(String item, List<Integer> amounts) {
        /** 구간 안 index 번째 목표 단계 개수 (모자라면 마지막 값). */
        public int amount(int index) {
            if (amounts.isEmpty()) return 0;
            return Math.max(0, amounts.get(Math.max(0, Math.min(amounts.size() - 1, index))));
        }
    }

    /** 목표 단계 한 번 시도의 재료 (개수 &gt; 0). */
    public record Cost(String item, int amount) {}

    public static final List<Band> DEFAULT_BANDS = List.of(new Band("low", 1, 3), new Band("mid", 4, 6), new Band("high", 7, 10));
    public static final EnhanceDef EMPTY = new EnhanceDef(false, DEFAULT_BANDS, Map.of(), List.of());

    /** 이 장비 항목이 있는가 (없으면 강화석·골드만). */
    public boolean has(String itemId) { return itemId != null && items.containsKey(itemId); }

    /** 목표 단계가 속한 구간 (마지막 구간 너머 = 마지막 구간, 첫 구간 앞 = null). */
    public Band band(int target) {
        if (bands.isEmpty() || target < 1) return null;
        for (Band b : bands) if (b.contains(target)) return b;
        Band last = bands.get(bands.size() - 1);
        return target > last.to() ? last : null;
    }

    /** 목표 단계 한 번 시도에 드는 그 장비의 재료 (강화석 제외). 항목이 없으면 빈 목록. */
    public List<Cost> costs(String itemId, int target) {
        Map<String, List<Material>> entry = itemId == null ? null : items.get(itemId);
        Band b = band(target);
        if (entry == null || b == null) return List.of();
        List<Material> mats = entry.get(b.id());
        if (mats == null) return List.of();
        int index = Math.min(target, b.to()) - b.from();
        List<Cost> out = new ArrayList<>();
        for (Material m : mats) {
            int n = m.amount(index);
            if (n > 0) out.add(new Cost(m.item(), n));
        }
        return List.copyOf(out);
    }
}
