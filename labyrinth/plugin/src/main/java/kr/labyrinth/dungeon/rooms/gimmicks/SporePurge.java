package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import kr.labyrinth.core.Text;
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
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.block.Action;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

/**
 * 3층 `spore_purge`: 포자 주머니 N개(HP pod_hp × 인스턴스 HP 배율)를 부순다. 오염된 바닥에선 감염이 쌓이고,
 * 빛나는 깨끗한 타일(주기적으로 이동) 위에서만 줄어든다. 감염 최대치 = 속박 + 피해.
 */
public final class SporePurge extends GimmickRoom {

    private final List<int[]> pods = new ArrayList<>();
    private double[] hp;
    private double maxHp;
    private final List<TextDisplay> bars = new ArrayList<>();
    private final List<int[]> clean = new ArrayList<>();
    private final Map<UUID, Double> infection = new HashMap<>();
    private final Map<UUID, Long> hitCooldown = new HashMap<>();
    private long nextShift;
    private long lastUpdate;

    public SporePurge(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        int n = Math.max(1, Math.min(6, params.integer("pods", 4)));
        int[][] spots = {{-6, -6}, {6, -6}, {6, 6}, {-6, 6}, {0, -7}, {0, 7}};
        for (int i = 0; i < n; i++) pods.add(new int[] {rx(spots[i][0]), rz(spots[i][1])});
    }

    @Override protected String title() { return "포자 정화"; }

    @Override
    protected String rules() {
        return "<gray>붉은 주머니들이 방을 숨 막히게 한다\n<gray>썩은 바닥 위, 몇 안 되는 빛만이 숨을 허락한다";
    }

    @Override
    protected List<String> hints() {
        return List.of(
                "썩은 바닥에 오래 서 있지 마라. 빛나는 곳은 썩지 않는다.",
                "붉은 포자 주머니는 칼에도 화살에도 터진다. 숨이 차면 빛나는 바닥 위에서 골라라.",
                "포자 주머니 " + pods.size() + "개를 모두 부숴라 (근접 좌클릭·화살). 균사 바닥에 서 있으면 감염이 쌓이고, 빛나는 타일(가끔 자리를 옮김) 위에서만 줄어든다. 가득 차면 몸이 굳고 다친다.");
    }

    @Override
    protected int timeLimit() { return 180; }

    @Override
    public void prepare(BlockList list) {
        for (int z = info.minZ(); z <= info.maxZ(); z++)
            for (int x = info.minX(); x <= info.maxX(); x++)
                list.add(fs.ox() + x, fs.y0(), fs.oz() + z, Material.MYCELIUM.createBlockData());
        for (int[] p : pods) {
            list.add(fs.ox() + p[0], fs.y0() + 1, fs.oz() + p[1], Material.MUSHROOM_STEM.createBlockData());
            list.add(fs.ox() + p[0], fs.y0() + 2, fs.oz() + p[1], Material.RED_MUSHROOM_BLOCK.createBlockData());
        }
    }

    @Override
    protected void begin() {
        maxHp = params.dbl("pod_hp", 400) * fs.ctx().hpMultiplier();
        hp = new double[pods.size()];
        for (int i = 0; i < pods.size(); i++) {
            hp[i] = maxHp;
            int[] p = pods.get(i);
            fs.setBlock(p[0], 1, p[1], Material.MUSHROOM_STEM);
            fs.setBlock(p[0], 2, p[1], Material.RED_MUSHROOM_BLOCK);
            bars.add(fs.text(fs.tile(p[0], p[1], 3.3), ""));
        }
        infection.clear();
        shiftTiles();
        lastUpdate = System.currentTimeMillis();
        refreshBars();
    }

    private void shiftTiles() {
        for (int[] c : clean) fs.setBlock(c[0], 0, c[1], Material.MYCELIUM);
        clean.clear();
        int n = Math.max(1, params.integer("clean_tiles", 6));
        int guard = 0;
        while (clean.size() < n && guard++ < 200) {
            int x = info.minX() + 1 + rng.nextInt(info.width() - 2), z = info.minZ() + 1 + rng.nextInt(info.depth() - 2);
            boolean bad = false;
            for (int[] p : pods) if (Math.abs(p[0] - x) <= 1 && Math.abs(p[1] - z) <= 1) bad = true;
            for (int[] c : clean) if (Math.abs(c[0] - x) <= 2 && Math.abs(c[1] - z) <= 2) bad = true;
            if (bad) continue;
            clean.add(new int[] {x, z});
            fs.setBlock(x, 0, z, Material.OCHRE_FROGLIGHT);
        }
        nextShift = System.currentTimeMillis() + Math.round(params.dbl("tile_shift_interval", 8) * 1000);
        fs.sound(center(), Sound.BLOCK_FUNGUS_PLACE, 1.0f, 0.6f);
    }

    private void refreshBars() {
        for (int i = 0; i < bars.size(); i++) {
            if (hp[i] <= 0) {
                bars.get(i).text(Text.mm("<dark_gray>정화됨"));
                continue;
            }
            int filled = (int) Math.ceil(10 * hp[i] / maxHp);
            bars.get(i).text(Text.mm("<red>포자 주머니</red>\n<red>" + "█".repeat(filled) + "<dark_gray>" + "█".repeat(10 - filled)));
        }
    }

    @Override
    protected void update(long t) {
        long now = System.currentTimeMillis();
        if (now >= nextShift) shiftTiles();
        if (t % 4 == 0) {
            for (int[] c : clean) fs.world().spawnParticle(Particle.WAX_ON, fs.tile(c[0], c[1], 1.1), 1, 0.25, 0.05, 0.25, 0.0);
            for (int i = 0; i < pods.size(); i++) {
                if (hp[i] <= 0) continue;
                int[] p = pods.get(i);
                fs.world().spawnParticle(Particle.SPORE_BLOSSOM_AIR, fs.tile(p[0], p[1], 2.5), 3, 1.0, 0.6, 1.0, 0.0);
            }
        }
        if (now - lastUpdate < 1000) return;
        double dt = (now - lastUpdate) / 1000.0;
        lastUpdate = now;
        double max = params.dbl("infection_max", 5), per = params.dbl("infection_per_second", 1);
        for (Player p : alivePlayersInside()) {
            Location l = p.getLocation();
            int tx = fs.tileX(l), tz = fs.tileZ(l);
            boolean safe = false;
            for (int[] c : clean) if (c[0] == tx && c[1] == tz) safe = true;
            double v = infection.getOrDefault(p.getUniqueId(), 0.0);
            v = safe ? Math.max(0, v - per * dt * 1.5) : v + per * dt;
            if (v >= max) {
                v = 0;
                hurt(p, params.dbl("infection_damage", 0.05), "spore_infection");
                p.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 40, 6, true, false, true));
                try {
                    fs.services().effects().apply(p, "root", 2.0, 1, null);
                } catch (Throwable ignored) {
                    // 상태이상 서비스 없음
                }
                p.playSound(l, Sound.ENTITY_SLIME_SQUISH, 1.0f, 0.5f);
                fs.services().hud().actionBar(p, Text.mm("<dark_green><b>감염 폭발!</b></dark_green> <gray>몸이 굳는다"), 40);
            } else if (v > 0) {
                int stacks = (int) Math.floor(v);
                fs.services().hud().actionBar(p, Text.mm("<green>감염</green> " + "<dark_green>●".repeat(stacks) + "<dark_gray>"
                        + "○".repeat((int) Math.max(0, max - stacks)) + (safe ? " <gold>정화 중" : "")), 25);
            }
            infection.put(p.getUniqueId(), v);
        }
    }

    @Override
    protected String status() {
        int left = 0;
        for (double v : hp) if (v > 0) left++;
        return "남은 포자 주머니 " + left + "/" + pods.size();
    }

    @Override
    protected float progress() {
        double sum = 0;
        for (double v : hp) sum += Math.max(0, v);
        return (float) (sum / Math.max(1, maxHp * pods.size()));
    }

    @Override
    public boolean onInteract(Player p, Block block, Action action) {
        int idx = podAt(block);
        if (idx < 0) return false;
        if (!running || hp[idx] <= 0) return true;
        if (action == Action.LEFT_CLICK_BLOCK) {
            long now = System.currentTimeMillis();
            if (now - hitCooldown.getOrDefault(p.getUniqueId(), 0L) < 350) return true;
            hitCooldown.put(p.getUniqueId(), now);
            damagePod(idx, Math.max(10, fs.services().stats().get(p).attackPower()));
        }
        return true;
    }

    @Override
    public void onProjectileHit(Player shooter, Block block) {
        int idx = podAt(block);
        if (idx < 0 || !running || hp[idx] <= 0) return;
        damagePod(idx, Math.max(10, fs.services().stats().get(shooter).attackPower()));
    }

    private int podAt(Block block) {
        int tx = block.getX() - fs.ox(), tz = block.getZ() - fs.oz(), dy = block.getY() - fs.y0();
        if (dy < 1 || dy > 2) return -1;
        for (int i = 0; i < pods.size(); i++) if (pods.get(i)[0] == tx && pods.get(i)[1] == tz) return i;
        return -1;
    }

    private void damagePod(int idx, double dmg) {
        hp[idx] -= dmg;
        int[] p = pods.get(idx);
        Location at = fs.tile(p[0], p[1], 2.3);
        fs.world().spawnParticle(Particle.BLOCK, at, 12, 0.3, 0.3, 0.3, Material.RED_MUSHROOM_BLOCK.createBlockData());
        fs.sound(at, Sound.BLOCK_FUNGUS_BREAK, 1.0f, 0.8f);
        if (hp[idx] <= 0) {
            hp[idx] = 0;
            fs.setBlock(p[0], 2, p[1], Material.AIR);
            fs.setBlock(p[0], 1, p[1], Material.BROWN_MUSHROOM_BLOCK);
            fs.world().spawnParticle(Particle.EXPLOSION, at, 1);
            fs.sound(at, Sound.ENTITY_SLIME_DEATH, 1.0f, 0.5f);
            boolean all = true;
            for (double v : hp) if (v > 0) all = false;
            if (all) succeed();
        }
        refreshBars();
    }

    @Override
    protected void cleanup() {
        for (TextDisplay d : bars) fs.untrack(d);
        bars.clear();
        for (int[] c : clean) fs.setBlock(c[0], 0, c[1], Material.MYCELIUM);
        clean.clear();
        infection.clear();
    }
}
