package kr.labyrinth.party;

import java.util.List;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;

/** 가변 파티 (PartyManager 안에서만 수정). 채팅 스레드에서도 읽으므로 CopyOnWrite. */
final class PartyImpl implements Party {

    private final String id;
    private volatile UUID leader;
    private final CopyOnWriteArrayList<UUID> members = new CopyOnWriteArrayList<>();

    PartyImpl(String id, UUID leader) {
        this.id = id;
        this.leader = leader;
        members.add(leader);
    }

    @Override public String id() { return id; }
    @Override public UUID leader() { return leader; }
    @Override public List<UUID> members() { return List.copyOf(members); }

    void leader(UUID u) { leader = u; }
    void add(UUID u) { if (!members.contains(u)) members.add(u); }
    void remove(UUID u) { members.remove(u); }
}
