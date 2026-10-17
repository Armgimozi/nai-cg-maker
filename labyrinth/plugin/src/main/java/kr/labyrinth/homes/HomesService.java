package kr.labyrinth.homes;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.homes.rules.ClaimRules;
import kr.labyrinth.homes.rules.CrossZoneListener;
import kr.labyrinth.homes.rules.Grace;
import kr.labyrinth.homes.rules.Guard;
import kr.labyrinth.homes.rules.LegacyScan;
import kr.labyrinth.homes.rules.Limits;
import kr.labyrinth.homes.rules.ParcelStore;
import kr.labyrinth.homes.rules.PlotIndex;
import kr.labyrinth.homes.rules.PlotReset;
import kr.labyrinth.homes.rules.PlotRules;
import kr.labyrinth.homes.rules.PlotRulesListener;
import kr.labyrinth.homes.rules.PlotStore;
import kr.labyrinth.homes.rules.TerrainLock;
import kr.labyrinth.homes.rules.TerrainLockListener;
import kr.labyrinth.village.VillageService;
import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.Plugin;

/**
 * 집 구역 실제 구현 (0.3.7) — 소유·권한·지형 잠금·이사 기간·맡긴 짐·관리자 일. 소유: 묶음 B.
 * <ul>
 *   <li>자리: {@link PlotIndex} (구역 집터 = {@link HomesDistrict#plots()} + convert 집터 = {@link PlotStore#customs})</li>
 *   <li>주인: {@link PlotStore} ({@code <월드>/labyrinth-plots.yml}) · 맡긴 짐: {@link ParcelStore} ({@code <월드>/labyrinth-parcels/})</li>
 *   <li>규칙: {@link PlotRules} (순수 표) → 리스너 셋 ({@link TerrainLockListener} LOW · {@link PlotRulesListener} · {@link CrossZoneListener})</li>
 *   <li>비우기·회수: {@link PlotReset} (짐 pending → 블록 지움 → 주인 풂 → 월드 저장 → ready, R3)</li>
 * </ul>
 * 메뉴·표지판·선물은 {@link HomesUi} (묶음 C) 로 넘긴다. 모든 일은 메인 스레드에서.
 */
public final class HomesService implements HomesApi {

    private final Services services;
    private volatile HomesConfig config;
    private volatile HomesDistrict district;
    private volatile HomesUi ui = new NoopHomesUi();
    private final List<Listener> listeners = new ArrayList<>();
    private volatile PlotIndex index = PlotIndex.EMPTY;
    private PlotStore store;
    private ParcelStore parcels;
    private volatile UUID mainUid;
    private final Set<String> busy = ConcurrentHashMap.newKeySet();
    private final Guard guard;
    private final PlotReset reset;
    private final LegacyScan legacy;
    private final Random rnd = new Random();
    private boolean staleWarned;
    /** district remove homes force 가 집을 회수하기 시작해 구역을 다 지울 때까지 (받기·주기 막음, live 11). */
    private volatile boolean districtRemoving;

    public HomesService(Services services, HomesConfig config) {
        this.services = services;
        this.config = config == null ? HomesConfig.DEFAULT : config;
        this.district = HomesDistrict.current();
        this.guard = new Guard(this);
        this.reset = new PlotReset(this);
        this.legacy = new LegacyScan(this);
        loadStores();
        rebuildIndex();
    }

    public Services services() { return services; }

    public HomesConfig config() { return config; }

    void reconfigure(HomesConfig c) {
        this.config = c == null ? HomesConfig.DEFAULT : c;
        checkLockStart();
    }

    public HomesUi ui() { return ui; }

    public void setUi(HomesUi ui) { this.ui = ui == null ? new NoopHomesUi() : ui; }

    /** 기능이 움직이는가 (받기·메뉴·회복): homes.enabled 이고 (집 구역이 지어짐 또는 convert 집터가 있음). */
    public boolean active() { return config.enabled() && (district.built() || !index.isEmpty()); }

    /**
     * 규칙 리스너가 일하는가: 집터가 있음 (homes.enabled: false 여도 — 주인 있는 집은 계속 지킴, live 7) 또는 잠금이 켜짐
     * (집터 없이 {@code /labadmin plot lock on} 한 서버 — 켜졌다고 하고 안 막던 것, exploit L8 · live 4).
     */
    public boolean rulesOn() { return TerrainLock.rulesOn(district.built(), !index.isEmpty(), lockedNow()); }

    /** 집 기능은 껐지만 집터는 지키는 중 (homes.enabled: false + 집터 있음) — 잠금·이사 기간 없이 남의 집만 막는다. */
    public boolean guardOnly() { return !config.enabled(); }

    /** labyrinth-plots.yml 을 읽지 못함 (live 6 안전 모드): 받기·주기·바꾸기·저장 막음, 구역 집터는 모두 남의 집, 들판 상자도 잠금. */
    public boolean storeBroken() { PlotStore st = store; return st != null && st.broken; }

    private HomesResult brokenFail() { return HomesResult.fail(Guard.BROKEN); }

    public HomesDistrict district() { return district; }

    public PlotIndex index() { return index; }

    public Guard guard() { return guard; }

    public PlotStore store() { return store; }

    public ParcelStore parcels() { return parcels; }

    public LegacyScan legacy() { return legacy; }

    public PlotReset resetter() { return reset; }

    public Plugin plugin() { return services.plugin(); }

    // ── 켜기·끄기 (HomesModule 이 부름) ───────────────────────────────────

    void enableRules(Plugin plugin) {
        disableRules();
        PlotRulesListener rules = new PlotRulesListener(this);
        listeners.add(new TerrainLockListener(this));
        listeners.add(rules);
        listeners.add(new CrossZoneListener(this));
        for (Listener l : listeners) Bukkit.getPluginManager().registerEvents(l, plugin);
        Bukkit.getScheduler().runTask(plugin, this::startup);
        sweepTask = Bukkit.getScheduler().runTaskTimer(plugin, () -> {
            try {
                rules.sweepTags(); // 집 동물·탈것 표시 (10초마다)
            } catch (Throwable t) {
                Log.warn("[집] 동물 표시 오류: " + t);
            }
        }, 200L, 200L);
    }

    void disableRules() {
        for (Listener l : listeners) HandlerList.unregisterAll(l);
        listeners.clear();
        legacy.cancel();
        if (sweepTask != null) sweepTask.cancel();
        sweepTask = null;
    }

    private org.bukkit.scheduler.BukkitTask sweepTask;

    /** 켠 뒤 한 번: 비우다 멈춘 짐 마저 · 잠금 시작 · 옛 구역 기록 알림. */
    private void startup() {
        if (storeBroken()) {
            Log.warn("[집] " + PlotStore.FILE + " 를 읽지 못해 안전 모드입니다 — 받기·주기·바꾸기를 막고, 모든 집터를 남의 집으로 봅니다. "
                    + "서버를 끄고 파일을 고치거나 월드 백업의 파일로 바꾼 뒤 다시 켜세요 (이 파일은 덮어쓰지 않습니다).");
            return; // 비우다 멈춘 집도 기록을 고친 뒤에 마저 함
        }
        try {
            reset.recoverAll();
        } catch (Throwable t) {
            Log.error("[집] 비우다 멈춘 집 마저 하기 실패", t);
        }
        checkLockStart();
        if (store != null && store.freshWorld) { // 새 배포 월드인데 잠금이 꺼진 채로 켰음 → 그 뒤 지은 것에는 보통 이사 기간을 준다
            store.freshWorld = false;
            saveStore();
        }
        warnStale();
    }

    private void loadStores() {
        World w = mainWorld();
        if (w == null) {
            store = new PlotStore(null);
            parcels = new ParcelStore(null);
            return;
        }
        store = PlotStore.load(new File(w.getWorldFolder(), PlotStore.FILE));
        if (!store.loadNote.isEmpty()) Log.warn("[집] " + PlotStore.FILE + " " + store.loadNote);
        parcels = new ParcelStore(new File(w.getWorldFolder(), ParcelStore.DIR));
    }

    /** 기록 저장 (실패하면 로그 — 이미 바뀐 메모리 값은 그대로). @return 저장했나 */
    public boolean saveStore() {
        if (storeBroken()) return false; // 읽지 못한 파일을 빈 기록으로 덮지 않음
        try {
            store.save();
            return true;
        } catch (IOException e) {
            Log.warn("[집] " + PlotStore.FILE + " 저장 실패: " + e.getMessage());
            return false;
        }
    }

    public synchronized void rebuildIndex() {
        List<PlotGeom> all = new ArrayList<>(district.plots());
        if (store != null) for (PlotStore.Custom c : store.customs.values()) all.add(c.geom());
        index = new PlotIndex(all);
    }

    // ── 월드 ─────────────────────────────────────────────────────────────

    /** 주 월드 (Bukkit.getWorlds().get(0)). */
    public World mainWorld() {
        UUID u = mainUid;
        if (u != null) {
            World w = Bukkit.getWorld(u);
            if (w != null) return w;
        }
        List<World> all = Bukkit.getWorlds();
        if (all.isEmpty()) return null;
        mainUid = all.get(0).getUID();
        return all.get(0);
    }

    public boolean isMain(World w) {
        if (w == null) return false;
        UUID u = mainUid;
        if (u == null) {
            World m = mainWorld();
            return m != null && m.getUID().equals(w.getUID());
        }
        return u.equals(w.getUID());
    }

    // ── 상태 ─────────────────────────────────────────────────────────────

    @Override
    public boolean enabled() { return config.enabled(); }

    @Override
    public boolean districtBuilt() { return district.built(); }

    /** 지금 잠금이 켜져 있나 (주 월드 기준). */
    public boolean lockedNow() {
        PlotStore st = store;
        return TerrainLock.locked(config.enabled(), config.terrainLock(), st == null ? TerrainLock.State.AUTO : st.lockState, district.built(),
                st != null && st.broken); // 안전 모드: 잠금 상태를 모르면 잠금
    }

    @Override
    public boolean isTerrainLocked(World world) { return isMain(world) && lockedNow(); }

    /** 이사 기간 (관리자가 바꾼 날수 · 시작 시각). */
    public Grace grace() {
        return new Grace(Grace.effectiveDays(store.graceDays, config.legacyGraceDays()), store.graceStartedAt);
    }

    public boolean graceActive() { return lockedNow() && grace().active(System.currentTimeMillis()); }

    @Override
    public int graceDaysLeft() { return lockedNow() ? grace().daysLeft(System.currentTimeMillis()) : 0; }

    @Override
    public String lockState() { return store.lockState.id() + (lockedNow() ? " (켜짐)" : " (꺼짐)"); }

    /** 잠금이 처음 켜졌으면 이사 기간을 시작하고 옛 건물 조사를 한 번 (plan §10). */
    public void checkLockStart() {
        PlotStore st = store;
        if (st == null || st.file() == null || st.broken) return;
        Grace.Start how = Grace.start(lockedNow(), st.lockStartedAt, st.freshWorld);
        if (how == Grace.Start.NONE) return;
        long now = System.currentTimeMillis();
        if (how == Grace.Start.FRESH) {
            // 새 배포 월드 (build_world.sh 가 넣은 fresh_world: true): 옮길 옛 건물이 없다 → 이사 기간·옛 건물 조사 없이 잠금 (live 2 · fun 1)
            st.freshWorld = false;
            st.lockStartedAt = now;
            st.graceStartedAt = now;
            st.graceDays = 0;
            st.legacyScannedAt = now;
            saveStore();
            Log.info("[집] 지형 잠금 켬 — 주 월드에서 집터 밖은 부수거나 지을 수 없습니다 (크리에이티브 관리자 제외) · 새 월드라 이사 기간 없음");
            return;
        }
        st.lockStartedAt = now;
        if (st.graceStartedAt <= 0) st.graceStartedAt = now;
        saveStore();
        int days = grace().days();
        Log.info("[집] 지형 잠금 켬 — 주 월드에서 집터 밖은 부수거나 지을 수 없습니다 (크리에이티브 관리자 제외)"
                + (days > 0 ? " · 이사 기간 " + days + "일 (집터·보호 칸 밖의 사람이 놓은 블록만 부수기)" : " · 이사 기간 없음"));
        if (st.legacyScannedAt <= 0 && plugin() != null && plugin().isEnabled()) legacy.start(null);
    }

    private void warnStale() {
        if (staleWarned || store == null || store.file() == null || !district.built()) return;
        if (store.districtBuild.isEmpty()) {
            store.districtBuild = district.buildId();
            saveStore();
            return;
        }
        if (store.stale(district.buildId())) {
            staleWarned = true;
            Log.warn("[집] 집 주인 기록(" + PlotStore.FILE + ")이 다른 집 구역(" + store.districtBuild + ") 것입니다 — 주인 "
                    + store.districtOwned() + "명. /labadmin plot list 로 확인하세요 (주인 기록은 그대로 둠).");
        }
    }

    // ── 자리 ─────────────────────────────────────────────────────────────

    @Override
    public PlotGeom plotAt(World world, int x, int y, int z) {
        if (world == null || !isMain(world)) return null;
        return index.at(x, y, z);
    }

    /** 열 (x, z) 의 집터 (높이 무관). */
    public PlotGeom columnPlot(World world, int x, int z) {
        if (world == null || !isMain(world)) return null;
        return index.column(x, z);
    }

    @Override
    public PlotGeom plot(String id) { return id == null ? null : index.byId(id); }

    @Override
    public List<PlotGeom> plots() { return index.all(); }

    @Override
    public int zone(World world, int x, int y, int z) {
        if (world == null || !isMain(world)) return ZONE_OUTSIDE;
        PlotGeom p = index.at(x, y, z);
        if (p != null) return p.key();
        VillageService v = VillageService.get();
        if (v != null && v.isProtected(world.getBlockAt(x, y, z))) return ZONE_PROTECTED;
        return ZONE_OUTSIDE;
    }

    // ── 사람 ─────────────────────────────────────────────────────────────

    @Override
    public UUID ownerOf(PlotGeom plot) {
        if (plot == null) return null;
        PlotStore.Owner o = store.owner(plot.id());
        return o == null ? null : o.owner;
    }

    /** 그 사람의 집 (지금 있는 집터만 — 구역이 지워져 남은 옛 기록은 건너뜀). */
    @Override
    public PlotGeom homeOf(UUID player) {
        if (player == null) return null;
        for (Map.Entry<String, PlotStore.Owner> e : store.owners.entrySet()) {
            if (!player.equals(e.getValue().owner)) continue;
            PlotGeom p = index.byId(e.getKey());
            if (p != null) return p;
        }
        return null;
    }

    @Override
    public PlotRole roleIn(Player player, PlotGeom plot) { return player == null ? PlotRole.NONE : roleOf(player.getUniqueId(), plot); }

    /** 비우는 중인 집은 아무도 못 씀 (NONE). */
    public PlotRole roleOf(UUID u, PlotGeom plot) {
        if (u == null || plot == null) return PlotRole.NONE;
        PlotStore.Owner o = store.owner(plot.id());
        if (o == null || busy.contains(PlotStore.norm(plot.id()))) return PlotRole.NONE;
        if (u.equals(o.owner)) return PlotRole.OWNER;
        if (o.trusted.containsKey(u)) return PlotRole.TRUSTED;
        return o.guests ? PlotRole.GUEST : PlotRole.NONE;
    }

    @Override
    public PlotInfo info(PlotGeom plot) {
        if (plot == null) return PlotInfo.empty(null, config.guestsDefault());
        PlotStore.Owner o = store.owner(plot.id());
        if (o == null) return PlotInfo.empty(plot, config.guestsDefault());
        long seen = 0;
        try {
            Player online = Bukkit.getPlayer(o.owner);
            seen = online != null ? System.currentTimeMillis() : Bukkit.getOfflinePlayer(o.owner).getLastSeen();
        } catch (Throwable ignored) {
            // 서버 없이 (시험)
        }
        return new PlotInfo(plot, o.owner, o.ownerName, ClaimRules.displayName(o.name, o.ownerName), new ArrayList<>(o.trusted.keySet()),
                new ArrayList<>(o.trusted.values()), o.guests, o.claimedAt, seen);
    }

    @Override
    public boolean canBuild(Player player, Block block) {
        if (player == null || block == null) return false;
        if (!active() || !isMain(block.getWorld())) return true;
        if (Guard.bypass(player)) return true;
        PlotRules.Where w = guard.where(player, block);
        return PlotRules.decide(PlotRules.Act.PLACE, w, false, false) != PlotRules.Verdict.DENY && w != PlotRules.Where.PROTECTED;
    }

    @Override
    public boolean canOpen(Player player, Block block) {
        if (player == null || block == null) return false;
        if (!active() || !isMain(block.getWorld())) return true;
        if (Guard.bypass(player)) return true;
        PlotRules.Where w = guard.where(player, block);
        if (w == PlotRules.Where.PROTECTED) return false;
        return PlotRules.decide(PlotRules.Act.CONTAINER, w, false, false) != PlotRules.Verdict.DENY;
    }

    @Override
    public boolean busy(PlotGeom plot) { return plot != null && busy.contains(PlotStore.norm(plot.id())); }

    public void markBusy(PlotGeom plot, boolean on) {
        if (plot == null) return;
        if (on) busy.add(PlotStore.norm(plot.id()));
        else busy.remove(PlotStore.norm(plot.id()));
    }

    @Override
    public long reclaimCooldownLeft(UUID player) {
        if (player == null) return 0;
        Long at = store.vacated.get(player);
        return ClaimRules.cooldownLeft(at == null ? 0 : at, System.currentTimeMillis(), config.reclaimCooldownMinutes());
    }

    // ── 일 ───────────────────────────────────────────────────────────────

    private boolean inDungeon(Player p) {
        try {
            return services.dungeon().isInLabyrinth(p) || services.dungeon().currentInstance(p).isPresent();
        } catch (Throwable t) {
            return false;
        }
    }

    @Override
    public HomesResult claim(Player player, String plotId) {
        if (player == null) return HomesResult.fail("플레이어만 받을 수 있습니다.");
        String pre = ClaimRules.preClaim(config.enabled(), storeBroken(), active(), districtRemoving); // 번지를 찾기 전에 (verify 4)
        if (pre != null) return HomesResult.fail(pre);
        UUID u = player.getUniqueId();
        PlotGeom plot;
        if (plotId == null || plotId.isBlank()) {
            plot = ClaimRules.pickAny(index.all(), p -> store.owner(p.id()) == null && !busy(p), rnd);
        } else {
            plot = plot(plotId.trim().replace("번지", ""));
            if (plot == null) return HomesResult.fail("그런 집터가 없습니다: " + Text.escape(plotId));
        }
        String err = ClaimRules.checkClaim(active(), inDungeon(player), homeOf(u) != null, reclaimCooldownLeft(u), plot,
                plot != null && store.owner(plot.id()) != null, plot != null && busy(plot));
        if (err != null) return HomesResult.fail(err);
        int cost = config.claimCost();
        PlayerData data = cost > 0 ? services.data().get(player) : null;
        if (data != null && !data.takeGold(cost)) return HomesResult.fail("골드가 모자랍니다 (" + Text.num(cost) + "G).");
        boolean first = assign(plot, u, player.getName());
        if (!saveStore()) {
            store.owners.remove(PlotStore.norm(plot.id()));
            if (data != null) data.addGold(cost);
            return HomesResult.fail("기록을 저장하지 못했습니다. 관리자에게 알려 주세요.");
        }
        changed(plot);
        try {
            ui.claimed(player, plot, first);
        } catch (Throwable t) {
            Log.error("[집] 받은 뒤 선물 오류", t);
        }
        return HomesResult.ok(ClaimRules.object(plot) + " 받았습니다.");
    }

    /** 주인으로 적음 (저장은 부르는 쪽). @return 처음 받은 집인가 */
    boolean assign(PlotGeom plot, UUID owner, String ownerName) {
        boolean first = store.known.add(owner);
        // 지금 없는 집터를 가리키는 그 사람의 옛 기록은 지움 (한 사람 한 집)
        store.owners.entrySet().removeIf(e -> owner.equals(e.getValue().owner) && index.byId(e.getKey()) == null);
        store.owners.put(PlotStore.norm(plot.id()), new PlotStore.Owner(owner, ownerName, config.guestsDefault(), System.currentTimeMillis()));
        return first;
    }

    @Override
    public HomesResult vacate(Player player, boolean confirmed) {
        if (player == null) return HomesResult.fail("플레이어만 할 수 있습니다.");
        if (storeBroken()) return brokenFail();
        PlotGeom home = homeOf(player.getUniqueId());
        if (home == null) return HomesResult.fail("집이 없습니다.");
        if (busy(home)) return HomesResult.fail(ClaimRules.object(home) + " 정리하는 중입니다.");
        if (!confirmed) {
            String what = home.custom() ? " 비우면 지은 것은 그대로 두고 집만 내놓습니다. 다시 받기는 "
                    : " 비우면 집 안 블록과 물건은 맡긴 짐으로 갑니다. 다시 받기는 "; // convert 집은 블록이 남음 (fun 3)
            return HomesResult.fail(ClaimRules.object(home) + what + ClaimRules.duration(config.reclaimCooldownMinutes() * 60_000L)
                    + " 뒤에 됩니다. 정말이면 /미궁 집 비우기 확인");
        }
        UUID u = player.getUniqueId();
        if (home.custom()) {
            release(home, u, true);
            saveStore();
            changed(home);
            return HomesResult.ok(ClaimRules.object(home) + " 비웠습니다. 지은 것은 그대로 남습니다.");
        }
        reset.start(home, u, player.getName(), "vacate", true).thenAccept(ok -> {
            Player p = Bukkit.getPlayer(u);
            if (p == null) return;
            if (ok) Text.send(p, "<gray>" + ClaimRules.object(home) + " 비웠습니다. 집 안 물건은 맡긴 짐에 있습니다 — <white>/미궁 집 짐</white>");
            else Text.error(p, ClaimRules.object(home) + " 비우지 못했습니다. 관리자에게 알려 주세요.");
        });
        return HomesResult.ok(ClaimRules.object(home) + " 비우는 중입니다.");
    }

    /** 주인 기록을 지움 (자기가 비웠으면 다시 받기 시각을 적음). 저장은 부르는 쪽. */
    public void release(PlotGeom plot, UUID owner, boolean self) {
        PlotStore.Owner o = store.owner(plot.id());
        if (o != null && (owner == null || owner.equals(o.owner))) store.owners.remove(PlotStore.norm(plot.id()));
        if (self && owner != null) store.vacated.put(owner, System.currentTimeMillis());
    }

    /** 소유가 바뀜 → 메뉴·표지판 (묶음 C). */
    public void changed(PlotGeom plot) {
        if (plot == null) return;
        try {
            ui.plotChanged(plot, info(plot));
        } catch (Throwable t) {
            Log.error("[집] 표지판·메뉴 새로 고침 오류 (" + plot.id() + ")", t);
        }
    }

    /** 그 사람이 그 집터 안 상자·탈것 창을 열어 두었으면 닫음. */
    public static void closeViews(Player p, PlotGeom plot) {
        if (p == null || plot == null) return;
        try {
            org.bukkit.Location l = p.getOpenInventory().getTopInventory().getLocation();
            if (l != null && plot.contains(l.getBlockX(), l.getBlockY(), l.getBlockZ())) p.closeInventory();
        } catch (Throwable ignored) {
            // 창 없음
        }
    }

    private PlotStore.Owner myHome(Player owner) {
        PlotGeom home = homeOf(owner.getUniqueId());
        return home == null ? null : store.owner(home.id());
    }

    /** 이름으로 플레이어 (접속 중 → 캐시) — 없으면 null. */
    public static OfflinePlayer findPlayer(String name) {
        if (name == null || name.isBlank()) return null;
        Player p = Bukkit.getPlayerExact(name.trim());
        if (p != null) return p;
        OfflinePlayer op = Bukkit.getOfflinePlayerIfCached(name.trim());
        return op == null || op.getName() == null ? null : op;
    }

    @Override
    public HomesResult invite(Player owner, String name) {
        if (storeBroken()) return brokenFail();
        PlotStore.Owner o = owner == null ? null : myHome(owner);
        if (o == null) return HomesResult.fail("집이 없습니다.");
        OfflinePlayer t = findPlayer(name);
        if (t == null) return HomesResult.fail("그 이름의 플레이어를 찾지 못했습니다: " + Text.escape(name));
        String err = ClaimRules.checkInvite(t.getUniqueId().equals(o.owner), o.trusted.containsKey(t.getUniqueId()), o.trusted.size(),
                config.maxTrusted());
        if (err != null) return HomesResult.fail(err);
        o.trusted.put(t.getUniqueId(), t.getName());
        if (!saveStore()) {
            o.trusted.remove(t.getUniqueId());
            return HomesResult.fail("기록을 저장하지 못했습니다.");
        }
        PlotGeom home = homeOf(o.owner);
        changed(home);
        if (t instanceof Player tp && tp.isOnline() && home != null) {
            Text.send(tp, "<gray>" + Text.escape(owner.getName()) + "님이 <white>" + home.label() + "</white>에 초대했습니다. 같이 짓고 상자를 쓸 수 있습니다.");
        }
        return HomesResult.ok(Text.escape(t.getName()) + "님을 초대했습니다.");
    }

    @Override
    public HomesResult kick(Player owner, String name) {
        if (storeBroken()) return brokenFail();
        PlotStore.Owner o = owner == null ? null : myHome(owner);
        if (o == null) return HomesResult.fail("집이 없습니다.");
        if (name == null || name.isBlank()) return HomesResult.fail("이름을 적어 주세요.");
        UUID hit = null;
        for (Map.Entry<UUID, String> e : o.trusted.entrySet()) if (e.getValue() != null && e.getValue().equalsIgnoreCase(name.trim())) hit = e.getKey();
        if (hit == null) {
            OfflinePlayer t = findPlayer(name);
            if (t != null && o.trusted.containsKey(t.getUniqueId())) hit = t.getUniqueId();
        }
        if (hit == null) return HomesResult.fail("초대한 사람 중에 없습니다: " + Text.escape(name));
        String was = o.trusted.remove(hit);
        saveStore();
        PlotGeom home = homeOf(o.owner);
        closeViews(Bukkit.getPlayer(hit), home); // 열어 둔 상자 창도 닫음 (exploit L2)
        changed(home);
        return HomesResult.ok(Text.escape(was == null || was.isEmpty() ? name : was) + "님을 내보냈습니다.");
    }

    @Override
    public HomesResult rename(Player owner, String name) {
        if (storeBroken()) return brokenFail();
        PlotStore.Owner o = owner == null ? null : myHome(owner);
        if (o == null) return HomesResult.fail("집이 없습니다.");
        long left = ClaimRules.renameLeft(o.renamedAt, System.currentTimeMillis(), config.renameCooldownMinutes());
        if (left > 0) return HomesResult.fail("이름은 " + ClaimRules.duration(left) + " 뒤에 바꿀 수 있습니다.");
        String clean = ClaimRules.cleanName(name);
        o.name = clean;
        o.renamedAt = System.currentTimeMillis();
        saveStore();
        changed(homeOf(o.owner));
        return HomesResult.ok(clean.isEmpty() ? "집 이름을 지웠습니다." : "집 이름을 바꿨습니다: " + Text.escape(clean));
    }

    /** 관리자: 이름 바꾸기 (쿨다운 없음, R18). 빈 글 = 기본 이름. */
    public HomesResult adminRename(PlotGeom plot, String name) {
        if (storeBroken()) return brokenFail();
        PlotStore.Owner o = plot == null ? null : store.owner(plot.id());
        if (o == null) return HomesResult.fail("주인이 없는 집입니다.");
        o.name = ClaimRules.cleanName(name);
        saveStore();
        changed(plot);
        return HomesResult.ok(plot.label() + " 이름: " + (o.name.isEmpty() ? "(기본) " + Text.escape(ClaimRules.displayName("", o.ownerName)) : Text.escape(o.name)));
    }

    @Override
    public HomesResult setGuests(Player owner, boolean allow) {
        if (storeBroken()) return brokenFail();
        PlotStore.Owner o = owner == null ? null : myHome(owner);
        if (o == null) return HomesResult.fail("집이 없습니다.");
        o.guests = allow;
        saveStore();
        PlotGeom home = homeOf(o.owner);
        if (!allow && home != null) for (Player pl : Bukkit.getOnlinePlayers()) {
            if (roleOf(pl.getUniqueId(), home) == PlotRole.NONE) closeViews(pl, home); // 손님이 열어 둔 작업대 창
        }
        changed(home);
        return HomesResult.ok(allow ? "손님을 받습니다. 손님은 문·작업대·종만 쓸 수 있습니다." : "손님을 받지 않습니다.");
    }

    @Override
    public List<ItemStack> parcel(UUID player) {
        List<ItemStack> out = new ArrayList<>();
        for (byte[] b : parcels.ready(player)) {
            ItemStack it = item(b);
            if (it != null) out.add(it);
        }
        return out;
    }

    @Override
    public HomesResult takeParcel(Player player) {
        if (player == null) return HomesResult.fail("플레이어만 받을 수 있습니다.");
        UUID u = player.getUniqueId();
        List<byte[]> raw = parcels.ready(u);
        if (raw.isEmpty()) return HomesResult.fail("맡긴 짐이 없습니다.");
        // 들어갈 만큼만 고름 (가방 사본에 넣어 봄) → 파일에서 먼저 뺌 → 가방에 넣음 → 못 넣은 것은 다시 파일로
        Inventory sim = Bukkit.createInventory(null, 36);
        ItemStack[] storage = player.getInventory().getStorageContents();
        for (int i = 0; i < Math.min(36, storage.length); i++) sim.setItem(i, storage[i] == null ? null : storage[i].clone());
        List<Integer> fit = new ArrayList<>();
        int bad = 0;
        for (int i = 0; i < raw.size(); i++) {
            ItemStack it = item(raw.get(i));
            if (it == null) {
                bad++;
                continue;
            }
            if (sim.addItem(it.clone()).isEmpty()) fit.add(i);
        }
        if (fit.isEmpty()) return HomesResult.fail(bad > 0 ? "맡긴 짐을 읽지 못했습니다. 관리자에게 알려 주세요." : "가방에 빈칸이 없습니다.");
        List<byte[]> taken;
        try {
            taken = parcels.remove(u, fit);
        } catch (IOException e) {
            Log.warn("[집] 맡긴 짐 파일 쓰기 실패 (" + player.getName() + "): " + e.getMessage());
            return HomesResult.fail("맡긴 짐을 꺼내지 못했습니다. 관리자에게 알려 주세요.");
        }
        List<byte[]> back = new ArrayList<>();
        int given = 0;
        for (byte[] b : taken) {
            ItemStack it = item(b);
            if (it == null) continue;
            Map<Integer, ItemStack> left = player.getInventory().addItem(it);
            if (left.isEmpty()) given++;
            else for (ItemStack l : left.values()) back.add(l.serializeAsBytes());
        }
        if (!back.isEmpty()) {
            try {
                parcels.add(u, player.getName(), back);
            } catch (IOException e) {
                Log.warn("[집] 못 준 짐 되돌리기 실패 (" + player.getName() + ", " + back.size() + "묶음): " + e.getMessage());
            }
        }
        try {
            player.saveData(); // 가방을 바로 저장 (짐 파일에서 뺀 것이 서버가 꺼져도 남게)
        } catch (Throwable ignored) {
            // 저장은 서버가 곧 다시 함
        }
        int remain = parcels.readyCount(u);
        return HomesResult.ok("맡긴 짐 " + given + "묶음을 받았습니다." + (remain > 0 ? " 가방이 차서 " + remain + "묶음은 그대로 있습니다." : ""));
    }

    static ItemStack item(byte[] b) {
        try {
            ItemStack it = ItemStack.deserializeBytes(b);
            return it == null || it.getType().isAir() ? null : it;
        } catch (Throwable t) {
            return null;
        }
    }

    // ── 관리자 일 (HomesAdminCommands) ───────────────────────────────────

    /** 관리자가 줌 (R18: 집이 있는 사람은 거절). */
    public HomesResult adminGive(PlotGeom plot, OfflinePlayer target) {
        if (storeBroken()) return brokenFail();
        if (districtRemoving) return HomesResult.fail("집 구역을 지우는 중입니다.");
        if (plot == null) return HomesResult.fail("그런 집터가 없습니다.");
        if (target == null) return HomesResult.fail("그 플레이어를 찾지 못했습니다.");
        PlotGeom has = homeOf(target.getUniqueId());
        if (has != null) return HomesResult.fail(Text.escape(target.getName()) + "님은 이미 집이 있습니다 (" + has.label() + ").");
        if (store.owner(plot.id()) != null) return HomesResult.fail(ClaimRules.topic(plot) + " 주인이 있습니다. 먼저 reclaim 하세요.");
        if (busy(plot)) return HomesResult.fail(ClaimRules.object(plot) + " 정리하는 중입니다.");
        boolean first = assign(plot, target.getUniqueId(), target.getName());
        saveStore();
        changed(plot);
        if (target instanceof Player p && p.isOnline()) {
            Text.send(p, "<gray>관리자가 <white>" + plot.label() + "</white>를 주었습니다. <white>/미궁 집</white>");
            try {
                ui.claimed(p, plot, first);
            } catch (Throwable t) {
                Log.error("[집] 받은 뒤 선물 오류", t);
            }
        }
        return HomesResult.ok(Text.escape(target.getName()) + "님에게 " + ClaimRules.object(plot) + " 주었습니다.");
    }

    /** 관리자 회수: 비우기와 같음, 짐은 원래 주인 몫 (다시 받기 시간은 세지 않음). convert 집은 소유만 풂 (R3e). */
    public CompletableFuture<Boolean> adminReclaim(PlotGeom plot) {
        if (storeBroken()) return CompletableFuture.completedFuture(false);
        PlotStore.Owner o = plot == null ? null : store.owner(plot.id());
        if (o == null) return CompletableFuture.completedFuture(false);
        if (busy(plot)) return CompletableFuture.completedFuture(false);
        if (plot.custom()) {
            release(plot, o.owner, false);
            saveStore();
            changed(plot);
            return CompletableFuture.completedFuture(true);
        }
        return reset.start(plot, o.owner, o.ownerName, "reclaim", false);
    }

    /** convert: 옛 건물 → 그 사람의 집터 (블록은 그대로). 상자 크기·높이는 {@link kr.labyrinth.homes.admin.ConvertRules} 가 먼저 본다. */
    public HomesResult convert(OfflinePlayer target, int x0, int z0, int x1, int z1, int yMin, int yMax, int floorY, double hx, double hy,
                               double hz) {
        if (storeBroken()) return brokenFail();
        if (target == null) return HomesResult.fail("그 플레이어를 찾지 못했습니다.");
        PlotGeom has = homeOf(target.getUniqueId());
        if (has != null) return HomesResult.fail(Text.escape(target.getName()) + "님은 이미 집이 있습니다 (" + has.label() + ").");
        PlotGeom over = index.overlapping(x0, z0, x1, z1, yMin, yMax);
        if (over != null) return HomesResult.fail(over.label() + "와 겹칩니다.");
        World w = mainWorld();
        VillageService v = VillageService.get();
        if (v != null && w != null) {
            for (int x = x0; x <= x1; x++) for (int z = z0; z <= z1; z++) for (int y = yMin; y <= yMax; y++) {
                if (v.isProtected(w.getBlockAt(x, y, z))) return HomesResult.fail("보호 칸 (" + x + ", " + y + ", " + z + ") 과 겹칩니다.");
            }
        }
        int n = store.nextCustomN();
        String id = "c" + n;
        store.customs.put(id, new PlotStore.Custom(id, n, x0, z0, x1, z1, yMin, yMax, floorY, hx, hy, hz, 0f));
        rebuildIndex();
        PlotGeom plot = index.byId(id);
        boolean first = assign(plot, target.getUniqueId(), target.getName());
        saveStore();
        changed(plot);
        if (target instanceof Player p && p.isOnline()) {
            Text.send(p, "<gray>관리자가 지은 곳을 집터 <white>" + id + "</white> 로 바꿨습니다. 그 안에서 짓고 부술 수 있습니다.");
            try {
                ui.claimed(p, plot, first);
            } catch (Throwable t) {
                Log.error("[집] 받은 뒤 선물 오류", t);
            }
        }
        return HomesResult.ok(id + " 집터를 만들었습니다: x " + x0 + ".." + x1 + " · z " + z0 + ".." + z1 + " · y " + yMin + ".." + yMax + " → "
                + Text.escape(target.getName()));
    }

    /** unconvert: 기록만 지움 (블록 그대로, 다시 잠김). */
    public HomesResult unconvert(PlotGeom plot) {
        if (storeBroken()) return brokenFail();
        if (plot == null || !plot.custom()) return HomesResult.fail("convert 집터 (c1, c2 …) 만 됩니다.");
        store.customs.remove(PlotStore.norm(plot.id()));
        store.owners.remove(PlotStore.norm(plot.id()));
        rebuildIndex();
        saveStore();
        changed(plot);
        return HomesResult.ok(plot.id() + " 집터를 지웠습니다. 블록은 그대로입니다.");
    }

    public HomesResult setLock(TerrainLock.State st) {
        if (storeBroken()) return brokenFail();
        store.lockState = st;
        saveStore();
        checkLockStart();
        return HomesResult.ok("지형 잠금: " + st.id() + " → 지금 " + (lockedNow() ? "켜짐" : "꺼짐")
                + (!config.terrainLock() ? " (config homes.terrain_lock: false 라 늘 꺼짐)" : "")
                + (lockedNow() && index.isEmpty() ? " — 집터가 없어 아무도 짓지 못합니다 (convert 로 집터를 주세요)" : ""));
    }

    public HomesResult setGraceDays(int days) {
        if (storeBroken()) return brokenFail();
        store.graceDays = Math.max(0, Math.min(365, days));
        saveStore();
        checkLockStart();
        Grace g = grace();
        return HomesResult.ok("이사 기간 " + g.days() + "일" + (g.startedAt() > 0 ? " · " + g.daysLeft(System.currentTimeMillis()) + "일 남음" : " · 잠금이 켜지면 시작"));
    }

    // ── 구역 ─────────────────────────────────────────────────────────────

    @Override
    public void districtChanged(HomesDistrict d) {
        this.district = d == null ? HomesDistrict.NONE : d;
        rebuildIndex();
        if (district.built() && store != null && store.file() != null) {
            if (!store.file().isFile()) saveStore(); // 빈 labyrinth-plots.yml (plan §2 짓는 순서)
            warnStale();
        }
        checkLockStart();
    }

    @Override
    public int ownedCount() { return store == null ? 0 : store.districtOwned(); }

    @Override
    public CompletableFuture<Integer> reclaimAll(CommandSender by, String why) {
        if (storeBroken()) return CompletableFuture.failedFuture(new IllegalStateException(PlotStore.FILE + " 를 읽지 못함"));
        districtRemoving = true; // 회수부터 구역을 다 지울 때까지 받기·주기 막음 (live 11)
        List<PlotGeom> owned = new ArrayList<>();
        for (PlotGeom p : index.all()) if (!p.custom() && store.owner(p.id()) != null) owned.add(p);
        CompletableFuture<Integer> done = new CompletableFuture<>();
        Log.info("[집] 모든 집 회수 시작 (" + owned.size() + "채)" + (why == null || why.isBlank() ? "" : " — " + why));
        reclaimNext(owned, 0, 0, by, done);
        return done;
    }

    private void reclaimNext(List<PlotGeom> list, int i, int count, CommandSender by, CompletableFuture<Integer> done) {
        if (i >= list.size()) {
            Log.info("[집] 모든 집 회수 끝 — " + count + "채");
            done.complete(count);
            return;
        }
        PlotGeom p = list.get(i);
        adminReclaim(p).whenComplete((ok, err) -> Bukkit.getScheduler().runTask(plugin(), () -> {
            boolean good = err == null && Boolean.TRUE.equals(ok);
            if (by != null) Text.send(by, "<gray>" + p.label() + " 회수 " + (good ? "<green>됨" : "<red>실패"));
            reclaimNext(list, i + 1, count + (good ? 1 : 0), by, done);
        }));
    }

    @Override
    public void districtRemoving(boolean on) { districtRemoving = on; }

    @Override
    public void districtRemoved() {
        districtRemoving = false;
        List<String> drop = new ArrayList<>();
        for (String id : store.owners.keySet()) if (!store.customs.containsKey(id)) drop.add(id);
        for (String id : drop) store.owners.remove(id);
        store.lockState = TerrainLock.State.AUTO;
        store.districtBuild = "";
        saveStore();
        rebuildIndex();
        Log.info("[집] 집 구역 지움 — 주인 기록 " + drop.size() + "개 지움 · 잠금 auto");
    }

    // ── 메뉴 ─────────────────────────────────────────────────────────────

    @Override
    public void openEstate(Player player) { ui.openEstate(player); }

    @Override
    public void openPlotSign(Player player, String plotId) { ui.openPlot(player, plot(plotId)); }

    // ── 자가 진단 ────────────────────────────────────────────────────────

    @Override
    public List<String> selfTestLines() {
        List<String> out = new ArrayList<>();
        out.add(rulesSelfTest());
        try {
            out.add(ui.selfTestLine());
        } catch (Throwable t) {
            out.add("[집 메뉴 자가 진단] 결과: 예외 1 · " + t.getClass().getSimpleName());
        }
        return out;
    }

    /** "[집터 자가 진단] 결과: 예외 0 · index=ok(2000/2000) · rules=ok(n/n) · owners=n · orphans=0 · over_cap=0 · parcels_pending=0 · lock=on · grace=n일". */
    String rulesSelfTest() {
        int errors = 0;
        StringBuilder sb = new StringBuilder();
        try {
            int[] r = indexCheck(2000);
            sb.append(" · index=").append(r[0] == r[1] ? "ok" : "FAIL").append('(').append(r[0]).append('/').append(r[1]).append(')');
        } catch (Throwable t) {
            errors++;
            sb.append(" · index=예외");
        }
        try {
            int[] r = PlotRules.selfCheck();
            sb.append(" · rules=").append(r[0] == r[1] ? "ok" : "FAIL").append('(').append(r[0]).append('/').append(r[1]).append(')');
        } catch (Throwable t) {
            errors++;
            sb.append(" · rules=예외");
        }
        int owners = 0, orphans = 0;
        for (String id : store.owners.keySet()) {
            if (index.byId(id) == null) orphans++;
            else owners++;
        }
        sb.append(" · owners=").append(owners).append(" · orphans=").append(orphans);
        try {
            int[] oc = overCap();
            sb.append(" · over_cap=").append(oc[0]).append(oc[1] > 0 ? "(안 불러온 " + oc[1] + "채 건너뜀)" : "");
        } catch (Throwable t) {
            errors++;
            sb.append(" · over_cap=예외");
        }
        try {
            sb.append(" · parcels_pending=").append(parcels.pendingOwners().size());
        } catch (Throwable t) {
            errors++;
            sb.append(" · parcels_pending=예외");
        }
        sb.append(" · lock=").append(lockedNow() ? "on" : "off").append(store.lockState == TerrainLock.State.AUTO ? "" : "(" + store.lockState.id() + ")");
        int left = graceDaysLeft();
        sb.append(" · grace=").append(left > 0 ? left + "일" : "없음");
        if (storeBroken()) sb.append(" · store=broken");
        if (!config.enabled() && rulesOn()) sb.append(" · homes=off(집터만 지킴)");
        if (!active()) sb.append(" · 집 구역 ").append(district.state());
        return "[집터 자가 진단] 결과: 예외 " + errors + sb;
    }

    /** 무작위 점 n 개: 색인 결과 = 모든 집터를 다 본 결과. [맞음, 전체]. */
    int[] indexCheck(int n) {
        List<PlotGeom> all = index.all();
        if (all.isEmpty()) return new int[] {n, n};
        int x0 = Integer.MAX_VALUE, z0 = Integer.MAX_VALUE, x1 = Integer.MIN_VALUE, z1 = Integer.MIN_VALUE, y0 = Integer.MAX_VALUE, y1 = Integer.MIN_VALUE;
        for (PlotGeom p : all) {
            x0 = Math.min(x0, p.x0());
            z0 = Math.min(z0, p.z0());
            x1 = Math.max(x1, p.x1());
            z1 = Math.max(z1, p.z1());
            y0 = Math.min(y0, p.yMin());
            y1 = Math.max(y1, p.yMax());
        }
        Random r = new Random(37);
        int ok = 0;
        for (int i = 0; i < n; i++) {
            int x = x0 - 4 + r.nextInt(x1 - x0 + 9), z = z0 - 4 + r.nextInt(z1 - z0 + 9), y = y0 - 4 + r.nextInt(y1 - y0 + 9);
            PlotGeom want = null;
            for (PlotGeom p : all) if (p.contains(x, y, z)) {
                want = p;
                break;
            }
            if (want == index.at(x, y, z)) ok++;
        }
        return new int[] {ok, n};
    }

    /** [한도를 넘은 집, 청크가 안 불러와져 건너뛴 집]. */
    int[] overCap() {
        World w = mainWorld();
        if (w == null) return new int[] {0, 0};
        int over = 0, skipped = 0;
        for (PlotGeom p : index.all()) {
            if (!loaded(w, p)) {
                skipped++;
                continue;
            }
            if (Limits.overTickParts(PlotRulesListener.countParts(w, p, null), config.tickParts().total(), config.tickParts().hoppers())) over++;
        }
        return new int[] {over, skipped};
    }

    /** 그 집터의 청크가 모두 불러와져 있나. */
    public static boolean loadedPlot(World w, PlotGeom p) { return loaded(w, p); }

    static boolean loaded(World w, PlotGeom p) {
        for (int cx = p.x0() >> 4; cx <= p.x1() >> 4; cx++) for (int cz = p.z0() >> 4; cz <= p.z1() >> 4; cz++) if (!w.isChunkLoaded(cx, cz)) return false;
        return true;
    }
}
