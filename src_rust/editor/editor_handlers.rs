// src_rust/editor/editor_handlers.rs - ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ

use std::sync::{Arc, Mutex};
use std::path::PathBuf;
use std::collections::HashMap;
use std::sync::mpsc;
use serde_json::json;
use crate::loader::DesktopPoniesLoader;
use crate::editor::ini_writer::write_pony_config;
use crate::loader::{PonyConfig, Behavior, SpeakDef, InteractionDef, EffectDef,
                    TargetMode, FollowOffsetType, TargetActivation};

pub fn handle_ipc(body: &str, loader: &Arc<Mutex<DesktopPoniesLoader>>, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    if body == "editor:load_ponies" {
        send_ponies_list(loader, sender);
    } else if let Some(pony_name) = body.strip_prefix("editor:load_pony:") {
        send_pony_config(loader, pony_name, sender);
    } else if let Some(data) = body.strip_prefix("editor:save_pony:") {
        save_pony_config(data, ponies_dir, sender);
    } else if let Some(pony_name) = body.strip_prefix("editor:delete_pony:") {
        delete_pony(pony_name, ponies_dir, sender);
    } else if let Some(data) = body.strip_prefix("gif:load:") {
        load_gif_for_editor(data, ponies_dir, sender);
    } else if let Some(data) = body.strip_prefix("gif:save:") {
        save_gif_from_editor(data, ponies_dir, sender);
    } else if let Some(data) = body.strip_prefix("gif:list:") {
        list_gifs_for_pony(data, ponies_dir, sender);
    } else if let Some(data) = body.strip_prefix("trace:parse_gif:") {
        parse_gif_bytes_for_trace(data, sender);
    } else if body == "editor:close" {
        println!("[Editor] Close request received");
    } else {
        println!("[Editor] Unknown IPC: {}", body);
    }
}

fn send_ponies_list(loader: &Arc<Mutex<DesktopPoniesLoader>>, sender: &mpsc::Sender<String>) {
    let loader = loader.lock().unwrap();
    let ponies: Vec<String> = loader.configs.iter().map(|c| c.name.clone()).collect();
    let response = json!({ "type": "ponies_list", "data": ponies });
    println!("[Editor] Sending ponies list ({} ponies)", ponies.len());
    let _ = sender.send(response.to_string());
}

fn send_pony_config(loader: &Arc<Mutex<DesktopPoniesLoader>>, pony_name: &str, sender: &mpsc::Sender<String>) {
    let loader = loader.lock().unwrap();
    if let Some(config) = loader.get_config(pony_name) {
        let response = json!({
            "type": "pony_config",
            "pony_name": pony_name,
            "data": {
                "name": config.name,
                "display_name": config.display_name,
                "categories": config.categories,
                "tags": config.tags,
                "behaviors": config.behaviors.iter().map(|b| json!({
                    "name": b.name, "probability": b.probability, "min_duration": b.min_duration,
                    "max_duration": b.max_duration, "speed": b.speed, "sprite_right": b.sprite_right,
                    "sprite_left": b.sprite_left, "movement": b.movement, "linked_behavior": b.linked_behavior,
                    "start_speech": b.start_speech, "end_speech": b.end_speech, "skip": b.skip,
                    "group": b.group, "do_not_repeat_animations": b.do_not_repeat_animations,
                })).collect::<Vec<_>>(),
                "speaks": config.speaks.iter().map(|s| json!({
                    "name": s.name, "text": s.text, "sound_files": s.sound_files,
                    "skip": s.skip, "frequency": s.frequency, "group": s.group,
                })).collect::<Vec<_>>(),
                "interactions": config.interactions.iter().map(|i| json!({
                    "name": i.name, "probability": i.probability, "cooldown": i.cooldown,
                    "targets": i.targets, "target_count": i.target_count,
                    "behaviors": i.behaviors, "duration": i.duration,
                })).collect::<Vec<_>>(),
                "effects": config.effects.iter().map(|e| json!({
                    "name": e.name, "linked": e.linked, "sprite_right": e.sprite_right,
                    "sprite_left": e.sprite_left, "duration": e.duration, "delay": e.delay,
                })).collect::<Vec<_>>(),
                "behavior_groups": config.behavior_groups,
            }
        });
        println!("[Editor] Sending config for pony: {}", pony_name);
        let _ = sender.send(response.to_string());
    } else {
        let response = json!({ "type": "error", "message": format!("Pony '{}' not found", pony_name) });
        let _ = sender.send(response.to_string());
    }
}

fn save_pony_config(data: &str, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    println!("[Editor] Saving pony config, data length: {}", data.len());
    if let Ok(config_data) = serde_json::from_str::<serde_json::Value>(data) {
        let pony_name = config_data["name"].as_str().unwrap_or("unknown");
        let pony_dir = ponies_dir.join(pony_name);
        if !pony_dir.exists() {
            let _ = std::fs::create_dir_all(&pony_dir);
        }
        let mut config = PonyConfig {
            name: pony_name.to_string(),
            display_name: config_data["display_name"].as_str().unwrap_or(pony_name).to_string(),
            categories: Vec::new(),
            tags: Vec::new(),
            directory: pony_dir,
            behaviors: Vec::new(),
            speaks: Vec::new(),
            interactions: Vec::new(),
            effects: Vec::new(),
            behavior_groups: HashMap::new(),
        };
        if let Some(cats) = config_data["categories"].as_array() {
            for cat in cats { if let Some(c) = cat.as_str() { config.categories.push(c.to_string()); } }
        }
        if let Some(tags) = config_data["tags"].as_array() {
            for tag in tags { if let Some(t) = tag.as_str() { config.tags.push(t.to_string()); } }
        }
        if let Some(behaviors) = config_data["behaviors"].as_array() {
            for b in behaviors {
                config.behaviors.push(Behavior {
                    name: b["name"].as_str().unwrap_or("").to_string(),
                    probability: b["probability"].as_f64().unwrap_or(0.1) as f32,
                    max_duration: b["max_duration"].as_f64().unwrap_or(15.0) as f32,
                    min_duration: b["min_duration"].as_f64().unwrap_or(5.0) as f32,
                    speed: b["speed"].as_f64().unwrap_or(3.0) as f32,
                    sprite_right: b["sprite_right"].as_str().unwrap_or("").to_string(),
                    sprite_left: b["sprite_left"].as_str().unwrap_or("").to_string(),
                    movement: b["movement"].as_str().unwrap_or("All").to_string(),
                    linked_behavior: b["linked_behavior"].as_str().unwrap_or("").to_string(),
                    start_speech: b["start_speech"].as_str().unwrap_or("").to_string(),
                    end_speech: b["end_speech"].as_str().unwrap_or("").to_string(),
                    skip: b["skip"].as_bool().unwrap_or(false),
                    target_x: 0.0, target_y: 0.0, follow_target: false, auto_select_follow: true,
                    follow_stopped: String::new(), follow_moving: String::new(),
                    right_image_center: (0.0, 0.0), left_image_center: (0.0, 0.0),
                    prevent_loop: false, group: b["group"].as_str().unwrap_or("0").to_string(),
                    follow_offset: String::new(), set_animation_speed: None, set_fps: None,
                    set_max_fps: None, sound_files: Vec::new(),
                    target_mode: TargetMode::None, target_vector: (0, 0), follow_target_name: String::new(),
                    auto_select_images_on_follow: true, follow_moving_behavior: String::new(),
                    follow_stopped_behavior: String::new(), follow_offset_type: FollowOffsetType::Fixed,
                    do_not_repeat_animations: b["do_not_repeat_animations"].as_bool().unwrap_or(false),
                });
            }
        }
        if let Some(speaks) = config_data["speaks"].as_array() {
            for s in speaks {
                let sound_files = if let Some(sf) = s["sound_files"].as_array() {
                    sf.iter().filter_map(|f| f.as_str().map(String::from)).collect()
                } else { Vec::new() };
                config.speaks.push(SpeakDef {
                    name: s["name"].as_str().unwrap_or("").to_string(),
                    text: s["text"].as_str().unwrap_or("").to_string(),
                    sound_files, skip: s["skip"].as_bool().unwrap_or(false),
                    frequency: s["frequency"].as_f64().unwrap_or(0.0) as f32,
                    group: s["group"].as_i64().unwrap_or(0) as i32,
                });
            }
        }
        if let Some(interactions) = config_data["interactions"].as_array() {
            for i in interactions {
                let targets = if let Some(t) = i["targets"].as_array() {
                    t.iter().filter_map(|v| v.as_str().map(String::from)).collect()
                } else { Vec::new() };
                let behaviors_list = if let Some(b) = i["behaviors"].as_array() {
                    b.iter().filter_map(|v| v.as_str().map(String::from)).collect()
                } else { Vec::new() };
                config.interactions.push(InteractionDef {
                    name: i["name"].as_str().unwrap_or("").to_string(),
                    probability: i["probability"].as_f64().unwrap_or(0.0) as f32,
                    cooldown: i["cooldown"].as_f64().unwrap_or(0.0) as f32,
                    targets, target_count: i["target_count"].as_str().unwrap_or("One").to_string(),
                    behaviors: behaviors_list, duration: i["duration"].as_f64().unwrap_or(300.0) as f32,
                    activation: TargetActivation::One, reactivation_delay: 0.0, initiator_name: String::new(),
                });
            }
        }
        if let Some(effects) = config_data["effects"].as_array() {
            for e in effects {
                config.effects.push(EffectDef {
                    name: e["name"].as_str().unwrap_or("").to_string(),
                    linked: e["linked"].as_str().unwrap_or("").to_string(),
                    sprite_right: e["sprite_right"].as_str().unwrap_or("").to_string(),
                    sprite_left: e["sprite_left"].as_str().unwrap_or("").to_string(),
                    duration: e["duration"].as_f64().unwrap_or(0.0) as f32,
                    delay: e["delay"].as_f64().unwrap_or(0.0) as f32,
                    placement_right: crate::loader::Direction::MiddleCenter,
                    placement_left: crate::loader::Direction::MiddleCenter,
                    centering_right: crate::loader::Direction::MiddleCenter,
                    centering_left: crate::loader::Direction::MiddleCenter,
                    follow: false, repeat_delay: 0.0, do_not_repeat_animations: false, behavior_name: String::new(),
                });
            }
        }
        match write_pony_config(&config) {
            Ok(_) => {
                let _ = sender.send(json!({ "type": "save_success", "message": format!("Pony '{}' saved", pony_name) }).to_string());
            }
            Err(e) => {
                let _ = sender.send(json!({ "type": "save_error", "message": format!("Failed: {}", e) }).to_string());
            }
        }
    } else {
        let _ = sender.send(json!({ "type": "save_error", "message": "Failed to parse config" }).to_string());
    }
}

fn delete_pony(pony_name: &str, ponies_dir: &PathBuf, sender: &mpsc::Sender<String>) {
    let pony_path = ponies_dir.join(pony_name);
    if pony_path.exists() {
        match std::fs::remove_dir_all(&pony_path) {
            Ok(_) => {
                let _ = sender.send(json!({ "type": "delete_success", "message": format!("Pony '{}' deleted", pony_name) }).to_string());
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
    if pony_path.exists() && pony_path.is_dir() {
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

// Очистка кадра от артефактов (шумовых пикселей)
fn clean_frame_artifacts(data: &mut [u8], width: u32, height: u32) {
    let w = width as usize;
    let h = height as usize;

    if data.len() != w * h * 4 {
        return;
    }

    // Создаём копию для анализа
    let copy = data.to_vec();

    // Проходим по всем пикселям
    for y in 0..h {
        for x in 0..w {
            let idx = (y * w + x) * 4;

            // Пропускаем полностью прозрачные пиксели
            if copy[idx + 3] == 0 {
                continue;
            }

            // Считаем количество непрозрачных соседей
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

            // Если пиксель изолированный (менее 2 соседей) - делаем его прозрачным
            if opaque_neighbors < 2 {
                data[idx] = 0;
                data[idx + 1] = 0;
                data[idx + 2] = 0;
                data[idx + 3] = 0;
            }
        }
    }
}

fn decode_gif_clean(path: &PathBuf) -> Result<(Vec<serde_json::Value>, u32, u32), String> {
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
        // Получаем задержку в миллисекундах
        let (numer, denom) = frame.delay().numer_denom_ms();
        let delay_ms = numer as u16;

        // GIF delay обычно в сотых долях секунды, но image возвращает в мс
        // Конвертируем в сотые доли (стандарт GIF)
        let delay_cs = (delay_ms as f32 / 10.0).round() as u16;
        let final_delay = if delay_cs > 0 { delay_cs } else { 10 }; // Минимум 10cs = 0.1 сек

        let buffer = frame.into_buffer();

        println!("[GIF] Frame {}: delay_ms={}, delay_cs={}", i, delay_ms, final_delay);

        // Получаем сырые RGBA данные
        let mut rgba_bytes = Vec::with_capacity((width * height * 4) as usize);
        for pixel in buffer.pixels() {
            rgba_bytes.push(pixel.0[0]); // R
            rgba_bytes.push(pixel.0[1]); // G
            rgba_bytes.push(pixel.0[2]); // B
            rgba_bytes.push(pixel.0[3]); // A
        }

        // Очищаем от артефактов
        clean_frame_artifacts(&mut rgba_bytes, width, height);

        frames_data.push(serde_json::json!({
            "data": rgba_bytes,
            "delay": final_delay, // Задержка в сотых долях секунды
            "width": width,
            "height": height
        }));
    }

    println!("[GIF] Successfully decoded {} frames", frames_data.len());
    Ok((frames_data, width, height))
}

// Альтернативный метод декодирования с использованием gif библиотеки
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

    // Буфер для накопления кадров
    let mut accumulated = vec![0u8; (width * height * 4) as usize];
    for i in (0..accumulated.len()).step_by(4) {
        accumulated[i + 3] = 0;
    }

    while let Some(frame) = gif.read_next_frame().map_err(|e| format!("Frame read error: {}", e))? {
        // Задержка в gif библиотеке уже в сотых долях секунды
        let delay = if frame.delay > 0 { frame.delay } else { 10 };
        let left = frame.left as u32;
        let top = frame.top as u32;
        let frame_width = frame.width as u32;
        let frame_height = frame.height as u32;

        println!("[GIF Lib] Frame {}: offset=({},{}), size={}x{}, delay={}cs",
                 frame_num, left, top, frame_width, frame_height, delay);

        // Накладываем новый кадр
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
            "delay": delay, // Уже в сотых долях
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

// Удаление дублирующихся кадров
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
        let gif_path = ponies_dir.join(pony_name).join(sprite_name_clean);

        println!("[Editor] Looking for GIF at: {:?}", gif_path);
        println!("[Editor] File exists: {}", gif_path.exists());

        if gif_path.exists() {
            // Пробуем clean-версию
            let result = decode_gif_clean(&gif_path);

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

    // Кадр 1 - красный квадрат на прозрачном фоне
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

    // Кадр 2 - синий квадрат на прозрачном фоне
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
                let gif_path = ponies_dir.join(pony_name).join(sprite_name);
                println!("[Editor] Saving GIF to: {:?}", gif_path);
                if let Some(frames) = gif_data["frames"].as_array() {
                    use std::fs::File;
                    use image::{ImageBuffer, Rgba, Frame, Delay};
                    use image::codecs::gif::{GifEncoder, Repeat};

                    if let Some(parent) = gif_path.parent() {
                        let _ = std::fs::create_dir_all(parent);
                    }

                    if let Ok(file) = File::create(&gif_path) {
                        let mut encoder = GifEncoder::new(file);
                        let _ = encoder.set_repeat(Repeat::Infinite);

                        for frame_data in frames {
                            let width = frame_data["width"].as_u64().unwrap_or(128) as u32;
                            let height = frame_data["height"].as_u64().unwrap_or(128) as u32;
                            let delay = frame_data["delay"].as_u64().unwrap_or(10) as u16;

                            if let Some(pixels) = frame_data["data"].as_array() {
                                let mut img = ImageBuffer::<Rgba<u8>, _>::new(width, height);
                                let pixels_len = pixels.len();

                                for y in 0..height {
                                    for x in 0..width {
                                        let idx = ((y * width + x) * 4) as usize;
                                        if idx + 3 < pixels_len {
                                            let r = pixels[idx].as_u64().unwrap_or(0) as u8;
                                            let g = pixels[idx + 1].as_u64().unwrap_or(0) as u8;
                                            let b = pixels[idx + 2].as_u64().unwrap_or(0) as u8;
                                            let a = pixels[idx + 3].as_u64().unwrap_or(255) as u8;

                                            if a > 0 {
                                                img.put_pixel(x, y, Rgba([r, g, b, a]));
                                            }
                                        }
                                    }
                                }

                                let delay_obj = Delay::from_numer_denom_ms(delay as u32, 100);
                                let frame = Frame::from_parts(img, 0, 0, delay_obj);
                                let _ = encoder.encode_frame(frame);
                            }
                        }
                        println!("[Editor] GIF saved successfully");
                        let response = serde_json::json!({ "type": "gif_save_success", "message": format!("Saved: {}", sprite_name) });
                        let _ = sender.send(response.to_string());
                        return;
                    } else {
                        eprintln!("[Editor] Failed to create file: {:?}", gif_path);
                    }
                }
            }
        }
    }
    let response = serde_json::json!({ "type": "gif_save_error", "message": "Failed to save GIF" });
    let _ = sender.send(response.to_string());
}

fn parse_gif_bytes_for_trace(data: &str, sender: &mpsc::Sender<String>) {
    println!("[Editor] Parsing GIF bytes for trace - START");

    if let Ok(msg) = serde_json::from_str::<serde_json::Value>(data) {
        if let Some(bytes_array) = msg["data"].as_array() {
            let bytes: Vec<u8> = bytes_array.iter()
                .filter_map(|v| v.as_u64().map(|n| n as u8))
                .collect();

            if bytes.is_empty() {
                let response = serde_json::json!({
                    "type": "trace_gif_parsed",
                    "error": "No data provided"
                });
                println!("[Editor] Sending trace error: no data");
                let _ = sender.send(response.to_string());
                return;
            }

            use std::io::Write;
            let temp_dir = std::env::temp_dir();
            let temp_file = temp_dir.join(format!("trace_{}.gif", std::process::id()));

            if let Ok(mut file) = std::fs::File::create(&temp_file) {
                let _ = file.write_all(&bytes);
                drop(file);

                let result = decode_gif_clean(&temp_file);
                let _ = std::fs::remove_file(&temp_file);

                match result {
                    Ok((frames_data, width, height)) => {
                        if frames_data.is_empty() {
                            let response = serde_json::json!({
                                "type": "trace_gif_parsed",
                                "error": "No frames decoded"
                            });
                            let _ = sender.send(response.to_string());
                            return;
                        }
                        // ОТПРАВЛЯЕМ ТОЛЬКО ПЕРВЫЙ КАДР
                        let first_frame = frames_data[0].clone();
                        let response = serde_json::json!({
                            "type": "trace_gif_parsed",
                            "frames": vec![first_frame],
                            "width": width,
                            "height": height
                        });
                        let response_str = response.to_string();
                        println!("[Editor] Sending trace response (1 frame), size: {} bytes", response_str.len());
                        let _ = sender.send(response_str);
                        return;
                    }
                    Err(e) => {
                        println!("[Editor] Trace parse error: {}, trying gif lib", e);
                        if let Ok(mut file) = std::fs::File::create(&temp_file) {
                            let _ = file.write_all(&bytes);
                            drop(file);
                            let result2 = decode_gif_with_gif_lib(&temp_file);
                            let _ = std::fs::remove_file(&temp_file);

                            match result2 {
                                Ok((frames_data, width, height)) => {
                                    if frames_data.is_empty() {
                                        let response = serde_json::json!({
                                            "type": "trace_gif_parsed",
                                            "error": "No frames decoded (alt)"
                                        });
                                        let _ = sender.send(response.to_string());
                                        return;
                                    }
                                    // ОТПРАВЛЯЕМ ТОЛЬКО ПЕРВЫЙ КАДР
                                    let first_frame = frames_data[0].clone();
                                    let response = serde_json::json!({
                                        "type": "trace_gif_parsed",
                                        "frames": vec![first_frame],
                                        "width": width,
                                        "height": height
                                    });
                                    let response_str = response.to_string();
                                    println!("[Editor] Sending trace response (alt, 1 frame), size: {} bytes", response_str.len());
                                    let _ = sender.send(response_str);
                                    return;
                                }
                                Err(e2) => {
                                    println!("[Editor] Alt trace parse error: {}", e2);
                                }
                            }
                        }
                    }
                }
            } else {
                println!("[Editor] Failed to create temp file for trace");
            }
        } else {
            println!("[Editor] No data array in trace message");
        }
    } else {
        println!("[Editor] Failed to parse trace message as JSON");
    }

    let response = serde_json::json!({
        "type": "trace_gif_parsed",
        "error": "Failed to parse GIF"
    });
    println!("[Editor] Sending trace error response");
    let _ = sender.send(response.to_string());
}