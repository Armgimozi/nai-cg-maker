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
    void anythingElseFallsBackToTheItemKey() {
        assertNull(DeathPenalty.translatableKey(null));
        assertNull(DeathPenalty.translatableKey(Component.text("책 제목")), "글 이름 (책 제목 등)");
        assertNull(DeathPenalty.translatableKey(Component.translatable("block.minecraft.player_head.named", Component.text("Vic"))),
                "인자 있는 번역 글");
        assertNull(DeathPenalty.translatableKey(Component.empty().append(Component.translatable("a")).append(Component.translatable("b"))),
                "조각이 둘");
    }
}
