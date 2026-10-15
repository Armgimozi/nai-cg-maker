package kr.labyrinth.dungeon;

import java.util.ArrayList;
import java.util.List;
import java.util.function.BiConsumer;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.gen.FloorLayout;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Player;

/**
 * 비밀 통로 런타임 (GDD §5.4). 막다른 길 끝의 금 간 벽({@link FloorLayout#SECRET})을 우클릭하거나 때리거나 투사체로 맞히면 무너져
 * 숨은 작은 방이 열린다 — 벽 블록은 공기가 되고({@link FloorState#setBlock} 로 기록 → 층 정리 때 함께 사라짐), 파티 전원에게 알림.
 * 열리지 않은 벽 근처에 파티원이 있으면 가끔 부스러기 먼지가 떨어져 단서가 된다.
 * <p>
 * 비밀방 안 보상(금 상자 등)은 다른 담당이 {@link FloorLayout#secretRooms()} 위치에 둔다 — 열릴 때 무언가 하려면 {@link #onOpen}.
 */
public final class SecretPassages {

    private final FloorState fs;
    private final List<FloorLayout.SecretRoom> list;
    private final boolean[] opened;
    private final List<BiConsumer<Integer, Player>> listeners = new ArrayList<>();
    private BlockData wallData;

    SecretPassages(FloorState fs) {
        this.fs = fs;
        this.list = fs.layout().secretRooms();
        this.opened = new boolean[list.size()];
    }

    public int count() { return list.size(); }

    public boolean isOpen(int index) { return index >= 0 && index < opened.length && opened[index]; }

    public int openedCount() {
        int k = 0;
        for (boolean b : opened) if (b) k++;
        return k;
    }

    /** 비밀방이 열릴 때 (비밀방 번호, 연 사람 — 자가 진단이면 null). */
    public void onOpen(BiConsumer<Integer, Player> listener) { listeners.add(listener); }

    private BlockData wallData() {
        if (wallData == null) {
            List<String> sec = fs.def().palette("secret");
            Material m = sec.isEmpty() ? null : Material.matchMaterial(sec.get(0));
            wallData = (m == null || !m.isBlock() ? Material.CRACKED_STONE_BRICKS : m).createBlockData();
        }
        return wallData;
    }

    /** 이 블록이 아직 안 열린 금 간 벽이면 연다. @return 금 간 벽이었으면 true (이벤트 취소) */
    boolean tryOpen(Player p, Block b) {
        if (list.isEmpty() || !fs.onThisFloor(b.getLocation())) return false;
        int tx = b.getX() - fs.ox(), tz = b.getZ() - fs.oz(), dy = b.getY() - fs.y0();
        int idx = fs.layout().secretWallAt(tx, tz);
        if (idx < 0 || dy < 1 || dy > fs.layout().height(tx, tz)) return false;
        if (opened[idx]) return false;
        open(idx, p);
        return true;
    }

    /** 비밀방 index 의 금 간 벽을 무너뜨린다. */
    public void open(int index, Player by) {
        if (index < 0 || index >= opened.length || opened[index]) return;
        opened[index] = true;
        FloorLayout.SecretRoom s = list.get(index);
        BlockData air = Material.AIR.createBlockData();
        Location mid = null;
        for (int w : s.wall()) {
            int x = FloorLayout.unpackX(w), z = FloorLayout.unpackZ(w);
            int h = fs.layout().height(x, z);
            for (int y = 1; y <= h; y++) fs.setBlock(x, y, z, air);
            Location at = fs.tile(x, z, 1.5);
            fs.world().spawnParticle(Particle.BLOCK, at, 30, 0.4, 0.8, 0.4, 0.1, wallData());
            if (mid == null || w == s.wall()[s.wall().length / 2]) mid = at;
        }
        if (mid != null) {
            fs.sound(mid, Sound.BLOCK_DEEPSLATE_BRICKS_BREAK, 1.0f, 0.7f);
            fs.sound(mid, Sound.ENTITY_ZOMBIE_BREAK_WOODEN_DOOR, 0.5f, 0.6f);
            fs.world().spawnParticle(Particle.CLOUD, mid, 12, 0.6, 0.6, 0.6, 0.02);
        }
        fs.exploration().markSecret(index);
        String who = by == null ? "누군가가" : Text.escape(by.getName()) + " 님이";
        fs.broadcast("<gold>숨겨진 통로!</gold> <gray>" + who + " 금 간 벽을 무너뜨렸습니다. 벽 너머에 작은 방이 있습니다.");
        for (BiConsumer<Integer, Player> l : listeners) {
            try {
                l.accept(index, by);
            } catch (Throwable t) {
                Log.error("비밀 통로 열림 처리 오류", t);
            }
        }
    }

    /** 2틱마다 — 40틱에 한 번, 가까운 금 간 벽에서 먼지가 떨어진다. */
    void tick(long t) {
        if (t % 40 != 0 || list.isEmpty()) return;
        List<Player> alive = fs.alivePlayers();
        if (alive.isEmpty()) return;
        for (FloorLayout.SecretRoom s : list) {
            if (opened[s.index()]) continue;
            int w = s.wall()[s.wall().length / 2];
            Location at = fs.tile(FloorLayout.unpackX(w), FloorLayout.unpackZ(w), 2.6);
            boolean near = false;
            for (Player p : alive) if (p.getLocation().distanceSquared(at) < 12 * 12) near = true;
            if (!near) continue;
            fs.world().spawnParticle(Particle.FALLING_DUST, at, 3, 0.9, 0.9, 0.9, 0.0, wallData());
        }
    }
}
