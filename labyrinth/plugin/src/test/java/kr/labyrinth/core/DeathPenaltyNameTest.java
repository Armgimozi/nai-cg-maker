package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.junit.jupiter.api.Test;

/** 0.3.6.1 죽음 페널티 채팅 — 이름 없는 바닐라 물건의 번역 키 (물약은 효과 이름까지). */
class DeathPenaltyNameTest {

    @Test
    void styledHoverNameWrapperIsUnwrapped() {
        // Paper effectiveName() = getStyledHoverName(): 빈 글 + 희귀도 색 + [진짜 이름] 하나
        Component styled = Component.empty().append(Component.translatable("item.minecraft.potion.effect.healing"))
                .color(NamedTextColor.WHITE);
        assertEquals("item.minecraft.potion.effect.healing", DeathPenalty.translatableKey(styled));
        assertEquals("item.minecraft.tipped_arrow.effect.poison",
                DeathPenalty.translatableKey(Component.translatable("item.minecraft.tipped_arrow.effect.poison")));
        assertEquals("block.minecraft.cobblestone",
                DeathPenalty.translatableKey(Component.empty().append(Component.translatable("block.minecraft.cobblestone"))));
    }

    @Test
    void consoleLineKeepsTheShownName() {
        // 서버장이 되돌려 줄 때 강화 단계까지 알 수 있게 (id 만으로는 +N 을 모름)
        assertEquals("guard_longsword×1 (+3 회랑 수비대 장검)", DeathPenalty.logEntry("guard_longsword", 1, " +3 회랑 수비대 장검 "));
        assertEquals("bread×5", DeathPenalty.logEntry("bread", 5, ""), "이름 없는 바닐라 물건");
        assertEquals("bread×5", DeathPenalty.logEntry("bread", 5, null));
        assertEquals("iron_ingot×13 (철 주괴)", DeathPenalty.logEntry("iron_ingot", 13, "철 주괴"));
        assertEquals("stick×1", DeathPenalty.logEntry("stick", 1, "STICK"), "id 와 같은 이름은 빼기");
    }

    @Test
    void anythingElseFallsBackToTheItemKey() {
        assertNull(DeathPenalty.translatableKey(null));
        assertNull(DeathPenalty.translatableKey(Component.text("책 제목")), "글 이름 (책 제목 등)");
        assertNull(DeathPenalty.translatableKey(Component.translatable("block.minecraft.player_head.named", Component.text("Vic"))),
                "인자 있는 번역 글");
        assertNull(DeathPenalty.translatableKey(Component.empty().append(Component.translatable("a")).append(Component.translatable("b"))),
                "조각이 둘");
    }
}
