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
import kr.labyrinth.dungeon.treasure.MimicEncounter;
import kr.labyrinth.dungeon.treasure.Treasures;
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
 * mimic_chance 확률로 상자 하나가 미믹 → 처음 연 순간 상자가 사라지고 그 자리에서 미믹이 튀어나온다({@link MimicEncounter},
 * 미로 미믹과 같은 몹·줄·시간). 미믹을 잡으면(또는 잠김 시간이 지나 달아나면) 그 자리에 상자가 돌아와 다른 상자처럼 각자 한 번씩 연다.
 */
public final class TreasureRoom extends Room {

    private final List<int[]> chests = new ArrayList<>();
    private final Map<Integer, Set<UUID>> opened = new HashMap<>();
    private int mimic = -1;
    private boolean mimicSprung;
    /** 미믹이 끝남(잡힘·달아남) → 그 자리에 상자가 돌아와 보통 상자가 됨. */
    private boolean mimicDone;
    private MimicEncounter mimicEnc;

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
        if (mimicSprung && !mimicDone) {
            MimicEncounter.State st = mimicEnc == null ? MimicEncounter.State.DEFEATED : mimicEnc.tick(System.currentTimeMillis());
            if (st != MimicEncounter.State.ALIVE) {
                if (st == MimicEncounter.State.FLED) mimicEnc.flee();
                restoreMimicChest(st == MimicEncounter.State.DEFEATED && mimicEnc != null && mimicEnc.count() > 0);
            }
        }
        if (t % 20 != 0 || state == State.CLEARED) return;
        for (int i = 0; i < chests.size(); i++) {
            if (i == mimic && mimicSprung && !mimicDone) continue;
            int[] c = chests.get(i);
            fs.world().spawnParticle(Particle.WAX_OFF, fs.tile(c[0], c[1], 1.3), 2, 0.3, 0.3, 0.3, 0.0);
        }
        if (mimicDone && aliveMobs() == 0 && allLooted()) state = State.CLEARED;
    }

    private boolean allLooted() {
        for (int i = 0; i < chests.size(); i++) {
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
            if (i == mimic && !mimicDone) {
                springMimic(block, p);
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

    /** 미믹 상자를 처음 열었다: 상자가 사라지고 그 자리에서 미믹이 연 사람을 보고 튀어나온다. */
    private void springMimic(Block block, Player opener) {
        if (mimicSprung) return;
        mimicSprung = true;
        int tx = block.getX() - fs.ox(), tz = block.getZ() - fs.oz();
        fs.setBlock(tx, 1, tz, Material.AIR);
        BlockFace f = facingCenter(tx, tz);
        mimicEnc = MimicEncounter.spring(fs, tx, tz, 1, f.getModX(), f.getModZ(), opener,
                fs.config().traps().mimicLockSeconds(), fs.config().mimicMobs(), rng);
        fs.actionBar(fs.allPlayers(), "<red><b>미믹이다!</b></red> <gray>상자가 이빨을 드러내고 덤벼든다", 50);
    }

    /** 미믹이 끝났다: 그 자리에 상자가 돌아오고 다른 상자처럼 각자 한 번씩 열 수 있다 (defeated = 잡았음 → 칭호 카운터). */
    private void restoreMimicChest(boolean defeated) {
        mimicDone = true;
        int[] c = chests.get(mimic);
        BlockData chest = Material.CHEST.createBlockData();
        if (chest instanceof Directional d) d.setFacing(facingCenter(c[0], c[1]));
        fs.setBlock(c[0], 1, c[1], chest);
        Location at = fs.tile(c[0], c[1], 1.4);
        fs.world().spawnParticle(Particle.HAPPY_VILLAGER, at, 16, 0.4, 0.3, 0.4, 0);
        fs.world().spawnParticle(Particle.BLOCK, at, 16, 0.35, 0.25, 0.35, 0.05, Material.OAK_PLANKS.createBlockData());
        fs.sound(at, Sound.BLOCK_CHEST_CLOSE, 1.0f, 1.4f);
        if (defeated) {
            fs.broadcast("<gold>미믹을 쓰러뜨렸다!</gold> <gray>그 자리에 상자가 나타났습니다 — 각자 열어 보세요.");
            for (Player p : fs.alivePlayers()) Treasures.count(fs, p, "mimic");
        } else {
            fs.broadcast("<gray>미믹이 깡충깡충 달아났습니다. 그 자리에 상자가 남았습니다.");
        }
    }
}
