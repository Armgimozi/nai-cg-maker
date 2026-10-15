package kr.labyrinth.items;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import java.util.Locale;
import java.util.Set;
import java.util.TreeSet;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Text;
import kr.labyrinth.items.crafting.LabCraftingService;
import kr.labyrinth.items.enhance.EnhanceService;
import kr.labyrinth.items.enhance.Enhancement;
import kr.labyrinth.items.loot.LabLootService;
import kr.labyrinth.items.weaponskills.LabWeaponSkillService;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

/**
 * items 담당 모듈 진입점: ItemService(굴림·툴팁·장비 컴포넌트) · LootService(개인 루팅) · CraftingService(대장장이 GUI) ·
 * WeaponSkillService(17종 무기 스킬) · AuraService(전설·신화 아우라) · 장비 StatContributor(+세트 효과) · 소모품 · 바닐라 가공 차단 ·
 * 강화(enhance/EnhanceService — 대장간 [강화], +10 빛) · 어깨·등 3D 장식({@link ArmorCosmetics} — 상의 세트별 탑승 디스플레이).
 * 명령: /미궁 강화|enhance (강화 창) · /미궁 장식|cosmetics [켜기|끄기] (내 어깨·등 장식) ·
 * /미궁 장식 내화면|self [켜기|끄기] (내 장식을 내 화면에도). 관리: /labadmin blacksmith [플레이어] · /labadmin loot &lt;테이블&gt; [플레이어] ·
 * /labadmin weaponskills · /labadmin enhance &lt;단계&gt; [플레이어] (주손 장비 단계 바로 설정).
 */
public final class ItemsModule implements Module {

    private final Services services;
    private LabWeaponSkillService weaponSkills;
    private AuraService auras;
    private ConsumableListener consumables;
    private EquipmentListener equipment;
    private LabLootService loot;
    private EnhanceService enhance;
    private ArmorCosmetics cosmetics;

    public ItemsModule(Services services) { this.services = services; }

    @Override
    public String name() { return "items"; }

    @Override
    public void enable() {
        services.setItems(new GearItemService(services));
        loot = new LabLootService(services);
        services.setLoot(loot);
        LabCraftingService crafting = new LabCraftingService(services);
        services.setCrafting(crafting);
        enhance = new EnhanceService(services);
        crafting.setEnhance(enhance);
        weaponSkills = new LabWeaponSkillService(services);
        services.setWeaponSkills(weaponSkills);

        var pm = Bukkit.getPluginManager();
        equipment = new EquipmentListener(services);
        pm.registerEvents(equipment, services.plugin());
        services.stats().addContributor(equipment);
        pm.registerEvents(loot, services.plugin());
        pm.registerEvents(new ItemGuardListener(services), services.plugin());
        weaponSkills.start();
        consumables = new ConsumableListener(services, weaponSkills);
        consumables.start();
        auras = new AuraService(services);
        auras.start();
        enhance.start();
        cosmetics = new ArmorCosmetics(services);
        cosmetics.start();

        registerCommands();
        checkContent();
        for (Player p : Bukkit.getOnlinePlayers()) services.stats().markDirty(p);
    }

    @Override
    public void disable() {
        if (auras != null) auras.stop();
        if (cosmetics != null) cosmetics.stop();
        if (enhance != null) enhance.stop();
        if (weaponSkills != null) weaponSkills.stop();
        if (consumables != null) consumables.stop();
        if (equipment != null) services.stats().removeContributor(equipment);
    }

    @Override
    public void reload() {
        if (auras != null) auras.reload();
        if (cosmetics != null) cosmetics.reload();
        if (enhance != null) enhance.reload();
        checkContent();
        for (Player p : Bukkit.getOnlinePlayers()) services.stats().markDirty(p);
    }

    /** 콘텐츠에 쓰인 무기 스킬 id 가 전부 구현돼 있는지 로그로 확인. */
    private void checkContent() {
        Set<String> missing = new TreeSet<>();
        for (ItemDef d : services.content().items().values()) {
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
                if (!weaponSkills.implementedIds().contains(s.id())) missing.add(s.id() + "(" + d.id() + ")");
            }
        }
        if (!missing.isEmpty()) Log.warn("[무기 스킬] 구현이 없는 id: " + String.join(", ", missing));
    }

    // ── 명령 ──────────────────────────────────────────────────────────────

    private SuggestionProvider<CommandSourceStack> players() {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            for (Player p : Bukkit.getOnlinePlayers()) if (p.getName().toLowerCase(Locale.ROOT).startsWith(rem)) b.suggest(p.getName());
            return b.buildFuture();
        };
    }

    private SuggestionProvider<CommandSourceStack> tables() {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            int n = 0;
            for (String id : services.content().lootTables().keySet()) {
                if (id.startsWith(rem) || (rem.length() >= 2 && id.contains(rem))) {
                    b.suggest(id);
                    if (++n >= 60) break;
                }
            }
            return b.buildFuture();
        };
    }

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    private Player target(CommandContext<CommandSourceStack> ctx, String name) {
        CommandSender s = ctx.getSource().getSender();
        Player t = name != null ? Bukkit.getPlayerExact(name) : CommandService.sender(ctx) instanceof Player p ? p : null;
        if (t == null) Text.error(s, "대상 플레이어를 찾을 수 없습니다.");
        return t;
    }

    private void registerCommands() {
        CommandService cmd = services.commands();
        cmd.addSubcommand("labadmin", Commands.literal("blacksmith")
                .executes(ctx -> run(ctx, () -> {
                    Player t = target(ctx, null);
                    if (t != null) services.crafting().openBlacksmith(t);
                }))
                .then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                        .executes(ctx -> run(ctx, () -> {
                            Player t = target(ctx, StringArgumentType.getString(ctx, "player"));
                            if (t != null) services.crafting().openBlacksmith(t);
                        }))));
        cmd.addSubcommand("labadmin", Commands.literal("loot")
                .then(Commands.argument("table", StringArgumentType.word()).suggests(tables())
                        .executes(ctx -> run(ctx, () -> lootTest(ctx, null)))
                        .then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                                .executes(ctx -> run(ctx, () -> lootTest(ctx, StringArgumentType.getString(ctx, "player")))))));
        for (String n : new String[] {"enhance", "강화"}) {
            cmd.addSubcommand("lab", Commands.literal(n).executes(ctx -> run(ctx,
                    () -> CommandService.withPlayer(CommandService.sender(ctx), enhance::open))));
        }
        for (String n : new String[] {"cosmetics", "장식"}) {
            var node = Commands.literal(n).executes(ctx -> run(ctx,
                    () -> CommandService.withPlayer(CommandService.sender(ctx), p -> toggleCosmetics(p, null))));
            for (String arg : new String[] {"켜기", "끄기", "on", "off"}) {
                node.then(Commands.literal(arg).executes(ctx -> run(ctx,
                        () -> CommandService.withPlayer(CommandService.sender(ctx), p -> toggleCosmetics(p, arg)))));
            }
            for (String self : new String[] {"내화면", "self"}) {
                var selfNode = Commands.literal(self).executes(ctx -> run(ctx,
                        () -> CommandService.withPlayer(CommandService.sender(ctx), p -> toggleSelfView(p, null))));
                for (String arg : new String[] {"켜기", "끄기", "on", "off"}) {
                    selfNode.then(Commands.literal(arg).executes(ctx -> run(ctx,
                            () -> CommandService.withPlayer(CommandService.sender(ctx), p -> toggleSelfView(p, arg)))));
                }
                node.then(selfNode);
            }
            cmd.addSubcommand("lab", node);
        }
        cmd.addSubcommand("labadmin", Commands.literal("enhance")
                .then(Commands.argument("level", IntegerArgumentType.integer(0, 20))
                        .executes(ctx -> run(ctx, () -> adminEnhance(ctx, null)))
                        .then(Commands.argument("player", StringArgumentType.word()).suggests(players())
                                .executes(ctx -> run(ctx, () -> adminEnhance(ctx, StringArgumentType.getString(ctx, "player")))))));
        cmd.addSubcommand("labadmin", Commands.literal("weaponskills").executes(ctx -> run(ctx, () -> {
            CommandSender s = ctx.getSource().getSender();
            Text.send(s, "<gray>무기 스킬 구현 " + weaponSkills.implementedIds().size() + "종: <white>"
                    + String.join(", ", new TreeSet<>(weaponSkills.implementedIds())));
        })));
    }

    /** /미궁 장식 [켜기|끄기] — 인자가 없으면 뒤집는다. 끄면 내 장식이 아예 생기지 않는다(남에게도 안 보임). */
    private void toggleCosmetics(Player p, String arg) {
        Boolean want = arg == null ? Boolean.valueOf(!cosmetics.isOn(p)) : ArmorPieceLayout.parseToggle(arg);
        if (want == null) {
            Text.error(p, "켜기 또는 끄기 로 적어 주세요.");
            return;
        }
        cosmetics.setOn(p, want);
        if (!cosmetics.config().enabled()) {
            Text.send(p, "<gray>이 서버는 어깨·등 장식을 쓰지 않습니다 <dark_gray>(config cosmetics.armor_pieces.enabled)</dark_gray>. 설정만 저장했습니다.");
            return;
        }
        Text.send(p, want ? "<gray>어깨·등 장식을 <white>켰습니다</white>. 미궁 상의를 입으면 다른 사람에게 입체 장식이 보입니다 "
                + "(내 화면에는 3인칭에서도 안 보임 — 직접 보려면 <white>/미궁 장식 내화면 켜기</white>)."
                : "<gray>어깨·등 장식을 <white>껐습니다</white>. 다시 켜려면 <white>/미궁 장식 켜기</white>");
        p.playSound(p.getLocation(), org.bukkit.Sound.UI_BUTTON_CLICK, 0.6f, want ? 1.4f : 0.9f);
    }

    /**
     * /미궁 장식 내화면 [켜기|끄기] — 내 장식을 내 화면에도 보이게 (기본 꺼짐). 서버는 1인칭/3인칭을 모르므로 켜면 1인칭에서도 보인다.
     * 인자가 없으면 뒤집는다.
     */
    private void toggleSelfView(Player p, String arg) {
        Boolean want = arg == null ? Boolean.valueOf(!cosmetics.isSelfView(p)) : ArmorPieceLayout.parseToggle(arg);
        if (want == null) {
            Text.error(p, "켜기 또는 끄기 로 적어 주세요.");
            return;
        }
        cosmetics.setSelfView(p, want);
        if (want) {
            Text.send(p, "<gray>내 어깨·등 장식을 <white>내 화면에도</white> 보입니다 — 3인칭(F5)에서 확인하세요. "
                    + "<yellow>1인칭에서 아래를 보거나 고개를 돌리면 어깨 장식이 화면 가장자리에 보일 수 있습니다.</yellow> "
                    + "<dark_gray>(되돌리기: /미궁 장식 내화면 끄기)");
            if (!cosmetics.isOn(p)) Text.send(p, "<gray>지금은 장식이 꺼져 있습니다 — <white>/미궁 장식 켜기</white>");
        } else {
            Text.send(p, "<gray>내 어깨·등 장식을 내 화면에서 <white>숨깁니다</white> (다른 사람에게는 그대로 보임).");
        }
        p.playSound(p.getLocation(), org.bukkit.Sound.UI_BUTTON_CLICK, 0.6f, want ? 1.4f : 0.9f);
    }

    private void adminEnhance(CommandContext<CommandSourceStack> ctx, String player) {
        Player t = target(ctx, player);
        if (t == null) return;
        int lv = Math.min(Enhancement.rules().maxLevel(), IntegerArgumentType.getInteger(ctx, "level"));
        var hand = t.getInventory().getItemInMainHand();
        if (!enhance.setLevel(hand, lv)) {
            Text.error(ctx.getSource().getSender(), "주손에 강화할 수 있는 미궁 무기·방어구·방패가 없습니다.");
            return;
        }
        t.getInventory().setItemInMainHand(hand);
        services.stats().markDirty(t);
        Text.send(ctx.getSource().getSender(), "<gray>" + Text.escape(t.getName()) + " 의 주손 장비를 <white>+" + lv + "</white> 로 바꿨습니다.");
    }

    private void lootTest(CommandContext<CommandSourceStack> ctx, String player) {
        String table = StringArgumentType.getString(ctx, "table");
        if (services.content().lootTable(table) == null) {
            Text.error(ctx.getSource().getSender(), "없는 루팅 테이블: " + Text.escape(table));
            return;
        }
        Player t = target(ctx, player);
        if (t != null) loot.adminTest(t, table);
    }
}
