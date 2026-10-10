package kr.souls.ui;

import io.papermc.paper.dialog.Dialog;
import io.papermc.paper.dialog.DialogResponseView;
import io.papermc.paper.registry.data.dialog.ActionButton;
import io.papermc.paper.registry.data.dialog.DialogBase;
import io.papermc.paper.registry.data.dialog.body.DialogBody;
import io.papermc.paper.registry.data.dialog.input.DialogInput;
import io.papermc.paper.registry.data.dialog.type.DialogType;
import kr.souls.Config;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.data.WorldState;
import kr.souls.hud.Glyphs;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * "세계 설정" 창 (5.7). 본문 한 줄과 PvP 줄 둘, PvP 체크 칸 하나, 난이도 단추 넷 (이름만: "쉬움", "보통 (권장)" …. 단추 설명 칸에 그
 * 난이도의 한 줄과 지금 듣는 배율). 단추를 누르면 체크 칸 값을 읽어 곧바로 정하고 출신 창으로 간다 (검토 settings-dialog-dense: 고름
 * 칸과 "시작한다" 를 없앴다). 기본 난이도 단추에 "(권장)" 을 단다. Esc 와 "나중에 정하기" 는 잠정 기본값 그대로 (StartFlow.settingsLater,
 * 설명 칸에 그 값). 예전 단추 글 "쉬움 — 적이 약하다" 는 줄표와 내레이션이 AI 티가 나서 바꿨다 (DECISIONS 2026-10-10).
 */
public final class SettingsDialog {
    public static final String ID = "settings";
    static final int WIDTH = 250;

    private SettingsDialog() {}

    public static void show(Souls plugin, Player p) {
        Ui ui = plugin.ui();
        Ui.Session s = ui.begin(ID, true);
        WorldState.Settings cur = plugin.worldState().get();
        boolean pvp0 = cur != null ? cur.pvp() : plugin.cfg().pvp.def();
        List<ActionButton> buttons = new ArrayList<>();
        for (Config.Difficulty d : plugin.cfg().difficulties.values()) {
            String id = d.id();
            Component name = Lang.c(p, "difficulty." + id + ".name"); // lang-dyn: difficulty.*.name
            Component desc = Lang.c(p, "difficulty." + id + ".desc"); // lang-dyn: difficulty.*.desc
            Component label = id.equals(plugin.cfg().difficultyDefault)
                    ? Lang.c(p, "start.choice-default", "name", name)
                    : Lang.c(p, "start.choice", "name", name);
            buttons.add(ui.button(s, id, label, Columns.lines(List.of(desc, summary(p, d))), WIDTH,
                    (pl, v) -> plugin.start().chooseSettings(pl, id, bool(v, "pvp", pvp0), "dialog")));
        }
        // "나중에 정하기" 의 설명 칸: 그동안 쓰는 잠정 설정 (검토 start-dialog-wording)
        String dNow = cur != null ? cur.difficulty() : plugin.cfg().difficultyDefault;
        Component laterTip = Lang.c(p, "start.later-tip", "difficulty", kr.souls.start.StartFlow.diffName(p, dNow), "pvp",
                kr.souls.start.StartFlow.pvpName(p, pvp0));
        ActionButton later = ui.button(s, "exit", Lang.c(p, "start.later"), laterTip, WIDTH, (pl, v) -> plugin.start().settingsLater(pl));
        List<DialogBody> body = List.of(DialogBody.plainMessage(Columns.lines(List.of(Lang.c(p, "start.body"), Lang.c(p, "start.pvp-hit"),
                Lang.c(p, "start.pvp-sweep"))), 300));
        Dialog d = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(Glyphs.dialogTitle(Lang.c(p, "start.title")))
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.NONE)
                        .body(body)
                        .inputs(List.of(DialogInput.bool("pvp", Lang.c(p, "start.pvp")).initial(pvp0).build()))
                        .build())
                .type(DialogType.multiAction(buttons).exitAction(later).columns(1).build()));
        ui.show(p, s, d);
    }

    /**
     * 단추 설명 칸의 둘째 줄: 지금 듣는 배율만 "받는 피해 ×0.7, 적 HP ×0.8" (검토 difficulty-promises-unbuilt). 패링 판정·에스트 횟수는 그 체계가
     * 생기는 M1 에 보통과 다를 때만 더한다 ("+0틱" 을 보이지 않게).
     */
    static Component summary(Player p, Config.Difficulty d) {
        return Lang.c(p, "difficulty.summary", "damage", num(d.enemyDamage()), "health", num(d.enemyHealth()));
    }

    static String num(double v) {
        String s = String.format(Locale.ROOT, "%.2f", v);
        while (s.endsWith("0") && !s.endsWith(".0")) s = s.substring(0, s.length() - 1);
        return s;
    }

    /** 체크 칸 값 (시험 명령이 눌렀거나 값이 없으면 def). */
    static boolean bool(DialogResponseView v, String key, boolean def) {
        if (v == null) return def;
        Boolean b = v.getBoolean(key);
        return b == null ? def : b;
    }
}
