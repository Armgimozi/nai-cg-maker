package kr.labyrinth.items.unique;

import kr.labyrinth.content.UniqueCatalog;
import kr.labyrinth.content.UniqueDef;
import kr.labyrinth.core.Text;

/**
 * 무기 고유 효과 툴팁 글 (unique_spec §6, 순수). 무기마다 수치가 달라 items.yml 에 글을 적지 않고 수치에서 만든다
 * (설계 도구 ud_assign.desc/short 와 같은 문장).
 * <pre>
 *   ✧ 고유 아물지 않는 상처 (재발동 1초)       ← head: 재발동 1초 이상만
 *     치명타 시 출혈 (중첩당 초당 공격력 15%, 최대 5)   ← desc: 34자 이하
 *   ✧ 아물지 않는 상처 치명타 → 출혈 15%       ← folded: 줄이 모자랄 때 한 줄
 * </pre>
 * '공격력 X%' = 한 방 기준 · '스킬 위력 X%' = 처치·스킬 뒤·지속 피해 세기 (combat_spec §3.5).
 */
public final class UniqueText {

    /** 머리 줄 색. */
    public static final String COLOR = "#9fe3ff";
    /** 설명 한 줄 최대 글자 수 (unique_spec §6). */
    public static final int MAX_DESC = 34;

    private UniqueText() {}

    /** "&lt;#9fe3ff&gt;✧ 고유&lt;/#9fe3ff&gt; &lt;white&gt;이름&lt;/white&gt; &lt;dark_gray&gt;(재발동 1초)" — 재발동 1초 미만은 적지 않는다. */
    public static String head(UniqueDef u) {
        UniqueCatalog.Effect e = u.effect();
        double icd = e == null ? 0 : e.icd();
        return "<" + COLOR + ">✧ 고유</" + COLOR + "> <white>" + Text.escape(u.name()) + "</white>"
                + (icd >= 1 ? " <dark_gray>(재발동 " + num(icd) + "초)" : "");
    }

    /** 설명 줄 (들여 쓰고 회색). */
    public static String descLine(UniqueDef u) { return "  <gray>" + Text.escape(desc(u)); }

    /** 접은 한 줄 "✧ 이름 짧은 설명". */
    public static String folded(UniqueDef u) {
        return "<" + COLOR + ">✧</" + COLOR + "> <white>" + Text.escape(u.name()) + "</white> <gray>" + Text.escape(shortText(u));
    }

    /** 설명 (태그 없음). */
    public static String desc(UniqueDef u) {
        return switch (u.id()) {
            case "rend" -> "치명타 시 출혈 (중첩당 초당 공격력 " + pc(u, "pct") + ", 최대 " + u.count("max_stacks") + ")";
            case "hemorrhage" -> "출혈 중인 적에게 치명 확률 +" + pc(u, "cc") + ", 치명 피해 +" + pc(u, "cd");
            case "leech" -> "기본 공격 피해의 " + pc(u, "pct") + " 회복 (초당 최대 HP " + pc(u, "cap") + "까지)";
            case "feast" -> "처치 시 최대 HP " + pc(u, "heal") + " 회복, " + sec(u, "duration") + "간 흡혈 +" + pc(u, "ls");
            case "thorns" -> "맞으면 줄기 전 피해의 " + pc(u, "pct") + "를 되돌린다 (근접만)";
            case "bash_stun" -> u.count("n") + "번째 공격마다 기절 " + sec(u, "stun") + " + 공격력 " + pc(u, "pct");
            case "steadfast" -> "HP " + pc(u, "thr") + " 이상이면 받는 피해 -" + pc(u, "dr") + ", 밀려나지 않음";
            case "cleave" -> "기본 공격이 주변 " + num(u.num("radius")) + "칸 적 " + u.count("targets") + "명에게 공격력 " + pc(u, "pct");
            case "chain_spark" -> pc(u, "chance") + " 확률로 번개가 " + u.count("targets") + "명에게 튐 (공격력 " + pc(u, "pct") + ")";
            case "death_burst" -> "처치한 적이 터져 " + num(u.num("radius")) + "칸 안 적에게 스킬 위력 " + pc(u, "pct");
            case "execute" -> "HP " + pc(u, "thr") + " 이하 적에게 피해 +" + pc(u, "pct") + " (보스는 60%만)";
            case "bloodrush" -> "처치하면 다음 공격 피해 +" + pc(u, "pct") + ", " + sec(u, "duration") + "간 이동 +" + pc(u, "ms");
            case "momentum" -> "적중마다 공격 속도 +" + pc(u, "as") + " (" + u.count("max_stacks") + "중첩), " + sec(u, "decay") + " 쉬면 사라짐";
            case "flurry" -> u.count("n") + "번째 공격마다 공격력 " + pc(u, "pct") + "의 추가 타격";
            case "counterstep" -> "회피하면 " + sec(u, "window") + " 안 다음 공격 치명타 확정, 피해 +" + pc(u, "pct");
            case "siphon" -> "처치 시 MP " + pc(u, "mp") + " 회복, 무기 스킬 대기 -" + sec(u, "cdr");
            case "overcharge" -> "스킬을 쓰면 다음 기본 공격이 스킬 위력 " + pc(u, "pct") + " 폭발";
            case "sanctify" -> "적중 시 " + num(u.num("radius")) + "칸 안 가장 다친 아군을 공격력 " + pc(u, "pct") + " 치유";
            case "ward_aura" -> sec(u, "period") + "마다 " + num(u.num("radius")) + "칸 아군에게 최대 HP " + pc(u, "pct") + " 보호막";
            case "imbue" -> switch (u.text("element", "burn")) {
                case "poison" -> pc(u, "chance") + " 확률로 독 중첩 (초당 스킬 위력 " + pc(u, "pct") + ", 최대 5)";
                case "frost" -> pc(u, "chance") + " 확률로 서리 1중첩, 5중첩이면 빙결 1초";
                default -> pc(u, "chance") + " 확률로 " + sec(u, "duration") + " 불태움 (초당 스킬 위력 " + pc(u, "pct") + ")";
            };
            case "exploit" -> "상태이상 걸린 적에게 피해 +" + pc(u, "pct") + " (2개면 1.6배)";
            case "first_strike" -> "처음 때리는 적에게 피해 +" + pc(u, "pct") + ", 치명 확률 +" + pc(u, "cc");
            case "backstab" -> "적의 등 뒤에서 때리면 피해 +" + pc(u, "pct");
            case "longshot" -> num(u.num("dist")) + "칸 밖 적에게 피해 +" + pc(u, "pct") + ", 화살·탄이 " + u.count("pierce") + "명 더 꿰뚫음";
            case "berserk" -> "잃은 HP 10%마다 피해 +" + pc(u, "pct") + ", 빈사 흡혈 +" + pc(u, "ls");
            case "armor_break" -> "적중마다 대상 방어 -" + pc(u, "pct") + " (" + u.count("max_stacks") + "중첩, " + sec(u, "duration") + ")";
            default -> {
                UniqueCatalog.Effect e = u.effect();
                yield e == null ? u.id() : e.name();
            }
        };
    }

    /** 짧은 설명 (접은 줄). */
    public static String shortText(UniqueDef u) {
        return switch (u.id()) {
            case "rend" -> "치명타 → 출혈 " + pc(u, "pct");
            case "hemorrhage" -> "출혈 적에게 치명 +" + pc(u, "cc");
            case "leech" -> "적중 회복 " + pc(u, "pct");
            case "feast" -> "처치 → HP " + pc(u, "heal");
            case "thorns" -> "반사 " + pc(u, "pct");
            case "bash_stun" -> u.count("n") + "타 기절 " + sec(u, "stun");
            case "steadfast" -> "HP 높으면 피해 -" + pc(u, "dr");
            case "cleave" -> "주변 " + u.count("targets") + "명 " + pc(u, "pct");
            case "chain_spark" -> "번개 " + u.count("targets") + "명 " + pc(u, "pct");
            case "death_burst" -> "처치 폭발 위력 " + pc(u, "pct");
            case "execute" -> "빈사 적 +" + pc(u, "pct");
            case "bloodrush" -> "처치 → 다음 +" + pc(u, "pct");
            case "momentum" -> "적중 공속 +" + pc(u, "as") + "×" + u.count("max_stacks");
            case "flurry" -> u.count("n") + "타 추가 " + pc(u, "pct");
            case "counterstep" -> "회피 → 확정 치명";
            case "siphon" -> "처치 → MP " + pc(u, "mp");
            case "overcharge" -> "스킬 후 폭발 위력 " + pc(u, "pct");
            case "sanctify" -> "적중 → 아군 치유";
            case "ward_aura" -> "보호막 " + pc(u, "pct") + "/" + sec(u, "period");
            case "imbue" -> switch (u.text("element", "burn")) {
                case "poison" -> "적중 → 독 중첩";
                case "frost" -> "적중 → 서리";
                default -> "적중 → 불태움";
            };
            case "exploit" -> "상태이상 적 +" + pc(u, "pct");
            case "first_strike" -> "첫 타 +" + pc(u, "pct");
            case "backstab" -> "등 뒤 +" + pc(u, "pct");
            case "longshot" -> "원거리 +" + pc(u, "pct");
            case "berserk" -> "다칠수록 +" + pc(u, "pct") + "/10%";
            case "armor_break" -> "방어 -" + pc(u, "pct") + "×" + u.count("max_stacks");
            default -> "";
        };
    }

    private static String pc(UniqueDef u, String key) { return Text.pct(u.num(key)); }

    private static String sec(UniqueDef u, String key) { return num(u.num(key)) + "초"; }

    /** 1.0 → "1", 2.5 → "2.5", 0.25 → "0.25". */
    static String num(double v) {
        if (Math.abs(v - Math.rint(v)) < 1e-9) return String.valueOf((long) Math.rint(v));
        String s = String.format(java.util.Locale.ROOT, "%.2f", v);
        return s.replaceAll("0+$", "").replaceAll("\\.$", "");
    }
}
