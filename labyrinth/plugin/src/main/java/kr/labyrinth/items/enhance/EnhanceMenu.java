package kr.labyrinth.items.enhance;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.EnhanceDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.ClickContext;
import kr.labyrinth.ui.Menu;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

/**
 * 강화 창 (GDD §11.13, glyphs.yml menus.enhance 소켓 배치). 장비는 창에 넣지 않고 <b>고르기만</b> 한다 —
 * 아래 내 가방이나 착용 장비 줄(주손·보조손·투구·흉갑·각반·장화)을 클릭하면 그 칸을 기억하고, [강화] 때 그 칸의
 * 아이템을 그 자리에서 고친다(아이템이 창에 머물지 않으니 닫기·튕김으로 잃어버릴 일이 없다).
 * <pre>
 *  4 규칙 · 11 장비 칸 → 13 성공 확률 → 15 [강화] · 22 실패하면
 *  비용 줄(4번째 줄): 골드 · 강화석 · 그 장비 재료(enhance.yml, 3칸 — 보유/필요 ✔/✘) · 보호 주문서(켜기/끄기)
 *    — 자리는 {@link EnhanceLayout}: 배경 소켓(glyphs.yml menus.enhance.slots)을 따른다.
 *      예전 배경(소켓 29·31·33) = 29 골드 · 31 강화석 · 33 주문서 · 재료 30 · 32 · 28, 글리프 끔 = 28 · 29 · 30~32 · 33
 *  37~42 착용 장비 · 43 도움말 · 45 대장간으로 · 49 보유 골드 · 53 닫기
 * </pre>
 * [강화] 버튼 설명에는 언제나(강화할 수 없을 때도) 골드와 비용 줄 전부가 나온다 — 모자란 것(✘)이 먼저.
 */
final class EnhanceMenu extends Menu {

    private static final int S_RULES = 4, S_GEAR = 11, S_CHANCE = 13, S_GO = 15, S_FAIL = 22, S_HELP = 43, S_BACK = 45, S_PURSE = 49,
            S_CLOSE = 53;
    private static final int[] EQUIP_SLOTS = {37, 38, 39, 40, 41, 42};
    private static final String[] EQUIP_NAMES = {"주손", "보조손(방패)", "투구", "흉갑", "각반", "장화"};

    private final Services services;
    private final EnhanceService enhance;
    /** 비용 줄 칸 (골드 · 강화석 · 재료 · 주문서) — 배경 소켓에 맞춘 배치. */
    private final int sGold, sStone, sScroll;
    /** 그 장비 재료 칸 (enhance.yml 순서). 더 많으면 마지막 칸과 [강화] 버튼 설명에 전부 나온다. */
    private final int[] sMats;
    /** 고른 칸 (플레이어 인벤토리 번호, -1 = 없음) + 고를 때의 사본(그 칸이 그대로인지 확인용). */
    private int slot = -1;
    private ItemStack snapshot;
    private boolean protect;
    private boolean busy;

    EnhanceMenu(Services services, EnhanceService enhance, Player viewer) {
        super(6, UiTheme.title("enhance", 6, "<#f3e3bd>장비 강화 — 대장장이 두르간"));
        this.services = services;
        this.enhance = enhance;
        EnhanceLayout layout = enhance.layout();
        this.sGold = layout.gold();
        this.sStone = layout.stone();
        this.sScroll = layout.protection();
        this.sMats = layout.materials();
        // 주손 장비가 강화할 수 있는 것이면 바로 골라 둔다
        int held = viewer.getInventory().getHeldItemSlot();
        ItemStack main = viewer.getInventory().getItem(held);
        if (EnhanceRules.enhanceable(services.items().defOf(main).orElse(null))) select(viewer, held, false);
    }

    @Override
    protected boolean allowBottomClicks() { return true; }

    /** 인벤토리 칸 번호: 주손 = 들고 있는 핫바 칸, 보조손 40, 투구 39, 흉갑 38, 각반 37, 장화 36. */
    private static int equipIndex(Player p, int i) {
        return switch (i) {
            case 0 -> p.getInventory().getHeldItemSlot();
            case 1 -> 40;
            case 2 -> 39;
            case 3 -> 38;
            case 4 -> 37;
            default -> 36;
        };
    }

    private ItemStack current(Player p) {
        if (slot < 0) return null;
        ItemStack cur = p.getInventory().getItem(slot);
        if (cur == null || snapshot == null || !cur.isSimilar(snapshot)) return null;
        return cur;
    }

    /** 칸을 고른다 — 툴팁이 옛 설정으로 그려져 있을 수 있으니 그 자리에서 다시 그린 뒤 사본을 뜬다. */
    private boolean select(Player p, int index, boolean feedback) {
        PlayerInventory inv = p.getInventory();
        ItemStack it = inv.getItem(index);
        ItemDef def = it == null ? null : services.items().defOf(it).orElse(null);
        if (!EnhanceRules.enhanceable(def)) {
            if (feedback) {
                EnhanceService.Problem pr = it == null || it.isEmpty() ? EnhanceService.Problem.NO_ITEM
                        : def == null ? EnhanceService.Problem.VANILLA : EnhanceService.Problem.NOT_ENHANCEABLE;
                services.hud().actionBar(p, Text.mm("<#ff6b6b>" + EnhanceService.message(pr)), 40);
                deny(p);
            }
            return false;
        }
        services.items().refresh(it);
        inv.setItem(index, it);
        slot = index;
        snapshot = inv.getItem(index) == null ? it.clone() : inv.getItem(index).clone();
        if (feedback) p.playSound(p.getLocation(), Sound.ITEM_ARMOR_EQUIP_CHAIN, 0.6f, 1.3f);
        return true;
    }

    @Override
    protected void build(Player viewer) {
        UiTheme.frame(this, "enhance", 6);
        EnhanceRules r = enhance.rules();
        PlayerData d = services.data().get(viewer);
        ItemStack cur = current(viewer);
        if (cur == null) {
            slot = -1;
            snapshot = null;
        }
        EnhanceService.Plan plan = cur == null ? null : enhance.plan(viewer, cur);

        deco(S_RULES, Button.icon(Material.KNOWLEDGE_BOOK, "<#e8d9b0><b>강화 규칙</b>", rulesLore(r)));

        // 장비 칸
        if (cur == null) {
            set(S_GEAR, Button.icon(Material.LIGHT_GRAY_STAINED_GLASS_PANE, "<gray>장비 칸",
                    List.of("<white>아래 가방이나 착용 장비 줄에서", "<white>강화할 장비를 클릭하세요.",
                            "<dark_gray>무기 · 방어구 · 방패 (장신구·바닐라 장비 불가)")), ctx -> deny(ctx.player()));
        } else {
            ItemStack shown = cur.clone();
            set(S_GEAR, shown, ctx -> {
                if (busy) return;
                slot = -1;
                snapshot = null;
                click(ctx.player());
                refresh();
            });
        }

        // 비용 · 확률
        if (plan == null || plan.problem() == EnhanceService.Problem.MAX_LEVEL) {
            String why = plan == null ? "장비를 고르면 보입니다" : "최대 단계 — 더 강화할 수 없습니다";
            deco(sGold, Button.icon(Material.GOLD_NUGGET, "<gray>골드", List.of("<dark_gray>" + why)));
            deco(sStone, Button.icon(Material.AMETHYST_SHARD, "<gray>강화석", List.of("<dark_gray>" + why)));
            deco(sMats[0], Button.icon(Material.BUNDLE, "<gray>장비 재료", List.of("<dark_gray>" + why,
                    "<dark_gray>장비마다 드는 재료가 다릅니다 — 그 장비의 제작 재료,",
                    "<dark_gray>제작법이 없으면 그 장비를 주는 몬스터·보스의 재료.")));
            deco(S_CHANCE, Button.icon(Material.GLASS_BOTTLE, "<gray>성공 확률", List.of("<dark_gray>" + why)));
            deco(S_FAIL, Button.icon(Material.GRAY_DYE, "<gray>실패하면", List.of("<dark_gray>" + why)));
        } else {
            boolean goldOk = d.gold() >= plan.gold();
            deco(sGold, Button.icon(Material.GOLD_INGOT, (goldOk ? "<#ffd27a>✔ " : "<#ff6b6b>✘ ") + "골드 " + Text.num(plan.gold()),
                    List.of("<gray>보유 " + (goldOk ? "<white>" : "<#ff6b6b>") + Text.num(d.gold()),
                            "<dark_gray>장비 레벨·희귀도·단계가 높을수록 비쌉니다.",
                            "<dark_gray>실패해도 돌려받지 못합니다.")));
            EnhanceCost.Check st = plan.stone();
            if (st != null) deco(sStone, costIcon(st, Material.AMETHYST_SHARD, "#c890ff", stoneSourceText(st.line().item())));
            List<EnhanceCost.Check> mats = plan.materials();
            long hiddenMissing = mats.stream().skip(sMats.length).filter(h -> !h.ok()).count();
            for (int k = 0; k < sMats.length && k < mats.size(); k++) {
                EnhanceCost.Check c = mats.get(k);
                String more = k == sMats.length - 1 && mats.size() > sMats.length
                        ? "그 밖에 " + (mats.size() - sMats.length) + "종" + (hiddenMissing > 0 ? " (" + hiddenMissing + "종 모자람)" : "")
                                + " — [강화] 버튼 설명 참고" : null;
                deco(sMats[k], costIcon(c, Material.PAPER, "#e8d9b0", more != null ? more : materialSourceText(c.line().item())));
            }
            if (mats.isEmpty()) {
                deco(sMats[0], Button.icon(Material.LIGHT_GRAY_DYE, "<gray>장비 재료 없음",
                        List.of("<dark_gray>이 장비는 이 단계에 강화석·골드만 듭니다.")));
            }
            String pc = plan.chance() >= 0.999 ? "#7fe07f" : plan.chance() >= 0.5 ? "#c8e07f" : plan.chance() >= 0.3 ? "#ffd27a" : "#ff8a6b";
            String stat = Enhancement.scaledText(plan.def());
            deco(S_CHANCE, Button.icon(plan.chance() >= 0.999 ? Material.EXPERIENCE_BOTTLE : Material.HONEY_BOTTLE,
                    "<" + pc + "><b>성공 확률 " + EnhanceRules.pct(plan.chance()) + "</b>",
                    lines("<gray>성공하면 <white>+" + plan.level() + " → <#ffd36b>+" + plan.target(),
                            "<gray>" + stat + " <white>×" + ItemTooltip.trim(r.multiplier(plan.level())) + " → <#ffd36b>×"
                                    + ItemTooltip.trim(r.multiplier(plan.target())) + " <dark_gray>(이번 단계 +"
                                    + Math.round(r.stepGain(plan.level()) * 100) + "%)",
                            plan.target() < r.maxLevel() ? "<dark_gray>그다음 단계(+" + (plan.target() + 1) + ")는 +"
                                    + Math.round(r.stepGain(plan.target()) * 100) + "% — 높은 단계일수록 상승폭이 커집니다" : null,
                            plan.target() >= r.config().broadcastFrom() ? "<#ffd36b>성공하면 서버 전체에 알려집니다!" : null)));
            boolean guarded = plan.downgrade() && protect && plan.haveScrolls() > 0;
            String failName = !plan.downgrade() ? "<gray>실패하면: <white>+" + plan.level() + " 그대로"
                    : guarded ? "<#7fd8ff>실패하면: +" + plan.level() + " 유지 <gray>(보호 주문서 1장)"
                    : "<#ff6b6b><b>실패하면: +" + (plan.level() - 1) + Enhancement.ro(plan.level() - 1) + " 하락</b>";
            deco(S_FAIL, Button.icon(!plan.downgrade() ? Material.GRAY_DYE : guarded ? Material.LIGHT_BLUE_DYE : Material.RED_DYE,
                    failName, lines("<gray>골드·강화석·재료는 사라집니다.", "<dark_gray>장비가 부서지는 일은 없습니다.",
                            plan.downgrade() && !guarded ? "<#ff8a8a>보호 주문서를 켜면 하락을 막을 수 있습니다." : null)));
        }

        // 보호 주문서
        drawProtection(viewer, r, plan);

        // [강화] 버튼
        drawGo(viewer, plan);

        // 착용 장비 줄
        for (int i = 0; i < EQUIP_SLOTS.length; i++) {
            final int idx = equipIndex(viewer, i);
            ItemStack it = viewer.getInventory().getItem(idx);
            ItemDef def = it == null ? null : services.items().defOf(it).orElse(null);
            if (EnhanceRules.enhanceable(def)) {
                ItemStack icon = it.clone();
                if (idx == slot) UiTheme.glint(icon, true);
                set(EQUIP_SLOTS[i], icon, ctx -> {
                    if (busy) return;
                    if (select(ctx.player(), idx, true)) refresh();
                });
            } else {
                deco(EQUIP_SLOTS[i], Button.icon(Material.LIGHT_GRAY_STAINED_GLASS_PANE, "<gray>" + EQUIP_NAMES[i],
                        List.of(it == null || it.isEmpty() ? "<dark_gray>비어 있음" : "<dark_gray>강화할 수 없는 물건")));
            }
        }
        deco(S_HELP, Button.icon(Material.BOOK, "<#e8d9b0>착용 장비 · 가방",
                List.of("<gray>왼쪽 줄 = 지금 착용한 장비 (클릭하여 고르기)", "<gray>아래 내 가방의 장비를 클릭해도 됩니다.",
                        "<dark_gray>장비는 창에 들어가지 않고 제자리에서 강화됩니다.")));

        set(S_BACK, UiTheme.back(), ctx -> {
            if (busy) return;
            services.crafting().openBlacksmith(ctx.player());
        });
        deco(S_PURSE, Button.icon(Material.GOLD_NUGGET, "<#ffd27a>보유 골드 " + Text.num(d.gold()),
                List.of("<gray>레벨 " + d.level(), "<dark_gray>강화석은 미궁 몬스터·상자·보스에게서, 하급은 떠돌이 상인 핀에게서.",
                        "<dark_gray>장비 재료는 그 장비를 얻는 곳(대장간 재료·몬스터·보스)에서 모읍니다.")));
        set(S_CLOSE, UiTheme.close(), ctx -> ctx.player().closeInventory());
    }

    private void drawProtection(Player viewer, EnhanceRules r, EnhanceService.Plan plan) {
        String id = r.config().protectionItem();
        ItemDef sd = services.content().item(id);
        String name = sd == null ? "보호 주문서" : sd.name();
        int have = enhance.count(viewer, id);
        List<String> lore = new ArrayList<>();
        lore.add("<gray>보유 <white>" + have + "장");
        boolean needed = plan != null && plan.problem() != EnhanceService.Problem.MAX_LEVEL && plan.downgrade();
        if (!needed) {
            lore.add("<dark_gray>지금 단계는 실패해도 내려가지 않아 필요 없습니다.");
            lore.add("<dark_gray>(+" + r.config().downgradeFrom() + " 이상에서 실패하면 한 단계 하락)");
        } else {
            lore.add(protect ? "<#7fd8ff>켜짐 <gray>— 하락할 실패에서 단계를 지키고 주문서 1장만 사라짐"
                    : "<gray>꺼짐 <dark_gray>— 실패하면 한 단계 내려갑니다");
            lore.add("<dark_gray>성공하거나 하락이 없는 실패에는 쓰이지 않습니다.");
            if (have <= 0) lore.add("<#ff8a8a>주문서가 없습니다 — 보스·정예 몬스터가 드물게 떨어뜨립니다.");
            else lore.add("<#ffd27a>▶ 클릭하여 " + (protect ? "끄기" : "켜기"));
        }
        String title = !needed ? "<gray>" + name + " <dark_gray>(필요 없음)"
                : protect && have > 0 ? "<#7fd8ff><b>" + name + ": 사용</b>" : "<gray>" + name + ": 사용 안 함";
        ItemStack icon = UiTheme.item(id, Material.PAPER, title, lore);
        if (have > 0) icon.setAmount(Math.min(64, have));
        UiTheme.glint(icon, needed && protect && have > 0);
        final boolean toggle = needed && have > 0;
        set(sScroll, icon, ctx -> {
            if (busy) return;
            if (!toggle) {
                deny(ctx.player());
                return;
            }
            protect = !protect;
            ctx.player().playSound(ctx.player().getLocation(), protect ? Sound.ITEM_BOOK_PAGE_TURN : Sound.UI_BUTTON_CLICK, 0.7f, 1.2f);
            refresh();
        });
    }

    private void drawGo(Player viewer, EnhanceService.Plan plan) {
        if (busy) {
            deco(S_GO, Button.icon(Material.ANVIL, "<#ffd27a>망치질 중…", List.of()));
            return;
        }
        if (plan == null) {
            set(S_GO, Button.icon(Material.ANVIL, "<gray>[ 강화 ]", List.of("<dark_gray>먼저 장비를 고르세요.")), ctx -> deny(ctx.player()));
            return;
        }
        long purse = services.data().get(viewer).gold();
        if (!plan.ok()) {
            List<String> lore = new ArrayList<>();
            if (plan.cost() != null) {
                // 재료 칸이 모자라 다 못 보여 줄 때도 여기서 전부 보인다 — 모자란 것(✘) 먼저
                lore.add("<gray>+" + plan.level() + " → +" + plan.target() + " · 성공 확률 <white>" + EnhanceRules.pct(plan.chance()));
                lore.addAll(costLines(plan, purse, true));
                lore.add("");
                lore.add("<dark_gray>모두 갖추면 강화할 수 있습니다.");
            }
            set(S_GO, Button.icon(Material.BARRIER, "<#ff6b6b>" + EnhanceService.message(plan.problem()), lore),
                    ctx -> deny(ctx.player()));
            return;
        }
        List<String> lore = new ArrayList<>();
        lore.add("<gray>+" + plan.level() + " → <#ffd36b>+" + plan.target() + " <gray>· 성공 확률 <white>" + EnhanceRules.pct(plan.chance()));
        lore.addAll(costLines(plan, purse, false));
        if (plan.downgrade()) {
            boolean guarded = protect && plan.haveScrolls() > 0;
            lore.add(guarded ? "<#7fd8ff>보호 주문서 사용 — 실패해도 내려가지 않음" : "<#ff8a8a>⚠ 실패하면 한 단계 내려갑니다");
        }
        lore.add("");
        lore.add("<#ffd27a>▶ 클릭하여 강화");
        ItemStack icon = Button.icon(Material.ANVIL, "<gradient:#ffd36b:#ff8a3d><b>[ 강화 ]</b></gradient>", lore);
        UiTheme.glint(icon, true);
        set(S_GO, icon, ctx -> go(ctx.player()));
    }

    private void go(Player p) {
        if (busy) return;
        ItemStack cur = current(p);
        if (cur == null) {
            deny(p);
            refresh();
            return;
        }
        EnhanceService.Result res = enhance.enhance(p, slot, snapshot, protect);
        if (res == null) {
            deny(p);
            refresh();
            return;
        }
        busy = true;
        snapshot = res.item().clone();
        refresh();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            busy = false;
            if (!p.isOnline() || p.getOpenInventory().getTopInventory().getHolder(false) != this) return;
            ItemStack now = slot < 0 ? null : p.getInventory().getItem(slot);
            if (now != null) snapshot = now.clone();
            refresh();
        }, EnhanceService.REVEAL_TICKS + 1);
    }

    @Override
    protected void onBottomClick(ClickContext ctx) {
        if (busy) return;
        Player p = ctx.player();
        ItemStack clicked = ctx.event().getCurrentItem();
        if (clicked == null || clicked.isEmpty()) return;
        if (select(p, ctx.slot(), true)) refresh();
    }

    private List<String> rulesLore(EnhanceRules r) {
        List<String> out = new ArrayList<>();
        StringBuilder sb = new StringBuilder("<gray>");
        int sure = 0;
        while (sure < r.maxLevel() && r.chance(sure + 1) >= 0.999) sure++;
        if (sure > 0) out.add("<gray>+1 ~ +" + sure + ": <#7fe07f>확정 성공");
        for (int t = sure + 1; t <= r.maxLevel(); t++) {
            if (sb.length() > 6) sb.append(" <dark_gray>·</dark_gray> ");
            sb.append("+").append(t).append(" <white>").append(EnhanceRules.pct(r.chance(t))).append("</white>");
            if ((t - sure) % 3 == 0 && t < r.maxLevel()) {
                out.add(sb.toString());
                sb = new StringBuilder("<gray>");
            }
        }
        if (sb.length() > 6) out.add(sb.toString());
        out.add("");
        out.add("<gray>실패하면 골드·강화석·재료가 사라집니다.");
        if (r.config().downgradeFrom() > 0) {
            out.add("<#ff8a8a>+" + r.config().downgradeFrom() + " 이상에서 실패하면 한 단계 하락 <dark_gray>(파괴 없음)");
            out.add("<#7fd8ff>보호 주문서: <gray>하락을 막고 주문서만 사라짐");
        }
        out.add("");
        out.add("<gray>무기 피해 · 방어구 방어·HP 배율 <dark_gray>(높을수록 상승폭이 큼)");
        StringBuilder curve = new StringBuilder("<white>");
        for (int lv = 1; lv <= r.maxLevel(); lv++) {
            curve.append(curve.length() > 7 ? " <dark_gray>·</dark_gray> " : "").append("+").append(lv).append(" ×")
                    .append(ItemTooltip.trim(r.multiplier(lv)));
            if (lv % 4 == 0 && lv < r.maxLevel()) {
                out.add(curve.toString());
                curve = new StringBuilder("<white>");
            }
        }
        if (curve.length() > 7) out.add(curve.toString());
        out.add("");
        out.add("<gray>재료: 강화석 + 그 장비의 제작 재료 <dark_gray>(아래 비용 줄)");
        out.add("<dark_gray>제작법이 없는 장비는 그 장비를 주는 몬스터·보스의 재료");
        String[] label = {"주 재료", "둘째 재료 더", "귀한 재료 더"};
        StringBuilder bands = new StringBuilder("<dark_gray>");
        List<EnhanceDef.Band> bl = services.content().enhance().bands();
        for (int i = 0; i < bl.size(); i++) {
            EnhanceDef.Band b = bl.get(i);
            bands.append(i == 0 ? "" : " · ").append("+").append(b.from()).append("~+").append(b.to()).append(" ")
                    .append(i < label.length ? label[i] : "재료");
        }
        out.add(bands.toString());
        out.add("<dark_gray>보스 고유 장비는 가장 높은 단계에 그 보스의 핵이 듭니다.");
        out.add("<gray>+" + r.config().glintFrom() + " 부터 이름이 빛나고, +" + r.maxLevel() + " 은 특별한 빛을 냅니다.");
        out.add("<gray>+" + r.config().broadcastFrom() + " 이상 성공은 서버 전체에 알려집니다.");
        List<String> stoneNames = new ArrayList<>();
        for (EnhanceRules.Stone s : enhance.rules().config().stones()) {
            ItemDef d = services.content().item(s.item());
            stoneNames.add(d == null ? s.item() : d.name());
        }
        out.add("<dark_gray>" + EnhanceGuide.stoneGuide(stoneNames));
        return out;
    }

    /** 강화석 얻는 곳 (재료라 층을 적는다 — 장비에는 층 글자 없음): "지하 1~3층 몬스터·상자·보스 · 상인". */
    private String stoneSourceText(String stone) {
        boolean shop = services.content().npcs().values().stream().anyMatch(n -> n.shop() != null
                && n.shop().stream().anyMatch(e -> stone.equals(e.item())));
        return EnhanceGuide.stoneSource(enhance.rules().config().stones(), stone, shop);
    }

    /** 비용 한 줄 아이콘: 이름 앞 ✔/✘, 개수 = 필요 개수, 설명 = 보유/필요 + 얻는 곳. */
    private ItemStack costIcon(EnhanceCost.Check c, Material fallback, String okColor, String source) {
        String id = c.line().item();
        ItemDef def = services.content().item(id);
        String name = def == null ? id : def.name();
        ItemStack icon = UiTheme.item(id, fallback, (c.ok() ? "<" + okColor + ">✔ " : "<#ff6b6b>✘ ") + name + " ×" + c.line().amount(),
                lines("<gray>보유 " + (c.ok() ? "<white>" : "<#ff6b6b>") + c.have() + "<gray> / 필요 " + c.line().amount(),
                        c.ok() ? null : "<#ff8a8a>" + (c.line().amount() - c.have()) + "개 모자랍니다.",
                        source == null ? null : "<dark_gray>" + source,
                        "<dark_gray>실패해도 돌려받지 못합니다."));
        icon.setAmount(Math.max(1, Math.min(64, c.line().amount())));
        return icon;
    }

    /** [강화] 버튼 설명의 비용 줄: 골드 + 강화석 + 장비 재료 (missingFirst = 모자란 ✘ 줄을 먼저). */
    private List<String> costLines(EnhanceService.Plan plan, long purse, boolean missingFirst) {
        boolean goldOk = purse >= plan.gold();
        String gold = (goldOk ? "<#7fe07f>✔ <gray>" : "<#ff6b6b>✘ <gray>") + "골드 <white>" + Text.num(plan.gold())
                + " <dark_gray>(보유 " + Text.num(purse) + ")";
        List<String> bad = new ArrayList<>(), good = new ArrayList<>();
        (goldOk || !missingFirst ? good : bad).add(gold);
        for (EnhanceCost.Check c : plan.checks()) (c.ok() || !missingFirst ? good : bad).add(checkLine(c));
        bad.addAll(good);
        return bad;
    }

    /** [강화] 버튼 설명의 비용 한 줄 ("✔ 균사 실 ×3 (보유 5)"). */
    private String checkLine(EnhanceCost.Check c) {
        ItemDef def = services.content().item(c.line().item());
        String name = def == null ? c.line().item() : def.name();
        return (c.ok() ? "<#7fe07f>✔ <gray>" : "<#ff6b6b>✘ <gray>") + name + " <white>×" + c.line().amount()
                + " <dark_gray>(보유 " + c.have() + ")";
    }

    /** 재료를 얻는 곳 (items.yml floor · sources 그대로: "지하 3층 몬스터·정예·상자"). */
    private String materialSourceText(String id) {
        ItemDef d = services.content().item(id);
        if (d == null) return null;
        List<String> src = new ArrayList<>();
        for (String s : d.sources()) {
            String label = switch (s) {
                case "drop" -> "몬스터";
                case "elite" -> "정예";
                case "boss" -> "보스";
                case "chest" -> "상자";
                case "craft" -> "대장간 정제";
                case "shop" -> "상인";
                default -> null;
            };
            if (label != null && !src.contains(label)) src.add(label);
        }
        if (src.isEmpty()) return d.floor() > 0 ? "지하 " + d.floor() + "층" : null;
        return (d.floor() > 0 ? "지하 " + d.floor() + "층 " : "") + String.join("·", src);
    }

    /** 빈(null) 줄을 뺀 설명 목록. */
    private static List<String> lines(String... ls) {
        List<String> out = new ArrayList<>();
        for (String l : ls) if (l != null) out.add(l);
        return out;
    }

    private void click(Player p) { p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.4f, 1.2f); }

    private void deny(Player p) { p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.6f, 0.6f); }
}
