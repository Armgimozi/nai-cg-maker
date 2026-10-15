package kr.labyrinth.dungeon.rooms;

import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;

/** 시작방: 파티 집결 → 카운트다운 → 문 개방. 가운데에 층 이름 표지. */
public final class StartRoom extends Room {

    private boolean countdown;
    private int remaining = -1;
    private long nextSecond;

    public StartRoom(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
    }

    @Override
    public boolean wantsDecor() { return false; }

    @Override
    public void prepare(BlockList list) {
        // 가운데 원형 문양 (입장 지점)
        int cx = info.centerX(), cz = info.centerZ();
        Material accent = Material.matchMaterial(fs.def().palette("accent").isEmpty() ? "CHISELED_STONE_BRICKS"
                : fs.def().palette("accent").get(0));
        if (accent == null || !accent.isBlock()) accent = Material.CHISELED_STONE_BRICKS;
        for (int dz = -2; dz <= 2; dz++) {
            for (int dx = -2; dx <= 2; dx++) {
                int d2 = dx * dx + dz * dz;
                if (d2 == 4 || d2 == 5 || d2 == 0) list.add(fs.ox() + cx + dx, fs.y0(), fs.oz() + cz + dz, accent.createBlockData());
            }
        }
    }

    @Override
    public void onReady() {
        lock();
        state = State.ACTIVE;
        Location sign = fs.tile(info.centerX(), info.minZ() + 2, 2.8);
        String sub = fs.def().subtitle() == null ? "지하 " + fs.floor() + "층" : fs.def().subtitle();
        fs.text(sign, "<gradient:#c9a2ff:#7fd8ff><b>" + sub + "</b></gradient>\n" + fs.def().name());
    }

    public boolean countdownStarted() { return countdown; }

    public void beginCountdown(int seconds) {
        if (countdown) return;
        countdown = true;
        remaining = Math.max(0, seconds);
        nextSecond = 0;
    }

    @Override
    public void tick(long t) {
        if (!countdown || remaining < 0) return;
        long now = System.currentTimeMillis();
        if (now < nextSecond) return;
        nextSecond = now + 1000;
        if (remaining > 0) {
            fs.title("<yellow><b>" + remaining + "</b></yellow>", "<gray>문이 열립니다", 0, 22, 0);
            for (Player p : fs.allPlayers()) p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_HAT, 0.8f, 1.0f + (3 - remaining) * 0.15f);
            remaining--;
            return;
        }
        remaining = -1;
        unlock();
        state = State.CLEARED;
        fs.markStarted();
        fs.title("<gold><b>출발!</b></gold>", "<gray>보스방은 미궁의 가장 남쪽에 있습니다", 0, 30, 10);
        fs.broadcast("<gray>미궁은 갈림길과 막다른 길투성이입니다. 지나온 길은 <white>/미궁 지도</white> 로 볼 수 있습니다. "
                + "<dark_gray>(막다른 길 끝의 금 간 벽은 때리면 무너진다는 소문이…)");
        for (Player p : fs.allPlayers()) p.playSound(p.getLocation(), Sound.EVENT_RAID_HORN, 0.6f, 1.2f);
        fs.world().spawnParticle(Particle.END_ROD, center().add(0, 0.5, 0), 40, 2.5, 0.5, 2.5, 0.02);
    }
}
