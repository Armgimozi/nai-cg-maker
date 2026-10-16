package kr.labyrinth.village;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import java.io.File;
import java.util.Locale;
import java.util.Map;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

/**
 * 명령: /미궁 마을 (/lab village, /lab 마을) — 광장으로 텔레포트.
 * 관리자 (콘솔 가능): /labadmin village build [here | &lt;x&gt; &lt;z&gt;] [north|east|south|west] [force] · info · dump ·
 * survey [반경] · pregen &lt;반경&gt; · selftest · apply · cancel  (VILLAGE.md §4.1 · §4.4)
 * · /labadmin wild [info] · selftest · reasons · border apply  (야생 막기, 0.3.5.1)
 * · /labadmin village district [info|preview|build|remove|selftest] mine [east|south_east|here [방향]]  (광산 마을, 0.3.6.1)
 */
final class VillageCommands {

    private final VillageModule module;

    VillageCommands(VillageModule module) { this.module = module; }

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    void register() {
        CommandService cmd = module.services().commands();
        for (String name : new String[] {"village", "마을"}) {
            cmd.addSubcommand("lab", Commands.literal(name).executes(ctx -> run(ctx,
                    () -> CommandService.withPlayer(CommandService.sender(ctx), VillageService::teleportCommand))));
        }
        LiteralArgumentBuilder<CommandSourceStack> v = Commands.literal("village");
        v.executes(ctx -> run(ctx, () -> help(ctx.getSource().getSender())));
        v.then(Commands.literal("build")
                .executes(ctx -> run(ctx, () -> build(CommandService.sender(ctx), "")))
                .then(Commands.argument("args", StringArgumentType.greedyString())
                        .suggests((c, b) -> {
                            for (String s : new String[] {"here", "north", "east", "south", "west", "force"}) b.suggest(s);
                            return b.buildFuture();
                        })
                        .executes(ctx -> run(ctx, () -> build(CommandService.sender(ctx), StringArgumentType.getString(ctx, "args"))))));
        v.then(Commands.literal("info").executes(ctx -> run(ctx, () -> info(ctx.getSource().getSender()))));
        v.then(Commands.literal("dump").executes(ctx -> run(ctx, () -> dump(ctx.getSource().getSender()))));
        v.then(Commands.literal("survey")
                .executes(ctx -> run(ctx, () -> survey(ctx.getSource().getSender(), 160)))
                .then(Commands.argument("radius", IntegerArgumentType.integer(16, 1024))
                        .executes(ctx -> run(ctx, () -> survey(ctx.getSource().getSender(), IntegerArgumentType.getInteger(ctx, "radius"))))));
        v.then(Commands.literal("pregen")
                .then(Commands.argument("radius", IntegerArgumentType.integer(16, 2048))
                        .executes(ctx -> run(ctx, () -> pregen(ctx.getSource().getSender(), IntegerArgumentType.getInteger(ctx, "radius"))))));
        v.then(Commands.literal("selftest").executes(ctx -> run(ctx, () -> selftest(ctx.getSource().getSender()))));
        v.then(Commands.literal("apply").executes(ctx -> run(ctx, () -> apply(ctx.getSource().getSender()))));
        v.then(districtCommands());
        v.then(Commands.literal("cancel").executes(ctx -> run(ctx, () -> {
            CommandSender s = ctx.getSource().getSender();
            if (VillageJob.cancelRunning()) Text.send(s, "<gray>마을 작업 취소 요청");
            else Text.error(s, "진행 중인 마을 작업이 없습니다.");
        })));
        cmd.addSubcommand("labadmin", v);

        // 야생 막기 (0.3.5.1, config wild)
        LiteralArgumentBuilder<CommandSourceStack> w = Commands.literal("wild");
        w.executes(ctx -> run(ctx, () -> wildInfo(ctx.getSource().getSender())));
        w.then(Commands.literal("info").executes(ctx -> run(ctx, () -> wildInfo(ctx.getSource().getSender()))));
        w.then(Commands.literal("selftest").executes(ctx -> run(ctx, () -> wildSelftest(ctx.getSource().getSender()))));
        w.then(Commands.literal("reasons").executes(ctx -> run(ctx, () -> wildReasons(ctx.getSource().getSender()))));
        w.then(Commands.literal("border").then(Commands.literal("apply").executes(ctx -> run(ctx, () -> {
            WildService ws = module.service().wild();
            if (ws == null) Text.error(ctx.getSource().getSender(), "야생 막기가 꺼져 있습니다.");
            else ws.forceBorder(ctx.getSource().getSender());
        }))));
        cmd.addSubcommand("labadmin", w);
    }

    private void wildInfo(CommandSender s) {
        WildService ws = module.service().wild();
        if (ws == null) {
            Text.error(s, "야생 막기가 꺼져 있습니다.");
            return;
        }
        ws.info(s);
        s.sendMessage(Text.mm(" <dark_gray>/labadmin wild selftest · reasons · border apply"));
    }

    private void wildSelftest(CommandSender s) {
        WildService ws = module.service().wild();
        if (ws == null || !ws.active()) {
            Text.error(s, "이 월드에는 마을이 없습니다 — 야생 막기가 꺼져 있습니다.");
            return;
        }
        new WildSelfTest(module, s, mainWorld()).start();
    }

    /** SpawnReason 마다 막음/허용과 이유 (WildSpawns). */
    private void wildReasons(CommandSender s) {
        Text.send(s, "<gold>마을 월드 스폰 이유</gold> <gray>(막음 = wild.spawns 범위 안의 몹일 때)");
        for (org.bukkit.event.entity.CreatureSpawnEvent.SpawnReason r : org.bukkit.event.entity.CreatureSpawnEvent.SpawnReason.values()) {
            WildSpawns.Rule rule = WildSpawns.rule(r);
            String tag = switch (rule.verdict()) {
                case WILD -> "<#ff9a4d>막음";
                case ACTION -> "<#7fe07f>허용";
                case KEEP_SOURCE -> "<#7fd8ff>허용(변신)";
            };
            s.sendMessage(Text.mm(" " + tag + " <white>" + r.name() + "</white> <dark_gray>— <gray>" + Text.escape(rule.why())));
        }
    }

    static void help(CommandSender s) {
        Text.send(s, "<gold>마을 관리 명령</gold> <gray>(개발용 — 배포 월드는 미리 지어 둠)");
        String[][] lines = {
                {"village build [here | <x> <z>] [방향] [force]", "지형 맞춰 마을 짓기 (자리·방향 생략 = 자동)"},
                {"village survey [반경]", "시드 고르기: 지형을 가장 덜 바꾸는 자리·방향 5곳"},
                {"village selftest", "지은 뒤 검사 (청사진·겹침·떠 있는 지형·나무·정문·NPC)"},
                {"village info · dump · pregen <반경> · apply · cancel", "정보 · 블록 덤프 · 청크 미리 생성 · 다시 적용 · 작업 취소"},
                {"wild [info] · wild selftest · wild reasons · wild border apply", "야생 막기: 경계·스폰 상태 · 점검 · 스폰 이유 표 · 마을 경계로 덮어쓰기"},
                {"village district info|preview|build|remove|selftest mine [자리]", "광산 마을: 상태 · 미리 보기(안 바꿈) · 짓기 · 되돌리기 · 점검 (자리 = east · south_east · here [방향])"},
        };
        for (String[] l : lines) s.sendMessage(Text.mm(" <white>/labadmin " + Text.escape(l[0]) + "</white> <dark_gray>—</dark_gray> <gray>" + l[1]));
    }

    private World mainWorld() { return Bukkit.getWorlds().get(0); }

    private boolean needLibrary(CommandSender s) {
        VillageLibrary lib = module.library();
        if (lib == null || !lib.ok()) {
            Text.error(s, "마을 청사진이 없습니다: " + Text.escape(lib == null ? "-" : String.join(" · ", lib.problems)));
            return false;
        }
        return true;
    }

    // ── build ────────────────────────────────────────────────────────────

    private void build(CommandSender s, String args) {
        if (!needLibrary(s)) return;
        World w = mainWorld();
        Integer x = null, z = null, turns = null;
        boolean force = false;
        String[] a = args.trim().isEmpty() ? new String[0] : args.trim().split("\\s+");
        for (int i = 0; i < a.length; i++) {
            String t = a[i].toLowerCase(Locale.ROOT);
            if (t.equals("here")) {
                if (!(s instanceof Player p)) {
                    Text.error(s, "here 는 플레이어만 쓸 수 있습니다 (콘솔: <x> <z>)");
                    return;
                }
                if (!p.getWorld().equals(w)) {
                    Text.error(s, "마을은 주 월드(" + w.getName() + ")에만 지을 수 있습니다.");
                    return;
                }
                x = p.getLocation().getBlockX();
                z = p.getLocation().getBlockZ();
            } else if (t.equals("force")) {
                force = true;
            } else if (Dir.parse(t) != null) {
                turns = Dir.parse(t).turns();
            } else if (t.matches("-?\\d+") && i + 1 < a.length && a[i + 1].matches("-?\\d+")) {
                x = Integer.parseInt(t);
                z = Integer.parseInt(a[++i]);
            } else {
                Text.error(s, "알 수 없는 인자: " + Text.escape(a[i]) + " <gray>(here | <x> <z> | north|east|south|west | force)");
                return;
            }
        }
        File f = VillageService.metaFile(w);
        VillageMeta old = null;
        if (f.isFile()) {
            if (!force) {
                Text.error(s, "이 월드에는 이미 마을이 있습니다 (" + Text.escape(f.getName()) + "). 다시 지으려면 <white>build … force</white> (개발용)");
                return;
            }
            try {
                old = VillageMeta.load(f);
            } catch (Exception e) {
                Text.error(s, "예전 메타데이터를 읽지 못했습니다: " + Text.escape(e.getMessage()));
                return;
            }
            // force 는 자리·방향을 안 주면 예전 마을 자리·방향 그대로 다시 짓는다
            if (x == null) {
                x = old.center[0];
                z = old.center[2];
                if (turns == null) {
                    try {
                        turns = Rot.turns(org.bukkit.block.structure.StructureRotation.valueOf(old.rotation));
                    } catch (IllegalArgumentException ignored) {
                        // 방향 자동
                    }
                }
            }
        }
        new VillageBuilder(module, s, w, x, z, turns, force, old).start();
    }

    // ── info ─────────────────────────────────────────────────────────────

    private void info(CommandSender s) {
        VillageService svc = module.service();
        VillageLibrary lib = module.library();
        Text.send(s, "<gold>마을 정보</gold>");
        if (lib != null && lib.ok()) {
            s.sendMessage(Text.mm(" <gray>청사진: <white>" + Text.escape(lib.layout.name) + "</white> · 조각 " + lib.pieces.size() + "종 · 배치 "
                    + lib.layout.pieces.size() + " · 길 " + lib.layout.paths.size() + " · R " + lib.planner.inner + " + B " + lib.planner.blend
                    + (lib.problems.isEmpty() ? "" : " <#ff9a4d>· 문제 " + lib.problems.size())));
        } else {
            s.sendMessage(Text.mm(" <gray>청사진: <#ff6b6b>없음"));
        }
        VillageMeta m = svc == null ? null : svc.meta();
        if (m == null) {
            s.sendMessage(Text.mm(" <gray>이 월드에는 마을이 없습니다 <dark_gray>(서버팩의 world 폴더를 쓰거나 개발 중이면 village build)"));
            return;
        }
        s.sendMessage(Text.mm(" <gray>마을: <white>" + Text.escape(m.name) + "</white> · 중심 (" + m.center[0] + ", " + m.center[1] + ", " + m.center[2]
                + ") · 회전 " + m.rotation + " · 반경 " + m.radius + " · 조각 " + m.pieces.size() + " · 길 " + m.paths.size()
                + " · 보호 상자 " + m.protect.size()));
        s.sendMessage(Text.mm(" <gray>지은 때: <white>" + Text.escape(m.builtAt) + "</white> · build_id <white>" + Text.escape(m.buildId) + "</white> · 플러그인 " + Text.escape(m.pluginVersion)));
        String now = svc.applyKey(), applied = svc.appliedKey();
        s.sendMessage(Text.mm(" <gray>적용: " + (now.equals(applied) ? "<#7fe07f>이 월드에 적용됨" : "<#ff9a4d>아직 (다음 시작 때 또는 village apply)")
                + " <dark_gray>(" + Text.escape(svc.world().getUID().toString()) + ")"));
        if (m.spawn != null) s.sendMessage(Text.mm(" <gray>스폰: " + fmt(m.spawn) + " · 입구: " + (m.entrance == null ? "없음" : fmt(m.entrance))));
        var placed = module.services().npcs() instanceof kr.labyrinth.mobs.npc.NpcServiceImpl impl ? impl.placed() : Map.<String, Location>of();
        for (Map.Entry<String, VillageMeta.Pos> e : m.npcs.entrySet()) {
            Location at = placed.get(e.getKey());
            boolean ok = at != null && at.getWorld() != null && at.getWorld().equals(svc.world())
                    && at.distanceSquared(svc.loc(e.getValue())) < 1.0;
            s.sendMessage(Text.mm("  <dark_gray>-</dark_gray> <white>" + e.getKey() + "</white> " + fmt(e.getValue()) + " "
                    + (ok ? "<#7fe07f>배치됨" : "<#ff9a4d>자리 다름/없음")));
        }
        s.sendMessage(Text.mm(" <gray>우클릭 칸 " + m.interact.size() + " · 연출 " + m.ambient.size()));
        WildService ws = svc.wild();
        if (ws != null && ws.active()) {
            s.sendMessage(Text.mm(" <gray>야생 막기: <white>" + Text.escape(ws.summary()) + "</white> <dark_gray>(자세히: labadmin wild)"));
        }
    }

    private static String fmt(VillageMeta.Pos p) {
        return "<white>" + Math.round(p.x() * 10) / 10.0 + " " + Math.round(p.y() * 10) / 10.0 + " " + Math.round(p.z() * 10) / 10.0 + "</white>";
    }

    // ── 그 밖 ────────────────────────────────────────────────────────────

    private void dump(CommandSender s) {
        VillageMeta m = module.service().meta();
        if (m == null) {
            Text.error(s, "이 월드에는 마을이 없습니다.");
            return;
        }
        new VillageTools.Dump(module, s, mainWorld(), m).start();
    }

    private void survey(CommandSender s, int radius) {
        if (!needLibrary(s)) return;
        new VillageSurvey(module, s, mainWorld(), radius).start();
    }

    private void pregen(CommandSender s, int radius) {
        World w = mainWorld();
        VillageMeta m = module.service().meta();
        int cx = m != null ? m.center[0] : w.getSpawnLocation().getBlockX();
        int cz = m != null ? m.center[2] : w.getSpawnLocation().getBlockZ();
        new VillageTools.Pregen(module, s, w, cx, cz, radius).start();
    }

    private void selftest(CommandSender s) {
        if (!needLibrary(s)) return;
        World w = mainWorld();
        if (!VillageService.metaFile(w).isFile()) {
            Text.error(s, "이 월드에는 마을이 없습니다 — 자가 진단할 것이 없습니다.");
            return;
        }
        VillageSelfTest t = new VillageSelfTest(module, s, w);
        // 0.3.6.1: 광산 마을이 지어져 있으면 이어서 그 자가 진단도 (두 줄)
        DistrictService ds = module.service().districts();
        if (ds != null) {
            for (DistrictMeta d : ds.active()) {
                if (!d.built()) continue;
                String id = d.id;
                t.then(() -> new VillageSelfTest(module, s, w, id).start());
                break;
            }
        }
        t.start();
    }

    // ── 광산 마을 (구역, 0.3.6.1) ────────────────────────────────────────

    private LiteralArgumentBuilder<CommandSourceStack> districtCommands() {
        LiteralArgumentBuilder<CommandSourceStack> d = Commands.literal("district");
        d.executes(ctx -> run(ctx, () -> districtInfo(ctx.getSource().getSender(), "mine")));
        d.then(Commands.literal("info").executes(ctx -> run(ctx, () -> districtInfo(ctx.getSource().getSender(), "mine")))
                .then(Commands.argument("id", StringArgumentType.word()).suggests((c, b) -> suggestIds(b))
                        .executes(ctx -> run(ctx, () -> districtInfo(ctx.getSource().getSender(), StringArgumentType.getString(ctx, "id"))))));
        for (String verb : new String[] {"preview", "build"}) {
            d.then(Commands.literal(verb)
                    .executes(ctx -> run(ctx, () -> districtBuild(CommandService.sender(ctx), verb, "mine")))
                    .then(Commands.argument("args", StringArgumentType.greedyString())
                            .suggests((c, b) -> {
                                for (String x : new String[] {"mine", "mine east", "mine south_east", "mine here", "mine here east"}) b.suggest(x);
                                return b.buildFuture();
                            })
                            .executes(ctx -> run(ctx, () -> districtBuild(CommandService.sender(ctx), verb, StringArgumentType.getString(ctx, "args"))))));
        }
        d.then(Commands.literal("remove")
                .then(Commands.argument("id", StringArgumentType.word()).suggests((c, b) -> suggestIds(b))
                        .executes(ctx -> run(ctx, () -> districtRemove(ctx.getSource().getSender(), StringArgumentType.getString(ctx, "id"))))));
        d.then(Commands.literal("selftest")
                .executes(ctx -> run(ctx, () -> districtSelftest(ctx.getSource().getSender(), "mine")))
                .then(Commands.argument("id", StringArgumentType.word()).suggests((c, b) -> suggestIds(b))
                        .executes(ctx -> run(ctx, () -> districtSelftest(ctx.getSource().getSender(), StringArgumentType.getString(ctx, "id"))))));
        return d;
    }

    private java.util.concurrent.CompletableFuture<com.mojang.brigadier.suggestion.Suggestions> suggestIds(
            com.mojang.brigadier.suggestion.SuggestionsBuilder b) {
        if (module.districts() != null) for (String id : module.districts().ids()) b.suggest(id);
        return b.buildFuture();
    }

    private DistrictLibrary.Entry needDistrict(CommandSender s, String id) {
        DistrictLibrary lib = module.districts();
        DistrictLibrary.Entry e = lib == null ? null : lib.get(id);
        if (e == null) {
            Text.error(s, "그런 구역이 없습니다: " + Text.escape(id) + " <gray>(" + (lib == null ? "-" : String.join(" · ", lib.ids())) + ")");
            return null;
        }
        if (!e.ok()) {
            Text.error(s, "구역 청사진 문제: " + Text.escape(String.join(" · ", e.problems())));
            return null;
        }
        if (module.service().districts() == null || module.service().meta() == null) {
            Text.error(s, "이 월드에는 마을이 없습니다 — 광산 마을은 마을 큰길 끝에 붙여 짓습니다. 광산은 /미궁 광산 으로 그대로 됩니다.");
            return null;
        }
        return e;
    }

    private void districtInfo(CommandSender s, String id) {
        DistrictService ds = module.service().districts();
        if (ds == null) {
            Text.error(s, "마을 기능이 꺼져 있습니다.");
            return;
        }
        ds.info(s, id);
        s.sendMessage(Text.mm(" <dark_gray>/labadmin village district preview|build|remove|selftest " + Text.escape(id) + " [east|south_east|here [방향]]"));
    }

    /** preview|build &lt;id&gt; [east|south_east|here [방향]] — 자리를 안 주면 config 차례 (east → south_east). */
    private void districtBuild(CommandSender s, String verb, String args) {
        String[] a = args.trim().isEmpty() ? new String[] {"mine"} : args.trim().split("\\s+");
        DistrictLibrary.Entry e = needDistrict(s, a[0].toLowerCase(Locale.ROOT));
        if (e == null) return;
        DistrictService ds = module.service().districts();
        boolean preview = verb.equals("preview");
        if (!preview) {
            DistrictMeta cur = ds.get(e.id());
            String why = DistrictPolicy.canBuild(cur == null ? null : cur.state, module.service().meta() != null);
            if (why != null) {
                Text.error(s, why);
                return;
            }
        }
        java.util.List<DistrictJob.SiteReq> sites = new java.util.ArrayList<>();
        if (a.length >= 2) {
            String t = a[1].toLowerCase(Locale.ROOT);
            if (t.equals("here")) {
                if (!(s instanceof Player p) || !p.getWorld().equals(mainWorld())) {
                    Text.error(s, "here 는 주 월드(" + mainWorld().getName() + ")에 있는 플레이어만 쓸 수 있습니다");
                    return;
                }
                Dir dir = a.length >= 3 ? Dir.parse(a[2]) : facing(p);
                if (dir == null) {
                    Text.error(s, "방향은 north · east · south · west 중 하나");
                    return;
                }
                sites.add(DistrictJob.SiteReq.here(p.getLocation().getBlockX(), p.getLocation().getBlockZ(), dir));
            } else {
                DistrictLayout.Site site = e.layout().site(t);
                if (site == null) {
                    Text.error(s, "그런 자리가 없습니다: " + Text.escape(t) + " <gray>(" + String.join(" · ", e.layout().siteIds()) + " · here [방향])");
                    return;
                }
                sites.add(DistrictJob.SiteReq.of(site));
            }
        } else {
            sites.addAll(DistrictJob.configSites(e, module.districtConfig().sites()));
        }
        DistrictJob.command(module, s, ds, e, preview ? DistrictJob.Mode.PREVIEW : DistrictJob.Mode.BUILD, sites).start();
    }

    /** 플레이어가 보는 방향 (구역이 펼쳐질 쪽). */
    static Dir facing(Player p) {
        float yaw = Math.floorMod(Math.round(p.getLocation().getYaw()), 360);
        if (yaw >= 315 || yaw < 45) return Dir.SOUTH;
        if (yaw < 135) return Dir.WEST;
        if (yaw < 225) return Dir.NORTH;
        return Dir.EAST;
    }

    private void districtRemove(CommandSender s, String id) {
        DistrictLibrary.Entry e = needDistrict(s, id.toLowerCase(Locale.ROOT));
        if (e == null) return;
        DistrictService ds = module.service().districts();
        DistrictMeta cur = ds.get(e.id());
        String why = DistrictPolicy.canRemove(cur == null ? null : cur.state, DistrictService.backupFile(mainWorld(), e.id()).isFile());
        if (why != null) {
            Text.error(s, why);
            return;
        }
        DistrictJob.command(module, s, ds, e, DistrictJob.Mode.REMOVE, java.util.List.of()).start();
    }

    private void districtSelftest(CommandSender s, String id) {
        DistrictLibrary.Entry e = needDistrict(s, id.toLowerCase(Locale.ROOT));
        if (e == null) return;
        DistrictMeta cur = module.service().districts().get(e.id());
        if (cur == null || !cur.built()) {
            Text.error(s, "광산 마을이 지어져 있지 않습니다 — 자가 진단할 것이 없습니다.");
            return;
        }
        new VillageSelfTest(module, s, mainWorld(), e.id()).start();
    }

    private void apply(CommandSender s) {
        VillageService svc = module.service();
        if (svc.meta() == null) {
            Text.error(s, "이 월드에는 마을이 없습니다.");
            return;
        }
        svc.applyIfNew(true);
        Text.send(s, "<green>마을을 다시 적용했습니다</green> <gray>(NPC " + svc.meta().npcs.size() + "명 · 입구 = 마을 게이트)");
    }
}
