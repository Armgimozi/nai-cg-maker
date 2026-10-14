package kr.labyrinth.classes;

import kr.labyrinth.Services;
import kr.labyrinth.core.Module;

/**
 * classes 담당 모듈 진입점. 이 파일과 이 패키지는 classes 담당 소유 — 다른 작업자는 수정하지 않는다.
 * <p>
 * enable() 에서 실제 구현을 등록한다: {@code services.setClasses / setEffects} (직업 스킬 skills/*, 상태이상, 버프 StatContributor).
 * 등록 전까지는 Services 의 안전한 기본 구현이 쓰인다. 하위 명령은 {@code services.commands().addSubcommand(...)} 로.
 */
public final class ClassesModule implements Module {

    private final Services services;

    public ClassesModule(Services services) { this.services = services; }

    @Override
    public String name() { return "classes"; }

    @Override
    public void enable() {
        // 예: services.setXxx(new XxxServiceImpl(services));
    }
}
