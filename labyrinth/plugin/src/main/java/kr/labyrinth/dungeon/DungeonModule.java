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
        registerSelfTest();
    }

    /** /labadmin selftest [층 수] — 플레이어 없이 층 생성·몹/보스·피해·정리 경로를 돌려 보는 자가 진단 (콘솔 가능). */
    private void registerSelfTest() {
        var root = io.papermc.paper.command.brigadier.Commands.literal("selftest");
        root.executes(c -> {
            kr.labyrinth.command.CommandService.safeRun(c, () -> SelfTest.start(services, dungeon, c.getSource().getSender(), 1));
            return com.mojang.brigadier.Command.SINGLE_SUCCESS;
        });
        root.then(io.papermc.paper.command.brigadier.Commands.argument("floors",
                com.mojang.brigadier.arguments.IntegerArgumentType.integer(1, 10)).executes(c -> {
            int n = com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(c, "floors");
            kr.labyrinth.command.CommandService.safeRun(c, () -> SelfTest.start(services, dungeon, c.getSource().getSender(), n));
            return com.mojang.brigadier.Command.SINGLE_SUCCESS;
        }));
        services.commands().addSubcommand("labadmin", root);
    }

    /** 예전 석문 기록(entrance.yml)을 복원 없이 버림 — 마을 월드 적용 때 (village 모듈이 호출). @return 버린 기록 수 */
    public int forgetSavedEntrance() {
        return entrance == null ? 0 : entrance.forgetSaved();
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
