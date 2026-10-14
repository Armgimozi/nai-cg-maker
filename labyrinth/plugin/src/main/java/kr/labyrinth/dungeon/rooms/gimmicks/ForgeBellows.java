package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
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
 * 5층 `forge_bellows`: 풀무 발판 N개. 사람이 선 발판 수 × heat_per_plate 만큼 초당 열기 상승, 아무도 없으면 heat_decay 감소.
 * 열기 heat_needed = 모루 점화 성공. 솔로는 발판 하나에 서면 solo_hold_bonus 배. 그 사이 용광로의 하수인이 방해한다.
 */
public final class ForgeBellows extends GimmickRoom {

    private final List<int[]> plates = new ArrayList<>();
    private double heat;
    private long lastUpdate;
    private long nextHarass;

    public ForgeBellows(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        int n = Math.max(1, Math.min(5, params.integer("plates", 3)));
        int[][] spots = {{-6, -5}, {6, -5}, {0, 6}, {-6, 5}, {6, 5}};
        for (int i = 0; i < n; i++) plates.add(new int[] {rx(spots[i][0]), rz(spots[i][1])});
    }

    @Override protected String title() { return "용광로의 풀무"; }

    @Override
    protected String rules() {
        return "<gray><gold>풀무 발판</gold> 위에 서서 열기를 올려라 — 함께 설수록 빠르다\n<gray>열기가 가득 차면 모루에 불이 붙는다. 아무도 없으면 식는다";
    }

    @Override
    protected int timeLimit() { return 150; }

    @Override
    public void prepare(BlockList list) {
        for (int[] p : plates) {
            list.add(fs.ox() + p[0], fs.y0(), fs.oz() + p[1], Material.MAGMA_BLOCK.createBlockData());
            list.add(fs.ox() + p[0], fs.y0() + 1, fs.oz() + p[1], Material.HEAVY_WEIGHTED_PRESSURE_PLATE.createBlockData());
        }
        int cx = fs.ox() + info.centerX(), cz = fs.oz() + info.centerZ();
        list.add(cx, fs.y0() + 1, cz, Material.POLISHED_BLACKSTONE_BRICKS.createBlockData());
        list.add(cx, fs.y0() + 2, cz, Material.ANVIL.createBlockData());
    }

    @Override
    protected void begin() {
        heat = 0;
        lastUpdate = System.currentTimeMillis();
        nextHarass = lastUpdate + 8000;
    }

    @Override
    protected void update(long t) {
        long now = System.currentTimeMillis();
        double dt = (now - lastUpdate) / 1000.0;
        lastUpdate = now;
        Set<Integer> occupied = new HashSet<>();
        for (Player p : alivePlayersInside()) {
            Location l = p.getLocation();
            int tx = fs.tileX(l), tz = fs.tileZ(l);
            for (int i = 0; i < plates.size(); i++) if (plates.get(i)[0] == tx && plates.get(i)[1] == tz) occupied.add(i);
        }
        double perPlate = params.dbl("heat_per_plate", 4);
        if (occupied.isEmpty()) {
            heat = Math.max(0, heat - params.dbl("heat_decay", 6) * dt);
        } else {
            double gain = occupied.size() * perPlate;
            if (partySize() == 1) gain *= params.dbl("solo_hold_bonus", 2.0);
            heat += gain * dt;
        }
        if (t % 4 == 0) {
            Location anvil = fs.tile(info.centerX(), info.centerZ(), 3.0);
            int flames = 1 + (int) (heat / 12);
            fs.world().spawnParticle(Particle.FLAME, anvil, flames, 0.35, 0.2, 0.35, 0.01);
            if (heat > 60) fs.world().spawnParticle(Particle.LAVA, anvil, 1, 0.2, 0.1, 0.2, 0.0);
            for (int i : occupied) {
                int[] pl = plates.get(i);
                fs.world().spawnParticle(Particle.SMALL_FLAME, fs.tile(pl[0], pl[1], 1.2), 4, 0.3, 0.05, 0.3, 0.01);
            }
            if (!occupied.isEmpty() && t % 20 == 0) fs.sound(anvil, Sound.BLOCK_FIRE_AMBIENT, 1.0f, 0.6f + (float) (heat / 150));
        }
        if (now >= nextHarass) {
            nextHarass = now + 10_000;
            if (aliveMobs() < 2 + partySize() / 2) spawn(fs.randomFloorMob(rng), randomSpot(4));
        }
        if (heat >= params.dbl("heat_needed", 100)) {
            Location anvil = fs.tile(info.centerX(), info.centerZ(), 2.5);
            fs.world().spawnParticle(Particle.LAVA, anvil, 30, 0.6, 0.4, 0.6, 0.1);
            fs.world().spawnParticle(Particle.FLAME, anvil, 80, 0.8, 1.0, 0.8, 0.08);
            fs.sound(anvil, Sound.BLOCK_ANVIL_USE, 1.0f, 0.6f);
            fs.sound(anvil, Sound.ENTITY_BLAZE_SHOOT, 1.0f, 0.5f);
            succeed();
        }
    }

    @Override
    protected String status() {
        return "열기 " + (int) heat + "/" + params.integer("heat_needed", 100);
    }

    @Override
    protected float progress() { return (float) (heat / Math.max(1, params.dbl("heat_needed", 100))); }

    @Override
    public boolean onInteract(Player p, Block block, Action action) {
        if (block.getType() == Material.ANVIL) return true; // 모루 GUI 막기
        return action == Action.PHYSICAL && block.getType() == Material.HEAVY_WEIGHTED_PRESSURE_PLATE;
    }
}
