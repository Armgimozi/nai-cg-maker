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
import kr.souls.util.Fx;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.player.PlayerQuitEvent;

import java.text.NumberFormat;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * 레벨 올리기 창 (5.9): 휴식 창의 "레벨 올리기" (화톳불에서만, 시험 모드는 /soulstest levelup). 서버가 사람마다 더할 점 (세션) 을 들고
 * 있다. 본문은 다크 소울 상태 창 꼴의 표 (StatSheet): 왼쪽에 레벨·보유 소울·필요 소울과 능력치 여섯 ("10 → 13"), 오른쪽에 나온 값.
 * 능력치 단추 ("생명력 +", 한 줄에 여섯) 는 지금 레벨부터 (더한 점 + 1) 레벨의 비용 합이 가진 소울 이하일 때만 한 점 더하고, "되돌린다" 는
 * 마지막으로 더한 점을 뺀다 (원래 값 밑으로는 못 내린다), "올린다" 는 소울과 비용을 다시 셈해 맞으면 소울을 빼고 능력치를 올린다. 누를
 * 때마다 새 값으로 창을 다시 띄운다. "그만둔다" 와 Esc 는 더한 점을 버리고 휴식 창으로 돌아간다. 쉬는 중에 맞으면 창을 닫고 버린다.
 * 단추를 표의 왼쪽 목록에 넣지 못하는 까닭: 바닐라 Dialog 는 본문 (글) 을 모두 그린 뒤에 단추 격자를 둔다 (MultiButtonDialogScreen). 그래서
 * 능력치 단추는 표 밑 한 줄에 표의 차례대로 둔다.
 * 높이 (검토 dialog-height·T6, 1.21.11 DialogScreen: 본문 요소 사이 10, 단추 20 + 사이 2): 표 열두 줄 (12 × 9 + 8 = 116) + 10 + 단추
 * 두 줄 (능력치 여섯, 되돌린다·올린다) 42 = 168 이라 1280×720 GUI 3 의 본문 칸 174 (240 − 머리 33 − 바닥 33) 안에 들어 다시 띄워도
 * 단추가 밀려나지 않는다 (스크롤이 생기지 않는다).
 */
public final class LevelUpDialog implements Listener {
    public static final String ID = "levelup";
    /** 능력치 단추 폭 (여섯이 한 줄: 6 × 64 + 5 × 2 = 394, 1280×720 GUI 3 의 화면 폭 426 안) */
    static final int PLUS_WIDTH = 64;
    /** 되돌린다·올린다 (둘이 한 줄: 능력치 단추 줄과 같은 폭 394) */
    static final int ACTION_WIDTH = 196;

    /** 사람마다 더할 점 (차례대로 되돌리려고 쌓아 둔다). base 는 창을 연 때의 능력치. */
    private static final class Session {
        StatBlock base;
        final Deque<String> added = new ArrayDeque<>();

        Session(StatBlock base) {
            this.base = base;
        }

        StatBlock target() {
            StatBlock t = base;
            for (String s : added) t = t.plus(s, 1);
            return t;
        }
    }

    private final Souls plugin;
    private final Map<UUID, Session> sessions = new HashMap<>();

    public LevelUpDialog(Souls plugin) {
        this.plugin = plugin;
    }

    public void open(Player p) {
        sessions.put(p.getUniqueId(), new Session(plugin.stats().of(p)));
        plugin.test(p, "LEVELUP open level=" + plugin.stats().level(p) + " souls=" + plugin.purse().get(p));
        show(p);
    }

    public boolean active(Player p) {
        return sessions.containsKey(p.getUniqueId());
    }

    private Session session(Player p) {
        return sessions.computeIfAbsent(p.getUniqueId(), k -> new Session(plugin.stats().of(p)));
    }

    public void show(Player p) {
        Session ss = session(p);
        Ui ui = plugin.ui();
        Ui.Session s = ui.begin(ID, true);
        StatBlock base = ss.base, target = ss.target();
        int from = base.level(), to = target.level();
        long cost = plugin.cfg().levelCost.sum(from, to - from);
        long held = plugin.purse().get(p);
        Derived now = plugin.stats().derived(p, base);
        Derived next = plugin.stats().derived(p, target);
        // 왼쪽 열: 레벨 (a → b), 보유 소울 (더한 점의 비용을 뺀 남은 소울), 필요 소울 (다음 한 점), 빈 줄, 능력치 여섯. 엘든 링 레벨업 창과 같다
        long nextPoint = plugin.cfg().levelCost.next(to);
        List<StatSheet.Cell> left = new ArrayList<>();
        left.add(StatSheet.head("table.level", String.valueOf(from), String.valueOf(to)));
        left.add(StatSheet.head("table.held", souls(held), souls(held - cost)));
        left.add(StatSheet.head("table.need", souls(nextPoint)));
        left.add(StatSheet.blankLeft());
        left.addAll(StatSheet.stats(base, target, java.util.Set.of()));
        List<Component> lines = StatSheet.lines(p, left, StatSheet.derived(p, now, to == from ? null : next, false));
        List<ActionButton> buttons = new ArrayList<>();
        // 다음 한 점을 살 수 있나 (모자라면 "+" 를 흐리게, 설명 칸에 "소울이 모자라다")
        boolean afford = plugin.cfg().levelCost.sum(from, to - from + 1) <= held;
        for (String id : StatBlock.IDS) {
            boolean can = afford && target.get(id) < plugin.cfg().stats.max;
            Component label = Component.text()
                    .append(Lang.c(p, "stat." + id + ".name")) // lang-dyn: stat.*.name
                    .append(Component.text(" +").color(can ? Columns.MAIN_COLOR : Columns.DIM_COLOR))
                    .build();
            buttons.add(ui.button(s, "plus_" + id, label, tip(p, id, target, afford), PLUS_WIDTH, (pl, v) -> plus(pl, id)));
        }
        buttons.add(ui.button(s, "undo", Lang.c(p, "levelup.undo"), null, ACTION_WIDTH, (pl, v) -> undo(pl)));
        buttons.add(ui.button(s, "confirm", Lang.c(p, "levelup.confirm"), null, ACTION_WIDTH, (pl, v) -> confirm(pl)));
        ActionButton cancel = ui.button(s, "exit", Lang.c(p, "levelup.cancel"), null, 200, (pl, v) -> cancel(pl));
        Dialog d = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(Glyphs.dialogTitle(Lang.c(p, "levelup.title")))
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.NONE)
                        .body(List.of(DialogBody.plainMessage(Columns.lines(lines), StatSheet.WIDTH)))
                        .build())
                // 여섯 열: 능력치 단추가 한 줄, 남은 둘 (되돌린다·올린다) 은 바닐라가 다음 줄 가운데에 놓는다
                .type(DialogType.multiAction(buttons).exitAction(cancel).columns(StatBlock.IDS.size()).build()));
        ui.show(p, s, d);
    }

    /**
     * "+" 단추의 설명 칸: 그 능력치의 두 효과를 한 점 더했을 때의 값 (근력의 둘째 줄은 "장비 중량 4.5 / 40.0 → 41.4", 무게 단계가 바뀌면
     * 셋째 줄 "보통 → 가벼움"), (정신력·지력) 아직 듣지 않는 값, (지력) 불에 타는 시간 (달라질 때만), 모자라면 "소울이 모자라다". 다음 한
     * 점의 비용은 표의 필요 소울에 있다.
     */
    private Component tip(Player p, String id, StatBlock target, boolean afford) {
        Derived a = plugin.stats().derived(p, target);
        Derived b = plugin.stats().derived(p, target.plus(id, 1));
        int row = StatRows.rowOf(id);
        String[] k = StatRows.keys(row, b), va = StatRows.values(row, a), vb = StatRows.values(row, b);
        String[] fa = StatRows.fine(row, a), fb = StatRows.fine(row, b);
        Component first = Lang.c(p, k[0]); // lang-dyn: derived.*
        Component second = Lang.c(p, k[1]); // lang-dyn: derived.*
        List<Component> out = new ArrayList<>();
        String secondv = step(va[1], vb[1], fa[1], fb[1]);
        // 근력: 장비 중량은 "장비 무게 / 한도" 로 (한 점은 한도만 올린다)
        if ("str".equals(id)) secondv = String.format(Locale.ROOT, "%.1f", a.weight()) + " / " + secondv;
        out.add(Lang.c(p, "levelup.tip", "first", first, "firstv", step(va[0], vb[0], fa[0], fb[0]), "second", second, "secondv", secondv));
        if ("str".equals(id) && !a.tier().id().equals(b.tier().id())) {
            Component ta = Lang.c(p, "load." + a.tier().id()), tb = Lang.c(p, "load." + b.tier().id()); // lang-dyn: load.*
            out.add(Lang.c(p, "levelup.load-change", "from", ta, "to", tb));
        }
        if (StatRows.later(row, 0)) out.add(Lang.c(p, "levelup.later", "what", first));
        if ("int".equals(id) && !burn(a.ailment()).equals(burn(b.ailment()))) {
            out.add(Lang.c(p, "levelup.burn", "from", burn(a.ailment()), "to", burn(b.ailment())));
        }
        if (!afford) out.add(Lang.c(p, "levelup.short"));
        return Columns.lines(out);
    }

    /** 설명 칸의 한 값: 한 점으로 달라지면 "51 → 52", 반올림으로 그대로면 "52" 하나 ("52 → 52" 는 고장처럼 읽힌다). */
    static String step(String now, String next) {
        return now.equals(next) ? now : now + " → " + next;
    }

    /**
     * 설명 칸의 한 값 (한 자리 더 본다): 보이는 값이 달라지면 "51 → 52". 반올림한 값은 그대로인데 실제로는 오르면 한 자리 더 ("95.3 → 95.6",
     * "+22.4% → +22.6%": 무른 상한 위의 한 점도 무엇을 주는지 보이게, 검토 softcap-dead-points). 정말 그대로면 하나.
     */
    static String step(String now, String next, String fineNow, String fineNext) {
        if (!now.equals(next)) return now + " → " + next;
        return fineNow.equals(fineNext) ? now : fineNow + " → " + fineNext;
    }

    /** 불에 타는 3초가 저항으로 몇 초가 되나 ("2.5"). */
    public static String burn(double resist) {
        return String.format(Locale.ROOT, "%.1f", 3.0 * (1 - resist));
    }

    private void plus(Player p, String id) {
        Session ss = session(p);
        StatBlock target = ss.target();
        if (target.get(id) >= plugin.cfg().stats.max) {
            plugin.test(p, "LEVELUP_PLUS_DENY why=max stat=" + id);
            show(p);
            return;
        }
        int from = ss.base.level();
        long need = plugin.cfg().levelCost.sum(from, target.level() - from + 1);
        if (need > plugin.purse().get(p)) {
            plugin.test(p, "LEVELUP_PLUS_DENY why=souls need=" + need + " souls=" + plugin.purse().get(p));
            Fx.sound(p.getLocation(), "block.note_block.basedrum", 0.5f, 0.6f);
            show(p);
            return;
        }
        ss.added.addLast(id);
        plugin.test(p, "LEVELUP_PLUS stat=" + id + " pending=" + ss.added.size() + " cost=" + need);
        show(p);
    }

    private void undo(Player p) {
        Session ss = session(p);
        if (!ss.added.isEmpty()) ss.added.removeLast();
        plugin.test(p, "LEVELUP_UNDO pending=" + ss.added.size());
        show(p);
    }

    /** 올린다. 시험 명령도 부른다. */
    public void confirm(Player p) {
        Session ss = session(p);
        StatBlock base = ss.base, target = ss.target();
        int from = base.level(), to = target.level();
        if (to == from) {
            show(p);
            return;
        }
        long cost = plugin.cfg().levelCost.sum(from, to - from);
        Profile pr = plugin.profiles().of(p);
        if (!pr.stats().equals(base) || !plugin.purse().spend(p, cost)) {
            plugin.test(p, "LEVELUP_DENY why=" + (pr.stats().equals(base) ? "souls" : "changed") + " cost=" + cost + " souls=" + pr.souls());
            ss.base = pr.stats();
            ss.added.clear();
            show(p);
            return;
        }
        double stBefore = plugin.stamina().max(p);
        pr.setStats(target);
        plugin.attributes().apply(p);
        plugin.load().refresh(p);
        plugin.stamina().grow(p, stBefore);
        plugin.profiles().save(p, true);
        var c = plugin.cfg().levelup;
        Fx.sound(p.getLocation(), c.sound(), c.volume(), c.pitch());
        plugin.test(p, "LEVELUP from=" + from + " to=" + to + " cost=" + cost + " souls=" + pr.souls() + " stats=" + target.line());
        ss.base = target;
        ss.added.clear();
        plugin.hud().invalidate(p);
        show(p);
    }

    /** 그만둔다 (Esc): 더한 점을 버리고 휴식 창으로. */
    public void cancel(Player p) {
        sessions.remove(p.getUniqueId());
        plugin.test(p, "LEVELUP cancel");
        RestMenu.show(plugin, p);
    }

    /** 시험 명령: 능력치에 n 점 더하기 (음수면 되돌리기). */
    public void add(Player p, String id, int n) {
        for (int i = 0; i < Math.abs(n); i++) {
            if (n > 0) plus(p, id);
            else undo(p);
        }
    }

    public void discard(Player p) {
        sessions.remove(p.getUniqueId());
    }

    static String souls(long n) {
        return NumberFormat.getIntegerInstance(Locale.US).format(n);
    }

    /** 쉬는 중에 맞으면 창을 닫고 더한 점을 버린다 (4.1). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof Player p) || e.getFinalDamage() <= 0) return;
        if (sessions.remove(p.getUniqueId()) != null || RestMenu.ID.equals(plugin.ui().openDialog(p))) {
            plugin.ui().close(p);
            plugin.test(p, "REST interrupted t=" + plugin.ticker().now());
        }
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        sessions.remove(e.getPlayer().getUniqueId());
    }
}
