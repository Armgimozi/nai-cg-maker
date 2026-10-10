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
import kr.souls.ui.Columns;
import kr.souls.ui.StatSheet;
import kr.souls.ui.StatsDialog;
import kr.souls.ui.Ui;
import org.bukkit.entity.Player;

import java.text.NumberFormat;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 휴식 창 (4.1). 지금은 시험 방 화톳불의 창이다 (TestBonfire): 맨 위 "세계를 정한다" (세계 설정이 잠정이고 이 사람이 정할 사람일 때,
 * 5.7), "레벨 올리기" (5.9), "능력치" (5.9), "출신을 다시 고른다" (출신의 레벨에서 아직 하나도 올리지 않았을 때 한 번, 검토 caster-trap·
 * repick-not-once: 쓰면 프로필의 repicked 가 서서 다시 나오지 않는다), 본문 "소울 · 레벨 · 다음 레벨 비용",
 * 나가기 동작 "일어선다". 이동·반지·기억·병 나누기·에스트 단추는 그 체계가 생기는 M2~M5 에 더한다. M2 의 진짜 화톳불도 이 창을 쓴다.
 */
public final class RestMenu {
    public static final String ID = "rest";

    private RestMenu() {}

    public static void show(Souls plugin, Player p) {
        Ui ui = plugin.ui();
        Ui.Session s = ui.begin(ID, true);
        Profile pr = plugin.profiles().of(p);
        List<ActionButton> buttons = new ArrayList<>();
        if (plugin.start().canSetNow(p)) {
            buttons.add(ui.button(s, "settings", Lang.c(p, "bonfire.settings"), null, 160, (pl, v) -> {
                // 누른 그때 다시 본다: 그 사이 관리자가 확정했거나 다른 사람이 정하는 중이면 알리고 휴식 창으로 (검토 settings-stale-eligibility)
                if (!plugin.start().canSetNow(pl)) {
                    plugin.test(pl, "SETTINGS_DENY why=stale_rest t=" + plugin.ticker().now());
                    pl.sendMessage(Lang.c(pl, "start.already-set"));
                    show(plugin, pl);
                } else if (!plugin.start().openSettings(pl, "rest")) {
                    show(plugin, pl);
                }
            }));
        }
        buttons.add(ui.button(s, "levelup", Lang.c(p, "bonfire.levelup"), null, 160, (pl, v) -> plugin.levelUp().open(pl)));
        buttons.add(ui.button(s, "stats", Lang.c(p, "bonfire.stats"), null, 160, (pl, v) -> StatsDialog.show(plugin, pl, pl, true)));
        if (plugin.start().canRepick(p)) {
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
        NumberFormat nf = NumberFormat.getIntegerInstance(Locale.US);
        String souls = nf.format(pr.souls());
        String next = nf.format(plugin.cfg().levelCost.next(pr.stats().level()));
        Dialog d = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(Glyphs.dialogTitle(Lang.c(p, "bonfire.test-name")))
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.NONE)
                        // 레벨·보유 소울·필요 소울을 칸 맞춤 세 줄로 (레벨 올리기 창의 머리와 같은 칸, ui/StatSheet)
                        .body(List.of(DialogBody.plainMessage(Columns.lines(StatSheet.leftLines(p, StatSheet.restHead(
                                String.valueOf(pr.stats().level()), souls, next))), 200)))
                        .build())
                .type(DialogType.multiAction(buttons).exitAction(leave).columns(1).build()));
        ui.show(p, s, d);
    }
}
