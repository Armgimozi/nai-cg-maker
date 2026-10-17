package kr.labyrinth.homes;

import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import kr.labyrinth.core.Text;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/** 안전한 기본 구현: 집 기능 없음 — 아무것도 막지 않고, 메뉴는 안내만. {@link HomesModule} 이 {@link HomesService} 로 바꾼다. 소유: 묶음 B. */
public class NoopHomesApi implements HomesApi {

    @Override
    public boolean enabled() { return false; }

    @Override
    public boolean districtBuilt() { return false; }

    @Override
    public boolean isTerrainLocked(World world) { return false; }

    @Override
    public PlotGeom plotAt(World world, int x, int y, int z) { return null; }

    @Override
    public PlotGeom plot(String id) { return null; }

    @Override
    public List<PlotGeom> plots() { return List.of(); }

    @Override
    public int zone(World world, int x, int y, int z) { return ZONE_OUTSIDE; }

    @Override
    public UUID ownerOf(PlotGeom plot) { return null; }

    @Override
    public PlotGeom homeOf(UUID player) { return null; }

    @Override
    public PlotRole roleIn(Player player, PlotGeom plot) { return PlotRole.NONE; }

    @Override
    public PlotInfo info(PlotGeom plot) { return PlotInfo.empty(plot, true); }

    @Override
    public boolean canBuild(Player player, Block block) { return true; }

    @Override
    public boolean canOpen(Player player, Block block) { return true; }

    @Override
    public HomesResult claim(Player player, String plotId) { return off(); }

    @Override
    public HomesResult vacate(Player player, boolean confirmed) { return off(); }

    @Override
    public HomesResult invite(Player owner, String name) { return off(); }

    @Override
    public HomesResult kick(Player owner, String name) { return off(); }

    @Override
    public HomesResult rename(Player owner, String name) { return off(); }

    @Override
    public HomesResult setGuests(Player owner, boolean allow) { return off(); }

    @Override
    public List<ItemStack> parcel(UUID player) { return List.of(); }

    @Override
    public HomesResult takeParcel(Player player) { return off(); }

    @Override
    public void districtChanged(HomesDistrict district) { }

    @Override
    public int ownedCount() { return 0; }

    @Override
    public CompletableFuture<Integer> reclaimAll(CommandSender by, String why) { return CompletableFuture.completedFuture(0); }

    @Override
    public void districtRemoved() { }

    @Override
    public void openEstate(Player player) { if (player != null) Text.error(player, "이 서버에서는 집 기능을 쓰지 않습니다."); }

    @Override
    public void openPlotSign(Player player, String plotId) { openEstate(player); }

    @Override
    public List<String> selfTestLines() { return List.of("[집터 자가 진단] 꺼짐 (homes.enabled: false 또는 집 모듈이 안 켜짐)"); }

    private static HomesResult off() { return HomesResult.fail("이 서버에서는 집 기능을 쓰지 않습니다."); }
}
