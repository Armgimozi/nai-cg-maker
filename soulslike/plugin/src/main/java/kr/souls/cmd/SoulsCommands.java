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
import kr.souls.data.Profile;
import kr.souls.data.WorldState;
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
 * /souls (관리자, 12.11): check, perf, reload, tp, build room, pack, 그리고 1.3판의 settings (세계 설정 창 / difficulty / pvp, 5.7),
 * origin reset (출신 지우기, 5.10), souls (소울 정하기·더하기, 5.4), profile dump. 바꾸는 명령은 모두 서버 기록에 남는다.
 * 나머지(build region, boss, state, give, spawn, telemetry)는 그 체계가 생기는 마일스톤에 더한다. 플레이어 명령 /stats 도 여기서 등록한다.
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
                .then(Commands.literal("settings")
                        .executes(ctx -> {
                            if (!(target(ctx) instanceof Player p)) return info(plugin, ctx.getSource().getSender());
                            if (!plugin.start().openSettings(p, "op")) Lang.tell(p, "admin.settings-busy");
                            return Command.SINGLE_SUCCESS;
                        })
                        .then(Commands.literal("difficulty").then(Commands.argument("id", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String id : plugin.cfg().difficulties.keySet()) b.suggest(id);
                                    return b.buildFuture();
                                })
                                .executes(ctx -> settings(plugin, ctx.getSource().getSender(), StringArgumentType.getString(ctx, "id"), null))))
                        .then(Commands.literal("pvp").then(Commands.argument("on", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    b.suggest("on");
                                    b.suggest("off");
                                    return b.buildFuture();
                                })
                                .executes(ctx -> settings(plugin, ctx.getSource().getSender(), null, StringArgumentType.getString(ctx, "on"))))))
                .then(Commands.literal("origin").then(Commands.literal("reset").then(Commands.argument("player", StringArgumentType.word())
                        .suggests((c, b) -> {
                            for (Player o : Bukkit.getOnlinePlayers()) b.suggest(o.getName());
                            return b.buildFuture();
                        })
                        .executes(ctx -> originReset(plugin, ctx.getSource().getSender(), StringArgumentType.getString(ctx, "player"), false))
                        .then(Commands.literal("keep-items").executes(ctx -> originReset(plugin, ctx.getSource().getSender(),
                                StringArgumentType.getString(ctx, "player"), true))))))
                .then(Commands.literal("souls").then(Commands.argument("player", StringArgumentType.word())
                        .suggests((c, b) -> {
                            for (Player o : Bukkit.getOnlinePlayers()) b.suggest(o.getName());
                            return b.buildFuture();
                        })
                        .then(Commands.argument("op", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    b.suggest("set");
                                    b.suggest("add");
                                    return b.buildFuture();
                                })
                                .then(Commands.argument("n", com.mojang.brigadier.arguments.LongArgumentType.longArg(0, Profile.SOULS_MAX))
                                        .executes(ctx -> souls(plugin, ctx.getSource().getSender(), StringArgumentType.getString(ctx, "player"),
                                                StringArgumentType.getString(ctx, "op"), com.mojang.brigadier.arguments.LongArgumentType.getLong(ctx, "n")))))))
                .then(Commands.literal("profile").then(Commands.literal("dump").then(Commands.argument("player", StringArgumentType.word())
                        .suggests((c, b) -> {
                            for (Player o : Bukkit.getOnlinePlayers()) b.suggest(o.getName());
                            return b.buildFuture();
                        })
                        .executes(ctx -> profileDump(plugin, ctx.getSource().getSender(), StringArgumentType.getString(ctx, "player"))))))
                .build();
        reg.register(root, "Soulslike admin commands", List.of());

        // /stats [이름]: 능력치 창 (5.9). 모든 플레이어 (souls.stats, 기본 참), 남의 것은 관리자만
        LiteralCommandNode<CommandSourceStack> stats = Commands.literal("stats")
                .requires(s -> s.getSender().hasPermission("souls.stats"))
                .executes(ctx -> {
                    if (!(target(ctx) instanceof Player p)) {
                        Lang.tell(ctx.getSource().getSender(), "admin.players-only");
                        return 0;
                    }
                    kr.souls.ui.StatsDialog.show(plugin, p, p, false);
                    return Command.SINGLE_SUCCESS;
                })
                .then(Commands.argument("player", StringArgumentType.word())
                        .requires(s -> s.getSender().hasPermission("souls.admin"))
                        .suggests((c, b) -> {
                            for (Player o : Bukkit.getOnlinePlayers()) b.suggest(o.getName());
                            return b.buildFuture();
                        })
                        .executes(ctx -> {
                            Player of = Bukkit.getPlayerExact(StringArgumentType.getString(ctx, "player"));
                            if (of == null) {
                                Lang.tell(ctx.getSource().getSender(), "admin.no-player", "player", StringArgumentType.getString(ctx, "player"));
                                return 0;
                            }
                            if (target(ctx) instanceof Player p) kr.souls.ui.StatsDialog.show(plugin, p, of, false);
                            else ctx.getSource().getSender().sendMessage(Component.text(plugin.stats().line(of), NamedTextColor.GRAY)); // lang-machine: 점검 줄
                            return Command.SINGLE_SUCCESS;
                        }))
                .build();
        reg.register(stats, "Soulslike status window", List.of());
    }

    /** 세계 설정 바꾸기 (관리자 명령, 5.7). 하나만 바꾸고 나머지는 그대로. 확정되고 rev 가 오른다. */
    private static int settings(Souls plugin, CommandSender to, String difficulty, String pvp) {
        WorldState.Settings cur = plugin.worldState().get();
        String d = difficulty != null ? WorldState.normalize(difficulty) : cur != null ? cur.difficulty() : plugin.cfg().difficultyDefault;
        boolean on = pvp != null ? List.of("on", "true", "1").contains(pvp.toLowerCase(Locale.ROOT))
                : cur != null ? cur.pvp() : plugin.cfg().pvp.def();
        if (!plugin.cfg().difficulties.containsKey(d) || (pvp != null && !List.of("on", "off", "true", "false", "1", "0").contains(pvp.toLowerCase(Locale.ROOT)))) {
            Lang.tell(to, "admin.settings-unknown", "value", difficulty != null ? difficulty : pvp);
            return 0;
        }
        Player viewer = to instanceof Player pl ? pl : null;
        plugin.start().chooseSettings(viewer, d, on, "command");
        Component name = Lang.c(viewer, "difficulty." + d + ".name"); // lang-dyn: difficulty.*.name
        Component pv = on ? Lang.c(viewer, "pvp.on") : Lang.c(viewer, "pvp.off");
        Lang.tell(to, "admin.settings-set", "difficulty", name, "pvp", pv);
        return Command.SINGLE_SUCCESS;
    }

    private static int info(Souls plugin, CommandSender to) {
        WorldState.Settings s = plugin.worldState().get();
        to.sendMessage(Component.text("settings " + (s == null ? "none" : s.line()), NamedTextColor.GRAY)); // lang-machine: 점검 줄
        return Command.SINGLE_SUCCESS;
    }

    private static int originReset(Souls plugin, CommandSender to, String name, boolean keepItems) {
        Player t = Bukkit.getPlayerExact(name);
        if (t == null) {
            // 접속하지 않은 사람의 PDC 는 쓸 수 없다 (읽기만, 검토 T24)
            Lang.tell(to, "admin.no-player", "player", name);
            return 0;
        }
        int items = plugin.start().resetOrigin(t, to.getName(), keepItems);
        Lang.tell(to, "admin.origin-reset", "player", t.getName(), "items", String.valueOf(items));
        return Command.SINGLE_SUCCESS;
    }

    private static int souls(Souls plugin, CommandSender to, String name, String op, long n) {
        Player t = Bukkit.getPlayerExact(name);
        if (t == null) {
            Lang.tell(to, "admin.no-player", "player", name);
            return 0;
        }
        if ("add".equals(op)) plugin.purse().add(t, n);
        else if ("set".equals(op)) plugin.purse().set(t, n);
        else {
            Lang.tell(to, "admin.settings-unknown", "value", op);
            return 0;
        }
        plugin.profiles().save(t, true);
        plugin.getLogger().info("소울: " + t.getName() + " " + op + " " + n + " → " + plugin.purse().get(t) + " (by " + to.getName() + ")");
        plugin.test(t, "SOULS n=" + plugin.purse().get(t) + " via=command");
        Lang.tell(to, "admin.souls-set", "player", t.getName(), "souls", String.valueOf(plugin.purse().get(t)));
        return Command.SINGLE_SUCCESS;
    }

    private static int profileDump(Souls plugin, CommandSender to, String name) {
        Player t = Bukkit.getPlayerExact(name);
        if (t == null) {
            Lang.tell(to, "admin.no-player", "player", name);
            return 0;
        }
        String json = plugin.profiles().of(t).toJson();
        plugin.getLogger().info("프로필 " + t.getName() + ": " + json);
        to.sendMessage(Component.text("profile " + t.getName() + " " + json, NamedTextColor.GRAY)); // lang-machine: 점검 줄
        return Command.SINGLE_SUCCESS;
    }

    static Entity target(CommandContext<CommandSourceStack> ctx) {
        Entity e = ctx.getSource().getExecutor();
        return e != null ? e : ctx.getSource().getSender() instanceof Player p ? p : null;
    }

    private static int help(CommandSender to) {
        String usage = "/souls check | perf | reload | tp <room|lane|slab|ledge|lobby> | build room | pack [resend] | " // lang-machine: 쓰는 법
                + "settings [difficulty <id> | pvp <on|off>] | origin reset <player> [keep-items] | souls <player> set|add <n> | profile dump <player>"; // lang-machine
        to.sendMessage(Component.text(usage, NamedTextColor.GRAY));
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
        boolean magic = RegistryAccess.registryAccess().getRegistry(RegistryKey.DAMAGE_TYPE).get(Key.key(Keys.NS, "magic")) != null;
        line(to, fails, magic, "damage_type souls:magic" + (magic ? " present" : " missing"));
        // 최대 HP 상한 (spigot.yml settings.attribute.maxHealth.max): 체력 99 의 최대 HP 가 들어가야 한다 (5.2)
        double cap = plugin.maxHealthCap(), need = plugin.cfg().stats.maxHealth.at(plugin.cfg().stats.max);
        line(to, fails, cap >= need, String.format(Locale.ROOT, "max health cap %.0f (need %.0f for vigor %d)", cap, need, plugin.cfg().stats.max));
        WorldState.Settings st = plugin.worldState().get();
        line(to, fails, true, "world settings " + (st == null ? "none (asked on first join)" : st.line()));
        line(to, fails, !plugin.origins().all().isEmpty(), "origins " + plugin.origins().all().size() + " "
                + plugin.origins().all().stream().map(o -> o.id()).toList());
        WorldService ws = plugin.worlds();
        World game = ws.world();
        line(to, fails, game != null, "world " + plugin.cfg().world.name() + (game != null ? " loaded" : " missing"));
        for (World w : game == null ? List.of(ws.lobby()) : List.of(ws.lobby(), game)) {
            line(to, fails, w.getDifficulty() == Difficulty.NORMAL, "difficulty " + w.getName() + "=" + w.getDifficulty());
            List<String> bad = ws.ruleMismatches(w);
            line(to, fails, bad.isEmpty(), "gamerules " + w.getName() + " " + (bad.isEmpty() ? ws.rules().size() + " ok" : bad)
                    + " (pvp=" + w.getGameRuleValue(org.bukkit.GameRules.PVP) + ", settings " + plugin.pvp().enabled() + ")");
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
        // YOU DIED 는 한 번만 (5.6): 팩의 사망 화면 제목, 서서히 나타나는 문구 줄 (팩의 제목이 비었고 death.title 이 꺼짐),
        // 플러그인 화면 제목 가운데 하나만 쓴다. 문구 줄은 팩을 따르므로 설정 death.screen-fade 와 팩이 어긋나면 알린다
        if (pk.ready()) {
            String screen = pk.packLang("en_us", "deathScreen.title");
            boolean onScreen = screen != null && !screen.isEmpty();
            boolean byPlugin = plugin.cfg().death.title();
            boolean fade = !byPlugin && pk.deathTitleBlank();
            boolean fadeGlyph = Glyphs.deathFadeLine(0) != null;
            boolean cfgFade = plugin.cfg().death.screenFade();
            line(to, fails, (onScreen != byPlugin || fade) && !(onScreen && fade) && (!fade || fadeGlyph)
                            && (byPlugin || cfgFade == fade),
                    "death title " + (onScreen && byPlugin ? "both (overlap)" : onScreen ? "death screen only"
                            : byPlugin ? "plugin title only" : fade ? "fading death screen line" + (fadeGlyph ? "" : " (glyphs missing)")
                            : "none (vanilla text or blank)")
                    + " (pack deathScreen.title=" + (screen == null ? "missing" : screen.isEmpty() ? "blank" : screen.length() + " chars")
                    + ", death.title=" + byPlugin + ", death.screen-fade=" + cfgFade
                    + (!byPlugin && cfgFade != fade ? ": config and pack disagree, rebuild the pack" : "") + ")");
        }
        line(to, fails, !plugin.skills().all().isEmpty(), "skills " + plugin.skills().all().size());
        // 문구 (10.3, 10.9): jar 안 lang/*.yml 의 열쇠와 jar 안 팩의 souls 언어 파일 열쇠가 같다 (낡은 팩 거르기)
        if (pk.ready()) {
            Set<String> want = new TreeSet<>();
            for (String k : Lang.keys()) want.add(Lang.PREFIX + k);
            // 팩이 갈래마다 짠 열쇠 (Lang.variant): 무기 설명 칸 실선 weapon.rule.<무기 id> (item/StatTable.rule, pack/typeset.py)
            for (String id : plugin.weapons().all().keySet()) want.add(Lang.PREFIX + "weapon.rule." + id);
            // 반지 설명 칸 실선 ring.rule.<반지 id> (item/Rings.lore)
            for (String id : plugin.rings().all().keySet()) want.add(Lang.PREFIX + "ring.rule." + id);
            // 표의 칸 (Lang.cell / rcell): 능력치·출신 창의 열 맞추기 (pack/typeset.py 의 CELLS)
            for (String k : Lang.cellKeys()) want.add(Lang.PREFIX + k);
            // 갈래 제목 (Lang.titled): 출신 확인 창 제목 origin.confirm-title.<출신 id> (pack/typeset.py 의 TITLE_VARIANTS)
            for (var o : plugin.origins().all()) {
                if (Lang.has("origin." + o.id() + ".name")) want.add(Lang.PREFIX + "origin.confirm-title." + o.id());
            }
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
        // 구르는 중이면 대역(탑승물)을 먼저 내린다: Paper 는 탑승물이 있으면 다른 세계로 옮기지 않는다
        plugin.roll().release(p);
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
