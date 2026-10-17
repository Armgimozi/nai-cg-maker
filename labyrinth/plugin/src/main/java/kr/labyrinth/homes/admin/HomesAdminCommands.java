package kr.labyrinth.homes.admin;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.builder.RequiredArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Teleports;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.HomesApi;
import kr.labyrinth.homes.HomesResult;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotInfo;
import kr.labyrinth.homes.rules.ClaimRules;
import kr.labyrinth.homes.rules.Grace;
import kr.labyrinth.homes.rules.TerrainLock;
import org.bukkit.Bukkit;
import org.bukkit.HeightMap;
import org.bukkit.Location;
import org.bukkit.OfflinePlayer;
import org.bukkit.World;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * {@code /labadmin plot …} (0.3.7, plan §6·§11 · review R18). 소유: 묶음 B.
 * <pre>
 * list · info [번지|이름] · tp &lt;번지&gt; · give &lt;번지&gt; &lt;이름&gt; · reclaim &lt;번지|이름&gt; ·
 * convert &lt;이름&gt; &lt;x1&gt; &lt;z1&gt; &lt;x2&gt; &lt;z2&gt; [y1 y2] · unconvert &lt;번지&gt; · lock [auto|on|off] · grace &lt;일&gt; · legacy ·
 * name &lt;번지&gt; [글] · parcel &lt;이름&gt; [give] · selftest
 * </pre>
 * 명령은 한 번만 등록되므로 실행할 때마다 지금의 {@code services.homes()} 를 쓴다 (모듈을 다시 켜도 새 서비스로).
 */
public final class HomesAdminCommands {

    private final HomesService service;

    public HomesAdminCommands(HomesService service) { this.service = service; }

    HomesService service() { return service; }

    /** 지금 켜진 집 서비스 (모듈을 다시 켰으면 새 것). */
    private HomesService svc() {
        try {
            HomesApi h = Services.get().homes();
            if (h instanceof HomesService hs) return hs;
        } catch (IllegalStateException ignored) {
            // 플러그인이 아직 안 켜짐
        }
        return service;
    }

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    private SuggestionProvider<CommandSourceStack> plotIds() {
        return (ctx, b) -> {
            for (PlotGeom p : svc().plots()) if (p.id().startsWith(b.getRemainingLowerCase())) b.suggest(p.id());
            return b.buildFuture();
        };
    }

    private static SuggestionProvider<CommandSourceStack> players() {
        return (ctx, b) -> {
            for (Player p : Bukkit.getOnlinePlayers()) if (p.getName().toLowerCase(java.util.Locale.ROOT).startsWith(b.getRemainingLowerCase())) b.suggest(p.getName());
            return b.buildFuture();
        };
    }

    private static RequiredArgumentBuilder<CommandSourceStack, String> word(String name) {
        return Commands.argument(name, StringArgumentType.word());
    }

    private static RequiredArgumentBuilder<CommandSourceStack, Integer> num(String name) {
        return Commands.argument(name, IntegerArgumentType.integer());
    }

    public void register(CommandService cmd) {
        LiteralArgumentBuilder<CommandSourceStack> m = Commands.literal("plot");
        m.executes(ctx -> run(ctx, () -> help(ctx.getSource().getSender())));
        m.then(Commands.literal("list").executes(ctx -> run(ctx, () -> list(ctx.getSource().getSender()))));
        m.then(Commands.literal("info")
                .executes(ctx -> run(ctx, () -> info(ctx.getSource().getSender(), null)))
                .then(word("target").suggests(plotIds()).executes(ctx -> run(ctx, () -> info(ctx.getSource().getSender(),
                        StringArgumentType.getString(ctx, "target"))))));
        m.then(Commands.literal("tp").then(word("plot").suggests(plotIds()).executes(ctx -> run(ctx,
                () -> tp(CommandService.sender(ctx), StringArgumentType.getString(ctx, "plot"))))));
        m.then(Commands.literal("give").then(word("plot").suggests(plotIds()).then(word("name").suggests(players()).executes(ctx -> run(ctx,
                () -> give(ctx.getSource().getSender(), StringArgumentType.getString(ctx, "plot"), StringArgumentType.getString(ctx, "name")))))));
        m.then(Commands.literal("reclaim").then(word("target").suggests(plotIds()).executes(ctx -> run(ctx,
                () -> reclaim(ctx.getSource().getSender(), StringArgumentType.getString(ctx, "target"))))));
        RequiredArgumentBuilder<CommandSourceStack, Integer> z2 = num("z2").executes(ctx -> run(ctx, () -> convert(ctx, null, null)));
        z2.then(num("y1").then(num("y2").executes(ctx -> run(ctx,
                () -> convert(ctx, IntegerArgumentType.getInteger(ctx, "y1"), IntegerArgumentType.getInteger(ctx, "y2"))))));
        m.then(Commands.literal("convert").then(word("name").suggests(players()).then(num("x1").then(num("z1").then(num("x2").then(z2))))));
        m.then(Commands.literal("unconvert").then(word("plot").suggests(plotIds()).executes(ctx -> run(ctx,
                () -> reply(ctx.getSource().getSender(), svc().unconvert(svc().plot(StringArgumentType.getString(ctx, "plot"))))))));
        LiteralArgumentBuilder<CommandSourceStack> lock = Commands.literal("lock").executes(ctx -> run(ctx, () -> lockInfo(ctx.getSource().getSender())));
        for (String st : new String[] {"auto", "on", "off"}) {
            lock.then(Commands.literal(st).executes(ctx -> run(ctx, () -> reply(ctx.getSource().getSender(), svc().setLock(TerrainLock.State.of(st))))));
        }
        m.then(lock);
        m.then(Commands.literal("grace").executes(ctx -> run(ctx, () -> lockInfo(ctx.getSource().getSender())))
                .then(Commands.argument("days", IntegerArgumentType.integer(0, 365)).executes(ctx -> run(ctx,
                        () -> reply(ctx.getSource().getSender(), svc().setGraceDays(IntegerArgumentType.getInteger(ctx, "days")))))));
        m.then(Commands.literal("legacy").executes(ctx -> run(ctx, () -> {
            CommandSender s = ctx.getSource().getSender();
            if (!svc().legacy().start(s)) Text.error(s, "조사가 이미 돌고 있습니다.");
        })));
        m.then(Commands.literal("name").then(word("plot").suggests(plotIds())
                .executes(ctx -> run(ctx, () -> reply(ctx.getSource().getSender(), svc().adminRename(svc().plot(StringArgumentType.getString(ctx, "plot")), ""))))
                .then(Commands.argument("text", StringArgumentType.greedyString()).executes(ctx -> run(ctx, () -> reply(ctx.getSource().getSender(),
                        svc().adminRename(svc().plot(StringArgumentType.getString(ctx, "plot")), StringArgumentType.getString(ctx, "text"))))))));
        m.then(Commands.literal("parcel").then(word("name").suggests(players())
                .executes(ctx -> run(ctx, () -> parcel(ctx.getSource().getSender(), StringArgumentType.getString(ctx, "name"), false)))
                .then(Commands.literal("give").executes(ctx -> run(ctx,
                        () -> parcel(ctx.getSource().getSender(), StringArgumentType.getString(ctx, "name"), true))))));
        m.then(Commands.literal("selftest").executes(ctx -> run(ctx, () -> {
            CommandSender s = ctx.getSource().getSender();
            for (String line : svc().selfTestLines()) Text.send(s, "<gray>" + Text.escape(line));
        })));
        cmd.addSubcommand("labadmin", m);
    }

    private static void reply(CommandSender s, HomesResult r) {
        if (r.ok()) Text.send(s, "<gray>" + r.message());
        else Text.error(s, r.message());
    }

    private void help(CommandSender s) {
        Text.send(s, "<gray>/labadmin plot <white>list</white> · <white>info [번지|이름]</white> · <white>tp <번지></white> · <white>give <번지> <이름></white> · "
                + "<white>reclaim <번지|이름></white> · <white>convert <이름> <x1> <z1> <x2> <z2> [y1 y2]</white> · <white>unconvert <번지></white> · "
                + "<white>lock [auto|on|off]</white> · <white>grace <일></white> · <white>legacy</white> · <white>name <번지> [글]</white> · "
                + "<white>parcel <이름> [give]</white> · <white>selftest</white>");
    }

    // ── 보기 ─────────────────────────────────────────────────────────────

    private void list(CommandSender s) {
        HomesService h = svc();
        List<PlotGeom> all = h.plots();
        Text.send(s, "<#ffd36b>집</#ffd36b> <gray>집 구역 " + h.district().state() + " · 집터 " + all.size() + " · 주인 있음 " + countOwned(h) + " · "
                + lockLine(h));
        int inactive = h.config().inactiveDays();
        for (PlotGeom p : all) {
            PlotInfo i = h.info(p);
            if (i.vacant()) {
                Text.send(s, "<gray> " + p.label() + " · <green>비어 있음</green>" + (h.busy(p) ? " · 정리 중" : ""));
                continue;
            }
            String seen = seen(i.ownerLastSeen());
            boolean old = inactive > 0 && i.ownerLastSeen() > 0 && System.currentTimeMillis() - i.ownerLastSeen() > inactive * Grace.DAY_MS;
            Text.send(s, "<gray> " + p.label() + " · <white>" + Text.escape(i.ownerName()) + "</white> (" + Text.escape(i.name()) + ") · 초대 "
                    + i.trusted().size() + " · 손님 " + (i.guests() ? "켬" : "끔") + " · 마지막 접속 " + seen
                    + (old ? " <#ff9b6b>(" + inactive + "일 넘음)</#ff9b6b>" : "") + (h.busy(p) ? " · 정리 중" : ""));
        }
        int parcels = h.parcels().owners().size();
        if (parcels > 0) Text.send(s, "<gray> 맡긴 짐이 있는 사람 " + parcels + "명 · /labadmin plot parcel <이름>");
    }

    private static int countOwned(HomesService h) {
        int n = 0;
        for (PlotGeom p : h.plots()) if (h.ownerOf(p) != null) n++;
        return n;
    }

    private static String lockLine(HomesService h) {
        int left = h.graceDaysLeft();
        return "지형 잠금 " + h.lockState() + (left > 0 ? " · 이사 기간 " + left + "일 남음" : "");
    }

    private void lockInfo(CommandSender s) {
        HomesService h = svc();
        Grace g = h.grace();
        Text.send(s, "<gray>" + lockLine(h) + " · 기간 " + g.days() + "일" + (g.startedAt() > 0 ? "" : " (잠금이 켜지면 시작)")
                + (h.config().terrainLock() ? "" : " · config homes.terrain_lock: false"));
    }

    private static String seen(long at) {
        if (at <= 0) return "모름";
        long d = System.currentTimeMillis() - at;
        if (d < 60_000) return "지금";
        Duration du = Duration.ofMillis(d);
        if (du.toDays() >= 1) return du.toDays() + "일 전";
        if (du.toHours() >= 1) return du.toHours() + "시간 전";
        return du.toMinutes() + "분 전";
    }

    /** 번지 또는 주인 이름 → 집터. */
    private PlotGeom target(String t) {
        HomesService h = svc();
        PlotGeom p = h.plot(t.replace("번지", ""));
        if (p != null) return p;
        OfflinePlayer op = HomesService.findPlayer(t);
        return op == null ? null : h.homeOf(op.getUniqueId());
    }

    private void info(CommandSender s, String t) {
        HomesService h = svc();
        PlotGeom p;
        if (t == null) {
            if (!(s instanceof Player pl)) {
                Text.error(s, "번지나 이름을 주세요.");
                return;
            }
            Location l = pl.getLocation();
            p = h.columnPlot(l.getWorld(), l.getBlockX(), l.getBlockZ());
            if (p == null) p = h.homeOf(pl.getUniqueId());
        } else p = target(t);
        if (p == null) {
            Text.error(s, "그 집터를 찾지 못했습니다" + (t == null ? " (집터 안에 서 있거나 번지를 주세요)." : ": " + Text.escape(t)));
            return;
        }
        PlotInfo i = h.info(p);
        Text.send(s, "<#ffd36b>" + p.label() + "</#ffd36b> <gray>x " + p.x0() + ".." + p.x1() + " · z " + p.z0() + ".." + p.z1() + " · 바닥 " + p.floorY()
                + " · 짓기 " + p.yMin() + ".." + p.yMax() + (p.custom() ? " · convert" : " · 대문 " + p.front()) + (h.busy(p) ? " · 정리 중" : ""));
        if (i.vacant()) {
            Text.send(s, "<gray> 비어 있음");
            return;
        }
        Text.send(s, "<gray> 주인 <white>" + Text.escape(i.ownerName()) + "</white> · 이름 " + Text.escape(i.name()) + " · 손님 " + (i.guests() ? "켬" : "끔")
                + " · 받은 날 " + seen(i.claimedAt()) + " · 마지막 접속 " + seen(i.ownerLastSeen()));
        Text.send(s, "<gray> 초대 " + i.trusted().size() + "명" + (i.trustedNames().isEmpty() ? "" : ": " + Text.escape(String.join(", ", i.trustedNames()))));
    }

    // ── 일 ───────────────────────────────────────────────────────────────

    private void tp(CommandSender s, String id) {
        if (!(s instanceof Player p)) {
            Text.error(s, "플레이어만 쓸 수 있습니다.");
            return;
        }
        HomesService h = svc();
        PlotGeom plot = target(id);
        World w = h.mainWorld();
        if (plot == null || w == null) {
            Text.error(s, "그 집터를 찾지 못했습니다: " + Text.escape(id));
            return;
        }
        Location to;
        if (plot.homeKnown()) to = new Location(w, plot.homeX(), plot.homeY(), plot.homeZ(), plot.homeYaw(), 0f);
        else {
            int cx = (plot.x0() + plot.x1()) / 2, cz = (plot.z0() + plot.z1()) / 2;
            to = new Location(w, cx + 0.5, w.getHighestBlockYAt(cx, cz, HeightMap.MOTION_BLOCKING_NO_LEAVES) + 1, cz + 0.5);
        }
        p.setFallDistance(0);
        Teleports.to(p, to);
        Text.send(p, "<gray>" + plot.label() + "로 왔습니다.");
    }

    private void give(CommandSender s, String id, String name) {
        HomesService h = svc();
        reply(s, h.adminGive(h.plot(id.replace("번지", "")), HomesService.findPlayer(name)));
    }

    private void reclaim(CommandSender s, String t) {
        HomesService h = svc();
        PlotGeom p = target(t);
        if (p == null || h.ownerOf(p) == null) {
            Text.error(s, "주인이 있는 집터를 찾지 못했습니다: " + Text.escape(t));
            return;
        }
        PlotInfo i = h.info(p);
        Text.send(s, "<gray>" + ClaimRules.object(p) + " 회수합니다 — 짐은 " + Text.escape(i.ownerName()) + "님의 맡긴 짐으로.");
        h.adminReclaim(p).thenAccept(ok -> Bukkit.getScheduler().runTask(h.plugin(), () -> {
            if (ok) Text.send(s, "<gray>" + ClaimRules.object(p) + " 회수했습니다." + (p.custom() ? " (convert 집: 소유만 풀고 블록은 그대로)" : ""));
            else Text.error(s, ClaimRules.object(p) + " 회수하지 못했습니다 (로그를 보세요).");
            Player op = Bukkit.getPlayer(i.owner());
            if (ok && op != null) Text.send(op, "<gray>관리자가 " + ClaimRules.object(p) + " 회수했습니다." + (p.custom() ? "" : " 집 안 물건은 맡긴 짐에 있습니다 — <white>/미궁 집 짐</white>"));
        }));
    }

    private void convert(CommandContext<CommandSourceStack> ctx, Integer y1, Integer y2) {
        CommandSender s = ctx.getSource().getSender();
        HomesService h = svc();
        OfflinePlayer target = HomesService.findPlayer(StringArgumentType.getString(ctx, "name"));
        if (target == null) {
            Text.error(s, "그 플레이어를 찾지 못했습니다.");
            return;
        }
        World w = h.mainWorld();
        if (w == null) return;
        int ax = IntegerArgumentType.getInteger(ctx, "x1"), az = IntegerArgumentType.getInteger(ctx, "z1");
        int bx = IntegerArgumentType.getInteger(ctx, "x2"), bz = IntegerArgumentType.getInteger(ctx, "z2");
        int gMin = Integer.MAX_VALUE, gMax = Integer.MIN_VALUE;
        if (y1 == null) {
            for (int x = Math.min(ax, bx); x <= Math.max(ax, bx) && x - Math.min(ax, bx) < 64; x++) {
                for (int z = Math.min(az, bz); z <= Math.max(az, bz) && z - Math.min(az, bz) < 64; z++) {
                    int y = w.getHighestBlockYAt(x, z, HeightMap.MOTION_BLOCKING_NO_LEAVES);
                    gMin = Math.min(gMin, y);
                    gMax = Math.max(gMax, y);
                }
            }
        }
        ConvertRules.Box box = ConvertRules.check(ax, az, bx, bz, y1, y2, gMin == Integer.MAX_VALUE ? 64 : gMin, gMax == Integer.MIN_VALUE ? 64 : gMax,
                w.getMinHeight(), w.getMaxHeight() - 1);
        if (!box.ok()) {
            Text.error(s, box.error());
            return;
        }
        int cx = (box.x0() + box.x1()) / 2, cz = (box.z0() + box.z1()) / 2;
        double hy = Math.min(box.y1(), w.getHighestBlockYAt(cx, cz, HeightMap.MOTION_BLOCKING_NO_LEAVES) + 1);
        reply(s, h.convert(target, box.x0(), box.z0(), box.x1(), box.z1(), box.y0(), box.y1(), box.floorY(), cx + 0.5, hy, cz + 0.5));
    }

    private void parcel(CommandSender s, String name, boolean give) {
        HomesService h = svc();
        OfflinePlayer op = HomesService.findPlayer(name);
        if (op == null) {
            Text.error(s, "그 플레이어를 찾지 못했습니다: " + Text.escape(name));
            return;
        }
        UUID u = op.getUniqueId();
        if (give) {
            Player p = op instanceof Player pl && pl.isOnline() ? pl : null;
            if (p == null) {
                Text.error(s, Text.escape(name) + "님이 접속해 있어야 돌려줄 수 있습니다.");
                return;
            }
            HomesResult r = h.takeParcel(p);
            reply(s, r);
            if (r.ok()) Text.send(p, "<gray>관리자가 맡긴 짐을 돌려주었습니다. " + r.message());
            return;
        }
        List<ItemStack> items = h.parcel(u);
        Text.send(s, "<gray>" + Text.escape(name) + "님의 맡긴 짐: " + items.size() + "묶음" + (h.parcels().pending(u) != null ? " · 비우는 중 하나 있음" : "")
                + (items.isEmpty() ? "" : " · 돌려주기: /labadmin plot parcel " + Text.escape(name) + " give"));
        int shown = 0;
        for (ItemStack it : items) {
            if (shown++ >= 12) {
                Text.send(s, "<gray> … " + (items.size() - 12) + "묶음 더");
                break;
            }
            Text.send(s, "<gray> " + it.getType().name().toLowerCase(java.util.Locale.ROOT) + " ×" + it.getAmount());
        }
    }
}
