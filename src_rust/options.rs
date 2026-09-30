// src_rust/options.rs
//
// Глобальные настройки и профили — порт Options.vb из Desktop Ponies 1.69.
// Профили хранятся в Profiles/<имя>.ini в том же формате, что и у
// оригинала (строка "options,...", затем "monitor", "count" и "tag"), поэтому
// профили из оригинальной программы читаются без изменений. Имя текущего
// профиля хранится в Profiles/current.txt.

use crate::ini::{comma_split_quote, quoted, Parser};
use crate::math::{RectF, RectI};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

pub const DEFAULT_PROFILE: &str = "default";
pub const SCREENSAVER_PROFILE: &str = "screensaver";
pub const DEFAULT_FPS_LIMIT: u32 = 60;
pub const MIN_FPS_LIMIT: u32 = 10;
pub const MAX_FPS_LIMIT: u32 = 240;
pub const DEFAULT_LUNA_IDLE_SECS: u32 = 20;
pub const MIN_LUNA_IDLE_SECS: u32 = 3;
pub const MAX_LUNA_IDLE_SECS: u32 = 3600;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ScreensaverStyle {
    Transparent,
    SolidColor,
    BackgroundImage,
}

#[derive(Clone, Debug)]
pub struct Options {
    pub profile_name: String,
    pub suspend_for_fullscreen_application: bool,
    pub show_in_taskbar: bool,
    pub always_on_top: bool,
    pub alpha_blending_enabled: bool,
    pub window_avoidance_enabled: bool,
    pub cursor_avoidance_enabled: bool,
    pub cursor_avoidance_size: f32,
    pub sound_enabled: bool,
    pub sound_volume: f32,
    pub sound_single_channel_only: bool,
    pub pony_avoids_ponies: bool,
    pub window_containment: bool,
    pub pony_effects_enabled: bool,
    pub pony_dragging_enabled: bool,
    pub pony_teleport_enabled: bool,
    pub pony_speech_enabled: bool,
    pub pony_speech_chance: f32,
    pub pony_interactions_enabled: bool,
    pub display_pony_interactions_errors: bool,
    pub screensaver_sound_enabled: bool,
    pub screensaver_style: ScreensaverStyle,
    pub screensaver_background_color: i32,
    pub screensaver_background_image_path: String,
    pub no_random_duplicates: bool,
    pub max_pony_count: i32,
    pub time_factor: f32,
    pub scale_factor: f32,
    pub exclusion_zone: RectF,
    /// Имена мониторов (DeviceName, напр. \\.\DISPLAY1).
    pub screens: Vec<String>,
    /// Ограничение области показа (None = все выбранные мониторы целиком).
    pub allowed_region: Option<RectI>,
    pub background_color: i32,
    /// Скелетная анимация (голова/хвост/корпус) для Mane 6 и принцесс.
    /// Дополнительная последняя колонка строки options — оригинал её игнорирует.
    pub skeletal_animation: bool,
    /// Ограничение частоты отрисовки (кадров в секунду). Дополнительная колонка
    /// строки options после skeletal_animation — оригинал её игнорирует.
    pub fps_limit: u32,
    /// Магия принцессы Луны (luna.rs): переносить окна, иконки, приходить к
    /// неподвижному курсору. Дополнительные колонки после fps_limit.
    pub luna_moves_windows: bool,
    pub luna_moves_icons: bool,
    pub luna_sleeps_by_cursor: bool,
    /// Луна сама открывает Яндекс Музыку и переключает треки.
    pub luna_music: bool,
    /// Луна переносит магией других пони (они в drag-состоянии).
    pub luna_moves_ponies: bool,
    /// Через сколько секунд неподвижности курсора Луна идёт к нему.
    pub luna_cursor_idle_secs: u32,
    /// Количества пони для запуска: каталог -> число.
    pub pony_counts: BTreeMap<String, i32>,
    pub custom_tags: Vec<String>,
    pub enable_pony_logs: bool,
    pub show_performance_graph: bool,
}

impl Default for Options {
    fn default() -> Options {
        Options {
            profile_name: DEFAULT_PROFILE.to_string(),
            suspend_for_fullscreen_application: true,
            show_in_taskbar: cfg!(windows),
            always_on_top: true,
            alpha_blending_enabled: true,
            window_avoidance_enabled: false,
            cursor_avoidance_enabled: true,
            cursor_avoidance_size: 100.0,
            sound_enabled: true,
            sound_volume: 0.75,
            sound_single_channel_only: false,
            pony_avoids_ponies: false,
            window_containment: false,
            pony_effects_enabled: true,
            pony_dragging_enabled: true,
            pony_teleport_enabled: false,
            pony_speech_enabled: true,
            pony_speech_chance: 0.01,
            pony_interactions_enabled: true,
            display_pony_interactions_errors: false,
            screensaver_sound_enabled: true,
            screensaver_style: ScreensaverStyle::Transparent,
            screensaver_background_color: 0,
            screensaver_background_image_path: String::new(),
            no_random_duplicates: true,
            max_pony_count: 500,
            time_factor: 1.0,
            scale_factor: 1.0,
            exclusion_zone: RectF::EMPTY,
            screens: Vec::new(),
            allowed_region: None,
            background_color: 0,
            // Выключена по умолчанию: переключатель убран из интерфейса, логика осталась.
            skeletal_animation: false,
            fps_limit: DEFAULT_FPS_LIMIT,
            luna_moves_windows: true,
            luna_moves_icons: true,
            luna_sleeps_by_cursor: true,
            luna_music: true,
            luna_moves_ponies: true,
            luna_cursor_idle_secs: DEFAULT_LUNA_IDLE_SECS,
            pony_counts: BTreeMap::new(),
            custom_tags: Vec::new(),
            enable_pony_logs: false,
            show_performance_graph: false,
        }
    }
}

fn valid_profile_name(name: &str) -> bool {
    !name.is_empty()
        && name != DEFAULT_PROFILE
        && !name.contains(['<', '>', ':', '"', '/', '\\', '|', '?', '*'])
        && !name.chars().any(|c| c.is_control())
}

fn clamp_exclusion(mut z: RectF) -> RectF {
    if z.x + z.w > 1.0 {
        z.w = 1.0 - z.x;
    }
    if z.y + z.h > 1.0 {
        z.h = 1.0 - z.y;
    }
    z
}

impl Options {
    pub fn profile_dir(root: &Path) -> PathBuf {
        root.join("Profiles")
    }

    /// Имена сохранённых профилей (без .ini), без default.
    pub fn known_profiles(root: &Path) -> Vec<String> {
        let mut v: Vec<String> = std::fs::read_dir(Self::profile_dir(root))
            .map(|rd| {
                rd.flatten()
                    .filter_map(|e| {
                        let p = e.path();
                        if p.extension().and_then(|x| x.to_str()).map(|x| x.eq_ignore_ascii_case("ini")).unwrap_or(false) {
                            p.file_stem()
                                .and_then(|s| s.to_str())
                                .filter(|s| *s != DEFAULT_PROFILE)
                                .map(String::from)
                        } else {
                            None
                        }
                    })
                    .collect()
            })
            .unwrap_or_default();
        v.sort_by_key(|s| s.to_lowercase());
        v
    }

    /// Профиль, выбранный в прошлый раз (Profiles/current.txt).
    pub fn current_profile_name(root: &Path) -> String {
        crate::loader::read_text_file(&Self::profile_dir(root).join("current.txt"))
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| DEFAULT_PROFILE.to_string())
    }

    /// Загружает профиль; если файла нет — значения по умолчанию с этим именем.
    pub fn load_profile(root: &Path, profile: &str, set_as_current: bool) -> Options {
        let mut o = Options::default();
        {
            // default тоже читается из Profiles/default.ini, если файл есть
            // (его создаёт сохранение настроек); иначе — значения по умолчанию.
            o.profile_name = profile.to_string();
            let path = Self::profile_dir(root).join(format!("{}.ini", profile));
            if let Some(text) = crate::loader::read_text_file(&path) {
                for line in text.lines() {
                    let cols = comma_split_quote(line);
                    if cols.is_empty() {
                        continue;
                    }
                    match cols[0].as_str() {
                        "options" => o.parse_options_line(cols),
                        "monitor" if cols.len() == 2 => o.screens.push(cols[1].clone()),
                        "count" if cols.len() == 3 => {
                            if let Ok(n) = cols[2].trim().parse::<i32>() {
                                if n > 0 {
                                    o.pony_counts.insert(cols[1].clone(), n);
                                }
                            }
                        }
                        "tag" if cols.len() == 2 => o.custom_tags.push(cols[1].clone()),
                        _ => {}
                    }
                }
            }
        }
        if set_as_current {
            let _ = std::fs::create_dir_all(Self::profile_dir(root));
            let _ = std::fs::write(Self::profile_dir(root).join("current.txt"), profile);
        }
        o
    }

    fn parse_options_line(&mut self, cols: Vec<String>) {
        let mut p = Parser::new(cols);
        p.no_parse();
        self.pony_speech_enabled = p.parse_bool(Some(true));
        self.pony_speech_chance = p.parse_f32(Some(0.01), 0.0, 1.0);
        self.cursor_avoidance_enabled = p.parse_bool(Some(true));
        self.cursor_avoidance_size = p.parse_f32(Some(100.0), 0.0, 10000.0);
        self.pony_dragging_enabled = p.parse_bool(Some(true));
        self.pony_interactions_enabled = p.parse_bool(Some(true));
        self.display_pony_interactions_errors = p.parse_bool(Some(false));
        let ex = RectF::new(
            p.parse_f32(Some(0.0), 0.0, 1.0),
            p.parse_f32(Some(0.0), 0.0, 1.0),
            p.parse_f32(Some(0.0), 0.0, 1.0),
            p.parse_f32(Some(0.0), 0.0, 1.0),
        );
        self.exclusion_zone = clamp_exclusion(ex);
        self.scale_factor = p.parse_f32(Some(1.0), 0.25, 4.0);
        self.max_pony_count = p.parse_i32(Some(300), 0, 10000);
        self.alpha_blending_enabled = p.parse_bool(Some(true));
        self.pony_effects_enabled = p.parse_bool(Some(true));
        self.window_avoidance_enabled = p.parse_bool(Some(false));
        self.pony_avoids_ponies = p.parse_bool(Some(false));
        self.window_containment = p.parse_bool(Some(false));
        self.pony_teleport_enabled = p.parse_bool(Some(false));
        self.time_factor = p.parse_f32(Some(1.0), 0.1, 10.0);
        self.sound_enabled = p.parse_bool(Some(true));
        self.sound_single_channel_only = p.parse_bool(Some(false));
        self.sound_volume = p.parse_f32(Some(0.75), 0.0, 1.0);
        self.always_on_top = p.parse_bool(Some(true));
        self.suspend_for_fullscreen_application = p.parse_bool(Some(true));
        self.screensaver_sound_enabled = p.parse_bool(Some(true));
        let style = p.map(
            &[
                ("transparent", ScreensaverStyle::Transparent),
                ("solidcolor", ScreensaverStyle::SolidColor),
                ("backgroundimage", ScreensaverStyle::BackgroundImage),
            ],
            Some(ScreensaverStyle::Transparent),
            ScreensaverStyle::Transparent,
        );
        self.screensaver_style = style;
        self.screensaver_background_color = p.parse_i32(Some(0), i32::MIN, i32::MAX);
        self.screensaver_background_image_path = p.not_null(Some("")).unwrap_or_default();
        self.no_random_duplicates = p.parse_bool(Some(true));
        self.show_in_taskbar = p.parse_bool(Some(cfg!(windows)));
        let region = RectI::new(
            p.parse_i32(Some(0), i32::MIN, i32::MAX),
            p.parse_i32(Some(0), i32::MIN, i32::MAX),
            p.parse_i32(Some(0), 0, i32::MAX),
            p.parse_i32(Some(0), 0, i32::MAX),
        );
        self.allowed_region = if region.w > 0 && region.h > 0 { Some(region) } else { None };
        self.background_color = p.parse_i32(Some(0), i32::MIN, i32::MAX);
        self.skeletal_animation = p.parse_bool(Some(false));
        self.fps_limit = p.parse_i32(Some(DEFAULT_FPS_LIMIT as i32), MIN_FPS_LIMIT as i32, MAX_FPS_LIMIT as i32) as u32;
        self.luna_moves_windows = p.parse_bool(Some(true));
        self.luna_moves_icons = p.parse_bool(Some(true));
        self.luna_sleeps_by_cursor = p.parse_bool(Some(true));
        self.luna_cursor_idle_secs = p.parse_i32(
            Some(DEFAULT_LUNA_IDLE_SECS as i32),
            MIN_LUNA_IDLE_SECS as i32,
            MAX_LUNA_IDLE_SECS as i32,
        ) as u32;
        self.luna_music = p.parse_bool(Some(true));
        self.luna_moves_ponies = p.parse_bool(Some(true));
    }

    /// Сохраняет профиль (не default).
    pub fn save_profile(&self, root: &Path, profile: &str) -> Result<(), String> {
        // default сохранять можно (иначе настройки не переживали бы перезапуск),
        // но создать новый профиль с таким именем через valid_profile_name нельзя.
        if profile != DEFAULT_PROFILE && !valid_profile_name(profile) {
            return Err("invalid profile name".to_string());
        }
        let b = |v: bool| if v { "True" } else { "False" };
        let region = self.allowed_region.unwrap_or_default();
        let style = match self.screensaver_style {
            ScreensaverStyle::Transparent => "Transparent",
            ScreensaverStyle::SolidColor => "SolidColor",
            ScreensaverStyle::BackgroundImage => "BackgroundImage",
        };
        let opt_line = [
            "options".to_string(),
            b(self.pony_speech_enabled).to_string(),
            self.pony_speech_chance.to_string(),
            b(self.cursor_avoidance_enabled).to_string(),
            self.cursor_avoidance_size.to_string(),
            b(self.pony_dragging_enabled).to_string(),
            b(self.pony_interactions_enabled).to_string(),
            b(self.display_pony_interactions_errors).to_string(),
            self.exclusion_zone.x.to_string(),
            self.exclusion_zone.y.to_string(),
            self.exclusion_zone.w.to_string(),
            self.exclusion_zone.h.to_string(),
            self.scale_factor.to_string(),
            self.max_pony_count.to_string(),
            b(self.alpha_blending_enabled).to_string(),
            b(self.pony_effects_enabled).to_string(),
            b(self.window_avoidance_enabled).to_string(),
            b(self.pony_avoids_ponies).to_string(),
            b(self.window_containment).to_string(),
            b(self.pony_teleport_enabled).to_string(),
            self.time_factor.to_string(),
            b(self.sound_enabled).to_string(),
            b(self.sound_single_channel_only).to_string(),
            self.sound_volume.to_string(),
            b(self.always_on_top).to_string(),
            b(self.suspend_for_fullscreen_application).to_string(),
            b(self.screensaver_sound_enabled).to_string(),
            style.to_string(),
            self.screensaver_background_color.to_string(),
            self.screensaver_background_image_path.clone(),
            b(self.no_random_duplicates).to_string(),
            b(self.show_in_taskbar).to_string(),
            region.x.to_string(),
            region.y.to_string(),
            region.w.to_string(),
            region.h.to_string(),
            self.background_color.to_string(),
            b(self.skeletal_animation).to_string(),
            self.fps_limit.to_string(),
            b(self.luna_moves_windows).to_string(),
            b(self.luna_moves_icons).to_string(),
            b(self.luna_sleeps_by_cursor).to_string(),
            self.luna_cursor_idle_secs.to_string(),
            b(self.luna_music).to_string(),
            b(self.luna_moves_ponies).to_string(),
        ]
        .join(",");
        let mut out = String::new();
        out.push_str(&opt_line);
        out.push('\n');
        for s in &self.screens {
            out.push_str(&format!("monitor,{}\n", quoted(s)));
        }
        for (k, v) in &self.pony_counts {
            if *v > 0 {
                out.push_str(&format!("count,{},{}\n", quoted(k), v));
            }
        }
        for t in &self.custom_tags {
            out.push_str(&format!("tag,{}\n", quoted(t)));
        }
        std::fs::create_dir_all(Self::profile_dir(root)).map_err(|e| e.to_string())?;
        std::fs::write(Self::profile_dir(root).join(format!("{}.ini", profile)), out).map_err(|e| e.to_string())
    }

    pub fn delete_profile(root: &Path, profile: &str) -> bool {
        valid_profile_name(profile) && std::fs::remove_file(Self::profile_dir(root).join(format!("{}.ini", profile))).is_ok()
    }

    pub fn total_ponies(&self) -> i32 {
        self.pony_counts.values().sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn profile_roundtrip() {
        let tmp = std::env::temp_dir().join(format!("dp_profiles_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&tmp);
        let mut o = Options::default();
        o.profile_name = "mine".into();
        o.scale_factor = 1.5;
        o.pony_speech_chance = 0.25;
        o.screens = vec!["\\\\.\\DISPLAY2".into()];
        o.pony_counts.insert("Twilight Sparkle".into(), 3);
        o.custom_tags.push("Faves".into());
        o.allowed_region = Some(RectI::new(10, 20, 300, 400));
        o.exclusion_zone = RectF::new(0.1, 0.2, 0.3, 0.4);
        o.pony_teleport_enabled = true;
        o.save_profile(&tmp, "mine").unwrap();
        assert_eq!(Options::known_profiles(&tmp), vec!["mine"]);
        let l = Options::load_profile(&tmp, "mine", true);
        assert_eq!(l.scale_factor, 1.5);
        assert_eq!(l.pony_speech_chance, 0.25);
        assert_eq!(l.screens, o.screens);
        assert_eq!(l.pony_counts.get("Twilight Sparkle"), Some(&3));
        assert_eq!(l.custom_tags, vec!["Faves"]);
        assert_eq!(l.allowed_region, Some(RectI::new(10, 20, 300, 400)));
        assert!(l.pony_teleport_enabled);
        assert!((l.exclusion_zone.w - 0.3).abs() < 1e-6);
        assert_eq!(Options::current_profile_name(&tmp), "mine");
        assert!(Options::delete_profile(&tmp, "mine"));
        assert!(Options::save_profile(&o, &tmp, "a/b").is_err());
        // default сохраняется и читается обратно, но не попадает в список профилей.
        o.fps_limit = 144;
        assert!(Options::save_profile(&o, &tmp, DEFAULT_PROFILE).is_ok());
        assert!(Options::known_profiles(&tmp).is_empty());
        assert_eq!(Options::load_profile(&tmp, DEFAULT_PROFILE, false).fps_limit, 144);
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn original_profile_line_is_parsed() {
        let tmp = std::env::temp_dir().join(format!("dp_profiles_orig_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(tmp.join("Profiles")).unwrap();
        // Строка, записанная оригинальной программой.
        std::fs::write(
            tmp.join("Profiles").join("orig.ini"),
            "options,True,0.01,True,100,True,True,False,0,0,0,0,1,300,True,True,False,False,False,False,1,True,False,0.75,True,True,True,Transparent,0,,True,True,0,0,0,0,0\nmonitor,\"\\\\.\\DISPLAY1\"\ncount,\"Applejack\",2\n",
        )
        .unwrap();
        let o = Options::load_profile(&tmp, "orig", false);
        assert_eq!(o.max_pony_count, 300);
        assert_eq!(o.screens, vec!["\\\\.\\DISPLAY1"]);
        assert_eq!(o.pony_counts["Applejack"], 2);
        assert!(o.allowed_region.is_none());
        let _ = std::fs::remove_dir_all(&tmp);
    }
}
