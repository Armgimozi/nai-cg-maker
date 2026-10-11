package kr.souls;

import org.bukkit.configuration.file.YamlConfiguration;

import java.io.File;

/** 시험이 읽는 저장소 파일 (gradle test 는 plugin/ 에서 돈다). */
public final class TestFiles {
    private TestFiles() {}

    public static File resource(String rel) {
        File f = new File("src/main/resources/" + rel);
        if (!f.isFile()) throw new IllegalStateException("없는 파일: " + f.getAbsolutePath());
        return f;
    }

    public static YamlConfiguration yaml(String rel) {
        return YamlConfiguration.loadConfiguration(resource(rel));
    }
}
