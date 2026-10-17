package kr.labyrinth.data;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 파일에 아직 쓰지 못한 스냅샷 (캐시에서 빠진 — 나간·오프라인 — 사람). 전용 스레드가 그 스냅샷을 다 쓰면 {@link #done} 으로 지운다.
 * 그 사이에 다시 들어와 데이터를 읽으면 파일(예전 값) 대신 {@link #get} 을 읽는다 — 나갈 때 바꾼 값
 * (싸우는 중 끊김 페널티의 골드·경험치 등)이 쓰기가 늦은 탓에 되살아나지 않게. 순수 자료 (시험할 수 있게).
 */
final class PendingWrites {

    private final Map<UUID, String> latest = new ConcurrentHashMap<>();

    /** 쓰기를 맡김 (같은 사람의 앞 스냅샷보다 새것). */
    void put(UUID id, String yaml) { latest.put(id, yaml); }

    /** 그 스냅샷을 다 씀 — 그 뒤 더 새 스냅샷이 맡겨졌으면 그것은 남긴다. */
    void done(UUID id, String yaml) { latest.remove(id, yaml); }

    /** 아직 안 쓴 가장 새 스냅샷 (없으면 null = 파일이 최신). */
    String get(UUID id) { return latest.get(id); }
}
