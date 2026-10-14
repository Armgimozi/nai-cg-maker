package kr.labyrinth.items;

import java.util.Collection;
import java.util.List;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * loot.yml 테이블 굴림 (GDD §11.10: 개인 루팅, 희귀도 가중치, LUK·파티 보정, 직업 편향). 소유: items 담당.
 * 기본 구현 {@link NoopLootService}.
 */
public interface LootService {

    /** looter 한 명 기준으로 테이블을 굴린 결과 (지급하지 않음). ctx null = 솔로·서버 난이도. */
    List<ItemStack> roll(String tableId, Player looter, InstanceContext ctx);

    /**
     * 개인 루팅: looters 각자 따로 굴려서 그 사람에게만 보이는 드롭(또는 인벤토리)으로 준다.
     * 골드(테이블 gold)도 각자 지급. {@code ItemObtainEvent} 발생.
     * @param source drop | elite | boss | chest
     */
    void drop(String tableId, Collection<Player> looters, Location location, InstanceContext ctx, String source);
}
