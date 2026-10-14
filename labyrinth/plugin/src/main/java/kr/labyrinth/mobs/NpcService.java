package kr.labyrinth.mobs;

import java.util.Optional;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

/**
 * NPC (npcs.yml: Mannequin + 커스텀 스킨, 우클릭 → 역할별 GUI). 소유: mobs+npc 담당. 기본 구현 {@link NoopNpcService}.
 * 오버월드 NPC 위치는 구현이 저장(npcs-placed.yml 등)하고 서버 시작 시 다시 세운다.
 */
public interface NpcService {

    /** npcId 를 loc 에 세우고 위치를 저장 (/labadmin setnpc). 이미 있으면 옮긴다. */
    Entity place(String npcId, Location loc);

    /** 저장된 NPC 제거. */
    boolean remove(String npcId);

    /** 엔티티가 NPC 면 그 id. */
    Optional<String> npcIdOf(Entity entity);

    /** 플레이어가 NPC 와 상호작용 (우클릭) — 역할별 메뉴 열기. */
    void interact(Player player, String npcId);

    /** 층 휴식방 등 임시 NPC 스폰 (저장 안 함). */
    Entity spawnTemporary(String npcId, Location loc);
}
