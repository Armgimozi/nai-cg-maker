package kr.labyrinth.command;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import io.papermc.paper.plugin.lifecycle.event.types.LifecycleEvents;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import kr.labyrinth.Services;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Text;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

/**
 * Paper Brigadier 명령 등록 (LifecycleEvents.COMMANDS). 루트 명령과 한국어 별칭은 여기서 정의하고,
 * 각 모듈은 자기 {@code enable()} 안에서 {@link #addSubcommand} 로 하위 명령을 붙인다
 * (등록은 서버가 명령을 만들 때 한 번에 일어나므로 enable 이후에 붙인 것은 다음 리로드부터 반영).
 * <pre>
 * services.commands().addSubcommand("party", Commands.literal("invite")
 *     .then(Commands.argument("player", StringArgumentType.word()).executes(ctx -> ...)));
 * </pre>
 * 루트: lab(미궁) · party(파티) · stats(스탯) · class(직업) · title(칭호) · pvp(대전) · labadmin(미궁관리).
 */
public final class CommandService implements Module {

    public static final String PERM_ADMIN = "labyrinth.admin";

    /** 루트 정의: 이름, 별칭, 설명, 관리자 전용, 인자 없이 실행 시 동작. */
    private record Root(String name, List<String> aliases, String description, boolean admin, Consumer<CommandSender> noArgs) {}

    private final Services services;
    private final Map<String, Root> roots = new LinkedHashMap<>();
    private final Map<String, List<LiteralArgumentBuilder<CommandSourceStack>>> subs = new LinkedHashMap<>();
    private final List<RootContribution> extraRoots = new ArrayList<>();

    private record RootContribution(LiteralArgumentBuilder<CommandSourceStack> node, String description, List<String> aliases) {}

    public CommandService(Services services) {
        this.services = services;
        root("lab", List.of("미궁", "labyrinth"), "미궁 라비린스 메뉴", false, s -> withPlayer(s, p -> services.menus().openMain(p)));
        root("party", List.of("파티"), "파티", false, s -> withPlayer(s, p -> services.menus().openParty(p)));
        root("stats", List.of("스탯"), "스탯 분배", false, s -> withPlayer(s, p -> services.menus().openStats(p)));
        root("class", List.of("직업"), "직업", false, s -> withPlayer(s, p -> services.menus().openClass(p)));
        root("title", List.of("칭호"), "칭호", false, s -> withPlayer(s, p -> services.menus().openTitles(p)));
        root("pvp", List.of("대전"), "파티 대 파티 대전", false, s -> withPlayer(s, p -> services.menus().openPvp(p)));
        root("labadmin", List.of("미궁관리"), "미궁 라비린스 관리", true, s -> AdminCommands.help(s));
    }

    private void root(String name, List<String> aliases, String desc, boolean admin, Consumer<CommandSender> noArgs) {
        roots.put(name, new Root(name, aliases, desc, admin, noArgs));
        subs.put(name, new ArrayList<>());
    }

    @Override
    public String name() { return "commands"; }

    @Override
    public void enable() {
        new AdminCommands(services).register(this);
        new PlayerCommands(services).register(this);
        services.plugin().getLifecycleManager().registerEventHandler(LifecycleEvents.COMMANDS,
                event -> registerAll(event.registrar()));
    }

    /** 루트 명령에 하위 명령 추가 (root = lab | party | stats | class | title | pvp | labadmin). */
    public void addSubcommand(String root, LiteralArgumentBuilder<CommandSourceStack> sub) {
        List<LiteralArgumentBuilder<CommandSourceStack>> list = subs.get(root);
        if (list == null) throw new IllegalArgumentException("알 수 없는 루트 명령: " + root);
        list.add(sub);
    }

    /** 완전히 새로운 루트 명령 추가 (가능하면 기존 루트의 하위 명령으로). */
    public void addRootCommand(LiteralArgumentBuilder<CommandSourceStack> node, String description, List<String> aliases) {
        extraRoots.add(new RootContribution(node, description, aliases));
    }

    private void registerAll(Commands registrar) {
        for (Root r : roots.values()) {
            LiteralArgumentBuilder<CommandSourceStack> node = Commands.literal(r.name());
            if (r.admin()) node.requires(src -> src.getSender().hasPermission(PERM_ADMIN));
            node.executes(ctx -> {
                safeRun(ctx, () -> r.noArgs().accept(ctx.getSource().getSender()));
                return Command.SINGLE_SUCCESS;
            });
            for (LiteralArgumentBuilder<CommandSourceStack> sub : subs.get(r.name())) node.then(sub);
            registrar.register(node.build(), r.description(), r.aliases());
        }
        for (RootContribution c : extraRoots) registrar.register(c.node().build(), c.description(), c.aliases());
    }

    // ── 헬퍼 (다른 모듈도 사용) ───────────────────────────────────────────

    /** 실행자가 플레이어면 action, 아니면 안내. */
    public static void withPlayer(CommandSender sender, Consumer<Player> action) {
        if (sender instanceof Player p) action.accept(p);
        else Text.error(sender, "플레이어만 사용할 수 있습니다.");
    }

    /** 명령 실행자 (콘솔이면 sender, execute as 면 executor). */
    public static CommandSender sender(CommandContext<CommandSourceStack> ctx) {
        return ctx.getSource().getExecutor() instanceof Player p ? p : ctx.getSource().getSender();
    }

    /** 예외가 서버 콘솔 스택트레이스 대신 짧은 메시지로 나가게. */
    public static void safeRun(CommandContext<CommandSourceStack> ctx, Runnable r) {
        try {
            r.run();
        } catch (Throwable t) {
            kr.labyrinth.core.Log.error("명령 처리 오류", t);
            Text.error(ctx.getSource().getSender(), "명령 처리 중 오류가 발생했습니다: " + Text.escape(String.valueOf(t.getMessage())));
        }
    }
}
