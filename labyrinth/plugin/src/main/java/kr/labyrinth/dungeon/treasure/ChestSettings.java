package kr.labyrinth.dungeon.treasure;

import kr.labyrinth.content.Params;

/**
 * floors.yml 층별 {@code chests:} (GDD §5.6, 생략한 키는 기본값).
 * <ul>
 *   <li>dead_end — 미로 막다른 길 끝에 상자를 둘 확률 · minor — 미로 굴 안 작은 막다른 길 확률(나무 위주)</li>
 *   <li>iron / gold — 막다른 길 상자가 철 / 금 상자일 확률 · gold_behind_trap — 앞 복도에 함정이 있는 상자가 금으로 바뀔 확률</li>
 *   <li>mimic — 막다른 길 상자(금 제외)가 미믹일 확률 (깊은 층일수록 높게)</li>
 *   <li>vault — 열쇠 금고(잠긴 문 뒤 금 상자 2~3개)를 둘지 · key_from_elite — 열쇠가 정예 처치에서 나올 확률(나머지는 철 상자 하나에서)</li>
 *   <li>bracket — 루팅 구간 강제 (0 = 층 번호로 자동: 1~3·4~6·7~9·10)</li>
 * </ul>
 */
public record ChestSettings(double deadEnd, double minor, double iron, double gold, double goldBehindTrap, double mimic,
                            boolean vault, double keyFromElite, int bracket) {

    public static final ChestSettings DEFAULT = new ChestSettings(0.85, 0.35, 0.25, 0.05, 0.35, 0.06, true, 0.5, 0);

    public ChestSettings {
        deadEnd = clamp(deadEnd);
        minor = clamp(minor);
        iron = clamp(iron);
        gold = clamp(gold);
        goldBehindTrap = clamp(goldBehindTrap);
        mimic = Math.max(0, Math.min(0.5, mimic));
        keyFromElite = clamp(keyFromElite);
        bracket = Math.max(0, Math.min(4, bracket));
    }

    private static double clamp(double v) { return Math.max(0, Math.min(1, v)); }

    public static ChestSettings of(Params p) {
        if (p == null || p.isEmpty()) return DEFAULT;
        ChestSettings d = DEFAULT;
        return new ChestSettings(p.dbl("dead_end", d.deadEnd), p.dbl("minor", d.minor), p.dbl("iron", d.iron), p.dbl("gold", d.gold),
                p.dbl("gold_behind_trap", d.goldBehindTrap), p.dbl("mimic", d.mimic), p.bool("vault", d.vault),
                p.dbl("key_from_elite", d.keyFromElite), p.integer("bracket", d.bracket));
    }
}
