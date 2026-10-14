package kr.labyrinth.stats;

import org.bukkit.entity.Player;

/**
 * 파생 능력치 계산에 가산 스탯을 보태는 주체. 장비(items), 칭호(titles), 버프(classes/StatusEffectService) 모듈이
 * {@code services.stats().addContributor(...)} 로 등록한다. 메인 스레드에서 호출된다.
 */
@FunctionalInterface
public interface StatContributor {
    void contribute(Player player, StatBlock block);
}
