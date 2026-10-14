package kr.labyrinth.bosses;

import java.util.function.Consumer;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.mobs.CustomMob;

/** 진행 중인 보스전 핸들. 보스 엔티티 자체가 {@link CustomMob} 이다. */
public interface BossHandle extends CustomMob {

    BossDef def();

    /** 현재 페이즈 (1부터). */
    int phase();

    /** 보스가 죽으면 (보상 지급 후) 한 번 호출된다. DungeonService 가 층 클리어 처리에 쓴다. */
    void onDeath(Consumer<BossHandle> callback);

    /** 전멸·인스턴스 종료로 보스전을 보상 없이 끝낸다 (엔티티·장판·소환물 정리). */
    void end();
}
