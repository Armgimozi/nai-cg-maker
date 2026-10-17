package kr.labyrinth.mine;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.command.CommandSender;

/**
 * 명령: {@code /미궁 광산} ({@code /lab mine}) · {@code /labadmin mine selftest|stats <이름>|rebuild [층]|test [층]|info}.
 * test = 손님 없이 광산을 시험하는 콘솔 고리 (캐기·공유 빈 광맥·사람 수 재생·가방 가득·약한 곡괭이·곡괭이 구성요소).
 */
final class MineCommands {

    private final MineModule module;

    MineCommands(MineModule module) { this.module = module; }

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    void register(CommandService cmd) {
        for (String name : new String[] {"광산", "mine"}) {
            cmd.addSubcommand("lab", Commands.literal(name).executes(ctx -> run(ctx,
                    () -> CommandService.withPlayer(CommandService.sender(ctx), module::openMine))));
        }
        LiteralArgumentBuilder<CommandSourceStack> m = Commands.literal("mine");
        m.executes(ctx -> run(ctx, () -> help(ctx.getSource().getSender())));
        m.then(Commands.literal("selftest").executes(ctx -> run(ctx, () -> new MineSelfTest(module).run(ctx.getSource().getSender()))));
        m.then(Commands.literal("info").executes(ctx -> run(ctx, () -> info(ctx.getSource().getSender()))));
        m.then(Commands.literal("stats").then(Commands.argument("name", StringArgumentType.word())
                .executes(ctx -> run(ctx, () -> stats(ctx.getSource().getSender(), StringArgumentType.getString(ctx, "name"))))));
        m.then(Commands.literal("rebuild")
                .executes(ctx -> run(ctx, () -> rebuild(ctx.getSource().getSender(), 0)))
                .then(Commands.argument("level", IntegerArgumentType.integer(1, 6))
                        .executes(ctx -> run(ctx, () -> rebuild(ctx.getSource().getSender(), IntegerArgumentType.getInteger(ctx, "level"))))));
        m.then(Commands.literal("test")
                .executes(ctx -> run(ctx, () -> new MineTestHook(module).run(ctx.getSource().getSender(), 0)))
                .then(Commands.argument("level", IntegerArgumentType.integer(1, 6))
                        .executes(ctx -> run(ctx, () -> new MineTestHook(module).run(ctx.getSource().getSender(),
                                IntegerArgumentType.getInteger(ctx, "level"))))));
        cmd.addSubcommand("labadmin", m);
    }

    private void help(CommandSender s) {
        Text.send(s, "<gray>/labadmin mine <white>selftest</white> · <white>info</white> · <white>stats <이름></white> · "
                + "<white>rebuild [층]</white> · <white>test [층]</white>");
    }

    private boolean needActive(CommandSender s) {
        if (module.active()) return true;
        Text.error(s, "광산이 꺼져 있습니다 (config mine.enabled · content/mine.yml).");
        return false;
    }

    private void info(CommandSender s) {
        if (!needActive(s)) return;
        MineConfig c = module.config();
        Text.send(s, "<#e8c58a>광산</#e8c58a> <gray>월드 <white>" + c.world() + "</white> · 층 <white>" + module.levels().size()
                + "</white> · 광맥 <white>" + module.veins().total() + "</white> · 지금 빈 광맥 <white>" + module.veins().state().count()
                + "</white> · 광산 사람 <white>" + module.veins().miners() + "</white> · 다시 차는 빠르기 ×"
                + MineMath.regrowFactor(module.veins().miners(), c.regenPlayersCap()) + " (최대 ×" + c.regenPlayersCap() + ")");
        for (MineLevel l : module.levels()) {
            int[] st = module.veins().status(l);
            Text.send(s, "<gray> " + l.coloredName() + " <gray>광맥 " + st[0] + "/" + st[1] + " · 보석 " + st[2] + "/" + st[3]
                    + " · 재생 " + c.regenMinutes().get(l.n - 1) + "분 · " + (module.ready(l.n) ? "<green>준비" : "<yellow>짓는 중"));
        }
        Text.send(s, "<gray> PvP: " + (module.pvpEnabled() ? "<white>켬</white> · " + Text.escape(module.pvpSummary())
                : "끔 (" + (c.pvp().enabled() ? "pvp.enabled 끔" : "mine.pvp.enabled: false") + " — 광산 안 피해 없음)"));
        MineLinks.District d = MineLinks.district();
        Text.send(s, "<gray> 광산 마을: " + (d == null ? "없음 (관리소로 그대로 됨)" : "있음 · 승강기 " + d.lifts().size() + "칸")
                + " · /미궁 광산 " + (c.teleportAllowed(module.services().plugin().getConfig().getBoolean("village.teleport_command", true))
                ? "켬" : "끔") + " (" + c.teleportCommand().id() + ")");
    }

    private void stats(CommandSender s, String name) {
        OfflinePlayer op = Bukkit.getPlayerExact(name);
        if (op == null) op = Bukkit.getOfflinePlayerIfCached(name);
        if (op == null) {
            Text.error(s, "그 이름의 플레이어를 찾지 못했습니다: " + Text.escape(name));
            return;
        }
        MineStats.Entry e = module.stats().get(op.getUniqueId());
        if (e == null) {
            Text.send(s, "<gray>" + Text.escape(name) + " — 서버가 켜진 뒤 캔 블록 없음");
            return;
        }
        StringBuilder sb = new StringBuilder();
        for (MineLevel l : module.levels()) {
            if (e.perLevel[l.n] > 0) sb.append(sb.isEmpty() ? "" : " · ").append(Text.escape(l.def.name())).append(' ').append(e.perLevel[l.n]);
        }
        Text.send(s, "<gray>" + Text.escape(name) + " — 서버가 켜진 뒤 <white>" + e.total + "</white>블록 (최근 1시간 <white>"
                + module.stats().lastHour(e) + "</white>) · " + (sb.isEmpty() ? "-" : sb));
    }

    private void rebuild(CommandSender s, int level) {
        if (!needActive(s)) return;
        Text.send(s, "<gray>광산 " + (level == 0 ? "모든 층" : level + "층") + " 다시 짓기를 시작합니다.");
        module.veins().refillAll();
        module.startBuild(level, s);
    }
}
