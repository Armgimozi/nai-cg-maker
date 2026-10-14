package kr.labyrinth.party;

import java.util.List;
import java.util.UUID;

/** 파티 읽기 전용 뷰. members 는 리더 포함, 가입 순. */
public interface Party {
    String id();
    UUID leader();
    List<UUID> members();
    default int size() { return members().size(); }
    default boolean isLeader(UUID u) { return leader().equals(u); }
    default boolean contains(UUID u) { return members().contains(u); }
}
