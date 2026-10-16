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
import kr.labyrinth.items.unique.UniqueEffectService;
import kr.labyrinth.items.unique.UniqueEffects;
import kr.labyrinth.items.weaponskills.LabWeaponSkillService;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

/**
 * items 담당 모듈 진입점: ItemService(굴림·툴팁·장비 컴포넌트) · LootService(개인 루팅) · CraftingService(대장장이 GUI) ·
 * WeaponSkillService(17종 무기 스킬) · UniqueEffects(무기 고유 효과 26종, {@link UniqueEffectService}) · AuraService(전설·신화 아우라) · 장비 StatContributor(+세트 효과 · 겉모습 수) ·
 * 겉모습 4부위 효과({@link ArmorLookService} — 가죽 구르기 · 천 마나 보호막) · 소모품 · 바닐라 가공 차단 ·
 * 강화(enhance/EnhanceService — 대장간 [강화], +10 빛).
 * 명령: /미궁 강화|enhance (강화 창). 관리: /labadmin blacksmith [플레이어] · /labadmin loot &lt;테이블&gt; [플레이어] ·
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
    private UniqueEffectService unique;
    private ArmorLookService looks;

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
        // 0.3.6 옛 광물 재료 → 광석·새 몬스터 재료 (접속·보관함·줍기·손에 들기·셜커·꾸러미·액자·거치대·바닥 아이템)
        ItemMigration036Listener mat036 = new ItemMigration036Listener(services);
        pm.registerEvents(mat036, services.plugin());
        mat036.start();
        weaponSkills.start();
        // 고유 효과: 피해 훅은 pvp 모듈보다 먼저 등록된다 (가시 반격이 PvP 배율 전 피해를 잡는다)
        unique = new UniqueEffectService(services);
        services.setUnique(unique);
        unique.start();
        consumables = new ConsumableListener(services, weaponSkills);
        consumables.start();
        // 방어구 겉모습 4부위 효과: 가죽 구르기 · 천 마나 보호막 (판금 버팀은 파생 능력치로)
        looks = new ArmorLookService(services);
        services.setLooks(looks);
        looks.start();
        auras = new AuraService(services);
        auras.start();
        enhance.start();

        registerCommands();
        checkContent();
        for (Player p : Bukkit.getOnlinePlayers()) services.stats().markDirty(p);
    }

    @Override
    public void disable() {
        if (auras != null) auras.stop();
        if (enhance != null) enhance.stop();
        if (weaponSkills != null) weaponSkills.stop();
        if (unique != null) {
            unique.stop();
            services.setUnique(UniqueEffects.NONE);
        }
        if (consumables != null) consumables.stop();
        if (looks != null) {
            looks.stop();
            services.setLooks(LookEffects.NONE);
        }
        if (equipment != null) services.stats().removeContributor(equipment);
    }

    @Override
    public void reload() {
        if (auras != null) auras.reload();
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
