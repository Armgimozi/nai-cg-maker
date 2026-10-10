package kr.souls.ui;

import io.papermc.paper.dialog.Dialog;
import io.papermc.paper.registry.data.dialog.ActionButton;
import io.papermc.paper.registry.data.dialog.DialogBase;
import io.papermc.paper.registry.data.dialog.body.DialogBody;
import io.papermc.paper.registry.data.dialog.type.DialogType;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.bonfire.RestMenu;
import kr.souls.data.Profile;
import kr.souls.hud.Glyphs;
import kr.souls.progression.Derived;
import kr.souls.progression.StatBlock;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 능력치 창 (5.9, 읽기만): 휴식 창의 "능력치" 와 명령 /stats (어디서나). 본문: "레벨 11 · 소울 11,360 · 기사", 능력치 여섯 한 줄, 값 표 여섯 줄
 * (레벨 올리기 창과 같은 표, 화살표 없이), 장비 무게 한 줄 ("장비 무게 7.0 / 44.2 · 가벼움"), 불에 타는 시간 한 줄 ("불에 타는 시간 3.0초 →
 * 2.5초": 지능의 상태 이상 저항을 길이로, 검토 int-dead-now·burn-line-unlabelled. 저항이 없으면 줄이 없다). 단추 "닫는다" (휴식 창에서
 * 열었으면 휴식 창으로). 휴식 창에서 열었을 때만 PvP 로 맞지 않는다 (어디서나 여는 /stats 는 숨을 곳이 아니다).
 */
public final class StatsDialog {
    public static final String ID = "stats";

    private StatsDialog() {}

    /** of: 이 사람의 능력치를 viewer 에게 (관리자의 /stats &lt;이름&gt;). fromRest 면 닫을 때 휴식 창으로. */
    public static void show(Souls plugin, Player viewer, Player of, boolean fromRest) {
        Ui ui = plugin.ui();
        Ui.Session s = ui.begin(ID, fromRest);
        Profile pr = plugin.profiles().of(of);
        StatBlock st = pr.stats();
        Derived d = plugin.stats().derived(of);
        Component origin = pr.origin() == null ? Lang.c(viewer, "stats.no-origin") : Lang.c(viewer, "origin." + pr.origin() + ".name"); // lang-dyn: origin.*.name
        List<Component> lines = new ArrayList<>();
        lines.add(Lang.c(viewer, "stats.head", "level", String.valueOf(st.level()), "souls", LevelUpDialog.souls(pr.souls()), "origin", origin));
        lines.add(OriginDialog.statsLine(viewer, st));
        lines.addAll(StatRows.rows(viewer, d, null));
        lines.add(Lang.c(viewer, "stats.load", "weight", String.format(Locale.ROOT, "%.1f", d.weight()), "cap",
                String.format(Locale.ROOT, "%.1f", d.cap()), "tier", Lang.c(viewer, "load." + d.tier().id()))); // lang-dyn: load.*
        // 지능의 상태 이상 저항을 길이로 (불에 타는 3초 → 몇 초). 저항이 없으면 (같은 값) 보이지 않는다 (검토 burn-line-unlabelled)
        String burnTo = LevelUpDialog.burn(d.ailment());
        if (!"3.0".equals(burnTo)) lines.add(Lang.c(viewer, "stats.burn", "from", "3.0", "to", burnTo));
        ActionButton close = ui.button(s, "exit", Lang.c(viewer, "stats.close"), null, 200, (pl, v) -> {
            if (fromRest) RestMenu.show(plugin, pl);
            else ui.close(pl);
        });
        Dialog dlg = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(Glyphs.dialogTitle(Lang.c(viewer, "stats.title")))
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.NONE)
                        .body(List.of(DialogBody.plainMessage(Columns.lines(lines), 300)))
                        .build())
                .type(DialogType.notice(close)));
        ui.show(viewer, s, dlg);
        plugin.test(viewer, plugin.stats().line(of));
    }
}
