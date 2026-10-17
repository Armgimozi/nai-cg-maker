package kr.labyrinth.homes.play;

import kr.labyrinth.homes.HomesService;
import org.bukkit.event.Listener;

/**
 * 집 안 회복·침대 쉬기·들어설 때 글 (0.3.7, plan §8 · 설계 §8) — 뼈대: 처리기 없음. 소유: 묶음 C.
 * <p>
 * 채울 것: 10틱 작업 (주 월드 온라인만) — 내 집·초대받은 집 높이 창 안 + calm_seconds 동안 피해 없음 + PvP 전투 아님 → 1초마다
 * 최대 HP·MP 의 home_regen 비율 ({@code StatService.heal} + {@code DamageService.healAmount REGEN} · {@code ClassService.restoreMana}) ·
 * 내 침대 우클릭 bed_rest.seconds (움직이거나 맞으면 끊김) → 가득 (cooldown_seconds) · 들어설 때 액션바 "◆ 3번지 · 하린의 집".
 * {@code PlayerMoveEvent} 는 쓰지 않는다.
 */
public final class HomeCareListener implements Listener {

    private final HomesService service;

    public HomeCareListener(HomesService service) { this.service = service; }

    HomesService service() { return service; }
}
