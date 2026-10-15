package kr.labyrinth.dungeon;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.PartyScaling;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.entity.Player;

/**
 * 인스턴스(한 파티의 한 층 공략)의 불변 배율 정보. 몹·보스·루팅이 배율을 여기서 읽는다.
 * 입장 시점의 서버 난이도·인원으로 고정된다 (중간에 난이도를 바꿔도 다음 입장부터).
 * 난이도는 생성자에서 그 층의 실효값({@link Difficulty#atFloor}, 층 램프)으로 한 번 바뀌므로
 * {@link #difficulty()} 를 읽는 몹·보스·함정·기믹방·안내문이 모두 층별 값을 쓴다.
 * <p>
 * DungeonService 가 만들고, 관리자 소환처럼 인스턴스 밖이면 {@link #adhoc} 로 만든다.
 */
public final class InstanceContext {

    private final String id;
    private final int floor;
    private final List<UUID> members;
    private final Difficulty difficulty;
    private final double rampProgress;
    private final PartyScaling scaling;
    private final String worldName;
    private final long startedAt;

    /** difficulty = 서버 난이도 프리셋 (램프 포함). 여기서 floor 의 실효값으로 바꾼다. */
    public InstanceContext(String id, int floor, List<UUID> members, Difficulty difficulty, PartyScaling scaling,
                           String worldName, long startedAt) {
        this(id, floor, members, difficulty, difficulty == null ? 1.0 : difficulty.rampProgress(floor), scaling,
                worldName, startedAt);
    }

    /**
     * 램프 진행도를 직접 넘긴다 — 대체 보스처럼 이미 층 실효값인(램프 없는) 난이도를 다시 감쌀 때 원래 ctx 의
     * {@link #rampProgress()} 를 이어받는다. 난이도에 램프가 남아 있으면 여기서 한 번만 적용된다.
     */
    public InstanceContext(String id, int floor, List<UUID> members, Difficulty difficulty, double rampProgress,
                           PartyScaling scaling, String worldName, long startedAt) {
        this.id = id;
        this.floor = floor;
        this.members = List.copyOf(members);
        this.difficulty = difficulty == null ? null : difficulty.atFloor(floor);
        this.rampProgress = Double.isNaN(rampProgress) ? 1.0 : Math.max(0.0, Math.min(1.0, rampProgress));
        this.scaling = scaling;
        this.worldName = worldName;
        this.startedAt = startedAt;
    }

    /** 인스턴스 밖(관리자 소환·테스트)용: id "adhoc", 인원 n. */
    public static InstanceContext adhoc(int floor, int partySize, Difficulty difficulty, PartyScaling scaling) {
        List<UUID> fake = new ArrayList<>();
        for (int i = 0; i < Math.max(1, partySize); i++) fake.add(new UUID(0L, i));
        return new InstanceContext("adhoc", floor, fake, difficulty, scaling, null, System.currentTimeMillis());
    }

    public String id() { return id; }
    public int floor() { return floor; }
    /** 입장 당시 파티원 UUID (사망·이탈자 포함). */
    public List<UUID> members() { return members; }
    public int partySize() { return Math.max(1, members.size()); }
    public boolean solo() { return partySize() == 1; }
    /** 이 층의 실효 난이도 (램프 적용 끝 — id·이름·drop·xp 는 서버 난이도 그대로). */
    public Difficulty difficulty() { return difficulty; }
    /** 층 램프 진행도 0~1 (램프 없거나 다 오른 층 = 1). 보스 기믹 배율({@code MechanicScaling})이 쓴다. */
    public double rampProgress() { return rampProgress; }
    public PartyScaling scaling() { return scaling; }
    public long startedAt() { return startedAt; }

    /** 미궁 월드 (없으면 null). */
    public World world() { return worldName == null ? null : Bukkit.getWorld(worldName); }

    /** 온라인이고 미궁 월드에 있는 파티원. */
    public List<Player> onlineMembers() {
        List<Player> out = new ArrayList<>();
        for (UUID u : members) {
            Player p = Bukkit.getPlayer(u);
            if (p != null && p.isOnline() && (worldName == null || p.getWorld().getName().equals(worldName))) out.add(p);
        }
        return out;
    }

    // ── 배율 (GDD §2.4, §2.5) ─────────────────────────────────────────────
    /** 몹·보스 HP 배율 = 난이도 hp(층 램프) × 파티 hp (솔로면 솔로 보정). */
    public double hpMultiplier() { return difficulty.hp() * scaling.hp(partySize()); }
    /** 몹·보스 피해 배율 = 난이도 damage(층 램프) × 파티 dmg (솔로면 솔로 보정). */
    public double damageMultiplier() { return difficulty.damage() * scaling.damage(partySize()); }
    /** 드롭 확률 배율 = 난이도 drop × 파티 보상. */
    public double dropMultiplier() { return difficulty.drop() * scaling.reward(partySize()); }
    /** 골드 배율 = 파티 보상 (난이도 무관). */
    public double goldMultiplier() { return scaling.reward(partySize()); }
    /** 경험치 배율 = 난이도 xp (파티원 각자 전부 받음). */
    public double xpMultiplier() { return difficulty.xp(); }
    /** 경고 시간: seconds × 난이도 telegraph, 최소 0.5초. */
    public double windup(double seconds) { return difficulty.windup(seconds); }

    @Override
    public String toString() {
        return "Instance[" + id + " floor=" + floor + " n=" + partySize() + " " + difficulty.id() + "]";
    }
}
