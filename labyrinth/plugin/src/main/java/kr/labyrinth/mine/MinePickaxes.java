package kr.labyrinth.mine;

import io.papermc.paper.block.BlockPredicate;
import io.papermc.paper.datacomponent.DataComponentType;
import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.ItemAdventurePredicate;
import io.papermc.paper.datacomponent.item.ItemAttributeModifiers;
import io.papermc.paper.datacomponent.item.Tool;
import io.papermc.paper.datacomponent.item.TooltipDisplay;
import io.papermc.paper.registry.RegistryKey;
import io.papermc.paper.registry.TypedKey;
import io.papermc.paper.registry.set.RegistrySet;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.ToolSpec;
import kr.labyrinth.core.Log;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.util.TriState;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.block.BlockType;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

/**
 * 곡괭이 구성요소 ({@link MineApi#applyPickaxe}, 계약 §2.6) — {@link PickaxePlan} 대로:
 * Tool 규칙(블록마다 speed, correct_for_drops TRUE, 그 밖 1.0, 내구 0) · CAN_BREAK (tier + 1 이하 광석·보석 블록, 0.3.6.1) · UNBREAKABLE ·
 * 공격 속성 비움 · 한 칸 1개 · 바탕 PAPER · TOOLTIP_DISPLAY 로 바닐라 줄 숨김 · PDC 지문(블록 설정이 바뀌면 접속 때 다시 씀).
 */
final class MinePickaxes {

    static final List<DataComponentType> HIDDEN = List.of(DataComponentTypes.TOOL, DataComponentTypes.CAN_BREAK,
            DataComponentTypes.UNBREAKABLE, DataComponentTypes.ATTRIBUTE_MODIFIERS);

    private final MineModule module;
    final NamespacedKey sigKey = new NamespacedKey(kr.labyrinth.core.Keys.NS, MineNames.PDC_TOOL_SIG);
    private final Map<String, Double> hardness = new HashMap<>();

    MinePickaxes(MineModule module) { this.module = module; }

    double hardness(String blockKey) {
        return hardness.computeIfAbsent(blockKey, k -> {
            Material m = Material.matchMaterial(k);
            return m == null ? 0.0 : (double) m.getHardness();
        });
    }

    PickaxePlan plan(ToolSpec tool) {
        return PickaxePlan.of(tool, module.mineDef(), this::hardness);
    }

    /** 곡괭이면 구성요소를 쓴 아이템 (PAPER 바탕이 아니면 PAPER 로 바꾼 사본), 아니면 그대로. */
    ItemStack apply(ItemStack stack, ItemDef def) {
        if (stack == null || def == null || !def.isTool()) return stack;
        return apply(stack, def.tool());
    }

    ItemStack apply(ItemStack stack, ToolSpec tool) {
        PickaxePlan plan = plan(tool);
        if (plan == null) return stack;
        ItemStack s = stack.getType() == Material.PAPER ? stack : stack.withType(Material.PAPER);
        try {
            Tool.Builder tb = Tool.tool().defaultMiningSpeed(PickaxePlan.DEFAULT_SPEED).damagePerBlock(PickaxePlan.DAMAGE_PER_BLOCK)
                    .canDestroyBlocksInCreative(true);
            List<TypedKey<BlockType>> can = new ArrayList<>();
            for (PickaxePlan.Rule r : plan.rules()) {
                TypedKey<BlockType> k = TypedKey.create(RegistryKey.BLOCK, Key.key(r.block()));
                can.add(k);
                tb.addRule(Tool.rule(RegistrySet.keySet(RegistryKey.BLOCK, k), r.speed(), TriState.TRUE));
            }
            s.setData(DataComponentTypes.TOOL, tb.build());
            ItemAdventurePredicate.Builder pb = ItemAdventurePredicate.itemAdventurePredicate();
            if (!can.isEmpty()) pb.addPredicate(BlockPredicate.predicate().blocks(RegistrySet.keySet(RegistryKey.BLOCK, can)).build());
            s.setData(DataComponentTypes.CAN_BREAK, pb.build());
        } catch (Throwable t) {
            Log.warnOnce("mine-tool", "[광산] 곡괭이 Tool·CAN_BREAK 를 쓰지 못했습니다: " + t);
        }
        if (PickaxePlan.UNBREAKABLE) s.setData(DataComponentTypes.UNBREAKABLE);
        s.setData(DataComponentTypes.ATTRIBUTE_MODIFIERS, ItemAttributeModifiers.itemAttributes().build());
        s.setData(DataComponentTypes.MAX_STACK_SIZE, 1);
        TooltipDisplay old = s.getData(DataComponentTypes.TOOLTIP_DISPLAY);
        TooltipDisplay.Builder tip = TooltipDisplay.tooltipDisplay();
        if (old != null) {
            tip.hideTooltip(old.hideTooltip());
            tip.hiddenComponents(old.hiddenComponents());
        }
        for (DataComponentType t : HIDDEN) {
            if (old == null || !old.hiddenComponents().contains(t)) tip.addHiddenComponents(t);
        }
        s.setData(DataComponentTypes.TOOLTIP_DISPLAY, tip.build());
        s.editPersistentDataContainer(pdc -> pdc.set(sigKey, PersistentDataType.STRING, plan.signature()));
        return s;
    }

    /** 아이템 구성요소가 계획과 같은가 (자가 진단 tool_mismatch). 다르면 그 이유, 같으면 null. */
    String mismatch(ItemStack s, ToolSpec tool) {
        PickaxePlan plan = plan(tool);
        if (plan == null) return "곡괭이 계획 없음";
        if (s == null) return "아이템 없음";
        if (s.getType() != Material.PAPER) return "바탕이 PAPER 아님 (" + s.getType() + ")";
        Tool t = s.getData(DataComponentTypes.TOOL);
        if (t == null) return "Tool 구성요소 없음";
        if (t.rules().size() != plan.rules().size()) return "Tool 규칙 " + t.rules().size() + " ≠ " + plan.rules().size();
        for (int i = 0; i < plan.rules().size(); i++) {
            Tool.Rule r = t.rules().get(i);
            PickaxePlan.Rule want = plan.rules().get(i);
            if (Math.abs(r.speed() - want.speed()) > 1e-4) return want.node() + " speed " + r.speed() + " ≠ " + want.speed();
            if (r.correctForDrops() != TriState.TRUE) return want.node() + " correct_for_drops ≠ TRUE";
        }
        ItemAdventurePredicate can = s.getData(DataComponentTypes.CAN_BREAK);
        if (can == null) return "CAN_BREAK 없음";
        int blocks = 0;
        for (BlockPredicate p : can.predicates()) if (p.blocks() != null) blocks += p.blocks().size();
        if (blocks != plan.canBreak().size()) return "CAN_BREAK 블록 " + blocks + " ≠ " + plan.canBreak().size();
        if (!s.hasData(DataComponentTypes.UNBREAKABLE)) return "UNBREAKABLE 없음";
        Integer max = s.getData(DataComponentTypes.MAX_STACK_SIZE);
        if (max == null || max != 1) return "한 칸 최대 ≠ 1";
        return null;
    }

    /** 가방의 곡괭이 중 지문이 지금 블록 설정과 다른 것을 다시 쓴다 (접속·광산 들어올 때). */
    int refresh(Player p) {
        MineDef mine = module.mineDef();
        if (mine == null || mine.isEmpty()) return 0;
        int n = 0;
        ItemStack[] items = p.getInventory().getContents();
        for (int i = 0; i < items.length; i++) {
            ItemStack it = items[i];
            if (it == null || it.getType().isAir()) continue;
            ItemDef def = module.services().items().defOf(it).orElse(null);
            if (def == null || !def.isTool()) continue;
            PickaxePlan plan = plan(def.tool());
            if (plan == null) continue;
            String sig = it.getPersistentDataContainer().get(sigKey, PersistentDataType.STRING);
            if (plan.signature().equals(sig) && it.getType() == Material.PAPER) continue;
            p.getInventory().setItem(i, apply(it, def));
            n++;
        }
        return n;
    }
}
