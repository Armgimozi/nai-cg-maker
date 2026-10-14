package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.rooms.GimmickRoom;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.block.data.type.Campfire;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.block.Action;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

/**
 * 2층 `torch_relay`: 어두운 방, 화로 N개는 burn_time 초 뒤 꺼짐 → 우클릭으로 다시 붙임. (N−1)개 이상 켜진 시간이
 * hold_seconds 쌓이면 성공. 덜 켜졌을 땐 어둠 효과. spawn_interval 초마다 어둠에서 거미.
 */
public final class TorchRelay extends GimmickRoom {

    private final List<int[]> braziers = new ArrayList<>();
    private double[] burn;
    private final List<TextDisplay> labels = new ArrayList<>();
    private double held;
    private long lastUpdate;
    private long nextSpawn;

    public TorchRelay(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        int n = Math.max(2, Math.min(6, params.integer("braziers", 4)));
        int[][] spots = {{-6, -6}, {6, -6}, {6, 6}, {-6, 6}, {0, -7}, {0, 7}};
        for (int i = 0; i < n; i++) braziers.add(new int[] {rx(spots[i][0]), rz(spots[i][1])});
    }

    @Override protected String title() { return "꺼져 가는 화로"; }

    @Override
    protected String rules() {
        return "<gray>어둠이 불씨를 하나씩 삼키려 한다\n<gray>불이 버티는 동안만 어둠이 물러선다";
    }

    @Override
    protected List<String> hints() {
        int need = Math.max(1, braziers.size() - 1);
        return List.of(
                "꺼진 화로도 손길이 닿으면 다시 숨을 쉰다.",
                "모든 불을 지킬 필요는 없다. 하나쯤 꺼져도 어둠은 버틴다 — 둘이 꺼지면 이야기가 다르다.",
                "꺼진 화로를 우클릭하면 다시 붙는다. 화로 " + need + "개 이상이 함께 타는 시간을 " + params.integer("hold_seconds", 40)
                        + "초 채우면 성공 — 파티는 화로를 나눠 맡아라.");
    }

    @Override public boolean wantsLights() { return false; }

    @Override
    protected int timeLimit() { return params.integer("hold_seconds", 40) * 3; }

    @Override
    public void prepare(BlockList list) {
        for (int[] b : braziers) {
            list.add(fs.ox() + b[0], fs.y0() + 1, fs.oz() + b[1], Material.POLISHED_BLACKSTONE_BRICKS.createBlockData());
            list.add(fs.ox() + b[0], fs.y0() + 2, fs.oz() + b[1], fire(false));
        }
    }

    private org.bukkit.block.data.BlockData fire(boolean lit) {
        Campfire c = (Campfire) Material.CAMPFIRE.createBlockData();
        c.setLit(lit);
        c.setSignalFire(false);
        return c;
    }

    @Override
    protected void begin() {
        double burnTime = params.dbl("burn_time", 18);
        burn = new double[braziers.size()];
        held = 0;
        for (int i = 0; i < braziers.size(); i++) {
            burn[i] = Math.max(4, burnTime - i * 3.5);
            int[] b = braziers.get(i);
            fs.setBlock(b[0], 2, b[1], fire(true));
            labels.add(fs.text(fs.tile(b[0], b[1], 3.4), ""));
        }
        lastUpdate = System.currentTimeMillis();
        nextSpawn = lastUpdate + Math.round(params.dbl("spawn_interval", 6) * 1000);
    }

    private int litCount() {
        int k = 0;
        for (double v : burn) if (v > 0) k++;
        return k;
    }

    @Override
    protected void update(long t) {
        long now = System.currentTimeMillis();
        double dt = (now - lastUpdate) / 1000.0;
        lastUpdate = now;
        for (int i = 0; i < burn.length; i++) {
            if (burn[i] <= 0) continue;
            burn[i] -= dt;
            if (burn[i] <= 0) {
                int[] b = braziers.get(i);
                fs.setBlock(b[0], 2, b[1], fire(false));
                fs.sound(fs.tile(b[0], b[1], 2), Sound.BLOCK_FIRE_EXTINGUISH, 0.8f, 0.8f);
            }
        }
        int need = Math.max(1, braziers.size() - 1);
        boolean enough = litCount() >= need;
        if (enough) held += dt;
        if (t % 10 == 0) {
            for (int i = 0; i < labels.size(); i++) {
                double v = burn[i];
                labels.get(i).text(kr.labyrinth.core.Text.mm(v > 0 ? (v < 5 ? "<red>" : "<gold>") + "🔥 " + (int) Math.ceil(v) + "초" : "<dark_gray>꺼짐"));
            }
            if (!enough) {
                for (Player p : alivePlayersInside()) p.addPotionEffect(new PotionEffect(PotionEffectType.DARKNESS, 40, 0, true, false, false));
            }
        }
        if (now >= nextSpawn) {
            nextSpawn = now + Math.round(params.dbl("spawn_interval", 6) * 1000);
            if (aliveMobs() < 3 + partySize()) {
                String id = params.str("darkness_spawn", null);
                if (id == null || fs.services().content().mob(id) == null) id = fs.randomFloorMob(rng);
                spawn(id, randomSpot(3));
            }
        }
        if (held >= params.dbl("hold_seconds", 40)) succeed();
    }

    @Override
    protected String status() {
        return "화로 " + litCount() + "/" + braziers.size() + " · " + (int) held + "/" + params.integer("hold_seconds", 40) + "초";
    }

    @Override
    protected float progress() { return (float) (held / Math.max(1, params.dbl("hold_seconds", 40))); }

    @Override
    public boolean onInteract(Player p, Block block, Action action) {
        if (block.getType() != Material.CAMPFIRE) return false;
        int tx = block.getX() - fs.ox(), tz = block.getZ() - fs.oz();
        for (int i = 0; i < braziers.size(); i++) {
            int[] b = braziers.get(i);
            if (b[0] != tx || b[1] != tz) continue;
            if (!running || action != Action.RIGHT_CLICK_BLOCK) return true;
            burn[i] = params.dbl("burn_time", 18);
            fs.setBlock(b[0], 2, b[1], fire(true));
            Location at = fs.tile(b[0], b[1], 2.5);
            fs.sound(at, Sound.ITEM_FIRECHARGE_USE, 0.8f, 1.2f);
            fs.world().spawnParticle(Particle.FLAME, at, 14, 0.25, 0.3, 0.25, 0.02);
            return true;
        }
        return false;
    }

    @Override
    protected void cleanup() {
        for (TextDisplay d : labels) fs.untrack(d);
        labels.clear();
        for (int i = 0; i < braziers.size(); i++) {
            int[] b = braziers.get(i);
            fs.setBlock(b[0], 2, b[1], fire(state == State.CLEARED));
        }
        for (Player p : fs.allPlayers()) p.removePotionEffect(PotionEffectType.DARKNESS);
    }
}
