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
    }

    public Services services() { return services; }

    public LabyrinthPlugin plugin() { return services.plugin(); }

    public VillageLibrary library() { return library; }

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
