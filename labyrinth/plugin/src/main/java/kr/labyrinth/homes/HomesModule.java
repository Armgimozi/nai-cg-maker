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
 * {@code /labadmin reload} 는 {@link #reload}: 설정을 다시 읽고 (켬↔끔이면 리스너를 붙이거나 뗌) content/housing.yml 을 다시 읽는다.
 * <ol>
 *   <li>config {@code homes:} → {@link HomesConfig}</li>
 *   <li>{@link HomesService} (묶음 B) → {@code services.setHomes}</li>
 *   <li>명령 (한 번만): {@code /labadmin plot} (묶음 B) · {@code /미궁 집} (묶음 C)</li>
 *   <li>규칙 리스너 (묶음 B) 는 늘 붙인다 — {@code homes.enabled: false} 여도 집터가 있으면 주인 있는 집은 지킨다 (잠금·받기는 없음, live 7)</li>
 *   <li>{@code homes.enabled} 일 때만: 놀이 연결 (묶음 C — 메뉴 {@link HomesUi}·회복·표지판)</li>
 * </ol>
 * 잠금·받기·회복은 집 구역이 지어진 뒤에만 움직인다 ({@link HomesService#active()} · {@link HomesService#rulesOn()}).
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
            new HomesCommands(() -> play).register(services.commands()); // 실행할 때마다 지금 켜진 놀이 연결을 본다
            commandsRegistered = true;
        }
        play = new PlayWiring(services, service);
        service.enableRules(services.plugin()); // 꺼져 있어도 집터는 지킴 (리스너가 rulesOn/guardOnly 를 봄)
        if (c.enabled()) play.enable();
        HomesDistrict d = service.district();
        Log.info("[집] " + (c.enabled() ? "켬" : "꺼짐 (homes.enabled: false" + (service.rulesOn() ? " — 집터는 계속 지킴" : "") + ")") + " · 집 구역 " + d.state() + " · 집터 " + d.plots().size()
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
        if (c.enabled() && was) play.reloadCatalog();
        if (c.enabled() && !was) play.enable();
        else if (!c.enabled() && was) play.disable(); // 규칙 리스너는 그대로 (집터는 계속 지킴)
    }
}
