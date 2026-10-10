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

/**
 * 능력치 창 (5.9, 읽기만): 휴식 창의 "능력치" 와 명령 /stats (어디서나). 본문은 레벨 올리기 창과 같은 표 (StatSheet, 화살표 없이): 왼쪽에
 * 출신·레벨·보유 소울·필요 소울 (엘든 링 상태 창처럼), 빈 줄, 능력치 여섯. 오른쪽에 나온 값을 무리마다 빈 줄로 나눠 (자원 | 장비 중량과
 * 무게 단계 | 움직임·공격 | 막기, StatSheet.derived 의 statsView: 왼쪽 머리 넷 밑의 빈 줄과 오른쪽 첫 빈 줄이 같은 높이). 표 밑에 불에
 * 타는 시간 한 줄 ("불에 타는 시간 2.5초 (기본 3.0초)": 지력의 상태 이상 내성을 길이로, 검토 int-dead-now·burn-line-unlabelled. 읽기만
 * 하는 창이라 레벨 업 미리보기의 화살표를 쓰지 않는다, 검토 stats-burn-arrow-semantics. 내성이 없으면 줄이 없다). 높이: 17 줄
 * (17 × 9 + 8 = 161) 이 1280×720 GUI 3 의 본문 칸 174 에 든다 (단추는 바닥 줄). 단추 "닫기" (휴식 창에서 열었으면 휴식 창으로).
 * 휴식 창에서 열었을 때만 PvP 로 맞지 않는다 (어디서나 여는 /stats 는 숨을 곳이 아니다).
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
        List<StatSheet.Cell> left = new ArrayList<>();
        // 출신 이름은 팩이 값 열 폭에 오른쪽을 맞춘 칸 (origin.*.name.rcell, 없으면 stats.no-origin.rcell)
        left.add(new StatSheet.Cell("table.origin", Lang.rcell(viewer, pr.origin() == null ? "stats.no-origin" : "origin." + pr.origin() + ".name"))); // lang-dyn: origin.*.name, stats.no-origin
        left.add(StatSheet.head("table.level", String.valueOf(st.level())));
        left.add(StatSheet.head("table.held", LevelUpDialog.souls(pr.souls())));
        left.add(StatSheet.head("table.need", LevelUpDialog.souls(plugin.cfg().levelCost.next(st.level()))));
        left.add(StatSheet.blankLeft());
        left.addAll(StatSheet.stats(st, st, java.util.Set.of()));
        List<Component> lines = new ArrayList<>(StatSheet.lines(viewer, left, StatSheet.derived(viewer, d, null, true)));
        // 지력의 상태 이상 내성을 길이로 (불에 타는 3초 → 몇 초). 저항이 없으면 (같은 값) 보이지 않는다 (검토 burn-line-unlabelled)
        String burnTo = LevelUpDialog.burn(d.ailment());
        if (!"3.0".equals(burnTo)) lines.add(Lang.c(viewer, "stats.burn", "from", "3.0", "to", burnTo));
        ActionButton close = ui.button(s, "exit", Lang.c(viewer, "stats.close"), null, 200, (pl, v) -> {
            if (fromRest) RestMenu.show(plugin, pl);
            else ui.close(pl);
        });
        Dialog dlg = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(Glyphs.dialogTitle(Lang.c(viewer, "stats.title")))
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.NONE)
                        .body(List.of(DialogBody.plainMessage(Columns.lines(lines), StatSheet.WIDTH)))
                        .build())
                .type(DialogType.notice(close)));
        ui.show(viewer, s, dlg);
        plugin.test(viewer, plugin.stats().line(of));
    }
}
