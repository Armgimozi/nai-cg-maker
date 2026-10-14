package kr.labyrinth.dungeon.rooms;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.Lidded;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.Directional;
import org.bukkit.entity.Player;
import org.bukkit.event.block.Action;

/**
 * 보물방: 상자 여러 개 (개인 루팅 — 각자 한 번씩 열어 자기 몫을 받음, 루팅 테이블 treasure_floor_N).
 * mimic_chance 확률로 상자 하나가 미믹 → 처음 연 순간 사라지고 층 일반 몹이 기습한다.
 */
public final class TreasureRoom extends Room {

    private final List<int[]> chests = new ArrayList<>();
    private final Map<Integer, Set<UUID>> opened = new HashMap<>();
    private int mimic = -1;
    private boolean mimicSprung;

    public TreasureRoom(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
        int n = fs.config().treasureChests();
        int cx = info.centerX(), cz = info.centerZ();
        int[][] spots = {{0, 4}, {-4, 2}, {4, 2}, {-3, -3}, {3, -3}, {0, -5}};
        for (int i = 0; i < n && i < spots.length; i++) chests.add(new int[] {cx + spots[i][0], cz + spots[i][1]});
        if (rng.nextDouble() < fs.config().mimicChance()) mimic = rng.nextInt(chests.size());
    }

    @Override
    public void prepare(BlockList list) {
        Material accent = accent();
        for (int[] c : chests) {
            BlockData chest = Material.CHEST.createBlockData();
            if (chest instanceof Directional d) d.setFacing(facingCenter(c[0], c[1]));
            list.add(fs.ox() + c[0], fs.y0() + 1, fs.oz() + c[1], chest);
            list.add(fs.ox() + c[0], fs.y0(), fs.oz() + c[1], accent.createBlockData());
        }
    }

    private Material accent() {
        List<String> a = fs.def().palette("accent");
        Material m = a.isEmpty() ? null : Material.matchMaterial(a.get(0));
        return m == null || !m.isBlock() ? Material.GILDED_BLACKSTONE : m;
    }

    private BlockFace facingCenter(int x, int z) {
        int dx = info.centerX() - x, dz = info.centerZ() - z;
        if (Math.abs(dx) > Math.abs(dz)) return dx > 0 ? BlockFace.EAST : BlockFace.WEST;
        return dz >= 0 ? BlockFace.SOUTH : BlockFace.NORTH;
    }

    @Override
    public void onReady() {
        fs.text(fs.tile(info.centerX(), info.centerZ(), 2.4), "<gold><b>보물의 방</b></gold>\n<gray>상자마다 각자 자기 몫이 들어 있다");
    }

    @Override
    public void onEnter(Player p) {
        if (state == State.IDLE) {
            state = State.ACTIVE;
            fs.sound(center(), Sound.BLOCK_CHEST_LOCKED, 0.6f, 1.4f);
        }
    }

    @Override
    public void tick(long t) {
        if (t % 20 != 0 || state == State.CLEARED) return;
        for (int i = 0; i < chests.size(); i++) {
            if (i == mimic && mimicSprung) continue;
            int[] c = chests.get(i);
            fs.world().spawnParticle(Particle.WAX_OFF, fs.tile(c[0], c[1], 1.3), 2, 0.3, 0.3, 0.3, 0.0);
        }
        if (mimicSprung && aliveMobs() == 0 && allLooted()) state = State.CLEARED;
    }

    private boolean allLooted() {
        for (int i = 0; i < chests.size(); i++) {
            if (i == mimic) continue;
            if (opened.getOrDefault(i, Set.of()).size() < fs.alivePlayers().size()) return false;
        }
        return true;
    }

    @Override
    public boolean onInteract(Player p, Block block, Action action) {
        if (block.getType() != Material.CHEST) return false;
        int tx = block.getX() - fs.ox(), tz = block.getZ() - fs.oz();
        for (int i = 0; i < chests.size(); i++) {
            int[] c = chests.get(i);
            if (c[0] != tx || c[1] != tz) continue;
            if (action != Action.RIGHT_CLICK_BLOCK) return true;
            if (i == mimic) {
                springMimic(block);
                return true;
            }
            Set<UUID> who = opened.computeIfAbsent(i, k -> new HashSet<>());
            if (!who.add(p.getUniqueId())) {
                Text.send(p, "<gray>이 상자의 내 몫은 이미 챙겼습니다.");
                return true;
            }
            Location at = block.getLocation().add(0.5, 1.0, 0.5);
            fs.loot("treasure_floor_" + fs.floor(), List.of(p), at, "chest");
            p.playSound(at, Sound.BLOCK_CHEST_OPEN, 0.8f, 1.1f);
            p.spawnParticle(Particle.TOTEM_OF_UNDYING, at, 16, 0.3, 0.3, 0.3, 0.15);
            if (block.getState() instanceof Lidded lid) {
                lid.open();
                Bukkit.getScheduler().runTaskLater(fs.services().plugin(), () -> {
                    if (block.getState() instanceof Lidded l2) l2.close();
                }, 30L);
            }
            return true;
        }
        return false;
    }

    private void springMimic(Block block) {
        if (mimicSprung) return;
        mimicSprung = true;
        Location at = block.getLocation().add(0.5, 0, 0.5);
        int tx = block.getX() - fs.ox(), tz = block.getZ() - fs.oz();
        fs.setBlock(tx, 1, tz, Material.AIR);
        fs.world().spawnParticle(Particle.LARGE_SMOKE, at.clone().add(0, 0.6, 0), 30, 0.4, 0.4, 0.4, 0.05);
        fs.sound(at, Sound.ENTITY_EVOKER_PREPARE_ATTACK, 1.0f, 0.7f);
        fs.actionBar(fs.allPlayers(), "<red><b>미믹이다!</b></red> <gray>상자가 이빨을 드러냈다", 50);
        int k = fs.config().mimicMobs();
        for (int i = 0; i < k; i++) spawn(fs.randomFloorMob(rng), at.clone().add(rng.nextDouble() - 0.5, 0, rng.nextDouble() - 0.5));
    }
}
