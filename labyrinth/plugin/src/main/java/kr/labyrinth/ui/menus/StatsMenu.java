package kr.labyrinth.ui.menus;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.core.ArmorLooks;
import kr.labyrinth.items.LookText;
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
            case STR -> "물리 공격력 +1%/점 · 넉백 저항";
            case DEX -> "공격 속도 +0.5% · 치명 +0.25%p · 회피 +0.1%p /점";
            case INT -> "마법 공격력 +1%/점 · 최대 MP +3 · 재사용 −0.2% (최대 20%)";
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
        der.add("<gray>공격력 <white>물리 " + Text.num(s.weaponDamage() * s.physicalPower()) + " · 마법 "
                + Text.num(s.weaponDamage() * s.magicPower()) + " <dark_gray>(손에 든 무기 한 방)");
        der.add("<gray>공격 속도 <white>초당 " + perSecond(s.attacksPerSecond()) + "회 <dark_gray>(+" + Text.pct(s.attackSpeed())
                + ")  <gray>스킬 위력 <white>" + Text.num(s.skillPower()));
        der.add("<gray>최대 HP <#ff5f6d>" + Text.num(s.maxHp()) + "  <gray>최대 MP <#6fc3ff>" + Text.num(s.maxMp()));
        der.add("<gray>방어 <white>" + Text.num(s.defense()) + "  <gray>피해 감소 <white>" + Text.pct(s.damageReduction()));
        der.add("<gray>치명타 <white>" + Text.pct(s.critChance()) + " <gray>× <white>" + String.format("%.2f", s.critDamage()));
        der.add("<gray>회피 <white>" + Text.pct(s.evasion()) + "  <gray>재사용 감소 <white>" + Text.pct(s.cooldownReduction())
                + (Math.abs(s.cooldownMult() - 1) > 1e-9 ? "  <gray>재사용 대기 <white>×" + String.format(java.util.Locale.ROOT, "%.2f", s.cooldownMult()) : ""));
        der.add("<gray>스킬 피해 <white>+" + Text.pct(s.skillDamage()) + "  <gray>치유량 <white>+" + Text.pct(s.healPower()));
        der.add("<gray>이동 속도 <white>" + signedPct(s.moveSpeed()));
        der.add("<gray>경험치 <white>+" + Text.pct(s.xpBonus()) + "  <gray>골드 <white>+" + Text.pct(s.goldBonus()));
        kr.labyrinth.pvp.PvpConfig pc = services.targets().pvpConfig();
        if (pc.enabled()) {
            // PvP 강인함·PvP 체력 (pvp_spec §4·§16) — 다른 플레이어에게 맞을 때만
            int lv = services.data().get(p).level();
            double res = kr.labyrinth.pvp.PvpMath.resilience(pc, s.stat(Stat.VIT), s.defense(), lv);
            double buffer = kr.labyrinth.pvp.PvpMath.bufferHp(pc, lv);
            der.add("<gray>PvP 강인함 <white>" + Text.pct(res) + "  <gray>PvP 체력 <white>" + Text.num(s.maxHp() + buffer)
                    + " <dark_gray>(최대 HP + " + Text.num(buffer) + ")");
        }
        deco(22, Button.icon(Material.BOOK, "<#7fd8ff><b>능력치 요약</b>", der));
        drawLook(p, s);

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

    /**
     * 겉모습 칸 (look_spec §6.2): "겉모습 판금 4 · 방패 1 → 버팀" + 지금 받는 숨은 효과 합. 가죽 4부위면 구르기 켜기/끄기 단추.
     */
    private void drawLook(Player p, DerivedStats s) {
        ArmorLooks cfg = services.settings().armorLooks();
        int shield = Math.max(0, s.lookCount(ArmorLook.HEAVY) - s.bodyLooks().getOrDefault(ArmorLook.HEAVY, 0));
        String line = lookSummary(cfg, s.bodyLooks(), shield, s.fullLook());
        List<String> lore = new ArrayList<>();
        lore.add(line);
        if (!cfg.enabled()) {
            lore.add("<dark_gray>이 서버는 겉모습 효과를 껐습니다");
        } else {
            for (ArmorLook l : ArmorLook.REAL) {
                int n = s.lookCount(l);
                if (n <= 0) continue;
                lore.add("<" + cfg.color(l) + ">" + cfg.name(l) + " " + n + "<gray>: " + pieceText(cfg.look(l), n));
            }
            if (s.fullLook() != null) {
                lore.add("<" + cfg.color(s.fullLook()) + ">4부위 · " + cfg.fullName(s.fullLook()) + "<gray> — " + fullText(cfg, s.fullLook()));
            }
        }
        deco(31, Button.icon(Material.LEATHER_CHESTPLATE, "<#c9a46a><b>겉모습</b>", lore));
        if (cfg.enabled() && s.full(ArmorLook.LIGHT)) {
            PlayerData d = services.data().get(p);
            boolean off = d.tumbleOff();
            set(40, Button.icon(off ? Material.GRAY_DYE : Material.RABBIT_FOOT,
                    (off ? "<gray>" : "<#c9a46a>") + "<b>" + cfg.tumble().name() + " " + (off ? "꺼짐" : "켜짐") + "</b>",
                    List.of("<gray>웅크리기 두 번 → 구르며 피함", "<#ffd36b>클릭: " + (off ? "켜기" : "끄기"))), ctx -> {
                PlayerData dd = services.data().get(ctx.player());
                dd.tumbleOff(!dd.tumbleOff());
                click(ctx.player());
                refresh();
            });
        }
    }

    /** "겉모습 판금 4 · 방패 1 → 버팀" · "겉모습 판금 2 · 가죽 2" · "겉모습 없음". */
    public static String lookSummary(ArmorLooks cfg, java.util.Map<ArmorLook, Integer> body, int shield, ArmorLook full) {
        List<String> parts = new ArrayList<>();
        for (ArmorLook l : ArmorLook.REAL) {
            int n = body.getOrDefault(l, 0);
            if (n > 0) parts.add(cfg.name(l) + " " + n);
        }
        int any = body.getOrDefault(ArmorLook.ANY, 0);
        if (any > 0) parts.add("왕관 " + any);
        if (shield > 0) parts.add("방패 " + shield);
        if (parts.isEmpty()) return "<gray>겉모습 없음";
        return "<gray>겉모습 <white>" + String.join(" · ", parts) + (full != null ? " <gray>→ <white>" + cfg.fullName(full) : "");
    }

    /** 숨은 효과 합 한 줄 ("방어 +16% · 받는 피해 −2% · 이동 속도 −8% …") — 툴팁과 같은 글 ({@link LookText}). */
    static String pieceText(ArmorLooks.Look look, int n) { return LookText.sum(look, n); }

    static String fullText(ArmorLooks cfg, ArmorLook l) { return LookText.fullText(cfg, l); }

    /** 부호 붙인 퍼센트 ("+4%" · "−8%"). */
    public static String signedPct(double v) { return LookText.signedPct(v); }

    /** 초당 횟수 — 소수 한 자리 ("1.5"). */
    static String perSecond(double v) {
        return String.format(java.util.Locale.ROOT, "%.1f", Math.max(0, v));
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
