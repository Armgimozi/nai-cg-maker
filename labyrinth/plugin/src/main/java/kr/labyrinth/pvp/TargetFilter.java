package kr.labyrinth.pvp;

import java.util.List;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/**
 * 근접·화살·스킬·무기 스킬·장판·물약이 '적/아군'을 고르는 단일 규칙 (아군 오사 방지). 소유: pvp 담당.
 * 규칙(GDD §18, {@link PvpRules}): 커스텀 몹은 플레이어의 적, <b>같은 파티원끼리는 어디서든 적이 아니고</b>
 * 그 밖의 플레이어끼리는 적(PvP 켜짐 · 마을 안전지대 밖일 때). 기본 구현 {@link DefaultTargetFilter} 는 PvP 꺼짐이고,
 * pvp 모듈이 켜지면 config {@code pvp:} 를 따르는 구현으로 바뀐다.
 */
public interface TargetFilter {

    /** source 가 target 을 공격해도 되는가. */
    boolean isEnemy(LivingEntity source, Entity target);

    /** source 의 아군인가 (자기 자신 포함, 치유·버프 대상). */
    boolean isAlly(LivingEntity source, Entity target);

    /** center 반경 radius 안의 source 기준 적 (살아 있는 것만, 가까운 순). */
    List<LivingEntity> enemiesIn(LivingEntity source, Location center, double radius);

    /** center 반경 radius 안의 아군 플레이어 (본인 포함). */
    List<Player> alliesIn(Player source, Location center, double radius);

    /** 현재 PvP 설정 (켜짐·배율·한 방 상한·안전지대). 메뉴·안내 표시와 피해 조정에 쓴다. */
    default PvpConfig pvpConfig() { return PvpConfig.OFF; }

    /** PvP 전투 상태 (회복·보호막·상태이상 배율). pvp 모듈이 꺼져 있으면 {@link PvpState#NONE}. */
    default PvpState pvp() { return PvpState.NONE; }

    /** 그 위치가 PvP 금지 구역(마을 안전지대)인가. */
    default boolean inSafeZone(Location location) { return false; }
}
