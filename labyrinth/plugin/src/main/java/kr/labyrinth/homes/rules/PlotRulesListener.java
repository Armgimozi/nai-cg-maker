package kr.labyrinth.homes.rules;

import kr.labyrinth.homes.HomesService;
import org.bukkit.event.Listener;

/**
 * 집터 안 권한 (0.3.7, plan §9 · review R4) — 뼈대: 처리기 없음. 소유: 묶음 B.
 * <p>
 * 채울 것: 부수기·놓기 (deny_place · 두 칸 블록 위 칸 같은 창) · 상자류 열기 ({@code BlockState instanceof InventoryHolder}) ·
 * 남의 집 블록 우클릭·좌클릭 기본 막음 + 허용 목록 (문·다락문·울타리 문·작업대류·종) · 엔티티 (때리기·끈·털 깎기·양동이·이름표·염색·타기·
 * 말/상자 보트/상자 수레 열기·낚싯대 끌기) · {@code PlayerArmorStandManipulateEvent} (따로) · 걸개 (받침·걸개 칸 둘 다) · 부싯돌 (모닥불·초만) ·
 * 표지판 글 · deny_use (용암 양동이·화염구, R21) · 틱 부품·엔티티 한도 (R15).
 * 처리기마다 맨 앞에서 {@code if (!service.active()) return;} (convert 집터만 있는 서버는 묶음 B 가 active 를 넓힌다).
 */
public final class PlotRulesListener implements Listener {

    private final HomesService service;

    public PlotRulesListener(HomesService service) { this.service = service; }

    HomesService service() { return service; }
}
