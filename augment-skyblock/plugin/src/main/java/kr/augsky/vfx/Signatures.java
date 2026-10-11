package kr.augsky.vfx;

import java.util.HashMap;
import java.util.Map;

/** 스킬 id → 전용 연출. 프리즘 17 + 보스 무기 22 + 보스 몬스터 16 + 섬·균열 몇 개 */
final class Signatures {
    private static final Map<String, Signature> ALL = new HashMap<>();

    static {
        PrismSigs.register(ALL);
        BossSigs.register(ALL);
        MobSigs.register(ALL);
        RiftSigs.register(ALL);
    }

    private Signatures() {}

    static Signature get(String skill) {
        Signature s = ALL.get(skill);
        return s != null ? s : Signature.NONE;
    }

    static int count() {
        return ALL.size();
    }
}
