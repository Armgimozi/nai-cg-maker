package kr.souls.item;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.BlocksAttacks;
import io.papermc.paper.datacomponent.item.UseEffects;
import io.papermc.paper.datacomponent.item.blocksattacks.DamageReduction;
import io.papermc.paper.datacomponent.item.blocksattacks.ItemDamageFunction;
import io.papermc.paper.registry.keys.tags.DamageTypeTagKeys;
import kr.souls.Keys;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextColor;
import org.bukkit.Material;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

import java.util.Locale;

/**
 * 데이터 성분을 붙이는 곳은 여기 한 곳이다 (9.8). 데이터 성분 API 는 1.21.11 에서도 실험 기능이라
 * Paper 빌드를 132 로 고정하고, 바뀌면 이 파일만 고친다.
 * M0 에는 막기 성분 서버 시험용 도구만 있다.
 */
@SuppressWarnings("UnstableApiUsage")
public final class ItemFactory {
    /** 시험용 막기 도구의 껍데기. 검 태그가 없고 우클릭 동작이 없는 바닐라 아이템 (9.8 후보). */
    public static final Material SHELL = Material.FLINT;

    /** 막기 시험의 세 가지 판. */
    public enum GuardTest {
        /** 설계 기본: 빈 감소표 + #bypasses_shield. generic 피해가 그대로 들어와야 한다 */
        EMPTY,
        /** 대조군: 바닐라 방패처럼 다 막는 감소표, 우회 없음. 피해가 0 이어야 한다 (시험이 막기를 알아보는지) */
        CONTROL,
        /** 다 막는 감소표 + #bypasses_shield. 우회가 먹으면 피해가 그대로 들어온다 */
        BYPASS;

        public static GuardTest parse(String s) {
            try {
                return valueOf(s.toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                return null;
            }
        }
    }

    private ItemFactory() {}

    /**
     * 막기 성분 (3.4). 막기 계산은 모두 플러그인이 한다. 바닐라 성분은 막는 자세, using_item 모델, 걸음 느려짐에만 쓴다.
     * 감소표는 늘 비워 둔다 (비어 있지 않으면 바닐라가 피해를 한 번 더 깎고, 내구도를 깎고, 공격자를 민다).
     * bypassedBy 는 #minecraft:bypasses_shield (generic 이 들어 있다), disableCooldownScale 은 0.
     */
    public static BlocksAttacks.Builder guardComponent() {
        return BlocksAttacks.blocksAttacks()
                .blockDelaySeconds(0f)
                .disableCooldownScale(0f)
                .bypassedBy(DamageTypeTagKeys.BYPASSES_SHIELD);
    }

    /** 막는 동안 걸음 배율 (2.3.9). 달리기는 없다. */
    public static UseEffects.Builder guardUse(float speed) {
        return UseEffects.useEffects().canSprint(false).interactVibrations(false).speedMultiplier(speed);
    }

    public static ItemStack testGuard(GuardTest kind) {
        ItemStack it = ItemStack.of(SHELL);
        BlocksAttacks.Builder ba = switch (kind) {
            case EMPTY -> guardComponent();
            case CONTROL -> BlocksAttacks.blocksAttacks().blockDelaySeconds(0f).disableCooldownScale(0f)
                    .addDamageReduction(DamageReduction.damageReduction().base(0f).factor(1f).horizontalBlockingAngle(90f).build())
                    .itemDamage(ItemDamageFunction.itemDamageFunction().threshold(1f).base(0f).factor(1f).build());
            case BYPASS -> guardComponent()
                    .addDamageReduction(DamageReduction.damageReduction().base(0f).factor(1f).horizontalBlockingAngle(90f).build())
                    .itemDamage(ItemDamageFunction.itemDamageFunction().threshold(1f).base(0f).factor(1f).build());
        };
        it.setData(DataComponentTypes.BLOCKS_ATTACKS, ba);
        it.setData(DataComponentTypes.USE_EFFECTS, guardUse(0.55f));
        // 내구도가 깎이는지 보려고 붙인다. 깎이는 아이템은 묶음이 될 수 없다
        it.setData(DataComponentTypes.MAX_STACK_SIZE, 1);
        it.setData(DataComponentTypes.MAX_DAMAGE, 100);
        it.setData(DataComponentTypes.DAMAGE, 0);
        it.setData(DataComponentTypes.ITEM_NAME, Component.text("시험 막기 · " + kind.name().toLowerCase(Locale.ROOT), TextColor.color(0x8f8164)));
        it.editPersistentDataContainer(pdc -> pdc.set(Keys.ITEM, PersistentDataType.STRING, "test_guard_" + kind.name().toLowerCase(Locale.ROOT)));
        return it;
    }

    /** 이 아이템이 시험 막기 도구인가. */
    public static boolean isTestGuard(ItemStack it) {
        String id = kr.souls.util.Items.tag(it, Keys.ITEM);
        return id != null && id.startsWith("test_guard_");
    }
}
