package kr.labyrinth.titles;

import io.papermc.paper.chat.ChatRenderer;
import io.papermc.paper.event.player.AsyncChatEvent;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
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
import kr.labyrinth.data.ServerRecords;
import kr.labyrinth.event.CraftEvent;
import kr.labyrinth.event.EnhanceEvent;
import kr.labyrinth.event.FloorClearEvent;
import kr.labyrinth.event.ItemObtainEvent;
import kr.labyrinth.event.LevelUpEvent;
import kr.labyrinth.event.MobKillEvent;
import kr.labyrinth.stats.StatContributor;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
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
 * 칭호 실제 구현 (GDD §12). 칭호마다 서버에서 단 한 명 — 사건이 일어나면 {@link TitleCounters} 로 카운터를 올리고,
 * 아직 주인이 없는 칭호만 {@link AchievementRules#qualifies} 로 판정해, 조건을 채운 첫 사람에게 records.yml
 * {@code title.<id>} 로 확정(claim — 메인 스레드에서 한 번만 성공, 재시작 후에도 유지)한 뒤 지급한다.
 * 파티 사건(층 돌파·보스 처치)은 그 보스에게 가장 많은 피해를 준 한 명({@link AwardOrder})만 받는다.
 * 접속·리로드로는 칭호를 주지 않는다. 서버 최초 돌파 기록({@code first_clear.floor_<n>})·최단 기록({@code speed.floor_<n>})도 여기서 남긴다.
 */
public final class LabTitleService extends BasicTitleService implements Listener {

    private static final Pattern HEX = Pattern.compile("#([0-9a-fA-F]{6})");
    /** 보스 처치 → 층 돌파 사이에 쓰는 전투 기록 유효 시간. */
    private static final long FIGHT_TTL_MS = 120_000L;

    /** 비동기 채팅 렌더러용 접두어 캐시 (메인 스레드에서 갱신). */
    private final Map<UUID, Component> prefixCache = new ConcurrentHashMap<>();
    private final Set<UUID> suppressed = ConcurrentHashMap.newKeySet();
    private final StatContributor bonusContributor = this::contributeBonus;
    /** 인스턴스 id → 방금 끝난 보스 전투 (피해·막타). 층 돌파 사건에서 받을 사람을 고를 때 쓴다. */
    private final Map<String, Fight> fights = new HashMap<>();

    private record Fight(Map<UUID, Double> damage, UUID lastHit, long at) {}

    public LabTitleService(Services services) { super(services); }

    void enable() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        services.stats().addContributor(bonusContributor);
        for (Player p : Bukkit.getOnlinePlayers()) {
            migrateAndSync(p);
            applyDisplay(p);
        }
    }

    void disable() {
        HandlerList.unregisterAll(this);
        services.stats().removeContributor(bonusContributor);
        prefixCache.clear();
        fights.clear();
    }

    /** reload: 칭호 정의가 바뀌었을 수 있으니 주인 대조·접두어·보너스만 갱신 (새로 주지는 않는다). */
    void reload() {
        for (Player p : Bukkit.getOnlinePlayers()) recheck(p);
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

    /** 칭호의 주인 (없으면 null). */
    public TitleView.Owner owner(String achievementId) {
        ServerRecords.Record r = services.records().get(TitleView.recordKey(achievementId)).orElse(null);
        if (r == null) return null;
        return new TitleView.Owner(r.names().isEmpty() ? "?" : r.names().get(0), r.time());
    }

    // ── 지급 ──────────────────────────────────────────────────────────────

    /** 관리자 지급: 주인이 없을 때만 (있으면 false — /labadmin title free 로 먼저 비운다). */
    @Override
    public boolean grant(Player player, String achievementId) {
        AchievementDef def = services.content().achievements().get(achievementId);
        if (def == null) return false;
        return claim(player, def);
    }

    /** 주인 확정 (records.yml) → 지급 → 방송. 이미 주인이 있으면 false. */
    private boolean claim(Player player, AchievementDef def) {
        String key = TitleView.recordKey(def.id());
        if (services.records().isClaimed(key)) return false;
        if (!services.records().claim(key, List.of(player.getUniqueId()), List.of(player.getName()),
                Map.of("achievement", def.id()))) return false;
        Log.info("칭호 주인: " + def.id() + " — " + player.getName());
        grantQuiet(player, def);
        if (def.broadcast()) broadcast(def, player.getName());
        return true;
    }

    /** 데이터 지급 + 보상 + 개인 연출 (방송 없이). */
    private void grantQuiet(Player player, AchievementDef def) {
        PlayerData d = services.data().get(player);
        d.grantAchievement(def.id());
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
        Text.send(player, TitleView.ownerMessage(def, services.content(), reward.toString()));
        if (!def.bonus().isEmpty()) {
            Text.send(player, "<gray>장착 효과: <white>" + TitleView.bonusText(def.bonus()) + "</white> <dark_gray>(/칭호 에서 장착)");
        }
        player.showTitle(Title.title(Text.mm("<#ffd36b>✦ 칭호의 주인 ✦"), title,
                Title.Times.times(Duration.ofMillis(250), Duration.ofMillis(2600), Duration.ofMillis(700))));
        player.playSound(player.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.9f, 1.0f);
        celebrate(player, colorOf(def.title()), true);
        services.hud().refresh(player);
        if (equipped(player) == null) equip(player, def.id()); // 첫 칭호는 바로 달아 준다
    }

    private void broadcast(AchievementDef def, String name) {
        Bukkit.getServer().sendMessage(Text.mm(TitleView.broadcast(def, name, services.content())));
        for (Player p : Bukkit.getOnlinePlayers()) {
            p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.7f, 0.8f);
            p.playSound(p.getLocation(), Sound.ENTITY_FIREWORK_ROCKET_TWINKLE_FAR, 0.8f, 1.0f);
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

    // ── 판정 ──────────────────────────────────────────────────────────────

    /**
     * 사건 하나 판정: 주인이 없는 칭호마다 ranked 순서로 조건을 채운 첫 사람에게 준다 (한 칭호 = 한 명).
     * 주인이 생긴 칭호는 건너뛴다 — 다시는 판정하지 않는다.
     */
    private void award(TitleTrigger t, List<Player> ranked) {
        if (ranked.isEmpty()) return;
        for (AchievementDef def : services.content().achievements().values()) {
            if (services.records().isClaimed(TitleView.recordKey(def.id()))) continue;
            for (Player p : ranked) {
                if (p == null || !p.isOnline()) continue;
                PlayerData d = services.data().get(p);
                if (d.hasAchievement(def.id())) continue;
                if (!AchievementRules.qualifies(def, t, lookup(d))) continue;
                claim(p, def);
                break;
            }
        }
    }

    /** 주인 기록과 데이터를 맞추고 접두어·보너스를 다시 건다. 칭호를 새로 주지는 않는다. */
    @Override
    public void recheck(Player player) {
        sync(player);
        applyDisplay(player);
        services.stats().markDirty(player);
    }

    /** 0.3.4 초기화(한 번) + 주인 대조. 바뀐 게 있으면 보너스를 다시 계산. */
    private void migrateAndSync(Player p) {
        PlayerData d = services.data().get(p);
        TitleMigration.Result r = TitleMigration.reset034(d, services.content().achievements().keySet());
        boolean changed = sync(p);
        if (r.ran()) {
            if (!r.revoked().isEmpty()) Log.info("칭호 초기화(0.3.4): " + p.getName() + " — 예전 칭호 " + r.revoked().size() + "개 회수");
            if (r.announce()) Text.send(p, TitleMigration.NOTICE);
        }
        if (changed || r.clearedEquipped() || !r.revoked().isEmpty()) {
            services.stats().markDirty(p);
            services.stats().recalc(p);
        }
    }

    /** records.yml(주인)과 PlayerData 맞추기. 바뀌었으면 true. */
    private boolean sync(Player p) {
        PlayerData d = services.data().get(p);
        Map<String, List<UUID>> owners = new LinkedHashMap<>();
        for (String id : services.content().achievements().keySet()) {
            services.records().get(TitleView.recordKey(id)).ifPresent(rec -> owners.put(id, rec.players()));
        }
        TitleMigration.Sync s = TitleMigration.sync(d, services.content().achievements().keySet(), owners);
        if (!s.revoked().isEmpty()) Log.info("칭호 회수(주인 아님): " + p.getName() + " — " + s.revoked());
        if (!s.restored().isEmpty()) Log.info("칭호 복구(주인 기록): " + p.getName() + " — " + s.restored());
        return s.changed();
    }

    /** 관리자: 칭호를 다시 주인 없는 상태로 (records 기록 삭제 + 접속 중인 주인에게서 회수). */
    public boolean free(String achievementId) {
        String key = TitleView.recordKey(achievementId);
        ServerRecords.Record r = services.records().get(key).orElse(null);
        if (r == null) return false;
        services.records().remove(key);
        for (UUID u : r.players()) {
            Player p = Bukkit.getPlayer(u);
            if (p != null && p.isOnline()) recheck(p);
        }
        return true;
    }

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
            // 층 서버 최초 돌파 기록 (입장 메뉴·/미궁 기록이 쓴다) — 칭호와 별개로 파티 전원 이름
            String key = "first_clear.floor_" + floor;
            boolean firstClear = false;
            if (!members.isEmpty() && !services.records().isClaimed(key)) {
                List<UUID> ids = members.stream().map(Player::getUniqueId).toList();
                List<String> names = members.stream().map(Player::getName).toList();
                Map<String, Object> extra = new LinkedHashMap<>();
                extra.put("difficulty", e.difficulty());
                extra.put("seconds", Math.round(e.seconds()));
                extra.put("party_size", e.partySize());
                if (services.records().claim(key, ids, names, extra)) {
                    firstClear = true;
                    for (Player p : members) services.data().get(p).counter(AchievementRules.P + "first_clear." + floor, 1);
                    Log.info("서버 최초 돌파 기록: 지하 " + floor + "층 — " + String.join(", ", names));
                    Bukkit.getServer().sendMessage(Text.mm("<gradient:#ffd36b:#ff8a3d><b>[서버 최초]</b></gradient> <white>"
                            + Text.escape(String.join(", ", names)) + "</white> <gray>" + (names.size() > 1 ? "파티가" : "님이")
                            + " 지하 " + floor + "층을 서버에서 처음으로 돌파했습니다!"));
                }
            }
            // 스피드런 서버 기록 (이전 기록을 깼을 때만 방송 — 첫 기록은 최초 돌파로 충분)
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
            Fight f = fights.remove(e.instanceId());
            if (f != null && System.currentTimeMillis() - f.at() > FIGHT_TTL_MS) f = null;
            List<Player> ranked = rank(members, f == null ? Map.of() : f.damage(), f == null ? null : f.lastHit());
            award(TitleTrigger.clear(floor, e.partySize(), e.deaths(), e.seconds(), e.difficulty(), firstClear), ranked);
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
            List<Player> list = new ArrayList<>();
            if (e.killer() != null) list.add(e.killer()); // 막타 먼저 (보스가 아니면 이 순서로 받는다)
            for (Player p : e.participants()) if (!list.contains(p)) list.add(p);
            for (Player p : list) {
                if (!p.isOnline()) continue;
                TitleCounters.onKill(store(services.data().get(p)), e.mobId(), rank, e.isBoss());
            }
            List<Player> ranked = list;
            if (e.isBoss()) {
                Map<UUID, Double> dmg = Map.of();
                UUID last = e.killer() == null ? null : e.killer().getUniqueId();
                try {
                    dmg = e.mob().damageByPlayer();
                    if (e.mob().lastHitPlayer() != null) last = e.mob().lastHitPlayer();
                } catch (Throwable ignored) {
                    // 피해 기록이 없는 구현 → 막타·파티 순서
                }
                ranked = rank(list, dmg, last);
                try {
                    var inst = e.mob().instance();
                    if (inst != null) {
                        fights.values().removeIf(f -> System.currentTimeMillis() - f.at() > FIGHT_TTL_MS);
                        fights.put(inst.id(), new Fight(dmg, last, System.currentTimeMillis()));
                    }
                } catch (Throwable ignored) {
                    // 인스턴스 밖 보스
                }
            }
            award(TitleTrigger.kill(e.mobId(), rank, e.isBoss()), ranked);
        });
    }

    /** 피해 많은 순 → 막타 → 원래 순서 (AwardOrder). */
    private static List<Player> rank(List<Player> players, Map<UUID, Double> damage, UUID lastHit) {
        Map<UUID, Player> byId = new LinkedHashMap<>();
        for (Player p : players) if (p != null) byId.putIfAbsent(p.getUniqueId(), p);
        List<Player> out = new ArrayList<>();
        for (UUID u : AwardOrder.rank(new ArrayList<>(byId.keySet()), damage, lastHit)) out.add(byId.get(u));
        return out;
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onLevel(LevelUpEvent e) {
        safe("LevelUpEvent", () -> award(TitleTrigger.level(e.oldLevel(), e.newLevel()), List.of(e.player())));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onObtain(ItemObtainEvent e) {
        safe("ItemObtainEvent", () -> {
            ItemDef def = e.def();
            // 관리자 지급·칭호 보상은 세지 않는다 (칭호 보상이 다른 칭호를 연달아 주지 않게)
            if (def == null || !def.isGear() || "admin".equals(e.source()) || "reward".equals(e.source())) return;
            TitleCounters.onObtain(store(services.data().get(e.player())), def.rarity(),
                    e.stack() == null ? 1 : Math.max(1, e.stack().getAmount()));
            award(TitleTrigger.obtain(def.rarity()), List.of(e.player()));
        });
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onCraft(CraftEvent e) {
        safe("CraftEvent", () -> {
            ItemDef def = e.recipe() == null ? null : services.content().item(e.recipe().result());
            Rarity r = def == null ? null : def.rarity();
            TitleCounters.onCraft(store(services.data().get(e.player())), r);
            award(TitleTrigger.craft(r), List.of(e.player()));
        });
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onEnhance(EnhanceEvent e) {
        safe("EnhanceEvent", () -> {
            TitleCounters.onEnhance(store(services.data().get(e.player())), e.success(), e.to());
            if (e.success()) award(TitleTrigger.enhance(e.to()), List.of(e.player()));
        });
    }

    @Override
    public void onTreasure(Player player, String kind) {
        safe("treasure", () -> award(TitleTrigger.treasure(kind), List.of(player)));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (!p.isOnline()) return;
            safe("join", () -> migrateAndSync(p));
            applyDisplay(p);
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
        // 주인이 아닌 칭호(회수 직전 등)는 보너스를 주지 않는다
        if (!services.data().get(p).hasAchievement(def.id())) return;
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
