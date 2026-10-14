package kr.labyrinth.dungeon.rooms;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.type.Stairs;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

/**
 * 휴식방: 몹 없음. 살아 있는 파티원이 들어오면 관전 중인 파티원 부활, 처음 도착한 사람마다 HP/MP 회복(1회).
 * 가운데 화톳불과 의자, 그 층의 이야기 NPC (npcs.yml placement: floor).
 */
public final class RestRoom extends Room {

    private final Set<UUID> healed = new HashSet<>();
    private final List<Entity> npcs = new ArrayList<>();

    public RestRoom(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
    }

    @Override
    public boolean wantsDecor() { return false; }

    @Override
    public void prepare(BlockList list) {
        int cx = fs.ox() + info.centerX(), cz = fs.oz() + info.centerZ(), y = fs.y0();
        // 돌 화로 위의 화톳불 (밟지 않게 한 칸 높임)
        list.add(cx, y + 1, cz, Material.POLISHED_BLACKSTONE_BRICKS.createBlockData());
        BlockData fire = Material.CAMPFIRE.createBlockData();
        if (fire instanceof org.bukkit.block.data.type.Campfire c) {
            c.setLit(true);
            c.setSignalFire(false);
        }
        list.add(cx, y + 2, cz, fire);
        // 사방 의자
        BlockFace[] faces = {BlockFace.NORTH, BlockFace.SOUTH, BlockFace.EAST, BlockFace.WEST};
        for (BlockFace f : faces) {
            Stairs st = (Stairs) Material.SPRUCE_STAIRS.createBlockData();
            st.setFacing(f.getOppositeFace());
            int bx = cx + f.getModX() * -3, bz = cz + f.getModZ() * -3;
            for (int side = -1; side <= 1; side++) {
                int sx = bx + (f.getModZ() != 0 ? side : 0), sz = bz + (f.getModX() != 0 ? side : 0);
                list.add(sx, y + 1, sz, st.clone());
            }
        }
        // 바닥 깔개
        for (int dz = -1; dz <= 1; dz++)
            for (int dx = -1; dx <= 1; dx++)
                if (dx != 0 || dz != 0) list.add(cx + dx, y, cz + dz, Material.STRIPPED_SPRUCE_WOOD.createBlockData());
    }

    @Override
    public void onReady() {
        fs.text(fs.tile(info.centerX(), info.centerZ(), 3.6), "<green><b>휴식의 방</b></green>\n<gray>쓰러진 동료가 이곳에서 다시 일어선다");
        // 층 이야기 NPC
        for (NpcDef n : fs.services().content().npcs().values()) {
            if (!"floor".equals(n.placement()) || n.floor() != fs.floor()) continue;
            try {
                Location at = fs.tile(info.minX() + 3, info.minZ() + 3, 1);
                at.setYaw(-45);
                Entity e = fs.services().npcs().spawnTemporary(n.id(), at);
                if (e != null) npcs.add(e);
            } catch (Throwable t) {
                Log.error("휴식방 NPC 소환 실패: " + n.id(), t);
            }
            break;
        }
    }

    @Override
    public void onEnter(Player p) {
        if (state == State.IDLE) {
            state = State.CLEARED;
            fs.actionBar(fs.allPlayers(), "<green>따뜻한 불빛이 몸을 감싼다...</green>", 50);
        }
        boolean anyDead = false;
        for (Player o : fs.run().onlineMembers()) if (!fs.run().isAlive(o)) anyDead = true;
        if (anyDead) {
            fs.run().reviveAll(center(), fs.config().restHeal());
            fs.broadcast("<green>휴식방의 불빛이 쓰러진 동료를 일으켜 세웠습니다.");
        }
        if (healed.add(p.getUniqueId())) {
            double frac = fs.config().restHeal();
            fs.services().stats().heal(p, fs.services().stats().maxHp(p) * frac);
            fs.services().classes().restoreMana(p, fs.services().classes().maxMana(p) * frac);
            fs.services().hud().refresh(p);
            p.playSound(p.getLocation(), Sound.BLOCK_BEACON_POWER_SELECT, 0.6f, 1.6f);
            p.spawnParticle(Particle.HEART, p.getLocation().add(0, 2, 0), 5, 0.4, 0.2, 0.4, 0.0);
        }
    }

    @Override
    public void tick(long t) {
        if (t % 20 == 0) fs.world().spawnParticle(Particle.CAMPFIRE_COSY_SMOKE, fs.tile(info.centerX(), info.centerZ(), 3.2), 1, 0.1, 0.1, 0.1, 0.01);
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        for (Entity e : npcs) if (e.isValid()) e.remove();
        npcs.clear();
    }
}
