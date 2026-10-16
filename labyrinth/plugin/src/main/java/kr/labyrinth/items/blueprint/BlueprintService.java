package kr.labyrinth.items.blueprint;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.event.ItemObtainEvent;
import kr.labyrinth.items.GearItemService;
import org.bukkit.Bukkit;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;

/**
 * 도안 (0.3.6 Q6). 희귀 이상 장비 레시피는 도안을 배워야 대장간에서 만든다 ({@link BlueprintRules}).
 * <ul>
 *   <li>도안 우클릭 = 영구히 배움 (한 장 소모). 이미 알면 안내만 하고 아이템은 남는다 — 남에게 주거나 판다.</li>
 *   <li>배운 것 = PlayerData ext {@code blueprints.learned} ({@link BlueprintBook}).</li>
 *   <li>0.3.6 첫 접속: 가방·엔더 상자·장신구 칸에 이미 가진 희귀 이상 장비의 도안은 배운 것으로 (ext {@code blueprints.v036}).</li>
 *   <li>상인 핀: 날마다 바뀌는 희귀 도안 {@code blueprints.shop_count} 개 (mobs/npc/ShopMenu 가 {@link #shopToday} 를 그린다).</li>
 *   <li>관리: /labadmin blueprint give|learn|forget|list.</li>
 * </ul>
 * config.yml {@code blueprints:} 가 없으면 기본값 ({@link BlueprintRules.Settings#DEFAULT}).
 */
public final class BlueprintService implements Listener {

    private static volatile BlueprintService current;

    private final Services services;
    private BlueprintRules.Settings settings = BlueprintRules.Settings.DEFAULT;

    public BlueprintService(Services services) { this.services = services; }

    /** 켜져 있는 서비스 (모듈이 켜지기 전·시험에서는 null). */
    public static BlueprintService get() { return current; }

    public void start() {
        reload();
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        registerCommands();
        current = this;
        for (Player p : Bukkit.getOnlinePlayers()) grandfather(p);
    }

    public void stop() {
        if (current == this) current = null;
    }

    public void reload() {
        settings = settings(services.plugin().getConfig().getConfigurationSection("blueprints"));
    }

    public static BlueprintRules.Settings settings(ConfigurationSection s) {
        BlueprintRules.Settings d = BlueprintRules.Settings.DEFAULT;
        if (s == null) return d;
        return new BlueprintRules.Settings(s.getBoolean("enabled", d.enabled()), s.getInt("shop_count", d.shopCount()),
                s.getInt("shop_price_base", d.shopBase()), s.getInt("shop_price_step", d.shopPerTier()));
    }

    public BlueprintRules.Settings settings() { return settings; }

    /**
     * 도안 잠금이 켜져 있는가: config blueprints.enabled 이고, items.yml 에 blueprint 가 있고, loot.yml 에 도안 항목이 하나라도 있을 때.
     * (손으로 고친 콘텐츠 파일이 자동 갱신되지 않아 도안이 나올 곳이 없으면 잠그지 않는다 — 진행이 막히지 않게.)
     */
    public boolean enabled() {
        if (!settings.enabled()) return false;
        Content c = services.content();
        if (c != checkedContent) {
            checkedContent = c;
            checkedActive = BlueprintRules.active(c);
            if (!checkedActive) Log.warn("[도안] items.yml 의 blueprint 또는 loot.yml 의 도안 항목이 없어 도안 잠금을 끕니다.");
        }
        return checkedActive;
    }

    private Content checkedContent;
    private boolean checkedActive;

    // ── 배우기 ─────────────────────────────────────────────

    public List<String> learned(Player p) { return BlueprintBook.learned(services.data().get(p).ext()); }

    public boolean knows(Player p, String recipeId) { return BlueprintBook.knows(services.data().get(p).ext(), recipeId); }

    /** 이 레시피를 지금 만들 수 있는가 (도안 기준만). */
    public boolean canCraft(Player p, RecipeDef r) {
        return BlueprintRules.canCraft(services.content(), r, enabled(), learned(p));
    }

    /** 이 레시피에 도안이 필요한가 (꺼져 있으면 false). */
    public boolean locked(RecipeDef r) { return enabled() && BlueprintRules.needsBlueprint(services.content(), r); }

    /** @return 새로 배웠으면 true */
    public boolean learn(Player p, String recipeId) {
        PlayerData d = services.data().get(p);
        boolean added = BlueprintBook.learn(d.ext(), recipeId);
        if (added) d.markDirty();
        return added;
    }

    public boolean forget(Player p, String recipeId) {
        PlayerData d = services.data().get(p);
        boolean gone = BlueprintBook.forget(d.ext(), recipeId);
        if (gone) d.markDirty();
        return gone;
    }

    /** 도안 우클릭 = 배우기. */
    @EventHandler(priority = EventPriority.HIGH)
    public void onUse(PlayerInteractEvent e) {
        if (e.getAction() != Action.RIGHT_CLICK_AIR && e.getAction() != Action.RIGHT_CLICK_BLOCK) return;
        ItemStack it = e.getItem();
        if (!BlueprintItems.isBlueprint(it)) return;
        e.setCancelled(true);
        Player p = e.getPlayer();
        String rid = BlueprintItems.recipeOf(it);
        Content c = services.content();
        RecipeDef r = rid == null ? null : c.recipes().get(rid);
        ItemDef d = r == null ? null : c.item(r.result());
        if (d == null) {
            Text.error(p, "알아볼 수 없는 도안입니다.");
            return;
        }
        String name = "<" + d.rarity().color() + ">" + d.name() + "</" + d.rarity().color() + ">";
        if (knows(p, rid)) {
            Text.send(p, "<gray>이미 배운 도안입니다: " + name + " <dark_gray>(남에게 주거나 팔 수 있습니다)");
            p.playSound(p.getLocation(), Sound.ITEM_BOOK_PAGE_TURN, 0.6f, 0.7f);
            return;
        }
        learn(p, rid);
        it.setAmount(it.getAmount() - 1);
        if (e.getHand() == EquipmentSlot.OFF_HAND) p.getInventory().setItemInOffHand(it.getAmount() <= 0 ? null : it);
        else p.getInventory().setItemInMainHand(it.getAmount() <= 0 ? null : it);
        Text.send(p, "<#ffd27a>도안을 배웠습니다:</#ffd27a> " + name);
        p.playSound(p.getLocation(), Sound.ITEM_BOOK_PAGE_TURN, 0.9f, 1.0f);
        p.playSound(p.getLocation(), Sound.BLOCK_ENCHANTMENT_TABLE_USE, 0.6f, 1.3f);
        p.spawnParticle(Particle.ENCHANT, p.getLocation().add(0, 1.2, 0), 30, 0.4, 0.5, 0.4, 0.6);
    }

    // ── 첫 접속 보호 ───────────────────────────────────────

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (p.isOnline()) grandfather(p);
        }, 40L);
    }

    /** 0.3.6 첫 접속 한 번: 이미 가진 희귀 이상 장비의 도안을 배운다. @return 새로 배운 개수 */
    public int grandfather(Player p) {
        PlayerData d = services.data().get(p);
        if (Boolean.TRUE.equals(d.ext().get(BlueprintBook.GRANDFATHER_KEY))) return 0;
        List<String> owned = new ArrayList<>();
        for (ItemStack s : p.getInventory().getContents()) addId(owned, s);
        for (ItemStack s : p.getEnderChest().getContents()) addId(owned, s);
        for (int i = 0; i < PlayerData.ACCESSORY_SLOTS; i++) {
            byte[] b = d.accessory(i);
            if (b == null) continue;
            try {
                addId(owned, ItemStack.deserializeBytes(b));
            } catch (Throwable t) {
                Log.warn("[도안] 장신구 칸 읽기 실패: " + p.getName());
            }
        }
        Set<String> learn = BlueprintRules.grandfather(services.content(), owned);
        int n = BlueprintBook.learnAll(d.ext(), learn);
        d.ext().put(BlueprintBook.GRANDFATHER_KEY, true);
        d.markDirty();
        if (n > 0) {
            Text.send(p, "<#ffd27a>도안이 새로 생겼습니다.</#ffd27a> <gray>가진 장비에 맞는 도안 <white>" + n
                    + "</white>개를 배웠습니다. 희귀 이상 장비는 이제 도안을 배워야 만듭니다.");
            Log.info("[도안] " + p.getName() + " 첫 접속 보호: " + n + "개 배움");
        }
        return n;
    }

    private void addId(List<String> out, ItemStack s) {
        if (s == null || s.isEmpty()) return;
        services.items().defOf(s).ifPresent(def -> out.add(def.id()));
    }

    // ── 주기 · 상인 ────────────────────────────────────────

    /** 도안 amount 장을 준다 (가방이 차면 발밑). @return 준 장 수 */
    public int give(Player p, String recipeId, int amount, String source) {
        ItemStack s = BlueprintItems.create(services, recipeId, Math.max(1, Math.min(16, amount)));
        if (s == null) return 0;
        int n = s.getAmount();
        GearItemService.deliver(p, s);
        ItemDef def = services.content().item(BlueprintRules.ITEM_ID);
        if (def != null) Bukkit.getPluginManager().callEvent(new ItemObtainEvent(p, def, s, source));
        return n;
    }

    /** 오늘 상인이 파는 도안 (희귀만, 날마다 바뀜 — 서버 시계 날짜). */
    public List<String> shopToday() {
        if (!enabled()) return List.of();
        return BlueprintRules.shopPicks(services.content(), LocalDate.now().toEpochDay(), settings.shopCount());
    }

    public int shopPrice(String recipeId) {
        return BlueprintRules.shopPrice(services.content(), services.content().recipes().get(recipeId), settings);
    }

    /** 상인에게서 도안 한 장 사기. @return 샀으면 true */
    public boolean buy(Player p, String recipeId) {
        if (!shopToday().contains(recipeId)) {
            Text.error(p, "오늘은 그 도안을 팔지 않습니다.");
            return false;
        }
        PlayerData d = services.data().get(p);
        int price = shopPrice(recipeId);
        if (!d.takeGold(price)) {
            Text.error(p, "골드가 부족합니다. <gray>(필요 " + Text.num(price) + " G)");
            p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.6f, 1.2f);
            return false;
        }
        if (give(p, recipeId, 1, "shop") <= 0) {
            d.addGold(price);
            return false;
        }
        Text.send(p, "<gray>도안 구매 <dark_gray>(-" + Text.num(price) + " G)");
        p.playSound(p.getLocation(), Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.7f, 1.3f);
        services.hud().refresh(p);
        return true;
    }

    /** 자가 진단: 단계마다 도안 하나를 뽑아 만들고 다시 읽는다. @return 문제 글 (없으면 빈 목록) */
    public List<String> selfCheck(int tier) {
        List<String> bad = new ArrayList<>();
        Content c = services.content();
        if (c.item(BlueprintRules.ITEM_ID) == null) {
            bad.add("items.yml 에 blueprint 가 없음");
            return bad;
        }
        String rid = BlueprintRules.pick(c, tier, null, 0, ThreadLocalRandom.current());
        if (rid == null) return bad; // 그 단계 근처에 도안 레시피가 없음 (괜찮음)
        ItemStack s = BlueprintItems.create(services, rid, 1);
        if (s == null || !rid.equals(BlueprintItems.recipeOf(s))) bad.add("도안 만들기·읽기 실패: " + rid);
        return bad;
    }

    // ── 명령 ───────────────────────────────────────────────

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    private SuggestionProvider<CommandSourceStack> players() {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            for (Player p : Bukkit.getOnlinePlayers()) if (p.getName().toLowerCase(Locale.ROOT).startsWith(rem)) b.suggest(p.getName());
            return b.buildFuture();
        };
    }

    private SuggestionProvider<CommandSourceStack> recipes(boolean all) {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            if (all && "all".startsWith(rem)) b.suggest("all");
            int n = 0;
            for (RecipeDef r : BlueprintRules.gated(services.content())) {
                if (r.id().startsWith(rem) || (rem.length() >= 2 && r.id().contains(rem))) {
                    b.suggest(r.id());
                    if (++n >= 60) break;
                }
            }
            return b.buildFuture();
        };
    }

    private Player target(CommandContext<CommandSourceStack> ctx, String name) {
        CommandSender s = ctx.getSource().getSender();
        Player t = name != null ? Bukkit.getPlayerExact(name) : CommandService.sender(ctx) instanceof Player p ? p : null;
        if (t == null) Text.error(s, "대상 플레이어를 찾을 수 없습니다.");
        return t;
    }

    private static String arg(CommandContext<CommandSourceStack> ctx, String name) {
        try {
            return StringArgumentType.getString(ctx, name);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    private static int intArg(CommandContext<CommandSourceStack> ctx, String name, int def) {
        try {
            return IntegerArgumentType.getInteger(ctx, name);
        } catch (IllegalArgumentException e) {
            return def;
        }
    }

    private void registerCommands() {
        CommandService cmd = services.commands();
        var give = Commands.argument("recipe", StringArgumentType.word()).suggests(recipes(false))
                .executes(ctx -> run(ctx, () -> adminGive(ctx)))
                .then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                        .executes(ctx -> run(ctx, () -> adminGive(ctx)))
                        .then(Commands.argument("amount", IntegerArgumentType.integer(1, 16))
                                .executes(ctx -> run(ctx, () -> adminGive(ctx)))));
        var learn = Commands.argument("recipe", StringArgumentType.word()).suggests(recipes(true))
                .executes(ctx -> run(ctx, () -> adminLearn(ctx, true)))
                .then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                        .executes(ctx -> run(ctx, () -> adminLearn(ctx, true))));
        var forget = Commands.argument("recipe", StringArgumentType.word()).suggests(recipes(true))
                .executes(ctx -> run(ctx, () -> adminLearn(ctx, false)))
                .then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                        .executes(ctx -> run(ctx, () -> adminLearn(ctx, false))));
        cmd.addSubcommand("labadmin", Commands.literal("blueprint")
                .then(Commands.literal("give").then(give))
                .then(Commands.literal("learn").then(learn))
                .then(Commands.literal("forget").then(forget))
                .then(Commands.literal("list")
                        .executes(ctx -> run(ctx, () -> adminList(ctx)))
                        .then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                                .executes(ctx -> run(ctx, () -> adminList(ctx))))));
    }

    private void adminGive(CommandContext<CommandSourceStack> ctx) {
        String rid = arg(ctx, "recipe");
        CommandSender s = ctx.getSource().getSender();
        if (!BlueprintRules.needsBlueprint(services.content(), services.content().recipes().get(rid))) {
            Text.error(s, "도안이 필요한 레시피가 아닙니다: " + Text.escape(rid));
            return;
        }
        Player t = target(ctx, arg(ctx, "player"));
        if (t == null) return;
        int n = give(t, rid, intArg(ctx, "amount", 1), "admin");
        Text.send(s, "<gray>" + Text.escape(t.getName()) + " 에게 도안 <white>" + Text.escape(rid) + "</white> " + n + "장을 줬습니다.");
    }

    private void adminLearn(CommandContext<CommandSourceStack> ctx, boolean learn) {
        String rid = arg(ctx, "recipe");
        CommandSender s = ctx.getSource().getSender();
        Player t = target(ctx, arg(ctx, "player"));
        if (t == null) return;
        PlayerData d = services.data().get(t);
        int n;
        if ("all".equals(rid)) {
            List<String> ids = new ArrayList<>();
            for (RecipeDef r : BlueprintRules.gated(services.content())) ids.add(r.id());
            n = learn ? BlueprintBook.learnAll(d.ext(), ids) : BlueprintBook.forgetAll(d.ext());
        } else {
            if (!BlueprintRules.needsBlueprint(services.content(), services.content().recipes().get(rid))) {
                Text.error(s, "도안이 필요한 레시피가 아닙니다: " + Text.escape(rid));
                return;
            }
            n = (learn ? BlueprintBook.learn(d.ext(), rid) : BlueprintBook.forget(d.ext(), rid)) ? 1 : 0;
        }
        d.markDirty();
        Text.send(s, "<gray>" + Text.escape(t.getName()) + ": 도안 " + n + "개 " + (learn ? "배움" : "잊음")
                + " <dark_gray>(지금 " + BlueprintBook.learned(d.ext()).size() + "개)");
    }

    private void adminList(CommandContext<CommandSourceStack> ctx) {
        CommandSender s = ctx.getSource().getSender();
        Player t = target(ctx, arg(ctx, "player"));
        if (t == null) return;
        List<String> ids = learned(t);
        int total = BlueprintRules.gated(services.content()).size();
        Text.send(s, "<gray>" + Text.escape(t.getName()) + " 이(가) 배운 도안 <white>" + ids.size() + "</white> / " + total
                + (enabled() ? "" : " <#ff8a8a>(도안 잠금 꺼짐 — 도안 없이 모두 만듦)"));
        StringBuilder sb = new StringBuilder();
        for (String id : ids) {
            Rarity r = BlueprintItems.rarityOf(services.content(), id);
            ItemDef d = services.content().item(services.content().recipes().containsKey(id) ? services.content().recipes().get(id).result() : null);
            if (sb.length() > 0) sb.append("<dark_gray>, ");
            sb.append("<").append(r.color()).append(">").append(d == null ? Text.escape(id) : d.name());
        }
        if (sb.length() > 0) Text.send(s, sb.toString());
        Text.send(s, "<dark_gray>오늘 상인: " + String.join(", ", shopToday()));
    }
}
