package kr.labyrinth.items;

import kr.labyrinth.content.ItemDef;

/** 착용 조건 (레벨·직업) — 순수 로직. 조건을 못 맞춘 장비는 스탯·무기 스킬·아우라 효과가 없다. */
public final class EquipRules {

    public enum Problem { NONE, LEVEL, CLASS }

    private EquipRules() {}

    public static Problem check(ItemDef def, int level, String classId) {
        if (def == null || !def.isGear()) return Problem.NONE;
        if (level < def.levelReq()) return Problem.LEVEL;
        if (!def.usableBy(classId)) return Problem.CLASS;
        return Problem.NONE;
    }

    public static boolean usable(ItemDef def, int level, String classId) {
        return check(def, level, classId) == Problem.NONE;
    }
}
