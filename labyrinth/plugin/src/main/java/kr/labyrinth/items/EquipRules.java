package kr.labyrinth.items;

import kr.labyrinth.content.ItemDef;

/**
 * 착용 조건 (레벨) — 순수 로직. 조건을 못 맞춘 장비는 스탯·무기 스킬·아우라 효과가 없다.
 * 직업 제한은 없다 — 어느 직업이든 모든 장비를 쓴다 (GDD §4.4, items.yml {@code classes} 는 추천 직업).
 */
public final class EquipRules {

    public enum Problem { NONE, LEVEL }

    private EquipRules() {}

    /** @param classId 직업 (판정에 쓰지 않음 — 호출부 호환용) */
    public static Problem check(ItemDef def, int level, String classId) {
        if (def == null || !def.isGear()) return Problem.NONE;
        if (level < def.levelReq()) return Problem.LEVEL;
        return Problem.NONE;
    }

    public static boolean usable(ItemDef def, int level, String classId) {
        return check(def, level, classId) == Problem.NONE;
    }
}
