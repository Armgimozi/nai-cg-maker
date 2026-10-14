package kr.labyrinth.bosses;

import com.mojang.brigadier.arguments.IntegerArgumentType;
import io.papermc.paper.command.brigadier.Commands;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.Location;
import org.bukkit.entity.Player;

/**
 * bosses 담당 모듈 진입점. 이 파일과 이 패키지는 bosses 담당 소유 — 다른 작업자는 수정하지 않는다.
 * <p>
 * {@link LabBossService} 를 등록하고 관리자 명령을 붙인다:
 * {@code /labadmin spawnboss <층> [인원]}(지금 서 있는 곳을 아레나 중심으로 — 블록 설치 없이 디스플레이로 대체),
 * {@code /labadmin endboss}(근처 보스전 강제 종료), {@code /labadmin bosses}(진행 중 보스·구현 층 목록).
 */
public final class BossesModule implements Module {

    private final Services services;
    private LabBossService service;

    public BossesModule(Services services) { this.services = services; }

    @Override
    public String name() { return "bosses"; }

    @Override
    public void enable() {
        service = new LabBossService(services);
        services.setBosses(service);
        service.start();
        registerCommands(services.commands());
    }

    @Override
    public void disable() {
        if (service != null) service.stop();
    }

    private void registerCommands(CommandService cmd) {
        cmd.addSubcommand("labadmin", Commands.literal("spawnboss")
                .then(Commands.argument("floor", IntegerArgumentType.integer(1, 10))
                        .executes(ctx -> {
                            CommandService.safeRun(ctx, () -> spawn(ctx.getSource().getSender(),
                                    IntegerArgumentType.getInteger(ctx, "floor"), -1, CommandService.sender(ctx)));
                            return 1;
                        })
                        .then(Commands.argument("party", IntegerArgumentType.integer(1, 10))
                                .executes(ctx -> {
                                    CommandService.safeRun(ctx, () -> spawn(ctx.getSource().getSender(),
                                            IntegerArgumentType.getInteger(ctx, "floor"), IntegerArgumentType.getInteger(ctx, "party"),
                                            CommandService.sender(ctx)));
                                    return 1;
                                }))));
        cmd.addSubcommand("labadmin", Commands.literal("endboss").executes(ctx -> {
            CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), p -> {
                Boss b = service.bossAt(p.getLocation());
                if (b == null) {
                    Text.error(p, "근처에 진행 중인 보스전이 없습니다.");
                    return;
                }
                b.end();
                Text.send(p, "<green>보스전을 종료했습니다:</green> " + b.def().name());
            }));
            return 1;
        }));
        cmd.addSubcommand("labadmin", Commands.literal("bosses").executes(ctx -> {
            CommandService.safeRun(ctx, () -> {
                var s = ctx.getSource().getSender();
                Text.send(s, "<gold>보스 구현 층:</gold> <white>" + service.implementedFloors());
                for (Boss b : service.bosses()) {
                    Location c = b.center();
                    InstanceContext ic = b.instance();
                    s.sendMessage(Text.mm("<gray> - " + b.def().name() + " <dark_gray>[" + (ic == null ? "관리자 소환" : ic.id()) + "] "
                            + c.getWorld().getName() + " " + c.getBlockX() + "," + c.getBlockY() + "," + c.getBlockZ()
                            + "</dark_gray> <red>" + Text.num(b.health()) + "/" + Text.num(b.maxHealth()) + "</red> 페이즈 " + b.phase()));
                }
            });
            return 1;
        }));
    }

    private void spawn(org.bukkit.command.CommandSender sender, int floor, int party, org.bukkit.command.CommandSender executor) {
        CommandService.withPlayer(executor, p -> {
            BossDef def = service.bossDef(floor);
            if (def == null) {
                Text.error(sender, "지하 " + floor + "층 보스 정의가 없습니다 (bosses.yml).");
                return;
            }
            int n = party > 0 ? party : Math.max(1, partyOf(p));
            InstanceContext ctx = InstanceContext.adhoc(floor, n, services.settings().difficulty(), services.settings().party());
            Location c = p.getLocation().getBlock().getLocation().add(0.5, 0, 0.5);
            Boss b = service.spawn(floor, c, ctx, true);
            if (b == null) {
                Text.error(sender, "지하 " + floor + "층 보스를 소환하지 못했습니다 (구현 층: " + service.implementedFloors() + ").");
                return;
            }
            Text.send(sender, "<green>보스 소환:</green> " + def.name() + " <gray>(인원 " + n + "명 기준, 난이도 "
                    + services.settings().difficulty().name() + ", 블록 대신 디스플레이)");
        });
    }

    private int partyOf(Player p) {
        try {
            return services.party().size(p);
        } catch (Throwable t) {
            return 1;
        }
    }
}
