package kr.labyrinth.dungeon;

import java.util.BitSet;
import kr.labyrinth.dungeon.gen.FloorLayout;
import org.bukkit.Location;

/**
 * 층 탐험 기록 (파티 공유). 살아 있는 파티원이 지나간 미로 셀, 찾은 보스 문(보스 연결 셀이나 보스 복도에 닿음), 연 비밀 통로.
 * 탐험 지도({@link ExplorationMap})가 이걸로 안개를 걷는다 — 시작방에서 보스 방향은 알려 주지 않는다.
 */
public final class Exploration {

    private final FloorState fs;
    private final BitSet visited;
    private final BitSet secrets = new BitSet();
    private boolean bossDoorFound;

    Exploration(FloorState fs) {
        this.fs = fs;
        this.visited = new BitSet(fs.layout().plan().cellCount());
        visited.set(fs.layout().plan().start());
    }

    /** 살아 있는 파티원 위치 (2틱마다). */
    void visit(Location l) {
        FloorLayout layout = fs.layout();
        int tx = fs.tileX(l), tz = fs.tileZ(l);
        int cell = layout.cellAt(tx, tz);
        if (cell >= 0 && layout.plan().used(cell)) {
            visited.set(cell);
            if (cell == layout.plan().bossAttach()) bossDoorFound = true;
        } else if (layout.beyondGrid(tz)) {
            bossDoorFound = true;
        }
    }

    public boolean visited(int cell) { return cell >= 0 && visited.get(cell); }

    public int visitedCount() { return visited.cardinality(); }

    public boolean bossDoorFound() { return bossDoorFound; }

    void markSecret(int index) { secrets.set(index); }

    public boolean secretFound(int index) { return secrets.get(index); }

    public int secretsFound() { return secrets.cardinality(); }

    /** 자가 진단용: 전부 지나간 것으로. */
    void revealAll() {
        for (int c = 0; c < fs.layout().plan().cellCount(); c++) if (fs.layout().plan().used(c)) visited.set(c);
        bossDoorFound = true;
    }
}
