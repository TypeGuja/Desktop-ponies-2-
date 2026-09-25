// src_rust/editor/editor_handlers.rs
//
// Обработчики IPC редактора пони. Данные пони конвертируются между моделью
// (model.rs, формат оригинального Desktop Ponies 1.69) и JSON, который
// ожидает интерфейс редактора (src_uiEditor). Сохранение пишет pony.ini в
// формате оригинала, сохраняя комментарии и нераспознанные строки.

use crate::loader::{load_pony_base, PonyCollection};
use crate::model::*;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::mpsc;
use std::sync::{Arc, Mutex};

pub type Shared = Arc<Mutex<PonyCollection>>;

/// Имя пони/файла из IPC подставляется в путь — без проверки ".." и разделителей
/// можно было бы выйти за пределы папки Ponies (например, удалить родительскую).
fn is_safe_name(name: &str) -> bool {
    !name.is_empty()
        && name != "."
        && name != ".."
        && !name.contains('/')
        && !name.contains('\\')
        && !name.contains(':')
        && !name.contains('\0')
}

pub fn handle_ipc(body: &str, loader: &Shared, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    if body == "editor:load_ponies" {
        send_ponies_list(loader, sender);
    } else if let Some(pony_name) = body.strip_prefix("editor:load_pony:") {
        send_pony_config(loader, pony_name, sender);
    } else if let Some(data) = body.strip_prefix("editor:save_pony:") {
        save_pony_config(data, loader, ponies_dir, sender);
    } else if let Some(data) = body.strip_prefix("pony:create:") {
        save_pony_config(data, loader, ponies_dir, sender);
    } else if let Some(data) = body.strip_prefix("gif:create:") {
        create_gif(data, ponies_dir, sender);
    } else if let Some(pony_name) = body.strip_prefix("editor:delete_pony:") {
        delete_pony(pony_name, loader, ponies_dir, sender);
    } else if let Some(data) = body.strip_prefix("gif:load:") {
        load_gif_for_editor(data, ponies_dir, sender);
    } else if let Some(path) = body.strip_prefix("trace:load_gif_path:") {
        handle_trace_gif_path(path, sender);
    } else if let Some(data) = body.strip_prefix("trace:load_gif:") {
        handle_trace_gif_base64(data, sender);
    } else if let Some(data) = body.strip_prefix("gif:save:") {
        save_gif_from_editor(data, ponies_dir, sender);
    } else if let Some(data) = body.strip_prefix("gif:list:") {
        list_gifs_for_pony(data, ponies_dir, sender);
    } else if body == "editor:close" {
        // Редактор — отдельный процесс (--editor): закрытие = выход.
        std::process::exit(0);
    } else {
        println!("[Editor] Unknown IPC: {}", body);
    }
}

fn send_ponies_list(loader: &Shared, sender: &mpsc::Sender<String>) {
    let c = loader.lock().unwrap();
    let ponies: Vec<String> = c.bases.iter().map(|b| b.directory.clone()).collect();
    // Гифка-превью каждой пони (как в меню выбора главной панели): имя каталога
    // -> путь относительно корня, отдаётся протоколом редактора (см. PREVIEW_ORIGIN).
    let previews: serde_json::Map<String, Value> = c
        .bases
        .iter()
        .filter_map(|b| crate::ui_state::preview_path(b, &c.root).map(|p| (b.directory.clone(), Value::String(p))))
        .collect();
    let _ = sender.send(
        json!({
            "type": "ponies_list",
            "data": ponies,
            "previews": previews,
            "preview_origin": crate::editor::editor_window::PREVIEW_ORIGIN,
        })
        .to_string(),
    );
}

// ---- Помощники разбора JSON (JS присылает числа то числом, то строкой)

fn jstr(v: &Value, default: &str) -> String {
    match v {
        Value::String(s) => s.clone(),
        Value::Number(n) => n.to_string(),
        Value::Bool(b) => b.to_string(),
        _ => default.to_string(),
    }
}
fn jf64(v: &Value, default: f64) -> f64 {
    match v {
        Value::Number(n) => n.as_f64().unwrap_or(default),
        Value::String(s) => s.trim().parse::<f64>().unwrap_or(default),
        _ => default,
    }
}
fn ji32(v: &Value, default: i32) -> i32 {
    match v {
        Value::Number(n) => n.as_i64().map(|x| x as i32).or_else(|| n.as_f64().map(|x| x as i32)).unwrap_or(default),
        Value::String(s) => s.trim().parse::<i32>().unwrap_or(default),
        _ => default,
    }
}
fn jbool(v: &Value, default: bool) -> bool {
    match v {
        Value::Bool(b) => *b,
        Value::String(s) => matches!(s.trim().to_lowercase().as_str(), "true" | "1" | "yes" | "on"),
        _ => default,
    }
}
fn jstr_list(v: &Value) -> Vec<String> {
    match v {
        Value::Array(a) => a.iter().filter_map(|x| x.as_str().map(String::from)).collect(),
        _ => Vec::new(),
    }
}
fn jpair(v: &Value) -> (i32, i32) {
    match v {
        Value::Array(a) if a.len() >= 2 => (ji32(&a[0], 0), ji32(&a[1], 0)),
        Value::String(s) => {
            let mut it = s.split(',');
            (
                it.next().and_then(|t| t.trim().parse().ok()).unwrap_or(0),
                it.next().and_then(|t| t.trim().parse().ok()).unwrap_or(0),
            )
        }
        _ => (0, 0),
    }
}

fn dir_name(d: Direction) -> &'static str {
    match d {
        Direction::TopLeft => "TopLeft",
        Direction::TopCenter => "TopCenter",
        Direction::TopRight => "TopRight",
        Direction::MiddleLeft => "MiddleLeft",
        Direction::MiddleCenter => "MiddleCenter",
        Direction::MiddleRight => "MiddleRight",
        Direction::BottomLeft => "BottomLeft",
        Direction::BottomCenter => "BottomCenter",
        Direction::BottomRight => "BottomRight",
        Direction::Random => "Random",
        Direction::RandomNotCenter => "RandomNotCenter",
    }
}

fn set_image(img: &mut SpriteImage, dir: &std::path::Path, file: &str) {
    if file.trim().is_empty() {
        img.path = String::new();
        img.size = (0, 0);
    } else {
        img.path = dir.join(file.trim()).to_string_lossy().to_string();
        img.update_size();
    }
}

fn behavior_to_json(b: &Behavior) -> Value {
    let rc = b.right_image.custom_center.unwrap_or((0, 0));
    let lc = b.left_image.custom_center.unwrap_or((0, 0));
    json!({
        "name": b.name, "probability": b.chance, "max_duration": b.max_duration, "min_duration": b.min_duration,
        "speed": b.speed, "sprite_right": b.right_image.file_name(), "sprite_left": b.left_image.file_name(),
        "movement": moves_to_ini(b.allowed_movement), "linked_behavior": b.linked_behavior,
        "start_speech": b.start_line, "end_speech": b.end_line, "skip": b.skip,
        "target_x": b.target_vector.0, "target_y": b.target_vector.1, "follow_target": b.follow_target,
        "auto_select_follow": b.auto_select_images_on_follow, "follow_stopped": b.follow_stopped,
        "follow_moving": b.follow_moving, "right_image_center": [rc.0, rc.1], "left_image_center": [lc.0, lc.1],
        "prevent_loop": b.do_not_repeat_image_animations, "group": b.group.to_string(),
        "follow_offset": match b.follow_offset { FollowOffsetType::Fixed => "Fixed", FollowOffsetType::Mirror => "Mirror" },
    })
}

fn behavior_from_json(b: &Value, dir: &std::path::Path) -> Behavior {
    let mut r = Behavior::new();
    r.name = jstr(&b["name"], "");
    r.chance = jf64(&b["probability"], 0.1).clamp(0.0, 1.0);
    r.max_duration = jf64(&b["max_duration"], 15.0).clamp(0.0, 300.0);
    r.min_duration = jf64(&b["min_duration"], 5.0).clamp(0.0, 300.0);
    if r.max_duration < r.min_duration {
        std::mem::swap(&mut r.max_duration, &mut r.min_duration);
    }
    r.speed = jf64(&b["speed"], 3.0).clamp(0.0, 30.0);
    set_image(&mut r.right_image, dir, &jstr(&b["sprite_right"], ""));
    set_image(&mut r.left_image, dir, &jstr(&b["sprite_left"], ""));
    r.allowed_movement = moves_from_any(&jstr(&b["movement"], "All")).unwrap_or(moves::ALL);
    r.linked_behavior = jstr(&b["linked_behavior"], "");
    r.start_line = jstr(&b["start_speech"], "");
    r.end_line = jstr(&b["end_speech"], "");
    r.skip = jbool(&b["skip"], false);
    r.target_vector = (ji32(&b["target_x"], 0), ji32(&b["target_y"], 0));
    r.follow_target = jstr(&b["follow_target"], "");
    r.auto_select_images_on_follow = jbool(&b["auto_select_follow"], true);
    r.follow_stopped = jstr(&b["follow_stopped"], "");
    r.follow_moving = jstr(&b["follow_moving"], "");
    let rc = jpair(&b["right_image_center"]);
    let lc = jpair(&b["left_image_center"]);
    r.right_image.custom_center = if rc == (0, 0) { None } else { Some(rc) };
    r.left_image.custom_center = if lc == (0, 0) { None } else { Some(lc) };
    r.do_not_repeat_image_animations = jbool(&b["prevent_loop"], false);
    r.group = ji32(&b["group"], 0).clamp(0, 100);
    r.follow_offset = if jstr(&b["follow_offset"], "").to_lowercase().contains("mirror") {
        FollowOffsetType::Mirror
    } else {
        FollowOffsetType::Fixed
    };
    r
}

fn speech_to_json(s: &Speech) -> Value {
    let files: Vec<String> = s
        .sound_file
        .iter()
        .map(|p| std::path::Path::new(p).file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default())
        .collect();
    json!({ "name": s.name, "text": s.text, "sound_files": files, "skip": s.skip, "group": s.group })
}

fn speech_from_json(s: &Value, dir: &std::path::Path) -> Speech {
    let files = jstr_list(&s["sound_files"]);
    let sound = files
        .iter()
        .find(|f| f.to_lowercase().ends_with(".mp3"))
        .or_else(|| files.first())
        .map(|f| dir.join(f.trim()).to_string_lossy().to_string());
    Speech {
        name: jstr(&s["name"], ""),
        text: jstr(&s["text"], ""),
        sound_file: sound,
        skip: jbool(&s["skip"], false),
        group: ji32(&s["group"], 0).clamp(0, 100),
    }
}

fn interaction_to_json(i: &InteractionBase) -> Value {
    json!({
        "name": i.name, "probability": i.chance, "proximity": i.proximity, "targets": i.target_names,
        "activation": i.activation.to_ini(), "behaviors": i.behavior_names, "reactivation_delay": i.reactivation_delay,
    })
}

fn interaction_from_json(i: &Value, initiator: &str) -> InteractionBase {
    InteractionBase {
        name: jstr(&i["name"], ""),
        initiator_name: initiator.to_string(),
        chance: jf64(&i["probability"], 0.0).clamp(0.0, 1.0),
        proximity: jf64(&i["proximity"], 125.0).clamp(0.0, 10000.0),
        target_names: jstr_list(&i["targets"]),
        activation: TargetActivation::from_ini(&jstr(&i["activation"], "One")).unwrap_or(TargetActivation::One),
        behavior_names: jstr_list(&i["behaviors"]),
        reactivation_delay: jf64(&i["reactivation_delay"], 60.0).clamp(0.0, 3600.0),
    }
}

fn effect_to_json(e: &EffectBase) -> Value {
    json!({
        "name": e.name, "linked": e.behavior_name, "sprite_right": e.right_image.file_name(),
        "sprite_left": e.left_image.file_name(), "duration": e.duration, "repeat_delay": e.repeat_delay,
        "placement_right": dir_name(e.placement_right), "centering_right": dir_name(e.centering_right),
        "placement_left": dir_name(e.placement_left), "centering_left": dir_name(e.centering_left),
        "follow": e.follow, "do_not_repeat_animations": e.do_not_repeat_image_animations,
    })
}

fn effect_from_json(e: &Value, dir: &std::path::Path) -> EffectBase {
    let mut r = EffectBase::new();
    r.name = jstr(&e["name"], "");
    r.behavior_name = jstr(&e["linked"], "");
    set_image(&mut r.right_image, dir, &jstr(&e["sprite_right"], ""));
    set_image(&mut r.left_image, dir, &jstr(&e["sprite_left"], ""));
    r.duration = jf64(&e["duration"], 5.0).clamp(0.0, 300.0);
    r.repeat_delay = jf64(&e["repeat_delay"], 0.0).clamp(0.0, 300.0);
    let d = |v: &Value| Direction::from_any(&jstr(v, "Center")).unwrap_or(Direction::Random);
    r.placement_right = d(&e["placement_right"]);
    r.centering_right = d(&e["centering_right"]);
    r.placement_left = d(&e["placement_left"]);
    r.centering_left = d(&e["centering_left"]);
    r.follow = jbool(&e["follow"], false);
    r.do_not_repeat_image_animations = jbool(&e["do_not_repeat_animations"], false);
    r
}

pub fn pony_to_json(b: &PonyBase) -> Value {
    let groups: HashMap<String, String> = b.behavior_groups.iter().map(|g| (g.number.to_string(), g.name.clone())).collect();
    json!({
        "name": b.directory, "display_name": b.display_name, "categories": b.tags, "tags": Vec::<String>::new(),
        "behaviors": b.behaviors.iter().map(behavior_to_json).collect::<Vec<_>>(),
        "speaks": b.speeches.iter().map(speech_to_json).collect::<Vec<_>>(),
        "interactions": b.interactions.iter().map(interaction_to_json).collect::<Vec<_>>(),
        "effects": b.effects.iter().map(effect_to_json).collect::<Vec<_>>(),
        "behavior_groups": groups,
    })
}

/// JSON редактора -> модель; existing даёт комментарии, нераспознанные строки и путь.
pub fn pony_from_json(v: &Value, existing: Option<&PonyBase>, ponies_dir: &std::path::Path) -> PonyBase {
    let name = v["name"].as_str().unwrap_or("unknown");
    let dir = existing.map(|e| e.path.clone()).unwrap_or_else(|| ponies_dir.join(name));
    let mut p = PonyBase::new(name, dir.clone());
    if let Some(e) = existing {
        p.comment_lines = e.comment_lines.clone();
        p.invalid_lines = e.invalid_lines.clone();
    }
    p.display_name = v["display_name"].as_str().filter(|s| !s.trim().is_empty()).unwrap_or(name).to_string();
    for t in jstr_list(&v["categories"]) {
        if !p.tags.iter().any(|x| ci_eq(x, &t)) && !t.is_empty() {
            p.tags.push(t);
        }
    }
    if let Some(obj) = v["behavior_groups"].as_object() {
        let mut gs: Vec<BehaviorGroup> = obj
            .iter()
            .filter_map(|(k, n)| Some(BehaviorGroup { number: k.trim().parse::<i32>().ok()?, name: n.as_str()?.to_string() }))
            .filter(|g| g.number != ANY_GROUP)
            .collect();
        gs.sort_by_key(|g| g.number);
        p.behavior_groups = gs;
    } else if let Some(e) = existing {
        p.behavior_groups = e.behavior_groups.clone();
    }
    let list = |k: &str| v[k].as_array().cloned().unwrap_or_default();
    p.behaviors = list("behaviors").iter().map(|b| behavior_from_json(b, &dir)).collect();
    p.speeches = list("speaks").iter().map(|s| speech_from_json(s, &dir)).collect();
    p.interactions = list("interactions").iter().map(|i| interaction_from_json(i, name)).collect();
    p.effects = list("effects").iter().map(|e| effect_from_json(e, &dir)).collect();
    p
}

fn send_pony_config(loader: &Shared, pony_name: &str, sender: &mpsc::Sender<String>) {
    let c = loader.lock().unwrap();
    if let Some(b) = c.bases.iter().find(|b| b.directory == pony_name) {
        let _ = sender.send(json!({ "type": "pony_config", "pony_name": pony_name, "data": pony_to_json(b) }).to_string());
    } else {
        let _ = sender.send(json!({ "type": "error", "message": format!("Pony '{}' not found", pony_name) }).to_string());
    }
}

/// Перечитывает Ponies с диска (редактор загружает всё, включая некорректные
/// поведения, чтобы их можно было исправить) и шлёт обновлённый список.
fn reload_and_send_list(loader: &Shared, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    {
        let mut c = loader.lock().unwrap();
        let root = ponies_dir.parent().map(|p| p.to_path_buf()).unwrap_or_default();
        *c = PonyCollection::load(&root, false);
    }
    send_ponies_list(loader, sender);
}

fn save_pony_config(data: &str, loader: &Shared, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    let Ok(v) = serde_json::from_str::<Value>(data) else {
        let _ = sender.send(json!({ "type": "save_error", "message": "Failed to parse config" }).to_string());
        return;
    };
    let name = v["name"].as_str().unwrap_or("unknown");
    if !is_safe_name(name) {
        let _ = sender.send(json!({ "type": "save_error", "message": format!("Invalid pony name '{}'", name) }).to_string());
        return;
    }
    let existing = loader.lock().unwrap().bases.iter().find(|b| b.directory == name).cloned();
    let pony = pony_from_json(&v, existing.as_ref(), ponies_dir);
    match pony.save() {
        Ok(_) => {
            let _ = sender.send(json!({ "type": "save_success", "message": format!("Pony '{}' saved", name) }).to_string());
            reload_and_send_list(loader, ponies_dir, sender);
        }
        Err(e) => {
            let _ = sender.send(json!({ "type": "save_error", "message": format!("Failed: {}", e) }).to_string());
        }
    }
}

fn delete_pony(pony_name: &str, loader: &Shared, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    if !is_safe_name(pony_name) {
        let _ = sender.send(json!({ "type": "error", "message": format!("Invalid pony name '{}'", pony_name) }).to_string());
        return;
    }
    let path = ponies_dir.join(pony_name);
    if path.exists() {
        match std::fs::remove_dir_all(&path) {
            Ok(_) => {
                let _ = sender.send(json!({ "type": "delete_success", "message": format!("Pony '{}' deleted", pony_name) }).to_string());
                reload_and_send_list(loader, ponies_dir, sender);
            }
            Err(e) => {
                let _ = sender.send(json!({ "type": "error", "message": format!("Failed to delete: {}", e) }).to_string());
            }
        }
    } else {
        let _ = sender.send(json!({ "type": "error", "message": format!("Pony '{}' not found", pony_name) }).to_string());
    }
}

fn list_gifs_for_pony(data: &str, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    let pony_path = ponies_dir.join(data);
    let mut gifs = Vec::new();
    if is_safe_name(data) && pony_path.exists() && pony_path.is_dir() {
        if let Ok(entries) = std::fs::read_dir(&pony_path) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().and_then(|e| e.to_str()) == Some("gif") {
                    if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                        gifs.push(name.to_string());
                    }
                }
            }
        }
    }
    let response = json!({ "type": "gif_list", "gifs": gifs, "pony_name": data });
    let _ = sender.send(response.to_string());
}

// ============================================================
// TRACE ОБРАБОТЧИКИ
// ============================================================

/// Обработчик загрузки внешней GIF по пути (основной способ)
fn handle_trace_gif_path(path_encoded: &str, sender: &mpsc::Sender<String>) {
    println!("[Editor] === TRACE LOAD GIF FROM PATH ===");

    // Декодируем URL-encoded путь
    let path = match urlencoding::decode(path_encoded) {
        Ok(p) => p.to_string(),
        Err(e) => {
            println!("[Editor] Path decode error: {}", e);
            let _ = sender.send(json!({
                "type": "trace_gif_error",
                "message": format!("Path decode error: {}", e)
            }).to_string());
            return;
        }
    };

    println!("[Editor] Path: {}", path);

    let gif_path = std::path::PathBuf::from(&path);
    if !gif_path.exists() {
        println!("[Editor] File not found: {}", path);
        let _ = sender.send(json!({
            "type": "trace_gif_error",
            "message": format!("File not found: {}", path)
        }).to_string());
        return;
    }

    // Декодируем GIF через существующий парсер
    match decode_gif_clean(&gif_path, true) {
        Ok((frames_data, width, height)) => {
            println!("[Editor] Trace decoded {} frames, {}x{}", frames_data.len(), width, height);

            let response = json!({
                "type": "trace_gif_data",
                "frames": frames_data,
                "width": width,
                "height": height
            });

            let _ = sender.send(response.to_string());
        }
        Err(e) => {
            println!("[Editor] Decode error: {}", e);
            let _ = sender.send(json!({
                "type": "trace_gif_error",
                "message": format!("GIF decode error: {}", e)
            }).to_string());
        }
    }
}

/// Обработчик загрузки внешней GIF через base64 (fallback)
fn handle_trace_gif_base64(base64_data: &str, sender: &mpsc::Sender<String>) {
    println!("[Editor] === TRACE LOAD GIF FROM BASE64 ===");
    println!("[Editor] Base64 data length: {}", base64_data.len());

    // Декодируем base64
    // ИСПРАВЛЕНО: в base64 0.21+ убрали свободные функции encode()/decode(),
    // теперь нужен Engine. Старый вызов base64::decode(...) не компилировался.
    use base64::{engine::general_purpose::STANDARD, Engine as _};
    let bytes = match STANDARD.decode(base64_data) {
        Ok(b) => b,
        Err(e) => {
            println!("[Editor] Base64 decode error: {}", e);
            let _ = sender.send(json!({
                "type": "trace_gif_error",
                "message": format!("Base64 decode error: {}", e)
            }).to_string());
            return;
        }
    };

    println!("[Editor] Decoded {} bytes", bytes.len());

    // Сохраняем во временный файл
    use std::fs::File;
    use std::io::Write;
    use std::env::temp_dir;
    use std::time::SystemTime;

    let temp_path = temp_dir().join(format!("trace_{}.gif", SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).map(|d| d.as_millis()).unwrap_or(0)));
    println!("[Editor] Temp file: {:?}", temp_path);

    if let Ok(mut file) = File::create(&temp_path) {
        if let Err(e) = file.write_all(&bytes) {
            let _ = sender.send(json!({
                "type": "trace_gif_error",
                "message": format!("Write error: {}", e)
            }).to_string());
            return;
        }
    } else {
        let _ = sender.send(json!({
            "type": "trace_gif_error",
            "message": "Failed to create temp file"
        }).to_string());
        return;
    }

    // Декодируем GIF через существующий парсер
    match decode_gif_clean(&temp_path, true) {
        Ok((frames_data, width, height)) => {
            println!("[Editor] Trace decoded {} frames, {}x{}", frames_data.len(), width, height);

            // Удаляем временный файл
            let _ = std::fs::remove_file(&temp_path);

            let response = json!({
                "type": "trace_gif_data",
                "frames": frames_data,
                "width": width,
                "height": height
            });

            let _ = sender.send(response.to_string());
        }
        Err(e) => {
            println!("[Editor] Decode error: {}", e);
            let _ = sender.send(json!({
                "type": "trace_gif_error",
                "message": format!("GIF decode error: {}", e)
            }).to_string());
        }
    }
}

// ============================================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С GIF
// ============================================================

fn clean_frame_artifacts(data: &mut [u8], width: u32, height: u32) {
    let w = width as usize;
    let h = height as usize;

    if data.len() != w * h * 4 {
        return;
    }

    let copy = data.to_vec();

    for y in 0..h {
        for x in 0..w {
            let idx = (y * w + x) * 4;

            if copy[idx + 3] == 0 {
                continue;
            }

            let mut opaque_neighbors = 0;

            for dy in -1..=1 {
                for dx in -1..=1 {
                    if dx == 0 && dy == 0 { continue; }

                    let nx = x as i32 + dx;
                    let ny = y as i32 + dy;

                    if nx >= 0 && nx < w as i32 && ny >= 0 && ny < h as i32 {
                        let nidx = (ny as usize * w + nx as usize) * 4;
                        if copy[nidx + 3] > 0 {
                            opaque_neighbors += 1;
                        }
                    }
                }
            }

            if opaque_neighbors < 2 {
                data[idx] = 0;
                data[idx + 1] = 0;
                data[idx + 2] = 0;
                data[idx + 3] = 0;
            }
        }
    }
}

fn decode_gif_clean(path: &PathBuf, clean: bool) -> Result<(Vec<serde_json::Value>, u32, u32), String> {
    use std::fs::File;
    use image::codecs::gif::GifDecoder;
    use image::AnimationDecoder;

    let file = File::open(path).map_err(|e| format!("Cannot open: {}", e))?;
    let decoder = GifDecoder::new(file).map_err(|e| format!("GIF decode error: {}", e))?;

    let frames = decoder.into_frames()
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("Frame error: {}", e))?;

    if frames.is_empty() {
        return Err("No frames in GIF".to_string());
    }

    let width = frames[0].buffer().width();
    let height = frames[0].buffer().height();

    println!("[GIF] Size: {}x{}, total frames: {}", width, height, frames.len());

    let mut frames_data = Vec::new();

    for (i, frame) in frames.into_iter().enumerate() {
        let (numer, denom) = frame.delay().numer_denom_ms();
        let delay_ms = if denom > 0 { (numer / denom).min(u16::MAX as u32) as u16 } else { 0 };

        let delay_cs = (delay_ms as f32 / 10.0).round() as u16;
        let final_delay = if delay_cs > 0 { delay_cs } else { 10 };

        let buffer = frame.into_buffer();

        println!("[GIF] Frame {}: delay_ms={}, delay_cs={}", i, delay_ms, final_delay);

        let mut rgba_bytes = Vec::with_capacity((width * height * 4) as usize);
        for pixel in buffer.pixels() {
            rgba_bytes.push(pixel.0[0]);
            rgba_bytes.push(pixel.0[1]);
            rgba_bytes.push(pixel.0[2]);
            rgba_bytes.push(pixel.0[3]);
        }

        // ИСПРАВЛЕНО: "чистка артефактов" удаляла каждый пиксель с менее чем
        // двумя непрозрачными соседями — то есть одиночные пиксели (блики в
        // глазах, кончики тонких линий) стирались из рисунка при ЗАГРУЗКЕ, а
        // затем навсегда терялись при сохранении. Для редактирования спрайта
        // чистка теперь отключена; она осталась только для трейс-подложки.
        if clean {
            clean_frame_artifacts(&mut rgba_bytes, width, height);
        }

        frames_data.push(serde_json::json!({
            "data": rgba_bytes,
            "delay": final_delay,
            "width": width,
            "height": height
        }));
    }

    println!("[GIF] Successfully decoded {} frames", frames_data.len());
    Ok((frames_data, width, height))
}

fn decode_gif_with_gif_lib(path: &PathBuf) -> Result<(Vec<serde_json::Value>, u32, u32), String> {
    use std::fs::File;
    use gif::{DecodeOptions, ColorOutput};

    let mut file = File::open(path).map_err(|e| format!("Cannot open: {}", e))?;

    let mut decoder = DecodeOptions::new();
    decoder.set_color_output(ColorOutput::RGBA);

    let mut gif = decoder.read_info(&mut file).map_err(|e| format!("GIF read error: {}", e))?;

    let width = gif.width() as u32;
    let height = gif.height() as u32;

    println!("[GIF Lib] Size: {}x{}", width, height);

    let mut frames_data = Vec::new();
    let mut frame_num = 0;

    let mut accumulated = vec![0u8; (width * height * 4) as usize];
    for i in (0..accumulated.len()).step_by(4) {
        accumulated[i + 3] = 0;
    }

    while let Some(frame) = gif.read_next_frame().map_err(|e| format!("Frame read error: {}", e))? {
        let delay = if frame.delay > 0 { frame.delay } else { 10 };
        let left = frame.left as u32;
        let top = frame.top as u32;
        let frame_width = frame.width as u32;
        let frame_height = frame.height as u32;

        println!("[GIF Lib] Frame {}: offset=({},{}), size={}x{}, delay={}cs",
                 frame_num, left, top, frame_width, frame_height, delay);

        for y in 0..frame_height {
            for x in 0..frame_width {
                let src_idx = ((y * frame_width + x) * 4) as usize;
                let dst_x = left + x;
                let dst_y = top + y;

                if dst_x < width && dst_y < height && src_idx + 3 < frame.buffer.len() {
                    let dst_idx = ((dst_y * width + dst_x) * 4) as usize;

                    let a = frame.buffer[src_idx + 3];

                    if a > 128 {
                        accumulated[dst_idx] = frame.buffer[src_idx];
                        accumulated[dst_idx + 1] = frame.buffer[src_idx + 1];
                        accumulated[dst_idx + 2] = frame.buffer[src_idx + 2];
                        accumulated[dst_idx + 3] = a;
                    }
                }
            }
        }

        let mut frame_copy = accumulated.clone();
        clean_frame_artifacts(&mut frame_copy, width, height);

        frames_data.push(serde_json::json!({
            "data": frame_copy,
            "delay": delay,
            "width": width,
            "height": height
        }));

        frame_num += 1;
    }

    if frames_data.is_empty() {
        return Err("No frames decoded".to_string());
    }

    println!("[GIF Lib] Successfully decoded {} frames", frames_data.len());
    Ok((frames_data, width, height))
}

fn deduplicate_frames(frames: &[serde_json::Value]) -> Vec<serde_json::Value> {
    let mut result = Vec::new();

    for (i, frame) in frames.iter().enumerate() {
        if i == 0 {
            result.push(frame.clone());
            continue;
        }

        let prev = &frames[i - 1];
        let prev_data = prev.get("data").and_then(|d| d.as_array());
        let curr_data = frame.get("data").and_then(|d| d.as_array());

        if let (Some(prev_arr), Some(curr_arr)) = (prev_data, curr_data) {
            let mut different = false;
            let check_len = prev_arr.len().min(curr_arr.len());

            for j in (0..check_len).step_by(4) {
                if prev_arr[j] != curr_arr[j] ||
                    prev_arr[j + 1] != curr_arr[j + 1] ||
                    prev_arr[j + 2] != curr_arr[j + 2] ||
                    prev_arr[j + 3] != curr_arr[j + 3] {
                    different = true;
                    break;
                }
            }

            if different {
                result.push(frame.clone());
            } else if let Some(last) = result.last_mut() {
                // ИСПРАВЛЕНО: одинаковые подряд кадры раньше просто выбрасывались
                // вместе со своей задержкой — "пауза" в анимации исчезала. Теперь
                // задержка дубликата прибавляется к предыдущему кадру.
                let extra = frame.get("delay").and_then(|d| d.as_u64()).unwrap_or(0);
                let base = last.get("delay").and_then(|d| d.as_u64()).unwrap_or(0);
                last["delay"] = json!(base + extra);
            }
        } else {
            result.push(frame.clone());
        }
    }

    result
}

fn load_gif_for_editor(data: &str, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    println!("[Editor] === LOAD GIF START ===");
    println!("[Editor] Loading GIF: {}", data);

    let parts: Vec<&str> = data.split(':').collect();

    if parts.len() >= 2 {
        let pony_name = parts[0];
        let sprite_name = parts[1];

        let sprite_name_clean = sprite_name.split('?').next().unwrap_or(sprite_name);
        if !is_safe_name(pony_name) || !is_safe_name(sprite_name_clean) {
            send_fallback_gif(sender);
            return;
        }
        let gif_path = ponies_dir.join(pony_name).join(sprite_name_clean);

        println!("[Editor] Looking for GIF at: {:?}", gif_path);
        println!("[Editor] File exists: {}", gif_path.exists());

        if gif_path.exists() {
            let result = decode_gif_clean(&gif_path, false);

            match result {
                Ok((frames_data, width, height)) => {
                    println!("[Editor] Decoded {} frames", frames_data.len());

                    let unique_frames = deduplicate_frames(&frames_data);
                    println!("[Editor] After dedup: {} frames", unique_frames.len());

                    let response = serde_json::json!({
                        "type": "gif_data",
                        "frames": unique_frames,
                        "width": width,
                        "height": height,
                        "current_frame": 0,
                        "sprite_name": sprite_name_clean,
                        "pony_name": pony_name
                    });

                    let response_str = response.to_string();
                    println!("[Editor] Sending response, size: {} bytes", response_str.len());
                    let _ = sender.send(response_str);
                    return;
                }
                Err(e) => {
                    println!("[Editor] Clean decode failed: {}, trying gif lib", e);

                    match decode_gif_with_gif_lib(&gif_path) {
                        Ok((frames_data, width, height)) => {
                            let unique_frames = deduplicate_frames(&frames_data);
                            let response = serde_json::json!({
                                "type": "gif_data",
                                "frames": unique_frames,
                                "width": width,
                                "height": height,
                                "current_frame": 0,
                                "sprite_name": sprite_name_clean,
                                "pony_name": pony_name
                            });
                            let _ = sender.send(response.to_string());
                            return;
                        }
                        Err(e2) => {
                            println!("[Editor] Gif lib decode also failed: {}", e2);
                        }
                    }
                }
            }
        } else {
            println!("[Editor] GIF not found at path: {:?}", gif_path);
        }
    }

    println!("[Editor] Sending fallback GIF");
    send_fallback_gif(sender);
}

fn send_fallback_gif(sender: &mpsc::Sender<String>) {
    let test_width = 128;
    let test_height = 128;
    let mut frames = Vec::new();

    let mut frame1 = vec![0u8; (test_width * test_height * 4) as usize];
    for y in 0..test_height {
        for x in 0..test_width {
            let idx = (y * test_width + x) * 4;
            if x > 32 && x < 96 && y > 32 && y < 96 {
                frame1[idx] = 255;
                frame1[idx + 1] = 0;
                frame1[idx + 2] = 0;
                frame1[idx + 3] = 255;
            } else {
                frame1[idx + 3] = 0;
            }
        }
    }
    frames.push(serde_json::json!({
        "data": frame1,
        "delay": 10,
        "width": test_width,
        "height": test_height
    }));

    let mut frame2 = vec![0u8; (test_width * test_height * 4) as usize];
    for y in 0..test_height {
        for x in 0..test_width {
            let idx = (y * test_width + x) * 4;
            if x > 32 && x < 96 && y > 32 && y < 96 {
                frame2[idx] = 0;
                frame2[idx + 1] = 0;
                frame2[idx + 2] = 255;
                frame2[idx + 3] = 255;
            } else {
                frame2[idx + 3] = 0;
            }
        }
    }
    frames.push(serde_json::json!({
        "data": frame2,
        "delay": 10,
        "width": test_width,
        "height": test_height
    }));

    let response = serde_json::json!({
        "type": "gif_data",
        "frames": frames,
        "width": test_width,
        "height": test_height,
        "current_frame": 0,
        "sprite_name": "debug_test",
        "pony_name": "debug"
    });
    let _ = sender.send(response.to_string());
    println!("[Editor] Sent fallback test pattern GIF with {} frames", frames.len());
}

fn save_gif_from_editor(data: &str, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    println!("[Editor] Saving GIF");
    if let Ok(gif_data) = serde_json::from_str::<serde_json::Value>(data) {
        if let Some(pony_name) = gif_data["pony_name"].as_str() {
            if let Some(sprite_name) = gif_data["sprite_name"].as_str() {
                if !is_safe_name(pony_name) || !is_safe_name(sprite_name) {
                    let response = serde_json::json!({ "type": "gif_save_error", "message": "Invalid pony or sprite name" });
                    let _ = sender.send(response.to_string());
                    return;
                }
                let gif_path = ponies_dir.join(pony_name).join(sprite_name);
                println!("[Editor] Saving GIF to: {:?}", gif_path);
                if let Some(frames) = gif_data["frames"].as_array() {
                    let width = gif_data["width"].as_u64().unwrap_or(128) as usize;
                    let height = gif_data["height"].as_u64().unwrap_or(128) as usize;

                    // Все кадры редактора одного размера — берём его из заголовка
                    // и дополняем/обрезаем данные кадра до w*h*4.
                    let rgba_frames: Vec<GifFrameRgba> = frames.iter().filter_map(|frame_data| {
                        let pixels = frame_data["data"].as_array()?;
                        let mut rgba = vec![0u8; width * height * 4];
                        for (dst, v) in rgba.iter_mut().zip(pixels) {
                            *dst = v.as_u64().unwrap_or(0).min(255) as u8;
                        }
                        let delay_cs = frame_data["delay"].as_u64().unwrap_or(10).clamp(1, u16::MAX as u64) as u16;
                        Some(GifFrameRgba { rgba, delay_cs })
                    }).collect();

                    // Кодируем в память и пишем файл одним вызовом: при ошибке
                    // кодирования исходный спрайт на диске остаётся целым.
                    let mut bytes = Vec::new();
                    let result = encode_gif_exact(&mut bytes, width, height, &rgba_frames).and_then(|_| {
                        if let Some(parent) = gif_path.parent() {
                            let _ = std::fs::create_dir_all(parent);
                        }
                        std::fs::write(&gif_path, &bytes).map_err(|e| e.to_string())
                    });
                    match result {
                        Ok(()) => {
                            println!("[Editor] GIF saved successfully");
                            let response = serde_json::json!({ "type": "gif_save_success", "message": format!("Saved: {}", sprite_name) });
                            let _ = sender.send(response.to_string());
                            return;
                        }
                        Err(e) => {
                            eprintln!("[Editor] Failed to save GIF {:?}: {}", gif_path, e);
                            let response = serde_json::json!({ "type": "gif_save_error", "message": format!("Failed to save GIF: {}", e) });
                            let _ = sender.send(response.to_string());
                            return;
                        }
                    }
                }
            }
        }
    }
    let response = serde_json::json!({ "type": "gif_save_error", "message": "Failed to save GIF" });
    let _ = sender.send(response.to_string());
}

/// Кадр для записи в GIF: RGBA-пиксели (w*h*4) и задержка в сотых секунды.
pub(crate) struct GifFrameRgba {
    pub rgba: Vec<u8>,
    pub delay_cs: u16,
}

/// Записывает GIF пиксель-в-пиксель, без потерь для пиксель-арта.
///
/// Раньше сохранение шло через image::GifEncoder (gif::Frame::from_rgba_speed):
/// полупрозрачные пиксели становились непрозрачными, прозрачным помечался
/// только ОДИН из RGB-вариантов прозрачного цвета (остальные рисовались,
/// например, чёрной каймой), при >256 цветах включался NeuQuant, а режим
/// disposal "Keep" оставлял на прозрачных местах следы прошлого кадра.
///
/// Теперь:
/// - альфа 0/1: a < 128 — прозрачный, иначе непрозрачный (как в оригинальных
///   спрайтах Desktop Ponies);
/// - если во всей анимации <= 255 непрозрачных цветов (обычно так) —
///   одна точная глобальная палитра, цвета не меняются вообще;
/// - иначе палитра на кадр: точная, а если в кадре > 255 цветов — NeuQuant
///   с отображением на ближайший цвет, БЕЗ дизеринга;
/// - disposal "Background": каждый кадр рисуется с чистого листа;
/// - никакого масштабирования — размер ровно width x height.
pub(crate) fn encode_gif_exact<W: std::io::Write>(
    out: W,
    width: usize,
    height: usize,
    frames: &[GifFrameRgba],
) -> Result<(), String> {
    use gif::{DisposalMethod, Encoder, Frame, Repeat};

    if frames.is_empty() {
        return Err("No frames".into());
    }
    if width == 0 || height == 0 || width > u16::MAX as usize || height > u16::MAX as usize {
        return Err(format!("Invalid GIF size {}x{}", width, height));
    }
    let n = width * height;
    let opaque = |px: &[u8]| px[3] >= 128;

    // Уникальные непрозрачные цвета по всей анимации (с ранним выходом).
    let mut global: HashMap<[u8; 3], u8> = HashMap::new();
    let mut global_fits = true;
    let mut any_transparent = false;
    'scan: for f in frames {
        for px in f.rgba[..n * 4].chunks_exact(4) {
            if !opaque(px) {
                any_transparent = true;
                continue;
            }
            let key = [px[0], px[1], px[2]];
            if !global.contains_key(&key) {
                if global.len() == 255 {
                    global_fits = false;
                    break 'scan;
                }
                let idx = global.len() as u8;
                global.insert(key, idx);
            }
        }
    }

    let build_palette = |map: &HashMap<[u8; 3], u8>| {
        let mut pal = vec![0u8; map.len() * 3 + 3]; // +1 слот под прозрачный
        for (c, &i) in map {
            pal[i as usize * 3..i as usize * 3 + 3].copy_from_slice(c);
        }
        pal
    };

    let global_palette = if global_fits { build_palette(&global) } else { Vec::new() };
    let mut encoder = Encoder::new(out, width as u16, height as u16, &global_palette)
        .map_err(|e| e.to_string())?;
    encoder.set_repeat(Repeat::Infinite).map_err(|e| e.to_string())?;

    for f in frames {
        let pixels = &f.rgba[..n * 4];
        let (indices, palette, transparent) = if global_fits {
            let t = global.len() as u8;
            let idx = pixels.chunks_exact(4)
                .map(|px| if opaque(px) { global[&[px[0], px[1], px[2]]] } else { t })
                .collect::<Vec<u8>>();
            (idx, None, any_transparent.then_some(t))
        } else {
            let mut local: HashMap<[u8; 3], u8> = HashMap::new();
            let mut fits = true;
            for px in pixels.chunks_exact(4).filter(|px| opaque(px)) {
                let key = [px[0], px[1], px[2]];
                if !local.contains_key(&key) {
                    if local.len() == 255 {
                        fits = false;
                        break;
                    }
                    let idx = local.len() as u8;
                    local.insert(key, idx);
                }
            }
            if fits {
                let t = local.len() as u8;
                let idx = pixels.chunks_exact(4)
                    .map(|px| if opaque(px) { local[&[px[0], px[1], px[2]]] } else { t })
                    .collect::<Vec<u8>>();
                (idx, Some(build_palette(&local)), Some(t))
            } else {
                // > 255 цветов в кадре: квантизация только по непрозрачным
                // пикселям, каждый пиксель -> ближайший цвет палитры (без
                // дизеринга, чтобы не было "шума").
                let sample: Vec<u8> = pixels.chunks_exact(4).filter(|px| opaque(px))
                    .flat_map(|px| [px[0], px[1], px[2], 255]).collect();
                let nq = color_quant::NeuQuant::new(1, 255, &sample);
                let mut pal = nq.color_map_rgb();
                pal.resize(256 * 3, 0);
                let idx = pixels.chunks_exact(4)
                    .map(|px| if opaque(px) { nq.index_of(&[px[0], px[1], px[2], 255]) as u8 } else { 255 })
                    .collect::<Vec<u8>>();
                (idx, Some(pal), Some(255))
            }
        };

        let frame = Frame {
            width: width as u16,
            height: height as u16,
            delay: f.delay_cs,
            dispose: DisposalMethod::Background,
            transparent,
            palette,
            buffer: std::borrow::Cow::Owned(indices),
            ..Frame::default()
        };
        encoder.write_frame(&frame).map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Создание нового спрайта (пустые кадры, присланные редактором) — тот же
/// формат, что и у gif:save, но имя без расширения дополняется ".gif", а в
/// ответ уходит gif_created (его ждёт main.js).
fn create_gif(data: &str, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    let Ok(mut gif_data) = serde_json::from_str::<Value>(data) else {
        let _ = sender.send(json!({ "type": "gif_save_error", "message": "Failed to parse GIF data" }).to_string());
        return;
    };
    let pony = gif_data["pony_name"].as_str().unwrap_or("").to_string();
    let mut sprite = gif_data["sprite_name"].as_str().unwrap_or("").to_string();
    if !sprite.to_lowercase().ends_with(".gif") {
        sprite.push_str(".gif");
    }
    gif_data["sprite_name"] = json!(sprite);

    // Используем обычный путь сохранения, но подменяем ответ на gif_created.
    let (tx, rx) = mpsc::channel::<String>();
    save_gif_from_editor(&gif_data.to_string(), ponies_dir, &tx);
    drop(tx);
    let ok = rx.iter().any(|m| m.contains("gif_save_success"));
    if ok {
        let _ = sender.send(json!({
            "type": "gif_created",
            "pony_name": pony,
            "sprite_name": sprite,
            "message": format!("Sprite created: {}", sprite)
        }).to_string());
    } else {
        let _ = sender.send(json!({ "type": "gif_save_error", "message": "Failed to create sprite" }).to_string());
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    fn decode_rgba_frames(bytes: &[u8]) -> Vec<Vec<u8>> {
        use image::AnimationDecoder;
        image::codecs::gif::GifDecoder::new(std::io::Cursor::new(bytes)).unwrap()
            .into_frames().map(|f| f.unwrap().into_buffer().into_raw()).collect()
    }

    /// Сохранение GIF не должно менять ни одного пикселя: цвета точные,
    /// прозрачность (с любым RGB) остаётся прозрачной, прошлый кадр не
    /// "просвечивает" сквозь прозрачные места следующего.
    #[test]
    fn gif_save_is_pixel_exact() {
        let (w, h) = (5usize, 3usize);
        let mut f1 = vec![0u8; w * h * 4];
        let mut f2 = vec![0u8; w * h * 4];
        for i in 0..w * h {
            f1[i * 4..i * 4 + 4].copy_from_slice(&[(i * 17) as u8, 200, (255 - i * 13) as u8, 255]);
        }
        f1[4..8].copy_from_slice(&[12, 34, 56, 0]);  // прозрачный с "мусорным" RGB
        f1[8..12].copy_from_slice(&[90, 90, 90, 200]); // почти непрозрачный -> 255
        f2[0..4].copy_from_slice(&[1, 2, 3, 255]);   // остальное прозрачно
        let frames = vec![GifFrameRgba { rgba: f1.clone(), delay_cs: 7 }, GifFrameRgba { rgba: f2.clone(), delay_cs: 3 }];
        let mut bytes = Vec::new();
        encode_gif_exact(&mut bytes, w, h, &frames).unwrap();
        let out = decode_rgba_frames(&bytes);
        assert_eq!(out.len(), 2);

        let mut want1 = f1.clone();
        want1[4..8].copy_from_slice(&[0, 0, 0, 0]);
        want1[11] = 255;
        let norm = |v: &[u8]| v.chunks(4).map(|p| if p[3] == 0 { [0, 0, 0, 0] } else { [p[0], p[1], p[2], p[3]] }).collect::<Vec<_>>();
        assert_eq!(norm(&out[0]), norm(&want1));
        assert_eq!(norm(&out[1]), norm(&f2));
    }

    /// Настоящие спрайты: загрузка редактором -> сохранение -> перечитывание
    /// даёт те же пиксели, что и исходный файл.
    #[test]
    fn real_sprites_survive_save() {
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("Ponies/Applejack");
        let mut checked = 0;
        for e in std::fs::read_dir(&dir).unwrap().flatten() {
            let path = e.path();
            if path.extension().map(|x| x != "gif").unwrap_or(true) { continue; }
            let (frames, w, h) = decode_gif_clean(&path, false).unwrap();
            let rgba: Vec<GifFrameRgba> = frames.iter().map(|f| GifFrameRgba {
                rgba: f["data"].as_array().unwrap().iter().map(|v| v.as_u64().unwrap() as u8).collect(),
                delay_cs: f["delay"].as_u64().unwrap() as u16,
            }).collect();
            let mut bytes = Vec::new();
            encode_gif_exact(&mut bytes, w as usize, h as usize, &rgba).unwrap();
            let out = decode_rgba_frames(&bytes);
            assert_eq!(out.len(), rgba.len(), "{:?}", path);
            for (i, (a, b)) in rgba.iter().zip(&out).enumerate() {
                let bad = a.rgba.chunks(4).zip(b.chunks(4))
                    .filter(|(p, q)| if p[3] < 128 { q[3] != 0 } else { p[..3] != q[..3] || q[3] != 255 })
                    .count();
                assert_eq!(bad, 0, "{:?} frame {}: {} pixels changed", path, i, bad);
            }
            checked += 1;
        }
        assert!(checked > 0);
    }

    /// Больше 255 цветов — квантизация, но без паники и с сохранением прозрачности.
    #[test]
    fn gif_save_many_colors() {
        let (w, h) = (32usize, 32usize);
        let mut f = vec![0u8; w * h * 4];
        for i in 0..w * h {
            f[i * 4..i * 4 + 4].copy_from_slice(&[(i % 256) as u8, (i / 4 % 256) as u8, 77, if i % 10 == 0 { 0 } else { 255 }]);
        }
        let mut bytes = Vec::new();
        encode_gif_exact(&mut bytes, w, h, &[GifFrameRgba { rgba: f.clone(), delay_cs: 10 }]).unwrap();
        let out = &decode_rgba_frames(&bytes)[0];
        for i in 0..w * h {
            assert_eq!(out[i * 4 + 3] == 0, f[i * 4 + 3] == 0, "pixel {}", i);
        }
    }

    /// Полный цикл редактора: загрузка -> JSON -> обратно -> сохранение ->
    /// перечитывание; данные должны совпасть с исходным pony.ini.
    #[test]
    fn editor_roundtrip_preserves_ini() {
        let tmp = std::env::temp_dir().join(format!("pony_editor_rt_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(tmp.join("Ponies/Applejack")).unwrap();
        let src = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("Ponies/Applejack");
        for e in std::fs::read_dir(&src).unwrap().flatten() {
            if e.path().extension().map(|x| x == "gif" || x == "ini").unwrap_or(false) {
                std::fs::copy(e.path(), tmp.join("Ponies/Applejack").join(e.file_name())).unwrap();
            }
        }
        let ponies_dir = tmp.join("Ponies");
        let loader: Shared = Arc::new(Mutex::new(PonyCollection::load(&tmp, false)));
        let before = loader.lock().unwrap().bases[0].clone();
        let (tx, rx) = mpsc::channel();
        send_pony_config(&loader, "Applejack", &tx);
        let msg: Value = serde_json::from_str(&rx.recv().unwrap()).unwrap();
        let mut data = msg["data"].clone();
        data["behaviors"][0]["group"] = json!(0); // число из JS не должно ломаться
        save_pony_config(&data.to_string(), &loader, &ponies_dir, &tx);
        let resp: Vec<Value> = rx.try_iter().map(|m| serde_json::from_str(&m).unwrap()).collect();
        assert!(resp.iter().any(|r| r["type"] == "save_success"), "{:?}", resp);
        assert!(resp.iter().any(|r| r["type"] == "ponies_list"));
        let after = loader.lock().unwrap().bases[0].clone();
        assert_eq!(before.to_ini_text(), after.to_ini_text(), "pony.ini must survive an editor round trip unchanged");

        let new_cfg = json!({"name":"NewPony","display_name":"New Pony","categories":["x"],"behaviors":[],"speaks":[],"effects":[],"interactions":[]});
        save_pony_config(&new_cfg.to_string(), &loader, &ponies_dir, &tx);
        assert!(loader.lock().unwrap().bases.iter().any(|b| b.directory == "NewPony"));
        delete_pony("..", &loader, &ponies_dir, &tx);
        assert!(tmp.join("Ponies").exists());
        let _ = std::fs::remove_dir_all(&tmp);
    }
}
