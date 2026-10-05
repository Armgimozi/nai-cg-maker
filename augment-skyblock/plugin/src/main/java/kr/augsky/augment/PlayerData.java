package kr.augsky.augment;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.UUID;

/** 플레이어 한 명의 증강 정보. players/<uuid>.yml 에 저장된다. */
public final class PlayerData {
    public final UUID id;
    public String lastName = "";
    public final LinkedHashMap<String, Integer> augments = new LinkedHashMap<>();
    public double soul;
    public boolean starterGiven;
    public int picks;
    /** '사람마다 한 번' 제단 모드에서 이미 쓴 제단 */
    public final java.util.Set<String> usedAltars = new java.util.HashSet<>();

    // 진행 중인 선택지 (창을 닫아도 유지된다)
    public Tier offerTier;
    public final List<String> offer = new ArrayList<>();
    public int rerolls;

    // 저장하지 않는 값
    transient Stats stats;
    public transient long undyingReadyAt, voidReadyAt, jumpReadyAt, regenLastAt;
    public transient boolean dirty;

    public PlayerData(UUID id) {
        this.id = id;
    }

    public int stacks(String augId) {
        return augments.getOrDefault(augId, 0);
    }

    public int owned(Tier t, AugmentRegistry reg) {
        int n = 0;
        for (var en : augments.entrySet()) {
            AugmentDef d = reg.get(en.getKey());
            if (d != null && d.tier() == t) n += en.getValue();
        }
        return n;
    }

    public int total() {
        int n = 0;
        for (int v : augments.values()) n += v;
        return n;
    }

    public boolean hasOffer() {
        return offerTier != null && !offer.isEmpty();
    }

    public void clearOffer() {
        offerTier = null;
        offer.clear();
        rerolls = 0;
    }
}
