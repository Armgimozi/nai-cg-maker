package kr.souls;

import io.papermc.paper.plugin.lifecycle.event.types.LifecycleEvents;
import kr.souls.bonfire.TestBonfire;
import kr.souls.cmd.SoulsCommands;
import kr.souls.cmd.TestCommands;
import kr.souls.combat.CombatState;
import kr.souls.combat.DamageHook;
import kr.souls.combat.FoeScaling;
import kr.souls.combat.Parry;
import kr.souls.combat.Pvp;
import kr.souls.combat.PvpGuard;
import kr.souls.combat.Roll;
import kr.souls.combat.Stamina;
import kr.souls.combat.TestHits;
import kr.souls.data.Profiles;
import kr.souls.data.WorldState;
import kr.souls.input.SneakTap;
import kr.souls.hud.Glyphs;
import kr.souls.hud.Hud;
import kr.souls.hud.Titles;
import kr.souls.item.RingSlots;
import kr.souls.item.Rings;
import kr.souls.item.WeaponGuard;
import kr.souls.item.Weapons;
import kr.souls.pack.PackService;
import kr.souls.progression.Ailments;
import kr.souls.progression.AttributeApplier;
import kr.souls.progression.DeathFlow;
import kr.souls.progression.Load;
import kr.souls.progression.Origins;
import kr.souls.progression.SoulPurse;
import kr.souls.progression.Stats;
import kr.souls.skill.Cooldowns;
import kr.souls.skill.HitEffects;
import kr.souls.skill.Mechanics;
import kr.souls.skill.SkillRegistry;
import kr.souls.skill.Targets;
import kr.souls.start.StartFlow;
import kr.souls.ui.LevelUpDialog;
import kr.souls.ui.Ui;
import kr.souls.util.Fx;
import kr.souls.world.Protection;
import kr.souls.world.WorldService;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.Set;

/**
 * 블록 소울 (Block Soul). 혼자 하는 소울류 서버 플러그인. 지금 판은 M0 (기반과 점검, 14절).
 * 데이터팩은 부트스트래퍼(SoulsBootstrap)가 세계를 읽기 전에 싣는다. 켜는 순서는 12.3 을 따른다.
 */
public final class Souls extends JavaPlugin {
    /** 켤 때 쓸어 내는 남은 물체 태그 (플러그인이 만든 물체는 하나도 저장하지 않는다) */
    public static final Set<String> SWEEP_TAGS = Set.of(Mechanics.FX_TAG, "souls_rig", TestHits.ENT_TAG);

    private Config cfg;
    private Content content;
    private SkillRegistry skills;
    private Weapons weapons;
    private Rings rings;
    private RingSlots ringSlots;
    private Cooldowns cooldowns;
    private WorldService worlds;
    private Ticker ticker;
    private Stamina stamina;
    private Roll roll;
    private Parry parry;
    private WeaponGuard weaponGuard;
    private Titles titles;
    private Hud hud;
    private DeathFlow death;
    private PackService pack;
    private TestHits testHits;
    // 1.3판 (5.7~5.10): 프로필, 세계 설정, 능력치, 장비 무게, 출신, 창, 시작 흐름, PvP, 피해 고리, 웅크리기 짧게 = 구르기
    private Profiles profiles;
    private WorldState worldState;
    private Origins origins;
    private Stats stats;
    private AttributeApplier attributes;
    private Load load;
    private SoulPurse purse;
    private Pvp pvp;
    private Ui ui;
    private StartFlow start;
    private LevelUpDialog levelUp;
    private TestBonfire testBonfire;
    private SneakTap sneakTap;
    private FoeScaling foes;

    @Override
    public void onEnable() {
        // 1. 키와 로거
        Keys.init(this);
        Fx.setLogger(getLogger());
        HitEffects.setLogger(getLogger());
        Mechanics.setLogger(getLogger());
        // 2. 기본 설정과 문구
        saveDefaultConfig();
        cfg = new Config(getConfig());
        Lang.load(this);
        // 3. 콘텐츠 꺼내기
        content = new Content(this);
        content.extract();
        // 4. 등록부 (스킬, 무기·방패·촉매, 출신, 반지. 그 뒤로 items → armor → enemies → bosses → encounters)
        cooldowns = new Cooldowns();
        skills = new SkillRegistry(getLogger());
        skills.load(content.yml("skills.yml"));
        weapons = new Weapons(getLogger());
        weapons.load(content.yml("weapons.yml"));
        origins = new Origins(getLogger());
        origins.load(content.yml("origins.yml"), weapons);
        rings = new Rings(getLogger());
        rings.load(content.yml("rings.yml"));
        // 프로필과 세계 설정 (게임 규칙 pvp 가 세계 설정을 따르므로 세계보다 먼저 만든다)
        profiles = new Profiles(this);
        worldState = new WorldState(this);
        pvp = new Pvp(this);
        foes = new FoeScaling(this);
        // 5. 세계: 로비와 souls_world, 게임 규칙, 난이도, 필요하면 접속을 막고 짓기
        worlds = new WorldService(this);
        worlds.start();
        worldState.load(worlds.world());
        worlds.applyPvp();
        checkMaxHealthCap();
        // 6. 서비스
        ticker = new Ticker(this);
        Glyphs.load(this);
        stamina = new Stamina(this);
        roll = new Roll(this);
        parry = new Parry(this);
        titles = new Titles();
        hud = new Hud(this);
        death = new DeathFlow(this);
        testHits = new TestHits();
        pack = new PackService(this);
        pack.start();
        stats = new Stats(this);
        attributes = new AttributeApplier(this);
        load = new Load(this);
        purse = new SoulPurse(this);
        ui = new Ui(this);
        titles.setBusy(ui::open);
        start = new StartFlow(this);
        levelUp = new LevelUpDialog(this);
        testBonfire = new TestBonfire(this);
        sneakTap = new SneakTap(this);
        ringSlots = new RingSlots(this);
        hud.setSoulSource(purse::get);
        Targets.pvp = pvp::allowed;
        start.enable();
        ticker.add("load", load::tick);
        ticker.add("stamina", stamina::tick);
        ticker.add("roll", roll::tick);
        ticker.add("tap", sneakTap::tick);
        ticker.add("hud", hud::tick);
        ticker.add("titles", titles::tick);
        ticker.add("rings", ringSlots::tick);
        ticker.start();
        // 7. 리스너, 명령어
        var pm = getServer().getPluginManager();
        pm.registerEvents(worlds, this);
        pm.registerEvents(new Protection(worlds), this);
        pm.registerEvents(stamina, this);
        pm.registerEvents(roll, this);
        pm.registerEvents(hud, this);
        pm.registerEvents(death, this);
        pm.registerEvents(testHits, this);
        pm.registerEvents(pack, this);
        weaponGuard = new WeaponGuard(this);
        pm.registerEvents(weaponGuard, this);
        pm.registerEvents(profiles, this);
        pm.registerEvents(pvp, this);
        pm.registerEvents(new PvpGuard(this), this);
        pm.registerEvents(new DamageHook(this), this);
        pm.registerEvents(foes, this);
        pm.registerEvents(new Ailments(this), this);
        pm.registerEvents(load, this);
        pm.registerEvents(ui, this);
        pm.registerEvents(start, this);
        pm.registerEvents(levelUp, this);
        pm.registerEvents(testBonfire, this);
        pm.registerEvents(sneakTap, this);
        pm.registerEvents(ringSlots, this);
        getLifecycleManager().registerEventHandler(LifecycleEvents.COMMANDS, e -> {
            SoulsCommands.register(this, e.registrar());
            TestCommands.register(this, e.registrar());
        });
        // 8. 남은 물체 쓸기, 9. 접속 중인 플레이어 다시 읽기 (/reload 뒤)
        Bukkit.getScheduler().runTask(this, () -> {
            int swept = sweep();
            if (swept > 0) getLogger().info("남은 물체 " + swept + "개를 쓸어 냈습니다.");
            for (Player p : Bukkit.getOnlinePlayers()) {
                attributes.apply(p);
                load.refresh(p);
                stamina.refill(p);
                hud.invalidate(p);
            }
            ringSlots.enable();
        });
        getLogger().info("블록 소울 (M0, 1.3판 시작 설정·출신·능력치) 준비 완료" + (cfg.testMode ? " — 시험 모드" : ""));
    }

    /**
     * 최대 HP 상한 (검토 T1): Spigot 의 기본 settings.attribute.maxHealth.max 는 1024 라 체력 37 언저리부터 최대 HP (5.2, 99 → 1500) 가
     * 말없이 잘린다. server/spigot.yml 이 2048 로 올린다. 낮으면 크게 알리고 /souls check 가 FAIL.
     */
    private void checkMaxHealthCap() {
        double cap = maxHealthCap();
        double want = cfg.stats.maxHealth.at(cfg.stats.max);
        if (cap + 1e-6 < want) {
            getLogger().severe("=================================================================");
            getLogger().severe("spigot.yml 의 settings.attribute.maxHealth.max 가 " + cap + " 입니다. 최대 HP " + want + " 보다 낮아 큰 체력이 잘립니다.");
            getLogger().severe("서버 폴더의 spigot.yml 에서 2048.0 으로 올리고 다시 켜 주세요 (배포 묶음의 server/spigot.yml).");
            getLogger().severe("=================================================================");
        }
    }

    @SuppressWarnings("removal") // Paper 에 spigot.yml 값을 읽는 다른 길이 없다
    public double maxHealthCap() {
        try {
            return Bukkit.spigot().getSpigotConfig().getDouble("settings.attribute.maxHealth.max", 2048.0);
        } catch (RuntimeException ex) {
            return 2048.0;
        }
    }

    @Override
    public void onDisable() {
        // 반지 칸 (2×2) 을 먼저 비운다: 서버를 끄면 플러그인이 꺼진 뒤 플레이어를 내보내며 바닐라가 2×2 를 떨어뜨린다 (반지는 프로필에 있다)
        if (ringSlots != null) ringSlots.disable();
        if (profiles != null) {
            profiles.saveAll();
            profiles.shutdown();
        }
        if (ticker != null) ticker.stop();
        if (pack != null) pack.stop();
        if (roll != null) roll.shutdown();
        if (hud != null) hud.shutdown();
        Bukkit.getServer().allowPausing(this, true);
        CombatState.clear();
    }

    /** 우리 태그가 붙은 물체를 모든 세계에서 지운다. */
    public int sweep() {
        int n = 0;
        for (World w : Bukkit.getWorlds()) {
            for (Entity e : w.getEntities()) {
                if (e instanceof Player) continue;
                for (String t : e.getScoreboardTags()) {
                    if (SWEEP_TAGS.contains(t)) {
                        e.remove();
                        n++;
                        break;
                    }
                }
            }
        }
        return n;
    }

    /**
     * config.yml, 그림 글자, 콘텐츠를 다시 읽는다 (세계와 팩은 그대로). 문구는 다시 읽지 않는다: jar 와 팩 안에만 있어
     * 글을 바꾸면 팩과 jar 를 함께 다시 만든다 (10.9).
     */
    public void reloadAll() {
        reloadConfig();
        cfg = new Config(getConfig());
        Glyphs.load(this);
        skills.load(content.yml("skills.yml"));
        weapons.load(content.yml("weapons.yml"));
        origins.load(content.yml("origins.yml"), weapons);
        rings.load(content.yml("rings.yml"));
        // 시험 모드를 켜고 끄면 /soulstest 가 보이고 숨는다. 바뀐 설정 (최대 HP·이동 속도·공격 속도 곡선, 무게 단계의 걷기 배율,
        // hud.show-souls 같은 것) 을 곧바로 건다: 창과 HUD 만 새 값이고 속성은 옛 값인 채 남지 않게 (검토 reload-stale-attributes)
        for (Player p : Bukkit.getOnlinePlayers()) {
            p.updateCommands();
            attributes.apply(p);
            load.reset(p);
            hud.invalidate(p);
            // 반지 칸의 사본을 새로 (rings.yml 의 효과 값이 바뀌면 설명 칸도 새 값, 검토 R6)
            ringSlots.refresh(p);
        }
        foes.applyAll();
        checkMaxHealthCap();
    }

    /**
     * 시험 줄 "[T] ..." (debug.test-mode 일 때만). 봇이 채팅으로 읽는다 (12.11).
     * p 가 null 이면 서버 기록에만.
     */
    public void test(Player p, String line) {
        if (!cfg.testMode) return;
        if (p != null) p.sendMessage(Component.text("[T] " + line, kr.souls.hud.Glyphs.ASH3)); // lang-machine: 봇이 읽는 시험 줄
        if (cfg.logTestLines) getLogger().info("[T] " + (p == null ? "" : p.getName() + " ") + line);
    }

    public Config cfg() { return cfg; }
    public Content content() { return content; }
    public SkillRegistry skills() { return skills; }
    public Weapons weapons() { return weapons; }
    public Rings rings() { return rings; }
    public RingSlots ringSlots() { return ringSlots; }
    public Cooldowns cooldowns() { return cooldowns; }
    public WorldService worlds() { return worlds; }
    public Ticker ticker() { return ticker; }
    public Stamina stamina() { return stamina; }
    public Roll roll() { return roll; }
    public Parry parry() { return parry; }
    public WeaponGuard weaponGuard() { return weaponGuard; }
    public Titles titles() { return titles; }
    public Hud hud() { return hud; }
    public DeathFlow death() { return death; }
    public PackService pack() { return pack; }
    public TestHits testHits() { return testHits; }
    public Profiles profiles() { return profiles; }
    public WorldState worldState() { return worldState; }
    public Origins origins() { return origins; }
    public Stats stats() { return stats; }
    public AttributeApplier attributes() { return attributes; }
    public Load load() { return load; }
    public SoulPurse purse() { return purse; }
    public Pvp pvp() { return pvp; }
    public Ui ui() { return ui; }
    public StartFlow start() { return start; }
    public LevelUpDialog levelUp() { return levelUp; }
    public TestBonfire testBonfire() { return testBonfire; }
    public SneakTap sneakTap() { return sneakTap; }
    public FoeScaling foes() { return foes; }

    /** 지금 세계 설정의 난이도 (5.7, 설정이 없으면 difficulty.default). */
    public Config.Difficulty difficulty() {
        var s = worldState == null ? null : worldState.get();
        return cfg.difficulty(s == null ? null : s.difficulty());
    }
}
