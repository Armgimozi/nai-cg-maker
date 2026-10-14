package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.rooms.GimmickRoom;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.FaceAttachable;
import org.bukkit.block.data.type.Switch;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.block.Action;
import org.bukkit.util.Transformation;
import org.joml.AxisAngle4f;
import org.joml.Vector3f;

/**
 * 4층 `valve_flow`: 밸브 N개(각 states 단계). 밸브 옆 수로의 거품 묶음 수 = 정답 단계. 모두 맞추면 수문 개방.
 * flood_seconds 동안 수면이 차오르고, 수면 아래에 잠긴 사람은 초당 flood_damage 피해. 시간이 다 되면 실패.
 */
public final class ValveFlow extends GimmickRoom {

    private final List<int[]> valves = new ArrayList<>();
    private int[] answer;
    private int[] value;
    private final List<TextDisplay> labels = new ArrayList<>();
    private BlockDisplay water;
    private int states;
    private long nextHint;
    private long lastDamage;

    public ValveFlow(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        int n = Math.max(1, Math.min(4, params.integer("valves", 3)));
        int[][] spots = {{-6, -5}, {6, -5}, {-6, 5}, {6, 5}};
        for (int i = 0; i < n; i++) valves.add(new int[] {rx(spots[i][0]), rz(spots[i][1])});
    }

    @Override protected String title() { return "수문의 밸브"; }

    @Override
    protected String rules() {
        return "<gray>물이 차오른다. 수로가 거품으로 무언가를 속삭인다\n<gray>밸브마다 제 목소리가 있다";
    }

    @Override
    protected List<String> hints() {
        return List.of(
                "수로를 가만히 들여다보라. 물은 숫자를 셀 줄 안다.",
                "밸브 옆 수로에서 거품이 몇 번 터지는지 세어 보라. 밸브의 눈금도 그만큼이다.",
                "밸브 옆 수로의 거품 묶음 수 = 그 밸브의 정답 단계 (●가 왼쪽에서 그 번째 칸). 밸브를 우클릭해 단계를 돌려 모두 맞춰라 — 물이 다 차기 전에.");
    }

    @Override
    protected int timeLimit() { return params.integer("flood_seconds", 60); }

    @Override
    public void prepare(BlockList list) {
        for (int[] v : valves) {
            list.add(fs.ox() + v[0], fs.y0() + 1, fs.oz() + v[1], Material.WAXED_OXIDIZED_COPPER.createBlockData());
            list.add(fs.ox() + v[0], fs.y0() + 2, fs.oz() + v[1], lever(false));
            // 수로 (바닥 높이의 물 + 받침)
            int bx = v[0] + (v[0] < info.centerX() ? 1 : -1);
            list.add(fs.ox() + bx, fs.y0() - 1, fs.oz() + v[1], Material.DARK_PRISMARINE.createBlockData());
            list.add(fs.ox() + bx, fs.y0(), fs.oz() + v[1], Material.WATER.createBlockData());
        }
    }

    private org.bukkit.block.data.BlockData lever(boolean on) {
        Switch sw = (Switch) Material.LEVER.createBlockData();
        sw.setAttachedFace(FaceAttachable.AttachedFace.FLOOR);
        sw.setFacing(BlockFace.SOUTH);
        sw.setPowered(on);
        return sw;
    }

    @Override
    protected void begin() {
        states = Math.max(2, Math.min(6, params.integer("states", 4)));
        answer = new int[valves.size()];
        value = new int[valves.size()];
        for (int i = 0; i < valves.size(); i++) {
            answer[i] = rng.nextInt(states);
            do { value[i] = rng.nextInt(states); } while (value[i] == answer[i]);
            int[] v = valves.get(i);
            labels.add(fs.text(fs.tile(v[0], v[1], 3.2), ""));
        }
        refresh();
        Location corner = fs.tile(info.minX(), info.minZ(), 1.05).add(-0.5, 0, -0.5);
        water = fs.track(fs.world().spawn(corner, BlockDisplay.class, d -> {
            d.setBlock(Material.LIGHT_BLUE_STAINED_GLASS.createBlockData());
            d.setTransformation(new Transformation(new Vector3f(0, 0, 0), new AxisAngle4f(),
                    new Vector3f(info.width(), 0.06f, info.depth()), new AxisAngle4f()));
            d.setInterpolationDuration(20);
            d.setBrightness(new org.bukkit.entity.Display.Brightness(12, 12));
        }));
        nextHint = System.currentTimeMillis() + 1500;
        lastDamage = System.currentTimeMillis();
    }

    private double surfaceY() {
        double frac = Math.min(1, elapsed() / Math.max(1, timeLimit()));
        return fs.y0() + 1.05 + frac * 2.4;
    }

    private void refresh() {
        for (int i = 0; i < labels.size(); i++) {
            StringBuilder pips = new StringBuilder();
            for (int s = 0; s < states; s++) pips.append(s == value[i] ? "<aqua>●" : "<dark_gray>○");
            labels.get(i).text(Text.mm("<aqua>밸브 " + (char) ('Ⅰ' + i) + "</aqua>\n" + pips));
        }
    }

    @Override
    protected void update(long t) {
        long now = System.currentTimeMillis();
        if (water != null && t % 20 == 0) {
            double rise = surfaceY() - (fs.y0() + 1.05);
            water.setInterpolationDelay(0);
            water.setTransformation(new Transformation(new Vector3f(0, (float) rise, 0), new AxisAngle4f(),
                    new Vector3f(info.width(), 0.06f, info.depth()), new AxisAngle4f()));
        }
        if (now >= nextHint) {
            nextHint = now + 4000;
            for (int i = 0; i < valves.size(); i++) {
                int[] v = valves.get(i);
                int bx = v[0] + (v[0] < info.centerX() ? 1 : -1);
                Location at = fs.tile(bx, v[1], 1.0);
                int puffs = answer[i] + 1;
                for (int k = 0; k < puffs; k++) {
                    Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> {
                        if (!running) return;
                        fs.world().spawnParticle(Particle.BUBBLE_POP, at, 10, 0.15, 0.1, 0.15, 0.02);
                        fs.world().spawnParticle(Particle.BUBBLE_COLUMN_UP, at, 6, 0.1, 0.0, 0.1, 0.05);
                        fs.sound(at, Sound.BLOCK_BUBBLE_COLUMN_BUBBLE_POP, 0.7f, 1.2f);
                    }, k * 9L);
                }
            }
        }
        if (now - lastDamage >= 1000) {
            lastDamage = now;
            double surf = surfaceY();
            for (Player p : alivePlayersInside()) {
                if (p.getLocation().getY() + 0.2 < surf) {
                    hurt(p, params.dbl("flood_damage", 0.03), "flood");
                    fs.services().hud().actionBar(p, Text.mm("<aqua>물에 잠겨 숨이 막힌다!</aqua>"), 25);
                }
            }
        }
    }

    @Override
    protected String status() {
        int ok = 0;
        for (int i = 0; i < valves.size(); i++) if (value[i] == answer[i]) ok++;
        return "수위 " + (int) Math.round((surfaceY() - fs.y0() - 1.05) / 2.4 * 100) + "%";
    }

    @Override
    public boolean onInteract(Player p, Block block, Action action) {
        if (block.getType() != Material.LEVER && block.getType() != Material.WAXED_OXIDIZED_COPPER) return false;
        int tx = block.getX() - fs.ox(), tz = block.getZ() - fs.oz();
        for (int i = 0; i < valves.size(); i++) {
            int[] v = valves.get(i);
            if (v[0] != tx || v[1] != tz) continue;
            if (!running || action != Action.RIGHT_CLICK_BLOCK) return true;
            value[i] = (value[i] + 1) % states;
            fs.setBlock(v[0], 2, v[1], lever(value[i] % 2 == 1));
            fs.sound(block.getLocation(), Sound.BLOCK_COPPER_TRAPDOOR_OPEN, 1.0f, 0.6f + value[i] * 0.2f);
            refresh();
            boolean all = true;
            for (int k = 0; k < valves.size(); k++) if (value[k] != answer[k]) all = false;
            if (all) {
                fs.sound(center(), Sound.BLOCK_PISTON_EXTEND, 1.0f, 0.5f);
                succeed();
            }
            return true;
        }
        return false;
    }

    @Override
    protected void cleanup() {
        for (TextDisplay d : labels) fs.untrack(d);
        labels.clear();
        if (water != null) fs.untrack(water);
        water = null;
    }
}
