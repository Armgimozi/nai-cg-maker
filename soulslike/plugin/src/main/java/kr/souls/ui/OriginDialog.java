package kr.souls.ui;

import io.papermc.paper.dialog.Dialog;
import io.papermc.paper.registry.data.dialog.ActionButton;
import io.papermc.paper.registry.data.dialog.DialogBase;
import io.papermc.paper.registry.data.dialog.body.DialogBody;
import io.papermc.paper.registry.data.dialog.type.DialogType;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.combat.DamageCalc;
import kr.souls.hud.Glyphs;
import kr.souls.item.ItemFactory;
import kr.souls.item.MasterKey;
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
import java.util.Locale;

/**
 * "너는 누구였나" 출신 창 (5.10): 머리줄 하나와 출신마다 단추 하나 (폭 320). 단추 글은 [이름 칸][레벨][능력치 여섯][시작 아이템 칸] 을
 * 열 맞추기로 짜서 (Columns, 팩의 칸) 모든 줄의 폭이 같고, 그래서 가운데 맞춤인 단추 글과 머리줄의 열이 위아래로 선다.
 * 단추를 누르면 확인 창: 설명 한 줄, 됨됨이 한 줄, 시작 아이템 그림 (가리키면 설명 칸), 레벨·최대 HP·마나·스태미나, 공격력, 조작 두 줄
 * (키 묶음 글: 그 사람이 바꾼 키 이름). "이 출신으로" / "돌아간다".
 * 높이: 제목 + 머리줄 + 단추 여섯 + 나가기 ≈ 228 GUI 픽셀이라 1280×720 GUI 3 (240) 에서도 굴리지 않는다 (검토 T4·dialog-height).
 */
public final class OriginDialog {
    public static final String ID = "origin";
    public static final String CONFIRM = "origin_confirm";
    static final int WIDTH = 320;

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

    /** 머리줄: 출신 · 레벨 · 체력 정신 기력 근력 민첩 지능 · 시작 아이템 (출신 줄과 같은 열). */
    static Component header(Player p) {
        TextComponent.Builder b = Component.text();
        b.append(Lang.cell(p, "origin.head-name"));
        b.append(Lang.rcell(p, "origin.head-level"));
        for (String id : StatBlock.IDS) b.append(Lang.rcell(p, "stat." + id + ".short")); // lang-dyn: stat.*.short
        b.append(Columns.pad(Columns.KIT_GAP));
        b.append(Lang.cell(p, "origin.head-kit"));
        return b.build().decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE);
    }

    /** 출신 한 줄 (단추 글). */
    static Component row(Player p, Origins.Origin o) {
        TextComponent.Builder b = Component.text();
        b.append(Lang.cell(p, "origin." + o.id() + ".name")); // lang-dyn: origin.*.name
        b.append(Columns.right(String.valueOf(o.level()), Columns.STAT_COL, Columns.VALUE_COLOR));
        StatBlock s = o.stats();
        for (String id : StatBlock.IDS) b.append(Columns.right(String.valueOf(s.get(id)), Columns.STAT_COL, Columns.VALUE_COLOR));
        b.append(Columns.pad(Columns.KIT_GAP));
        b.append(Lang.cell(p, "origin." + o.id() + ".kit")); // lang-dyn: origin.*.kit
        return b.build().decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE);
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
        List<DialogBody> body = new ArrayList<>();
        List<Component> top = new ArrayList<>();
        top.add(Lang.c(p, "origin." + id + ".desc")); // lang-dyn: origin.*.desc
        top.add(Lang.c(p, "origin." + id + ".style")); // lang-dyn: origin.*.style
        body.add(DialogBody.plainMessage(Columns.lines(top), 300));
        // 시작 아이템 그림 (지금 만들 수 있는 것만. 가리키면 무기 설명 칸)
        Weapons.Def main = null, cat = null;
        boolean offEmpty = true, bow = false;
        for (Origins.Kit k : o.kit()) {
            ItemStack it = null;
            if ("weapon".equals(k.kind())) {
                Weapons.Def d = plugin.weapons().get(k.id());
                if (d == null) continue;
                it = ItemFactory.weapon(d);
                if ("off".equals(k.to())) offEmpty = false;
                if ("main".equals(k.to()) && Stats.isMelee(d)) main = d;
                if (Stats.isCatalyst(d)) cat = d;
                if (Weapons.BOW.equals(d.use())) bow = true;
            } else if ("item".equals(k.kind()) && MasterKey.ID.equals(k.id())) {
                it = MasterKey.make();
            }
            if (it != null) {
                body.add(DialogBody.item(it).description(DialogBody.plainMessage(it.getData(io.papermc.paper.datacomponent.DataComponentTypes.ITEM_NAME), 200))
                        .showTooltip(true).showDecorations(true).build());
            }
        }
        StatBlock st = o.stats();
        Derived d = Derived.of(st, plugin.cfg().stats, plugin.cfg().load, Stats.arms(main), offEmpty, Stats.arms(cat), 0,
                plugin.cfg().stamina.regenPerTick());
        List<Component> info = new ArrayList<>();
        info.add(Lang.c(p, "origin.stats", "level", String.valueOf(st.level()), "hp", fmt(d.maxHp()), "mana", fmt(d.maxMana()),
                "stamina", fmt(d.maxStamina())));
        info.add(statsLine(p, st));
        if (main != null) {
            String ar = fmt(DamageCalc.ar(plugin.cfg().stats, Stats.arms(main), st.str(), offEmpty));
            Component w = Lang.c(p, "weapon." + main.id() + ".name"); // lang-dyn: weapon.*.name
            info.add(offEmpty ? Lang.c(p, "origin.attack-2h", "weapon", w, "attack", ar) : Lang.c(p, "origin.attack", "weapon", w, "attack", ar));
        }
        if (cat != null) info.add(Lang.c(p, "origin.no-rites"));
        if (bow) info.add(Lang.c(p, "origin.no-bow"));
        info.add(rollHint(plugin, p));
        info.add(Lang.c(p, "controls.hint.art", "bind", Component.keybind("key.swapOffhand")));
        body.add(DialogBody.plainMessage(Columns.lines(info), 300));
        ActionButton yes = ui.button(s, "choose", Lang.c(p, "origin.choose"), null, 150, (pl, v) -> plugin.start().chooseOrigin(pl, id, "dialog"));
        ActionButton no = ui.button(s, "back", Lang.c(p, "origin.back"), null, 150, (pl, v) -> show(plugin, pl));
        Dialog dlg = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(Glyphs.dialogTitle(Lang.c(p, "origin." + id + ".name"))) // lang-dyn: origin.*.name
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.NONE)
                        .body(body)
                        .build())
                .type(DialogType.confirmation(yes, no)));
        ui.show(p, s, dlg);
    }

    /** 조작 알림: 구르기 (키 묶음 글. 웅크리기 키 짧게, roll-key: f 면 F). */
    public static Component rollHint(Souls plugin, Player p) {
        return plugin.cfg().controls.sneakRolls()
                ? Lang.c(p, "controls.hint.roll", "bind", Component.keybind("key.sneak"))
                : Lang.c(p, "controls.hint.roll-f", "bind", Component.keybind("key.swapOffhand"));
    }

    /** "체력 15 · 정신 9 · 기력 11 · 근력 13 · 민첩 11 · 지능 9" (능력치 이름은 줄임 이름). */
    public static Component statsLine(Player p, StatBlock st) {
        TextComponent.Builder b = Component.text();
        boolean first = true;
        for (String id : StatBlock.IDS) {
            if (!first) b.append(Lang.c(p, "stats.sep"));
            first = false;
            b.append(Lang.c(p, "stats.pair", "stat", Lang.c(p, "stat." + id + ".short"), "value", String.valueOf(st.get(id)))); // lang-dyn: stat.*.short
        }
        return b.build();
    }

    static String fmt(double v) {
        return String.format(Locale.ROOT, "%.0f", v);
    }
}
