package kr.souls;

import io.papermc.paper.plugin.lifecycle.event.types.LifecycleEvents;
import kr.souls.cmd.SoulsCommands;
import kr.souls.cmd.TestCommands;
import kr.souls.combat.CombatState;
import kr.souls.combat.Roll;
import kr.souls.combat.Stamina;
import kr.souls.combat.TestHits;
import kr.souls.hud.Glyphs;
import kr.souls.hud.Hud;
import kr.souls.hud.Titles;
import kr.souls.pack.PackService;
import kr.souls.progression.DeathFlow;
import kr.souls.skill.Cooldowns;
import kr.souls.skill.HitEffects;
import kr.souls.skill.Mechanics;
import kr.souls.skill.SkillRegistry;
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
 * 스퀘어 소울 (Square Soul). 혼자 하는 소울류 서버 플러그인. 지금 판은 M0 (기반과 점검, 14절).
 * 데이터팩은 부트스트래퍼(SoulsBootstrap)가 세계를 읽기 전에 싣는다. 켜는 순서는 12.3 을 따른다.
 */
public final class Souls extends JavaPlugin {
    /** 켤 때 쓸어 내는 남은 물체 태그 (플러그인이 만든 물체는 하나도 저장하지 않는다) */
    public static final Set<String> SWEEP_TAGS = Set.of(Mechanics.FX_TAG, "souls_rig", TestHits.ENT_TAG);

    private Config cfg;
    private Content content;
    private SkillRegistry skills;
    private Cooldowns cooldowns;
    private WorldService worlds;
    private Ticker ticker;
    private Stamina stamina;
    private Roll roll;
    private Titles titles;
    private Hud hud;
    private DeathFlow death;
    private PackService pack;
    private TestHits testHits;

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
        // 4. 등록부 (M0: 스킬만. 그 뒤로 items → weapons → shields → armor → rings → enemies → bosses → encounters)
        cooldowns = new Cooldowns();
        skills = new SkillRegistry(getLogger());
        skills.load(content.yml("skills.yml"));
        // 5. 세계: 로비와 souls_world, 게임 규칙, 난이도, 필요하면 접속을 막고 짓기
        worlds = new WorldService(this);
        worlds.start();
        // 6. 서비스
        ticker = new Ticker(this);
        Glyphs.load(this);
        stamina = new Stamina(this);
        roll = new Roll(this);
        titles = new Titles();
        hud = new Hud(this);
        death = new DeathFlow(this);
        testHits = new TestHits();
        pack = new PackService(this);
        pack.start();
        ticker.add("stamina", stamina::tick);
        ticker.add("roll", roll::tick);
        ticker.add("hud", hud::tick);
        ticker.add("titles", titles::tick);
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
        getLifecycleManager().registerEventHandler(LifecycleEvents.COMMANDS, e -> {
            SoulsCommands.register(this, e.registrar());
            TestCommands.register(this, e.registrar());
        });
        // 8. 남은 물체 쓸기, 9. 접속 중인 플레이어 다시 읽기 (/reload 뒤)
        Bukkit.getScheduler().runTask(this, () -> {
            int swept = sweep();
            if (swept > 0) getLogger().info("남은 물체 " + swept + "개를 쓸어 냈습니다.");
            for (Player p : Bukkit.getOnlinePlayers()) {
                stamina.refill(p);
                hud.invalidate(p);
            }
        });
        getLogger().info("스퀘어 소울 (M0) 준비 완료" + (cfg.testMode ? " — 시험 모드" : ""));
    }

    @Override
    public void onDisable() {
        if (ticker != null) ticker.stop();
        if (pack != null) pack.stop();
        if (roll != null) roll.shutdown();
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
        // 시험 모드를 켜고 끄면 /soulstest 가 보이고 숨는다. 바뀐 설정 (hud.show-souls 같은 것) 으로 HUD 를 다시 그린다
        for (Player p : Bukkit.getOnlinePlayers()) {
            p.updateCommands();
            hud.invalidate(p);
        }
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
    public Cooldowns cooldowns() { return cooldowns; }
    public WorldService worlds() { return worlds; }
    public Ticker ticker() { return ticker; }
    public Stamina stamina() { return stamina; }
    public Roll roll() { return roll; }
    public Titles titles() { return titles; }
    public Hud hud() { return hud; }
    public DeathFlow death() { return death; }
    public PackService pack() { return pack; }
    public TestHits testHits() { return testHits; }
}
