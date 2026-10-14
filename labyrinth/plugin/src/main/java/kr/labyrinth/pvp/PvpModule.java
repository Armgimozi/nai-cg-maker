package kr.labyrinth.pvp;

import kr.labyrinth.Services;
import kr.labyrinth.core.Module;

/**
 * pvp 담당 모듈 진입점. 이 파일과 이 패키지는 pvp 담당 소유 — 다른 작업자는 수정하지 않는다.
 * <p>
 * enable() 에서 실제 구현을 등록한다: {@code services.setTargets} (ArenaService, MatchService, PvpRules, RatingService).
 * 등록 전까지는 Services 의 안전한 기본 구현이 쓰인다. 하위 명령은 {@code services.commands().addSubcommand(...)} 로.
 */
public final class PvpModule implements Module {

    private final Services services;

    public PvpModule(Services services) { this.services = services; }

    @Override
    public String name() { return "pvp"; }

    @Override
    public void enable() {
        // 예: services.setXxx(new XxxServiceImpl(services));
    }
}
