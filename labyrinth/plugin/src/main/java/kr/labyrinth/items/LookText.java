package kr.labyrinth.items;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.core.ArmorLooks;
import kr.labyrinth.core.Text;

/**
 * 방어구 겉모습 글 (look_spec §1.4 · §6, 순수) — 툴팁 · /스탯 · 도감이 같은 문장을 쓴다.
 * <pre>
 *   판금 ▲ 방어 +4% · 받는 피해 −0.5%
 *       ▼ 이동 속도 −2% · 회피 −1%p · 재사용 대기 +2%
 *   판금 4부위 · 버팀: 밀려남 −60% · 기절·속박·빙결 −40% (보스 제외)
 * </pre>
 */
public final class LookText {

    /** ▲ (좋은 쪽) 색 · ▼ (나쁜 쪽) 색. */
    public static final String UP = "#9be89b";
    public static final String DOWN = "#c08a8a";

    private LookText() {}

    /** 숨은 효과 키 이름. */
    public static String keyName(String k) {
        return switch (k) {
            case "defense_pct" -> "방어";
            case "hp_pct" -> "최대 HP";
            case "mana_regen_pct" -> "MP 재생";
            case "cooldown_pct" -> "재사용 대기";
            case "damage_reduction" -> "받는 피해";
            case "move_speed" -> "이동 속도";
            case "evasion" -> "회피";
            case "crit_chance" -> "치명";
            case "attack_speed" -> "공격 속도";
            case "skill_damage" -> "스킬 피해";
            default -> ItemTooltip.statName(k);
        };
    }

    /** 이 값이 입는 사람에게 좋은가 (재사용 대기는 줄어야 좋다). */
    public static boolean good(String k, double v) {
        return "cooldown_pct".equals(k) ? v < 0 : v > 0;
    }

    /** "방어 +4%" · "받는 피해 −0.5%" (받는 피해 감소는 덜 받는 쪽으로) · "회피 −1%p". */
    public static String part(String k, double v) {
        double shown = "damage_reduction".equals(k) ? -v : v;
        return keyName(k) + " " + signedPct(shown) + ("evasion".equals(k) || "crit_chance".equals(k) ? "p" : "");
    }

    /** 부호 붙인 퍼센트 ("+4%" · "−8%"). */
    public static String signedPct(double v) {
        return (v < 0 ? "−" : "+") + Text.pct(Math.abs(v));
    }

    /** 부위 n 개 몫 한 줄 ("방어 +16% · 받는 피해 −2% · 이동 속도 −8% …"). */
    public static String sum(ArmorLooks.Look look, int n) {
        if (look == null) return "";
        List<String> t = new ArrayList<>();
        look.piece().forEach((k, v) -> t.add(part(k, v * n)));
        return String.join(" · ", t);
    }

    /** 4부위 효과 설명 ("밀려남 −60% · 기절·속박·빙결 −40% (보스 제외)"). */
    public static String fullText(ArmorLooks cfg, ArmorLook l) {
        if (l == null) return "";
        return switch (l) {
            case HEAVY -> "밀려남 −" + Text.pct(cfg.steadfast().knockbackResist()) + " · 기절·속박·빙결 −"
                    + Text.pct(cfg.steadfast().ccResist()) + " (보스 제외)";
            case LIGHT -> "웅크리기 두 번 → " + num(cfg.tumble().distance()) + "칸 구르며 피함 (" + num(cfg.tumble().cooldown()) + "초)";
            case CLOTH -> "받는 피해 " + Text.pct(cfg.manaShield().absorb()) + "를 MP로 받음 (MP 1 = 피해 "
                    + num(cfg.manaShield().damagePerMp()) + ")";
            default -> "";
        };
    }

    /**
     * 툴팁 겉모습 줄 (부위 하나 몫): ▲ 좋은 쪽 한 줄 · ▼ 나쁜 쪽 한 줄 · 4부위 줄 (방패는 4부위 대신 안내 한 줄,
     * 악몽의 왕관 any 는 한 줄). 평상복·꺼진 설정·방어구가 아니면 빈 목록.
     */
    public static List<String> tooltip(ArmorLooks cfg, ArmorLook look, boolean shield) {
        List<String> out = new ArrayList<>();
        if (cfg == null || !cfg.enabled() || look == null || look == ArmorLook.PLAIN) return out;
        if (look == ArmorLook.ANY) {
            out.add("<gray>어느 겉모습과도 4부위를 이룬다");
            return out;
        }
        ArmorLooks.Look l = cfg.look(look);
        if (l == null) return out;
        String c = cfg.color(look);
        List<String> up = new ArrayList<>(), down = new ArrayList<>();
        for (Map.Entry<String, Double> e : l.piece().entrySet()) {
            if (e.getValue() == 0) continue;
            (good(e.getKey(), e.getValue()) ? up : down).add(part(e.getKey(), e.getValue()));
        }
        String name = "<" + c + ">" + Text.escape(l.name()) + "</" + c + ">";
        if (!up.isEmpty()) out.add(name + " <" + UP + ">▲</" + UP + "> <gray>" + String.join(" · ", up));
        if (!down.isEmpty()) {
            out.add((up.isEmpty() ? name + " " : "    ") + "<" + DOWN + ">▼</" + DOWN + "> <gray>" + String.join(" · ", down));
        }
        if (shield) {
            out.add("<dark_gray>(방패는 " + Text.escape(l.name()) + " 한 부위 — 4부위 수에는 안 든다)");
        } else {
            out.add("<" + c + ">" + Text.escape(l.name()) + " " + cfg.fullPieces() + "부위 · " + Text.escape(cfg.fullName(look))
                    + ":</" + c + "> <gray>" + fullText(cfg, look));
        }
        return out;
    }

    static String num(double v) {
        return v == Math.rint(v) ? String.valueOf((long) v) : String.format(java.util.Locale.ROOT, "%.1f", v);
    }
}
