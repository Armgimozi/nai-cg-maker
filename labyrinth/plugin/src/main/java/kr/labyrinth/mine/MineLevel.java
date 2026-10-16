package kr.labyrinth.mine;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.MineDef;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.data.BlockData;

/**
 * 광산 층 하나 (실행 중): mine.yml 정의 + jar 청사진 + 블록 상태 풀이 + 광맥 목록.
 * 청사진 글자 {@code @vein:<광석>}·{@code @gem:<보석>} 은 여기서 mine.yml 블록으로 풀린다.
 */
final class MineLevel {

    /** 광맥 또는 보석 노드 하나. key = "L<n>:v<i>" / "L<n>:g<i>". */
    record Vein(MineLevel level, String key, MineBlueprint.Node at, MineDef.Node node, boolean gem, BlockData full) {
        int x() { return at.x(); }
        int y() { return at.y(); }
        int z() { return at.z(); }
    }

    final int n;
    final MineDef.Level def;
    final MineBlueprint bp;
    final BlockData depleted;
    /** 팔레트 글자 → 블록 상태 (공기 포함). 풀 수 없는 글자는 null (자가 진단 mismatched). */
    final Map<Integer, BlockData> data = new HashMap<>();
    final List<Vein> veins = new ArrayList<>();
    final List<Vein> gems = new ArrayList<>();
    final List<String> problems = new ArrayList<>();
    /** 블록 설정까지 넣은 층 지문 (labyrinth-mine.yml). */
    final String hash;

    MineLevel(MineDef mine, MineDef.Level def, MineBlueprint bp) {
        this.n = def.n();
        this.def = def;
        this.bp = bp;
        this.depleted = parse(def.depletedBlock(), "빈 광맥 블록");
        data.put(MineBlueprint.AIR, Bukkit.createBlockData(org.bukkit.Material.AIR));
        StringBuilder sig = new StringBuilder(bp.sha1).append('|').append(def.depletedBlock()).append('|').append(def.biome())
                .append('|').append(def.biomeY());
        for (Map.Entry<Integer, String> e : bp.palette().entrySet()) {
            String s = e.getValue();
            String block = s;
            if (s.startsWith(MineBlueprint.VEIN) || s.startsWith(MineBlueprint.GEM)) {
                MineDef.Node node = mine.node(s.substring(s.indexOf(':') + 1));
                if (node == null) {
                    problems.add("청사진의 " + s + " 가 mine.yml 에 없음");
                    continue;
                }
                block = node.block();
                sig.append('|').append(s).append('=').append(block);
            }
            BlockData bd = parse(block, s);
            if (bd != null) data.put(e.getKey(), bd);
        }
        this.hash = MineBlueprint.sha1(sig.toString()).substring(0, 16);
        for (MineBlueprint.Node v : bp.veins()) {
            MineDef.Node node = mine.ores().get(v.id());
            BlockData bd = node == null ? null : parse(node.block(), v.id());
            if (node != null && bd != null) veins.add(new Vein(this, VeinState.veinKey(n, v.index()), v, node, false, bd));
        }
        for (MineBlueprint.Node g : bp.gems()) {
            MineDef.Node node = mine.gems().get(g.id());
            BlockData bd = node == null ? null : parse(node.block(), g.id());
            if (node != null && bd != null) gems.add(new Vein(this, VeinState.gemKey(n, g.index()), g, node, true, bd));
        }
    }

    private BlockData parse(String s, String what) {
        try {
            return Bukkit.createBlockData(s);
        } catch (Throwable t) {
            problems.add(what + " 블록 상태를 읽지 못함: " + s);
            return null;
        }
    }

    /** 청사진 칸의 블록 상태 (KEEP = 공기로 치움). */
    BlockData expected(int cp) {
        if (cp == MineBlueprint.KEEP) return data.get(MineBlueprint.AIR);
        return data.get(cp);
    }

    Location landing(World w) {
        MineBlueprint.Marker m = bp.marker("landing");
        if (m == null) return new Location(w, 0.5, def.floorY() + 1, 3.5);
        return new Location(w, m.pos()[0], m.pos()[1], m.pos()[2], m.yaw(), 0f);
    }

    /** y 가 이 층 상자 [바닥 − 4, 바닥 + 15] 안인가. */
    boolean containsY(double y) {
        List<Integer> b = def.box();
        if (b.size() == 6) return y >= b.get(1) && y < b.get(4) + 1;
        return y >= def.floorY() - 4 && y < def.floorY() + 16;
    }

    int boxBottom() {
        List<Integer> b = def.box();
        return b.size() == 6 ? b.get(1) : def.floorY() - 4;
    }

    String coloredName() { return "<" + def.titleColor() + ">" + kr.labyrinth.core.Text.escape(def.name()) + "</" + def.titleColor() + ">"; }
}
