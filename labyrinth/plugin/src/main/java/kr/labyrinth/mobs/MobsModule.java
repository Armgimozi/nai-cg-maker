package kr.labyrinth.mobs;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.BoolArgumentType;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import java.util.Map;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.InstanceContext;
import kr.labyrinth.mobs.npc.NpcServiceImpl;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.util.RayTraceResult;

/**
 * mobs+npc 담당 모듈 진입점. 이 파일과 이 패키지는 mobs+npc 담당 소유 — 다른 작업자는 수정하지 않는다.
 * <p>
 * enable(): {@link MobServiceImpl}(ModelRig·AI·스킬·보상)과 {@link NpcServiceImpl}(Mannequin NPC)을 등록하고
 * 관리 명령을 붙인다: {@code /labadmin spawnmob <id> [개수] [정예]}, {@code killmobs [반경]},
 * {@code mobdrill <몹 id…|all|f<층>>}(스킬 훈련 — {@link MobDrill}), {@code setnpc <id>}, {@code removenpc <id>}, {@code npcs}.
 */
public final class MobsModule implements Module {

    private final Services services;
    private MobServiceImpl mobs;
    private NpcServiceImpl npcs;

    public MobsModule(Services services) { this.services = services; }

    @Override
    public String name() { return "mobs"; }

    @Override
    public void enable() {
        mobs = new MobServiceImpl(services);
        npcs = new NpcServiceImpl(services);
        services.setMobs(mobs);
        services.setNpcs(npcs);
        mobs.start();
        npcs.start();
        registerCommands(services.commands());
    }

    @Override
    public void disable() {
        MobDrill.abort();
        if (npcs != null) npcs.stop();
        if (mobs != null) mobs.stop();
    }

    @Override
    public void reload() {
        if (mobs != null) mobs.purgeInvalid();
        if (npcs != null) npcs.respawnAll();
    }

    // ── 명령 ─────────────────────────────────────────────────────────────

    private SuggestionProvider<CommandSourceStack> mobIds() {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            int n = 0;
            for (MobDef d : services.content().mobs().values()) {
                if (d.id().startsWith(rem) || (rem.length() >= 2 && d.id().contains(rem))) {
                    b.suggest(d.id());
                    if (++n >= 60) break;
                }
            }
            return b.buildFuture();
        };
    }

    private SuggestionProvider<CommandSourceStack> npcIds() {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            for (NpcDef d : services.content().npcs().values()) if (d.id().startsWith(rem)) b.suggest(d.id());
            return b.buildFuture();
        };
    }

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    private void registerCommands(CommandService cmd) {
        cmd.addSubcommand("labadmin", Commands.literal("spawnmob")
                .then(Commands.argument("mob", StringArgumentType.word()).suggests(mobIds())
                        .executes(ctx -> run(ctx, () -> spawnMob(ctx, 1, false)))
                        .then(Commands.argument("count", IntegerArgumentType.integer(1, 30))
                                .executes(ctx -> run(ctx, () -> spawnMob(ctx, IntegerArgumentType.getInteger(ctx, "count"), false)))
                                .then(Commands.argument("elite", BoolArgumentType.bool())
                                        .executes(ctx -> run(ctx, () -> spawnMob(ctx, IntegerArgumentType.getInteger(ctx, "count"),
                                                BoolArgumentType.getBool(ctx, "elite"))))))));

        cmd.addSubcommand("labadmin", Commands.literal("killmobs")
                .executes(ctx -> run(ctx, () -> killMobs(ctx, 48)))
                .then(Commands.argument("radius", IntegerArgumentType.integer(1, 512))
                        .executes(ctx -> run(ctx, () -> killMobs(ctx, IntegerArgumentType.getInteger(ctx, "radius"))))));

        cmd.addSubcommand("labadmin", Commands.literal("mobdrill")
                .then(Commands.argument("mobs", StringArgumentType.greedyString()).suggests(mobIds())
                        .executes(ctx -> run(ctx, () -> mobDrill(ctx)))));

        cmd.addSubcommand("labadmin", Commands.literal("setnpc")
                .then(Commands.argument("npc", StringArgumentType.word()).suggests(npcIds())
                        .executes(ctx -> run(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), p -> setNpc(p,
                                StringArgumentType.getString(ctx, "npc")))))));

        cmd.addSubcommand("labadmin", Commands.literal("removenpc")
                .then(Commands.argument("npc", StringArgumentType.word()).suggests(npcIds())
                        .executes(ctx -> run(ctx, () -> {
                            String id = StringArgumentType.getString(ctx, "npc");
                            boolean ok = npcs.remove(id);
                            if (ok) Text.send(ctx.getSource().getSender(), "<green>NPC 제거:</green> <white>" + Text.escape(id));
                            else Text.error(ctx.getSource().getSender(), "배치된 NPC 가 아닙니다: " + Text.escape(id));
                        }))));

        cmd.addSubcommand("labadmin", Commands.literal("npcs").executes(ctx -> run(ctx, () -> {
            var s = ctx.getSource().getSender();
            Text.send(s, "<gold>NPC 목록</gold> <gray>(배치 = /labadmin setnpc <id>)");
            Map<String, Location> placed = npcs.placed();
            for (NpcDef d : services.content().npcs().values()) {
                Location l = placed.get(d.id());
                String where = l != null ? "<green>배치됨</green> <dark_gray>" + l.getWorld().getName() + " " + l.getBlockX() + ","
                        + l.getBlockY() + "," + l.getBlockZ() : placed.containsKey(d.id()) ? "<yellow>월드 없음"
                        : "floor".equals(d.placement()) ? "<gray>층 휴식방 자동" : "<red>미배치";
                s.sendMessage(Text.mm("<gray> - <white>" + d.id() + "</white> " + d.name() + " <dark_gray>[" + d.role() + "]</dark_gray> " + where));
            }
        })));
    }

    private void spawnMob(CommandContext<CommandSourceStack> ctx, int count, boolean elite) {
        String id = StringArgumentType.getString(ctx, "mob");
        var sender = ctx.getSource().getSender();
        MobDef def = services.content().mob(id);
        if (def == null) {
            Text.error(sender, "없는 몹: " + Text.escape(id));
            return;
        }
        Location at = ctx.getSource().getLocation();
        if (CommandService.sender(ctx) instanceof Player p) at = targetSpot(p);
        if (at == null || at.getWorld() == null) {
            Text.error(sender, "소환할 위치를 찾을 수 없습니다.");
            return;
        }
        int n = 0;
        int party = sender instanceof Player p ? services.party().size(p) : 1;
        InstanceContext ictx = InstanceContext.adhoc(Math.max(1, def.floor()), party, services.settings().difficulty(),
                services.settings().party());
        for (int i = 0; i < count; i++) {
            Location l = at.clone().add((i % 5) * 1.6 - (Math.min(count, 5) - 1) * 0.8, 0, (i / 5) * 1.6);
            if (!l.getBlock().isPassable()) l = at.clone();
            if (mobs.spawn(id, l, ictx, elite) != null) n++;
        }
        Text.send(sender, "<white>" + def.name() + "</white> <gray>×" + n + (elite ? " <gold>(정예 변종)</gold>" : "")
                + " 소환 <dark_gray>(난이도 " + services.settings().difficulty().name() + ", 파티 " + party + "명 기준)");
    }

    /** 몹 스킬 훈련: 토큰 = 몹 id · all(전부) · f<층>(그 층 몹 전부). */
    private void mobDrill(CommandContext<CommandSourceStack> ctx) {
        var sender = ctx.getSource().getSender();
        java.util.LinkedHashSet<String> ids = new java.util.LinkedHashSet<>();
        for (String tok : StringArgumentType.getString(ctx, "mobs").trim().split("[\\s,]+")) {
            if (tok.isBlank()) continue;
            String k = tok.toLowerCase(java.util.Locale.ROOT);
            if (k.equals("all")) {
                ids.addAll(services.content().mobs().keySet());
            } else if (k.matches("f\\d+")) {
                int floor = Integer.parseInt(k.substring(1));
                for (MobDef d : services.content().mobs().values()) if (d.floor() == floor) ids.add(d.id());
            } else if (services.content().mob(k) != null) {
                ids.add(k);
            } else {
                Text.error(sender, "없는 몹: " + Text.escape(tok));
                return;
            }
        }
        Location at = ctx.getSource().getLocation();
        if (CommandService.sender(ctx) instanceof Player p) at = targetSpot(p);
        if (at == null || at.getWorld() == null) {
            Text.error(sender, "훈련할 위치를 찾을 수 없습니다.");
            return;
        }
        MobDrill.start(services, mobs, sender, at, new java.util.ArrayList<>(ids));
    }

    /** 바라보는 블록 위 (8블록 안), 없으면 발밑. */
    private static Location targetSpot(Player p) {
        RayTraceResult r = p.getWorld().rayTraceBlocks(p.getEyeLocation(), p.getEyeLocation().getDirection(), 8,
                FluidCollisionMode.NEVER, true);
        if (r != null && r.getHitBlock() != null) {
            Block b = r.getHitBlock();
            Block above = b.getRelative(0, 1, 0);
            if (above.isPassable() && above.getRelative(0, 1, 0).isPassable()) {
                Location l = above.getLocation().add(0.5, 0, 0.5);
                l.setYaw(p.getLocation().getYaw() + 180);
                return l;
            }
        }
        return p.getLocation();
    }

    private void killMobs(CommandContext<CommandSourceStack> ctx, int radius) {
        Location at = ctx.getSource().getLocation();
        int n = mobs.removeNear(at, radius);
        Text.send(ctx.getSource().getSender(), "<gray>반경 " + radius + "블록의 커스텀 몹 <white>" + n + "</white>마리 제거");
    }

    private void setNpc(Player p, String id) {
        NpcDef def = services.content().npcs().get(id);
        if (def == null) {
            Text.error(p, "없는 NPC: " + Text.escape(id));
            return;
        }
        Location l = p.getLocation().clone();
        l.setPitch(0);
        if (npcs.place(id, l) == null) {
            Text.error(p, "NPC 를 세우지 못했습니다.");
            return;
        }
        NpcServiceImpl.sparkle(l);
        Text.send(p, def.name() + " <green>배치 완료</green> <gray>(지금 서 있는 자리 · 바라보는 방향, 블록 변경 없음)");
    }
}
