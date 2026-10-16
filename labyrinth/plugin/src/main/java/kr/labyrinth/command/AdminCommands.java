package kr.labyrinth.command;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.LongArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.builder.RequiredArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import java.util.Locale;
import kr.labyrinth.Services;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.DerivedStats;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

/**
 * core 관리 명령 (/labadmin = /미궁관리, 권한 labyrinth.admin):
 * reload · give &lt;아이템&gt; [개수] [플레이어] · setup|difficulty &lt;난이도&gt; · level|xp|gold|points &lt;플레이어&gt; &lt;값&gt; ·
 * info [플레이어] · pack. 다른 모듈은 {@code addSubcommand("labadmin", ...)} 로 spawnmob 등을 붙인다.
 */
final class AdminCommands {

    private final Services services;

    AdminCommands(Services services) { this.services = services; }

    static void help(CommandSender s) {
        s.sendMessage(Text.mm("<gradient:#c9a2ff:#7fd8ff><b>미궁 라비린스 관리</b></gradient>"));
        s.sendMessage(Text.mm("<gray>/labadmin reload <dark_gray>— 설정·콘텐츠 다시 읽기"));
        s.sendMessage(Text.mm("<gray>/labadmin setup <난이도> <dark_gray>— 초기 설정 (easy/normal/hard/nightmare)"));
        s.sendMessage(Text.mm("<gray>/labadmin difficulty <난이도> <dark_gray>— 서버 난이도 변경"));
        s.sendMessage(Text.mm("<gray>/labadmin give <아이템> [개수] [플레이어]"));
        s.sendMessage(Text.mm("<gray>/labadmin level|xp|gold|points <플레이어> <값>"));
        s.sendMessage(Text.mm("<gray>/labadmin setclass <플레이어> <직업|none> <dark_gray>— 직업 바로 바꾸기 (두루마리·대기 시간 없이)"));
        s.sendMessage(Text.mm("<gray>/labadmin info [플레이어] <dark_gray>— 능력치 확인"));
        s.sendMessage(Text.mm("<gray>/labadmin pack <dark_gray>— 리소스팩 상태·재전송"));
    }

    private static LiteralArgumentBuilder<CommandSourceStack> lit(String name) {
        return Commands.literal(name);
    }

    private SuggestionProvider<CommandSourceStack> players() {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            for (Player p : Bukkit.getOnlinePlayers()) if (p.getName().toLowerCase(Locale.ROOT).startsWith(rem)) b.suggest(p.getName());
            return b.buildFuture();
        };
    }

    private SuggestionProvider<CommandSourceStack> items() {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            int n = 0;
            for (String id : services.content().items().keySet()) {
                if (id.startsWith(rem) || (rem.length() >= 2 && id.contains(rem))) {
                    b.suggest(id);
                    if (++n >= 60) break;
                }
            }
            return b.buildFuture();
        };
    }

    private SuggestionProvider<CommandSourceStack> difficulties() {
        return (c, b) -> {
            services.settings().difficulties().keySet().forEach(b::suggest);
            return b.buildFuture();
        };
    }

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    void register(CommandService cmd) {
        cmd.addSubcommand("labadmin", lit("reload").executes(ctx -> run(ctx, () -> reload(ctx.getSource().getSender()))));

        cmd.addSubcommand("labadmin", lit("give")
                .then(Commands.argument("item", StringArgumentType.word()).suggests(items())
                        .executes(ctx -> run(ctx, () -> give(ctx, 1, null)))
                        .then(Commands.argument("amount", IntegerArgumentType.integer(1, 2304))
                                .executes(ctx -> run(ctx, () -> give(ctx, IntegerArgumentType.getInteger(ctx, "amount"), null)))
                                .then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                                        .executes(ctx -> run(ctx, () -> give(ctx, IntegerArgumentType.getInteger(ctx, "amount"),
                                                StringArgumentType.getString(ctx, "player"))))))));

        for (String name : new String[] {"setup", "difficulty"}) {
            cmd.addSubcommand("labadmin", lit(name)
                    .executes(ctx -> run(ctx, () -> {
                        CommandSender s = ctx.getSource().getSender();
                        Text.send(s, "<gray>현재 서버 난이도: <white>" + (services.settings().isDifficultySet()
                                ? services.settings().difficulty().name() : "미설정"));
                        if (kr.labyrinth.core.ServerSetup.lockedDifficulty() != null)
                            Text.send(s, "<dark_gray>한 번 정한 난이도는 바꿀 수 없습니다."
                                    + (s instanceof Player ? "" : " (꼭 바꿔야 하면 labadmin difficulty unlock)"));
                        else if (s instanceof Player p) services.menus().openSetup(p);
                    }))
                    .then(Commands.argument("difficulty", StringArgumentType.word()).suggests(difficulties())
                            .executes(ctx -> run(ctx, () -> setDifficulty(ctx.getSource().getSender(),
                                    StringArgumentType.getString(ctx, "difficulty"))))));
        }

        cmd.addSubcommand("labadmin", playerValue("level", 1, 50, (p, v) -> {
            services.levels().setLevel(p, (int) (long) v);
            return "레벨 " + services.data().get(p).level();
        }));
        cmd.addSubcommand("labadmin", playerValue("xp", 1, 100_000_000L, (p, v) -> {
            services.levels().addXp(p, v);
            return "경험치 +" + Text.num(v);
        }));
        cmd.addSubcommand("labadmin", playerValue("gold", 0, 1_000_000_000L, (p, v) -> {
            services.data().get(p).gold(v);
            return "골드 " + Text.num(v);
        }));
        cmd.addSubcommand("labadmin", playerValue("points", 0, 10_000L, (p, v) -> {
            services.data().get(p).statPoints((int) (long) v);
            return "스탯 포인트 " + v;
        }));

        cmd.addSubcommand("labadmin", lit("info")
                .executes(ctx -> run(ctx, () -> CommandService.withPlayer(ctx.getSource().getSender(), p -> info(p, p))))
                .then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                        .executes(ctx -> run(ctx, () -> {
                            Player t = Bukkit.getPlayerExact(StringArgumentType.getString(ctx, "player"));
                            if (t == null) Text.error(ctx.getSource().getSender(), "접속 중인 플레이어가 아닙니다.");
                            else info(ctx.getSource().getSender(), t);
                        }))));

        cmd.addSubcommand("labadmin", lit("pack").executes(ctx -> run(ctx, () -> {
            CommandSender s = ctx.getSource().getSender();
            var pack = services.pack();
            // 0.3.6.1: 방식마다 쓰는 주소 (내장 · pack.url · 공개 사본) — PackService.describe
            for (String line : pack.describe(s instanceof Player pl ? pl : null)) Text.send(s, line);
            if (s instanceof Player p && pack.isAvailable()) {
                Text.send(s, "<gray>지금 보내는 주소: <white>" + Text.escape(pack.sendUrlFor(p)));
                pack.send(p);
            }
        })));
    }

    @FunctionalInterface
    private interface PlayerSetter {
        String apply(Player p, Long value);
    }

    private LiteralArgumentBuilder<CommandSourceStack> playerValue(String name, long min, long max, PlayerSetter setter) {
        RequiredArgumentBuilder<CommandSourceStack, String> player = Commands.argument("player", StringArgumentType.word()).suggests(players());
        player.then(Commands.argument("value", LongArgumentType.longArg(min, max)).executes(ctx -> run(ctx, () -> {
            CommandSender s = ctx.getSource().getSender();
            Player t = Bukkit.getPlayerExact(StringArgumentType.getString(ctx, "player"));
            if (t == null) {
                Text.error(s, "접속 중인 플레이어가 아닙니다.");
                return;
            }
            String result = setter.apply(t, LongArgumentType.getLong(ctx, "value"));
            services.stats().recalc(t);
            Text.send(s, "<white>" + t.getName() + "</white> <gray>→ " + Text.escape(result));
        })));
        return lit(name).then(player);
    }

    private void reload(CommandSender s) {
        long t0 = System.currentTimeMillis();
        var report = services.reload();
        Text.send(s, "<green>다시 읽기 완료</green> <gray>(" + (System.currentTimeMillis() - t0) + "ms) "
                + Text.escape(services.content().summary()));
        if (!report.errors().isEmpty() || !report.warnings().isEmpty()) {
            Text.send(s, "<yellow>콘텐츠 검사: 오류 " + report.errors().size() + " · 경고 " + report.warnings().size()
                    + " <gray>(자세한 내용은 콘솔)");
            int n = 0;
            for (String e : report.errors()) {
                if (n++ >= 8) break;
                s.sendMessage(Text.mm("<red> - " + Text.escape(e)));
            }
        }
    }

    private void give(CommandContext<CommandSourceStack> ctx, int amount, String playerName) {
        CommandSender s = ctx.getSource().getSender();
        String id = StringArgumentType.getString(ctx, "item");
        Player target = playerName != null ? Bukkit.getPlayerExact(playerName)
                : CommandService.sender(ctx) instanceof Player p ? p : null;
        if (target == null) {
            Text.error(s, "대상 플레이어를 찾을 수 없습니다.");
            return;
        }
        if (services.content().item(id) == null) {
            Text.error(s, "없는 아이템: " + Text.escape(id));
            return;
        }
        int given = services.items().give(target, id, amount, "admin");
        Text.send(s, "<white>" + target.getName() + "</white><gray>에게 </gray>" + services.content().item(id).name()
                + " <gray>×" + given + " 지급");
    }

    private void setDifficulty(CommandSender s, String id) {
        kr.labyrinth.core.ServerSetup.applyDifficulty(s, id);
    }

    private void info(CommandSender s, Player t) {
        PlayerData d = services.data().get(t);
        DerivedStats st = services.stats().get(t);
        var cls = services.classes().classOf(t);
        s.sendMessage(Text.mm("<gold><b>" + t.getName() + "</b></gold> <gray>Lv." + d.level() + " ("
                + Text.num(d.xp()) + "/" + Text.num(services.levels().curve().xpToNext(d.level())) + ") · 직업 "
                + (cls == null ? "없음" : cls.name()) + " · 골드 " + Text.num(d.gold()) + " · 해금 " + d.unlockedFloor() + "층"));
        s.sendMessage(Text.mm("<gray>HP " + Text.num(services.stats().currentHp(t)) + "/" + Text.num(st.maxHp())
                + " · MP " + Text.num(services.classes().mana(t)) + "/" + Text.num(st.maxMp()) + " · 공격력 "
                + Text.num(st.attackPower()) + " · 방어 " + Text.num(st.defense()) + " · 치명 " + Text.pct(st.critChance())));
    }
}
