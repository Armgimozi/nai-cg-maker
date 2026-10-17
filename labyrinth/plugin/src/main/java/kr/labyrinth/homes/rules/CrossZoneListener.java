package kr.labyrinth.homes.rules;

import kr.labyrinth.homes.HomesService;
import org.bukkit.event.Listener;

/**
 * 경계 넘는 것 (0.3.7, plan §9 "경계 넘는 것") — 뼈대: 처리기 없음. 소유: 묶음 B.
 * <p>
 * 채울 것: 물·용암 흐름 · 피스톤 · 깔때기·공급기 옮김·줍기 · 나무·큰 버섯 (R17 글) · 뼛가루 · 퍼짐 · 자람 · 불 타기·번짐 · 폭발 blockList ·
 * 엔티티 블록 바꿈 · 눈 골렘 자국 · 스펀지 · 발사기 ({@code BlockDispenseEvent}) · {@code TNTPrimeEvent} · 리스폰 정박기 ·
 * 구리 골렘 ({@code ItemTransportingEntityValidateTargetEvent}) · 차원문 ({@code PortalCreateEvent}).
 * 잦은 이벤트는 주 월드가 아니거나 두 칸 청크 모두 집터가 없으면 바로 끝낸다.
 */
public final class CrossZoneListener implements Listener {

    private final HomesService service;

    public CrossZoneListener(HomesService service) { this.service = service; }

    HomesService service() { return service; }
}
