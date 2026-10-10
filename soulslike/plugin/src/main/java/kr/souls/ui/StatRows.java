package kr.souls.ui;

import kr.souls.progression.Derived;
import kr.souls.progression.StatBlock;
import net.kyori.adventure.text.Component;

import java.util.Locale;

/**
 * 능력치 하나의 두 효과 (5.2, 사용자가 정한 둘씩): 레벨 올리기 창의 "+" 단추 설명 칸이 한 점 더했을 때의 값을 보인다 (LevelUpDialog.tip).
 * 창 본문의 표는 StatSheet (왼쪽 능력치 여섯, 오른쪽 나온 값) 다. 예전에는 이 짝으로 본문 표를 짜고 줄 맨 앞에 능력치 한 글자
 * (체·정·기 …) 를 붙였으나, 방어력·마법 저항은 레벨로도 올라 짝이 맞지 않았고 한 글자 열이 이상하게 읽혀 없앴다 (DECISIONS 2026-10-10).
 * <pre>
 *   생명력  최대 HP        방어력
 *   정신력  최대 마나      마법 저항
 *   지구력  최대 스태미나  스태미나 회복 (초당)
 *   근력    공격력         장비 중량 ("장비 무게 / 한도": 한 점은 한도를 올린다)
 *   민첩    이동 속도      공격 속도
 *   지력    술법 세기      상태 이상 저항
 * </pre>
 * 아직 듣지 않는 값 (술법이 생기는 M5 전의 최대 마나·술법 세기) 은 흐린 갈색 (검토 stat-values-without-effect).
 */
public final class StatRows {
    private StatRows() {}

    /** 줄 i 의 두 열쇠 (derived.*). 공격력은 양손이면 derived.attack-2h. */
    static String[] keys(int i, Derived d) {
        return switch (i) {
            case 0 -> new String[] {"derived.max-hp", "derived.defense"};
            case 1 -> new String[] {"derived.max-mana", "derived.magic-res"};
            case 2 -> new String[] {"derived.max-stamina", "derived.regen"};
            case 3 -> new String[] {d.twoHanded() ? "derived.attack-2h" : "derived.attack", "derived.load"};
            case 4 -> new String[] {"derived.move", "derived.attack-speed"};
            default -> new String[] {"derived.spell", "derived.ailment"};
        };
    }

    /** 줄 i 의 두 값 (글). */
    static String[] values(int i, Derived d) {
        return switch (i) {
            case 0 -> new String[] {f0(d.maxHp()), f0(d.defense())};
            case 1 -> new String[] {f0(d.maxMana()), f0(d.magicRes())};
            case 2 -> new String[] {f0(d.maxStamina()), String.format(Locale.ROOT, "%.1f", d.regenPerSec())};
            case 3 -> new String[] {d.attack() <= 0 ? "–" : f0(d.attack()), String.format(Locale.ROOT, "%.1f", d.cap())};
            case 4 -> new String[] {pct(d.move()), pct(d.attackSpeed() - 1)};
            default -> new String[] {d.spellPower() <= 0 ? "–" : f0(d.spellPower()), String.format(Locale.ROOT, "%.0f%%", d.ailment() * 100)};
        };
    }

    /**
     * 줄 i 의 두 값을 한 자리 더 (레벨 올리기 "+" 단추의 설명 칸만): 정수로 보이는 값은 소수 한 자리, 퍼센트는 늘 소수 한 자리. 무른 상한
     * 위에서 한 점이 반올림한 값을 바꾸지 못할 때 ("공격력 95 → 95" 가 되어 능력치가 죽은 듯 읽힌다, 검토 softcap-dead-points)
     * LevelUpDialog 가 이것으로 "95.3 → 95.6" 을 보인다.
     */
    static String[] fine(int i, Derived d) {
        return switch (i) {
            case 0 -> new String[] {f1(d.maxHp()), f1(d.defense())};
            case 1 -> new String[] {f1(d.maxMana()), f1(d.magicRes())};
            case 2 -> new String[] {f1(d.maxStamina()), String.format(Locale.ROOT, "%.2f", d.regenPerSec())};
            case 3 -> new String[] {d.attack() <= 0 ? "–" : f1(d.attack()), f1(d.cap())};
            case 4 -> new String[] {pct1(d.move()), pct1(d.attackSpeed() - 1)};
            default -> new String[] {d.spellPower() <= 0 ? "–" : f1(d.spellPower()), String.format(Locale.ROOT, "%.1f%%", d.ailment() * 100)};
        };
    }

    /** 몫 → 소수 한 자리 퍼센트 ("+22.4%", 0 은 "0%"). */
    static String pct1(double v) {
        double a = Math.abs(v);
        if (a < 0.0005) return "0%";
        return String.format(Locale.ROOT, "%s%.1f%%", v < 0 ? "-" : "+", a * 100);
    }

    /** 능력치 id 의 줄 번호. */
    public static int rowOf(String stat) {
        return Math.max(0, StatBlock.IDS.indexOf(stat));
    }

    /** 줄 i 의 값 j 가 아직 듣지 않나 (술법 M5 전: 정신의 최대 마나, 지력의 술법 세기). */
    public static boolean later(int i, int j) {
        return j == 0 && (i == 1 || i == 5);
    }

    /** 장비 중량 칸: "21.0 / 38.9" (장비 무게 / 한도, 값 열 끝에 오른쪽 맞춤). 한도가 바뀌면 새 한도만 바랜 금. */
    static Component load(Derived now, Derived next) {
        String w = f1(now.weight()), cap = f1(now.cap());
        String to = next == null ? cap : f1(next.cap());
        return Columns.rightParts(Columns.VALUE, new String[] {w + " / ", to},
                new net.kyori.adventure.text.format.TextColor[] {Columns.VALUE_COLOR, to.equals(cap) ? Columns.VALUE_COLOR : Columns.NEXT_COLOR});
    }

    static String f1(double v) {
        return String.format(Locale.ROOT, "%.1f", v);
    }

    static String f0(double v) {
        return String.format(Locale.ROOT, "%.0f", v);
    }

    /**
     * 몫 → 부호가 붙은 퍼센트: 10% 밑은 소수 한 자리 ("+0.5%", "−15%" 는 "-15%"), 10% 넘으면 정수 ("+12%"), 0 은 "0%". 한 점마다 무엇이든
     * 보이게 1% 밑도 숨기지 않는다 (검토 slow-stats-feel-dead).
     */
    public static String pct(double v) {
        double a = Math.abs(v);
        if (a < 0.0005) return "0%";
        String sign = v < 0 ? "-" : "+";
        if (a >= 0.0995) return String.format(Locale.ROOT, "%s%.0f%%", sign, a * 100);
        return String.format(Locale.ROOT, "%s%.1f%%", sign, a * 100);
    }
}
