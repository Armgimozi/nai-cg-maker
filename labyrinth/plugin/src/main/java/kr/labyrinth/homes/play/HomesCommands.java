package kr.labyrinth.homes.play;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.ArgumentBuilder;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import java.util.List;
import java.util.function.BiConsumer;
import java.util.function.Supplier;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.HomesConfig;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotInfo;
import kr.labyrinth.homes.PlotRole;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;

/**
 * {@code /미궁 집} ({@code /lab 집}, {@code /lab home}) (0.3.7, plan §6). 일은 {@code HomesApi} (묶음 B), 글·메뉴·이동은 여기.
 * <pre>
 *   (없음)            관리인 메뉴              가기 · go            내 집으로
 *   받기 [번지]  claim 받기 (번지가 없으면 지도)  초대 &lt;이름&gt;   invite
 *   내보내기 &lt;이름&gt; kick                     이름 &lt;글&gt;     name
 *   손님 [켬|끔] guests                      방문 &lt;이름&gt;   visit
 *   짐 · parcel        맡긴 짐                  비우기 [확인] vacate [confirm]
 *   여기 · here        서 있는 집터              도움 · help
 * </pre>
 * 명령은 서버가 켜질 때 한 번 붙인다 — 실행할 때마다 지금 켜진 집 모듈({@code play.get()})을 본다.
 */
public final class HomesCommands {

    private final Supplier<PlayWiring> play;

    public HomesCommands(Supplier<PlayWiring> play) { this.play = play; }

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    /** 플레이어 + 켜진 집 모듈일 때만. */
    private void with(CommandContext<CommandSourceStack> ctx, BiConsumer<Player, PlayUi> action) {
        CommandService.withPlayer(CommandService.sender(ctx), p -> {
            PlayWiring w = play.get();
            PlayUi ui = w == null ? null : w.ui();
            if (ui == null || !w.service().enabled()) {
                Text.error(p, "이 서버에서는 집 기능을 쓰지 않습니다.");
                return;
            }
            action.accept(p, ui);
        });
    }

    public void register(CommandService cmd) {
        for (String root : new String[] {"집", "home"}) {
            LiteralArgumentBuilder<CommandSourceStack> n = Commands.literal(root)
                    .executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> ui.openEstate(p))));
            sub(n, List.of("가기", "go"), (p, ui) -> ui.travel().goHome(p));
            for (String lit : new String[] {"받기", "claim"}) {
                n.then(Commands.literal(lit)
                        .executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> ui.openClaim(p))))
                        .then(Commands.argument("plot", StringArgumentType.greedyString()).suggests(vacantPlots())
                                .executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> claim(p, ui, StringArgumentType.getString(ctx, "plot")))))));
            }
            named(n, List.of("초대", "invite"), (p, ui, name) -> ui.send(p, ui.service().invite(p, name)));
            named(n, List.of("내보내기", "kick"), (p, ui, name) -> ui.send(p, ui.service().kick(p, name)));
            named(n, List.of("방문", "visit"), (p, ui, name) -> ui.travel().visit(p, name));
            for (String lit : new String[] {"이름", "name"}) {
                n.then(Commands.literal(lit)
                        .executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> ui.suggest(p, "/미궁 집 이름 ", "새 이름을 적어 보내세요."))))
                        .then(Commands.argument("text", StringArgumentType.greedyString())
                                .executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> ui.send(p, ui.service().rename(p, StringArgumentType.getString(ctx, "text"))))))));
            }
            for (String lit : new String[] {"손님", "guests"}) {
                LiteralArgumentBuilder<CommandSourceStack> g = Commands.literal(lit)
                        .executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> guests(p, ui, null))));
                for (String on : new String[] {"켬", "on"}) g.then(Commands.literal(on).executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> guests(p, ui, true)))));
                for (String off : new String[] {"끔", "off"}) g.then(Commands.literal(off).executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> guests(p, ui, false)))));
                n.then(g);
            }
            sub(n, List.of("짐", "parcel"), (p, ui) -> ui.openParcel(p));
            for (String lit : new String[] {"비우기", "vacate"}) {
                LiteralArgumentBuilder<CommandSourceStack> v = Commands.literal(lit)
                        .executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> ui.vacateCommand(p, false))));
                for (String c : new String[] {"확인", "confirm"}) v.then(Commands.literal(c).executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> ui.vacateCommand(p, true)))));
                n.then(v);
            }
            sub(n, List.of("여기", "here"), this::here);
            sub(n, List.of("도움", "help"), (p, ui) -> help(p));
            cmd.addSubcommand("lab", n);
        }
    }

    private interface NamedAction {
        void run(Player p, PlayUi ui, String name);
    }

    private void sub(LiteralArgumentBuilder<CommandSourceStack> n, List<String> names, BiConsumer<Player, PlayUi> action) {
        for (String lit : names) n.then(Commands.literal(lit).executes(ctx -> run(ctx, () -> with(ctx, action))));
    }

    private void named(LiteralArgumentBuilder<CommandSourceStack> n, List<String> names, NamedAction action) {
        for (String lit : names) {
            ArgumentBuilder<CommandSourceStack, ?> arg = Commands.argument("player", StringArgumentType.word()).suggests(onlinePlayers())
                    .executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> action.run(p, ui, StringArgumentType.getString(ctx, "player")))));
            n.then(Commands.literal(lit)
                    .executes(ctx -> run(ctx, () -> with(ctx, (p, ui) -> Text.error(p, "이름을 적어 주세요: <white>/미궁 집 " + lit + " <이름>"))))
                    .then(arg));
        }
    }

    private static SuggestionProvider<CommandSourceStack> onlinePlayers() {
        return (ctx, b) -> {
            for (Player o : Bukkit.getOnlinePlayers()) b.suggest(o.getName());
            return b.buildFuture();
        };
    }

    private SuggestionProvider<CommandSourceStack> vacantPlots() {
        return (ctx, b) -> {
            PlayWiring w = play.get();
            if (w != null) for (PlotGeom g : w.service().plots()) if (w.service().ownerOf(g) == null) b.suggest(g.id());
            return b.buildFuture();
        };
    }

    private static void claim(Player p, PlayUi ui, String arg) {
        String id = arg == null ? "" : arg.trim();
        if (id.equals("아무") || id.equals("아무데나") || id.equals("아무 데나") || id.equalsIgnoreCase("any")) id = "";
        if (id.endsWith("번지")) id = id.substring(0, id.length() - 2).trim();
        ui.claim(p, id.isEmpty() ? null : id);
    }

    private static void guests(Player p, PlayUi ui, Boolean on) {
        HomesService s = ui.service();
        PlotGeom home = s.homeOf(p.getUniqueId());
        if (home == null) {
            Text.error(p, "집이 없습니다.");
            return;
        }
        boolean next = on == null ? !s.info(home).guests() : on;
        ui.send(p, s.setGuests(p, next));
    }

    private void here(Player p, PlayUi ui) {
        HomesService s = ui.service();
        PlotGeom g = s.plotAt(p.getLocation());
        if (g == null) {
            Text.send(p, "<gray>여기는 집터가 아닙니다." + (s.isTerrainLocked(p.getWorld()) ? " 집터 밖은 부수거나 지을 수 없습니다." : ""));
            return;
        }
        PlotInfo info = s.info(g);
        PlotRole role = s.roleIn(p, g);
        HomesConfig c = s.config();
        String who = info.vacant() ? "<#7fe07f>빈 집" : "주인 <white>" + Text.escape(info.ownerName()) + "</white>";
        String me = switch (role) {
            case OWNER -> "내 집";
            case TRUSTED -> "초대받은 집 (짓기·상자 됨)";
            case GUEST -> "손님 (문·작업대·종)";
            default -> info.vacant() ? "받을 수 있음 — /미궁 집 받기 " + g.id() : "손대지 못함";
        };
        Text.send(p, "<#ffd36b>" + Text.escape(g.label()) + "</#ffd36b> <gray>· " + who + " <gray>· " + me + " <dark_gray>· 짓기 높이 "
                + g.yMin() + "~" + g.yMax() + " (바닥 " + g.floorY() + ", 아래 " + c.heightBelow() + " · 위 " + c.heightAbove() + ")");
    }

    private static void help(Player p) {
        Text.send(p, "<#ffd36b>/미궁 집</#ffd36b> <gray>관리인 메뉴 · <white>가기</white> · <white>받기 [번지]</white> · <white>방문 <이름></white> · "
                + "<white>초대 <이름></white> · <white>내보내기 <이름></white> · <white>이름 <글></white> · <white>손님 [켬|끔]</white> · "
                + "<white>짐</white> · <white>비우기</white> · <white>여기</white>");
    }
}
