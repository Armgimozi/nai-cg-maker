package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.rooms.GimmickRoom;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.block.Action;

/**
 * 6층 `lights_out`: grid×grid 영혼 등불. 하나를 치면 자신과 상하좌우가 반전. 시작 배치는 정답에서 scramble_moves 수만큼
 * 섞은 상태라 항상 풀린다. 제한 시간 안에 전부 켜면 성공. 방 안은 냉기 피해.
 */
public final class LightsOut extends GimmickRoom {

    private final int n;
    private LightsOutGrid grid;
    private long lastFrost;
    private final Map<UUID, Long> cooldown = new HashMap<>();

    public LightsOut(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        this.n = Math.max(3, Math.min(5, params.integer("grid", 4)));
    }

    @Override protected String title() { return "서리 등불"; }

    @Override
    protected String rules() {
        return "<gray>서리가 등불을 하나씩 꺼뜨렸다\n<gray>등불들은 서로 손을 잡고 있다. 냉기가 몸을 깎는다";
    }

    @Override
    protected List<String> hints() {
        return List.of(
                "등불 하나를 깨우면 이웃들도 함께 뒤척인다.",
                "받침대를 치면 그 등불과 앞·뒤·왼쪽·오른쪽 이웃이 함께 뒤바뀐다. 모든 등불이 켜져야 한다.",
                "받침대를 치면 자신과 상하좌우가 뒤바뀐다. 한쪽 끝 줄부터, 꺼진 등불 바로 다음 줄의 받침대를 쳐서 한 줄씩 밀어 나가라. 마지막 줄만 남으면 첫 줄 하나를 바꾸고 다시 밀어라.");
    }

    @Override
    protected int timeLimit() { return params.integer("time_limit", 120); }

    /** 격자 칸 (i, j) → 타일. 간격 2, 방 중심 정렬. */
    private int tx(int i) { return info.centerX() + (int) Math.round((i - (n - 1) / 2.0) * 2); }

    private int tz(int j) { return info.centerZ() + (int) Math.round((j - (n - 1) / 2.0) * 2); }

    @Override
    public void prepare(BlockList list) {
        for (int j = 0; j < n; j++)
            for (int i = 0; i < n; i++)
                list.add(fs.ox() + tx(i), fs.y0() + 1, fs.oz() + tz(j), Material.CHISELED_QUARTZ_BLOCK.createBlockData());
    }

    @Override
    protected void begin() {
        grid = new LightsOutGrid(n);
        grid.scramble(params.integer("scramble_moves", 6), new java.util.SplittableRandom(rng.nextLong()));
        render();
        lastFrost = System.currentTimeMillis();
    }

    private void render() {
        for (int j = 0; j < n; j++) {
            for (int i = 0; i < n; i++) {
                boolean on = grid.on(i, j);
                fs.setBlock(tx(i), 1, tz(j), on ? Material.SEA_LANTERN : Material.BLUE_ICE);
                org.bukkit.block.data.BlockData lantern = Material.SOUL_LANTERN.createBlockData();
                fs.setBlock(tx(i), 2, tz(j), on ? lantern : Material.AIR.createBlockData());
            }
        }
    }

    @Override
    protected void update(long t) {
        long now = System.currentTimeMillis();
        if (now - lastFrost >= 1000) {
            lastFrost = now;
            for (Player p : alivePlayersInside()) {
                hurt(p, params.dbl("frost_damage", 0.02), "frost_room");
                p.setFreezeTicks(Math.min(p.getMaxFreezeTicks(), p.getFreezeTicks() + 30));
            }
        }
        if (t % 6 == 0) fs.world().spawnParticle(Particle.SNOWFLAKE, center().add(0, 2, 0), 10, 5, 1.5, 5, 0.01);
    }

    @Override
    protected String status() { return "켜진 등불 " + grid.litCount() + "/" + (n * n); }

    @Override
    protected float progress() { return grid == null ? 0 : grid.litCount() / (float) (n * n); }

    @Override
    public boolean onInteract(Player p, Block block, Action action) {
        int bx = block.getX() - fs.ox(), bz = block.getZ() - fs.oz(), dy = block.getY() - fs.y0();
        if (dy < 1 || dy > 2) return false;
        for (int j = 0; j < n; j++) {
            for (int i = 0; i < n; i++) {
                if (tx(i) != bx || tz(j) != bz) continue;
                if (!running || grid == null) return true;
                if (action != Action.LEFT_CLICK_BLOCK && action != Action.RIGHT_CLICK_BLOCK) return true;
                long now = System.currentTimeMillis();
                if (now - cooldown.getOrDefault(p.getUniqueId(), 0L) < 300) return true;
                cooldown.put(p.getUniqueId(), now);
                grid.press(i, j);
                render();
                Location at = fs.tile(bx, bz, 2.2);
                fs.sound(at, Sound.BLOCK_AMETHYST_BLOCK_HIT, 1.0f, grid.on(i, j) ? 1.4f : 0.7f);
                fs.world().spawnParticle(Particle.SOUL_FIRE_FLAME, at, 6, 0.2, 0.2, 0.2, 0.01);
                if (grid.solved()) {
                    for (Player o : alivePlayersInside()) o.setFreezeTicks(0);
                    succeed();
                }
                return true;
            }
        }
        return false;
    }

    @Override
    protected void cleanup() {
        if (grid == null) return;
        for (int j = 0; j < n; j++) {
            for (int i = 0; i < n; i++) {
                fs.setBlock(tx(i), 1, tz(j), state == State.CLEARED && grid.solved() ? Material.SEA_LANTERN : Material.CHISELED_QUARTZ_BLOCK);
                fs.setBlock(tx(i), 2, tz(j), state == State.CLEARED && grid.solved() ? Material.SOUL_LANTERN : Material.AIR);
            }
        }
    }
}
