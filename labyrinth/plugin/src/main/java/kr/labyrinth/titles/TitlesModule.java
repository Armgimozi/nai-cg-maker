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
 * 관리: /labadmin title grant|revoke &lt;플레이어&gt; &lt;id&gt; · /labadmin title recheck [플레이어].
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
                .then(Commands.literal("grant").then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                        .then(Commands.argument("id", StringArgumentType.word()).suggests(allIds())
                                .executes(ctx -> run(ctx, () -> admin(ctx, true))))))
                .then(Commands.literal("revoke").then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                        .then(Commands.argument("id", StringArgumentType.word()).suggests(allIds())
                                .executes(ctx -> run(ctx, () -> admin(ctx, false))))))
                .then(Commands.literal("recheck")
                        .executes(ctx -> run(ctx, () -> {
                            Bukkit.getOnlinePlayers().forEach(services.titles()::recheck);
                            Text.send(ctx.getSource().getSender(), "<green>접속 중인 모든 플레이어의 업적을 다시 검사했습니다.");
                        }))));
    }

    private void equip(Player p, String id) {
        AchievementDef def = services.content().achievements().get(id);
        if (def == null || !services.data().get(p).hasAchievement(id)) {
            Text.error(p, "아직 얻지 못한 칭호입니다.");
            return;
        }
        services.titles().equip(p, id);
        Text.send(p, "<gray>칭호 장착: </gray><title>", Text.ph("title", Text.mm(def.title())));
    }

    private void list(Player p) {
        PlayerData d = services.data().get(p);
        p.sendMessage(Text.mm("<gradient:#c9a2ff:#ffd36b><b>━━━ 내 칭호 ━━━</b></gradient> <gray>" + d.achievements().size()
                + " / " + services.content().achievements().size()));
        for (String id : d.achievements().keySet()) {
            AchievementDef def = services.content().achievements().get(id);
            if (def == null) continue;
            boolean eq = id.equals(d.equippedTitle());
            p.sendMessage(Text.mm(" <click:run_command:'/title equip " + id + "'><hover:show_text:'<gray>클릭하여 장착'>"
                    + (eq ? "<#ffd36b>▶ </#ffd36b>" : "<dark_gray>· </dark_gray>") + def.title() + "</hover></click> <dark_gray>— "
                    + Text.escape(def.description())));
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
            Text.error(s, "없는 업적: " + Text.escape(id));
            return;
        }
        if (grant) {
            boolean ok = services.titles().grant(t, id);
            Text.send(s, ok ? "<green>지급했습니다." : "<gray>이미 가지고 있습니다.");
        } else {
            PlayerData d = services.data().get(t);
            d.revokeAchievement(id);
            if (id.equals(d.equippedTitle())) services.titles().equip(t, null);
            Text.send(s, "<yellow>회수했습니다.");
        }
    }
}
