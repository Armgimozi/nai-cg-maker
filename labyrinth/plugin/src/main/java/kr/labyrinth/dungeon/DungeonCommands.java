package kr.labyrinth.dungeon;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import java.util.Locale;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

/**
 * 미궁 명령: /미궁 귀환(return)·정보(info) + 관리자 setentrance [block|npc] · removeentrance · tpfloor &lt;층&gt; ·
 * unlock &lt;플레이어&gt; &lt;층&gt; · instances · endinstance &lt;id&gt;. (입장·퇴장은 core 가 붙임 → DungeonService)
 */
final class DungeonCommands {

    private final Services services;
    private final DungeonManager manager;
    private final EntranceService entrance;

    DungeonCommands(Services services, DungeonManager manager, EntranceService entrance) {
        this.services = services;
        this.manager = manager;
        this.entrance = entrance;
    }

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    void register() {
        CommandService cmd = services.commands();
        for (String name : new String[] {"return", "귀환"}) {
            cmd.addSubcommand("lab", Commands.literal(name).executes(ctx -> run(ctx,
                    () -> CommandService.withPlayer(CommandService.sender(ctx), p -> manager.leave(p)))));
        }
        for (String name : new String[] {"info", "정보"}) {
            cmd.addSubcommand("lab", Commands.literal(name).executes(ctx -> run(ctx,
                    () -> CommandService.withPlayer(CommandService.sender(ctx), this::info))));
        }

        cmd.addSubcommand("labadmin", Commands.literal("setentrance")
                .executes(ctx -> run(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx),
                        p -> Text.send(p, entrance.setEntrance(p, null)))))
                .then(Commands.argument("mode", StringArgumentType.word())
                        .suggests((c, b) -> {
                            b.suggest("block");
                            b.suggest("npc");
                            return b.buildFuture();
                        })
                        .executes(ctx -> run(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx),
                                p -> Text.send(p, entrance.setEntrance(p, StringArgumentType.getString(ctx, "mode"))))))));
        cmd.addSubcommand("labadmin", Commands.literal("removeentrance")
                .executes(ctx -> run(ctx, () -> Text.send(ctx.getSource().getSender(), entrance.removeEntrance()))));

        cmd.addSubcommand("labadmin", Commands.literal("tpfloor")
                .then(Commands.argument("floor", IntegerArgumentType.integer(1, 10))
                        .executes(ctx -> run(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx),
                                p -> manager.adminEnter(p, IntegerArgumentType.getInteger(ctx, "floor")))))));

        cmd.addSubcommand("labadmin", Commands.literal("unlock")
                .then(Commands.argument("player", StringArgumentType.word())
                        .suggests((c, b) -> {
                            String rem = b.getRemainingLowerCase();
                            for (Player p : Bukkit.getOnlinePlayers()) if (p.getName().toLowerCase(Locale.ROOT).startsWith(rem)) b.suggest(p.getName());
                            return b.buildFuture();
                        })
                        .then(Commands.argument("floor", IntegerArgumentType.integer(1, 10))
                                .executes(ctx -> run(ctx, () -> {
                                    CommandSender s = ctx.getSource().getSender();
                                    Player t = Bukkit.getPlayerExact(StringArgumentType.getString(ctx, "player"));
                                    if (t == null) {
                                        Text.error(s, "접속 중인 플레이어가 아닙니다.");
                                        return;
                                    }
                                    int f = Math.min(services.content().maxFloor(), IntegerArgumentType.getInteger(ctx, "floor"));
                                    services.data().get(t).unlockedFloor(f);
                                    Text.send(s, "<white>" + t.getName() + "</white> <gray>해금층 → 지하 " + f + "층");
                                })))));

        cmd.addSubcommand("labadmin", Commands.literal("instances").executes(ctx -> run(ctx, () -> {
            CommandSender s = ctx.getSource().getSender();
            if (manager.runs().isEmpty()) {
                Text.send(s, "<gray>진행 중인 미궁이 없습니다.");
                return;
            }
            Text.send(s, "<gold>진행 중인 미궁 " + manager.runs().size() + "개");
            for (Run r : manager.runs()) s.sendMessage(Text.mm(" <dark_gray>-</dark_gray> " + r.summary()));
        })));

        cmd.addSubcommand("labadmin", Commands.literal("endinstance")
                .then(Commands.argument("id", StringArgumentType.word())
                        .suggests((c, b) -> {
                            for (String id : manager.runMap().keySet()) b.suggest(id);
                            return b.buildFuture();
                        })
                        .executes(ctx -> run(ctx, () -> {
                            String id = StringArgumentType.getString(ctx, "id");
                            manager.endInstance(id);
                            Text.send(ctx.getSource().getSender(), "<gray>종료 요청: " + Text.escape(id));
                        }))));
    }

    private void info(Player p) {
        Run r = manager.runOf(p);
        if (r == null) {
            int u = services.data().get(p).unlockedFloor();
            Text.send(p, "<gray>미궁 밖입니다. 입장 가능: <white>지하 1~" + u + "층</white> · 서버 난이도 <white>"
                    + (services.settings().isDifficultySet() ? services.settings().difficulty().name() : "미설정") + "</white>");
            return;
        }
        Text.send(p, r.summary());
    }
}
