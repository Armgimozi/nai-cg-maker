package kr.souls.ui;

import io.papermc.paper.dialog.Dialog;
import io.papermc.paper.registry.data.dialog.ActionButton;
import io.papermc.paper.registry.data.dialog.DialogBase;
import io.papermc.paper.registry.data.dialog.body.DialogBody;
import io.papermc.paper.registry.data.dialog.type.DialogType;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.combat.Parry;
import kr.souls.hud.Glyphs;
import kr.souls.item.Weapons;
import kr.souls.progression.Derived;
import kr.souls.progression.Origins;
import kr.souls.progression.StatBlock;
import kr.souls.progression.Stats;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

import java.util.ArrayList;
import java.util.List;

/**
 * "출신 선택" 창 (5.10): 머리줄 하나와 출신마다 단추 하나 (폭 370). 단추 글은 [이름 칸][레벨][능력치 여섯][시작 아이템 칸] 을
 * 열 맞추기로 짜서 (Columns, 팩의 칸) 모든 줄의 폭이 같고, 그래서 가운데 맞춤인 단추 글과 머리줄의 열이 위아래로 선다. 단추의 설명 칸은
 * 그 출신이 무엇을 들었는지 한 줄 (origin.*.desc).
 * 단추를 누르면 확인 창: 한 글 (어떻게 싸우는지 한 줄 origin.*.style, 빈 줄, 능력치 표 StatSheet: 왼쪽 능력치 여섯, 오른쪽 최대 HP·마나·
 * 스태미나·장비 중량·공격력·방어력, 조작 한 줄: 키 묶음 글이라 그 사람이 바꾼 키 이름) 과 시작 아이템 그림 (가리키면 설명 칸). 설명 한 줄
 * (desc) 은 확인 창에 다시 쓰지 않는다: 제목이 출신 이름이고 desc 는 출신 창의 설명 칸에 있다 (검토 origin-confirm-crowded).
 * "이 출신으로 시작" / "뒤로".
 * 높이: 제목 + 머리줄 + 단추 여섯 + 나가기 ≈ 228 GUI 픽셀이라 1280×720 GUI 3 (240) 에서도 굴리지 않는다 (검토 T4·dialog-height).
 * 확인 창도 시작 아이템이 셋인 도적·궁수까지 1280×720 GUI 3 의 본문 칸 174 에 든다 (confirm 의 셈).
 */
public final class OriginDialog {
    public static final String ID = "origin";
    public static final String CONFIRM = "origin_confirm";
    /** 출신 줄 단추와 머리줄 폭. 글이 서는 폭 (− 16) = 이름 칸 + 능력치 일곱 칸 (Columns.STAT_COL 30) + KIT_GAP + 아이템 칸 (pack/typeset.py ROWS) */
    static final int WIDTH = 370;
    /**
     * 확인 창의 시작 아이템 이름 칸 (pack/typeset.py CAPTION_*): 그 창의 아이템 이름 가운데 가장 넓은 제목 글꼴 폭 + CAPTION_PAD 를
     * [CAPTION_MIN, CAPTION_MAX] 에. 한 창의 이름 칸은 같은 폭이라 아이콘이 세로로 선다. 짧은 이름만 있으면 CAPTION_MIN (이름이 그림 곁에
     * 붙는다: 200 이면 가운데 맞춤이라 그림에서 멀리 떨어졌다, 검토 origin-table-scan). 폭을 모르면 (옛 팩) CAPTION_FALLBACK.
     */
    static final int CAPTION_MIN = 150, CAPTION_MAX = 300, CAPTION_PAD = 16, CAPTION_FALLBACK = 240;

    private OriginDialog() {}

    public static void show(Souls plugin, Player p) {
        Ui ui = plugin.ui();
        Ui.Session s = ui.begin(ID, true);
        List<ActionButton> buttons = new ArrayList<>();
        for (Origins.Origin o : plugin.origins().all()) {
            String id = o.id();
            buttons.add(ui.button(s, id, row(p, o), Lang.c(p, "origin." + id + ".desc"), WIDTH, // lang-dyn: origin.*.desc
                    (pl, v) -> confirm(plugin, pl, id)));
        }
        ActionButton later = ui.button(s, "exit", Lang.c(p, "origin.later"), null, 200, (pl, v) -> plugin.start().originLater(pl));
        Dialog d = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(Glyphs.dialogTitle(Lang.c(p, "origin.title")))
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.NONE)
                        .body(List.of(DialogBody.plainMessage(header(p), WIDTH)))
                        .build())
                .type(DialogType.multiAction(buttons).exitAction(later).columns(1).build()));
        ui.show(p, s, d);
    }

    /** 머리줄: 출신, 레벨, 생명력 정신력 지구력 근력 민첩 지력, 시작 아이템 (출신 줄과 같은 열). */
    static Component header(Player p) {
        TextComponent.Builder b = Component.text();
        b.append(Lang.cell(p, "origin.head-name"));
        b.append(Lang.rcell(p, "origin.head-level"));
        for (String id : StatBlock.IDS) b.append(Lang.rcell(p, "stat." + id + ".short")); // lang-dyn: stat.*.short
        b.append(Columns.pad(Columns.KIT_GAP));
        b.append(Lang.cell(p, "origin.head-kit"));
        return b.build().decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE);
    }

    /** 출신 한 줄 (단추 글). 그 출신의 주 능력치 (가장 높은 것, 둘째가 12 넘고 셋째보다 높으면 그것도) 는 양피지색 굵게 (검토 origin-table-scan). */
    static Component row(Player p, Origins.Origin o) {
        TextComponent.Builder b = Component.text();
        b.append(Lang.cell(p, "origin." + o.id() + ".name")); // lang-dyn: origin.*.name
        b.append(Columns.right(String.valueOf(o.level()), Columns.STAT_COL, Columns.VALUE_COLOR));
        StatBlock s = o.stats();
        java.util.Set<String> main = mainStats(s);
        for (String id : StatBlock.IDS) {
            boolean m = main.contains(id);
            b.append(Columns.right(String.valueOf(s.get(id)), Columns.STAT_COL, m ? Columns.MAIN_COLOR : Columns.VALUE_COLOR, m));
        }
        b.append(Columns.pad(Columns.KIT_GAP));
        b.append(Lang.cell(p, "origin." + o.id() + ".kit")); // lang-dyn: origin.*.kit
        return b.build().decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE);
    }

    /** 주 능력치: 가장 높은 값이 하나뿐이면 그것, 둘째 값이 12 이상이고 셋째보다 높으면 그것도 (빈털터리처럼 모두 같으면 없음). */
    static java.util.Set<String> mainStats(StatBlock s) {
        List<String> ids = new ArrayList<>(StatBlock.IDS);
        ids.sort((x, y) -> Integer.compare(s.get(y), s.get(x)));
        java.util.Set<String> out = new java.util.HashSet<>();
        int v0 = s.get(ids.get(0)), v1 = s.get(ids.get(1)), v2 = s.get(ids.get(2));
        if (v0 > v1) {
            out.add(ids.get(0));
            if (v1 >= 12 && v1 > v2) out.add(ids.get(1));
        }
        return out;
    }

    /** 확인 창. */
    static void confirm(Souls plugin, Player p, String id) {
        Origins.Origin o = plugin.origins().get(id);
        if (o == null) {
            show(plugin, p);
            return;
        }
        Ui ui = plugin.ui();
        Ui.Session s = ui.begin(CONFIRM, true);
        // 시작 아이템 (지금 만들 수 있는 것만): 그림과 이름 칸 (가리키면 무기 설명 칸)
        List<ItemStack> stacks = new ArrayList<>();
        List<Component> names = new ArrayList<>();
        List<String> nameKeys = new ArrayList<>();
        Weapons.Def main = null, cat = null, off = null;
        boolean offEmpty = true;
        for (Origins.Kit k : o.kit()) {
            if (!Origins.creatable(k, plugin.weapons())) continue;
            ItemStack it = Origins.make(k, plugin.weapons());
            if (it == null) continue;
            String key;
            Component name;
            if ("weapon".equals(k.kind())) {
                Weapons.Def d = plugin.weapons().get(k.id());
                if ("off".equals(k.to())) {
                    offEmpty = false;
                    off = d;
                }
                if ("main".equals(k.to()) && Stats.isMelee(d)) main = d;
                if (Stats.isCatalyst(d)) cat = d;
                key = "weapon." + k.id() + ".name";
                name = it.getData(io.papermc.paper.datacomponent.DataComponentTypes.ITEM_NAME);
            } else if (it.getAmount() > 1) {
                // 개수가 있는 것 (궁수의 화살): 이름 칸에 개수를 쓰고 아이콘의 개수 숫자는 끈다 (숫자가 그림에 겹쳤다, 검토 archer-arrow-row-visual)
                key = "origin.kit-arrows";
                name = Lang.c(p, "origin.kit-arrows", "count", String.valueOf(it.getAmount()));
            } else {
                key = "item." + k.id() + ".name";
                name = it.getData(io.papermc.paper.datacomponent.DataComponentTypes.ITEM_NAME);
            }
            if (name == null) name = Component.translatable(it.getType().translationKey());
            stacks.add(it);
            names.add(name);
            nameKeys.add(key);
        }
        int captionW = captionWidth(Lang.langOf(p), nameKeys);
        List<DialogBody> items = new ArrayList<>();
        for (int i = 0; i < stacks.size(); i++) {
            ItemStack it = stacks.get(i);
            items.add(DialogBody.item(it).description(DialogBody.plainMessage(names.get(i), captionW)).showTooltip(true)
                    .showDecorations(it.getAmount() <= 1).build());
        }
        StatBlock st = o.stats();
        Derived d = Derived.of(st, plugin.cfg().stats, plugin.cfg().load, Stats.arms(main), offEmpty, Stats.arms(cat), kitWeight(plugin, o),
                plugin.cfg().stamina.regenPerTick());
        // 한 글 (본문 요소 사이 10 을 아낀다): 어떻게 싸우는지 한 줄, 빈 줄, 능력치 표 (왼쪽 능력치 여섯, 주 능력치는 출신 줄처럼 굵게. 오른쪽
        // 그 출신으로 시작할 때의 값), 조작 한 줄 (구르기와 패링). 그 밑에 시작 아이템. 시작 아이템이 셋인 도적·궁수도 1280×720 GUI 3 의
        // 본문 칸 174 에 든다: 글 9 줄 (9 × 9 + 8 = 89) + 아이템 셋 (17 × 3) + 사이 10 × 3 = 170. 아이템이 둘 이하면 표와 조작 줄 사이에도
        // 빈 줄 (10 줄 98 + 아이템 둘 34 + 사이 20 = 152)
        List<Component> info = new ArrayList<>();
        info.add(Lang.c(p, "origin." + id + ".style")); // lang-dyn: origin.*.style
        info.add(Component.empty());
        info.addAll(StatSheet.lines(p, StatSheet.stats(st, st, mainStats(st)), StatSheet.origin(d)));
        if (items.size() <= 2) info.add(Component.empty());
        // 패링 (F, 왼손에 든 것으로): 그 출신의 왼손 물건이 패링할 수 있을 때만 (대방패·빈 왼손은 F 가 아무것도 하지 않는다). 구르기와 한 줄
        Component controls = rollHint(plugin, p);
        if (Parry.baseWindow(plugin.cfg().parry, off, offEmpty) > 0) {
            controls = Component.text().append(controls).append(Columns.pad(StatSheet.GAP)).append(parryHint(plugin, p)).build();
        }
        info.add(controls);
        List<DialogBody> body = new ArrayList<>();
        body.add(DialogBody.plainMessage(Columns.lines(info), StatSheet.WIDTH));
        body.addAll(items);
        ActionButton yes = ui.button(s, "choose", Lang.c(p, "origin.choose"), null, 150, (pl, v) -> plugin.start().chooseOrigin(pl, id, "dialog"));
        ActionButton no = ui.button(s, "back", Lang.c(p, "origin.back"), null, 150, (pl, v) -> show(plugin, pl));
        Dialog dlg = Dialog.create(b -> b.empty()
                // 제목 글꼴과 금실 (다른 창 제목과 같게, 검토 confirm-title-unstyled): 팩이 출신마다 짠 origin.confirm-title.<id>
                .base(DialogBase.builder(Glyphs.dialogTitle(Lang.titled(p, "origin.confirm-title", id, "origin." + id + ".name"))) // lang-dyn: origin.*.name
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.NONE)
                        .body(body)
                        .build())
                .type(DialogType.confirmation(yes, no)));
        ui.show(p, s, dlg);
    }

    /** 시작 아이템 이름 칸 폭 (CAPTION_*): 이름 열쇠들의 제목 글꼴 폭 (glyphs.yml captions) 가운데 가장 넓은 것 + CAPTION_PAD. */
    static int captionWidth(String lang, List<String> keys) {
        int w = 0;
        for (String k : keys) {
            int kw = Glyphs.captions().width(lang, k);
            if (kw < 0) return CAPTION_FALLBACK;
            w = Math.max(w, kw);
        }
        return Math.max(CAPTION_MIN, Math.min(CAPTION_MAX, w + CAPTION_PAD));
    }

    /** 조작 알림: 구르기 (키 묶음 글. 웅크리기 키 짧게, roll-key: f 면 F). */
    public static Component rollHint(Souls plugin, Player p) {
        return plugin.cfg().controls.sneakRolls()
                ? Lang.c(p, "controls.hint.roll", "bind", Component.keybind("key.sneak"))
                : Lang.c(p, "controls.hint.roll-f", "bind", Component.keybind("key.swapOffhand"));
    }

    /** 조작 알림: 패링 (키 묶음 글. F, roll-key: f·both 면 F 가 구르기라 웅크리기 키 + F). */
    public static Component parryHint(Souls plugin, Player p) {
        return plugin.cfg().controls.fRolls()
                ? Lang.c(p, "controls.hint.parry-sneak", "sneak", Component.keybind("key.sneak"), "bind", Component.keybind("key.swapOffhand"))
                : Lang.c(p, "controls.hint.parry", "bind", Component.keybind("key.swapOffhand"));
    }

    /** 시작 장비의 무게 (5.8: 단축 슬롯·왼손에 놓이는 souls 무기·방패·촉매만. 가방에 가는 것은 들지 않는다). */
    static double kitWeight(Souls plugin, Origins.Origin o) {
        double w = 0;
        for (Origins.Kit k : o.kit()) {
            if (!"weapon".equals(k.kind()) || k.to() == null) continue;
            if (!"main".equals(k.to()) && !"off".equals(k.to()) && !k.to().startsWith("hotbar:")) continue;
            Weapons.Def def = plugin.weapons().get(k.id());
            if (def != null) w += def.weight();
        }
        return w;
    }
}
