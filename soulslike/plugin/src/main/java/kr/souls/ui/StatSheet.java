package kr.souls.ui;

import kr.souls.Lang;
import kr.souls.progression.Derived;
import kr.souls.progression.StatBlock;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * 능력치 표 (5.9, 5.10, DECISIONS 2026-10-10): 다크 소울 상태 창처럼 왼쪽 열에 머리 (레벨·보유 소울·필요 소울, 능력치 창은 출신도) 와
 * 능력치 여섯의 세로 목록 (이름 왼쪽, 값 오른쪽, 더할 점이 있으면 "10 → 13"), 오른쪽 열에 그 능력치에서 나온 값 (최대 HP … 상태 이상 저항).
 * 예전 표의 한 글자 열 (체·정·기 …) 과 "체력 10 · 정신 10 · …" 줄은 없앴다 (사용자: 한 글자씩 세로로 붙은 게 이상하다).
 * <pre>
 *   레벨          1 → 4      최대 HP          400 → 454
 *   보유 소울    25,000      최대 마나               60
 *   필요 소울       380      최대 스태미나          100
 *                            스태미나 회복         44.0
 *   생명력      10 → 12      장비 중량       4.5 / 40.0
 *   정신력           10      이동 속도               0%
 *   지구력           10      공격력            68 → 72
 *   근력        10 → 11      공격 속도               0%
 *   민첩             10      술법 세기                –
 *   지력             10      방어력            36 → 38
 *                            마법 저항         32 → 34
 *                            상태 이상 저항          0%
 * </pre>
 * 줄 맞추기 (Columns 와 같은 길): 바닐라 plain_message 는 줄마다 가운데에 놓으므로 모든 줄의 폭이 같아야 열이 선다. 이름 칸은 팩이 그
 * 언어의 무리 (왼쪽 table.*·stat.*.name, 오른쪽 derived.*) 에서 가장 긴 이름 폭까지 채운 칸 (Lang.cell), 값은 열 끝에 오른쪽 맞춤한 고정 폭
 * (왼쪽 LEFT_VALUE, 오른쪽 Columns.VALUE), 빈 칸은 글이 없는 칸 열쇠 (table.blank, derived.blank) 와 값 폭만큼의 빈칸. 줄 폭 =
 * 왼쪽 이름 칸 + LEFT_VALUE + GAP + 오른쪽 이름 칸 + VALUE (팩의 pack/typeset.py ROWS 가 본문에 서는 폭 WIDTH − 16 을 넘지 않는지 본다).
 */
public final class StatSheet {
    /** 본문 폭 (plain_message). 글이 서는 폭은 이것 − 16 (FocusableTextWidget 의 안쪽 여백) */
    public static final int WIDTH = 320;
    /** 왼쪽 열의 값 폭 (보유 소울 "999,999 → 997,940" 82 가 든다. 넘으면 바뀐 값만) */
    public static final int LEFT_VALUE = 84;
    /** 두 열 사이 (왼쪽 값 열 끝과 오른쪽 이름 칸 사이) */
    public static final int GAP = 24;
    /** 이름 칸 글자색 (두 열 모두. 값은 Columns.VALUE_COLOR) */
    public static final TextColor LABEL_COLOR = TextColor.color(0x858079);
    static final String BLANK_LEFT = "table.blank";
    static final String BLANK_RIGHT = "derived.blank";

    private StatSheet() {}

    /** 한 칸: 이름 칸 열쇠 (팩이 채운 칸) 와 이미 열 끝에 맞춘 값 (null 이면 빈칸). */
    public record Cell(String key, Component value) {
        static Cell blank(String key) {
            return new Cell(key, null);
        }
    }

    /** 왼쪽 열과 오른쪽 열을 줄로 (짧은 쪽은 빈 칸). */
    public static List<Component> lines(Player p, List<Cell> left, List<Cell> right) {
        int n = Math.max(left.size(), right.size());
        List<Component> out = new ArrayList<>(n);
        for (int i = 0; i < n; i++) {
            Cell l = i < left.size() ? left.get(i) : Cell.blank(BLANK_LEFT);
            Cell r = i < right.size() ? right.get(i) : Cell.blank(BLANK_RIGHT);
            TextComponent.Builder b = Component.text();
            b.append(label(p, l.key())).append(l.value() != null ? l.value() : Columns.pad(LEFT_VALUE));
            b.append(Columns.pad(GAP));
            b.append(label(p, r.key())).append(r.value() != null ? r.value() : Columns.pad(Columns.VALUE));
            out.add(b.build().decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE));
        }
        return out;
    }

    /** 이름 칸 (팩이 채운 칸 열쇠, 글자색은 LABEL_COLOR: 능력치 이름의 열쇠 꼴은 단추 색이라 덮는다). */
    static Component label(Player p, String key) {
        return Lang.cell(p, key).color(LABEL_COLOR); // lang-dyn: table.*, stat.*.name, derived.*
    }

    /**
     * 왼쪽 열만 (휴식 창 본문: 레벨·보유 소울·필요 소울, 레벨 올리기 창의 머리와 같은 칸). 줄 폭은 모두 왼쪽 이름 칸 + LEFT_VALUE 라
     * 가운데 맞춤에서도 열이 선다. 예전의 "소울 30,000 · 레벨 8 · 다음 460" 가운뎃점 줄을 바꿨다 (DECISIONS 2026-10-10).
     */
    public static List<Component> leftLines(Player p, List<Cell> left) {
        List<Component> out = new ArrayList<>(left.size());
        for (Cell l : left) {
            out.add(Component.text().append(label(p, l.key())).append(l.value() != null ? l.value() : Columns.pad(LEFT_VALUE)).build()
                    .decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE));
        }
        return out;
    }

    /** 휴식 창 본문의 세 칸: 레벨, 보유 소울, 필요 소울 (다음 한 레벨의 비용). */
    public static List<Cell> restHead(String level, String held, String need) {
        return List.of(head("table.level", level), head("table.held", held), head("table.need", need));
    }

    // ------------------------------------------------------------------ 왼쪽 열

    /** 능력치 여섯 (차례 StatBlock.IDS). target 이 base 와 다르면 "10 → 13". main 은 굵게 (출신 확인 창의 주 능력치). */
    public static List<Cell> stats(StatBlock base, StatBlock target, Set<String> main) {
        List<Cell> out = new ArrayList<>(6);
        for (String id : StatBlock.IDS) {
            String a = String.valueOf(base.get(id)), b = String.valueOf(target.get(id));
            Component v = main.contains(id) ? Columns.right(a, LEFT_VALUE, Columns.MAIN_COLOR, true) : Columns.change(a, b, LEFT_VALUE);
            out.add(new Cell("stat." + id + ".name", v));
        }
        return out;
    }

    /** 왼쪽 열의 머리 한 칸: 값 하나 (오른쪽 맞춤). */
    public static Cell head(String key, String value) {
        return new Cell(key, Columns.right(value, LEFT_VALUE, Columns.VALUE_COLOR));
    }

    /** 왼쪽 열의 머리 한 칸: 바뀌는 값 ("1 → 4", 폭이 모자라면 바뀐 값만 바랜 금으로). */
    public static Cell head(String key, String now, String next) {
        if (next == null || next.equals(now)) return head(key, now);
        String full = now + " → " + next;
        int w = Columns.width(full);
        if (w > LEFT_VALUE) return new Cell(key, Columns.right(next, LEFT_VALUE, Columns.NEXT_COLOR));
        return new Cell(key, Columns.change(now, next, LEFT_VALUE));
    }

    public static Cell blankLeft() {
        return Cell.blank(BLANK_LEFT);
    }

    // ------------------------------------------------------------------ 오른쪽 열

    /**
     * 오른쪽 열 (레벨 올리기 창과 능력치 창이 같다): 몸 (최대 HP·마나·스태미나, 스태미나 회복, 장비 중량, 이동 속도), 공격 (공격력, 공격
     * 속도, 술법 세기), 막기 (방어력, 마법 저항, 상태 이상 저항). next 가 있으면 바뀐 값만 "a → b" (장비 중량은 새 한도만 바랜 금).
     * 아직 듣지 않는 값 (술법이 생기는 M5 전의 최대 마나·술법 세기) 은 흐린 갈색. tierRow 면 장비 중량 밑에 무게 단계 (이름 없는 칸,
     * 능력치 창: 레벨 올리기 창은 근력 단추의 설명 칸이 단계가 바뀌는 것을 보인다).
     */
    public static List<Cell> derived(Player p, Derived now, Derived next, boolean tierRow) {
        Derived n = next == null ? now : next;
        List<Cell> out = new ArrayList<>(13);
        out.add(new Cell("derived.max-hp", Columns.change(f0(now.maxHp()), f0(n.maxHp()), Columns.VALUE)));
        out.add(new Cell("derived.max-mana", later(f0(now.maxMana()), f0(n.maxMana()))));
        out.add(new Cell("derived.max-stamina", Columns.change(f0(now.maxStamina()), f0(n.maxStamina()), Columns.VALUE)));
        out.add(new Cell("derived.regen", Columns.change(f1(now.regenPerSec()), f1(n.regenPerSec()), Columns.VALUE)));
        out.add(new Cell("derived.load", StatRows.load(now, next)));
        if (tierRow) out.add(new Cell(BLANK_RIGHT, Lang.rcell(p, "load." + now.tier().id()))); // lang-dyn: load.*
        out.add(new Cell("derived.move", Columns.change(StatRows.pct(now.move()), StatRows.pct(n.move()), Columns.VALUE)));
        out.add(new Cell(n.twoHanded() ? "derived.attack-2h" : "derived.attack",
                Columns.change(attack(now.attack()), attack(n.attack()), Columns.VALUE)));
        out.add(new Cell("derived.attack-speed", Columns.change(StatRows.pct(now.attackSpeed() - 1), StatRows.pct(n.attackSpeed() - 1),
                Columns.VALUE)));
        out.add(new Cell("derived.spell", later(attack(now.spellPower()), attack(n.spellPower()))));
        out.add(new Cell("derived.defense", Columns.change(f0(now.defense()), f0(n.defense()), Columns.VALUE)));
        out.add(new Cell("derived.magic-res", Columns.change(f0(now.magicRes()), f0(n.magicRes()), Columns.VALUE)));
        out.add(new Cell("derived.ailment", Columns.change(ailment(now.ailment()), ailment(n.ailment()), Columns.VALUE)));
        return out;
    }

    /**
     * 출신 확인 창의 오른쪽 열 (5.10): 그 출신으로 시작할 때의 최대 HP·마나·스태미나, 장비 중량 (시작 장비 / 한도), 주무기 공격력 (양손이면
     * "공격력 (양손)", 근접 주무기가 없으면 "–"), 방어력. 왼쪽 능력치 여섯과 같은 여섯 줄 (1280×720 GUI 3 에서 창이 넘치지 않게).
     */
    public static List<Cell> origin(Derived d) {
        List<Cell> out = new ArrayList<>(6);
        out.add(new Cell("derived.max-hp", Columns.right(f0(d.maxHp()), Columns.VALUE, Columns.VALUE_COLOR)));
        out.add(new Cell("derived.max-mana", later(f0(d.maxMana()), f0(d.maxMana()))));
        out.add(new Cell("derived.max-stamina", Columns.right(f0(d.maxStamina()), Columns.VALUE, Columns.VALUE_COLOR)));
        out.add(new Cell("derived.load", StatRows.load(d, null)));
        out.add(new Cell(d.twoHanded() ? "derived.attack-2h" : "derived.attack", Columns.right(attack(d.attack()), Columns.VALUE,
                Columns.VALUE_COLOR)));
        out.add(new Cell("derived.defense", Columns.right(f0(d.defense()), Columns.VALUE, Columns.VALUE_COLOR)));
        return out;
    }

    /** 아직 듣지 않는 값: 흐린 갈색 (바뀌어도 화살표째 흐리게). */
    static Component later(String now, String next) {
        if (now.equals(next)) return Columns.right(now, Columns.VALUE, Columns.DIM_COLOR);
        return Columns.rightParts(Columns.VALUE, new String[] {now + " → " + next}, new TextColor[] {Columns.DIM_COLOR});
    }

    static String attack(double v) {
        return v <= 0 ? "–" : f0(v);
    }

    static String ailment(double v) {
        return String.format(Locale.ROOT, "%.0f%%", v * 100);
    }

    static String f0(double v) {
        return String.format(Locale.ROOT, "%.0f", v);
    }

    static String f1(double v) {
        return String.format(Locale.ROOT, "%.1f", v);
    }
}
