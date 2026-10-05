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
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.List;

public final class AugSky extends JavaPlugin {
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

    @Override
    public void onEnable() {
        Keys.init(this);
        Fx.setLogger(getLogger());
        HitEffects.setLogger(getLogger());
        Mechanics.setLogger(getLogger());
        saveDefaultConfig();
        for (String f : List.of("augments.yml", "weapons.yml", "skills.yml", "mobs.yml", "items.yml")) {
            if (!new File(getDataFolder(), f).exists()) saveResource(f, false);
        }

        cooldowns = new Cooldowns();
        skills = new SkillRegistry(getLogger());
        weapons = new WeaponRegistry(this);
        items = new CustomItems(this);
        recipes = new Recipes(this);
        augmentRegistry = new AugmentRegistry(getLogger());
        augments = new AugmentService(this, augmentRegistry, new PlayerDataStore(getDataFolder(), getLogger()));
        mobRegistry = new MobRegistry(getLogger());
        loadContent();

        allies = new Allies(this);
        menus = new Menus(this);
        mobs = new MobManager(this, mobRegistry);
        altars = new AltarService(this);
        weaponListener = new WeaponListener(this);
        pack = new PackService(this);
        mapBuilder = new MapBuilder(this);

        var pm = getServer().getPluginManager();
        pm.registerEvents(allies, this);
        pm.registerEvents(menus, this);
        pm.registerEvents(mobs, this);
        pm.registerEvents(altars, this);
        pm.registerEvents(weaponListener, this);
        pm.registerEvents(new AugmentListener(this), this);
        pm.registerEvents(new ItemGuard(this), this);
        pm.registerEvents(pack, this);

        Commands cmds = new Commands(this);
        for (String c : List.of("augment", "augspawn", "weapons", "augadmin")) {
            PluginCommand pc = getCommand(c);
            if (pc != null) {
                pc.setExecutor(cmds);
                pc.setTabCompleter(cmds);
            }
        }

        pack.start();
        Bukkit.getScheduler().runTask(this, () -> {
            altars.scanLoaded();
            mobs.scanLoaded();
            for (Player p : Bukkit.getOnlinePlayers()) augments.refresh(p);
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
        augmentRegistry.load(yml("augments.yml"));
        mobRegistry.load(yml("mobs.yml"));
        recipes.registerAll();
    }

    public void reloadContent() {
        reloadConfig();
        loadContent();
        for (Player p : Bukkit.getOnlinePlayers()) {
            augments.refresh(p);
            p.discoverRecipes(recipes.keys());
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
}
