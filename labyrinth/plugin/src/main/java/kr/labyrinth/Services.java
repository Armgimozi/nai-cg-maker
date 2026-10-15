package kr.labyrinth;

import java.io.IOException;
import java.nio.file.Path;
import java.util.Objects;
import java.util.function.Consumer;
import kr.labyrinth.bosses.BossService;
import kr.labyrinth.bosses.NoopBossService;
import kr.labyrinth.classes.BasicClassService;
import kr.labyrinth.classes.ClassService;
import kr.labyrinth.classes.NoopStatusEffectService;
import kr.labyrinth.classes.StatusEffectService;
import kr.labyrinth.combat.DamageService;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.Content;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Settings;
import kr.labyrinth.data.PlayerDataService;
import kr.labyrinth.data.ServerRecords;
import kr.labyrinth.dungeon.DungeonService;
import kr.labyrinth.dungeon.NoopDungeonService;
import kr.labyrinth.items.BasicItemService;
import kr.labyrinth.items.CraftingService;
import kr.labyrinth.items.ItemService;
import kr.labyrinth.items.LootService;
import kr.labyrinth.items.NoopCraftingService;
import kr.labyrinth.items.NoopLootService;
import kr.labyrinth.items.NoopWeaponSkillService;
import kr.labyrinth.items.WeaponSkillService;
import kr.labyrinth.mobs.MobService;
import kr.labyrinth.mobs.NoopMobService;
import kr.labyrinth.mobs.NoopNpcService;
import kr.labyrinth.mobs.NpcService;
import kr.labyrinth.pack.PackService;
import kr.labyrinth.party.PartyService;
import kr.labyrinth.party.SoloPartyService;
import kr.labyrinth.pvp.DefaultTargetFilter;
import kr.labyrinth.pvp.TargetFilter;
import kr.labyrinth.stats.LevelService;
import kr.labyrinth.stats.StatService;
import kr.labyrinth.titles.BasicTitleService;
import kr.labyrinth.titles.TitleService;
import kr.labyrinth.ui.BasicHudService;
import kr.labyrinth.ui.ChatMenuService;
import kr.labyrinth.ui.HudService;
import kr.labyrinth.ui.MenuService;
import org.bukkit.configuration.file.FileConfiguration;

/**
 * 서비스 레지스트리 (ARCHITECTURE §4). 생성자 주입 대신 이것 하나를 넘긴다 — 순환 참조는 getter 로 지연 접근.
 * <p>
 * 팀 모듈 서비스(items/classes/mobs/bosses/dungeon/party/titles/ui/pvp)는 처음엔 안전한 기본 구현이 들어 있고,
 * 각 담당 모듈의 {@code enable()} 에서 setter 로 실제 구현을 넣는다. 그러니 다른 서비스 참조는
 * 필드에 저장하지 말고 매번 {@code services.xxx()} 로 얻을 것.
 */
public final class Services {

    private static volatile Services instance;

    private final LabyrinthPlugin plugin;
    private volatile Settings settings = new Settings(null);
    private volatile Content content = Content.empty();

    // core (plugin-core 소유)
    private final ServerRecords records;
    private final PlayerDataService data;
    private final StatService stats;
    private final LevelService levels;
    private final DamageService damage;
    private final PackService pack;
    private final CommandService commands;

    // 팀 계약 (기본 구현 → 담당 모듈이 교체)
    private volatile ItemService items;
    private volatile LootService loot;
    private volatile CraftingService crafting;
    private volatile WeaponSkillService weaponSkills;
    private volatile ClassService classes;
    private volatile StatusEffectService effects;
    private volatile TargetFilter targets;
    private volatile MobService mobs;
    private volatile NpcService npcs;
    private volatile BossService bosses;
    private volatile DungeonService dungeon;
    private volatile PartyService party;
    private volatile TitleService titles;
    private volatile HudService hud;
    private volatile MenuService menus;

    Services(LabyrinthPlugin plugin) {
        this.plugin = plugin;
        instance = this;
        this.records = new ServerRecords(this);
        this.data = new PlayerDataService(this);
        this.stats = new StatService(this);
        this.levels = new LevelService(this);
        this.damage = new DamageService(this);
        this.pack = new PackService(this);
        this.commands = new CommandService(this);

        this.items = new BasicItemService(this);
        this.loot = new NoopLootService();
        this.crafting = new NoopCraftingService();
        this.weaponSkills = new NoopWeaponSkillService();
        this.classes = new BasicClassService(this);
        this.effects = new NoopStatusEffectService();
        this.targets = new DefaultTargetFilter(this);
        this.mobs = new NoopMobService();
        this.npcs = new NoopNpcService();
        this.bosses = new NoopBossService();
        this.dungeon = new NoopDungeonService(this);
        this.party = new SoloPartyService();
        this.titles = new BasicTitleService(this);
        this.hud = new BasicHudService(this);
        this.menus = new ChatMenuService(this);
    }

    /** 정적 접근 (리스너·유틸 등 Services 를 받기 어려운 곳). 플러그인이 켜져 있을 때만 유효. */
    public static Services get() {
        Services s = instance;
        if (s == null) throw new IllegalStateException("Labyrinth 가 아직 켜지지 않았습니다");
        return s;
    }

    // ── 설정·콘텐츠 ───────────────────────────────────────────────────────

    public LabyrinthPlugin plugin() { return plugin; }
    public Settings settings() { return settings; }
    public Content content() { return content; }

    void loadSettings() {
        plugin.reloadConfig();
        settings = new Settings(plugin.getConfig());
    }

    /** config.yml 수정 + 저장 + 다시 읽기 (난이도 설정 등). */
    public void updateConfig(Consumer<FileConfiguration> edit) {
        edit.accept(plugin.getConfig());
        plugin.saveConfig();
        loadSettings();
    }

    ContentValidator.Report loadContent() {
        try {
            ContentLoader.copyDefaults(plugin);
        } catch (IOException e) {
            Log.error("기본 콘텐츠 복사 실패", e);
        }
        Path dir = plugin.getDataFolder().toPath().resolve("content");
        ContentLoader.Result r = ContentLoader.load(dir);
        for (String p : r.problems()) Log.warn("[콘텐츠] " + p);
        ContentValidator.Report report = ContentValidator.validate(r.content());
        for (String e : report.errors()) Log.warn("[콘텐츠 오류] " + e);
        if (!report.warnings().isEmpty()) Log.info("[콘텐츠] 경고 " + report.warnings().size() + "건 (첫 항목: " + report.warnings().get(0) + ")");
        content = r.content();
        if (!plugin.getConfig().getBoolean("ui.use_glyphs", true)) {
            // 리소스팩 UI 폰트가 클라이언트에서 안 보일 때(네모 박스) 임시로 끄는 스위치 — 글자 HUD·기본 메뉴 제목으로 대체
            Content c = content;
            content = new Content(c.classes(), c.items(), c.sets(), c.mobs(), c.bosses(), c.floors(), c.lootTables(),
                    c.lootSettings(), c.recipes(), c.achievements(), c.npcs(), c.auras(), c.fxModels(),
                    java.util.Map.of(), java.util.Map.of(), c.enhance());
            Log.info("ui.use_glyphs: false — UI 글리프(커스텀 폰트)를 쓰지 않고 글자 HUD 로 표시합니다.");
        }
        Log.info("콘텐츠 로드: " + content.summary());
        if (!report.ok()) Log.warn("콘텐츠 검사 오류 " + report.errors().size() + "건 — 해당 항목은 동작하지 않을 수 있습니다.");
        java.util.List<String> errors = new java.util.ArrayList<>(r.problems());
        errors.addAll(report.errors());
        return new ContentValidator.Report(java.util.List.copyOf(errors), report.warnings());
    }

    /** /labadmin reload: 설정·콘텐츠 다시 읽고 모든 모듈 reload(). */
    public ContentValidator.Report reload() {
        loadSettings();
        ContentValidator.Report report = loadContent();
        plugin.reloadModules();
        return report;
    }

    // ── core 서비스 ───────────────────────────────────────────────────────

    public ServerRecords records() { return records; }
    public PlayerDataService data() { return data; }
    public StatService stats() { return stats; }
    public LevelService levels() { return levels; }
    public DamageService damage() { return damage; }
    public PackService pack() { return pack; }
    public CommandService commands() { return commands; }

    // ── 팀 계약 getter ────────────────────────────────────────────────────

    public ItemService items() { return items; }
    public LootService loot() { return loot; }
    public CraftingService crafting() { return crafting; }
    public WeaponSkillService weaponSkills() { return weaponSkills; }
    public ClassService classes() { return classes; }
    public StatusEffectService effects() { return effects; }
    public TargetFilter targets() { return targets; }
    public MobService mobs() { return mobs; }
    public NpcService npcs() { return npcs; }
    public BossService bosses() { return bosses; }
    public DungeonService dungeon() { return dungeon; }
    public PartyService party() { return party; }
    public TitleService titles() { return titles; }
    public HudService hud() { return hud; }
    public MenuService menus() { return menus; }

    // ── 팀 계약 setter (담당 모듈 enable 에서 호출) ───────────────────────

    public void setItems(ItemService s) { items = Objects.requireNonNull(s); }
    public void setLoot(LootService s) { loot = Objects.requireNonNull(s); }
    public void setCrafting(CraftingService s) { crafting = Objects.requireNonNull(s); }
    public void setWeaponSkills(WeaponSkillService s) { weaponSkills = Objects.requireNonNull(s); }
    public void setClasses(ClassService s) { classes = Objects.requireNonNull(s); }
    public void setEffects(StatusEffectService s) { effects = Objects.requireNonNull(s); }
    public void setTargets(TargetFilter s) { targets = Objects.requireNonNull(s); }
    public void setMobs(MobService s) { mobs = Objects.requireNonNull(s); }
    public void setNpcs(NpcService s) { npcs = Objects.requireNonNull(s); }
    public void setBosses(BossService s) { bosses = Objects.requireNonNull(s); }
    public void setDungeon(DungeonService s) { dungeon = Objects.requireNonNull(s); }
    public void setParty(PartyService s) { party = Objects.requireNonNull(s); }
    public void setTitles(TitleService s) { titles = Objects.requireNonNull(s); }

    public void setHud(HudService s) {
        HudService old = hud;
        hud = Objects.requireNonNull(s);
        if (old instanceof BasicHudService b && old != s) b.stop();
    }

    public void setMenus(MenuService s) { menus = Objects.requireNonNull(s); }

    static void clear() { instance = null; }
}
