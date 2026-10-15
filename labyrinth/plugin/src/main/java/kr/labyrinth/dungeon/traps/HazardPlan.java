package kr.labyrinth.dungeon.traps;

import java.util.List;
import kr.labyrinth.content.Params;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.gen.RoomType;
import kr.labyrinth.dungeon.treasure.ChestSettings;
import kr.labyrinth.dungeon.treasure.TreasurePlan;
import kr.labyrinth.dungeon.treasure.TreasurePlanner;

/**
 * 한 층의 함정 + 미로 보물 배치 (순수). 순서: 보물(상자·금고·열쇠) → 함정(상자 앞에 많이) → 함정 뒤 상자 금으로.
 * FloorState·단위 테스트·MazeRenderDump 가 같은 함수를 쓴다.
 */
public record HazardPlan(TreasurePlan treasure, List<TrapSpot> traps, TrapSettings trapSettings, ChestSettings chestSettings) {

    public static HazardPlan plan(FloorLayout l, Params traps, Params chests, long seed) {
        TrapSettings ts = TrapSettings.of(traps);
        ChestSettings cs = ChestSettings.of(chests);
        boolean elite = false;
        for (FloorLayout.RoomInfo r : l.rooms()) if (r.type() == RoomType.ELITE) elite = true;
        TreasurePlan tp = TreasurePlanner.plan(l, cs, seed, elite);
        List<TrapSpot> spots = TrapPlanner.plan(l, ts, tp, seed);
        tp = TreasurePlanner.upgradeBehindTraps(tp, TrapPlanner.tiles(spots), cs, seed);
        return new HazardPlan(tp, List.copyOf(spots), ts, cs);
    }
}
