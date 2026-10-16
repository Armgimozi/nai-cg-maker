package kr.labyrinth.core;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ThreadLocalRandom;
import java.util.random.RandomGenerator;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.DeathPenaltyRules.Config;
import kr.labyrinth.core.DeathPenaltyRules.Lost;
import kr.labyrinth.core.DeathPenaltyRules.Plan;
import kr.labyrinth.core.DeathPenaltyRules.Where;
import kr.labyrinth.data.PlayerData;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TranslatableComponent;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.persistence.PersistentDataType;

/**
 * 0.3.6.1 죽음 페널티 — 실제 적용 (규칙은 {@link DeathPenaltyRules}).
 * <ul>
 *   <li>미궁 공략 중 쓰러짐: {@code dungeon.Run#onMemberDeath} → {@link #onDungeonDown} (경험치 + 가방 칸, 안내는 바로 — 미궁은 부활 화면이 없다)</li>
 *   <li>그 밖의 진짜 죽음: {@link DeathKeep} MONITOR → {@link #onRealDeath} (경험치만, 안내는 부활한 뒤)</li>
 * </ul>
 * 토템·부활 아이템으로 살아나면 죽음 이벤트가 없으므로 아무것도 잃지 않는다.
 */
public final class DeathPenalty {

    private DeathPenalty() {}

    /** = {@code items.EquipmentListener.LAB_ARROW} (미궁 활 무한 화살). */
    private static final NamespacedKey LAB_ARROW = Keys.key("lab_arrow");
    /** PlayerData ext: 미궁 첫 입장 안내를 봤는지. */
    static final String NOTICE_FLAG = "death.penalty_notice";

    /** 미궁 공략 중 쓰러짐. 실패해도 쓰러짐 처리는 그대로 이어지게 예외를 삼킨다. */
    public static void onDungeonDown(Services s, Player p, boolean adminTest) {
        try {
            Config c = s.settings().deathPenalty();
            Plan plan = DeathPenaltyRules.plan(c, Where.DUNGEON_RUN, adminTest);
            if (!plan.any()) return;
            List<Lost> lost = new ArrayList<>();
            List<String> ids = new ArrayList<>();
            if (plan.destroySlots()) destroySlots(s, p, c, ThreadLocalRandom.current(), lost, ids);
            long xp = plan.resetXp() ? resetXp(s, p) : 0;
            for (String line : DeathPenaltyRules.lines(lost, xp)) Text.send(p, line);
            log(p, "미궁", ids, xp);
        } catch (Throwable t) {
            Log.error("죽음 페널티 처리 실패 (" + p.getName() + ")", t);
        }
    }

    /**
     * 취소되지 않은 죽음 (미궁 밖, 또는 미궁 월드의 공략 밖). 경험치만 — 소지품은 DeathKeep/바닐라 규칙대로.
     *
     * @return 부활한 뒤 보낼 채팅 줄 (없으면 빈 목록)
     */
    public static List<String> onRealDeath(Services s, Player p, boolean labyrinthWorld) {
        try {
            Plan plan = DeathPenaltyRules.plan(s.settings().deathPenalty(),
                    labyrinthWorld ? Where.LABYRINTH_WORLD : Where.OUTSIDE, false);
            if (!plan.resetXp()) return List.of();
            long xp = resetXp(s, p);
            log(p, labyrinthWorld ? "미궁 월드" : p.getWorld().getName(), List.of(), xp);
            return DeathPenaltyRules.lines(List.of(), xp);
        } catch (Throwable t) {
            Log.error("죽음 페널티 처리 실패 (" + p.getName() + ")", t);
            return List.of();
        }
    }

    /** 미궁에 처음 들어갈 때 한 번 (dungeon.Run#begin). */
    public static void noticeOnce(Services s, Player p, boolean adminTest) {
        if (adminTest) return;
        try {
            String msg = DeathPenaltyRules.notice(s.settings().deathPenalty());
            if (msg == null) return;
            PlayerData d = s.data().get(p);
            if (Boolean.TRUE.equals(d.ext().get(NOTICE_FLAG))) return;
            d.ext().put(NOTICE_FLAG, true);
            d.markDirty();
            Text.send(p, msg);
        } catch (Throwable t) {
            Log.error("죽음 페널티 안내 실패 (" + p.getName() + ")", t);
        }
    }

    /** 이번 레벨 경험치를 0 으로. @return 잃은 양 (최고 레벨이거나 0 이면 0) */
    static long resetXp(Services s, Player p) {
        PlayerData d = s.data().get(p);
        long lost = DeathPenaltyRules.xpLost(d.level(), d.xp(), s.levels().maxLevel());
        if (lost <= 0) return 0;
        d.xp(0);
        d.markDirty();
        try {
            s.hud().refresh(p);
        } catch (Throwable ignored) {
            // HUD 는 다음 갱신 때
        }
        return lost;
    }

    /** 가방 칸 지우기. 열린 창(판매 바구니·커서·2×2 제작 칸)을 먼저 닫아 그 물건도 가방으로 돌려놓고 같은 규칙으로 고른다. */
    static void destroySlots(Services s, Player p, Config c, RandomGenerator rng, List<Lost> lost, List<String> ids) {
        p.closeInventory();
        PlayerInventory inv = p.getInventory();
        ItemStack[] storage = inv.getStorageContents();
        boolean[] eligible = new boolean[storage.length];
        for (int i = 0; i < storage.length; i++) {
            ItemStack it = storage[i];
            eligible[i] = it != null && !it.isEmpty() && !safe(s, it, c);
        }
        int[] slots = DeathPenaltyRules.pickSlots(eligible, inv.getHeldItemSlot(), c.slotsMin(), c.slotsMax(), rng);
        for (int slot : slots) {
            ItemStack it = storage[slot];
            lost.add(new Lost(nameOf(it), it.getAmount()));
            ids.add(idOf(s, it) + "×" + it.getAmount());
            inv.setItem(slot, null);
        }
    }

    static boolean safe(Services s, ItemStack it, Config c) {
        ItemDef def = s.items().defOf(it).orElse(null);
        boolean arrow = it.getPersistentDataContainer().has(LAB_ARROW, PersistentDataType.BYTE);
        return DeathPenaltyRules.alwaysSafe(def == null ? null : def.type(), idOf(def, it), arrow, c.safeItems());
    }

    private static String idOf(Services s, ItemStack it) {
        return idOf(s.items().defOf(it).orElse(null), it);
    }

    private static String idOf(ItemDef def, ItemStack it) {
        return def != null ? def.id() : it.getType().getKey().getKey().toLowerCase(Locale.ROOT);
    }

    /** 채팅용 이름: 보이는 이름 그대로 (미궁 아이템 = "+3 회랑 수비대 장검" 같은 이름), 이름 없는 바닐라 아이템은 받는 사람 언어로. */
    static String nameOf(ItemStack it) {
        Component c = it.effectiveName();
        if (c instanceof TranslatableComponent t && t.children().isEmpty()) return "<lang:" + t.key() + ">";
        String plain = Text.plain(c);
        return plain.isBlank() ? "<lang:" + it.translationKey() + ">" : Text.escape(plain);
    }

    private static void log(Player p, String where, List<String> ids, long xp) {
        if (ids.isEmpty() && xp <= 0) return;
        Log.info("[죽음 페널티] " + p.getName() + " (" + where + ")" + (ids.isEmpty() ? "" : " 잃은 물건 " + String.join(", ", ids))
                + (xp > 0 ? " · 경험치 -" + xp : ""));
    }
}
