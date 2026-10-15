package kr.labyrinth.classes;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.core.Settings;

/**
 * 시작 꾸러미 받은 양 기록과 모자란 몫 계산 (순수 — 단위 테스트). 꾸러미 목록을 늘리면 이미 받은 사람에게는 차이만 준다.
 * 기록 = PlayerData ext {@link #GOT}: "아이템id*개수" 목록 (골드는 {@link #GOLD}*n). 아이템 id 에 ':'·'.' 이 있어도 안전하게 문자열 목록으로 둔다.
 */
final class StarterKit {

    /** 받은 양 기록 (ext). */
    static final String GOT = "starter.kit_got";
    /** 예전 판 기록 — 받았으면 true. 그때 목록은 {@link Settings#LEGACY_STARTER_KIT_032}, 골드 0. */
    static final String LEGACY_FLAG = "starter.kit";
    /** 골드 줄의 이름. */
    static final String GOLD = "$gold";

    private StarterKit() {}

    /** ext 에서 지금까지 받은 양. 새 기록이 없고 예전 표시만 있으면 예전 목록을 받은 것으로 본다. */
    static Map<String, Integer> received(Map<String, Object> ext) {
        Map<String, Integer> got = new LinkedHashMap<>();
        if (ext.get(GOT) instanceof List<?> list) {
            for (Object o : list) {
                String s = String.valueOf(o);
                int i = s.lastIndexOf('*');
                if (i <= 0) continue;
                try {
                    got.merge(s.substring(0, i), Math.max(0, Integer.parseInt(s.substring(i + 1).trim())), Integer::sum);
                } catch (NumberFormatException ignored) {
                    // 망가진 줄은 건너뛴다
                }
            }
        } else if (Boolean.TRUE.equals(ext.get(LEGACY_FLAG))) {
            for (Settings.KitItem k : Settings.LEGACY_STARTER_KIT_032) got.merge(k.item(), k.amount(), Integer::sum);
        }
        return got;
    }

    /** 꾸러미(목록 + 골드) 대비 모자란 몫. 이미 받은 양 이상이면 0 → 빠진다. 순서는 꾸러미 순서, 골드는 맨 끝. */
    static Map<String, Integer> owed(List<Settings.KitItem> kit, int gold, Map<String, Integer> got) {
        Map<String, Integer> want = new LinkedHashMap<>();
        for (Settings.KitItem k : kit) want.merge(k.item(), k.amount(), Integer::sum);
        if (gold > 0) want.put(GOLD, gold);
        Map<String, Integer> out = new LinkedHashMap<>();
        want.forEach((id, n) -> {
            int left = n - got.getOrDefault(id, 0);
            if (left > 0) out.put(id, left);
        });
        return out;
    }

    /** 받은 양 + 이번에 준 양 → ext 에 넣을 목록. */
    static List<String> record(Map<String, Integer> got, Map<String, Integer> given) {
        Map<String, Integer> all = new LinkedHashMap<>(got);
        given.forEach((id, n) -> all.merge(id, n, Integer::sum));
        List<String> out = new ArrayList<>();
        all.forEach((id, n) -> out.add(id + "*" + n));
        return out;
    }
}
