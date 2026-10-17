package kr.labyrinth.homes;

import kr.labyrinth.Services;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;
import kr.labyrinth.homes.admin.HomesAdminCommands;
import kr.labyrinth.homes.play.HomesCommands;
import kr.labyrinth.homes.play.PlayWiring;

/**
 * 집 구역 모듈 (0.3.7 — 마을 남쪽 "등불 골목" 10채 + 주 월드 지형 잠금). 모듈 차례: Village → Mine → Homes (마을 모듈이 먼저 구역 기록을 읽어
 * {@link HomesDistrict#publish} 로 남겨 둔다). 소유: 묶음 C (묶음 B 는 {@link HomesService} 안, 묶음 C 는 {@link PlayWiring} 안을 채운다).
 * <ol>
 *   <li>config {@code homes:} → {@link HomesConfig}</li>
 *   <li>{@link HomesService} (묶음 B) → {@code services.setHomes}</li>
 *   <li>명령 (한 번만): {@code /labadmin plot} (묶음 B) · {@code /미궁 집} (묶음 C)</li>
 *   <li>{@code homes.enabled} 일 때만: 규칙 리스너 (묶음 B) · 놀이 연결 (묶음 C — 메뉴 {@link HomesUi}·회복·표지판)</li>
 * </ol>
 * 잠금·받기·회복은 집 구역이 지어진 뒤에만 움직인다 ({@link HomesService#active()}).
 */
public final class HomesModule implements Module {

    private final Services services;
    private HomesService service;
    private PlayWiring play;
    private boolean commandsRegistered;

    public HomesModule(Services services) { this.services = services; }

    @Override
    public String name() { return "homes"; }

    @Override
    public void enable() {
        HomesConfig c = HomesConfig.fromRoot(services.plugin().getConfig());
        service = new HomesService(services, c);
        services.setHomes(service);
        if (!commandsRegistered) {
            new HomesAdminCommands(service).register(services.commands());
            new HomesCommands(service).register(services.commands());
            commandsRegistered = true;
        }
        play = new PlayWiring(services, service);
        if (c.enabled()) {
            service.enableRules(services.plugin());
            play.enable();
        }
        HomesDistrict d = service.district();
        Log.info("[집] " + (c.enabled() ? "켬" : "꺼짐 (homes.enabled: false)") + " · 집 구역 " + d.state() + " · 집터 " + d.plots().size()
                + " · 지형 잠금 설정 " + (c.terrainLock() ? "켬" : "끔"));
    }

    @Override
    public void disable() {
        if (play != null) play.disable();
        if (service != null) service.disableRules();
        services.setHomes(new NoopHomesApi());
    }

    @Override
    public void reload() {
        if (service == null) return;
        HomesConfig c = HomesConfig.fromRoot(services.plugin().getConfig());
        boolean was = service.config().enabled();
        service.reconfigure(c);
        if (c.enabled() && !was) {
            service.enableRules(services.plugin());
            play.enable();
        } else if (!c.enabled() && was) {
            play.disable();
            service.disableRules();
        }
    }
}
