package kr.augsky;

import kr.augsky.altar.AltarService;
import kr.augsky.altar.Menus;
import kr.augsky.augment.AugmentListener;
import kr.augsky.augment.AugmentRegistry;
import kr.augsky.augment.AugmentService;
import kr.augsky.augment.PlayerData;
import kr.augsky.augment.PlayerDataStore;
import kr.augsky.cmd.Commands;
import kr.augsky.item.CustomItems;
import kr.augsky.item.ItemGuard;
import kr.augsky.item.Recipes;
import kr.augsky.map.MapBuilder;
import kr.augsky.mob.MobManager;
import kr.augsky.mob.MobRegistry;
import kr.augsky.nether.NetherService;
import kr.augsky.nether.VoidNether;
import kr.augsky.pack.PackService;
import kr.augsky.skill.Allies;
import kr.augsky.skill.Cooldowns;
import kr.augsky.skill.HitEffects;
import kr.augsky.skill.Mechanics;
import kr.augsky.skill.SkillRegistry;
import kr.augsky.util.Fx;
import kr.augsky.util.Items;
import kr.augsky.weapon.WeaponListener;
import kr.augsky.weapon.WeaponRegistry;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.PluginCommand;
import org.bukkit.configuration.Configuration;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.generator.ChunkGenerator;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;

public final class AugSky extends JavaPlugin {
    /**
     * 콘텐츠 YAML 의 판. 예전 파일을 그대로 두면 맞지 않을 만큼 바꿨을 때 올린다
     * (2: 무기 스킬 정리·클릭 조합, 3: 전투 효과를 확률 대신 N번째 공격마다로 바꾼 설명, 탱크엔진 증강,
     * 4: 조합법 재설계(섬 재료, 같은 종류만 강화), 안내서에서 위치 힌트 제거, 자연 스폰 교체에 허스크·스트레이,
     * 5: 안내서에 섬 도감. 4 판 jar 가 옛 안내서로 한 번 배포되어서, 그 서버에도 새 안내서가 가도록 다시 올린다,
     * 6: 하늘 네더 (안내서에 네더 하늘 쪽과 화염 섬 이름 정리, 지옥 임프 설명),
     * 7: 제단 수와 배치 (하늘 18곳 + 하늘 네더 6곳, 안내서의 제단 수)).
     */
    private static final int CONTENT_VERSION = 7;
    private static final List<String> CONTENT_FILES = List.of("augments.yml", "weapons.yml", "skills.yml", "mobs.yml", "items.yml", "armor.yml");

    private SkillRegistry skills;
    private WeaponRegistry weapons;
    private CustomItems items;
    private Recipes recipes;
    private AugmentService augments;
    private MobManager mobs;
    private AltarService altars;
    private Menus menus;
    private Allies allies;
    private Cooldowns cooldowns;
    private PackService pack;
    private MapBuilder mapBuilder;
    private WeaponListener weaponListener;
    private AugmentRegistry augmentRegistry;
    private MobRegistry mobRegistry;
    private kr.augsky.armor.ArmorService armor;
    private NetherService nether;

    @Override
    public void onEnable() {
        Keys.init(this);
        Fx.setLogger(getLogger());
        HitEffects.setLogger(getLogger());
        Mechanics.setLogger(getLogger());
        saveDefaultConfig();
        extractContent();

        cooldowns = new Cooldowns();
        skills = new SkillRegistry(getLogger());
        weapons = new WeaponRegistry(this);
        items = new CustomItems(this);
        recipes = new Recipes(this);
        augmentRegistry = new AugmentRegistry(getLogger());
        augments = new AugmentService(this, augmentRegistry, new PlayerDataStore(getDataFolder(), getLogger()));
        mobRegistry = new MobRegistry(getLogger());
        armor = new kr.augsky.armor.ArmorService(this);
        loadContent();

        allies = new Allies(this);
        menus = new Menus(this);
        mobs = new MobManager(this, mobRegistry);
        altars = new AltarService(this);
        weaponListener = new WeaponListener(this);
        pack = new PackService(this);
        mapBuilder = new MapBuilder(this);
        nether = new NetherService(this);

        var pm = getServer().getPluginManager();
        pm.registerEvents(allies, this);
        pm.registerEvents(menus, this);
        pm.registerEvents(mobs, this);
        pm.registerEvents(altars, this);
        pm.registerEvents(weaponListener, this);
        pm.registerEvents(new AugmentListener(this), this);
        pm.registerEvents(new ItemGuard(this), this);
        pm.registerEvents(pack, this);
        pm.registerEvents(armor, this);
        pm.registerEvents(nether, this);

        Commands cmds = new Commands(this);
        for (String c : List.of("augment", "augspawn", "weapons", "armorcodex", "augadmin")) {
            PluginCommand pc = getCommand(c);
            if (pc != null) {
                pc.setExecutor(cmds);
                pc.setTabCompleter(cmds);
            }
        }

        pack.start();
        nether.start();
        Bukkit.getScheduler().runTask(this, () -> {
            altars.scanLoaded();
            altars.checkMap();
            mobs.scanLoaded();
            for (Player p : Bukkit.getOnlinePlayers()) {
                augments.refresh(p);
                weaponListener.refreshItems(p);
            }
        });
        getLogger().info("증강 스카이블럭 준비 완료");
    }

    @Override
    public void onDisable() {
        if (augments != null) augments.store().saveAll();
        if (allies != null) allies.removeAll();
        if (mobs != null) mobs.removeBars();
        if (pack != null) pack.stop();
    }

    /**
     * 콘텐츠 YAML 을 꺼낸다. 파일이 없을 때만 꺼내므로 예전 서버에는 옛 파일이 남는다.
     * 그래서 판이 올라가면 옛 파일을 old-content-v{옛 판}/ 으로 옮겨 두고(지우지 않는다) 새로 꺼낸다.
     */
    private void extractContent() {
        File dir = getDataFolder();
        File verFile = new File(dir, "content-version.txt");
        int stored = 0;
        if (verFile.exists()) {
            try {
                stored = Integer.parseInt(Files.readString(verFile.toPath(), StandardCharsets.UTF_8).trim());
            } catch (IOException | NumberFormatException ex) {
                stored = 0;
            }
        }
        boolean upgraded = true;
        if (stored < CONTENT_VERSION) {
            List<String> old = new ArrayList<>();
            for (String f : CONTENT_FILES) if (new File(dir, f).exists()) old.add(f);
            if (!old.isEmpty()) upgraded = backupContent(dir, old, Math.max(1, stored));
        }
        for (String f : CONTENT_FILES) {
            if (!new File(dir, f).exists()) saveResource(f, false);
        }
        // 옮기다 실패했으면 판을 올리지 않아 다음에 다시 시도한다
        if (upgraded && stored < CONTENT_VERSION) {
            try {
                Files.writeString(verFile.toPath(), CONTENT_VERSION + "\n", StandardCharsets.UTF_8);
            } catch (IOException ex) {
                getLogger().warning("content-version.txt 를 쓰지 못했습니다: " + ex.getMessage());
            }
        }
    }

    private boolean backupContent(File dir, List<String> files, int fromVersion) {
        File backup = new File(dir, "old-content-v" + fromVersion);
        for (int n = 2; backup.exists(); n++) backup = new File(dir, "old-content-v" + fromVersion + "-" + n);
        List<String> moved = new ArrayList<>();
        try {
            Files.createDirectories(backup.toPath());
            for (String f : files) {
                Files.move(new File(dir, f).toPath(), new File(backup, f).toPath());
                moved.add(f);
            }
        } catch (IOException ex) {
            // 옛 파일과 새 파일이 섞이면 스킬 이름이 어긋나므로, 옮긴 것을 되돌려 옛 판 그대로 쓴다
            for (String f : moved) {
                try {
                    Files.move(new File(backup, f).toPath(), new File(dir, f).toPath());
                } catch (IOException ignored) {
                    // 되돌리지 못한 파일은 백업 폴더에 남아 있다
                }
            }
            getLogger().warning("예전 콘텐츠 파일을 " + backup.getName() + "/ 로 옮기지 못해 그대로 씁니다: " + ex.getMessage());
            return false;
        }
        String bookNote = replaceGuideBook(dir, backup) ? " (config.yml 은 그 폴더에 복사해 두고 guide-book 만 새 안내서로 바꿈)" : "";
        getLogger().info("콘텐츠가 새 판(v" + CONTENT_VERSION + ")으로 바뀌어 예전 " + String.join(", ", files) + " 을 "
                + backup.getName() + "/ 에 옮겨 두고 새로 꺼냈습니다" + bookNote + ". 고친 내용이 있으면 그 폴더에서 옮겨 오세요.");
        return true;
    }

    /**
     * 안내서 글도 콘텐츠 설명이라 같이 바꾼다. 나머지 설정은 그대로 두고, 새로 생긴 설정 묶음만 기본값으로 더한다.
     * 먼저 config.yml 을 백업 폴더에 복사하고, 읽히지 않는 config.yml 은 건드리지 않는다
     * (getConfig() 는 깨진 파일을 빈 설정으로 읽으므로, 그대로 저장하면 다른 설정이 모두 날아간다).
     */
    private boolean replaceGuideBook(File dir, File backup) {
        Configuration defs = getConfig().getDefaults();
        List<String> book = defs == null ? List.of() : defs.getStringList("guide-book");
        File cfgFile = new File(dir, "config.yml");
        if (book.isEmpty() || !cfgFile.exists()) return false;
        try {
            Files.copy(cfgFile.toPath(), new File(backup, "config.yml").toPath());
        } catch (IOException ex) {
            getLogger().warning("config.yml 을 " + backup.getName() + "/ 에 복사하지 못해 안내서 글을 그대로 둡니다: " + ex.getMessage());
            return false;
        }
        YamlConfiguration cfg = new YamlConfiguration();
        try {
            cfg.load(cfgFile);
        } catch (IOException | InvalidConfigurationException ex) {
            getLogger().warning("config.yml 을 읽지 못해 안내서 글을 바꾸지 않았습니다. 파일을 고친 뒤 guide-book 을 플러그인 jar 안의 config.yml 내용으로 바꿔 주세요: " + ex.getMessage());
            return false;
        }
        cfg.set("guide-book", book);
        // 새 판에서 생긴 설정 묶음(예: nether)은 기본값과 설명째 넣어 둔다 (없어도 기본값으로 돌지만, 고칠 수 있게 보이도록)
        for (String key : defs.getKeys(false)) {
            if (cfg.contains(key)) continue;
            if (defs.get(key) instanceof ConfigurationSection sec) {
                for (String sub : sec.getKeys(true)) if (!sec.isConfigurationSection(sub)) cfg.set(key + "." + sub, sec.get(sub));
                for (String sub : sec.getKeys(true)) cfg.setComments(key + "." + sub, defs.getComments(key + "." + sub));
            } else {
                cfg.set(key, defs.get(key));
            }
            cfg.setComments(key, defs.getComments(key));
        }
        try {
            cfg.save(cfgFile);
        } catch (IOException ex) {
            getLogger().warning("config.yml 에 새 안내서 글을 쓰지 못했습니다: " + ex.getMessage());
            return false;
        }
        reloadConfig();
        return true;
    }

    private YamlConfiguration yml(String name) {
        File f = new File(getDataFolder(), name);
        YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
        // 사용자가 지운 항목은 jar 기본값으로 채우지 않는다. 파일이 깨졌을 때만 기본값을 쓴다
        if (y.getKeys(false).isEmpty() && getResource(name) != null) {
            y = YamlConfiguration.loadConfiguration(new InputStreamReader(getResource(name), StandardCharsets.UTF_8));
        }
        return y;
    }

    private void loadContent() {
        skills.load(yml("skills.yml"));
        items.load(yml("items.yml"));
        weapons.load(yml("weapons.yml"));
        armor.load(yml("armor.yml"));
        augmentRegistry.load(yml("augments.yml"));
        mobRegistry.load(yml("mobs.yml"));
        recipes.registerAll();
    }

    public void reloadContent() {
        reloadConfig();
        loadContent();
        // 바뀐 조합법과 레시피 책을 접속 중인 플레이어에게 다시 보낸다
        Bukkit.updateRecipes();
        for (Player p : Bukkit.getOnlinePlayers()) {
            augments.refresh(p);
            p.discoverRecipes(recipes.keys());
            // 무기 설명·수치와 안내서 글은 아이템에 박혀 있으므로 바뀐 정의로 다시 쓴다
            weaponListener.refreshItems(p);
        }
    }

    /** 처음 들어온 플레이어에게 안내서와 시작 보급을 준다. */
    public void starterKit(Player p) {
        PlayerData d = augments.data(p);
        if (d.starterGiven) return;
        d.starterGiven = true;
        Items.give(p, items.guideBook());
        for (String spec : getConfig().getStringList("starter.items")) {
            String[] parts = spec.split("\\*");
            int n = parts.length > 1 ? Integer.parseInt(parts[1].trim()) : 1;
            ItemStack it = items.spec(parts[0].trim(), n);
            if (it != null) Items.give(p, it);
        }
        augments.store().save(d);
        p.sendMessage(kr.augsky.util.Text.mm("<#ffcc55>✦ 증강 스카이블럭에 오신 걸 환영합니다! <gray>안내서와 시작 보급을 받았습니다."));
    }

    /** bukkit.yml 의 generator: AugmentSkyblock:nether (또는 하늘 네더 폴더를 다른 플러그인이 열 때) 는 빈 네더 생성기. */
    @Override
    public ChunkGenerator getDefaultWorldGenerator(String worldName, String id) {
        if ("nether".equals(id) || worldName.endsWith("_augsky_nether")) return new VoidNether();
        return null;
    }

    /** 제단·둥지 기록을 볼 월드: 하늘 네더에 있으면 하늘. */
    public World home(World w) {
        return nether != null && nether.isSky(w) ? Bukkit.getWorlds().get(0) : w;
    }

    public Location spawnLocation() {
        World w = Bukkit.getWorlds().get(0);
        return w.getSpawnLocation().add(0.5, 0, 0.5);
    }

    public SkillRegistry skills() { return skills; }
    public WeaponRegistry weapons() { return weapons; }
    public CustomItems items() { return items; }
    public Recipes recipes() { return recipes; }
    public AugmentService augments() { return augments; }
    public MobManager mobs() { return mobs; }
    public AltarService altars() { return altars; }
    public Menus menus() { return menus; }
    public Allies allies() { return allies; }
    public Cooldowns cooldowns() { return cooldowns; }
    public PackService pack() { return pack; }
    public MapBuilder mapBuilder() { return mapBuilder; }
    public WeaponListener weaponListener() { return weaponListener; }
    public kr.augsky.armor.ArmorService armor() { return armor; }
    public NetherService nether() { return nether; }
}
