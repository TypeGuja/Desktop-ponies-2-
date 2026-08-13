// src_rust/editor/ini_writer.rs
use std::fs;
use std::io::Write;
use crate::loader::{PonyConfig, Behavior, SpeakDef, InteractionDef, EffectDef,
                    TargetMode, FollowOffsetType, TargetActivation, Direction};

pub fn write_pony_config(config: &PonyConfig) -> Result<(), String> {
    let ini_path = config.directory.join("pony.ini");
    let mut content = String::new();

    // Display Name
    if config.display_name != config.name {
        content.push_str(&format!("Name,\"{}\"\n", escape_ini_string(&config.display_name)));
    }

    // Categories
    if !config.categories.is_empty() {
        content.push_str("Categories");
        for cat in &config.categories { content.push_str(&format!(",\"{}\"", escape_ini_string(cat))); }
        content.push('\n');
    }

    // Tags
    if !config.tags.is_empty() {
        content.push_str("Tags");
        for tag in &config.tags { content.push_str(&format!(",\"{}\"", escape_ini_string(tag))); }
        content.push('\n');
    }

    // Groups
    let mut groups: Vec<(&i32, &String)> = config.behavior_groups.iter().filter(|(num, _)| **num != 0).collect();
    if !groups.is_empty() {
        groups.sort_by_key(|(num, _)| *num);
        content.push_str("Groups");
        for (num, name) in groups { content.push_str(&format!(",{}=\"{}\"", num, escape_ini_string(name))); }
        content.push('\n');
    }

    // Behaviors
    for behavior in &config.behaviors { write_behavior(&mut content, behavior); }

    // Speaks
    for speak in &config.speaks { write_speak(&mut content, speak); }

    // Interactions
    for interaction in &config.interactions { write_interaction(&mut content, interaction); }

    // Effects
    for effect in &config.effects { write_effect(&mut content, effect); }

    let mut file = fs::File::create(&ini_path).map_err(|e| format!("Failed to create pony.ini: {}", e))?;
    file.write_all(content.as_bytes()).map_err(|e| format!("Failed to write: {}", e))?;
    println!("[Editor] Saved config to: {:?}", ini_path);
    Ok(())
}

fn escape_ini_string(s: &str) -> String { s.replace('"', "\"\"") }

fn write_behavior(content: &mut String, b: &Behavior) {
    let right_center = format!("{:.0},{:.0}", b.right_image_center.0, b.right_image_center.1);
    let left_center = format!("{:.0},{:.0}", b.left_image_center.0, b.left_image_center.1);
    let sound_files = if b.sound_files.is_empty() {
        String::new()
    } else {
        format!("{{{}}}", b.sound_files.iter().map(|s| format!("\"{}\"", escape_ini_string(s))).collect::<Vec<_>>().join(","))
    };

    // ИСПРАВЛЕНО: раньше здесь пропускалось поле set_max_fps, из-за чего все
    // последующие поля (sound_files, target_mode, target_vector, follow_target_name,
    // auto_select_images_on_follow, follow_moving_behavior, follow_stopped_behavior,
    // follow_offset_type) записывались со сдвигом на одну колонку, а do_not_repeat_animations
    // вообще терялось при обратном чтении. Сохранение пони в редакторе портило pony.ini.
    content.push_str(&format!(
        "Behavior,\"{}\",{},{},{},{},\"{}\",\"{}\",\"{}\",\"{}\",\"{}\",\"{}\",{},{},{},\"{}\",{},\"{}\",\"{}\",\"{}\",\"{}\",{},{},\"{}\",\"{}\",{},{},{},\"",
        escape_ini_string(&b.name), b.probability, b.max_duration, b.min_duration, b.speed,
        escape_ini_string(&b.sprite_right), escape_ini_string(&b.sprite_left), escape_ini_string(&b.movement),
        escape_ini_string(&b.linked_behavior), escape_ini_string(&b.start_speech), escape_ini_string(&b.end_speech),
        b.skip, b.target_x, b.target_y, b.follow_target, b.auto_select_follow,
        escape_ini_string(&b.follow_stopped), escape_ini_string(&b.follow_moving),
        right_center, left_center, b.prevent_loop, b.group, escape_ini_string(&b.follow_offset),
        b.set_animation_speed.unwrap_or(0.0), b.set_fps.unwrap_or(0.0), b.set_max_fps.unwrap_or(0.0), sound_files
    ));

    match b.target_mode {
        TargetMode::None => content.push_str(",\"None\""),
        TargetMode::Pony => content.push_str(&format!(",\"Pony:{}\"", escape_ini_string(&b.follow_target_name))),
        TargetMode::Point => content.push_str(&format!(",\"Point:{},{}\"", b.target_vector.0, b.target_vector.1)),
    }
    content.push_str(&format!(",\"{},{}\"", b.target_vector.0, b.target_vector.1));
    content.push_str(&format!(",\"{}\"", escape_ini_string(&b.follow_target_name)));
    content.push_str(&format!(",{}", b.auto_select_images_on_follow));
    content.push_str(&format!(",\"{}\"", escape_ini_string(&b.follow_moving_behavior)));
    content.push_str(&format!(",\"{}\"", escape_ini_string(&b.follow_stopped_behavior)));
    match b.follow_offset_type {
        FollowOffsetType::Fixed => content.push_str(",\"Fixed\""),
        FollowOffsetType::Mirror => content.push_str(",\"Mirror\""),
    }
    content.push_str(&format!(",{}\n", b.do_not_repeat_animations));
}

fn write_speak(content: &mut String, s: &SpeakDef) {
    let sound_files = if s.sound_files.is_empty() {
        String::new()
    } else {
        format!("{{{}}}", s.sound_files.iter().map(|f| format!("\"{}\"", escape_ini_string(f))).collect::<Vec<_>>().join(","))
    };
    content.push_str(&format!("Speak,\"{}\",\"{}\",{},{},{},{}\n",
                              escape_ini_string(&s.name), escape_ini_string(&s.text), sound_files, s.skip, s.frequency, s.group));
}

fn write_interaction(content: &mut String, i: &InteractionDef) {
    let targets = format!("{{{}}}", i.targets.iter().map(|t| format!("\"{}\"", escape_ini_string(t))).collect::<Vec<_>>().join(","));
    let behaviors = format!("{{{}}}", i.behaviors.iter().map(|b| format!("\"{}\"", escape_ini_string(b))).collect::<Vec<_>>().join(","));
    let activation = match i.activation {
        TargetActivation::One => "One",
        TargetActivation::Any => "Any",
        TargetActivation::All => "All",
    };
    content.push_str(&format!("Interaction,\"{}\",{},{},{},{},{},{},\"{}\",{},\"{}\"\n",
                              escape_ini_string(&i.name), i.probability, i.cooldown, targets, i.target_count,
                              behaviors, i.duration, activation, i.reactivation_delay, escape_ini_string(&i.initiator_name)));
}

fn write_effect(content: &mut String, e: &EffectDef) {
    content.push_str(&format!("Effect,\"{}\",\"{}\",\"{}\",\"{}\",{},{},\"{}\",\"{}\",\"{}\",\"{}\",{},{},{},\"{}\"\n",
                              escape_ini_string(&e.name), escape_ini_string(&e.linked), escape_ini_string(&e.sprite_right),
                              escape_ini_string(&e.sprite_left), e.duration, e.delay,
                              e.placement_right.to_display_string(), e.placement_left.to_display_string(),
                              e.centering_right.to_display_string(), e.centering_left.to_display_string(),
                              e.follow, e.repeat_delay, e.do_not_repeat_animations, escape_ini_string(&e.behavior_name)));
}