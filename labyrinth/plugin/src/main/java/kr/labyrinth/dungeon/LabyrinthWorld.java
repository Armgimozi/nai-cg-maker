package kr.labyrinth.dungeon;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;
import kr.labyrinth.core.Log;
import org.bukkit.Bukkit;
import org.bukkit.Difficulty;
import org.bukkit.GameRule;
import org.bukkit.GameRules;
import org.bukkit.World;
import org.bukkit.WorldCreator;
import org.bukkit.entity.SpawnCategory;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * labyrinth_world (공허) 만들기/불러오기 + 이전 세션 잔여 블록 정리 + 더러운 슬롯 기록.
 * 정리는 이 월드 폴더(이름이 정확히 같고 메인 월드가 아닌 것)의 region/entities/poi 만 지운다.
 */
final class LabyrinthWorld {

    private final JavaPlugin plugin;
    private final String name;
    private final File stateFile;
    private final List<Integer> dirtySlots = new ArrayList<>();
    private World world;

    LabyrinthWorld(JavaPlugin plugin, String name) {
        this.plugin = plugin;
        this.name = name;
        this.stateFile = new File(plugin.getDataFolder(), "dungeon-state.yml");
    }

    World world() { return world; }

    String name() { return name; }

    /** 청소가 안 된(이전 세션이 남긴) 슬롯 — 배정하지 않는다. */
    List<Integer> dirtySlots() { return dirtySlots; }

    World loadOrCreate(boolean resetOnStartup) {
        YamlConfiguration st = YamlConfiguration.loadConfiguration(stateFile);
        dirtySlots.clear();
        dirtySlots.addAll(st.getIntegerList("dirty_slots"));
        World loaded = Bukkit.getWorld(name);
        if (loaded == null && resetOnStartup) {
            String recorded = st.getString("world_folder", "");
            File folder = recorded == null || recorded.isBlank() ? new File(Bukkit.getWorldContainer(), name) : new File(recorded);
            if (safeToReset(folder)) {
                int n = 0;
                for (String sub : new String[] {"region", "entities", "poi"}) n += deleteTree(new File(folder, sub).toPath());
                if (n > 0) Log.info("미궁 월드 잔여 지역 파일 " + n + "개 정리 (" + folder.getName() + ")");
                dirtySlots.clear();
            }
        }
        if (loaded == null) {
            WorldCreator wc = new WorldCreator(name)
                    .environment(World.Environment.NORMAL)
                    .generator(new VoidGenerator())
                    .generateStructures(false);
            loaded = wc.createWorld();
        }
        world = loaded;
        if (world != null) {
            applyRules(world);
            save(world.getWorldFolder().getAbsolutePath());
        }
        return world;
    }

    private boolean safeToReset(File folder) {
        try {
            if (!folder.isDirectory() || !folder.getName().equals(name)) return false;
            if (!Bukkit.getWorlds().isEmpty()) {
                File main = Bukkit.getWorlds().get(0).getWorldFolder().getCanonicalFile();
                File f = folder.getCanonicalFile();
                if (f.equals(main) || main.toPath().startsWith(f.toPath())) return false;
            }
            File container = Bukkit.getWorldContainer().getCanonicalFile();
            return !folder.getCanonicalFile().equals(container);
        } catch (IOException e) {
            return false;
        }
    }

    private static int deleteTree(Path dir) {
        if (!Files.isDirectory(dir)) return 0;
        int[] count = {0};
        try (Stream<Path> s = Files.walk(dir)) {
            s.sorted(Comparator.reverseOrder()).forEach(p -> {
                try {
                    if (Files.isRegularFile(p)) count[0]++;
                    Files.deleteIfExists(p);
                } catch (IOException e) {
                    Log.warn("미궁 월드 파일 삭제 실패: " + p.getFileName());
                }
            });
        } catch (IOException e) {
            Log.warn("미궁 월드 정리 실패: " + e.getMessage());
        }
        return count[0];
    }

    static void applyRules(World w) {
        rule(w, GameRules.ADVANCE_TIME, false);
        rule(w, GameRules.ADVANCE_WEATHER, false);
        rule(w, GameRules.SPAWN_MOBS, false);
        rule(w, GameRules.SPAWN_MONSTERS, false);
        rule(w, GameRules.SPAWN_PATROLS, false);
        rule(w, GameRules.SPAWN_PHANTOMS, false);
        rule(w, GameRules.SPAWN_WANDERING_TRADERS, false);
        rule(w, GameRules.SPAWN_WARDENS, false);
        rule(w, GameRules.RAIDS, false);
        rule(w, GameRules.FIRE_SPREAD_RADIUS_AROUND_PLAYER, 0);
        rule(w, GameRules.MOB_GRIEFING, false);
        rule(w, GameRules.SPREAD_VINES, false);
        rule(w, GameRules.RANDOM_TICK_SPEED, 0);
        rule(w, GameRules.KEEP_INVENTORY, true);
        rule(w, GameRules.IMMEDIATE_RESPAWN, true);
        rule(w, GameRules.SHOW_ADVANCEMENT_MESSAGES, false);
        rule(w, GameRules.SHOW_DEATH_MESSAGES, false);
        rule(w, GameRules.SPECTATORS_GENERATE_CHUNKS, false);
        rule(w, GameRules.PVP, false);
        rule(w, GameRules.LOCATOR_BAR, false);
        rule(w, GameRules.SPAWNER_BLOCKS_WORK, false);
        w.setTime(18000);
        w.setStorm(false);
        w.setThundering(false);
        for (SpawnCategory c : SpawnCategory.values()) {
            if (c == SpawnCategory.MISC) continue;
            try {
                w.setSpawnLimit(c, 0);
            } catch (Exception ignored) {
                // 일부 분류는 설정 불가
            }
        }
        w.setDifficulty(Difficulty.NORMAL);
    }

    private static <T> void rule(World w, GameRule<T> rule, T value) {
        try {
            w.setGameRule(rule, value);
        } catch (Throwable t) {
            Log.warnOnce("gamerule:" + rule, "[미궁] 게임 규칙 설정 실패: " + rule + " (" + t.getMessage() + ")");
        }
    }

    void markDirty(int slot) {
        if (!dirtySlots.contains(slot)) dirtySlots.add(slot);
        saveAsync();
    }

    void markClean(int slot) {
        if (dirtySlots.remove((Integer) slot)) saveAsync();
    }

    private void saveAsync() {
        String folder = world == null ? "" : world.getWorldFolder().getAbsolutePath();
        save(folder);
    }

    private void save(String folder) {
        YamlConfiguration st = new YamlConfiguration();
        st.set("world_folder", folder);
        st.set("dirty_slots", new ArrayList<>(dirtySlots));
        try {
            st.save(stateFile);
        } catch (IOException e) {
            Log.warn("dungeon-state.yml 저장 실패: " + e.getMessage());
        }
    }
}
