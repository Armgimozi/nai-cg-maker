package kr.labyrinth.items;

import java.util.Map;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.stats.Stat;

/**
 * 착용 조건 (요구 능력치) — 순수 로직. 레벨 제한·직업 제한은 없다 (GDD §4.4, items.yml {@code classes} 는 추천 직업).
 * <ul>
 *   <li>무기·방어구·방패만 {@code requires}/{@code requires_any} 를 본다. 장신구·재료·소모품은 언제나 통과.</li>
 *   <li>판정 능력치 = 직업 기본 + 분배 포인트 + 칭호 보너스 ({@link StatRequirement#playerStats}, 장비 제외).</li>
 *   <li>못 맞춘 방어구·방패는 새로 입을 수 없다. 이미 입은 것(분배 초기화·전직으로 모자라게 된 것)은 그대로 두되 스탯이 없다.
 *       무기는 들 수 있지만 스탯·피해 보너스·무기 스킬이 없다. 아이템을 지우거나 떨구지 않는다.</li>
 * </ul>
 */
public final class EquipRules {

    public enum Problem { NONE, STATS }

    private EquipRules() {}

    /** @param stats 판정 능력치 ({@link StatRequirement#playerStats}) */
    public static Problem check(ItemDef def, Map<Stat, Integer> stats) {
        if (def == null || !def.isGear()) return Problem.NONE;
        return def.requirement().met(stats) ? Problem.NONE : Problem.STATS;
    }

    public static boolean usable(ItemDef def, Map<Stat, Integer> stats) {
        return check(def, stats) == Problem.NONE;
    }

    /** 못 맞춘 조건 문구 "요구 힘 30 (현재 22)" (맞췄거나 요구 없음 = 빈 문자열). */
    public static String problemText(ItemDef def, Map<Stat, Integer> stats) {
        return def == null ? "" : def.requirement().shortfall(stats);
    }
}
