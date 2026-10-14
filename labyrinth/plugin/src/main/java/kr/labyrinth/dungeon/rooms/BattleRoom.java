package kr.labyrinth.dungeon.rooms;

import kr.labyrinth.content.IntRange;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.mobs.CustomMob;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;

/**
 * 전투방(일반 몹 mob_density × 인원 보정, 전멸 시 개방) / 엘리트방(엘리트 1 + 일반 2~3, 엘리트 처치 시 개방).
 * 문은 진입 후 잠깐 뒤 닫힌다. 안에 살아 있는 파티원이 사라지면 방을 초기화해 진행이 막히지 않게 한다.
 */
public final class BattleRoom extends Room {

    private final boolean elite;
    private long lockAt = -1;
    private long spawnAt = -1;
    private CustomMob eliteMob;
    private int spawned;

    public BattleRoom(FloorState fs, FloorLayout.RoomInfo info, boolean elite) {
        super(fs, info);
        this.elite = elite;
    }

    @Override
    public void onEnter(Player p) {
        if (state != State.IDLE) return;
        state = State.ACTIVE;
        emptyTicks = 0;
        long now = System.currentTimeMillis();
        lockAt = now + fs.config().roomLockDelay() * 1000L;
        spawnAt = lockAt + 600;
        fs.actionBar(fs.allPlayers(), elite ? "<dark_red><b>강력한 기척이 느껴진다...</b></dark_red> <gray>문이 닫힙니다"
                : "<red>적의 기척!</red> <gray>문이 닫힙니다", 50);
        fs.sound(center(), Sound.BLOCK_TRIAL_SPAWNER_DETECT_PLAYER, 1.0f, elite ? 0.6f : 0.9f);
    }

    @Override
    public void tick(long t) {
        if (state != State.ACTIVE) return;
        long now = System.currentTimeMillis();
        if (lockAt > 0 && now >= lockAt) {
            lockAt = -1;
            lock();
        }
        if (spawnAt > 0 && now >= spawnAt) {
            spawnAt = -1;
            spawnWave();
            if (spawned == 0) {
                clear();
                return;
            }
        }
        if (spawnAt > 0 || lockAt > 0) return;
        if (t % 10 == 0) {
            boolean done = elite ? (eliteMob == null || !FloorState.alive(eliteMob)) : aliveMobs() == 0;
            if (done) {
                clear();
                return;
            }
            if (abandoned(24)) reset(); // 10틱마다 호출 → 약 6초
        }
    }

    private void spawnWave() {
        int n = fs.ctx().partySize();
        if (elite) {
            String eliteId = fs.def().elite();
            Location at = center();
            eliteMob = spawn(eliteId, at);
            if (eliteMob != null) {
                spawned++;
                fs.title("", "<dark_red><b>" + eliteMob.displayName() + "</b></dark_red>", 5, 40, 10);
                fs.sound(at, Sound.ENTITY_RAVAGER_ROAR, 1.0f, 0.8f);
            }
            int adds = 2 + rng.nextInt(2);
            for (int i = 0; i < adds; i++) if (spawn(fs.randomFloorMob(rng), randomSpot(4)) != null) spawned++;
            return;
        }
        IntRange density = fs.def().mobDensity();
        int base = density.roll(java.util.concurrent.ThreadLocalRandom.current());
        int count = (int) Math.round(base * (1 + fs.config().mobCountPerMember() * (n - 1)));
        count = Math.max(1, Math.min(fs.config().maxMobsPerRoom(), count));
        for (int i = 0; i < count; i++) {
            Location at = randomSpot(4);
            if (spawn(fs.randomFloorMob(rng), at) != null) spawned++;
        }
        if (spawned > 0) fs.actionBar(alivePlayersInside(), "<red>적 " + spawned + "마리</red>", 40);
    }

    private void clear() {
        state = State.CLEARED;
        unlock();
        Location c = center();
        fs.world().spawnParticle(Particle.HAPPY_VILLAGER, c.clone().add(0, 0.5, 0), 20, 3, 0.4, 3, 0.0);
        fs.sound(c, Sound.BLOCK_AMETHYST_BLOCK_CHIME, 1.0f, 1.2f);
        fs.actionBar(fs.allPlayers(), elite ? "<gold>정예를 쓰러뜨렸습니다!</gold> <gray>문이 열렸습니다"
                : "<green>방을 정리했습니다.</green> <gray>문이 열렸습니다", 50);
    }

    /** 고착 방지: 안에 아무도 없으면 몹을 거두고 문을 열어 다음 진입 때 다시 시작. */
    private void reset() {
        removeMobs();
        eliteMob = null;
        spawned = 0;
        unlock();
        state = State.IDLE;
        emptyTicks = 0;
        for (Player p : fs.allPlayers()) Text.send(p, "<gray>방의 적들이 어둠 속으로 물러났습니다. 다시 들어가면 전투가 시작됩니다.");
    }
}
