package kr.labyrinth.dungeon.treasure;

import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** 개인 루팅 장부 (순수): 상자마다 연 사람 — 같은 상자를 열면 각자 자기 몫을 한 번씩 굴린다. */
public final class ChestLedger {

    private final Map<Integer, Set<UUID>> opened = new HashMap<>();

    /** who 가 chest 를 처음 열면 true (이미 열었으면 false — 몫 없음). */
    public boolean open(int chest, UUID who) {
        return opened.computeIfAbsent(chest, k -> new HashSet<>()).add(who);
    }

    public boolean has(int chest, UUID who) {
        Set<UUID> s = opened.get(chest);
        return s != null && s.contains(who);
    }

    /** party 전원이 열었나 (비어 있으면 false). */
    public boolean allOpened(int chest, Collection<UUID> party) {
        if (party.isEmpty()) return false;
        Set<UUID> s = opened.get(chest);
        return s != null && s.containsAll(party);
    }

    public int count(int chest) {
        Set<UUID> s = opened.get(chest);
        return s == null ? 0 : s.size();
    }

    /** 한 번이라도 열린 상자 수. */
    public int touched() { return opened.size(); }
}
