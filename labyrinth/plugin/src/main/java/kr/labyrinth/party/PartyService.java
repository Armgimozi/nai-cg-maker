package kr.labyrinth.party;

import java.util.List;
import java.util.Optional;
import org.bukkit.entity.Player;

/**
 * 파티 (생성/초대/수락/탈퇴/추방/위임/파티 채팅, 최대 인원 config). 소유: dungeon+party 담당.
 * 기본 구현 {@link SoloPartyService}: 모두 솔로.
 */
public interface PartyService {

    Optional<Party> partyOf(Player player);

    /** 파티원 중 온라인인 플레이어 (본인 포함). 파티가 없으면 [본인]. */
    List<Player> onlineMembers(Player player);

    /** 파티장 (파티가 없으면 본인). */
    Player leader(Player player);

    default boolean sameParty(Player a, Player b) {
        if (a.equals(b)) return true;
        return partyOf(a).map(p -> p.contains(b.getUniqueId())).orElse(false);
    }

    /** 파티 인원 (솔로 1). */
    default int size(Player player) { return partyOf(player).map(Party::size).orElse(1); }
}
