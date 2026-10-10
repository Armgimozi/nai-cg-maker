plugins {
    java
}

group = "kr.souls"
version = "0.1.0"

repositories {
    mavenCentral()
    maven("https://repo.papermc.io/repository/maven-public/")
}

dependencies {
    compileOnly("io.papermc.paper:paper-api:1.21.11-R0.1-SNAPSHOT")
    // 순수 Java 시험 (13.1): 곡선·비용·피해 계산·짧은 누름 판정·프로필 JSON 은 Bukkit 없이 돈다.
    // 설정 기본값 시험만 YamlConfiguration (paper-api) 을 쓴다
    testImplementation(platform("org.junit:junit-bom:5.10.3"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
    testImplementation("io.papermc.paper:paper-api:1.21.11-R0.1-SNAPSHOT")
}

tasks.test {
    useJUnitPlatform()
    testLogging {
        events("failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.SHORT
    }
}

java {
    toolchain.languageVersion.set(JavaLanguageVersion.of(21))
}

tasks.withType<JavaCompile> {
    options.encoding = "UTF-8"
    options.release.set(21)
    // 1.21.4 → 1.21.11 에서 이름이 바뀌거나 없어질 API 를 빌드 때 보이게 한다
    options.compilerArgs.addAll(listOf("-Xlint:deprecation", "-Xlint:removal"))
}

tasks.processResources {
    filteringCharset = "UTF-8"
    // paper-plugin.yml (부트스트래퍼가 jar 안 데이터팩을 싣는다, 12.2). 버전만 채운다
    filesMatching("paper-plugin.yml") {
        expand("version" to project.version)
    }
}

tasks.jar {
    archiveFileName.set("Soulslike.jar")
}
