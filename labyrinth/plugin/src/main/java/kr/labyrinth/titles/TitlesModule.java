package kr.labyrinth.titles;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import java.util.Locale;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.data.ServerRecords;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

/**
 * ui+titles 담당 모듈 진입점 — 업적 판정·칭호 장착·서버 최초 기록 ({@link LabTitleService}).
 * 명령: /칭호 (메뉴) · /칭호 장착|equip &lt;id&gt; · /칭호 해제|unequip · /칭호 목록|list · /칭호 기록|records,
 * 관리: /labadmin title list (조건까지 보임 — 관리자 전용) · grant|revoke &lt;플레이어&gt; &lt;id&gt; · free &lt;id&gt; · recheck.
 */
public final class TitlesModule implements Module {

    private final Services services;
    private LabTitleService impl;

    public TitlesModule(Services services) { this.services = services; }

    @Override
    public String name() { return "titles"; }

    @Override
    public void enable() {
        impl = new LabTitleService(services);
        services.setTitles(impl);
        impl.enable();
        registerCommands();
    }

    @Override
    public void disable() {
        if (impl != null) impl.disable();
    }

    @Override
    public void reload() {
        if (impl != null) impl.reload();
    }

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    private SuggestionProvider<CommandSourceStack> owned() {
        return (c, b) -> {
            if (c.getSource().getSender() instanceof Player p) {
                String rem = b.getRemainingLowerCase();
                for (String id : services.data().get(p).achievements().keySet()) if (id.startsWith(rem)) b.suggest(id);
            }
            return b.buildFuture();
        };
    }

    private SuggestionProvider<CommandSourceStack> allIds() {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            for (String id : services.content().achievements().keySet()) if (id.startsWith(rem)) b.suggest(id);
            return b.buildFuture();
        };
    }

    private SuggestionProvider<CommandSourceStack> players() {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            for (Player p : Bukkit.getOnlinePlayers()) if (p.getName().toLowerCase(Locale.ROOT).startsWith(rem)) b.suggest(p.getName());
            return b.buildFuture();
        };
    }

    private void registerCommands() {
        CommandService cmd = services.commands();
        for (String n : new String[] {"equip", "장착"}) {
            cmd.addSubcommand("title", Commands.literal(n).then(Commands.argument("id", StringArgumentType.word()).suggests(owned())
                    .executes(ctx -> run(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx),
                            p -> equip(p, StringArgumentType.getString(ctx, "id")))))));
        }
        for (String n : new String[] {"unequip", "해제"}) {
            cmd.addSubcommand("title", Commands.literal(n).executes(ctx -> run(ctx, () -> CommandService.withPlayer(
                    CommandService.sender(ctx), p -> {
                        services.titles().equip(p, null);
                        Text.send(p, "<gray>칭호를 해제했습니다.");
                    }))));
        }
        for (String n : new String[] {"list", "목록"}) {
            cmd.addSubcommand("title", Commands.literal(n).executes(ctx -> run(ctx, () -> CommandService.withPlayer(
                    CommandService.sender(ctx), this::list))));
        }
        for (String n : new String[] {"records", "기록"}) {
            cmd.addSubcommand("title", Commands.literal(n).executes(ctx -> run(ctx, () -> records(ctx.getSource().getSender()))));
        }
        cmd.addSubcommand("labadmin", Commands.literal("title")
                .then(Commands.literal("list").executes(ctx -> run(ctx, () -> adminList(ctx.getSource().getSender()))))
                .then(Commands.literal("grant").then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                        .then(Commands.argument("id", StringArgumentType.word()).suggests(allIds())
                                .executes(ctx -> run(ctx, () -> admin(ctx, true))))))
                .then(Commands.literal("revoke").then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                        .then(Commands.argument("id", StringArgumentType.word()).suggests(allIds())
                                .executes(ctx -> run(ctx, () -> admin(ctx, false))))))
                .then(Commands.literal("free").then(Commands.argument("id", StringArgumentType.word()).suggests(allIds())
                        .executes(ctx -> run(ctx, () -> {
                            String id = StringArgumentType.getString(ctx, "id");
                            boolean ok = impl != null && impl.free(id);
                            Text.send(ctx.getSource().getSender(), ok ? "<yellow>주인 기록을 지웠습니다. 다시 누구나 얻을 수 있습니다."
                                    : "<gray>주인이 없는 칭호입니다.");
                        }))))
                .then(Commands.literal("recheck")
                        .executes(ctx -> run(ctx, () -> {
                            Bukkit.getOnlinePlayers().forEach(services.titles()::recheck);
                            Text.send(ctx.getSource().getSender(), "<green>접속 중인 모든 플레이어의 칭호를 주인 기록과 맞췄습니다.");
                        }))));
    }

    private void equip(Player p, String id) {
        AchievementDef def = services.content().achievements().get(id);
        if (def == null || !services.data().get(p).hasAchievement(id)) {
            Text.error(p, "내 칭호가 아닙니다.");
            return;
        }
        services.titles().equip(p, id);
        Text.send(p, "<gray>칭호 장착: </gray><title>", Text.ph("title", Text.mm(def.title())));
    }

    private void list(Player p) {
        PlayerData d = services.data().get(p);
        int owned = 0;
        for (String id : services.content().achievements().keySet()) if (impl != null && impl.owner(id) != null) owned++;
        p.sendMessage(Text.mm("<gradient:#c9a2ff:#ffd36b><b>━━━ 칭호 ━━━</b></gradient> <gray>" + services.content().achievements().size()
                + "개 · 주인 있음 " + owned + " · 칭호마다 단 한 명"));
        for (AchievementDef def : services.content().achievements().values()) {
            boolean mine = d.hasAchievement(def.id());
            String line = TitleView.listLine(def, impl == null ? null : impl.owner(def.id()), mine, services.content());
            if (mine) line = "<click:run_command:'/title equip " + def.id() + "'><hover:show_text:'<gray>클릭하여 장착'>" + line + "</hover></click>";
            p.sendMessage(Text.mm(line));
        }
    }

    /** 관리자 전용: 조건까지 전부 (플레이어에게는 주인이 생기기 전까지 비밀). */
    private void adminList(CommandSender s) {
        s.sendMessage(Text.mm("<gold><b>━━━ 칭호 (관리자 — 조건 포함) ━━━</b></gold>"));
        for (AchievementDef def : services.content().achievements().values()) {
            TitleView.Owner o = impl == null ? null : impl.owner(def.id());
            s.sendMessage(Text.mm(" <white>" + def.id() + "</white> " + def.title() + " <gray>— "
                    + Text.escape(AchievementRules.conditionText(def, services.content())) + " <dark_gray>· "
                    + (o == null ? "주인 없음" : "주인 " + Text.escape(o.name()))));
        }
    }

    private void records(CommandSender s) {
        s.sendMessage(Text.mm("<gradient:#ffd36b:#ff8a3d><b>━━━ 서버 최초 기록 ━━━</b></gradient>"));
        int max = Math.max(10, services.content().maxFloor());
        boolean any = false;
        for (int f = 1; f <= max; f++) {
            ServerRecords.Record r = services.records().get("first_clear.floor_" + f).orElse(null);
            if (r == null) continue;
            any = true;
            s.sendMessage(Text.mm("<gold>지하 " + f + "층</gold> <white>" + Text.escape(String.join(", ", r.names())) + "</white> <dark_gray>— "
                    + new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm").format(new java.util.Date(r.time()))));
        }
        if (!any) s.sendMessage(Text.mm("<gray>아직 아무도 미궁의 층을 돌파하지 못했습니다. 첫 기록의 주인공이 되어 보세요!"));
    }

    private void admin(CommandContext<CommandSourceStack> ctx, boolean grant) {
        CommandSender s = ctx.getSource().getSender();
        Player t = Bukkit.getPlayerExact(StringArgumentType.getString(ctx, "player"));
        String id = StringArgumentType.getString(ctx, "id");
        if (t == null) {
            Text.error(s, "접속 중인 플레이어가 아닙니다.");
            return;
        }
        if (services.content().achievements().get(id) == null) {
            Text.error(s, "없는 칭호: " + Text.escape(id));
            return;
        }
        if (grant) {
            TitleView.Owner o = impl == null ? null : impl.owner(id);
            if (o != null) {
                Text.error(s, "이미 주인이 있습니다: " + Text.escape(o.name()) + " — 먼저 /labadmin title free " + Text.escape(id));
                return;
            }
            boolean ok = services.titles().grant(t, id);
            Text.send(s, ok ? "<green>지급했습니다 (이 칭호의 주인이 됨)." : "<gray>지급하지 못했습니다.");
        } else {
            PlayerData d = services.data().get(t);
            if (impl != null && services.records().get(TitleView.recordKey(id))
                    .map(r -> r.players().contains(t.getUniqueId())).orElse(false)) {
                impl.free(id);
            }
            d.revokeAchievement(id);
            if (id.equals(d.equippedTitle())) services.titles().equip(t, null);
            Text.send(s, "<yellow>회수했습니다.");
        }
    }
}
