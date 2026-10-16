package kr.labyrinth.content;

import java.util.List;
import java.util.Map;
import java.util.NavigableMap;

/**
 * items.yml sets: 세트 효과. bonuses 키 = 착용 개수(이상), 값 = 스탯 키 → 수치.
 * look = 겉모습 (heavy · light · cloth — 장비 텍스처도 이 값). lookEffects = false 면 평상복 (겉모습 효과 없음, 4부위로 안 셈 —
 * 수련생·길잡이, items.yml {@code look_effects: false}).
 */
public record ItemSetDef(String id, String name, String look, List<String> pieces,
                         NavigableMap<Integer, Map<String, Double>> bonuses, boolean lookEffects) {

    /** 0.3.4 꼴 (겉모습 효과 있음). */
    public ItemSetDef(String id, String name, String look, List<String> pieces, NavigableMap<Integer, Map<String, Double>> bonuses) {
        this(id, name, look, pieces, bonuses, true);
    }

    /** 이 세트 부위의 겉모습 (평상복이면 PLAIN, 모르는 look 이면 null). */
    public ArmorLook armorLook() {
        if (!lookEffects) return ArmorLook.PLAIN;
        ArmorLook l = ArmorLook.byId(look);
        return l != null && l.real() ? l : null;
    }
}
