package kr.labyrinth.pvp;

import java.util.List;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/**
 * 스킬·무기 스킬·장판이 '적/아군'을 고르는 단일 규칙 (아군 오사 방지). 소유: pvp 담당.
 * 미궁에서는 커스텀 몹이 적, 매치 안에서는 상대 팀 플레이어가 적. 기본 구현 {@link DefaultTargetFilter}.
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
}
