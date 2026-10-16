package kr.labyrinth.mine;

import kr.labyrinth.content.ToolSpec;

/**
 * 단단함 규칙 (주인 결정 2, 계약 §2.3): 광석·보석 tier ≤ 곡괭이 tier 일 때만 캔다. 레벨 조건은 어디에도 없다 —
 * 친구가 준 곡괭이를 써도 된다. 못 캐면 금도 안 가고(CAN_BREAK 밖) 액션바 한 줄. 순수.
 */
public final class TierRule {

    private TierRule() {}

    public enum Verdict { OK, NO_PICKAXE, TOO_WEAK }

    /** 손에 든 곡괭이(없으면 null)로 그 등급을 캘 수 있나. */
    public static Verdict check(ToolSpec tool, int nodeTier) {
        if (tool == null || !tool.isPickaxe()) return Verdict.NO_PICKAXE;
        return tool.canMine(nodeTier) ? Verdict.OK : Verdict.TOO_WEAK;
    }

    /** 액션바 글 (OK 면 null). */
    public static String message(Verdict v) {
        return switch (v) {
            case OK -> null;
            case TOO_WEAK -> MineNames.TOO_WEAK;
            case NO_PICKAXE -> MineNames.NEED_PICKAXE;
        };
    }
}
