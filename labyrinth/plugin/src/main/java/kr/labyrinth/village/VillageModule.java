package kr.labyrinth.village;

import java.util.function.IntSupplier;
import kr.labyrinth.LabyrinthPlugin;
import kr.labyrinth.Services;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;

/**
 * 마을 모듈 (VILLAGE.md §4): 청사진(jar village/) 로드 → VillageService(실행 중 마을 + 야생 막기 WildService) → 명령
 * (/labadmin village … · /labadmin wild … · /미궁 마을). 마을은 미리 지은 월드에만 있다 — 다른 월드에 자동으로 짓지 않는다.
 */
public final class VillageModule implements Module {

    private final Services services;
    private final IntSupplier forgetOldEntrance;
    private VillageLibrary library;
    private DistrictLibrary districts;
    private VillageService service;

    /** @param forgetOldEntrance 예전 석문 기록(entrance.yml)을 복원 없이 버리는 dungeon 쪽 함수 (버린 칸 수) */
    public VillageModule(Services services, IntSupplier forgetOldEntrance) {
        this.services = services;
        this.forgetOldEntrance = forgetOldEntrance;
    }

    @Override
    public String name() { return "village"; }

    @Override
    public void enable() {
        loadLibrary();
        service = new VillageService(this);
        service.enable();
        new VillageCommands(this).register();
    }

    @Override
    public void disable() {
        VillageJob.cancelRunning();
        VillageJob.abortNow();
        if (service != null) service.disable();
    }

    @Override
    public void reload() {
        if (VillageJob.running() == null) loadLibrary();
        if (service != null && service.wild() != null) service.wild().refresh("reload"); // config wild 다시 읽기 (경계·스폰)
    }

    void loadLibrary() {
        library = VillageLibrary.load(services.plugin());
        if (library.ok()) {
            Log.info("[마을] 청사진: " + library.layout.name + " · 조각 " + library.pieces.size() + "종 / 배치 " + library.layout.pieces.size()
                    + "개 · 길 " + library.layout.paths.size() + "개" + (library.problems.isEmpty() ? "" : " · 문제 " + library.problems.size() + "건"));
        } else {
            Log.info("[마을] 청사진 없음 — village build/survey 는 쓸 수 없습니다 (" + String.join(" · ", library.problems) + ")");
        }
        for (String p : library.problems) Log.warn("[마을 청사진] " + p);
        districts = DistrictLibrary.load(services.plugin());
        for (DistrictLibrary.Entry e : districts.districts) {
            Log.info("[마을] 구역 청사진: " + e.layout().name + " · 조각 " + e.layout().pieces.size() + " · 길 " + e.layout().paths.size()
                    + " · 자리 " + String.join("·", e.layout().siteIds()) + " · 지문 " + (e.fp() == null ? "없음" : e.fp().worlds.size() + "개")
                    + (e.ok() ? "" : " · 문제 " + String.join(" · ", e.problems())));
        }
        for (String p : districts.problems) Log.warn("[구역 청사진] " + p);
    }

    public Services services() { return services; }

    public LabyrinthPlugin plugin() { return services.plugin(); }

    public VillageLibrary library() { return library; }

    /** 구역 청사진 (0.3.6.1 광산 마을 · 0.3.7 집 구역 — order 차례). */
    public DistrictLibrary districts() { return districts; }

    /**
     * 구역 하나의 짓기 설정 (구역 기계가 씀). enabled = 그 구역을 저절로 지을 수 있는 모듈이 켜짐 (광산 mine.enabled · 집 homes.enabled).
     * 관리자 명령(district build)은 enabled 와 상관없이 된다.
     */
    record DistrictConf(boolean enabled, boolean autoBuild, java.util.List<String> sites, int blocksPerTick, boolean notifyAdmins) {}

    /**
     * config 의 구역 절 (키가 없으면 기본값 — 0.3.6 이하 config.yml 에는 mine.district, 0.3.6.1 이하에는 homes 절이 없다):
     * mine → {@code mine.district} · homes → {@code homes.district} (0.3.7, {@link kr.labyrinth.homes.HomesConfig#district()}).
     */
    DistrictConf districtConfig(String id) {
        if ("homes".equals(id)) {
            try {
                kr.labyrinth.homes.HomesConfig h = kr.labyrinth.homes.HomesConfig.fromRoot(plugin().getConfig());
                var d = h.district();
                return new DistrictConf(h.enabled(), d.autoBuild(), d.sites(), d.blocksPerTick(), d.notifyAdmins());
            } catch (Throwable t) {
                var d = kr.labyrinth.homes.HomesConfig.DEFAULT_DISTRICT;
                return new DistrictConf(true, d.autoBuild(), d.sites(), d.blocksPerTick(), d.notifyAdmins());
            }
        }
        boolean enabled = true;
        kr.labyrinth.mine.MineConfig.District d;
        try {
            kr.labyrinth.mine.MineConfig m = kr.labyrinth.mine.MineConfig.fromRoot(plugin().getConfig());
            enabled = m.enabled();
            d = m.district();
        } catch (Throwable t) {
            d = kr.labyrinth.mine.MineConfig.DEFAULT_DISTRICT;
        }
        return new DistrictConf(enabled, d.autoBuild(), d.sites(), d.blocksPerTick(), d.notifyAdmins());
    }

    /** 집터 짓기 높이 창 [바닥 − below, 바닥 + above] 의 below·above (config homes.height — 구역 기록 plots: 에 남김). */
    int[] homesHeight() {
        try {
            kr.labyrinth.homes.HomesConfig h = kr.labyrinth.homes.HomesConfig.fromRoot(plugin().getConfig());
            return new int[] {h.heightBelow(), h.heightAbove()};
        } catch (Throwable t) {
            return new int[] {kr.labyrinth.homes.HomesConfig.DEFAULT.heightBelow(), kr.labyrinth.homes.HomesConfig.DEFAULT.heightAbove()};
        }
    }

    public VillageService service() { return service; }

    int forgetOldEntrance() {
        try {
            return forgetOldEntrance == null ? 0 : forgetOldEntrance.getAsInt();
        } catch (Throwable t) {
            Log.error("[마을] 예전 석문 기록 정리 실패", t);
            return 0;
        }
    }

    int blocksPerTick() { return Math.max(200, plugin().getConfig().getInt("village.blocks_per_tick", 4000)); }

    boolean teleportCommand() { return plugin().getConfig().getBoolean("village.teleport_command", true); }

    boolean blockMobSpawns() { return plugin().getConfig().getBoolean("village.block_mob_spawns", true); }
}
