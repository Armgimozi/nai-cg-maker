package kr.labyrinth.dungeon;

import java.util.Collection;
import java.util.Optional;
import org.bukkit.World;
import org.bukkit.entity.Player;

/**
 * 미궁 입장·진행·퇴장 (소유: dungeon+party 담당). 기본 구현 {@link NoopDungeonService}.
 * 층 클리어 시 {@code event.FloorClearEvent} 발생, 해금층 갱신, 보상, 귀환.
 */
public interface DungeonService {

    /** 미궁 전용 공허 월드 (아직 없으면 null). */
    World world();

    /** 이 월드가 미궁 월드인가 — 모든 리스너의 첫 검사 (ARCHITECTURE §7). */
    boolean isLabyrinthWorld(World world);

    /** 플레이어가 미궁 월드에 있는가. */
    default boolean isInLabyrinth(Player player) { return isLabyrinthWorld(player.getWorld()); }

    /** 플레이어가 속한 진행 중 인스턴스. */
    Optional<InstanceContext> currentInstance(Player player);

    Collection<InstanceContext> instances();

    /**
     * 입장 시도 (파티면 파티장만, 파티원 전원 입구 근처). 난이도 미설정·해금 부족 등은 메시지로 거절.
     * @return 입장 절차가 시작됐으면 true
     */
    boolean enter(Player leader, int floor);

    /** 인스턴스에서 나가 입구로 귀환. */
    void leave(Player player);

    /** 관리자 강제 종료. */
    void endInstance(String instanceId);

    // ── classes 담당이 추가 (사제 부활의 성가) — dungeon 구현은 자기 사망/관전 상태와 맞게 재정의할 것 ──

    /** 쓰러져 관전 중인가 (기본: 미궁 월드에서 관전 모드). */
    default boolean isDowned(Player player) {
        return player.getGameMode() == org.bukkit.GameMode.SPECTATOR && isInLabyrinth(player);
    }

    /**
     * 쓰러진 플레이어를 at 에 hpRatio(최대 HP 비율)로 부활. 기본 구현: 관전 → 서바이벌, 순간이동, HP 설정.
     * dungeon 구현은 인스턴스의 사망자 목록·전멸 판정도 함께 갱신하도록 재정의한다.
     * @return 부활시켰으면 true
     */
    default boolean revive(Player player, org.bukkit.Location at, double hpRatio) {
        if (!isDowned(player)) return false;
        player.setGameMode(org.bukkit.GameMode.SURVIVAL);
        player.teleport(at);
        kr.labyrinth.Services s = kr.labyrinth.Services.get();
        s.stats().setHp(player, s.stats().maxHp(player) * Math.max(0.05, Math.min(1.0, hpRatio)));
        return true;
    }
}
