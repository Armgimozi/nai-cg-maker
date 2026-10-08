package kr.souls.bonfire;

import kr.souls.Souls;
import kr.souls.skill.Combat;
import kr.souls.world.TestRoom;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.inventory.EquipmentSlot;

/**
 * 시험 방 화톳불 (4.1): 지도의 화톳불 (M2) 이 생기기 전에 레벨 올리기를 해 보는 곳. 시험 방 (TestRoom 판 3) 의 첫 자리 동쪽 6칸에
 * 켜진 캠프파이어 블록 하나. 우클릭하면 쉰다: HP·스태미나를 채우고 (앉기는 M2) 휴식 창을 띄운다.
 * 물체 (Interaction) 를 두지 않고 블록 우클릭 (PlayerInteractEvent RIGHT_CLICK_BLOCK) 을 받는다: 저장하지 않는 물체는 청크가 내려가면
 * 사라지고 다시 켜도 생기지 않아 (1.21.11 에는 스폰 청크가 없다) 말없이 안 듣게 될 수 있었다 (검토 T20). Protection 이 블록 쓰기를
 * 막아도 이벤트는 온다. 손마다 오므로 주손만 듣는다.
 * 가는 법: 접속하면 시험 방 첫 자리에 서므로 오른쪽 (동쪽) 으로 여섯 걸음, 또는 /souls tp room. 시험 모드 /soulstest rest 는 같은 창.
 */
public final class TestBonfire implements Listener {
    private final Souls plugin;

    public TestBonfire(Souls plugin) {
        this.plugin = plugin;
    }

    /** 화톳불 블록 자리 (세계가 없으면 null). */
    public Location where() {
        World w = plugin.worlds().world();
        if (w == null) return null;
        int[] c = plugin.worlds().roomCenter();
        return TestRoom.bonfire(w, c[0], c[1], c[2]);
    }

    @EventHandler(priority = EventPriority.NORMAL)
    public void onInteract(PlayerInteractEvent e) {
        if (e.getAction() != Action.RIGHT_CLICK_BLOCK || e.getHand() != EquipmentSlot.HAND) return;
        Block b = e.getClickedBlock();
        Location at = where();
        if (b == null || at == null || !b.getWorld().equals(at.getWorld()) || b.getX() != at.getBlockX() || b.getY() != at.getBlockY()
                || b.getZ() != at.getBlockZ()) {
            return;
        }
        Player p = e.getPlayer();
        e.setCancelled(true);
        if (plugin.start().unborn(p)) return; // StartFlow 가 출신 창을 다시 띄운다
        rest(p);
    }

    /** 쉰다: HP·스태미나를 채우고 휴식 창. */
    public void rest(Player p) {
        p.setHealth(Combat.maxHealth(p));
        p.setFireTicks(0);
        plugin.stamina().refill(p);
        plugin.profiles().save(p, false);
        plugin.test(p, "REST shown t=" + plugin.ticker().now());
        RestMenu.show(plugin, p);
    }
}
