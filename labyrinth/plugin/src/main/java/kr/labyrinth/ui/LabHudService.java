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
import net.kyori.adventure.text.format.NamedTextColor;
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
 *   <li>액션바(초당 4회 검사, 값이 바뀌었을 때만 + 2초마다 유지 재전송): HP·MP·경험치 막대 + 레벨 + 골드 (글리프 / 텍스트 대체).
 *       안내 글({@link #actionBar})·시전 막대({@link #castBar})가 있어도 HUD 는 계속 그리고, 글은 HUD 위(바닐라 액션바 글줄)
 *       가운데에 함께 그린다 — {@link #withMessage} 참고.</li>
 *   <li>사이드바(1초마다, 바뀐 줄만): 미궁 안 — 층·난이도·진행 방·타이머·사망·파티원 HP 미니 막대</li>
 *   <li>보스바: 다른 모듈이 key 로 띄우는 것</li>
 *   <li>이름표: 플레이어마다 개인 스코어보드 → 대상별 팀 prefix (칭호) + 색 (pvp: 내 파티원 초록)</li>
 * </ul>
 */
public final class LabHudService implements HudService, Listener {

    private static final int LINES = 15;
    private static final String OBJ = "lab_side";

    private final Services services;
    private final Map<UUID, Map<String, BossBar>> bars = new ConcurrentHashMap<>();
    /** 화면 밖으로 밀어 낼 거리(px): 글 사본이 어떤 화면 폭(GUI 배율 1, 8K)에서도 안 보이게. */
    static final int OFFSCREEN = 4096;

    /** HUD 위에 함께 그리는 안내 글 (until 까지). */
    private record Overlay(Component text, int width, long until, long seq) {}

    /** 시전 막대 (until 까지, 진행도 0~1). */
    private record Cast(Component label, int width, double progress, long until) {}

    private final Map<UUID, Overlay> overlays = new ConcurrentHashMap<>();
    private final Map<UUID, Cast> casts = new ConcurrentHashMap<>();
    private long overlaySeq;
    private final Map<UUID, String> lastKey = new HashMap<>();
    private final Map<UUID, Long> lastSent = new HashMap<>();
    private final Map<UUID, Scoreboard> boards = new HashMap<>();
    private final Map<UUID, String[]> lastLines = new HashMap<>();
    private final Map<UUID, Component> nameTags = new HashMap<>();
    /** 보는 사람 → (대상 → 이름표 색). */
    private final Map<UUID, Map<UUID, NamedTextColor>> tagColors = new HashMap<>();
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
        bars.clear();
        tagColors.clear();
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
        UUID u = p.getUniqueId();
        Overlay ov = overlays.get(u);
        if (ov != null && ov.until() <= now) {
            overlays.remove(u, ov);
            ov = null;
        }
        Cast cs = casts.get(u);
        if (cs != null && cs.until() <= now) {
            casts.remove(u, cs);
            cs = null;
        }
        boolean glyphs = GlyphHud.available();
        if (!glyphs && (ov != null || cs != null)) {
            // 글자 HUD(리소스팩 글리프 없음): 한 줄에 다 못 넣으니 예전처럼 안내 글만 보인다
            String k = "msg|" + (ov != null ? ov.seq() : "") + "|" + (cs != null ? Math.round(cs.progress() * 20) : "");
            Long last = lastSent.get(u);
            if (k.equals(lastKey.get(u)) && last != null && now - last < 2000) return;
            lastKey.put(u, k);
            lastSent.put(u, now);
            p.sendActionBar(ov != null ? ov.text() : cs.label().append(Text.mm(" <white>"
                    + "▮".repeat((int) Math.round(cs.progress() * 20)) + "<dark_gray>" + "▯".repeat(20 - (int) Math.round(cs.progress() * 20)))));
            return;
        }
        DerivedStats s = services.stats().get(p);
        PlayerData d = services.data().get(p);
        double hp = services.stats().currentHp(p);
        double mp = services.classes().mana(p);
        double maxHp = Math.max(1, s.maxHp());
        double maxMp = Math.max(1, s.maxMp());
        boolean maxLevel = d.level() >= services.levels().maxLevel();
        double xp = maxLevel ? 1.0 : services.levels().progress(p);
        double cast = cs == null ? -1 : cs.progress();
        String key = Math.round(hp) + "/" + Math.round(maxHp) + "|" + Math.round(mp) + "/" + Math.round(maxMp) + "|"
                + d.level() + "|" + Math.round(xp * 1000) + "|" + d.gold() + "|" + Math.round(shieldOf(p)) + "|" + statusOf(p)
                + "|" + (ov == null ? "" : ov.seq()) + "|" + (cs == null ? "" : Math.round(cast * 100) + cs.label().hashCode());
        Long last = lastSent.get(p.getUniqueId());
        if (key.equals(lastKey.get(p.getUniqueId())) && last != null && now - last < 2000) return;
        lastKey.put(p.getUniqueId(), key);
        lastSent.put(p.getUniqueId(), now);
        if (!glyphs) {
            p.sendActionBar(actionLine(hp, maxHp, mp, maxMp, d.level(), xp, maxLevel, d.gold()));
            return;
        }
        Component hud = GlyphHud.compose(UiTheme.hudSection(), hp, maxHp, mp, maxMp, shieldOf(p), d.level(), xp, d.gold(),
                statusOf(p), cast);
        if (ov != null) hud = withMessage(hud, ov.text(), ov.width(), GlyphHud.total(UiTheme.hudSection()));
        else if (cs != null) hud = withMessage(hud, cs.label(), cs.width(), GlyphHud.total(UiTheme.hudSection()));
        p.sendActionBar(hud);
    }

    /**
     * HUD(폭 total, 가운데 정렬)에 안내 글을 얹는다: {@code [글][space(b)][HUD][space(+OFF)][글 사본][space(b − OFF)]}.
     * <p>
     * 액션바는 전체 폭(advance 합)으로 가운데 정렬되므로, 글 폭 m′ 이 추정치 m 과 다르면 보통은 HUD 까지 밀린다.
     * 같은 글을 HUD 뒤에 한 번 더(화면 밖 OFFSCREEN px) 그리면 앞뒤 m′ 이 정확히 상쇄되어 HUD 왼쪽 끝 = 화면 가운데 − total/2
     * 가 글 폭과 무관하게 지켜진다. 보이는 글의 가운데만 (m − m′)/2 px 비킬 수 있다 (키 이름·unifont 기호 폭 차이).
     * 세로: 기본 글꼴 글줄(화면 아래 −72) = HUD 글리프들보다 위 빈 줄.
     */
    static Component withMessage(Component hud, Component msg, int estWidth, int total) {
        int b = -(total / 2) - estWidth / 2;
        return Component.empty()
                .append(msg)
                .append(Glyphs.space(b))
                .append(hud)
                .append(Glyphs.space(OFFSCREEN))
                .append(msg)
                .append(Glyphs.space(b - OFFSCREEN));
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
        if (text == null) return;
        long seq;
        synchronized (this) {
            seq = ++overlaySeq;
        }
        overlays.put(player.getUniqueId(), new Overlay(text, TextWidth.width(text),
                System.currentTimeMillis() + Math.max(1, ticks) * 50L, seq));
        sendNow(player);
    }

    @Override
    public void castBar(Player player, Component label, double progress, int ticks) {
        Component l = label == null ? Component.empty() : label;
        casts.put(player.getUniqueId(), new Cast(l, TextWidth.width(l), Math.max(0, Math.min(1, progress)),
                System.currentTimeMillis() + Math.max(1, ticks) * 50L));
        sendNow(player);
    }

    @Override
    public void clearCast(Player player) {
        if (casts.remove(player.getUniqueId()) != null) sendNow(player);
    }

    /** 바로 다시 그린다 (안내 글·시전 막대가 바뀐 순간). */
    private void sendNow(Player p) {
        lastKey.remove(p.getUniqueId());
        lastSent.remove(p.getUniqueId());
        if (!org.bukkit.Bukkit.isPrimaryThread()) return;   // 다음 틱(≤5틱)에 그려진다
        try {
            actionBarTick(p, System.currentTimeMillis());
        } catch (Throwable t) {
            Log.error("HUD 갱신 오류 (" + p.getName() + ")", t);
        }
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
            Map<UUID, NamedTextColor> colors = tagColors.get(p.getUniqueId());
            if (colors != null) {
                for (Map.Entry<UUID, NamedTextColor> e : colors.entrySet()) {
                    Player t = Bukkit.getPlayer(e.getKey());
                    if (t != null) applyColor(sb, t, e.getValue());
                }
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

    /** 대상 팀 색 (null = 기본). 칭호 접두어 팀과 같은 팀을 쓴다 — 한 사람은 스코어보드마다 팀 하나에만 들어갈 수 있어서. */
    private static void applyColor(Scoreboard sb, Player target, NamedTextColor color) {
        String name = teamName(target.getUniqueId());
        Team t = sb.getTeam(name);
        if (t == null) {
            if (color == null) return;
            t = sb.registerNewTeam(name);
        }
        if (!t.hasEntry(target.getName())) t.addEntry(target.getName());
        if (color == null) {
            if (t.hasColor()) t.color(null); // null = 색 없음 (Paper: Optional.empty)
        } else if (!t.hasColor() || !color.equals(t.color())) {
            t.color(color);
        }
    }

    @Override
    public void nameTagColor(Player viewer, Player target, NamedTextColor color) {
        if (viewer == null || target == null || viewer.equals(target)) return;
        Map<UUID, NamedTextColor> m = tagColors.computeIfAbsent(viewer.getUniqueId(), k -> new HashMap<>());
        if (color == null) {
            if (m.remove(target.getUniqueId()) == null) {
                Scoreboard sb = boards.get(viewer.getUniqueId());
                Team t = sb == null ? null : sb.getTeam(teamName(target.getUniqueId()));
                if (t == null || !t.hasColor()) return; // 원래 색 없음 — 할 일 없음
            }
        } else {
            m.put(target.getUniqueId(), color);
        }
        applyColor(board(viewer), target, color);
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
        return Text.mm(" " + classIcon(m) + self + Text.escape(name) + " <" + color + ">" + HudBars.partyBarMini(ratio, color) + " <" + color + ">" + Math.round(ratio * 100) + "%");
    }

    /** 직업 아이콘 글리프 party_class_&lt;직업&gt; + 한 칸 (직업 없음·글리프 없음 = 빈 문자열). */
    private String classIcon(Player m) {
        try {
            var cls = services.classes().classOf(m);
            if (cls == null) return "";
            var g = services.content().glyphs().get("party_class_" + cls.id());
            return g == null ? "" : "<white><font:labyrinth:ui>" + g.ch() + "</font></white> ";
        } catch (Throwable t) {
            return "";
        }
    }

    static String difficultyColor(String id) {
        return switch (id == null ? "" : id) {
            case "easy" -> "<#7fe07f>";
            case "hard" -> "<#ff9a4d>";
            case "nightmare" -> "<#ff4d6d>";
            default -> "<#7fd8ff>";
        };
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
        overlays.remove(u);
        casts.remove(u);
        lastKey.remove(u);
        lastSent.remove(u);
        lastLines.remove(u);
        nameTags.remove(u);
        tagColors.remove(u);
        for (Map<UUID, NamedTextColor> m : tagColors.values()) m.remove(u);
        boards.remove(u);
        String team = teamName(u);
        for (Scoreboard sb : boards.values()) {
            Team t = sb.getTeam(team);
            if (t != null) t.unregister();
        }
    }
}
