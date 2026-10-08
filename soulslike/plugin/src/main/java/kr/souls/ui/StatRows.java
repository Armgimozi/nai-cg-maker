package kr.souls.ui;

import kr.souls.progression.Derived;
import kr.souls.progression.StatBlock;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 능력치 창과 레벨 올리기 창의 값 표 (5.9): 여섯 줄, 줄마다 한 능력치의 두 효과 (사용자가 정한 둘씩). 차례는 능력치 차례와 같다.
 * <pre>
 *   체력  최대 HP        방어력
 *   정신  최대 마나      마법 저항
 *   기력  최대 스태미나  스태미나 회복 (초당)
 *   근력  공격력         무게 한도
 *   민첩  이동 속도      공격 속도
 *   지능  술 세기        상태 이상 저항
 * </pre>
 * next 가 있으면 (레벨 올리기 미리보기) 바뀐 값만 "a → b".
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

    /** 표 여섯 줄. */
    public static List<Component> rows(Player p, Derived now, Derived next) {
        List<Component> out = new ArrayList<>();
        for (int i = 0; i < 6; i++) {
            String[] k = keys(i, next != null ? next : now);
            String[] a = values(i, now);
            String[] b = next == null ? a : values(i, next);
            out.add(Columns.row(p, k[0], Columns.change(a[0], b[0], Columns.VALUE), k[1], Columns.change(a[1], b[1], Columns.VALUE)));
        }
        return out;
    }

    static String f0(double v) {
        return String.format(Locale.ROOT, "%.0f", v);
    }

    /** 몫 → "+3.0%" (10% 넘으면 "+12%"). 1% 밑은 "0%" (검토 dex-too-weak: 0.3% 같은 값을 보이지 않는다). */
    static String pct(double v) {
        if (v < 0.00995) return "0%";
        if (v >= 0.0995) return String.format(Locale.ROOT, "+%.0f%%", v * 100);
        return String.format(Locale.ROOT, "+%.1f%%", v * 100);
    }
}
