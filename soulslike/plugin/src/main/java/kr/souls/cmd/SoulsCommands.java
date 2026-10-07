package kr.souls.cmd;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.tree.LiteralCommandNode;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import io.papermc.paper.datapack.Datapack;
import io.papermc.paper.registry.RegistryAccess;
import io.papermc.paper.registry.RegistryKey;
import kr.souls.Keys;
import kr.souls.Souls;
import kr.souls.SoulsBootstrap;
import kr.souls.hud.Glyphs;
import kr.souls.pack.PackService;
import kr.souls.world.TestRoom;
import kr.souls.world.WorldService;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.Difficulty;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.List;

/**
 * /souls (관리자, 12.11). M0 에 있는 것만: check, perf, reload, tp, build room, pack.
 * 나머지(build region, boss, profile, state, give, spawn, telemetry)는 그 체계가 생기는 마일스톤에 더한다.
 */
public final class SoulsCommands {
    private SoulsCommands() {}

    public static void register(Souls plugin, Commands reg) {
        LiteralCommandNode<CommandSourceStack> root = Commands.literal("souls")
                .requires(s -> s.getSender().hasPermission("souls.admin"))
                .executes(ctx -> help(ctx.getSource().getSender()))
                .then(Commands.literal("check").executes(ctx -> check(plugin, ctx.getSource().getSender())))
                .then(Commands.literal("perf").executes(ctx -> perf(plugin, ctx.getSource().getSender())))
                .then(Commands.literal("reload").executes(ctx -> {
                    plugin.reloadAll();
                    ctx.getSource().getSender().sendMessage(Component.text("설정, 문구, 그림 글자, 콘텐츠를 다시 읽었다.", NamedTextColor.GRAY));
                    return Command.SINGLE_SUCCESS;
                }))
                .then(Commands.literal("tp")
                        .then(Commands.argument("anchor", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String s : List.of("room", "lane", "ledge", "lobby")) b.suggest(s);
                                    return b.buildFuture();
                                })
                                .executes(ctx -> tp(plugin, ctx, StringArgumentType.getString(ctx, "anchor")))))
                .then(Commands.literal("build")
                        .then(Commands.literal("room").executes(ctx -> {
                            plugin.worlds().buildRoom(ctx.getSource().getSender());
                            return Command.SINGLE_SUCCESS;
                        })))
                .then(Commands.literal("pack")
                        .executes(ctx -> packStatus(plugin, ctx.getSource().getSender()))
                        .then(Commands.literal("resend").executes(ctx -> {
                            if (target(ctx) instanceof Player p) plugin.pack().send(p);
                            return Command.SINGLE_SUCCESS;
                        })))
                .build();
        reg.register(root, "식은 가마 관리자 명령어", List.of());
    }

    static Entity target(CommandContext<CommandSourceStack> ctx) {
        Entity e = ctx.getSource().getExecutor();
        return e != null ? e : ctx.getSource().getSender() instanceof Player p ? p : null;
    }

    private static int help(CommandSender to) {
        to.sendMessage(Component.text("/souls check | perf | reload | tp <room|lane|ledge|lobby> | build room | pack [resend]", NamedTextColor.GRAY));
        return Command.SINGLE_SUCCESS;
    }

    private static void line(CommandSender to, List<String> fails, boolean ok, String text) {
        String l = (ok ? "[CHECK] OK " : "[CHECK] FAIL ") + text;
        if (!ok) fails.add(text);
        to.sendMessage(Component.text(l, ok ? NamedTextColor.GRAY : NamedTextColor.RED));
        if (to instanceof Player) Bukkit.getLogger().info(l);
    }

    /** 기동 점검 (13.2 의 T1): 데이터팩, 바이옴, 피해 종류, 난이도, 게임 규칙, 시험 방, 팩, 그림 글자, 스킬. */
    static int check(Souls plugin, CommandSender to) {
        List<String> fails = new ArrayList<>();
        boolean dp = false;
        for (Datapack d : Bukkit.getDatapackManager().getEnabledPacks()) {
            if (d.getName().contains(SoulsBootstrap.DATAPACK_ID)) dp = true;
        }
        line(to, fails, dp, "datapack " + SoulsBootstrap.DATAPACK_ID + (dp ? " 켜짐" : " 없음"));
        var biomes = RegistryAccess.registryAccess().getRegistry(RegistryKey.BIOME);
        List<String> missing = new ArrayList<>();
        for (String n : List.of("hub", "prison", "redin", "parish", "mire", "spire", "ossuary", "forge", "kiln")) {
            if (biomes.get(Key.key(Keys.NS, n)) == null) missing.add(n);
        }
        line(to, fails, missing.isEmpty(), "biomes " + (9 - missing.size()) + "/9" + (missing.isEmpty() ? "" : " 없음: " + missing));
        boolean hit = RegistryAccess.registryAccess().getRegistry(RegistryKey.DAMAGE_TYPE).get(Key.key(Keys.NS, "hit")) != null;
        line(to, fails, hit, "damage_type souls:hit" + (hit ? " 있음" : " 없음"));
        WorldService ws = plugin.worlds();
        World game = ws.world();
        line(to, fails, game != null, "world " + plugin.cfg().world.name() + (game != null ? " 열림" : " 없음"));
        for (World w : game == null ? List.of(ws.lobby()) : List.of(ws.lobby(), game)) {
            line(to, fails, w.getDifficulty() == Difficulty.NORMAL, "difficulty " + w.getName() + "=" + w.getDifficulty());
            List<String> bad = ws.ruleMismatches(w);
            line(to, fails, bad.isEmpty(), "gamerules " + w.getName() + " " + (bad.isEmpty() ? WorldService.rules().size() + "개 맞음" : bad));
        }
        if (game != null) {
            Integer room = game.getPersistentDataContainer().get(Keys.ROOM, PersistentDataType.INTEGER);
            line(to, fails, room != null && room >= TestRoom.VERSION, "test room 판 " + room + " (" + ws.lastBuild() + ")");
            Location s = ws.roomSpawn();
            line(to, fails, true, "biome at room = " + game.getBiome(s.getBlockX(), s.getBlockY(), s.getBlockZ()).getKey());
        }
        PackService pk = plugin.pack();
        boolean packOk = pk.ready() && (pk.check() == PackService.Check.OK || pk.check() == PackService.Check.OFF);
        line(to, fails, packOk, "pack sha1=" + pk.sha1() + " check=" + pk.check() + " required=" + pk.required()
                + " url=" + pk.url() + (pk.checkNote().isEmpty() ? "" : " (" + pk.checkNote() + ")"));
        String names = plugin.cfg().death.titleGlyphs();
        boolean glyph = Glyphs.line(names) != null;
        line(to, fails, glyph, "glyphs " + Glyphs.size() + "개, 사망 제목 '" + names + "' " + (glyph ? "있음" : "없음 (붉은 일반 글씨로 대신)"));
        line(to, fails, !plugin.skills().all().isEmpty(), "skills " + plugin.skills().all().size() + "개");
        String sum = "[CHECK] 끝 FAIL " + fails.size();
        to.sendMessage(Component.text(sum, fails.isEmpty() ? NamedTextColor.GRAY : NamedTextColor.RED));
        if (to instanceof Player) Bukkit.getLogger().info(sum);
        return Command.SINGLE_SUCCESS;
    }

    private static int perf(Souls plugin, CommandSender to) {
        for (String l : plugin.ticker().report()) to.sendMessage(Component.text(l, NamedTextColor.GRAY));
        to.sendMessage(Component.text(String.format("서버 평균 틱 %.2f ms", Bukkit.getAverageTickTime()), NamedTextColor.GRAY));
        return Command.SINGLE_SUCCESS;
    }

    private static int tp(Souls plugin, CommandContext<CommandSourceStack> ctx, String anchor) {
        if (!(target(ctx) instanceof Player p)) return 0;
        WorldService ws = plugin.worlds();
        World w = ws.world();
        int[] c = ws.roomCenter();
        Location to = switch (anchor) {
            case "room" -> ws.roomSpawn();
            case "lane" -> w == null ? null : TestRoom.lane(w, c[0], c[1], c[2]);
            case "ledge" -> w == null ? null : TestRoom.ledge(w, c[0], c[1], c[2]);
            case "lobby" -> ws.lobby().getSpawnLocation();
            default -> null;
        };
        if (to == null) {
            p.sendMessage(Component.text("그런 자리는 없다: " + anchor, NamedTextColor.GRAY));
            return 0;
        }
        p.teleport(to);
        return Command.SINGLE_SUCCESS;
    }

    private static int packStatus(Souls plugin, CommandSender to) {
        PackService pk = plugin.pack();
        to.sendMessage(Component.text("팩 sha1=" + pk.sha1() + " check=" + pk.check() + " required=" + pk.required()
                + " send-at=" + plugin.cfg().pack.sendAt() + "\n" + pk.url() + "\n" + pk.checkNote(), NamedTextColor.GRAY));
        return Command.SINGLE_SUCCESS;
    }
}
