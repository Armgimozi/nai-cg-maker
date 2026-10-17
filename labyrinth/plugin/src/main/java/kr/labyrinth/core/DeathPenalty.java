package kr.labyrinth.core;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.BundleContents;
import io.papermc.paper.datacomponent.item.ItemContainerContents;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
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
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.TranslatableComponent;
import org.bukkit.NamespacedKey;
import org.bukkit.Tag;
import org.bukkit.entity.Player;
import org.bukkit.inventory.CraftingInventory;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.persistence.PersistentDataType;

/**
 * 죽음 페널티 — 실제 적용 (규칙은 {@link DeathPenaltyRules}). 0.3.6.1 에 생기고 0.3.6.2 에 장비 보호 · 셜커 상자 규칙 · 골드를 더함.
 * <ul>
 *   <li>미궁 공략 중 쓰러짐: {@code dungeon.Run#onMemberDeath} → {@link #onDungeonDown} (경험치 + 가방 칸 + 골드, 안내는 바로 — 미궁은 부활 화면이 없다).
 *       쓰러질 때 한 번 — 이미 쓰러진(관전) 사람은 다시 오지 않고(DungeonManager 가 살아 있을 때만 부름), 전멸에 더 잃는 것은 없다.</li>
 *   <li>그 밖의 진짜 죽음: {@link DeathKeep} MONITOR → {@link #onRealDeath} (경험치만, 안내는 부활한 뒤)</li>
 * </ul>
 * 토템·부활 아이템으로 살아나면 죽음 이벤트가 없으므로 아무것도 잃지 않는다.
 */
public final class DeathPenalty {

    private DeathPenalty() {}

    /** = {@code items.EquipmentListener.LAB_ARROW} (미궁 활 무한 화살). */
    private static final NamespacedKey LAB_ARROW = Keys.key("lab_arrow");
    /** PlayerData ext: 미궁 첫 입장 안내를 본 판 (0.3.6.1 = true, 0.3.6.2 = 2). */
    static final String NOTICE_FLAG = "death.penalty_notice";
    /** 안내 판. 규칙이 바뀌면 올린다 — 0.3.6.2 에 장비 보호·골드가 생겨 0.3.6.1 안내를 본 사람에게도 한 번 더. */
    static final int NOTICE_VERSION = 2;

    /**
     * 미궁 공략 중 쓰러짐. 실패해도 쓰러짐 처리는 그대로 이어지게 예외를 삼킨다.
     * 순서: 열린 창 정리 → 칸 고르기·이름 (여기서 실패하면 아무것도 안 지움) → 잃을 경험치·골드 셈 → 콘솔 기록 → 경험치·골드 빼기
     * → 물건 지우기 → 가방에 못 넣었던 커서 물건 넣기 → 채팅.
     * 기록을 바꾸기 앞에 남겨, 중간에 무슨 일이 나도 서버장이 콘솔을 보고 되돌려 줄 수 있게 한다.
     */
    public static void onDungeonDown(Services s, Player p, boolean adminTest) {
        List<ItemStack> over = List.of();
        try {
            Config c = s.settings().deathPenalty();
            Plan plan = DeathPenaltyRules.plan(c, Where.DUNGEON_RUN, adminTest);
            if (!plan.any()) return;
            List<Pick> picks = List.of();
            if (plan.destroySlots()) {
                try {
                    over = settleLoose(s, p, c);
                    picks = pick(s, p, c, ThreadLocalRandom.current());
                } catch (Throwable t) {
                    Log.error("죽음 페널티 칸 고르기 실패 — 물건은 안 지움 (" + p.getName() + ")", t);
                    picks = List.of();
                }
            }
            PlayerData d = s.data().get(p);
            long xp = plan.resetXp() ? xpToLose(s, d) : 0;
            long goldBefore = d.gold();
            long gold = plan.loseGold() ? DeathPenaltyRules.goldLost(goldBefore, c.gold(), ThreadLocalRandom.current()) : 0;
            List<Lost> lost = new ArrayList<>(picks.size());
            List<String> ids = new ArrayList<>(picks.size());
            for (Pick k : picks) {
                lost.addAll(k.lost());
                ids.add(k.log());
            }
            log(p, "미궁", ids, xp, gold, goldBefore);
            apply(s, p, d, xp, gold);
            remove(p, picks);
            List<ItemStack> rest = over;
            over = List.of();
            putBack(s, p, rest);
            for (String line : DeathPenaltyRules.lines(lost, gold, xp)) Text.send(p, line);
        } catch (Throwable t) {
            Log.error("죽음 페널티 처리 실패 (" + p.getName() + ")", t);
        } finally {
            // 중간에 실패해도 커서에서 떼어 둔 물건은 돌려준다
            if (!over.isEmpty()) {
                try {
                    putBack(s, p, over);
                } catch (Throwable t) {
                    Log.error("죽음 페널티 커서 물건 돌려주기 실패 (" + p.getName() + ")", t);
                }
            }
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
            PlayerData d = s.data().get(p);
            long xp = xpToLose(s, d);
            log(p, labyrinthWorld ? "미궁 월드" : p.getWorld().getName(), List.of(), xp, 0, d.gold());
            apply(s, p, d, xp, 0);
            return DeathPenaltyRules.lines(List.of(), xp);
        } catch (Throwable t) {
            Log.error("죽음 페널티 처리 실패 (" + p.getName() + ")", t);
            return List.of();
        }
    }

    /** 미궁에 처음 들어갈 때 한 번 (dungeon.Run#begin). 규칙이 바뀐 판({@link #NOTICE_VERSION})마다 한 번 더. */
    public static void noticeOnce(Services s, Player p, boolean adminTest) {
        if (adminTest) return;
        try {
            String msg = DeathPenaltyRules.notice(s.settings().deathPenalty());
            if (msg == null) return;
            PlayerData d = s.data().get(p);
            if (noticeSeen(d.ext().get(NOTICE_FLAG))) return;
            d.ext().put(NOTICE_FLAG, NOTICE_VERSION);
            d.markDirty();
            Text.send(p, msg);
        } catch (Throwable t) {
            Log.error("죽음 페널티 안내 실패 (" + p.getName() + ")", t);
        }
    }

    /** 지금 판 안내를 봤나 (0.3.6.1 의 true 는 예전 판). */
    static boolean noticeSeen(Object flag) {
        return flag instanceof Number n && n.intValue() >= NOTICE_VERSION;
    }

    /** 잃을 경험치 = 이번 레벨에서 모은 만큼 (최고 레벨이거나 0 이면 0). 아직 안 뺌. */
    static long xpToLose(Services s, PlayerData d) {
        return DeathPenaltyRules.xpLost(d.level(), d.xp(), s.levels().maxLevel());
    }

    /** 경험치를 0 으로 · 골드를 뺀다 (0 아래로 내려가지 않음). */
    private static void apply(Services s, Player p, PlayerData d, long xp, long gold) {
        if (xp <= 0 && gold <= 0) return;
        if (xp > 0) d.xp(0);
        if (gold > 0) d.gold(Math.max(0, d.gold() - gold));
        d.markDirty();
        try {
            s.hud().refresh(p);
        } catch (Throwable ignored) {
            // HUD 는 다음 갱신 때
        }
    }

    /**
     * 뽑힌 한 칸: 칸 번호 (36 = 보조손) · 그 칸에 남길 것 (null = 비움, 셜커 상자면 장비만 남은 상자) · 채팅 줄 · 콘솔 기록
     * (id×개수 (보이던 이름), 상자면 "shulker_box 속 [id×개수, …]").
     */
    record Pick(int slot, ItemStack after, List<Lost> lost, String log) {}

    /**
     * 열린 창 정리: 커서·제작 칸(2×2, 3×3)의 물건을 떼어 창을 닫고, 장비·상자부터 가방에 넣는다. 그러면 그 물건도 같은 규칙으로 고른다.
     * 바닐라처럼 창을 그냥 닫으면 가방이 꽉 찼을 때 발밑에 떨어져, 혼자 전멸하면 미궁과 함께 사라진다 (장비도).
     *
     * @return 가방에 아직 못 넣은 것 (장비 먼저) — 칸을 지운 뒤 {@link #putBack}
     */
    static List<ItemStack> settleLoose(Services s, Player p, Config c) {
        List<ItemStack> loose = new ArrayList<>();
        List<ItemStack> over = new ArrayList<>();
        int done = 0;
        try {
            // 비운 다음에 담는다 — 중간에 실패해도 같은 물건이 두 번 생기지 않게
            InventoryView view = p.getOpenInventory();
            ItemStack cursor = p.getItemOnCursor().clone();
            if (!cursor.isEmpty()) {
                p.setItemOnCursor(null);
                loose.add(cursor);
            }
            if (view.getTopInventory() instanceof CraftingInventory grid) {
                List<ItemStack> in = new ArrayList<>();
                ItemStack[] m = grid.getMatrix();
                for (ItemStack it : m) if (it != null && !it.isEmpty()) in.add(it.clone());
                if (!in.isEmpty()) {
                    grid.setMatrix(new ItemStack[m.length]);
                    loose.addAll(in);
                }
            }
            p.closeInventory();
            Stacks box = new Stacks(s, c);
            loose.sort(Comparator.comparing((ItemStack it) -> !DeathPenaltyRules.mustReturn(it, box))); // 장비·상자 먼저
            PlayerInventory inv = p.getInventory();
            for (; done < loose.size(); done++) over.addAll(inv.addItem(loose.get(done)).values());
            return over;
        } catch (Throwable t) {
            over.addAll(loose.subList(Math.min(done, loose.size()), loose.size()));
            putBack(s, p, over);
            throw t;
        }
    }

    /** 가방에 넣고, 그래도 자리가 없으면 바닐라처럼 발밑에 떨군다 (콘솔에 남김). */
    static void putBack(Services s, Player p, List<ItemStack> items) {
        for (ItemStack it : items) {
            if (it == null || it.isEmpty()) continue;
            for (ItemStack left : p.getInventory().addItem(it).values()) {
                p.getWorld().dropItem(p.getLocation(), left);
                Log.info("[죽음 페널티] " + p.getName() + " 가방이 꽉 차 커서 물건을 발밑에 떨굼: "
                        + logEntry(idOf(s, left), left.getAmount(), shownName(left, isLab(s, left))));
            }
        }
    }

    /**
     * 지울 칸 고르기 (아직 안 지움). 열린 창은 {@link #settleLoose} 가 먼저 정리한다.
     * 장비·열쇠 같은 안전한 것, 빈 셜커 상자·장비만 든 상자는 후보가 아니다 ({@link DeathPenaltyRules#losable}).
     * 손에 든 칸 · 보조손은 상자일 때만 ({@link DeathPenaltyRules#eligible}).
     */
    static List<Pick> pick(Services s, Player p, Config c, RandomGenerator rng) {
        PlayerInventory inv = p.getInventory();
        ItemStack[] slots = Arrays.copyOf(inv.getStorageContents(), DeathPenaltyRules.CANDIDATE_SLOTS);
        slots[DeathPenaltyRules.OFFHAND] = inv.getItemInOffHand();
        Stacks box = new Stacks(s, c);
        boolean[] eligible = DeathPenaltyRules.eligible(slots, inv.getHeldItemSlot(), box);
        int[] picked = DeathPenaltyRules.pickSlots(eligible, -1, c.slotsMin(), c.slotsMax(), rng);
        List<Pick> out = new ArrayList<>(picked.length);
        for (int slot : picked) {
            ItemStack it = slots[slot];
            List<ItemStack> gone = new ArrayList<>();
            ItemStack after = DeathPenaltyRules.strip(it, box, gone);
            if (gone.isEmpty()) continue;
            String boxName = after == null ? null : nameOf(it, isLab(s, it));
            List<Lost> lost = new ArrayList<>(gone.size());
            List<String> logs = new ArrayList<>(gone.size());
            for (ItemStack g : gone) {
                boolean lab = isLab(s, g);
                lost.add(new Lost(nameOf(g, lab), g.getAmount(), boxName));
                logs.add(logEntry(idOf(s, g), g.getAmount(), shownName(g, lab)));
            }
            String log = after == null ? logs.get(0) : idOf(s, it) + " 속 [" + String.join(", ", logs) + "]";
            out.add(new Pick(slot, after, lost, log));
        }
        return out;
    }

    private static boolean isLab(Services s, ItemStack it) { return s.items().defOf(it).isPresent(); }

    /** 콘솔 기록 한 칸: id×개수 (보이던 이름 — 강화 +N · 모루 이름 포함). 이름이 없거나 id 와 같으면 id×개수만. */
    static String logEntry(String id, int amount, String shown) {
        String n = shown == null ? "" : shown.strip();
        return id + "×" + amount + (n.isEmpty() || n.equalsIgnoreCase(id) ? "" : " (" + n + ")");
    }

    /** 보이는 이름 글 그대로 (모루 이름 · 미궁 아이템 이름). 이름 없는 바닐라 아이템은 "". */
    private static String shownName(ItemStack it, boolean labItem) {
        try {
            Component custom = it.getData(DataComponentTypes.CUSTOM_NAME);
            Component c = custom != null ? custom : labItem ? it.effectiveName() : null;
            return c == null ? "" : Text.plain(c);
        } catch (Throwable t) {
            return "";
        }
    }

    /** 고른 칸 지우기 — 떨구지 않는다. 셜커 상자는 장비만 남긴 상자로 바꾼다. 후보 36번 = 보조손. */
    private static void remove(Player p, List<Pick> picks) {
        PlayerInventory inv = p.getInventory();
        for (Pick k : picks) {
            if (k.slot() == DeathPenaltyRules.OFFHAND) inv.setItemInOffHand(k.after());
            else inv.setItem(k.slot(), k.after());
        }
    }

    /**
     * 상자 규칙이 ItemStack 을 보는 법. 담는 물건 = 셜커 상자(CONTAINER, 비었어도) · 꾸러미(BUNDLE_CONTENTS).
     * 셜커 상자는 자리를 지키고 지운 자리는 빈 칸, 꾸러미는 빈 것을 뺀다 (꾸러미는 빈 아이템을 받지 않는다).
     */
    static final class Stacks implements DeathPenaltyRules.Box<ItemStack> {
        private final Services services;
        private final Config config;

        Stacks(Services services, Config config) {
            this.services = services;
            this.config = config;
        }

        @Override
        public boolean empty(ItemStack it) { return it == null || it.isEmpty(); }

        @Override
        public boolean keep(ItemStack it) { return safe(services, it, config); }

        @Override
        public List<ItemStack> contents(ItemStack it) {
            if (empty(it)) return null;
            ItemContainerContents box = it.getData(DataComponentTypes.CONTAINER);
            if (box != null) return new ArrayList<>(box.contents());
            BundleContents bundle = it.getData(DataComponentTypes.BUNDLE_CONTENTS);
            if (bundle != null) return new ArrayList<>(bundle.contents());
            if (Tag.SHULKER_BOXES.isTagged(it.getType())) return new ArrayList<>(); // 빈 셜커 상자 (자료 없음)
            return null;
        }

        @Override
        public ItemStack withContents(ItemStack it, List<ItemStack> contents) {
            ItemStack copy = it.clone();
            if (it.getData(DataComponentTypes.BUNDLE_CONTENTS) != null && it.getData(DataComponentTypes.CONTAINER) == null) {
                List<ItemStack> in = new ArrayList<>(contents.size());
                for (ItemStack c : contents) if (!empty(c)) in.add(c);
                copy.setData(DataComponentTypes.BUNDLE_CONTENTS, BundleContents.bundleContents(in));
            } else {
                List<ItemStack> in = new ArrayList<>(contents.size());
                for (ItemStack c : contents) in.add(c == null ? ItemStack.empty() : c);
                copy.setData(DataComponentTypes.CONTAINER, ItemContainerContents.containerContents(in));
            }
            return copy;
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

    /**
     * 채팅용 이름: 모루로 붙인 이름 · 미궁 아이템 이름("+3 회랑 수비대 장검", "도안: …")은 보이는 글 그대로,
     * 이름 없는 바닐라 아이템은 {@code <lang:…>} 로 받는 사람 언어 (plain 으로 펴면 서버 영어 "Bread" 가 된다).
     */
    static String nameOf(ItemStack it, boolean labItem) {
        Component custom = it.getData(DataComponentTypes.CUSTOM_NAME);
        Component c = custom != null ? custom : labItem ? it.effectiveName() : null;
        String plain = c == null ? "" : Text.plain(c);
        return plain.isBlank() ? "<lang:" + vanillaKey(it) + ">" : Text.escape(plain);
    }

    /**
     * 바닐라 이름 키. {@code translationKey()} 는 아이템 종류 키라 물약·화살·수상한 스튜가 모두 "물약"·"화살" 이 되므로,
     * 보이는 이름이 인자 없는 번역 글이면 그 키를 쓴다 (예: item.minecraft.potion.effect.healing = "치유의 물약").
     */
    static String vanillaKey(ItemStack it) {
        try {
            String k = translatableKey(it.effectiveName());
            if (k != null) return k;
        } catch (Throwable ignored) {
            // 아래 기본 키
        }
        return it.translationKey();
    }

    /**
     * 이름 글의 번역 키 (인자 없는 번역 글일 때만, 아니면 null). Paper {@code effectiveName()} 은 빈 글에 희귀도 색을 입히고
     * 그 안에 진짜 이름을 하나 붙인 모양({@code getStyledHoverName}: "" + [translate …])이라, 빈 껍데기는 벗겨 본다.
     */
    static String translatableKey(Component c) {
        for (int depth = 0; c != null && depth < 4; depth++) {
            if (c instanceof TranslatableComponent t) {
                return t.arguments().isEmpty() && t.children().isEmpty() && !t.key().isBlank() ? t.key() : null;
            }
            if (c instanceof TextComponent tc && tc.content().isEmpty() && tc.children().size() == 1) {
                c = tc.children().get(0);
                continue;
            }
            return null;
        }
        return null;
    }

    /** 콘솔 한 줄: "[죽음 페널티] 이름 (곳) 잃은 물건 … · 골드 -N (보유 A → B) · 경험치 -N". 잃은 것이 없으면 안 남긴다. */
    private static void log(Player p, String where, List<String> ids, long xp, long gold, long goldBefore) {
        String line = logLine(p.getName(), where, ids, xp, gold, goldBefore);
        if (line != null) Log.info(line);
    }

    static String logLine(String name, String where, List<String> ids, long xp, long gold, long goldBefore) {
        if (ids.isEmpty() && xp <= 0 && gold <= 0) return null;
        return "[죽음 페널티] " + name + " (" + where + ")" + (ids.isEmpty() ? "" : " 잃은 물건 " + String.join(", ", ids))
                + (gold > 0 ? " · 골드 -" + gold + " (보유 " + goldBefore + " → " + Math.max(0, goldBefore - gold) + ")" : "")
                + (xp > 0 ? " · 경험치 -" + xp : "");
    }
}
