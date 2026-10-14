package kr.labyrinth.dungeon;

import kr.labyrinth.Services;
import kr.labyrinth.core.Module;
import kr.labyrinth.party.PartyManager;

/**
 * dungeon+party 담당 모듈 진입점. 이 파일과 이 패키지는 dungeon+party 담당 소유 — 다른 작업자는 수정하지 않는다.
 * <p>
 * enable(): 파티(PartyManager) → 공허 월드·인스턴스(DungeonManager) → 오버월드 입구(EntranceService) → 명령.
 */
public final class DungeonModule implements Module {

    private final Services services;
    private PartyManager party;
    private DungeonManager dungeon;
    private EntranceService entrance;

    public DungeonModule(Services services) { this.services = services; }

    @Override
    public String name() { return "dungeon"; }

    @Override
    public void enable() {
        party = new PartyManager(services);
        party.enable();
        services.setParty(party);

        dungeon = new DungeonManager(services);
        dungeon.enable();
        services.setDungeon(dungeon);

        entrance = new EntranceService(services, dungeon);
        entrance.enable();

        new DungeonCommands(services, dungeon, entrance).register();
    }

    @Override
    public void disable() {
        if (entrance != null) entrance.disable();
        if (dungeon != null) dungeon.disable();
        if (party != null) party.disable();
    }

    @Override
    public void reload() {
        if (dungeon != null) dungeon.reload();
    }
}
