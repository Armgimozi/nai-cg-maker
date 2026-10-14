package kr.labyrinth.ui;

import com.mojang.brigadier.Command;
import io.papermc.paper.command.brigadier.Commands;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Module;

/**
 * ui+titles 담당 모듈 진입점: 상자 GUI 메뉴({@link LabMenuService}, ui/menus/*) + HUD({@link LabHudService}).
 * 글리프(리소스팩 UI 그림)는 glyphs.yml 이 있으면 자동 적용, 없으면 텍스트/평범한 제목으로 동작한다.
 * 하위 명령: /미궁 메뉴|menu · /미궁 장신구|accessories · /미궁 대장간|blacksmith · /미궁 상점|shop · /미궁 대전|pvp.
 */
public final class UiModule implements Module {

    private final Services services;
    private LabHudService hud;

    public UiModule(Services services) { this.services = services; }

    @Override
    public String name() { return "ui"; }

    @Override
    public void enable() {
        UiTheme.loadMeta(services);
        services.setMenus(new LabMenuService(services));
        hud = new LabHudService(services);
        services.setHud(hud);
        hud.start();
        // 칭호 접두어가 HUD 등록보다 먼저 계산됐을 수 있으니 다시 반영
        for (org.bukkit.entity.Player p : org.bukkit.Bukkit.getOnlinePlayers()) {
            hud.nameTagPrefix(p, services.titles().prefix(p));
        }
        registerCommands();
    }

    @Override
    public void disable() {
        if (hud != null) hud.stop();
    }

    @Override
    public void reload() {
        UiTheme.loadMeta(services);
    }

    private void sub(String en, String ko, java.util.function.Consumer<org.bukkit.entity.Player> action) {
        for (String n : new String[] {en, ko}) {
            services.commands().addSubcommand("lab", Commands.literal(n).executes(ctx -> {
                CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), action));
                return Command.SINGLE_SUCCESS;
            }));
        }
    }

    private void registerCommands() {
        sub("menu", "메뉴", p -> services.menus().openMain(p));
        sub("accessories", "장신구", p -> services.menus().openAccessories(p));
        sub("blacksmith", "대장간", p -> services.menus().openBlacksmith(p));
        sub("shop", "상점", p -> services.menus().openMerchant(p));
        sub("pvp", "대전", p -> services.menus().openPvp(p));
        sub("codex", "도감", p -> new kr.labyrinth.ui.menus.CodexMenu(services).open(p));
        services.commands().addRootCommand(Commands.literal("codex").executes(ctx -> {
            CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx),
                    p -> new kr.labyrinth.ui.menus.CodexMenu(services).open(p)));
            return Command.SINGLE_SUCCESS;
        }), "미궁 도감 — 아이템·몬스터·보스와 획득처", java.util.List.of("도감"));
        sub("records", "기록", p -> new kr.labyrinth.ui.menus.RecordsMenu(services, pl -> services.menus().openMain(pl)).open(p));
    }
}
