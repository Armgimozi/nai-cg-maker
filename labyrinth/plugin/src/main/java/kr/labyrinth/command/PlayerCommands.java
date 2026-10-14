package kr.labyrinth.command;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import io.papermc.paper.command.brigadier.Commands;
import kr.labyrinth.Services;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.Stat;

/**
 * core 가 직접 붙이는 플레이어 하위 명령:
 * <ul>
 *   <li>/미궁 입장 [층] (enter) · /미궁 퇴장 (leave) — DungeonService/MenuService 로 위임</li>
 *   <li>/스탯 add &lt;스탯&gt; [양] (분배, 별칭 '투자')</li>
 * </ul>
 */
final class PlayerCommands {

    private final Services services;

    PlayerCommands(Services services) { this.services = services; }

    void register(CommandService cmd) {
        for (String enter : new String[] {"enter", "입장"}) {
            cmd.addSubcommand("lab", Commands.literal(enter)
                    .executes(ctx -> {
                        CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx),
                                p -> services.menus().openEntrance(p)));
                        return Command.SINGLE_SUCCESS;
                    })
                    .then(Commands.argument("floor", IntegerArgumentType.integer(1, 10)).executes(ctx -> {
                        int floor = IntegerArgumentType.getInteger(ctx, "floor");
                        CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx),
                                p -> services.dungeon().enter(p, floor)));
                        return Command.SINGLE_SUCCESS;
                    })));
        }
        for (String diff : new String[] {"difficulty", "난이도"}) {
            cmd.addSubcommand("lab", Commands.literal(diff)
                    .executes(ctx -> {
                        CommandService.safeRun(ctx, () -> {
                            var s = CommandService.sender(ctx);
                            kr.labyrinth.core.Text.send(s, "<gray>현재 서버 난이도: <white>" + (services.settings().isDifficultySet()
                                    ? services.settings().difficulty().name() : "미설정"));
                            if (s instanceof org.bukkit.entity.Player p) {
                                if (kr.labyrinth.core.ServerSetup.canSetDifficulty(p)) services.menus().openSetup(p);
                                else kr.labyrinth.core.Text.error(p, "서버 난이도는 관리자만 바꿀 수 있습니다.");
                            }
                        });
                        return Command.SINGLE_SUCCESS;
                    })
                    .then(Commands.argument("id", StringArgumentType.word())
                            .suggests((c, b) -> {
                                services.settings().difficulties().keySet().forEach(b::suggest);
                                return b.buildFuture();
                            })
                            .executes(ctx -> {
                                String id = StringArgumentType.getString(ctx, "id");
                                CommandService.safeRun(ctx, () -> kr.labyrinth.core.ServerSetup.applyDifficulty(CommandService.sender(ctx), id));
                                return Command.SINGLE_SUCCESS;
                            })));
        }
        for (String leave : new String[] {"leave", "퇴장"}) {
            cmd.addSubcommand("lab", Commands.literal(leave).executes(ctx -> {
                CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx),
                        p -> services.dungeon().leave(p)));
                return Command.SINGLE_SUCCESS;
            }));
        }
        for (String add : new String[] {"add", "투자"}) {
            cmd.addSubcommand("stats", Commands.literal(add)
                    .then(Commands.argument("stat", StringArgumentType.word())
                            .suggests((c, b) -> {
                                for (Stat s : Stat.values()) {
                                    if (s.name().startsWith(b.getRemainingLowerCase().toUpperCase()) || s.displayName().startsWith(b.getRemaining())) {
                                        b.suggest(s.name());
                                    }
                                }
                                return b.buildFuture();
                            })
                            .executes(ctx -> allocate(ctx.getSource().getSender(), StringArgumentType.getString(ctx, "stat"), 1, ctx))
                            .then(Commands.argument("amount", IntegerArgumentType.integer(1, 500))
                                    .executes(ctx -> allocate(ctx.getSource().getSender(), StringArgumentType.getString(ctx, "stat"),
                                            IntegerArgumentType.getInteger(ctx, "amount"), ctx)))));
        }
    }

    private int allocate(org.bukkit.command.CommandSender sender, String statKey, int amount,
                         com.mojang.brigadier.context.CommandContext<io.papermc.paper.command.brigadier.CommandSourceStack> ctx) {
        CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), p -> {
            Stat stat = Stat.byKey(statKey);
            if (stat == null) {
                Text.error(p, "알 수 없는 스탯입니다: " + Text.escape(statKey) + " <gray>(STR DEX INT VIT WIS LUK)");
                return;
            }
            PlayerData d = services.data().get(p);
            int n = Math.min(amount, d.statPoints());
            if (n <= 0 || !d.allocate(stat, n)) {
                Text.error(p, "남은 스탯 포인트가 없습니다.");
                return;
            }
            services.stats().recalc(p);
            Text.send(p, "<" + stat.color() + ">" + stat.displayName() + "</" + stat.color() + "> <white>+" + n
                    + "</white> <gray>(남은 포인트 " + d.statPoints() + ")");
            p.playSound(p.getLocation(), org.bukkit.Sound.UI_BUTTON_CLICK, 0.6f, 1.4f);
        }));
        return Command.SINGLE_SUCCESS;
    }
}
