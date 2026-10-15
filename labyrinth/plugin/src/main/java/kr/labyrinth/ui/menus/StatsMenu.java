package kr.labyrinth.ui.menus;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.DerivedStats;
import kr.labyrinth.stats.Stat;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * /스탯 — 스탯 분배: 스탯마다 [아이콘 / +1 / +5 / 전부], 파생 능력치 요약, 초기화(첫 1회 무료, 이후 망각의 주문서 1장).
 */
public final class StatsMenu extends LabMenu {

    private static final Stat[] ORDER = {Stat.STR, Stat.DEX, Stat.INT, Stat.VIT, Stat.WIS, Stat.LUK};
    private static final int[] COLS = {1, 2, 3, 5, 6, 7};
    public static final String FREE_RESET_KEY = "ui.free_stat_reset_used";
    static final String RESET_ITEM = "stat_reset_scroll";

    private long resetArmedUntil;

    public StatsMenu(Services services) {
        super(services, "stats", 6, "<#ffd84f>스탯 분배");
    }

    static String emblem(Stat s) {
        return switch (s) {
            case STR -> "berserker_emblem";
            case DEX -> "hunter_emblem";
            case INT -> "arcanist_emblem";
            case VIT -> "guardian_emblem";
            case WIS -> "priest_emblem";
            case LUK -> "shadow_emblem";
        };
    }

    static String effect(Stat s) {
        return switch (s) {
            case STR -> "근접 공격력 · 방어 관통";
            case DEX -> "원거리 공격력 · 공격 속도 · 회피";
            case INT -> "마법 공격력 · 최대 MP · 스킬 피해";
            case VIT -> "최대 HP · 방어력 · HP 재생";
            case WIS -> "마나 재생 · 치유량 · 해로운 효과 지속 감소";
            case LUK -> "치명타 확률 · 드롭률 · 골드";
        };
    }

    @Override
    protected void draw(Player p) {
        PlayerData d = services.data().get(p);
        DerivedStats s = services.stats().get(p);
        int pts = d.statPoints();
        deco(4, Button.icon(pts > 0 ? Material.NETHER_STAR : Material.FIREWORK_STAR, (pts > 0 ? "<#7fe07f>" : "<gray>") + "남은 포인트 <b>" + pts + "</b>",
                List.of("<gray>Lv.1 에 " + services.settings().level().startPoints() + " 포인트, 레벨이 오를 때마다 "
                        + services.settings().level().pointsPerLevel() + " 포인트",
                        "<gray>현재 레벨 <#ffd84f>" + d.level())));
        for (int i = 0; i < ORDER.length; i++) {
            Stat st = ORDER[i];
            int col = COLS[i];
            int total = s.stat(st);
            int inv = d.allocated(st);
            List<String> lore = new ArrayList<>();
            lore.add("<gray>현재 <white>" + total + "</white> <dark_gray>(투자 " + inv + " · 기본/장비 " + (total - inv) + ")");
            lore.add("<" + st.color() + ">▸ " + effect(st));
            ItemStack icon = model(emblem(st), Material.PAPER, "<" + st.color() + "><b>" + st.displayName() + "</b> <gray>" + st.name(), lore);
            deco(9 + col, icon);
            final Stat stat = st;
            set(18 + col, plus(st, 1, pts), ctx -> allocate(ctx.player(), stat, 1));
            set(27 + col, plus(st, 5, pts), ctx -> allocate(ctx.player(), stat, 5));
            set(36 + col, plus(st, -1, pts), ctx -> allocate(ctx.player(), stat, Math.max(1, services.data().get(ctx.player()).statPoints())));
        }
        // 파생 능력치
        List<String> der = new ArrayList<>();
        der.add("<gray>공격력 <white>" + Text.num(s.attackPower()) + "  <gray>무기 <white>" + Text.num(s.weaponDamage()));
        der.add("<gray>최대 HP <#ff5f6d>" + Text.num(s.maxHp()) + "  <gray>최대 MP <#6fc3ff>" + Text.num(s.maxMp()));
        der.add("<gray>방어 <white>" + Text.num(s.defense()) + "  <gray>피해 감소 <white>" + Text.pct(s.damageReduction()));
        der.add("<gray>치명타 <white>" + Text.pct(s.critChance()) + " <gray>× <white>" + String.format("%.2f", s.critDamage()));
        der.add("<gray>회피 <white>" + Text.pct(s.evasion()) + "  <gray>재사용 감소 <white>" + Text.pct(s.cooldownReduction()));
        der.add("<gray>스킬 피해 <white>+" + Text.pct(s.skillDamage()) + "  <gray>치유량 <white>+" + Text.pct(s.healPower()));
        der.add("<gray>공격 속도 <white>+" + Text.pct(s.attackSpeed()) + "  <gray>이동 속도 <white>+" + Text.pct(s.moveSpeed()));
        der.add("<gray>경험치 <white>+" + Text.pct(s.xpBonus()) + "  <gray>골드 <white>+" + Text.pct(s.goldBonus()));
        deco(22, Button.icon(Material.BOOK, "<#7fd8ff><b>능력치 요약</b>", der));

        boolean free = services.data().get(p).counter(FREE_RESET_KEY) == 0;
        boolean armed = System.currentTimeMillis() < resetArmedUntil;
        List<String> rl = new ArrayList<>();
        rl.add("<gray>투자한 포인트를 모두 돌려받습니다.");
        rl.add(free ? "<#7fe07f>첫 초기화는 무료!" : "<gray>필요: <white>망각의 주문서 1장 <dark_gray>(상인에게서 구입)");
        rl.add("");
        rl.add(armed ? "<#ff6b6b><b>한 번 더 클릭하면 초기화합니다</b>" : "<#ffd36b>클릭: 초기화");
        set(49, UiTheme.glint(model(RESET_ITEM, Material.PAPER, (armed ? "<#ff6b6b>" : "<#c79bff>") + "<b>스탯 초기화</b>", rl), armed),
                ctx -> reset(ctx.player()));
        backButton(45, MainMenu::reopen);
    }

    private ItemStack plus(Stat st, int amount, int pts) {
        boolean can = pts > 0;
        String label = amount < 0 ? "전부" : "+" + amount;
        Material m = !can ? Material.GRAY_DYE : amount == 1 ? Material.LIME_DYE : amount == 5 ? Material.GREEN_DYE : Material.EMERALD;
        return Button.icon(m, (can ? "<" + st.color() + ">" : "<dark_gray>") + st.displayName() + " " + label,
                List.of(can ? "<gray>클릭하여 투자" : "<dark_gray>남은 포인트가 없습니다"));
    }

    private void allocate(Player p, Stat st, int amount) {
        PlayerData d = services.data().get(p);
        int n = Math.min(amount, d.statPoints());
        if (n <= 0 || !d.allocate(st, n)) {
            deny(p);
            return;
        }
        services.stats().recalc(p);
        services.hud().refresh(p);
        ok(p);
        refresh();
    }

    private void reset(Player p) {
        long now = System.currentTimeMillis();
        if (now >= resetArmedUntil) {
            resetArmedUntil = now + 5000;
            click(p);
            refresh();
            return;
        }
        resetArmedUntil = 0;
        PlayerData d = services.data().get(p);
        int invested = 0;
        for (Stat s : Stat.values()) invested += d.allocated(s);
        if (invested <= 0) {
            Text.error(p, "되돌릴 포인트가 없습니다.");
            deny(p);
            refresh();
            return;
        }
        boolean free = d.counter(FREE_RESET_KEY) == 0;
        if (!free && !takeItem(p, RESET_ITEM)) {
            Text.error(p, "망각의 주문서가 필요합니다. <gray>(떠돌이 상인 핀에게서 살 수 있습니다)");
            deny(p);
            refresh();
            return;
        }
        if (free) d.counter(FREE_RESET_KEY, 1);
        int back = d.resetAllocation();
        services.stats().recalc(p);
        services.hud().refresh(p);
        Text.send(p, "<#c79bff>스탯을 초기화했습니다.</#c79bff> <gray>포인트 <white>" + back + "</white> 반환");
        p.playSound(p.getLocation(), org.bukkit.Sound.BLOCK_ENCHANTMENT_TABLE_USE, 0.8f, 1.2f);
        refresh();
    }

    private boolean takeItem(Player p, String id) {
        ItemStack[] contents = p.getInventory().getContents();
        for (int i = 0; i < contents.length; i++) {
            ItemStack s = contents[i];
            if (s == null || s.isEmpty()) continue;
            if (services.items().defOf(s).map(def -> def.id().equals(id)).orElse(false)) {
                s.setAmount(s.getAmount() - 1);
                p.getInventory().setItem(i, s.getAmount() <= 0 ? null : s);
                return true;
            }
        }
        return false;
    }
}
