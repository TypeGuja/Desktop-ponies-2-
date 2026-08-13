// src_rust/context_menu.rs

// ДОБАВЛЕНО: раньше 180.0/28.0/4.0 (ширина меню/высота пункта/отступ) были
// продублированы как "магические числа" в трёх местах (hit_test,
// is_point_inside, main.rs::render_context_menu), и их легко было развести
// в разные стороны при правке одного места без другого. Вынесены в общие
// константы + helper menu_size(), которым main.rs тоже пользуется при
// создании отдельного окна-хитбокса меню.
pub const MENU_WIDTH: f32 = 180.0;
pub const ITEM_HEIGHT: f32 = 28.0;
pub const MENU_PADDING: f32 = 4.0;

/// Полный размер меню (ширина, высота) в пикселях для данного числа пунктов.
pub fn menu_size(item_count: usize) -> (u32, u32) {
    let height = item_count as f32 * ITEM_HEIGHT + MENU_PADDING * 2.0;
    (MENU_WIDTH as u32, height.ceil() as u32)
}

// ИЗМЕНЕНО: сверился с настоящим оригиналом контекстного меню
// (DesktopPonyAnimator.vb::CreatePonyMenu/DisplayPonyMenu — не Pony.vb).
// Добавлены RemoveEvery (соответствует "Remove Every {name}" в оригинале) и
// настоящий выбор конкретного пони при добавлении (подменю, как
// "Add Pony" → список в оригинале) вместо мгновенного случайного спавна.
#[derive(Clone, Debug, PartialEq)]
pub enum PonyAction {
    Remove,
    RemoveEvery,
    ToggleSleep,
    ToggleSleepAll,
    OpenAddPonyMenu,
    SpawnRandomPony,
    SpawnNamedPony(String),
    BackToMainMenu,
    ReturnToMenu,
    Exit,
}

#[derive(Clone, Debug)]
pub struct MenuItem {
    pub label: String,
    pub action: PonyAction,
    pub enabled: bool,
}

impl MenuItem {
    pub fn new(label: &str, action: PonyAction) -> Self {
        Self {
            label: label.to_string(),
            action,
            enabled: true,
        }
    }
}

pub struct ContextMenu {
    pub visible: bool,
    pub x: f32,
    pub y: f32,
    pub pony_index: Option<usize>,
    pub pony_name: Option<String>,
    pub items: Vec<MenuItem>,
}

impl ContextMenu {
    pub fn new() -> Self {
        Self {
            visible: false,
            x: 0.0,
            y: 0.0,
            pony_index: None,
            pony_name: None,
            // Пункты пересобираются в show() под конкретного пони (Remove
            // должен показывать его имя) — здесь достаточно пустого списка,
            // он не отображается, пока меню не открыто.
            items: Vec::new(),
        }
    }

    // ИЗМЕНЕНО: пункты меню собираются заново при каждом открытии — не
    // только из-за имени в "Remove", но и потому что подписи Sleep/Pause и
    // Sleep/Pause All должны переключаться на "Wake up/Resume" в зависимости
    // от текущего состояния (как в оригинале, DisplayPonyMenu), а не быть
    // статичными.
    pub fn show(&mut self, x: f32, y: f32, pony_index: usize, pony_name: &str,
                is_sleeping: bool, all_sleeping: bool) {
        self.visible = true;
        self.x = x;
        self.y = y;
        self.pony_index = Some(pony_index);
        self.pony_name = Some(pony_name.to_string());
        self.items = Self::build_main_items(pony_name, is_sleeping, all_sleeping);
    }

    /// Пересобирает пункты в главный список (используется и при первом
    /// открытии, и при возврате из подменю "Add Pony" кнопкой "← Back").
    pub fn show_main_menu(&mut self, is_sleeping: bool, all_sleeping: bool) {
        let pony_name = self.pony_name.clone().unwrap_or_default();
        self.items = Self::build_main_items(&pony_name, is_sleeping, all_sleeping);
    }

    fn build_main_items(pony_name: &str, is_sleeping: bool, all_sleeping: bool) -> Vec<MenuItem> {
        vec![
            MenuItem::new(&format!("🗑 Remove ({})", pony_name), PonyAction::Remove),
            MenuItem::new(&format!("🗑 Remove Every ({})", pony_name), PonyAction::RemoveEvery),
            MenuItem::new(
                if is_sleeping { "☀ Wake up/Resume" } else { "💤 Sleep/Pause" },
                PonyAction::ToggleSleep,
            ),
            MenuItem::new(
                if all_sleeping { "☀ Wake up/Resume All" } else { "💤 Sleep/Pause All" },
                PonyAction::ToggleSleepAll,
            ),
            MenuItem::new("➕ Add Pony ▸", PonyAction::OpenAddPonyMenu),
            MenuItem::new("🏠 Return to Menu", PonyAction::ReturnToMenu),
            MenuItem::new("✖ Exit", PonyAction::Exit),
        ]
    }

    // ДОБАВЛЕНО: подменю выбора конкретного пони для добавления — аналог
    // "Add Pony" → список пони в оригинале (там ещё и по тегам сгруппировано,
    // здесь для простоты плоский список, но выбор конкретного пони, а не
    // мгновенный случайный спавн, сохранён).
    pub fn show_add_pony_list(&mut self, pony_names: &[String]) {
        let mut items = Vec::with_capacity(pony_names.len() + 2);
        items.push(MenuItem::new("🎲 Random", PonyAction::SpawnRandomPony));
        for name in pony_names {
            items.push(MenuItem::new(name, PonyAction::SpawnNamedPony(name.clone())));
        }
        items.push(MenuItem::new("← Back", PonyAction::BackToMainMenu));
        self.items = items;
    }

    pub fn hide(&mut self) {
        self.visible = false;
        self.pony_index = None;
        self.pony_name = None;
    }

    // ИСПРАВЛЕНО: раньше hit_test принимал координаты мыши в системе
    // координат ГЛАВНОГО окна и сам вычитал self.x/self.y, потому что меню
    // рисовалось прямо на поверхности главного окна. Теперь у меню
    // собственное окно-хитбокс (см. MenuWindow в main.rs), и координаты
    // клика уже приходят локальными для этого окна (0,0 — левый верхний
    // угол меню) — вычитать self.x/self.y больше не нужно, поэтому и сам
    // метод стал проще и надёжнее (не зависит от синхронизации между
    // положением окна меню и хранимыми self.x/self.y).
    pub fn hit_test(&self, local_x: f32, local_y: f32) -> Option<usize> {
        if !self.visible {
            return None;
        }

        if local_x < 0.0 || local_x > MENU_WIDTH {
            return None;
        }

        let rel_y = local_y - MENU_PADDING;
        if rel_y < 0.0 {
            return None;
        }

        let index = (rel_y / ITEM_HEIGHT) as usize;
        if index < self.items.len() && self.items[index].enabled {
            Some(index)
        } else {
            None
        }
    }

    /// Получить действие по индексу
    pub fn get_action(&self, index: usize) -> Option<PonyAction> {
        self.items.get(index).map(|item| item.action.clone())
    }
}
