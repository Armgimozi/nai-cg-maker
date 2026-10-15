package kr.labyrinth;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.bosses.BossesModule;
import kr.labyrinth.classes.ClassesModule;
import kr.labyrinth.core.EntityJanitor;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.SetupListener;
import kr.labyrinth.dungeon.DungeonModule;
import kr.labyrinth.items.ItemsModule;
import kr.labyrinth.mobs.MobsModule;
import kr.labyrinth.pvp.PvpModule;
import kr.labyrinth.titles.TitlesModule;
import kr.labyrinth.ui.BasicHudService;
import kr.labyrinth.ui.MenuListener;
import kr.labyrinth.ui.UiModule;
import kr.labyrinth.village.VillageModule;
import org.bukkit.Bukkit;
import org.bukkit.plugin.java.JavaPlugin;

/**
 * 미궁 라비린스 플러그인 진입점. onEnable: 설정·콘텐츠 로드 → 모듈 enable(순서대로) / onDisable: 역순 disable + 저장.
 * 모듈 순서: core(janitor·records·data·stats·levels·combat·pack) → 팀 모듈(items·classes·mobs·dungeon·bosses·titles·ui·pvp)
 * → death(인벤세이브) → village → setup → commands(마지막: 다른 모듈이 붙인 하위 명령까지 등록).
 */
public final class LabyrinthPlugin extends JavaPlugin {

    private Services services;
    private final List<Module> modules = new ArrayList<>();
    private final List<Module> enabled = new ArrayList<>();

    @Override
    public void onEnable() {
        Log.init(getLogger());
        saveDefaultConfig();
        services = new Services(this);
        services.loadSettings();
        services.loadContent();

        Bukkit.getPluginManager().registerEvents(new MenuListener(), this);

        modules.add(new EntityJanitor(services));
        modules.add(services.records());
        modules.add(services.data());
        modules.add(services.stats());
        modules.add(services.levels());
        modules.add(services.damage());
        modules.add(services.pack());
        // ── 팀 모듈: 각 담당자가 자기 XxxModule.enable() 에서 services.setXxx(...) 로 실제 구현을 넣는다 ──
        modules.add(new ItemsModule(services));
        modules.add(new ClassesModule(services));
        modules.add(new MobsModule(services));
        DungeonModule dungeon = new DungeonModule(services);
        modules.add(dungeon);
        modules.add(new BossesModule(services));
        modules.add(new TitlesModule(services));
        modules.add(new UiModule(services));
        modules.add(new PvpModule(services));
        modules.add(new kr.labyrinth.core.DeathKeep(services)); // 인벤세이브 (config death) — 미궁 밖 모든 월드
        // 미리 지은 마을 (주 월드에 labyrinth-village.yml 이 있을 때만 켜짐) — dungeon·ui 뒤, setup 앞
        modules.add(new VillageModule(services, dungeon::forgetSavedEntrance));
        // ──────────────────────────────────────────────────────────────────────────
        modules.add(new SetupListener(services));
        modules.add(services.commands());
        modules.add(new kr.labyrinth.core.ServerListListener(services));

        for (Module m : modules) {
            try {
                m.enable();
                enabled.add(m);
            } catch (Throwable t) {
                Log.error("모듈 '" + m.name() + "' 켜기 실패 — 이 모듈 없이 계속합니다", t);
            }
        }
        if (services.hud() instanceof BasicHudService basic) basic.start();
        getLogger().info("미궁 라비린스 활성화 (" + enabled.size() + "/" + modules.size() + " 모듈)");
    }

    @Override
    public void onDisable() {
        for (int i = enabled.size() - 1; i >= 0; i--) {
            Module m = enabled.get(i);
            try {
                m.disable();
            } catch (Throwable t) {
                Log.error("모듈 '" + m.name() + "' 끄기 실패", t);
            }
        }
        if (services != null && services.hud() instanceof BasicHudService basic) basic.stop();
        enabled.clear();
        modules.clear();
        Services.clear();
    }

    /** 모든 켜진 모듈의 reload() (Services#reload 에서 호출). */
    void reloadModules() {
        for (Module m : enabled) {
            try {
                m.reload();
            } catch (Throwable t) {
                Log.error("모듈 '" + m.name() + "' 다시 읽기 실패", t);
            }
        }
    }

    public Services services() { return services; }
}
