package kr.labyrinth.titles;

import io.papermc.paper.chat.ChatRenderer;
import io.papermc.paper.event.player.AsyncChatEvent;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.ToLongFunction;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import kr.labyrinth.Services;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.event.CraftEvent;
import kr.labyrinth.event.FloorClearEvent;
import kr.labyrinth.event.ItemObtainEvent;
import kr.labyrinth.event.LevelUpEvent;
import kr.labyrinth.event.MobKillEvent;
import kr.labyrinth.event.PvpMatchEndEvent;
import kr.labyrinth.stats.StatContributor;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.OfflinePlayer;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;

/**
 * 업적·칭호 실제 구현 (GDD §12). 이벤트 → {@link TitleCounters} 로 카운터 갱신 → {@link AchievementRules} 로 판정 → 지급.
 * 서버 최초 기록은 {@code ServerRecords} 로 확정(키 {@code first_clear.floor_<n>}, {@code title.<업적 id>}),
 * 방송·효과음·불꽃놀이 같은 파티클 연출, 칭호 장착(채팅 렌더러 · 탭 목록 · 이름표 접두어), 장착 칭호 보너스(StatContributor).
 */
public final class LabTitleService extends BasicTitleService implements Listener {

    private static final Pattern HEX = Pattern.compile("#([0-9a-fA-F]{6})");

    /** 비동기 채팅 렌더러용 접두어 캐시 (메인 스레드에서 갱신). */
    private final Map<UUID, Component> prefixCache = new ConcurrentHashMap<>();
    private final Set<UUID> suppressed = ConcurrentHashMap.newKeySet();
    private final StatContributor bonusContributor = this::contributeBonus;

    public LabTitleService(Services services) { super(services); }

    void enable() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        services.stats().addContributor(bonusContributor);
        for (Player p : Bukkit.getOnlinePlayers()) applyDisplay(p);
    }

    void disable() {
        HandlerList.unregisterAll(this);
        services.stats().removeContributor(bonusContributor);
        prefixCache.clear();
    }

    /** reload: 칭호 정의가 바뀌었을 수 있으니 접두어·보너스 갱신 + 소급 판정. */
    void reload() {
        for (Player p : Bukkit.getOnlinePlayers()) {
            applyDisplay(p);
            services.stats().markDirty(p);
            recheck(p);
        }
    }

    // ── 조회 헬퍼 ─────────────────────────────────────────────────────────

    static TitleCounters.Store store(PlayerData d) {
        return new TitleCounters.Store() {
            @Override public long get(String key) { return d.counter(key); }
            @Override public void set(String key, long value) { d.counter(key, value); }
        };
    }

    static ToLongFunction<String> lookup(PlayerData d) {
        return k -> "level".equals(k) ? d.level() : d.counter(k);
    }

    @Override
    public long[] progress(Player player, String achievementId) {
        AchievementDef def = services.content().achievements().get(achievementId);
        if (def == null) return new long[] {0, 1};
        PlayerData d = services.data().get(player);
        if (d.hasAchievement(achievementId)) {
            long[] pr = AchievementRules.progress(def, lookup(d));
            return new long[] {pr[1], pr[1]};
        }
        return AchievementRules.progress(def, lookup(d));
    }

    // ── 지급 ──────────────────────────────────────────────────────────────

    @Override
    public boolean grant(Player player, String achievementId) {
        AchievementDef def = services.content().achievements().get(achievementId);
        if (def == null) return false;
        if (!grantQuiet(player, def)) return false;
        if (def.broadcast()) broadcast(def, List.of(player.getName()), isServerFirst(def));
        return true;
    }

    /** 방송 없이 지급 + 개인 연출. */
    private boolean grantQuiet(Player player, AchievementDef def) {
        PlayerData d = services.data().get(player);
        if (!d.grantAchievement(def.id())) return false;
        if (def.rewardGold() > 0) d.addGold(def.rewardGold());
        def.rewardItems().forEach((id, n) -> {
            try {
                services.items().give(player, id, n, "reward");
            } catch (Throwable t) {
                Log.error("칭호 보상 지급 실패: " + id, t);
            }
        });
        Component title = Text.mm(def.title());
        StringBuilder reward = new StringBuilder();
        if (def.rewardGold() > 0) reward.append(" <gold>+").append(Text.num(def.rewardGold())).append(" 골드</gold>");
        def.rewardItems().forEach((id, n) -> {
            ItemDef idef = services.content().item(id);
            reward.append(" <white>").append(idef == null ? id : idef.name()).append(" ×").append(n).append("</white>");
        });
        Text.send(player, "<#ffd36b>칭호 획득!</#ffd36b> <title> <dark_gray>—</dark_gray> <gray><desc></gray>" + reward,
                Text.ph("title", title), Text.ph("desc", def.description()));
        if (!def.bonus().isEmpty()) {
            Text.send(player, "<gray>장착 효과: <white>" + bonusText(def.bonus()) + "</white> <dark_gray>(/칭호 에서 장착)");
        }
        player.showTitle(Title.title(Text.mm("<#ffd36b>✦ 칭호 획득 ✦"), title,
                Title.Times.times(Duration.ofMillis(250), Duration.ofMillis(2600), Duration.ofMillis(700))));
        player.playSound(player.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.9f, 1.0f);
        celebrate(player, colorOf(def.title()), isServerFirst(def) || def.broadcast());
        services.hud().refresh(player);
        if (equipped(player) == null) {
            // 첫 칭호는 자동 장착 (처음 하는 사람도 바로 보이게)
            equip(player, def.id());
        }
        return true;
    }

    private static boolean isServerFirst(AchievementDef def) {
        return "FIRST_CLEAR".equalsIgnoreCase(def.conditionType())
                || (def.condition() != null && def.condition().bool("server_first", false));
    }

    private void broadcast(AchievementDef def, List<String> names, boolean serverFirst) {
        String who = String.join(", ", names.stream().map(Text::escape).toList());
        Component msg;
        if (serverFirst) {
            msg = Text.mm("<gradient:#ffd36b:#ff8a3d><b>[서버 최초]</b></gradient> <white>" + who + "</white> <gray>"
                    + (names.size() > 1 ? "파티가" : "님이") + " </gray><title> <gray>칭호를 손에 넣었습니다!</gray> <dark_gray>— <desc>",
                    Text.ph("title", Text.mm(def.title())), Text.ph("desc", def.description()));
        } else {
            msg = Text.mm("<#c9a2ff>[칭호]</#c9a2ff> <white>" + who + "</white> <gray>님이 </gray><title> <gray>칭호를 얻었습니다!",
                    Text.ph("title", Text.mm(def.title())));
        }
        Bukkit.getServer().sendMessage(msg);
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (serverFirst) {
                p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.7f, 0.8f);
                p.playSound(p.getLocation(), Sound.ENTITY_FIREWORK_ROCKET_TWINKLE_FAR, 0.8f, 1.0f);
            } else {
                p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_CHIME, 0.6f, 1.5f);
            }
        }
    }

    /** 불꽃놀이 같은 파티클 연출 (블록·엔티티 없이 파티클과 소리만 — 아무것도 부수지 않는다). */
    private void celebrate(Player p, Color color, boolean big) {
        int bursts = big ? 4 : 1;
        for (int i = 0; i < bursts; i++) {
            final int n = i;
            Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
                if (!p.isOnline()) return;
                Location c = p.getLocation().add(0, 2.4 + n * 0.5, 0);
                double r = 1.2 + n * 0.35;
                Particle.DustOptions dust = new Particle.DustOptions(color, 1.4f);
                Particle.DustOptions white = new Particle.DustOptions(Color.fromRGB(0xFFF4D6), 1.0f);
                int pts = 28;
                for (int k = 0; k < pts; k++) {
                    double phi = Math.acos(1 - 2.0 * (k + 0.5) / pts);
                    double theta = Math.PI * (1 + Math.sqrt(5)) * k + n;
                    double x = Math.cos(theta) * Math.sin(phi) * r;
                    double y = Math.cos(phi) * r;
                    double z = Math.sin(theta) * Math.sin(phi) * r;
                    p.getWorld().spawnParticle(Particle.DUST, c.clone().add(x, y, z), 1, 0, 0, 0, 0, (k & 1) == 0 ? dust : white);
                }
                p.getWorld().spawnParticle(Particle.FIREWORK, c, big ? 30 : 14, 0.2, 0.2, 0.2, 0.12);
                if (n == 0) p.getWorld().spawnParticle(Particle.TOTEM_OF_UNDYING, p.getLocation().add(0, 1, 0), big ? 50 : 20, 0.4, 0.6, 0.4, 0.35);
                p.getWorld().playSound(c, n % 2 == 0 ? Sound.ENTITY_FIREWORK_ROCKET_BLAST : Sound.ENTITY_FIREWORK_ROCKET_TWINKLE, 0.8f, 1.0f + n * 0.1f);
            }, 4L + i * 9L);
        }
    }

    private static Color colorOf(String mini) {
        if (mini != null) {
            Matcher m = HEX.matcher(mini);
            if (m.find()) return Color.fromRGB(Integer.parseInt(m.group(1), 16));
        }
        return Color.fromRGB(0xFFD36B);
    }

    static String bonusText(Map<String, Double> bonus) {
        List<String> parts = new ArrayList<>();
        bonus.forEach((k, v) -> {
            kr.labyrinth.stats.Stat st = kr.labyrinth.stats.Stat.byKey(k);
            if (st != null) parts.add(st.displayName() + " +" + Math.round(v));
            else if ("xp_bonus".equals(k)) parts.add("경험치 +" + Text.pct(v));
            else if ("gold_bonus".equals(k)) parts.add("골드 +" + Text.pct(v));
            else parts.add(k + " +" + v);
        });
        return String.join(" · ", parts);
    }

    // ── 판정 ──────────────────────────────────────────────────────────────

    /** 여러 플레이어를 한 번에 판정 → 같은 업적은 방송을 한 번만 (파티 클리어 등). */
    private void evaluate(List<Player> players) {
        Map<String, List<Player>> newly = new LinkedHashMap<>();
        for (Player p : players) {
            if (p == null || !p.isOnline()) continue;
            PlayerData d = services.data().get(p);
            ToLongFunction<String> look = lookup(d);
            for (AchievementDef def : services.content().achievements().values()) {
                if (d.hasAchievement(def.id())) continue;
                if (def.condition() != null && def.condition().bool("server_first", false)
                        && !"PVP_FIRST_WIN".equalsIgnoreCase(def.conditionType())
                        && AchievementRules.baseMet(def.conditionType(), def.condition(), look)) {
                    trySoloServerFirst(p, d, def);
                }
                if (AchievementRules.met(def, look)) newly.computeIfAbsent(def.id(), k -> new ArrayList<>()).add(p);
            }
        }
        newly.forEach((id, list) -> {
            AchievementDef def = services.content().achievements().get(id);
            List<String> names = new ArrayList<>();
            for (Player p : list) if (grantQuiet(p, def)) names.add(p.getName());
            if (!names.isEmpty() && def.broadcast()) broadcast(def, names, isServerFirst(def));
        });
    }

    private void trySoloServerFirst(Player p, PlayerData d, AchievementDef def) {
        String key = "title." + def.id();
        if (services.records().isClaimed(key)) return;
        if (services.records().claim(key, List.of(p.getUniqueId()), List.of(p.getName()), Map.of("achievement", def.id()))) {
            d.counter(AchievementRules.P + "server_first." + def.id(), 1);
        }
    }

    @Override
    public void recheck(Player player) { evaluate(List.of(player)); }

    // ── 이벤트 ────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onFloorClear(FloorClearEvent e) {
        safe("FloorClearEvent", () -> {
            int floor = e.floor();
            List<Player> members = e.members().stream().filter(Player::isOnline).toList();
            for (Player p : members) {
                PlayerData d = services.data().get(p);
                TitleCounters.onClear(store(d), floor, e.partySize(), e.deaths(), e.seconds(), e.difficulty(),
                        d.counter("dungeon.clear_floor_" + floor));
            }
            String key = "first_clear.floor_" + floor;
            if (!members.isEmpty() && !services.records().isClaimed(key)) {
                List<UUID> ids = members.stream().map(Player::getUniqueId).toList();
                List<String> names = members.stream().map(Player::getName).toList();
                Map<String, Object> extra = new LinkedHashMap<>();
                extra.put("difficulty", e.difficulty());
                extra.put("seconds", Math.round(e.seconds()));
                extra.put("party_size", e.partySize());
                if (services.records().claim(key, ids, names, extra)) {
                    for (Player p : members) services.data().get(p).counter(AchievementRules.P + "first_clear." + floor, 1);
                    Log.info("서버 최초 돌파 기록: 지하 " + floor + "층 — " + String.join(", ", names));
                }
            }
            // 스피드런 서버 기록 (이전 기록을 깼을 때만 방송 — 첫 기록은 최초 돌파 방송으로 충분)
            String speedKey = "speed.floor_" + floor;
            boolean hadRecord = services.records().isClaimed(speedKey);
            if (!members.isEmpty() && e.seconds() > 0 && services.records().bestTime(speedKey, e.seconds(),
                    members.stream().map(Player::getUniqueId).toList(), members.stream().map(Player::getName).toList())) {
                if (hadRecord) {
                    Bukkit.getServer().sendMessage(Text.mm(Text.PREFIX + "<#7fd8ff>지하 " + floor + "층 최단 기록 갱신!</#7fd8ff> <white>"
                            + Text.escape(String.join(", ", members.stream().map(Player::getName).toList())) + "</white> <gray>— "
                            + AchievementRules.timeText(Math.round(e.seconds()))));
                }
            }
            evaluate(members);
        });
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onKill(MobKillEvent e) {
        safe("MobKillEvent", () -> {
            String rank = null;
            if (!e.isBoss()) {
                MobDef def = services.content().mob(e.mobId());
                rank = def == null ? "normal" : def.rank();
            }
            List<Player> list = new ArrayList<>(e.participants());
            if (e.killer() != null && !list.contains(e.killer())) list.add(e.killer());
            for (Player p : list) {
                if (!p.isOnline()) continue;
                TitleCounters.onKill(store(services.data().get(p)), e.mobId(), rank, e.isBoss());
            }
            evaluate(list);
        });
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onLevel(LevelUpEvent e) { safe("LevelUpEvent", () -> evaluate(List.of(e.player()))); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onObtain(ItemObtainEvent e) {
        safe("ItemObtainEvent", () -> {
            ItemDef def = e.def();
            if (def == null || !def.isGear() || "admin".equals(e.source())) return;
            TitleCounters.onObtain(store(services.data().get(e.player())), def.rarity(),
                    e.stack() == null ? 1 : Math.max(1, e.stack().getAmount()));
            evaluate(List.of(e.player()));
        });
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onCraft(CraftEvent e) {
        safe("CraftEvent", () -> {
            ItemDef def = e.recipe() == null ? null : services.content().item(e.recipe().result());
            Rarity r = def == null ? null : def.rarity();
            TitleCounters.onCraft(store(services.data().get(e.player())), r);
            evaluate(List.of(e.player()));
        });
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onPvp(PvpMatchEndEvent e) {
        safe("PvpMatchEndEvent", () -> {
            List<Player> online = new ArrayList<>();
            List<Player> winners = new ArrayList<>();
            for (UUID u : e.winners()) {
                Player p = Bukkit.getPlayer(u);
                if (p == null) continue;
                online.add(p);
                winners.add(p);
                TitleCounters.onPvp(store(services.data().get(p)), true, e.streaks().get(u), e.ratings().get(u));
            }
            for (UUID u : e.losers()) {
                Player p = Bukkit.getPlayer(u);
                if (p == null) continue;
                online.add(p);
                TitleCounters.onPvp(store(services.data().get(p)), false, e.streaks().get(u), e.ratings().get(u));
            }
            // 서버 최초 대전 승리 팀 (server_first PVP_FIRST_WIN) — 승리 팀 전원
            for (AchievementDef def : services.content().achievements().values()) {
                if (!"PVP_FIRST_WIN".equalsIgnoreCase(def.conditionType())) continue;
                if (def.condition() == null || !def.condition().bool("server_first", false)) continue;
                String key = "title." + def.id();
                if (e.winners().isEmpty() || services.records().isClaimed(key)) continue;
                List<String> names = new ArrayList<>();
                for (UUID u : e.winners()) {
                    OfflinePlayer op = Bukkit.getOfflinePlayer(u);
                    names.add(op.getName() == null ? u.toString().substring(0, 8) : op.getName());
                }
                if (services.records().claim(key, e.winners(), names, Map.of("match", e.matchId()))) {
                    for (Player p : winners) services.data().get(p).counter(AchievementRules.P + "server_first." + def.id(), 1);
                }
            }
            // 레이팅 높은 사람부터 판정 (server_first PVP_RATING 은 먼저 도달한 1명)
            online.sort(Comparator.comparingLong((Player p) -> -services.data().get(p).counter(AchievementRules.P + "pvp_rating")));
            evaluate(online);
        });
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (!p.isOnline()) return;
            applyDisplay(p);
            recheck(p);
        }, 30L);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        prefixCache.remove(e.getPlayer().getUniqueId());
        suppressed.remove(e.getPlayer().getUniqueId());
    }

    /** 채팅: [칭호] 이름 » 메시지 (파티 채팅 등으로 취소된 메시지는 건드리지 않는다). */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onChat(AsyncChatEvent e) {
        Component prefix = prefixCache.getOrDefault(e.getPlayer().getUniqueId(), Component.empty());
        e.renderer(ChatRenderer.viewerUnaware((source, name, message) -> Component.empty()
                .append(prefix)
                .append(name.colorIfAbsent(net.kyori.adventure.text.format.NamedTextColor.WHITE))
                .append(Text.mm("<dark_gray> » </dark_gray>"))
                .append(message.colorIfAbsent(net.kyori.adventure.text.format.NamedTextColor.GRAY))));
    }

    private void safe(String what, Runnable r) {
        try {
            r.run();
        } catch (Throwable t) {
            Log.error("칭호 처리 오류 (" + what + ")", t);
        }
    }

    // ── 장착 · 표시 · 보너스 ──────────────────────────────────────────────

    @Override
    public boolean equip(Player player, String achievementId) {
        if (achievementId != null && services.content().achievements().get(achievementId) == null) return false;
        if (!super.equip(player, achievementId)) return false;
        applyDisplay(player);
        services.stats().markDirty(player);
        services.stats().recalc(player);
        return true;
    }

    /** 채팅 캐시 · 탭 목록 이름 · 이름표 접두어 갱신. */
    public void applyDisplay(Player p) {
        Component prefix = prefix(p);
        prefixCache.put(p.getUniqueId(), prefix);
        p.playerListName(Component.empty().append(prefix).append(Component.text(p.getName())));
        services.hud().nameTagPrefix(p, prefix);
    }

    private void contributeBonus(Player p, kr.labyrinth.stats.StatBlock block) {
        if (suppressed.contains(p.getUniqueId())) return;
        AchievementDef def = equipped(p);
        if (def == null || def.bonus().isEmpty()) return;
        def.bonus().forEach(block::add);
    }

    @Override
    public void setBonusSuppressed(Player player, boolean on) {
        boolean changed = on ? suppressed.add(player.getUniqueId()) : suppressed.remove(player.getUniqueId());
        if (changed) {
            services.stats().markDirty(player);
            services.stats().recalc(player);
        }
    }
}
