package kr.labyrinth.party;

import java.util.List;
import java.util.Optional;
import org.bukkit.entity.Player;

/** 안전한 기본 구현: 파티 없음, 모두 솔로. */
public class SoloPartyService implements PartyService {
    @Override
    public Optional<Party> partyOf(Player player) { return Optional.empty(); }

    @Override
    public List<Player> onlineMembers(Player player) { return List.of(player); }

    @Override
    public Player leader(Player player) { return player; }
}
