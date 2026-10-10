package kr.souls.ui;

import kr.souls.progression.Derived;
import kr.souls.progression.StatBlock;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 능력치 창과 레벨 올리기 창의 값 표 (5.9): 여섯 줄, 줄마다 한 능력치의 두 효과 (사용자가 정한 둘씩). 차례는 능력치 차례와 같고, 줄 맨
 * 앞에 그 능력치의 한 글자 (체·정·기·근·민·지, 영어 VIG MND END STR DEX INT, 흐린 금: 검토 levelup-row-mapping).
 * <pre>
 *   체  최대 HP        방어력
 *   정  최대 마나      마법 저항
 *   기  최대 스태미나  스태미나 회복 (초당)
 *   근  공격력         무게 한도 ("장비 무게 / 한도")
 *   민  이동 속도      공격 속도
 *   지  술법 세기      상태 이상 저항
 * </pre>
 * next 가 있으면 (레벨 올리기 미리보기) 바뀐 값만 "a → b" (무게 한도는 폭이 모자라 새 한도만 바랜 금으로). 아직 듣지 않는 값 (술법이
 * 생기는 M5 전의 최대 마나·술법 세기) 은 흐린 갈색 (검토 stat-values-without-effect).
 */
public final class StatRows {
    private StatRows() {}

    /** 줄 i 의 두 열쇠 (derived.*). 공격력은 양손이면 derived.attack-2h. */
    static String[] keys(int i, Derived d) {
        return switch (i) {
            case 0 -> new String[] {"derived.max-hp", "derived.defense"};
            case 1 -> new String[] {"derived.max-mana", "derived.magic-res"};
            case 2 -> new String[] {"derived.max-stamina", "derived.regen"};
            case 3 -> new String[] {d.twoHanded() ? "derived.attack-2h" : "derived.attack", "derived.load-cap"};
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

    /** 능력치 id 의 줄 번호. */
    public static int rowOf(String stat) {
        return Math.max(0, StatBlock.IDS.indexOf(stat));
    }

    /** 줄 i 의 값 j 가 아직 듣지 않나 (술법 M5 전: 정신의 최대 마나, 지능의 술법 세기). */
    public static boolean later(int i, int j) {
        return j == 0 && (i == 1 || i == 5);
    }

    /** 표 여섯 줄. */
    public static List<Component> rows(Player p, Derived now, Derived next) {
        List<Component> out = new ArrayList<>();
        for (int i = 0; i < 6; i++) {
            String[] k = keys(i, next != null ? next : now);
            String[] a = values(i, now);
            String[] b = next == null ? a : values(i, next);
            Component v0 = !later(i, 0) ? Columns.change(a[0], b[0], Columns.VALUE)
                    : a[0].equals(b[0]) ? Columns.right(a[0], Columns.VALUE, Columns.DIM_COLOR)
                    : Columns.rightParts(Columns.VALUE, new String[] {a[0] + " → " + b[0]}, new net.kyori.adventure.text.format.TextColor[] {Columns.DIM_COLOR});
            Component v1 = i == 3 ? load(now, next) : Columns.change(a[1], b[1], Columns.VALUE);
            out.add(Columns.row(p, "stat." + StatBlock.IDS.get(i) + ".tag", k[0], v0, k[1], v1));
        }
        return out;
    }

    /** 근력 줄의 무게 칸: "21.0 / 38.9" (장비 무게 / 한도). 한도가 바뀌면 새 한도만 바랜 금. */
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
