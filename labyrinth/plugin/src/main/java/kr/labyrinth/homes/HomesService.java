package kr.labyrinth.homes;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import kr.labyrinth.Services;
import kr.labyrinth.homes.rules.CrossZoneListener;
import kr.labyrinth.homes.rules.PlotRulesListener;
import kr.labyrinth.homes.rules.TerrainLockListener;
import kr.labyrinth.village.VillageService;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.Plugin;

/**
 * 집 구역 실제 구현 (0.3.7) — 소유·권한·지형 잠금·이사 기간·맡긴 짐·관리자 일. 소유: 묶음 B.
 * <p>
 * 뼈대: 자리 찾기(plotAt·plot·plots·zone)만 구역 기록 그대로 하고, 나머지는 "준비 중" (아무것도 막지 않음 — 지형 잠금 꺼짐).
 * 묶음 B 가 {@code rules/}(PlotIndex·PlotStore·ParcelStore·PlotRules·TerrainLock·Grace·TickParts …) 로 채운다.
 * 메뉴·표지판·선물은 {@link HomesUi} (묶음 C) 로 넘긴다.
 */
public final class HomesService implements HomesApi {

    private final Services services;
    private volatile HomesConfig config;
    private volatile HomesDistrict district;
    private volatile HomesUi ui = new NoopHomesUi();
    private final List<Listener> listeners = new ArrayList<>();

    public HomesService(Services services, HomesConfig config) {
        this.services = services;
        this.config = config == null ? HomesConfig.DEFAULT : config;
        this.district = HomesDistrict.current();
    }

    public Services services() { return services; }

    public HomesConfig config() { return config; }

    void reconfigure(HomesConfig c) { this.config = c == null ? HomesConfig.DEFAULT : c; }

    public HomesUi ui() { return ui; }

    public void setUi(HomesUi ui) { this.ui = ui == null ? new NoopHomesUi() : ui; }

    /** 기능이 움직이는가: homes.enabled 이고 집 구역이 지어짐. (convert 집만 있는 서버는 묶음 B 가 더한다.) */
    public boolean active() { return config.enabled() && district.built(); }

    public HomesDistrict district() { return district; }

    // ── 리스너 (homes.enabled 일 때만 — 처리기 안에서 active() 를 본다) ──

    void enableRules(Plugin plugin) {
        disableRules();
        listeners.add(new PlotRulesListener(this));
        listeners.add(new TerrainLockListener(this));
        listeners.add(new CrossZoneListener(this));
        for (Listener l : listeners) Bukkit.getPluginManager().registerEvents(l, plugin);
    }

    void disableRules() {
        for (Listener l : listeners) HandlerList.unregisterAll(l);
        listeners.clear();
    }

    // ── 상태 ─────────────────────────────────────────────────────────────

    @Override
    public boolean enabled() { return config.enabled(); }

    @Override
    public boolean districtBuilt() { return district.built(); }

    @Override
    public boolean isTerrainLocked(World world) { return false; } // 묶음 B: TerrainLock (auto·on·off, 주 월드만)

    // ── 자리 ─────────────────────────────────────────────────────────────

    @Override
    public PlotGeom plotAt(World world, int x, int y, int z) {
        if (world == null || !isMain(world)) return null;
        for (PlotGeom p : district.plots()) if (p.contains(x, y, z)) return p; // 묶음 B: PlotIndex (청크 → 집터) + convert 집터
        return null;
    }

    @Override
    public PlotGeom plot(String id) {
        if (id == null) return null;
        for (PlotGeom p : district.plots()) if (p.id().equalsIgnoreCase(id.trim())) return p;
        return null;
    }

    @Override
    public List<PlotGeom> plots() { return district.plots(); }

    @Override
    public int zone(World world, int x, int y, int z) {
        PlotGeom p = plotAt(world, x, y, z);
        if (p != null) return p.key();
        VillageService v = VillageService.get();
        if (v != null && world != null && v.isProtected(world.getBlockAt(x, y, z))) return ZONE_PROTECTED;
        return ZONE_OUTSIDE;
    }

    static boolean isMain(World w) {
        List<World> all = Bukkit.getWorlds();
        return !all.isEmpty() && all.get(0).equals(w);
    }

    // ── 사람 (묶음 B: PlotStore) ──────────────────────────────────────────

    @Override
    public UUID ownerOf(PlotGeom plot) { return null; }

    @Override
    public PlotGeom homeOf(UUID player) { return null; }

    @Override
    public PlotRole roleIn(Player player, PlotGeom plot) { return PlotRole.NONE; }

    @Override
    public PlotInfo info(PlotGeom plot) { return PlotInfo.empty(plot, config.guestsDefault()); }

    @Override
    public boolean canBuild(Player player, Block block) { return true; }

    @Override
    public boolean canOpen(Player player, Block block) { return true; }

    // ── 일 (묶음 B) ──────────────────────────────────────────────────────

    @Override
    public HomesResult claim(Player player, String plotId) { return HomesResult.notReady(); }

    @Override
    public HomesResult vacate(Player player, boolean confirmed) { return HomesResult.notReady(); }

    @Override
    public HomesResult invite(Player owner, String name) { return HomesResult.notReady(); }

    @Override
    public HomesResult kick(Player owner, String name) { return HomesResult.notReady(); }

    @Override
    public HomesResult rename(Player owner, String name) { return HomesResult.notReady(); }

    @Override
    public HomesResult setGuests(Player owner, boolean allow) { return HomesResult.notReady(); }

    @Override
    public List<ItemStack> parcel(UUID player) { return List.of(); }

    @Override
    public HomesResult takeParcel(Player player) { return HomesResult.notReady(); }

    // ── 구역 ─────────────────────────────────────────────────────────────

    @Override
    public void districtChanged(HomesDistrict d) { this.district = d == null ? HomesDistrict.NONE : d; }

    @Override
    public int ownedCount() { return 0; }

    @Override
    public CompletableFuture<Integer> reclaimAll(CommandSender by, String why) { return CompletableFuture.completedFuture(0); }

    @Override
    public void districtRemoved() { }

    // ── 메뉴 ─────────────────────────────────────────────────────────────

    @Override
    public void openEstate(Player player) { ui.openEstate(player); }

    @Override
    public void openPlotSign(Player player, String plotId) { ui.openPlot(player, plot(plotId)); }

    // ── 자가 진단 ────────────────────────────────────────────────────────

    @Override
    public List<String> selfTestLines() {
        return List.of("[집터 자가 진단] 결과: 준비 중 · 구역 " + district.state() + " · 집터 " + district.plots().size(), ui.selfTestLine());
    }
}
