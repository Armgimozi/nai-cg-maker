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
