package kr.souls.bonfire;

import io.papermc.paper.dialog.Dialog;
import io.papermc.paper.registry.data.dialog.ActionButton;
import io.papermc.paper.registry.data.dialog.DialogBase;
import io.papermc.paper.registry.data.dialog.body.DialogBody;
import io.papermc.paper.registry.data.dialog.type.DialogType;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.data.Profile;
import kr.souls.hud.Glyphs;
import kr.souls.progression.Origins;
import kr.souls.ui.StatsDialog;
import kr.souls.ui.Ui;
import org.bukkit.entity.Player;

import java.text.NumberFormat;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 휴식 창 (4.1). 지금은 시험 방 화톳불의 창이다 (TestBonfire): 맨 위 "세계를 정한다" (세계 설정이 잠정이고 이 사람이 정할 사람일 때,
 * 5.7), "레벨 올리기" (5.9), "능력치" (5.9), "출신을 다시 고른다" (출신의 레벨에서 아직 하나도 올리지 않았을 때 한 번, 검토 caster-trap),
 * 나가기 동작 "일어선다". 이동·반지·기억·병 나누기·에스트 단추는 그 체계가 생기는 M2~M5 에 더한다. M2 의 진짜 화톳불도 이 창을 쓴다.
 */
public final class RestMenu {
    public static final String ID = "rest";

    private RestMenu() {}

    public static void show(Souls plugin, Player p) {
        Ui ui = plugin.ui();
        Ui.Session s = ui.begin(ID);
        Profile pr = plugin.profiles().of(p);
        List<ActionButton> buttons = new ArrayList<>();
        if (plugin.start().canSetNow(p)) {
            buttons.add(ui.button(s, "settings", Lang.c(p, "bonfire.settings"), null, 160, (pl, v) -> {
                if (!plugin.start().openSettings(pl, "rest")) show(plugin, pl);
            }));
        }
        buttons.add(ui.button(s, "levelup", Lang.c(p, "bonfire.levelup"), null, 160, (pl, v) -> plugin.levelUp().open(pl)));
        buttons.add(ui.button(s, "stats", Lang.c(p, "bonfire.stats"), null, 160, (pl, v) -> StatsDialog.show(plugin, pl, pl, true)));
        Origins.Origin o = plugin.origins().get(pr.origin());
        if (o != null && pr.stats().level() == o.level()) {
            buttons.add(ui.button(s, "repick", Lang.c(p, "bonfire.repick"), Lang.c(p, "bonfire.repick-tip"), 160,
                    (pl, v) -> {
                        if (!plugin.start().repick(pl)) show(plugin, pl);
                    }));
        }
        ActionButton leave = ui.button(s, "exit", Lang.c(p, "bonfire.leave"), null, 160, (pl, v) -> {
            plugin.levelUp().discard(pl);
            ui.close(pl);
            plugin.test(pl, "REST leave t=" + plugin.ticker().now());
        });
        String souls = NumberFormat.getIntegerInstance(Locale.US).format(pr.souls());
        Dialog d = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(Glyphs.dialogTitle(Lang.c(p, "bonfire.test-name")))
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.NONE)
                        .body(List.of(DialogBody.plainMessage(Lang.c(p, "bonfire.status", "souls", souls, "level",
                                String.valueOf(pr.stats().level())))))
                        .build())
                .type(DialogType.multiAction(buttons).exitAction(leave).columns(1).build()));
        ui.show(p, s, d);
    }
}
