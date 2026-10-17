package kr.labyrinth.homes.rules;

import kr.labyrinth.homes.HomesService;
import org.bukkit.event.Listener;

/**
 * 주 월드 지형 잠금 (0.3.7, plan §9·§10) — 뼈대: 처리기 없음. 소유: 묶음 B.
 * <p>
 * 채울 것 (우선순위 LOW): 주 월드 아님 → 끝 · 집터 → PlotRules · {@code VillageService.isProtected} → 손대지 않음 (마을 HIGH 가 막고 글) ·
 * 잠금 켜짐 → 막음 (부수기·놓기·양동이·걸개·엔티티 놓기 {@code EntityPlaceEvent}·{@code VehicleDestroyEvent}·손 도구
 * {@code VillageService.changesBlocks}·불·뼛가루·{@code SignChangeEvent}·끈·엔티티 양동이·밭 밟기). 이사 기간: 집터·보호 상자 밖 UNNATURAL 만 부수기.
 * 글: 풀·꽃은 글 없이, 나머지 2초에 한 번 "집터 밖은 부수거나 지을 수 없습니다 — /미궁 집". 크리에이티브 관리자는 막지 않음.
 */
public final class TerrainLockListener implements Listener {

    private final HomesService service;

    public TerrainLockListener(HomesService service) { this.service = service; }

    HomesService service() { return service; }
}
