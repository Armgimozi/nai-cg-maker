package kr.labyrinth.mine;

import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.World;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/** 안전한 기본 구현: 광산 꺼짐. Q1 MineModule 이 교체한다. */
public class NoopMineApi implements MineApi {

    @Override
    public boolean enabled() { return false; }

    @Override
    public boolean isMineWorld(World world) {
        return world != null && MineNames.WORLD.equals(world.getName());
    }

    @Override
    public void openLift(Player player) { closed(player, "openLift"); }

    @Override
    public void openOffice(Player player) { closed(player, "openOffice"); }

    @Override
    public void openInfo(Player player) { closed(player, "openInfo"); }

    @Override
    public ItemStack applyPickaxe(ItemStack stack, ItemDef def) { return stack; }

    private static void closed(Player player, String what) {
        Log.notImplemented("MineApi." + what);
        if (player != null) Text.error(player, "광산이 아직 열리지 않았습니다.");
    }
}
