package kr.labyrinth.homes;

import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 집 구역 (0.3.7) — 다른 패키지가 부르는 입구 ({@code services.homes()}). 소유: 묶음 B (구현 {@link HomesService}).
 * 기본 구현 {@link NoopHomesApi} = 집 기능 없음 (아무것도 막지 않음).
 * <p>
 * 바꿀 때는 <b>더하기만</b> 한다 (default 메서드). 묶음 A (구역 기계) 는 구역 쪽 메서드를, 묶음 C (메뉴·명령) 는 일 메서드를 부른다.
 * <p>
 * zone 값: 집터 {@link PlotGeom#key()} (1 이상, 높이 창 안) · {@link #ZONE_PROTECTED} (마을·광산·집 구역 보호 상자) · {@link #ZONE_OUTSIDE} (그 밖).
 */
public interface HomesApi {

    int ZONE_PROTECTED = 0;
    int ZONE_OUTSIDE = -1;

    // ── 상태 ─────────────────────────────────────────────────────────────

    /** config homes.enabled. */
    boolean enabled();

    /** 집 구역이 지어졌는가 (구역 기록 state built). */
    boolean districtBuilt();

    /** 그 월드에서 지형 잠금이 켜져 있는가 (주 월드만 · auto = terrain_lock 이고 구역 built · on · off). */
    boolean isTerrainLocked(World world);

    // ── 자리 ─────────────────────────────────────────────────────────────

    /** (x, y, z) 가 들어 있는 집터 (높이 창 안 · 구역 집터와 convert 집터, 없으면 null). */
    PlotGeom plotAt(World world, int x, int y, int z);

    default PlotGeom plotAt(Location l) {
        return l == null || l.getWorld() == null ? null : plotAt(l.getWorld(), l.getBlockX(), l.getBlockY(), l.getBlockZ());
    }

    /** id ("1".."10", "c1" …) 로 (없으면 null). */
    PlotGeom plot(String id);

    /** 모든 집터 (구역 + convert), 번호 차례. */
    List<PlotGeom> plots();

    /** zone 값 (위 설명). */
    int zone(World world, int x, int y, int z);

    // ── 사람 ─────────────────────────────────────────────────────────────

    /** 주인 (빈 집이면 null). */
    UUID ownerOf(PlotGeom plot);

    /** 그 사람의 집 (없으면 null). */
    PlotGeom homeOf(UUID player);

    /** 그 집터에서 그 사람의 자리. */
    PlotRole roleIn(Player player, PlotGeom plot);

    /** 소유 기록 (빈 집도 — {@link PlotInfo#vacant()}). */
    PlotInfo info(PlotGeom plot);

    /** 그 블록을 부수거나 놓을 수 있나 — 집터 권한 · 보호 상자 · 지형 잠금 · 이사 기간 · 크리에이티브 관리자를 모두 본 최종 판단. */
    boolean canBuild(Player player, Block block);

    /** 그 블록(상자류)을 열 수 있나 — 집 안은 주인·초대만, 집 밖 옛 상자는 열림. */
    boolean canOpen(Player player, Block block);

    // ── 일 (묶음 C 의 메뉴·명령이 부름) ──────────────────────────────────

    /** 받기 (plotId null = 아무 데나). */
    HomesResult claim(Player player, String plotId);

    /** 비우기 (confirmed false = 확인 안내만). */
    HomesResult vacate(Player player, boolean confirmed);

    HomesResult invite(Player owner, String name);

    HomesResult kick(Player owner, String name);

    HomesResult rename(Player owner, String name);

    HomesResult setGuests(Player owner, boolean allow);

    /** 맡긴 짐 (ready 만, 보기용 복사본). */
    List<ItemStack> parcel(UUID player);

    /** 맡긴 짐 모두 받기 (가방이 차면 남은 것은 그대로). */
    HomesResult takeParcel(Player player);

    // ── 구역 (묶음 A 의 구역 기계가 부름) ────────────────────────────────

    /** 구역 기록을 읽었거나 지었거나 지웠다 ({@link HomesDistrict#publish}). */
    void districtChanged(HomesDistrict district);

    /** 주인이 있는 집 수 (district remove homes 가 묻는다 — review R9). */
    int ownedCount();

    /** 모든 집을 회수해 맡긴 짐으로 (district remove homes force, R9). 끝나면 회수한 집 수. */
    CompletableFuture<Integer> reclaimAll(CommandSender by, String why);

    /** 집 구역 블록을 되돌린 뒤: 소유·색인을 지우고 잠금을 auto 로 (R9). */
    void districtRemoved();

    // ── 메뉴 (묶음 C 의 {@link HomesUi} 로 넘김) ─────────────────────────

    /** 관리인 메뉴 (NPC estate · interact estate · /미궁 집 · 메인 메뉴 "집"). npcs.yml 정의가 없어도 열린다 (R20). */
    void openEstate(Player player);

    /** 대문 표지판 우클릭 (interact plot:&lt;id&gt;) — 그 집터 메뉴. */
    void openPlotSign(Player player, String plotId);

    // ── 자가 진단 ────────────────────────────────────────────────────────

    /** "[집터 자가 진단] …" (묶음 B) + "[집 메뉴 자가 진단] …" (묶음 C) 줄들. village selftest · /labadmin plot selftest 가 붙인다. */
    List<String> selfTestLines();
}
