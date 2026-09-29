// Minimal Luau runner for testing pure Roblox modules outside Studio.
// Exposes: readfile(path) -> string?, compile(src, chunkname) -> function (errors on syntax error),
// listdir(path) -> {string}. The test harness (written in Luau) builds a fake `script`/`require`.
use mlua::{Lua, Result};

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let path = &args[1];
    let lua = Lua::new();
    let g = lua.globals();
    g.set("readfile", lua.create_function(|_, p: String| Ok(std::fs::read_to_string(p).ok()))?)?;
    g.set("listdir", lua.create_function(|_, p: String| {
        let mut v: Vec<String> = match std::fs::read_dir(&p) {
            Ok(rd) => rd.filter_map(|e| e.ok()).map(|e| e.file_name().to_string_lossy().into_owned()).collect(),
            Err(_) => vec![],
        };
        v.sort();
        Ok(v)
    })?)?;
    g.set("compile", lua.create_function(|lua, (src, name): (String, String)| {
        lua.load(&src).set_name(format!("@{name}")).into_function()
    })?)?;
    let argv: Vec<String> = args[2..].to_vec();
    g.set("ARGS", argv)?;
    let src = std::fs::read_to_string(path).expect("read script");
    if let Err(e) = lua.load(&src).set_name(format!("@{path}")).exec() {
        eprintln!("{e}");
        std::process::exit(1);
    }
    Ok(())
}
