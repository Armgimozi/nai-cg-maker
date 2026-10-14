package kr.labyrinth.ui;

import kr.labyrinth.Services;
import kr.labyrinth.core.Module;

/**
 * ui+titles 담당 모듈 진입점. 이 파일과 이 패키지는 ui+titles 담당 소유 — 다른 작업자는 수정하지 않는다.
 * <p>
 * enable() 에서 실제 구현을 등록한다: {@code services.setHud / setMenus} (menus/*, 커스텀 폰트 HUD). Menu/Button/MenuListener/Glyphs 프레임워크는 core 소유.
 * 등록 전까지는 Services 의 안전한 기본 구현이 쓰인다. 하위 명령은 {@code services.commands().addSubcommand(...)} 로.
 */
public final class UiModule implements Module {

    private final Services services;

    public UiModule(Services services) { this.services = services; }

    @Override
    public String name() { return "ui"; }

    @Override
    public void enable() {
        // 예: services.setXxx(new XxxServiceImpl(services));
    }
}
