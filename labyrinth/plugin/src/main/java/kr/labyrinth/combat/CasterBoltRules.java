package kr.labyrinth.combat;

import java.util.List;

/**
 * 시전 무기 마법탄의 순수 규칙 (0.3.6.1, Bukkit 무관 — 단위 테스트 대상). 런타임은 {@code CasterBolts} · {@code AttackClock} · {@code CombatListener}.
 * <ul>
 *   <li><b>좌클릭 감지</b> ({@link #punch}): Paper 26.3 의 좌클릭 패킷(punch)이 부르는 {@code PlayerArmSwingEvent}(주손) 하나로 본다.
 *       같은 틱(또는 바로 다음 틱)에 몹을 직접 클릭했거나·아이템을 버렸거나·우클릭으로 무언가를 썼거나·창을 열었거나·좌클릭한 블록을
 *       다른 기능(미궁 금 간 벽·포자 주머니·퍼즐 블록·상자)이 썼으면 이미 쓴 클릭.
 *       서바이벌·크리에이티브에서 손 닿는 블록을 보고 누르면 블록 캐기라 마법탄이 안 나간다 (어드벤처 미궁에서는 나가고 벽에서 멈춘다).</li>
 *   <li><b>몹 직접 클릭</b> ({@link #entityClick}): 시전 무기로 손 닿는 적을 클릭하면 바닐라 공격은 막고 그 적에게 마법탄을 바로 넣는다
 *       (한 클릭 = 한 발, 같은 시계). 적이 아닌 것(동물·주민·갑옷 거치대·액자·NPC·같은 파티)은 지금처럼 바닐라에 맡긴다.</li>
 *   <li><b>바닐라 근접 피해</b> ({@link #cancelMeleeDamage}): 어떤 길로든 시전 무기의 근접 피해가 적에게 들어오면 취소만 한다 — 피해는 마법탄이 준다
 *       (두 번 맞지 않게).</li>
 *   <li><b>색</b> ({@link #trailColor}): 무기 텍스처 팔레트의 밝은 두 색(4·5번째) 가운데 더 짙은(채도 × 명도) 쪽.</li>
 * </ul>
 */
public final class CasterBoltRules {

    private CasterBoltRules() {}

    /** 좌클릭(팔 휘두름) 하나를 어떻게 볼지. */
    public enum Punch {
        /** 마법탄 (공격 시계가 통과시키면 나간다). */
        BOLT,
        /** 시전 무기가 아니거나 꺼짐. */
        NOT_CASTER,
        /** 이미 쓴 클릭 (몹 직접 클릭·버리기·우클릭·창 열기·다른 기능이 쓴 블록 좌클릭과 같은 틱). */
        CONSUMED,
        /** 지금은 공격할 수 없음 (관전·죽음·기절·창이 열려 있음). */
        BUSY,
        /** 블록 캐기 (서바이벌·크리에이티브에서 손 닿는 블록). */
        DIG
    }

    /**
     * @param caster          시전 무기를 들었고 마법탄이 켜져 있음 (요구 능력치 미달 무기 = 맨손이라 아님)
     * @param consumed        같은 틱에 이미 쓴 클릭 ({@link #consumed(int, int)})
     * @param busy            관전·죽음·기절·창 열림
     * @param canBreakBlocks  서바이벌·크리에이티브 (어드벤처·관전은 false)
     * @param blockInReach    조준선이 손 닿는 거리(블록 상호작용 거리) 안의 블록에 닿음
     */
    public static Punch punch(boolean caster, boolean consumed, boolean busy, boolean canBreakBlocks, boolean blockInReach) {
        if (!caster) return Punch.NOT_CASTER;
        if (consumed) return Punch.CONSUMED;
        if (busy) return Punch.BUSY;
        if (canBreakBlocks && blockInReach) return Punch.DIG;
        return Punch.BOLT;
    }

    /** 몹(엔티티)을 직접 클릭했을 때. */
    public enum EntityClick {
        /** 바닐라 공격을 막고, 공격 시계가 통과시키면 그 적에게 마법탄을 바로 넣는다. */
        BOLT_STRIKE,
        /** 바닐라 그대로 (시전 무기가 아니거나 꺼짐, 또는 적이 아님). 뒤따르는 휘두름은 이미 쓴 클릭. */
        VANILLA
    }

    public static EntityClick entityClick(boolean caster, boolean livingEnemy) {
        return caster && livingEnemy ? EntityClick.BOLT_STRIKE : EntityClick.VANILLA;
    }

    /** 시전 무기(마법탄 켜짐)의 바닐라 근접 피해가 적에게 들어왔다 → 취소만 (피해는 마법탄 한 발). */
    public static boolean cancelMeleeDamage(boolean caster, boolean enemy) { return caster && enemy; }

    /** 같은 틱 또는 바로 다음 틱이면 이미 쓴 클릭 (패킷이 틱 경계에 걸려 나뉘어 와도 한 번으로). */
    public static boolean consumed(int consumedTick, int nowTick) {
        int d = nowTick - consumedTick;
        return d >= 0 && d <= 1;
    }

    /** 마법탄 기본 색 (팔레트가 없을 때) — 옅은 보라. */
    public static final int DEFAULT_COLOR = 0xB98CFF;

    /**
     * 무기 팔레트 (#rrggbb 5색, 어두운 → 밝은) → 마법탄 색. 4·5번째(밝은 쪽) 가운데 채도 × 명도가 큰 쪽 — 지팡이 머리의 빛나는 색.
     * 둘 다 거의 흰색이면 그 가운데 덜 흰 쪽. 팔레트가 짧으면 있는 색 가운데 같은 기준, 없거나 못 읽으면 fallback.
     */
    public static int trailColor(List<String> palette, int fallback) {
        if (palette == null || palette.isEmpty()) return fallback;
        int from = Math.max(0, palette.size() - 2);
        int best = -1;
        double bestScore = -1;
        for (int i = from; i < palette.size(); i++) {
            int rgb = parse(palette.get(i));
            if (rgb < 0) continue;
            double s = vividness(rgb);
            if (s > bestScore) {
                bestScore = s;
                best = rgb;
            }
        }
        if (best < 0) {
            for (String h : palette) {
                int rgb = parse(h);
                if (rgb >= 0 && vividness(rgb) > bestScore) {
                    bestScore = vividness(rgb);
                    best = rgb;
                }
            }
        }
        return best < 0 ? fallback : best;
    }

    /** HSV 채도 × 명도 (0~1). */
    static double vividness(int rgb) {
        double r = (rgb >> 16 & 0xFF) / 255.0, g = (rgb >> 8 & 0xFF) / 255.0, b = (rgb & 0xFF) / 255.0;
        double max = Math.max(r, Math.max(g, b)), min = Math.min(r, Math.min(g, b));
        double sat = max <= 0 ? 0 : (max - min) / max;
        return sat * max;
    }

    /** "#rrggbb" / "rrggbb" → 0xRRGGBB, 못 읽으면 -1. */
    static int parse(String hex) {
        if (hex == null) return -1;
        String h = hex.trim();
        if (h.startsWith("#")) h = h.substring(1);
        if (h.length() != 6) return -1;
        try {
            return Integer.parseInt(h, 16) & 0xFFFFFF;
        } catch (NumberFormatException e) {
            return -1;
        }
    }
}
