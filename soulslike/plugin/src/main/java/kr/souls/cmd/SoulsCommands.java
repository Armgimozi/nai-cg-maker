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
import kr.souls.Lang;
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
import java.util.Locale;
import java.util.Set;
import java.util.TreeSet;

/**
 * /souls (관리자, 12.11). M0 에 있는 것만: check, perf, reload, tp, build room, pack.
 * 나머지(build region, boss, profile, state, give, spawn, telemetry)는 그 체계가 생기는 마일스톤에 더한다.
 * 사람에게 하는 답은 번역 열쇠 (lang 의 admin.*). check·pack·perf 의 줄은 봇과 사람이 함께 읽는 점검 기록이라
 * 언어와 상관없이 같은 ASCII 꼴로 낸다 ("[CHECK] OK datapack soulsdp enabled", 서버 기록에도 같은 줄).
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
                    Lang.tell(ctx.getSource().getSender(), "admin.reloaded");
                    return Command.SINGLE_SUCCESS;
                }))
                .then(Commands.literal("tp")
                        .then(Commands.argument("anchor", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String s : List.of("room", "lane", "slab", "ledge", "lobby")) b.suggest(s);
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
        reg.register(root, "Soulslike admin commands", List.of());
    }

    static Entity target(CommandContext<CommandSourceStack> ctx) {
        Entity e = ctx.getSource().getExecutor();
        return e != null ? e : ctx.getSource().getSender() instanceof Player p ? p : null;
    }

    private static int help(CommandSender to) {
        to.sendMessage(Component.text("/souls check | perf | reload | tp <room|lane|slab|ledge|lobby> | build room | pack [resend]", NamedTextColor.GRAY)); // lang-machine: 쓰는 법
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
        line(to, fails, dp, "datapack " + SoulsBootstrap.DATAPACK_ID + (dp ? " enabled" : " missing"));
        var biomes = RegistryAccess.registryAccess().getRegistry(RegistryKey.BIOME);
        List<String> missing = new ArrayList<>();
        for (String n : List.of("hub", "prison", "redin", "parish", "mire", "spire", "ossuary", "forge", "kiln")) {
            if (biomes.get(Key.key(Keys.NS, n)) == null) missing.add(n);
        }
        line(to, fails, missing.isEmpty(), "biomes " + (9 - missing.size()) + "/9" + (missing.isEmpty() ? "" : " missing: " + missing));
        boolean hit = RegistryAccess.registryAccess().getRegistry(RegistryKey.DAMAGE_TYPE).get(Key.key(Keys.NS, "hit")) != null;
        line(to, fails, hit, "damage_type souls:hit" + (hit ? " present" : " missing"));
        WorldService ws = plugin.worlds();
        World game = ws.world();
        line(to, fails, game != null, "world " + plugin.cfg().world.name() + (game != null ? " loaded" : " missing"));
        for (World w : game == null ? List.of(ws.lobby()) : List.of(ws.lobby(), game)) {
            line(to, fails, w.getDifficulty() == Difficulty.NORMAL, "difficulty " + w.getName() + "=" + w.getDifficulty());
            List<String> bad = ws.ruleMismatches(w);
            line(to, fails, bad.isEmpty(), "gamerules " + w.getName() + " " + (bad.isEmpty() ? WorldService.rules().size() + " ok" : bad));
        }
        if (game != null) {
            Integer room = game.getPersistentDataContainer().get(Keys.ROOM, PersistentDataType.INTEGER);
            line(to, fails, room != null && room >= TestRoom.VERSION, "test room v" + room + " (" + ws.lastBuild() + ")");
            Location s = ws.roomSpawn();
            line(to, fails, true, "biome at room = " + game.getBiome(s.getBlockX(), s.getBlockY(), s.getBlockZ()).getKey());
        }
        PackService pk = plugin.pack();
        boolean packOk = pk.ready() && (pk.check() == PackService.Check.OK || pk.check() == PackService.Check.OFF);
        line(to, fails, packOk, "pack sha1=" + pk.sha1() + " check=" + pk.check() + " required=" + pk.required()
                + " url=" + pk.url() + (pk.checkNote().isEmpty() ? "" : " (" + pk.checkNote() + ")"));
        String names = plugin.cfg().death.titleGlyphs();
        boolean glyph = Glyphs.line(names) != null;
        line(to, fails, glyph, "glyphs " + Glyphs.size() + ", death title '" + names + "' " + (glyph ? "present" : "missing (red plain text instead)"));
        // YOU DIED 는 한 번만 (5.6): 팩의 사망 화면 제목과 플러그인 화면 제목 가운데 하나만 쓴다
        if (pk.ready()) {
            String screen = pk.packLang("en_us", "deathScreen.title");
            boolean onScreen = screen != null && !screen.isEmpty();
            boolean byPlugin = plugin.cfg().death.title();
            line(to, fails, onScreen != byPlugin, "death title " + (onScreen && byPlugin ? "both (overlap)"
                    : onScreen ? "death screen only" : byPlugin ? "plugin title only" : "none (vanilla text or blank)")
                    + " (pack deathScreen.title=" + (screen == null ? "missing" : screen.isEmpty() ? "blank" : screen.length() + " chars")
                    + ", death.title=" + byPlugin + ")");
        }
        line(to, fails, !plugin.skills().all().isEmpty(), "skills " + plugin.skills().all().size());
        // 문구 (10.3, 10.9): jar 안 lang/*.yml 의 열쇠와 jar 안 팩의 souls 언어 파일 열쇠가 같다 (낡은 팩 거르기)
        if (pk.ready()) {
            Set<String> want = new TreeSet<>();
            for (String k : Lang.keys()) want.add(Lang.PREFIX + k);
            Set<String> ko = pk.packLangKeys("souls", "ko_kr");
            Set<String> en = pk.packLangKeys("souls", "en_us");
            line(to, fails, !want.isEmpty() && want.equals(ko) && want.equals(en), "lang keys " + want.size() + ", pack souls ko_kr "
                    + (ko == null ? "missing" : ko.size()) + " en_us " + (en == null ? "missing" : en.size()));
        } else {
            line(to, fails, Lang.size() > 0, "lang keys " + Lang.size() + " (no pack to compare)");
        }
        String sum = "[CHECK] done FAIL " + fails.size();
        to.sendMessage(Component.text(sum, fails.isEmpty() ? NamedTextColor.GRAY : NamedTextColor.RED));
        if (to instanceof Player) Bukkit.getLogger().info(sum);
        return Command.SINGLE_SUCCESS;
    }

    private static int perf(Souls plugin, CommandSender to) {
        for (String l : plugin.ticker().report()) to.sendMessage(Component.text(l, NamedTextColor.GRAY));
        to.sendMessage(Component.text(String.format(Locale.ROOT, "server avg tick %.2f ms", Bukkit.getAverageTickTime()), NamedTextColor.GRAY)); // lang-machine
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
            case "slab" -> w == null ? null : TestRoom.slab(w, c[0], c[1], c[2]);
            case "ledge" -> w == null ? null : TestRoom.ledge(w, c[0], c[1], c[2]);
            case "lobby" -> ws.lobby().getSpawnLocation();
            default -> null;
        };
        if (to == null) {
            Lang.tell(p, "admin.no-anchor", "anchor", anchor);
            return 0;
        }
        p.teleport(to);
        return Command.SINGLE_SUCCESS;
    }

    private static int packStatus(Souls plugin, CommandSender to) {
        PackService pk = plugin.pack();
        to.sendMessage(Component.text("pack sha1=" + pk.sha1() + " check=" + pk.check() + " required=" + pk.required() // lang-machine
                + " send-at=" + plugin.cfg().pack.sendAt() + "\n" + pk.url() + "\n" + pk.checkNote(), NamedTextColor.GRAY));
        return Command.SINGLE_SUCCESS;
    }
}
