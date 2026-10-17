package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Method;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.junit.jupiter.api.Test;

/**
 * 리스너가 review R4 의 구멍을 모두 듣는가 (이벤트 이름) · 잠금 리스너는 LOW (마을 보호 HIGH 보다 먼저, plan §9 리스너 차례).
 * 핸들러 목록이 따로인 이벤트 (PlayerArmorStandManipulate · PlayerItemFrameChange) 는 따로 들어야 한다 (review §4).
 */
class ListenerCoverageTest {

    private static Map<String, EventPriority> handlers(Class<?> c) {
        Map<String, EventPriority> out = new HashMap<>();
        for (Method m : c.getDeclaredMethods()) {
            EventHandler h = m.getAnnotation(EventHandler.class);
            if (h == null || m.getParameterCount() != 1) continue;
            out.put(m.getParameterTypes()[0].getSimpleName(), h.priority());
        }
        return out;
    }

    @Test
    void terrainLockIsLowAndCoversVillageGaps() {
        Map<String, EventPriority> h = handlers(TerrainLockListener.class);
        for (String ev : List.of("BlockBreakEvent", "BlockPlaceEvent", "PlayerBucketEmptyEvent", "PlayerBucketFillEvent", "PlayerInteractEvent",
                "HangingPlaceEvent", "HangingBreakEvent", "BlockIgniteEvent",
                // 마을 핸들러에 없는 것 (R4 끝 항목)
                "EntityPlaceEvent", "VehicleDestroyEvent", "SignChangeEvent", "PlayerLeashEntityEvent", "PlayerBucketEntityEvent")) {
            assertTrue(h.containsKey(ev), ev);
            assertEquals(EventPriority.LOW, h.get(ev), ev + " 는 LOW");
        }
        assertTrue(h.containsKey("PlayerJoinEvent"), "이사 기간 안내");
    }

    @Test
    void plotRulesCoverEntities() {
        Map<String, EventPriority> h = handlers(PlotRulesListener.class);
        for (String ev : List.of("PlayerInteractEntityEvent", "PlayerArmorStandManipulateEvent", "PlayerItemFrameChangeEvent", "EntityDamageEvent",
                "PlayerShearEntityEvent", "SheepDyeWoolEvent", "PlayerNameEntityEvent", "PlayerFishEvent", "VehicleEnterEvent", "InventoryOpenEvent",
                "PlayerUnleashEntityEvent", "PlayerTakeLecternBookEvent",
                // 한도 (R15 · 틱 부품)
                "BlockPlaceEvent", "HangingPlaceEvent", "EntityPlaceEvent", "EntityBreedEvent", "CreatureSpawnEvent")) {
            assertTrue(h.containsKey(ev), ev);
        }
    }

    @Test
    void crossZoneCoversEdges() {
        Map<String, EventPriority> h = handlers(CrossZoneListener.class);
        for (String ev : List.of("BlockFromToEvent", "BlockPistonExtendEvent", "BlockPistonRetractEvent", "InventoryMoveItemEvent",
                "InventoryPickupItemEvent", "StructureGrowEvent", "BlockFertilizeEvent", "BlockSpreadEvent", "BlockGrowEvent", "BlockBurnEvent",
                "EntityExplodeEvent", "BlockExplodeEvent", "EntityChangeBlockEvent", "EntityBlockFormEvent", "SpongeAbsorbEvent", "BlockDispenseEvent",
                "TNTPrimeEvent", "ItemTransportingEntityValidateTargetEvent", "PortalCreateEvent", "EntityInteractEvent")) {
            assertTrue(h.containsKey(ev), ev);
        }
    }
}
