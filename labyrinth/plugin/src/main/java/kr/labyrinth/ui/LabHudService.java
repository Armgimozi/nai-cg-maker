package kr.labyrinth.ui;

import io.papermc.paper.scoreboard.numbers.NumberFormat;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.dungeon.DungeonService;
import kr.labyrinth.dungeon.InstanceContext;
import kr.labyrinth.stats.DerivedStats;
import net.kyori.adventure.bossbar.BossBar;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.scoreboard.Criteria;
import org.bukkit.scoreboard.DisplaySlot;
import org.bukkit.scoreboard.Objective;
import org.bukkit.scoreboard.Score;
import org.bukkit.scoreboard.Scoreboard;
import org.bukkit.scoreboard.Team;

/**
 * 미궁 HUD 실제 구현.
 * <ul>
 *   <li>액션바(초당 4회 검사, 값이 바뀌었을 때만 + 2초마다 유지 재전송): HP·MP·경험치 막대 + 레벨 + 골드 (글리프 / 텍스트 대체)</li>
 *   <li>사이드바(1초마다, 바뀐 줄만): 미궁 안 — 층·난이도·진행 방·타이머·사망·파티원 HP 미니 막대 / 대전 중 — 라운드·점수·타이머·양 팀 HP</li>
 *   <li>보스바: 다른 모듈이 key 로 띄우는 것 + 대전 라운드 타이머</li>
 *   <li>이름표 접두어: 플레이어마다 개인 스코어보드 → 대상별 팀 prefix (칭호)</li>
 * </ul>
 */
public final class LabHudService implements HudService, Listener {

    private static final int LINES = 15;
    private static final String OBJ = "lab_side";

    private final Services services;
    private final Map<UUID, Map<String, BossBar>> bars = new ConcurrentHashMap<>();
    private final Map<UUID, Long> overrideUntil = new ConcurrentHashMap<>();
    private final Map<UUID, String> lastKey = new HashMap<>();
    private final Map<UUID, Long> lastSent = new HashMap<>();
    private final Map<UUID, Scoreboard> boards = new HashMap<>();
    private final Map<UUID, String[]> lastLines = new HashMap<>();
    private final Map<UUID, Component> nameTags = new HashMap<>();
    private final Map<UUID, PvpHud> pvp = new HashMap<>();
    private final Map<UUID, Long> pvpAt = new HashMap<>();
    private final Map<UUID, BossBar> pvpBars = new HashMap<>();
    private BukkitTask task;
    private long tick;

    public LabHudService(Services services) { this.services = services; }

    public void start() {
        stop();
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        for (Player p : Bukkit.getOnlinePlayers()) board(p);
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tickAll, 10L, 5L);
    }

    public void stop() {
        if (task != null) task.cancel();
        task = null;
        HandlerList.unregisterAll(this);
        bars.forEach((u, m) -> {
            Player p = Bukkit.getPlayer(u);
            if (p != null) m.values().forEach(p::hideBossBar);
        });
        pvpBars.forEach((u, b) -> {
            Player p = Bukkit.getPlayer(u);
            if (p != null) p.hideBossBar(b);
        });
        bars.clear();
        pvpBars.clear();
        pvp.clear();
        Scoreboard main = Bukkit.getScoreboardManager().getMainScoreboard();
        for (UUID u : boards.keySet()) {
            Player p = Bukkit.getPlayer(u);
            if (p != null && p.getScoreboard() == boards.get(u)) p.setScoreboard(main);
        }
        boards.clear();
        lastLines.clear();
        lastKey.clear();
    }

    private void tickAll() {
        tick++;
        long now = System.currentTimeMillis();
        for (Player p : Bukkit.getOnlinePlayers()) {
            try {
                actionBarTick(p, now);
                if (tick % 4 == 0) sidebarTick(p, now);
            } catch (Throwable t) {
                Log.error("HUD 갱신 오류 (" + p.getName() + ")", t);
            }
        }
    }

    // ── 액션바 ────────────────────────────────────────────────────────────

    private void actionBarTick(Player p, long now) {
        Long until = overrideUntil.get(p.getUniqueId());
        if (until != null) {
            if (until > now) return;
            overrideUntil.remove(p.getUniqueId());
            lastKey.remove(p.getUniqueId());
        }
        DerivedStats s = services.stats().get(p);
        PlayerData d = services.data().get(p);
        double hp = services.stats().currentHp(p);
        double mp = services.classes().mana(p);
        double maxHp = Math.max(1, s.maxHp());
        double maxMp = Math.max(1, s.maxMp());
        boolean maxLevel = d.level() >= services.levels().maxLevel();
        double xp = maxLevel ? 1.0 : services.levels().progress(p);
        String key = Math.round(hp) + "/" + Math.round(maxHp) + "|" + Math.round(mp) + "/" + Math.round(maxMp) + "|"
                + d.level() + "|" + Math.round(xp * 1000) + "|" + d.gold() + "|" + Math.round(shieldOf(p)) + "|" + statusOf(p);
        Long last = lastSent.get(p.getUniqueId());
        if (key.equals(lastKey.get(p.getUniqueId())) && last != null && now - last < 2000) return;
        lastKey.put(p.getUniqueId(), key);
        lastSent.put(p.getUniqueId(), now);
        p.sendActionBar(GlyphHud.available()
                ? GlyphHud.compose(UiTheme.hudSection(), hp, maxHp, mp, maxMp, shieldOf(p), d.level(), xp, d.gold(), statusOf(p))
                : actionLine(hp, maxHp, mp, maxMp, d.level(), xp, maxLevel, d.gold()));
    }

    static String gap() { return "   "; }

    private double shieldOf(Player p) {
        try {
            return services.effects().shield(p);
        } catch (Throwable t) {
            return 0;
        }
    }

    /** 걸려 있는 상태이상 → status_* 글리프 id (액션바 상태 줄). */
    private List<String> statusOf(Player p) {
        List<String> out = new ArrayList<>();
        try {
            var fx = services.effects();
            for (String id : UiTheme.statusIds()) {
                boolean on = "stealth".equals(id) ? fx.isStealthed(p) : fx.has(p, id);
                if (on) out.add("status_" + id);
                if (out.size() >= 8) break;
            }
        } catch (Throwable ignored) {
            // 상태 줄은 장식 — 실패해도 HUD 는 계속
        }
        return out;
    }

    private Component actionLine(double hp, double maxHp, double mp, double maxMp, int level, double xp, boolean maxLevel, long gold) {
        int cells = 10;
        Component c = Component.empty()
                .append(HudBars.icon("hp", "<#ff5f6d>❤"))
                .append(Component.space())
                .append(HudBars.bar("hp", hp / maxHp, cells, "#ff5f6d"))
                .append(Text.mm(" <white>" + Text.num(hp) + "<#6f6880>/" + Text.num(maxHp) + gap()))
                .append(HudBars.icon("mp", "<#6fc3ff>✦"))
                .append(Component.space())
                .append(HudBars.bar("mp", mp / maxMp, 8, "#6fc3ff"))
                .append(Text.mm(" <white>" + Text.num(mp) + "<#6f6880>/" + Text.num(maxMp) + gap()))
                .append(HudBars.icon("level", "<#ffd84f>Lv."))
                .append(Text.mm("<#ffd84f>" + level + " "))
                .append(HudBars.bar("xp", xp, 6, "#b8f05a"))
                .append(Text.mm(" <#b8f05a>" + (maxLevel ? "MAX" : Text.pct(Math.floor(xp * 1000) / 1000.0)) + gap()))
                .append(HudBars.icon("gold", "<#f2c14e>⛃"))
                .append(Text.mm(" <#f2c14e>" + Text.num(gold)));
        return c;
    }

    @Override
    public void actionBar(Player player, Component text, int ticks) {
        overrideUntil.put(player.getUniqueId(), System.currentTimeMillis() + Math.max(1, ticks) * 50L);
        player.sendActionBar(text);
    }

    @Override
    public void refresh(Player player) {
        lastSent.remove(player.getUniqueId());
        lastKey.remove(player.getUniqueId());
    }

    // ── 보스바 ────────────────────────────────────────────────────────────

    @Override
    public void showBossBar(Player player, String key, BossBar bar) {
        Map<String, BossBar> m = bars.computeIfAbsent(player.getUniqueId(), u -> new ConcurrentHashMap<>());
        BossBar old = m.put(key, bar);
        if (old != null && old != bar) player.hideBossBar(old);
        player.showBossBar(bar);
    }

    @Override
    public void hideBossBar(Player player, String key) {
        Map<String, BossBar> m = bars.get(player.getUniqueId());
        if (m == null) return;
        BossBar old = m.remove(key);
        if (old != null) player.hideBossBar(old);
    }

    // ── 스코어보드 (사이드바 + 이름표) ─────────────────────────────────────

    private static String teamName(UUID u) { return "lt" + u.toString().replace("-", "").substring(0, 14); }

    private Scoreboard board(Player p) {
        Scoreboard sb = boards.get(p.getUniqueId());
        if (sb != null && p.getScoreboard() == sb) return sb;
        if (sb == null) {
            sb = Bukkit.getScoreboardManager().getNewScoreboard();
            boards.put(p.getUniqueId(), sb);
            for (Map.Entry<UUID, Component> e : nameTags.entrySet()) {
                Player t = Bukkit.getPlayer(e.getKey());
                if (t != null) applyTeam(sb, t, e.getValue());
            }
        }
        p.setScoreboard(sb);
        return sb;
    }

    private static void applyTeam(Scoreboard sb, Player target, Component prefix) {
        String name = teamName(target.getUniqueId());
        Team t = sb.getTeam(name);
        if (t == null) t = sb.registerNewTeam(name);
        t.prefix(prefix);
        if (!t.hasEntry(target.getName())) t.addEntry(target.getName());
    }

    @Override
    public void nameTagPrefix(Player target, Component prefix) {
        nameTags.put(target.getUniqueId(), prefix);
        board(target);
        for (Scoreboard sb : boards.values()) applyTeam(sb, target, prefix);
    }

    private void setLines(Player p, Component title, List<Component> lines) {
        Scoreboard sb = board(p);
        Objective obj = sb.getObjective(OBJ);
        if (obj == null) {
            obj = sb.registerNewObjective(OBJ, Criteria.DUMMY, title);
            obj.numberFormat(NumberFormat.blank());
            obj.setDisplaySlot(DisplaySlot.SIDEBAR);
            lastLines.put(p.getUniqueId(), new String[LINES + 1]);
        }
        String[] cache = lastLines.computeIfAbsent(p.getUniqueId(), u -> new String[LINES + 1]);
        String titleKey = Text.MM.serialize(title);
        if (!titleKey.equals(cache[LINES])) {
            obj.displayName(title);
            cache[LINES] = titleKey;
        }
        int n = Math.min(LINES, lines.size());
        for (int i = 0; i < LINES; i++) {
            String entry = "lab_l" + i;
            if (i < n) {
                Component line = lines.get(i);
                String k = Text.MM.serialize(line);
                if (!k.equals(cache[i])) {
                    Score sc = obj.getScore(entry);
                    sc.setScore(LINES - i);
                    sc.customName(line);
                    cache[i] = k;
                }
            } else if (cache[i] != null) {
                obj.getScore(entry).resetScore();
                cache[i] = null;
            }
        }
    }

    private void clearSidebar(Player p) {
        Scoreboard sb = boards.get(p.getUniqueId());
        if (sb == null) return;
        Objective obj = sb.getObjective(OBJ);
        if (obj != null) obj.unregister();
        lastLines.remove(p.getUniqueId());
    }

    private void sidebarTick(Player p, long now) {
        PvpHud st = pvp.get(p.getUniqueId());
        if (st != null) {
            Long at = pvpAt.get(p.getUniqueId());
            if (at == null || now - at > 15_000) {
                clearPvpMatch(p);
            } else {
                setLines(p, Text.mm("<gradient:#ff6b6b:#ffd36b><b>⚔ 파티 대전</b></gradient>"), pvpLines(st));
                return;
            }
        }
        Optional<InstanceContext> inst = services.dungeon().currentInstance(p);
        if (inst.isEmpty() || !services.dungeon().isInLabyrinth(p)) {
            clearSidebar(p);
            return;
        }
        setLines(p, Text.mm("<gradient:#c9a2ff:#7fd8ff><b>미궁 라비린스</b></gradient>"), labyrinthLines(p, inst.get(), now));
    }

    private List<Component> labyrinthLines(Player p, InstanceContext ctx, long now) {
        List<Component> out = new ArrayList<>();
        DungeonService.FloorProgress fp = null;
        try {
            fp = services.dungeon().floorProgress(p);
        } catch (Throwable ignored) {
            // dungeon 구현이 바뀌어도 HUD 는 계속
        }
        int floor = fp != null ? fp.floor() : ctx.floor();
        FloorDef def = services.content().floor(floor);
        Difficulty diff = ctx.difficulty();
        out.add(Text.mm("<#6f6880>───────────────"));
        out.add(Text.mm(" <#c9a2ff>지하 <white><b>" + floor + "</b></white>층 <gray>" + (def == null ? "" : Text.escape(Text.strip(def.name())))));
        out.add(Text.mm(" <gray>난이도 " + difficultyColor(diff.id()) + diff.name() + " <dark_gray>· <gray>" + ctx.partySize() + "인"));
        if (fp != null && !fp.ready()) {
            out.add(Text.mm(" <gray>미궁 형성 중 <white>" + Text.pct(fp.progress())));
        } else if (fp != null && fp.roomsTotal() > 0) {
            out.add(Text.mm(" <gray>정복 <white>" + fp.roomsCleared() + "</white><dark_gray>/</dark_gray>" + fp.roomsTotal() + " 방 "
                    + "<#7fe07f>" + HudBars.textBar((double) fp.roomsCleared() / fp.roomsTotal(), 6, "■", "") + "<#3a3546>"
                    + "■".repeat(6 - HudBars.filledCells((double) fp.roomsCleared() / fp.roomsTotal(), 6))));
        }
        long started = fp != null ? fp.startedAt() : ctx.startedAt();
        out.add(Text.mm(" <gray>시간 <white>" + UiTheme.clock((now - started) / 1000) + (fp != null && fp.deaths() > 0
                ? " <dark_gray>· <#ff6b6b>사망 " + fp.deaths() : "")));
        out.add(Text.mm(" "));
        List<Player> members = new ArrayList<>(ctx.onlineMembers());
        if (members.size() <= 1) {
            out.add(Text.mm(" <#c9a2ff>솔로 공략"));
            out.add(memberLine(p, p));
        } else {
            out.add(Text.mm(" <#c9a2ff>파티 <gray>(" + members.size() + "명)"));
            int shown = 0;
            for (Player m : members) {
                if (shown >= 8) break;
                out.add(memberLine(p, m));
                shown++;
            }
        }
        out.add(Text.mm("<#6f6880>───────────────"));
        return out;
    }

    private Component memberLine(Player viewer, Player m) {
        boolean downed;
        try {
            downed = services.dungeon().isDowned(m);
        } catch (Throwable t) {
            downed = false;
        }
        String name = m.getName().length() > 10 ? m.getName().substring(0, 10) : m.getName();
        if (downed) return Text.mm(" <#ff6b6b>✖ <dark_gray><st>" + Text.escape(name) + "</st> <#ff6b6b>쓰러짐");
        double max = Math.max(1, services.stats().maxHp(m));
        double ratio = services.stats().currentHp(m) / max;
        String color = ratio > 0.6 ? "#7fe07f" : ratio > 0.3 ? "#ffd36b" : "#ff6b6b";
        String self = m.equals(viewer) ? "<white>" : "<gray>";
        return Text.mm(" " + self + Text.escape(name) + " <" + color + ">" + HudBars.partyBarMini(ratio, color) + " <" + color + ">" + Math.round(ratio * 100) + "%");
    }

    static String difficultyColor(String id) {
        return switch (id == null ? "" : id) {
            case "easy" -> "<#7fe07f>";
            case "hard" -> "<#ff9a4d>";
            case "nightmare" -> "<#ff4d6d>";
            default -> "<#7fd8ff>";
        };
    }

    // ── 파티 대전 HUD ─────────────────────────────────────────────────────

    @Override
    public void pvpMatch(Player viewer, PvpHud state) {
        if (state == null) {
            clearPvpMatch(viewer);
            return;
        }
        pvp.put(viewer.getUniqueId(), state);
        pvpAt.put(viewer.getUniqueId(), System.currentTimeMillis());
        BossBar.Color color = switch (state.phase() == null ? "" : state.phase()) {
            case "prep", "between" -> BossBar.Color.YELLOW;
            case "sudden_death" -> BossBar.Color.PURPLE;
            case "end" -> BossBar.Color.WHITE;
            default -> BossBar.Color.RED;
        };
        float prog = state.phaseSeconds() <= 0 ? 1f : (float) Math.max(0, Math.min(1, state.secondsLeft() / (double) state.phaseSeconds()));
        Component name = Text.mm("<white>라운드 " + state.round() + " <dark_gray>|</dark_gray> <#7fd8ff>" + state.scoreUs()
                + "</#7fd8ff> <gray>:</gray> <#ff6b6b>" + state.scoreThem() + "</#ff6b6b> <dark_gray>|</dark_gray> "
                + phaseName(state.phase()) + " <white>" + UiTheme.clock(state.secondsLeft()));
        BossBar bar = pvpBars.get(viewer.getUniqueId());
        if (bar == null) {
            bar = BossBar.bossBar(name, prog, color, BossBar.Overlay.NOTCHED_10);
            pvpBars.put(viewer.getUniqueId(), bar);
            viewer.showBossBar(bar);
        } else {
            bar.name(name);
            bar.progress(prog);
            bar.color(color);
        }
        setLines(viewer, Text.mm("<gradient:#ff6b6b:#ffd36b><b>⚔ 파티 대전</b></gradient>"), pvpLines(state));
    }

    @Override
    public void clearPvpMatch(Player viewer) {
        pvp.remove(viewer.getUniqueId());
        pvpAt.remove(viewer.getUniqueId());
        BossBar bar = pvpBars.remove(viewer.getUniqueId());
        if (bar != null) viewer.hideBossBar(bar);
        clearSidebar(viewer);
    }

    static String phaseName(String phase) {
        return switch (phase == null ? "" : phase) {
            case "prep" -> "<#ffd36b>준비";
            case "between" -> "<#ffd36b>다음 라운드";
            case "sudden_death" -> "<#c9a2ff>서든데스";
            case "end" -> "<white>종료";
            default -> "<#ff6b6b>전투";
        };
    }

    private List<Component> pvpLines(PvpHud s) {
        List<Component> out = new ArrayList<>();
        out.add(Text.mm("<#6f6880>───────────────"));
        out.add(Text.mm(" <gray>라운드 <white>" + s.round() + "</white> <dark_gray>· <gray>" + s.roundsToWin() + "선승"));
        out.add(Text.mm(" <gray>점수 <#7fd8ff><b>" + s.scoreUs() + "</b></#7fd8ff> <gray>:</gray> <#ff6b6b><b>" + s.scoreThem() + "</b>"));
        out.add(Text.mm(" " + phaseName(s.phase()) + " <white>" + UiTheme.clock(s.secondsLeft())));
        out.add(Text.mm(" "));
        out.add(Text.mm(" <#7fd8ff>우리 팀 <gray>" + Text.escape(s.usName() == null ? "" : s.usName())));
        int budget = 4;
        for (TeamMember m : s.us()) {
            if (budget-- <= 0) break;
            out.add(teamLine(m, "#7fd8ff"));
        }
        out.add(Text.mm(" <#ff6b6b>상대 팀 <gray>" + Text.escape(s.themName() == null ? "" : s.themName())));
        budget = 4;
        for (TeamMember m : s.them()) {
            if (budget-- <= 0) break;
            out.add(teamLine(m, "#ff6b6b"));
        }
        return out;
    }

    private static Component teamLine(TeamMember m, String color) {
        String name = m.name() == null ? "?" : m.name().length() > 10 ? m.name().substring(0, 10) : m.name();
        if (!m.alive()) return Text.mm("  <dark_gray>✖ <st>" + Text.escape(name) + "</st>");
        return Text.mm("  <gray>" + Text.escape(name) + " <" + color + ">" + HudBars.partyBarMini(m.hpRatio(), color));
    }

    // ── 접속 · 종료 ───────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        board(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        UUID u = e.getPlayer().getUniqueId();
        bars.remove(u);
        overrideUntil.remove(u);
        lastKey.remove(u);
        lastSent.remove(u);
        lastLines.remove(u);
        pvp.remove(u);
        pvpAt.remove(u);
        pvpBars.remove(u);
        nameTags.remove(u);
        boards.remove(u);
        String team = teamName(u);
        for (Scoreboard sb : boards.values()) {
            Team t = sb.getTeam(team);
            if (t != null) t.unregister();
        }
    }
}
