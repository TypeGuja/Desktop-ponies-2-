// src_rust/sim.rs
//
// Симуляция пони — порт класса Pony (и Effect / House / PonyContext) из
// оригинального Desktop Ponies 1.69 (Pony.vb). Логика шагов, выбор
// поведений, движение, отскоки, речь, эффекты, взаимодействия и дома
// повторяют оригинал: шаг симуляции 25 Гц (StepRate), скорость в пикселях за
// шаг, состояния MouseOver / Drag / Sleep, следование за целью и т.д.
//
// Модуль не зависит от окон и графики: всё окружение (регион экрана,
// курсор, окна для избегания) приходит через Context. Это позволяет
// тестировать поведение детерминированно (fastrand с фиксированным seed).

use crate::math::{RectF, RectI, V2};
use crate::model::*;
use std::collections::{HashMap, HashSet};
use std::rc::Rc;

pub const STEP_RATE: f64 = 25.0;
/// Длительность шага в миллисекундах.
pub const STEP_SIZE: f64 = 1000.0 / STEP_RATE;
pub const EPSILON: f32 = 1.0 / 16777216.0;
const RANDOM_SPEECH_DELAY_MS: f64 = 10_000.0;
const RECALL_EXPIRE_DELAY_MS: f64 = 3_000.0;

pub type PonyId = u64;
pub type EffectId = u64;

// ------------------------------------------------------------------ Context

pub struct Context {
    pub effects_enabled: bool,
    pub speech_enabled: bool,
    pub interactions_enabled: bool,
    pub random_speech_chance: f64,
    pub cursor_avoidance_enabled: bool,
    pub cursor_avoidance_radius: f32,
    pub dragging_enabled: bool,
    pub pony_avoidance_enabled: bool,
    pub window_avoidance_enabled: bool,
    pub stay_in_containing_window: bool,
    pub time_factor: f64,
    pub scale_factor: f32,
    pub region: RectI,
    /// Нормализованная зона исключения (0..1 от региона).
    pub exclusion_zone: RectF,
    pub teleportation_enabled: bool,
    pub cursor: (i32, i32),
    /// Окно под точкой экрана (для избегания окон / ограничения окном).
    pub window_at_point: Option<Box<dyn Fn(i32, i32) -> Option<RectI>>>,
    /// Реальные рабочие области мониторов внутри region (пусто = весь region).
    pub areas: Vec<RectI>,
    /// Куски region, где экрана нет (мониторы разного размера): пони туда не заходят.
    pub dead_zones: Vec<RectI>,
}

impl Context {
    pub fn new(region: RectI) -> Context {
        Context {
            effects_enabled: true,
            speech_enabled: true,
            interactions_enabled: true,
            random_speech_chance: 0.01,
            cursor_avoidance_enabled: true,
            cursor_avoidance_radius: 100.0,
            dragging_enabled: true,
            pony_avoidance_enabled: false,
            window_avoidance_enabled: false,
            stay_in_containing_window: false,
            time_factor: 1.0,
            scale_factor: 1.0,
            region,
            exclusion_zone: RectF::EMPTY,
            teleportation_enabled: false,
            cursor: (i32::MIN, i32::MIN),
            window_at_point: None,
            areas: Vec::new(),
            dead_zones: Vec::new(),
        }
    }

    /// Все запретные прямоугольники: зона исключения из настроек и места без экрана.
    pub fn blocked_regions(&self) -> Vec<RectI> {
        let mut v = Vec::new();
        let ex = self.exclusion_region();
        if !(ex.w == 0 && ex.h == 0) {
            v.push(ex);
        }
        v.extend(self.dead_zones.iter().copied());
        v
    }

    /// Рабочая область монитора, в которой точка (или весь region, если мониторы не заданы).
    pub fn area_at(&self, x: i32, y: i32) -> RectI {
        self.areas.iter().copied().find(|a| a.contains_point(x, y)).unwrap_or_else(|| {
            // ближайшая по расстоянию до центра — если точка в «мёртвой зоне»
            self.areas
                .iter()
                .copied()
                .min_by_key(|a| {
                    let cx = x.clamp(a.x, a.right() - 1);
                    let cy = y.clamp(a.y, a.bottom() - 1);
                    (cx - x).abs() + (cy - y).abs()
                })
                .unwrap_or(self.region)
        })
    }

    /// Options.GetExclusionArea
    pub fn exclusion_region(&self) -> RectI {
        let a = self.region;
        let z = self.exclusion_zone;
        let x = a.x as f32 + a.w as f32 * z.x;
        let y = a.y as f32 + a.h as f32 * z.y;
        let w = a.w as f32 * z.w;
        let h = a.h as f32 * z.h;
        let mut r = RectI::new(x.round() as i32, y.round() as i32, w.round() as i32, h.round() as i32);
        if r.right() > a.right() {
            r.w -= r.right() - a.right();
        }
        if r.bottom() > a.bottom() {
            r.h -= r.bottom() - a.bottom();
        }
        r
    }
}

// ------------------------------------------------------------------ Effect

pub struct Effect {
    pub id: EffectId,
    pub base: Rc<PonyBase>,
    pub base_index: usize,
    /// Пони-владелец (для Follow-эффектов и позиции).
    pub owner: Option<PonyId>,
    internal_start_time: f64,
    current_time: f64,
    last_update_time: f64,
    pub desired_duration: Option<f64>,
    pub expired: bool,
    pub top_left: (i32, i32),
    pub facing_left: bool,
    pub being_dragged: bool,
    placement: Direction,
    centering: Direction,
    initial_offset: V2,
}

impl Effect {
    pub fn effect_base(&self) -> &EffectBase {
        &self.base.effects[self.base_index]
    }
    pub fn image(&self) -> &SpriteImage {
        let e = self.effect_base();
        if self.facing_left { &e.left_image } else { &e.right_image }
    }
    pub fn facing_right(&self) -> bool {
        !self.facing_left
    }
    pub fn current_image_size(&self) -> V2 {
        self.image().size_v()
    }
    /// Время от начала показа эффекта (для анимации гифки), мс.
    pub fn image_time_index(&self) -> f64 {
        self.current_time - self.internal_start_time
    }
    pub fn region(&self, scale: f32) -> RectI {
        let s = self.current_image_size();
        RectI::new(self.top_left.0, self.top_left.1, (s.x * scale) as i32, (s.y * scale) as i32)
    }
}

fn direction_weight_h(rng: &mut fastrand::Rng, d: Direction) -> f32 {
    match d {
        Direction::TopLeft | Direction::MiddleLeft | Direction::BottomLeft => 0.0,
        Direction::TopCenter | Direction::MiddleCenter | Direction::BottomCenter => 0.5,
        Direction::TopRight | Direction::MiddleRight | Direction::BottomRight => 1.0,
        Direction::Random | Direction::RandomNotCenter => rng.f32(),
    }
}

fn direction_weight_v(rng: &mut fastrand::Rng, d: Direction) -> f32 {
    match d {
        Direction::TopLeft | Direction::TopCenter | Direction::TopRight => 0.0,
        Direction::MiddleLeft | Direction::MiddleCenter | Direction::MiddleRight => 0.5,
        Direction::BottomLeft | Direction::BottomCenter | Direction::BottomRight => 1.0,
        Direction::Random | Direction::RandomNotCenter => rng.f32(),
    }
}

/// Effect.GetEffectLocation
pub fn effect_location(
    rng: &mut fastrand::Rng,
    effect_size: V2,
    placement: Direction,
    parent_top_left: V2,
    parent_size: V2,
    centering: Direction,
    scale: f32,
) -> (i32, i32) {
    let psx = parent_size.x * direction_weight_h(rng, placement);
    let psy = parent_size.y * direction_weight_v(rng, placement);
    let on_parent = V2::new(parent_top_left.x + psx, parent_top_left.y + psy);
    let esx = effect_size.x * scale * direction_weight_h(rng, centering);
    let esy = effect_size.y * scale * direction_weight_v(rng, centering);
    V2::new(on_parent.x - esx, on_parent.y - esy).round()
}

const CONCRETE_DIRECTIONS: [Direction; 9] = [
    Direction::TopLeft,
    Direction::TopCenter,
    Direction::TopRight,
    Direction::MiddleLeft,
    Direction::MiddleCenter,
    Direction::MiddleRight,
    Direction::BottomLeft,
    Direction::BottomCenter,
    Direction::BottomRight,
];

fn resolve_direction(rng: &mut fastrand::Rng, d: Direction) -> Direction {
    match d {
        Direction::RandomNotCenter => {
            let opts: Vec<Direction> = CONCRETE_DIRECTIONS.iter().copied().filter(|x| *x != Direction::MiddleCenter).collect();
            opts[rng.usize(0..opts.len())]
        }
        Direction::Random => CONCRETE_DIRECTIONS[rng.usize(0..CONCRETE_DIRECTIONS.len())],
        other => other,
    }
}

// ------------------------------------------------------------------ Interaction

pub struct InteractionInst {
    pub base: InteractionBase,
    pub targets: Vec<PonyId>,
    pub trigger: Option<PonyId>,
    pub initiator: Option<PonyId>,
    pub involved_targets: Vec<PonyId>,
}

// ------------------------------------------------------------------ Pony

/// Удержание пони на месте в заданном поведении (Луна колдует: зависает в
/// позе полёта лицом к цели). Сон, перетаскивание и наведение курсора важнее.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Hold {
    pub behavior: usize,
    pub facing_right: bool,
}

struct EffectRepeat {
    base_index: usize,
    last_external_start: f64,
    last_internal_start: f64,
}

pub struct Pony {
    pub id: PonyId,
    pub base: Rc<PonyBase>,

    current_time: f64,
    last_update_time: f64,
    pub expired: bool,
    behavior_start_time: f64,
    behavior_desired_duration: f64,
    current_behavior: usize,
    visual_override: Option<usize>,
    behavior_changed_during_step: bool,
    facing_right: bool,
    region: RectI,
    location: V2,
    movement: V2,
    movement_without_destination_needed: bool,
    follow_target: Option<PonyId>,
    destination: Option<V2>,
    last_step_in_bounds: bool,
    rebound_cooldown_end: f64,
    rebounding_into_containment: bool,
    allowing_natural_return: bool,
    speech_start: f64,
    speech_duration: f64,
    current_speech_text: Option<String>,
    current_speech_sound: Option<String>,
    effect_bases_to_repeat: Vec<EffectRepeat>,
    effects_to_manually_expire: Vec<EffectId>,
    active_effects: Vec<EffectId>,
    interactions: Vec<u64>,
    current_interaction: Option<u64>,
    interaction_cooldown_end: f64,
    in_mouseover: bool,
    in_drag: bool,
    in_sleep: bool,
    behavior_before_special: Option<usize>,
    drag_behaviors: HashMap<i32, usize>,
    mouseover_behaviors: HashMap<i32, usize>,
    sleep_behavior: usize,
    has_stationary: bool,
    has_moving: bool,
    at_destination_override: Option<bool>,
    in_region: Option<bool>,

    // Публично устанавливаемые
    pub drag: bool,
    pub sleep: bool,
    pub movement_override: Option<V2>,
    speed_override: Option<f64>,
    pub destination_override: Option<V2>,
    pub follow_target_override: Option<PonyId>,
    pub hold: Option<Hold>,
    /// Пони несёт магия (Луна): она в drag-состоянии, но стоит здесь, а не под курсором.
    pub carry: Option<V2>,
}

impl Pony {
    fn new(id: PonyId, base: Rc<PonyBase>) -> Pony {
        assert!(!base.behaviors.is_empty(), "base must contain at least one behavior");
        let mut p = Pony {
            id,
            base: base.clone(),
            current_time: 0.0,
            last_update_time: 0.0,
            expired: false,
            behavior_start_time: 0.0,
            behavior_desired_duration: 0.0,
            current_behavior: 0,
            visual_override: None,
            behavior_changed_during_step: false,
            facing_right: false,
            region: RectI::default(),
            location: V2::NAN,
            movement: V2::ZERO,
            movement_without_destination_needed: false,
            follow_target: None,
            destination: None,
            last_step_in_bounds: true,
            rebound_cooldown_end: 0.0,
            rebounding_into_containment: false,
            allowing_natural_return: false,
            speech_start: -RANDOM_SPEECH_DELAY_MS,
            speech_duration: 0.0,
            current_speech_text: None,
            current_speech_sound: None,
            effect_bases_to_repeat: Vec::new(),
            effects_to_manually_expire: Vec::new(),
            active_effects: Vec::new(),
            interactions: Vec::new(),
            current_interaction: None,
            interaction_cooldown_end: 0.0,
            in_mouseover: false,
            in_drag: false,
            in_sleep: false,
            behavior_before_special: None,
            drag_behaviors: HashMap::new(),
            mouseover_behaviors: HashMap::new(),
            sleep_behavior: 0,
            has_stationary: false,
            has_moving: false,
            at_destination_override: None,
            in_region: None,
            drag: false,
            sleep: false,
            movement_override: None,
            speed_override: None,
            destination_override: None,
            follow_target_override: None,
            hold: None,
            carry: None,
        };

        let flagged_sleep = p.behavior_matching(&[&|b: &Behavior| b.allowed_movement & moves::SLEEP != 0]);
        p.sleep_behavior = flagged_sleep.unwrap_or_else(|| p.fallback_stationary(ANY_GROUP));

        let groups: HashSet<i32> = base.behaviors.iter().map(|b| b.group).collect();
        for group in groups {
            let fallback = p.fallback_stationary(group);
            let mo = p
                .behavior_matching(&[&|b: &Behavior| b.group == group && b.allowed_movement & moves::MOUSE_OVER != 0])
                .unwrap_or(fallback);
            p.mouseover_behaviors.insert(group, mo);
            let dr = p
                .behavior_matching(&[&|b: &Behavior| b.group == group && b.allowed_movement & moves::DRAGGED != 0])
                .unwrap_or_else(|| flagged_sleep.unwrap_or(mo));
            p.drag_behaviors.insert(group, dr);
        }
        p.has_stationary = base.behaviors.iter().any(|b| b.speed_px_per_sec() == 0.0);
        p.has_moving = base.behaviors.iter().any(|b| b.speed_px_per_sec() > 0.0);
        p
    }

    fn behavior_matching(&self, predicates: &[&dyn Fn(&Behavior) -> bool]) -> Option<usize> {
        for pr in predicates {
            for (i, b) in self.base.behaviors.iter().enumerate() {
                if pr(b) {
                    return Some(i);
                }
            }
        }
        None
    }

    fn fallback_stationary(&self, group: i32) -> usize {
        let m = self.behavior_matching(&[
            &|b: &Behavior| b.group == group && b.speed_px_per_sec() == 0.0 && !b.skip && b.target_mode() == TargetMode::None,
            &|b: &Behavior| b.group == group && b.speed_px_per_sec() == 0.0,
            &|b: &Behavior| b.speed_px_per_sec() == 0.0 && !b.skip && b.target_mode() == TargetMode::None,
            &|b: &Behavior| b.speed_px_per_sec() == 0.0,
        ]);
        if let Some(m) = m {
            return m;
        }
        let mut best = 0;
        for i in 1..self.base.behaviors.len() {
            if self.base.behaviors[i].speed_px_per_sec() < self.base.behaviors[best].speed_px_per_sec() {
                best = i;
            }
        }
        best
    }

    // ---- публичное состояние
    pub fn location(&self) -> V2 { self.location }
    pub fn set_location(&mut self, l: V2) { self.location = l; }
    pub fn facing_right(&self) -> bool { self.facing_right }
    pub fn region(&self) -> RectI { self.region }
    pub fn current_behavior(&self) -> &Behavior { &self.base.behaviors[self.current_behavior] }
    pub fn current_behavior_index(&self) -> usize { self.current_behavior }
    pub fn current_behavior_group(&self) -> i32 { self.base.behaviors[self.current_behavior].group }
    pub fn speech_text(&self) -> Option<&str> { self.current_speech_text.as_deref() }
    pub fn take_speech_sound(&mut self) -> Option<String> { self.current_speech_sound.take() }
    pub fn speech_sound(&self) -> Option<&str> { self.current_speech_sound.as_deref() }
    pub fn destination(&self) -> Option<V2> { self.destination }
    pub fn movement(&self) -> V2 { self.movement }
    pub fn set_facing_right(&mut self, v: bool) { self.facing_right = v; }

    /// Сдвиг для отрисовки между шагами симуляции. Симуляция идёт по 25 шагов
    /// в секунду, а кадры рисуются чаще; без этого пони двигались бы рывками
    /// раз в шаг. Сдвиг — доля движения последнего шага, прошедшая с момента
    /// этого шага. На логику (позицию, попадания, границы) он не влияет.
    pub fn render_offset(&self, now_ms: f64, time_factor: f64) -> V2 {
        if self.drag || self.in_drag || self.in_sleep {
            return V2::ZERO;
        }
        let step = STEP_SIZE / time_factor;
        let frac = ((now_ms - self.last_update_time) / step).clamp(0.0, 1.0) as f32;
        self.movement * frac
    }
    pub fn is_sleeping(&self) -> bool { self.in_sleep }
    /// Пони сейчас тащат мышью (симуляция подтвердила захват).
    pub fn is_dragging(&self) -> bool { self.in_drag && self.carry.is_none() }
    /// Пони в drag-состоянии, но несёт её магия, а не курсор.
    pub fn is_carried(&self) -> bool { self.in_drag && self.carry.is_some() }
    pub fn speed_override(&self) -> Option<f64> { self.speed_override }
    pub fn set_speed_override(&mut self, v: Option<f64>) { self.speed_override = v.map(|x| x.max(0.0)); }

    pub fn is_busy(&self) -> bool {
        self.current_interaction.is_some()
            || self.in_mouseover
            || self.in_drag
            || self.in_sleep
            || self.movement_override.is_some()
            || self.destination_override.is_some()
            || self.hold.is_some()
    }

    pub fn at_destination(&self) -> bool {
        match self.destination {
            Some(d) => V2::dist_sq(self.location, d) < EPSILON,
            None => false,
        }
    }

    /// Поведение, чьё изображение сейчас показывается.
    pub fn image_behavior_index(&self) -> usize {
        self.visual_override.unwrap_or(self.current_behavior)
    }

    pub fn current_image(&self) -> &SpriteImage {
        let b = &self.base.behaviors[self.image_behavior_index()];
        if self.facing_right { &b.right_image } else { &b.left_image }
    }

    /// Время анимации изображения (мс от начала поведения).
    pub fn image_time_index(&self) -> f64 {
        self.current_time - self.behavior_start_time
    }

    pub fn prevent_animation_loop(&self) -> bool {
        self.base.behaviors[self.current_behavior].do_not_repeat_image_animations
    }

    fn region_f_for_image(&self, image: &SpriteImage, scale: f32) -> RectF {
        let c = image.center();
        let s = image.size_v();
        RectF::new(
            self.location.x - c.x * scale,
            self.location.y - c.y * scale,
            s.x * scale,
            s.y * scale,
        )
    }

    fn region_f(&self, scale: f32) -> RectF {
        self.region_f_for_image(self.current_image(), scale)
    }
}

// ------------------------------------------------------------------ House

pub struct House {
    pub id: u64,
    pub base: Rc<HouseBase>,
    pub top_left: (i32, i32),
    pub expired: bool,
    pub drag: bool,
    deployed: HashSet<PonyId>,
    recalling: HashSet<PonyId>,
    recall_expiring: HashMap<PonyId, f64>,
    last_cycle_time: f64,
}

impl House {
    pub fn region(&self, scale: f32) -> RectI {
        let s = self.base.image.size;
        RectI::new(self.top_left.0, self.top_left.1, (s.0 as f32 * scale) as i32, (s.1 as f32 * scale) as i32)
    }
}

// ------------------------------------------------------------------ World

pub struct World {
    pub ctx: Context,
    pub ponies: Vec<Pony>,
    pub effects: Vec<Effect>,
    pub houses: Vec<House>,
    interactions: HashMap<u64, InteractionInst>,
    /// Все известные пони (для случайных гостей домов).
    pub all_bases: Vec<Rc<PonyBase>>,
    pub max_pony_count: usize,
    rng: fastrand::Rng,
    next_id: u64,
    next_interaction_id: u64,
    /// Текущее время симуляции (мс).
    pub elapsed: f64,
    interactions_dirty: bool,
}

impl World {
    pub fn new(ctx: Context, seed: Option<u64>) -> World {
        World {
            ctx,
            ponies: Vec::new(),
            effects: Vec::new(),
            houses: Vec::new(),
            interactions: HashMap::new(),
            all_bases: Vec::new(),
            max_pony_count: 500,
            rng: match seed {
                Some(s) => fastrand::Rng::with_seed(s),
                None => fastrand::Rng::new(),
            },
            next_id: 1,
            next_interaction_id: 1,
            elapsed: 0.0,
            interactions_dirty: false,
        }
    }

    pub fn rng(&mut self) -> &mut fastrand::Rng {
        &mut self.rng
    }

    pub fn idx(&self, id: PonyId) -> Option<usize> {
        self.ponies.iter().position(|p| p.id == id)
    }

    pub fn pony(&self, id: PonyId) -> Option<&Pony> {
        self.idx(id).map(|i| &self.ponies[i])
    }

    pub fn pony_mut(&mut self, id: PonyId) -> Option<&mut Pony> {
        let i = self.idx(id)?;
        Some(&mut self.ponies[i])
    }

    /// Добавляет пони и запускает её (Start).
    pub fn add_pony(&mut self, base: Rc<PonyBase>) -> PonyId {
        let id = self.next_id;
        self.next_id += 1;
        self.ponies.push(Pony::new(id, base));
        let i = self.ponies.len() - 1;
        self.start_pony(i);
        self.interactions_dirty = true;
        id
    }

    pub fn add_pony_at(&mut self, base: Rc<PonyBase>, location: V2) -> PonyId {
        let id = self.next_id;
        self.next_id += 1;
        let mut p = Pony::new(id, base);
        p.location = location;
        self.ponies.push(p);
        let i = self.ponies.len() - 1;
        self.start_pony(i);
        self.interactions_dirty = true;
        id
    }

    pub fn remove_pony(&mut self, id: PonyId) {
        if let Some(i) = self.idx(id) {
            self.expire_pony(i);
        }
    }

    // ------------------------------------------------------------ update

    /// Продвигает симуляцию до момента now_ms (мс).
    pub fn update(&mut self, now_ms: f64) {
        self.elapsed = now_ms;
        if self.interactions_dirty {
            self.initialize_interactions();
            self.interactions_dirty = false;
        }

        // Дома: цикл гостей
        let manual: Vec<PonyId> = self
            .ponies
            .iter()
            .filter(|p| p.speed_override.is_some() && p.destination_override.is_some())
            .map(|p| p.id)
            .collect();
        for h in 0..self.houses.len() {
            self.cycle_visitors(h, &manual);
        }

        for i in 0..self.ponies.len() {
            self.update_pony(i, now_ms);
        }
        for e in 0..self.effects.len() {
            self.update_effect(e, now_ms);
        }
        self.cleanup_expired();
    }

    fn cleanup_expired(&mut self) {
        let removed: Vec<PonyId> = self.ponies.iter().filter(|p| p.expired).map(|p| p.id).collect();
        if !removed.is_empty() {
            self.ponies.retain(|p| !p.expired);
            self.interactions_dirty = true;
            // Гости домов, покинувшие мир.
            for h in &mut self.houses {
                for id in &removed {
                    h.deployed.remove(id);
                    h.recalling.remove(id);
                    h.recall_expiring.remove(id);
                }
            }
        }
        self.effects.retain(|e| !e.expired);
        self.houses.retain(|h| !h.expired);
    }

    fn update_pony(&mut self, i: usize, update_time: f64) {
        self.ponies[i].current_speech_sound = None;
        let scaled_step = STEP_SIZE / self.ctx.time_factor;
        while !self.ponies[i].expired && update_time - self.ponies[i].last_update_time >= scaled_step {
            self.ponies[i].last_update_time += scaled_step;
            self.step_once(i);
        }
    }

    fn start_pony(&mut self, i: usize) {
        let start = self.elapsed;
        {
            let p = &mut self.ponies[i];
            p.current_time = start;
            p.last_update_time = start;
        }
        self.set_behavior_internal(i, None, true);
        if self.ponies[i].location.is_nan() {
            let scale = self.ctx.scale_factor;
            let region = self.ctx.region;
            let rf = self.ponies[i].region_f(scale);
            let area = V2::new(region.w as f32 - rf.w, region.h as f32 - rf.h);
            let center = self.ponies[i].current_image().center() * scale;
            let blocked = self.ctx.dead_zones.clone();
            for attempt in 0..40 {
                let rx = self.rng.f64() as f32;
                let ry = self.rng.f64() as f32;
                self.ponies[i].location = center + V2::new(area.x * rx, area.y * ry) + V2::new(region.x as f32, region.y as f32);
                let r = self.ponies[i].region_f(scale);
                if attempt == 39 || !blocked.iter().any(|b| r.intersects(&b.to_f())) {
                    break;
                }
            }
        }
        self.update_state(i, true, true);
    }

    fn step_once(&mut self, i: usize) {
        {
            let p = &mut self.ponies[i];
            p.current_time += STEP_SIZE;
            p.destination = None;
            p.behavior_changed_during_step = false;
        }
        let exited_sleep = self.handle_sleep(i);
        let exited_mo_drag = self.handle_mouseover_and_drag(i);
        self.apply_hold(i);
        let dest_override = self.ponies[i].destination_override;
        let mut at_override = self.ponies[i].at_destination_override;
        self.send_to_custom_destination(i, dest_override, &mut at_override);
        self.ponies[i].at_destination_override = at_override;
        self.handle_follow_target_override(i);
        self.start_interaction_at_random(i);

        let expired = {
            let p = &self.ponies[i];
            p.behavior_desired_duration < p.current_time - p.behavior_start_time
        };
        if expired {
            let base = self.ponies[i].base.clone();
            let cur = self.ponies[i].current_behavior;
            let linked = base.behavior_by_name(&base.behaviors[cur].linked_behavior);
            if linked.is_none() {
                self.end_interaction(i, false, false);
            }
            let end_line = base.speech_by_name(&base.behaviors[cur].end_line);
            if let Some(s) = end_line {
                self.speak_internal(i, Some(s));
            }
            self.set_behavior_internal(i, linked, true);
            let cur = self.ponies[i].current_behavior;
            let b = &base.behaviors[cur];
            if base.speech_by_name(&b.start_line).is_none()
                && base.speech_by_name(&b.end_line).is_none()
                && self.rng.f64() < self.ctx.random_speech_chance
            {
                self.speak_internal(i, None);
            }
        }
        {
            let p = &mut self.ponies[i];
            if p.current_time - p.speech_start > p.speech_duration {
                p.current_speech_text = None;
            }
        }
        let tele = self.ctx.teleportation_enabled;
        self.update_state(i, tele, exited_sleep || exited_mo_drag || expired);
    }

    // ------------------------------------------------------------ special states

    fn handle_sleep(&mut self, i: usize) -> bool {
        let mut resumed = false;
        let (sleep, in_sleep) = (self.ponies[i].sleep, self.ponies[i].in_sleep);
        if sleep && !in_sleep {
            let sb = self.ponies[i].sleep_behavior;
            {
                let p = &mut self.ponies[i];
                p.in_sleep = true;
                p.behavior_before_special = Some(p.current_behavior);
            }
            let speak = self.ponies[i].base.behaviors[sb].allowed_movement & moves::SLEEP != 0;
            self.set_behavior_internal(i, Some(sb), speak);
        } else if !sleep && in_sleep {
            self.ponies[i].in_sleep = false;
            if self.ponies[i].current_interaction.is_none() {
                let prev = self.ponies[i].behavior_before_special;
                self.set_behavior_internal(i, prev, false);
            }
            self.ponies[i].behavior_before_special = None;
            resumed = true;
        }
        if self.ponies[i].in_sleep {
            self.extend_behavior_duration_indefinitely(i);
        }
        resumed
    }

    fn handle_mouseover_and_drag(&mut self, i: usize) -> bool {
        let mut resumed = false;
        let scale = self.ctx.scale_factor;
        let cursor = self.ctx.cursor;
        let group = self.ponies[i].current_behavior_group();
        let mo_idx = *self.ponies[i].mouseover_behaviors.get(&group).unwrap_or(&0);
        let is_mouse_over = {
            let p = &self.ponies[i];
            let b = &p.base.behaviors[mo_idx];
            let img = if p.facing_right { &b.right_image } else { &b.left_image };
            p.region.contains_point(cursor.0, cursor.1)
                && p.region_f_for_image(img, scale).contains_point(V2::new(cursor.0 as f32, cursor.1 as f32))
        };
        {
            let p = &self.ponies[i];
            if self.ctx.cursor_avoidance_enabled
                && is_mouse_over
                && !p.in_mouseover
                && !p.in_drag
                && p.current_interaction.is_none()
                && !p.in_sleep
            {
                self.ponies[i].in_mouseover = true;
                self.ponies[i].behavior_before_special = Some(self.ponies[i].current_behavior);
                self.set_behavior_internal(i, Some(mo_idx), false);
                self.speak_internal(i, None);
            }
        }
        let (drag, in_drag) = (self.ponies[i].drag || self.ponies[i].carry.is_some(), self.ponies[i].in_drag);
        if self.ctx.dragging_enabled && drag && !in_drag {
            self.ponies[i].in_drag = true;
            if self.ponies[i].behavior_before_special.is_none() {
                self.ponies[i].behavior_before_special = Some(self.ponies[i].current_behavior);
            }
            if self.ponies[i].current_interaction.is_some() {
                self.end_interaction(i, true, true);
                self.ponies[i].behavior_before_special = None;
            }
            if !self.ponies[i].in_sleep {
                let g = self.ponies[i].current_behavior_group();
                let db = *self.ponies[i].drag_behaviors.get(&g).unwrap_or(&0);
                let speak = self.ponies[i].base.behaviors[db].allowed_movement & moves::DRAGGED != 0;
                self.set_behavior_internal(i, Some(db), speak);
            }
        } else if !drag && in_drag {
            self.ponies[i].in_drag = false;
            if !self.ponies[i].in_sleep {
                if self.ctx.cursor_avoidance_enabled {
                    self.ponies[i].in_mouseover = true;
                    let g = self.ponies[i].current_behavior_group();
                    let mb = *self.ponies[i].mouseover_behaviors.get(&g).unwrap_or(&0);
                    self.set_behavior_internal(i, Some(mb), false);
                } else {
                    let prev = self.ponies[i].behavior_before_special;
                    self.set_behavior_internal(i, prev, false);
                    self.ponies[i].behavior_before_special = None;
                    resumed = true;
                }
            }
        }
        if !self.ponies[i].in_drag && !is_mouse_over && self.ponies[i].in_mouseover {
            self.ponies[i].in_mouseover = false;
            let prev = self.ponies[i].behavior_before_special;
            self.set_behavior_internal(i, prev, false);
            self.ponies[i].behavior_before_special = None;
            resumed = true;
        }
        if self.ponies[i].in_mouseover || self.ponies[i].in_drag {
            self.extend_behavior_duration_indefinitely(i);
        }
        resumed
    }

    fn apply_hold(&mut self, i: usize) {
        let Some(h) = self.ponies[i].hold else { return };
        {
            let p = &self.ponies[i];
            if p.in_sleep || p.in_drag || p.in_mouseover || h.behavior >= p.base.behaviors.len() {
                return;
            }
        }
        if self.ponies[i].current_behavior != h.behavior {
            self.end_interaction(i, true, false);
            self.set_behavior_internal(i, Some(h.behavior), false);
        }
        self.ponies[i].facing_right = h.facing_right;
        self.extend_behavior_duration_indefinitely(i);
    }

    fn extend_behavior_duration_indefinitely(&mut self, i: usize) {
        let p = &mut self.ponies[i];
        let cur = p.current_time - p.behavior_start_time;
        if p.behavior_desired_duration < cur {
            p.behavior_desired_duration = cur;
        }
    }

    fn send_to_custom_destination(&mut self, i: usize, custom: Option<V2>, at_custom: &mut Option<bool>) {
        if self.ponies[i].destination.is_none() {
            if let Some(dest) = custom {
                let mut now_at = V2::dist_sq(self.ponies[i].location, dest) < EPSILON;
                match (now_at, *at_custom) {
                    (true, None) | (true, Some(false)) => {
                        self.end_interaction(i, true, false);
                        let c = self.get_candidate_behavior(i, Some(&|b: &Behavior| b.speed_px_per_sec() == 0.0));
                        self.set_behavior_internal(i, c, false);
                    }
                    (false, None) | (false, Some(true)) => {
                        self.end_interaction(i, true, false);
                        if self.ponies[i].has_moving || self.ponies[i].speed_override.is_some() {
                            let c = self.get_candidate_behavior(i, Some(&|b: &Behavior| b.speed_px_per_sec() > 0.0));
                            self.set_behavior_internal(i, c, false);
                        } else {
                            // Нет подвижных поведений: телепортируемся.
                            self.ponies[i].location = dest;
                            now_at = true;
                        }
                    }
                    _ => {}
                }
                *at_custom = Some(now_at);
                self.ponies[i].destination = Some(dest);
                self.extend_behavior_duration_indefinitely(i);
            } else {
                *at_custom = None;
            }
        }
    }

    fn get_in_region_destination(&mut self, i: usize) -> Option<V2> {
        let scale = self.ctx.scale_factor;
        let ctx_region = self.ctx.region.to_f();
        let excl = self.ctx.exclusion_region().to_f();
        let mut cur = self.ponies[i].region_f(scale);
        let mut dest = self.ponies[i].location;
        let loc = self.ponies[i].location;

        if !ctx_region.contains_rect(&cur) {
            let left = ctx_region.left() - cur.left();
            let right = cur.right() - ctx_region.right();
            let top = ctx_region.top() - cur.top();
            let bottom = cur.bottom() - ctx_region.bottom();
            if left > 0.0 {
                dest.x += left;
            } else if right > 0.0 {
                dest.x -= right;
            }
            if top > 0.0 {
                dest.y += top;
            } else if bottom > 0.0 {
                dest.y -= bottom;
            }
        }

        for excl in self.ctx.blocked_regions().into_iter().map(|r| r.to_f()) {
        if !excl.size_is_zero() && cur.intersects(&excl) {
            let change = V2::new((dest.x - loc.x).ceil(), (dest.y - loc.y).ceil());
            cur.x += change.x;
            cur.y += change.y;
            let left_d = cur.right() - excl.left();
            let right_d = excl.right() - cur.left();
            let top_d = cur.bottom() - excl.top();
            let bottom_d = excl.bottom() - cur.top();
            let left_has = excl.left() - ctx_region.left() >= cur.w;
            let right_has = ctx_region.right() - excl.right() >= cur.w;
            let top_has = excl.top() - ctx_region.top() >= cur.h;
            let bottom_has = ctx_region.bottom() - excl.bottom() >= cur.h;
            let mut min_d = f32::MAX;
            if left_has {
                min_d = left_d;
            }
            if right_has && right_d < min_d {
                min_d = right_d;
            }
            if top_has && top_d < min_d {
                min_d = top_d;
            }
            if bottom_has && bottom_d < min_d {
                min_d = bottom_d;
            }
            if left_d == min_d && left_has {
                dest.x -= left_d;
            } else if right_d == min_d && right_has {
                dest.x += right_d;
            } else if top_d == min_d && top_has {
                dest.y -= top_d;
            } else if bottom_d == min_d && bottom_has {
                dest.y += bottom_d;
            }
            cur = self.ponies[i].region_f(scale);
            cur.x += dest.x - loc.x;
            cur.y += dest.y - loc.y;
        }
        }
        if V2::dist_sq(dest, loc) < EPSILON { None } else { Some(dest) }
    }

    fn handle_follow_target_override(&mut self, i: usize) {
        if let Some(t) = self.ponies[i].follow_target_override {
            if let Some(ti) = self.idx(t) {
                if !self.ponies[ti].expired {
                    self.ponies[i].follow_target = Some(t);
                }
            }
        }
    }

    // ------------------------------------------------------------ speech

    pub fn speak(&mut self, id: PonyId, suggested: Option<usize>) {
        if let Some(i) = self.idx(id) {
            self.speak_internal(i, suggested);
        }
    }

    /// Произвольная реплика (например, от нейросети): показывается как речь пони.
    pub fn say_custom(&mut self, id: PonyId, text: &str) {
        if !self.ctx.speech_enabled {
            return;
        }
        if let Some(i) = self.idx(id) {
            let p = &mut self.ponies[i];
            p.speech_start = p.current_time;
            p.current_speech_text = Some(format!("{}: \"{}\"", p.base.display_name, text));
            p.speech_duration = 500.0 + p.current_speech_text.as_ref().unwrap().chars().count() as f64 / 15.0 * 1000.0;
            p.current_speech_sound = None;
        }
    }

    fn speak_internal(&mut self, i: usize, suggested: Option<usize>) {
        if !self.ctx.speech_enabled {
            return;
        }
        let base = self.ponies[i].base.clone();
        let idx = match suggested {
            Some(s) => s,
            None => {
                if base.speeches.is_empty() {
                    return;
                }
                let p = &self.ponies[i];
                if p.current_interaction.is_some()
                    || p.follow_target.is_some()
                    || p.current_time - (p.speech_start + p.speech_duration) < RANDOM_SPEECH_DELAY_MS
                {
                    return;
                }
                let group = p.current_behavior_group();
                let candidates: Vec<usize> = base
                    .speeches
                    .iter()
                    .enumerate()
                    .filter(|(_, s)| !s.skip && (s.group == ANY_GROUP || s.group == group))
                    .map(|(k, _)| k)
                    .collect();
                if candidates.is_empty() {
                    return;
                }
                candidates[self.rng.usize(0..candidates.len())]
            }
        };
        let s = &base.speeches[idx];
        let p = &mut self.ponies[i];
        p.speech_start = p.current_time;
        let text = format!("{}: \"{}\"", base.display_name, s.text);
        p.speech_duration = 500.0 + text.chars().count() as f64 / 15.0 * 1000.0;
        p.current_speech_text = Some(text);
        p.current_speech_sound = s.sound_file.clone();
    }

    // ------------------------------------------------------------ behaviors

    /// SetBehavior (внешний вызов).
    pub fn set_behavior(&mut self, id: PonyId, suggested: Option<usize>, speak: bool) {
        if let Some(i) = self.idx(id) {
            self.end_interaction(i, true, false);
            self.set_behavior_internal(i, suggested, speak);
            let tele = self.ctx.teleportation_enabled;
            self.update_state(i, tele, true);
        }
    }

    fn set_behavior_internal(&mut self, i: usize, suggested: Option<usize>, speak: bool) {
        {
            let p = &mut self.ponies[i];
            p.follow_target = None;
            p.destination = None;
            p.movement_without_destination_needed = true;
            p.behavior_changed_during_step = true;
        }
        let chosen = match suggested {
            Some(s) => s,
            None => self
                .get_candidate_behavior(i, None)
                .expect("pony has no behaviors"),
        };
        let base = self.ponies[i].base.clone();
        let b = &base.behaviors[chosen];
        let dur = {
            let special = {
                let p = &self.ponies[i];
                p.in_mouseover || p.in_drag || p.in_sleep
            };
            if special {
                0.0
            } else {
                (b.min_duration + self.rng.f64() * (b.max_duration - b.min_duration)) * 1000.0
            }
        };
        {
            let p = &mut self.ponies[i];
            p.current_behavior = chosen;
            p.behavior_start_time = p.current_time;
            p.behavior_desired_duration = dur;
        }
        self.set_follow_target(i);

        let to_expire: Vec<EffectId> = std::mem::take(&mut self.ponies[i].effects_to_manually_expire);
        for eid in to_expire {
            self.expire_effect(eid);
        }
        self.ponies[i].effect_bases_to_repeat.clear();

        if speak {
            if let Some(s) = base.speech_by_name(&b.start_line) {
                self.speak_internal(i, Some(s));
            }
        }
    }

    fn behavior_allowed_by_group(&self, i: usize, b: &Behavior) -> bool {
        b.group == ANY_GROUP || b.group == self.ponies[i].current_behavior_group()
    }

    fn target_reachable(&self, i: usize, b: &Behavior) -> bool {
        if b.target_mode() != TargetMode::Pony {
            return true;
        }
        self.ponies.iter().enumerate().any(|(k, p)| {
            k != i && !p.expired && ci_eq(&p.base.directory, &b.follow_target)
        })
    }

    fn get_candidate_behavior(&mut self, i: usize, filter: Option<&dyn Fn(&Behavior) -> bool>) -> Option<usize> {
        let base = self.ponies[i].base.clone();
        let source: Vec<usize> = (0..base.behaviors.len())
            .filter(|k| filter.map(|f| f(&base.behaviors[*k])).unwrap_or(true))
            .collect();
        let mut candidates: Vec<usize> = source
            .iter()
            .copied()
            .filter(|k| {
                let b = &base.behaviors[*k];
                !b.skip && self.behavior_allowed_by_group(i, b) && self.target_reachable(i, b)
            })
            .collect();
        if candidates.is_empty() {
            candidates = source
                .iter()
                .copied()
                .filter(|k| {
                    let b = &base.behaviors[*k];
                    !b.skip && self.behavior_allowed_by_group(i, b)
                })
                .collect();
        }
        if candidates.is_empty() {
            candidates = source.iter().copied().filter(|k| !base.behaviors[*k].skip).collect();
        }
        if candidates.is_empty() {
            candidates = source.clone();
        }
        if candidates.is_empty() {
            candidates = (0..base.behaviors.len()).collect();
        }
        if candidates.is_empty() {
            return None;
        }
        if candidates.len() == 1 {
            return Some(candidates[0]);
        }
        let total: f64 = candidates.iter().map(|k| base.behaviors[*k].chance).sum();
        let random_chance = self.rng.f64() * total;
        let mut current = 0.0;
        let mut choice = candidates[0];
        for k in candidates {
            choice = k;
            current += base.behaviors[k].chance;
            if current >= random_chance {
                break;
            }
        }
        Some(choice)
    }

    fn set_follow_target(&mut self, i: usize) {
        let base = self.ponies[i].base.clone();
        let beh = &base.behaviors[self.ponies[i].current_behavior];
        if self.ponies[i].follow_target.is_none() && !beh.follow_target.is_empty() {
            if let Some(ci) = self.ponies[i].current_interaction {
                if let Some(inter) = self.interactions.get(&ci) {
                    let me = self.ponies[i].id;
                    let initiator = inter.initiator;
                    let involved = inter.involved_targets.clone();
                    if initiator == Some(me) {
                        self.ponies[i].follow_target = self.random_follow_target(i, &involved, &beh.follow_target);
                    } else if let Some(init) = initiator {
                        let init_dir = self.pony(init).map(|p| p.base.directory.clone());
                        if init_dir.as_deref() == Some(beh.follow_target.as_str()) {
                            self.ponies[i].follow_target = Some(init);
                        } else {
                            let others: Vec<PonyId> = involved.into_iter().filter(|id| *id != me).collect();
                            self.ponies[i].follow_target = self.random_follow_target(i, &others, &beh.follow_target);
                        }
                    }
                }
            }
            if self.ponies[i].follow_target.is_none() {
                let me = self.ponies[i].id;
                let others: Vec<PonyId> = self.ponies.iter().filter(|p| p.id != me).map(|p| p.id).collect();
                self.ponies[i].follow_target = self.random_follow_target(i, &others, &beh.follow_target);
            }
        }
    }

    fn random_follow_target(&mut self, _i: usize, candidates: &[PonyId], wanted_dir: &str) -> Option<PonyId> {
        let suitable: Vec<PonyId> = candidates
            .iter()
            .copied()
            .filter(|id| self.pony(*id).map(|p| !p.expired && ci_eq(&p.base.directory, wanted_dir)).unwrap_or(false))
            .collect();
        if suitable.is_empty() {
            None
        } else {
            Some(suitable[self.rng.usize(0..suitable.len())])
        }
    }

    // ------------------------------------------------------------ state update

    fn update_state(&mut self, i: usize, teleport_when_out_of_bounds: bool, start_effects_now: bool) {
        if let Some(t) = self.ponies[i].follow_target {
            if self.pony(t).map(|p| p.expired).unwrap_or(true) {
                self.ponies[i].follow_target = None;
            }
        }
        self.update_natural_return_to_zone(i);
        self.ensure_within_bounds(i, teleport_when_out_of_bounds);
        self.update_destination(i);
        let old_movement = self.ponies[i].movement;
        self.update_movement(i);
        if self.ponies[i].movement != old_movement {
            self.ponies[i].rebounding_into_containment = false;
        }
        self.set_visual_override_behavior(i);
        self.update_location(i);
        if start_effects_now {
            self.start_effects(i);
        }
        self.repeat_effects(i);
    }

    fn update_natural_return_to_zone(&mut self, i: usize) {
        if !self.ponies[i].behavior_changed_during_step {
            return;
        }
        if self.ponies[i].allowing_natural_return {
            self.ponies[i].allowing_natural_return = false;
        } else {
            self.update_region(i);
            let scale = self.ctx.scale_factor;
            let cur = self.ponies[i].region_f(scale);
            let region = self.ctx.region.to_f();
            let inside = region.contains_rect(&cur);
            let on_edge = !inside || self.ctx.blocked_regions().iter().any(|b| cur.intersects(&b.to_f()));
            if on_edge {
                self.ponies[i].allowing_natural_return = true;
            }
        }
    }

    fn ensure_within_bounds(&mut self, i: usize, teleport: bool) {
        {
            let p = &self.ponies[i];
            if p.is_busy() || p.rebounding_into_containment || p.allowing_natural_return || p.follow_target.is_some() {
                return;
            }
        }
        let in_region_dest = self.get_in_region_destination(i);
        if teleport {
            if let Some(d) = in_region_dest {
                self.ponies[i].location = d;
                self.ponies[i].last_step_in_bounds = true;
            }
            self.ponies[i].in_region = None;
        } else {
            let mut in_region = self.ponies[i].in_region;
            self.send_to_custom_destination(i, in_region_dest, &mut in_region);
            self.ponies[i].in_region = in_region;
        }
    }

    fn update_destination(&mut self, i: usize) {
        if self.ponies[i].destination.is_some() {
            return;
        }
        let base = self.ponies[i].base.clone();
        let beh = &base.behaviors[self.ponies[i].current_behavior];
        if self.ponies[i].follow_target_override.is_some() {
            if let Some(t) = self.ponies[i].follow_target {
                if let Some(tp) = self.pony(t) {
                    self.ponies[i].destination = Some(tp.location);
                    return;
                }
            }
        }
        let mut offset = V2::new(beh.target_vector.0 as f32, beh.target_vector.1 as f32);
        if let Some(t) = self.ponies[i].follow_target {
            if let Some(tp) = self.pony(t) {
                if !tp.location.x.is_nan() {
                    if beh.follow_offset == FollowOffsetType::Mirror && !tp.facing_right {
                        offset.x = -offset.x;
                    }
                    self.ponies[i].destination = Some(tp.location + offset);
                    return;
                }
            }
        }
        if beh.target_mode() == TargetMode::Point {
            let rel = offset * 0.01;
            let r = self.ctx.region;
            self.ponies[i].destination =
                Some(V2::new(r.x as f32 + rel.x * r.w as f32, r.y as f32 + rel.y * r.h as f32));
        }
    }

    fn speed_in_pixels_per_step(&self, i: usize) -> f64 {
        let p = &self.ponies[i];
        p.speed_override.unwrap_or(p.base.behaviors[p.current_behavior].speed_px_per_sec()) / STEP_RATE
    }

    fn update_movement(&mut self, i: usize) {
        let mut normalize = false;
        let mut scale_up = false;
        let (special, has_override, dest) = {
            let p = &self.ponies[i];
            (p.in_mouseover || p.in_drag || p.in_sleep || p.hold.is_some(), p.movement_override, p.destination)
        };
        if special {
            self.ponies[i].movement = V2::ZERO;
        } else if let Some(mv) = has_override {
            self.ponies[i].movement = mv;
            self.ponies[i].movement_override = None;
            normalize = true;
            scale_up = true;
            self.ponies[i].movement_without_destination_needed = false;
        } else if let Some(d) = dest {
            self.ponies[i].movement = d - self.ponies[i].location;
            normalize = true;
        } else if self.ponies[i].movement_without_destination_needed {
            let preserve = !self.ponies[i].behavior_changed_during_step;
            self.set_movement_without_destination(i, preserve);
            self.ponies[i].movement_without_destination_needed = false;
        }
        if normalize {
            let magnitude = self.ponies[i].movement.length();
            if magnitude > EPSILON {
                self.ponies[i].facing_right = self.ponies[i].movement.x > 0.0;
                let speed = self.speed_in_pixels_per_step(i) as f32;
                if magnitude > speed || scale_up {
                    self.ponies[i].movement = self.ponies[i].movement / magnitude * speed;
                }
            }
        }
    }

    fn set_movement_without_destination(&mut self, i: usize, preserve_current_directions: bool) {
        let mv = self.ponies[i].base.behaviors[self.ponies[i].current_behavior].allowed_movement & moves::ALL;
        let speed = self.speed_in_pixels_per_step(i);
        if mv == moves::NONE || speed == 0.0 {
            self.ponies[i].movement = V2::ZERO;
            return;
        }
        let mut list: Vec<u8> = Vec::new();
        if mv & moves::HORIZONTAL_ONLY != 0 {
            list.push(moves::HORIZONTAL_ONLY);
        }
        if mv & moves::VERTICAL_ONLY != 0 {
            list.push(moves::VERTICAL_ONLY);
        }
        if mv & moves::DIAGONAL_ONLY != 0 {
            list.push(moves::DIAGONAL_ONLY);
        }
        let selected = list[self.rng.usize(0..list.len())];
        let cur = self.ponies[i].movement;
        let was_right = cur.x > 0.0 || (cur.x == 0.0 && self.rng.f64() < 0.5);
        let was_down = cur.y > 0.0 || (cur.y == 0.0 && self.rng.f64() < 0.5);
        let mut m = match selected {
            moves::HORIZONTAL_ONLY => V2::new(speed as f32, 0.0),
            moves::VERTICAL_ONLY => V2::new(0.0, speed as f32),
            _ => {
                let angle_deg = match mv {
                    moves::DIAGONAL_VERTICAL => self.rng.f64() * 30.0 + 15.0,
                    moves::DIAGONAL_HORIZONTAL => self.rng.f64() * 30.0 + 105.0,
                    _ => self.rng.f64() * 60.0 + 15.0,
                };
                let a = angle_deg.to_radians();
                V2::new((speed * a.sin()) as f32, (speed * a.cos()) as f32)
            }
        };
        if preserve_current_directions {
            if was_right ^ (m.x > 0.0) {
                m.x = -m.x;
            }
            if was_down ^ (m.y > 0.0) {
                m.y = -m.y;
            }
            self.ponies[i].movement = m;
        } else if self.ponies[i].allowing_natural_return {
            if let Some(d) = self.get_in_region_destination(i) {
                if (d.x > self.ponies[i].location.x) ^ (m.x > 0.0) {
                    m.x = -m.x;
                }
                if (d.y > self.ponies[i].location.y) ^ (m.y > 0.0) {
                    m.y = -m.y;
                }
            }
            self.ponies[i].movement = m;
            self.ponies[i].facing_right = m.x > 0.0;
        } else {
            let right = self.rng.f64() < 0.5;
            self.ponies[i].facing_right = right;
            if !right {
                m.x = -m.x;
            }
            if self.rng.f64() < 0.5 {
                m.y = -m.y;
            }
            self.ponies[i].movement = m;
        }
    }

    fn set_visual_override_behavior(&mut self, i: usize) {
        let base = self.ponies[i].base.clone();
        let beh = &base.behaviors[self.ponies[i].current_behavior];
        if self.ponies[i].follow_target.is_some() || beh.target_mode() == TargetMode::Point {
            let previous = self.ponies[i].visual_override;
            let speed = self.ponies[i].movement.length();
            if let Some(v) = self.ponies[i].visual_override {
                if (base.behaviors[v].speed_px_per_sec() == 0.0) ^ (speed == 0.0) {
                    self.ponies[i].visual_override = None;
                }
            }
            if !beh.auto_select_images_on_follow {
                self.ponies[i].visual_override = if speed == 0.0 {
                    base.behavior_by_name(&beh.follow_stopped)
                } else {
                    base.behavior_by_name(&beh.follow_moving)
                };
            }
            if self.ponies[i].visual_override.is_none() {
                if speed == 0.0 {
                    if !self.ponies[i].has_stationary {
                        self.ponies[i].visual_override = previous;
                    }
                    if self.ponies[i].visual_override.is_none() {
                        self.ponies[i].visual_override =
                            self.get_candidate_behavior(i, Some(&|b: &Behavior| b.speed_px_per_sec() == 0.0));
                    }
                } else {
                    if !self.ponies[i].has_moving {
                        self.ponies[i].visual_override = previous;
                    }
                    if self.ponies[i].visual_override.is_none() {
                        self.ponies[i].visual_override =
                            self.get_candidate_behavior(i, Some(&|b: &Behavior| b.speed_px_per_sec() > 0.0));
                    }
                }
            }
        } else {
            self.ponies[i].visual_override = None;
        }
    }

    fn update_location(&mut self, i: usize) {
        if self.ponies[i].in_drag {
            let cursor = V2::new(self.ctx.cursor.0 as f32, self.ctx.cursor.1 as f32);
            self.ponies[i].location = self.ponies[i].carry.unwrap_or(cursor);
        } else {
            let mv = self.ponies[i].movement;
            self.ponies[i].location += mv;
            self.update_region(i);
            let no_dest = self.ponies[i].destination.is_none();
            if no_dest && (self.ponies[i].last_step_in_bounds || !self.teleport_to_boundary_if_outside(i)) {
                self.rebound_off_regions(i);
            }
        }
        let scale = self.ctx.scale_factor;
        let cur = self.ponies[i].region_f(scale);
        let region = self.ctx.region.to_f();
        self.ponies[i].last_step_in_bounds =
            region.contains_rect(&cur) && !self.ctx.blocked_regions().iter().any(|b| cur.intersects(&b.to_f()));
        if self.ponies[i].last_step_in_bounds || !cur.intersects(&region) {
            self.ponies[i].rebounding_into_containment = false;
            self.ponies[i].allowing_natural_return = false;
        }
        self.update_region(i);
    }

    fn update_region(&mut self, i: usize) {
        let scale = self.ctx.scale_factor;
        let r = self.ponies[i].region_f(scale);
        let (x, y) = V2::new(r.x, r.y).round();
        self.ponies[i].region = RectI::new(x, y, r.w as i32, r.h as i32);
    }

    fn teleport_to_boundary_if_outside(&mut self, i: usize) -> bool {
        let scale = self.ctx.scale_factor;
        let cr = self.ctx.region.to_f();
        let cur = self.ponies[i].region_f(scale);
        let initial = self.ponies[i].location;
        let p = &mut self.ponies[i];
        if cr.top() > cur.bottom() {
            p.location.y += cr.top() - cur.bottom();
            if p.movement.y < 0.0 {
                p.movement.y = -p.movement.y;
            }
        } else if cur.top() > cr.bottom() {
            p.location.y -= cur.top() - cr.bottom();
            if p.movement.y > 0.0 {
                p.movement.y = -p.movement.y;
            }
        }
        if cr.left() > cur.right() {
            p.location.x += cr.left() - cur.right();
            if p.movement.x < 0.0 {
                p.movement.x = -p.movement.x;
            }
        } else if cur.left() > cr.right() {
            p.location.x -= cur.left() - cr.right();
            if p.movement.x > 0.0 {
                p.movement.x = -p.movement.x;
            }
        }
        if p.movement.x != 0.0 {
            p.facing_right = p.movement.x > 0.0;
        }
        p.location != initial
    }

    fn rebound_off_regions(&mut self, i: usize) {
        if self.ponies[i].rebound_cooldown_end <= self.ponies[i].current_time {
            let mut rebounded = false;
            if self.ctx.stay_in_containing_window {
                if let Some(win) = self.window_region_at_center(i) {
                    let r = self.ponies[i].region;
                    if win.x <= r.x && win.y <= r.y && win.right() >= r.right() && win.bottom() >= r.bottom() {
                        rebounded |= self.rebound_into_containment_region(i, win, true);
                    }
                }
            }
            if self.ctx.window_avoidance_enabled {
                for w in self.nearby_window_regions(i) {
                    rebounded |= self.rebound_out_of_exclusion_region(i, w, false);
                }
            }
            if self.ctx.pony_avoidance_enabled && self.ponies.len() + self.effects.len() <= 25 {
                let me = self.ponies[i].id;
                let others: Vec<RectI> = self.ponies.iter().filter(|p| p.id != me).map(|p| p.region).collect();
                for r in others {
                    rebounded |= self.rebound_out_of_exclusion_region(i, r, true);
                }
            }
            if self.ctx.cursor_avoidance_enabled {
                rebounded |= self.rebound_to_avoid_cursor(i);
            }
            if rebounded {
                self.ponies[i].rebound_cooldown_end = self.ponies[i].current_time + 1000.0;
            }
        }
        if !self.ponies[i].allowing_natural_return {
            if self.ponies[i].last_step_in_bounds {
                for ex in self.ctx.blocked_regions() {
                    self.rebound_out_of_exclusion_region(i, ex, true);
                }
            }
            let cr = self.ctx.region;
            let check_v = !self.ponies[i].rebounding_into_containment;
            let rebounding = self.rebound_into_containment_region(i, cr, check_v);
            self.ponies[i].rebounding_into_containment = self.ponies[i].rebounding_into_containment || rebounding;
        }
    }

    fn rebound_into_containment_region(&mut self, i: usize, region: RectI, check_vertical_boundaries: bool) -> bool {
        if !self.ponies[i].last_step_in_bounds {
            return false;
        }
        let scale = self.ctx.scale_factor;
        let cur = self.ponies[i].region_f(scale);
        let initial = self.ponies[i].location;
        let p = &mut self.ponies[i];
        if region.top() as f32 > cur.top() {
            p.location.y += 2.0 * (region.top() as f32 - cur.top());
            if p.movement.y < 0.0 {
                p.movement.y = -p.movement.y;
            }
        } else if cur.bottom() > region.bottom() as f32 {
            p.location.y -= 2.0 * (cur.bottom() - region.bottom() as f32);
            if p.movement.y > 0.0 {
                p.movement.y = -p.movement.y;
            }
        }
        if check_vertical_boundaries {
            if region.left() as f32 > cur.left() {
                p.location.x += 2.0 * (region.left() as f32 - cur.left());
                if p.movement.x < 0.0 {
                    p.movement.x = -p.movement.x;
                }
            } else if cur.right() > region.right() as f32 {
                p.location.x -= 2.0 * (cur.right() - region.right() as f32);
                if p.movement.x > 0.0 {
                    p.movement.x = -p.movement.x;
                }
            }
            if p.movement.x != 0.0 {
                p.facing_right = p.movement.x > 0.0;
            }
        }
        p.location != initial
    }

    fn rebound_out_of_exclusion_region(&mut self, i: usize, excl: RectI, move_away_if_contained: bool) -> bool {
        if excl.w == 0 && excl.h == 0 {
            return false;
        }
        let scale = self.ctx.scale_factor;
        let cur = self.ponies[i].region_f(scale);
        let ex = excl.to_f();
        if !cur.intersects(&ex) {
            return false;
        }
        if !move_away_if_contained && ex.contains_rect(&cur) {
            return false;
        }
        let left = cur.right() - ex.left();
        let right = ex.right() - cur.left();
        let top = cur.bottom() - ex.top();
        let bottom = ex.bottom() - cur.top();
        let min_d = left.min(right).min(top.min(bottom));
        let p = &mut self.ponies[i];
        if left == min_d {
            if p.movement.x > 0.0 {
                p.movement.x = -p.movement.x;
            }
            p.location.x += 2.0 * p.movement.x;
        } else if right == min_d {
            if p.movement.x < 0.0 {
                p.movement.x = -p.movement.x;
            }
            p.location.x += 2.0 * p.movement.x;
        } else if top == min_d {
            if p.movement.y > 0.0 {
                p.movement.y = -p.movement.y;
            }
            p.location.y += 2.0 * p.movement.y;
        } else if bottom == min_d {
            if p.movement.y < 0.0 {
                p.movement.y = -p.movement.y;
            }
            p.location.y += 2.0 * p.movement.y;
        }
        if p.movement.x != 0.0 {
            p.facing_right = p.movement.x > 0.0;
        }
        true
    }

    fn rebound_to_avoid_cursor(&mut self, i: usize) -> bool {
        if self.ponies[i].in_mouseover {
            return false;
        }
        let cursor = V2::new(self.ctx.cursor.0 as f32, self.ctx.cursor.1 as f32);
        let radius = self.ctx.cursor_avoidance_radius;
        let p = &mut self.ponies[i];
        let is_over = V2::dist_sq(p.location, cursor) < radius * radius;
        if is_over {
            let initial = p.movement;
            if p.location.x < cursor.x {
                if p.movement.x > 0.0 {
                    p.movement.x = -p.movement.x;
                }
            } else if p.movement.x < 0.0 {
                p.movement.x = -p.movement.x;
            }
            if p.location.y < cursor.y {
                if p.movement.y > 0.0 {
                    p.movement.y = -p.movement.y;
                }
            } else if p.movement.y < 0.0 {
                p.movement.y = -p.movement.y;
            }
            if initial != p.movement {
                p.location += p.movement;
                if p.movement.x != 0.0 {
                    p.facing_right = p.movement.x > 0.0;
                }
                return true;
            }
        }
        false
    }

    fn window_region_at_center(&self, i: usize) -> Option<RectI> {
        let f = self.ctx.window_at_point.as_ref()?;
        let scale = self.ctx.scale_factor;
        let c = self.ponies[i].region_f(scale).center();
        let (x, y) = c.round();
        f(x, y)
    }

    fn nearby_window_regions(&self, i: usize) -> Vec<RectI> {
        let Some(f) = self.ctx.window_at_point.as_ref() else { return Vec::new() };
        let r = self.ponies[i].region;
        [(r.left(), r.top()), (r.right(), r.top()), (r.left(), r.bottom()), (r.right(), r.bottom())]
            .iter()
            .filter_map(|(x, y)| f(*x, *y))
            .collect()
    }

    // ------------------------------------------------------------ effects

    fn start_effects(&mut self, i: usize) {
        let base = self.ponies[i].base.clone();
        let cur = self.ponies[i].current_behavior;
        let name = base.behaviors[cur].name.clone();
        let (lu, ct) = (self.ponies[i].last_update_time, self.ponies[i].current_time);
        for (k, e) in base.effects.iter().enumerate() {
            if !ci_eq(&e.behavior_name, &name) {
                continue;
            }
            self.start_new_effect(i, k, lu, ct, V2::ZERO);
            if e.repeat_delay > 0.0 {
                self.ponies[i].effect_bases_to_repeat.push(EffectRepeat {
                    base_index: k,
                    last_external_start: lu,
                    last_internal_start: ct,
                });
            }
        }
    }

    fn start_new_effect(&mut self, i: usize, base_index: usize, external_start: f64, internal_start: f64, offset: V2) {
        if !self.ctx.effects_enabled {
            return;
        }
        let base = self.ponies[i].base.clone();
        let eb = &base.effects[base_index];
        let facing_left = !self.ponies[i].facing_right;
        let placement = resolve_direction(&mut self.rng, if facing_left { eb.placement_left } else { eb.placement_right });
        let centering = resolve_direction(&mut self.rng, if facing_left { eb.centering_left } else { eb.centering_right });
        let id = self.next_id;
        self.next_id += 1;
        let mut eff = Effect {
            id,
            base: base.clone(),
            base_index,
            owner: Some(self.ponies[i].id),
            internal_start_time: internal_start,
            current_time: internal_start,
            last_update_time: external_start,
            desired_duration: None,
            expired: false,
            top_left: (0, 0),
            facing_left,
            being_dragged: false,
            placement,
            centering,
            initial_offset: offset,
        };
        // Start(): позиция относительно родителя
        let scale = self.ctx.scale_factor;
        let rf = self.ponies[i].region_f(scale);
        eff.top_left = effect_location(
            &mut self.rng,
            eff.current_image_size(),
            eff.placement,
            V2::new(rf.x, rf.y) + eff.initial_offset,
            V2::new(self.ponies[i].region.w as f32, self.ponies[i].region.h as f32),
            eff.centering,
            scale,
        );
        if eb.duration == 0.0 {
            self.ponies[i].effects_to_manually_expire.push(id);
        } else {
            eff.desired_duration = Some(eb.duration * 1000.0);
        }
        self.ponies[i].active_effects.push(id);
        self.effects.push(eff);
    }

    fn repeat_effects(&mut self, i: usize) {
        let n = self.ponies[i].effect_bases_to_repeat.len();
        for k in 0..n {
            let (bi, mut last_ext, mut last_int) = {
                let r = &self.ponies[i].effect_bases_to_repeat[k];
                (r.base_index, r.last_external_start, r.last_internal_start)
            };
            let repeat_ms = self.ponies[i].base.effects[bi].repeat_delay * 1000.0;
            if repeat_ms <= 0.0 {
                continue;
            }
            let mut internal_start = last_int + repeat_ms;
            let now = self.ponies[i].current_time;
            let mut guard = 0;
            while now - internal_start >= 0.0 && guard < 1000 {
                guard += 1;
                let offset = -self.ponies[i].movement * ((now - internal_start) / STEP_SIZE) as f32;
                last_ext += repeat_ms / self.ctx.time_factor;
                self.start_new_effect(i, bi, last_ext, internal_start, offset);
                last_int = internal_start;
                internal_start += repeat_ms;
            }
            let r = &mut self.ponies[i].effect_bases_to_repeat[k];
            r.last_external_start = last_ext;
            r.last_internal_start = last_int;
        }
    }

    fn update_effect(&mut self, e: usize, update_time: f64) {
        if self.effects[e].expired {
            return;
        }
        let scaled = STEP_SIZE / self.ctx.time_factor;
        while update_time - self.effects[e].last_update_time >= scaled {
            self.effects[e].last_update_time += scaled;
            self.effects[e].current_time += STEP_SIZE;
        }
        let scale = self.ctx.scale_factor;
        if self.effects[e].effect_base().follow {
            if let Some(owner) = self.effects[e].owner {
                if let Some(pi) = self.idx(owner) {
                    let rf = self.ponies[pi].region_f(scale);
                    let size = V2::new(self.ponies[pi].region.w as f32, self.ponies[pi].region.h as f32);
                    let (size_img, placement, centering) = {
                        let ef = &self.effects[e];
                        (ef.current_image_size(), ef.placement, ef.centering)
                    };
                    self.effects[e].top_left =
                        effect_location(&mut self.rng, size_img, placement, V2::new(rf.x, rf.y), size, centering, scale);
                }
            }
        } else if self.effects[e].being_dragged {
            let s = self.effects[e].current_image_size();
            self.effects[e].top_left = (
                (self.ctx.cursor.0 as f32 - s.x / 2.0) as i32,
                (self.ctx.cursor.1 as f32 - s.y / 2.0) as i32,
            );
        }
        if let Some(d) = self.effects[e].desired_duration {
            if self.effects[e].image_time_index() > d {
                self.effects[e].expired = true;
            }
        }
    }

    fn expire_effect(&mut self, id: EffectId) {
        if let Some(e) = self.effects.iter_mut().find(|e| e.id == id) {
            e.expired = true;
        }
    }

    fn expire_pony(&mut self, i: usize) {
        if self.ponies[i].expired {
            return;
        }
        self.ponies[i].expired = true;
        let active = std::mem::take(&mut self.ponies[i].active_effects);
        for e in active {
            self.expire_effect(e);
        }
    }

    // ------------------------------------------------------------ interactions

    pub fn initialize_interactions(&mut self) {
        // Сохраняем только текущие (идущие) взаимодействия.
        let keep: HashSet<u64> = self.ponies.iter().filter_map(|p| p.current_interaction).collect();
        self.interactions.retain(|k, _| keep.contains(k));
        for p in &mut self.ponies {
            p.interactions.clear();
        }
        for i in 0..self.ponies.len() {
            let base = self.ponies[i].base.clone();
            let me = self.ponies[i].id;
            for ib in &base.interactions {
                let mut targets: Vec<PonyId> = Vec::new();
                let mut missing: HashSet<String> = ib.target_names.iter().map(|s| s.to_lowercase()).collect();
                for cand in &self.ponies {
                    if cand.id == me {
                        continue;
                    }
                    let is_target = ib.target_names.iter().any(|t| ci_eq(t, &cand.base.directory));
                    let has_beh = cand
                        .base
                        .behaviors
                        .iter()
                        .any(|b| ib.behavior_names.iter().any(|n| ci_eq(n, &b.name)));
                    if is_target && has_beh {
                        missing.remove(&cand.base.directory.to_lowercase());
                        targets.push(cand.id);
                    }
                }
                if targets.is_empty() || (ib.activation == TargetActivation::All && !missing.is_empty()) {
                    continue;
                }
                let id = self.next_interaction_id;
                self.next_interaction_id += 1;
                self.interactions.insert(
                    id,
                    InteractionInst {
                        base: ib.clone(),
                        targets,
                        trigger: None,
                        initiator: None,
                        involved_targets: Vec::new(),
                    },
                );
                self.ponies[i].interactions.push(id);
            }
        }
    }

    fn start_interaction_at_random(&mut self, i: usize) {
        if !self.ctx.interactions_enabled || self.ponies[i].is_busy() {
            return;
        }
        if self.ponies[i].current_time < self.ponies[i].interaction_cooldown_end {
            return;
        }
        let ids = self.ponies[i].interactions.clone();
        for iid in ids {
            let chance = match self.interactions.get(&iid) {
                Some(x) => x.base.chance,
                None => continue,
            };
            if self.rng.f64() > chance {
                continue;
            }
            let (trigger, available) = self.get_interaction_trigger_if_conditions_met(i, iid);
            let Some(trigger) = trigger else { continue };
            if let Some(x) = self.interactions.get_mut(&iid) {
                x.trigger = Some(trigger);
            }
            self.start_interaction(i, iid, available);
            return;
        }
    }

    fn has_allowed_behavior(&self, i: usize, names: &[String]) -> bool {
        self.ponies[i]
            .base
            .behaviors
            .iter()
            .any(|b| self.behavior_allowed_by_group(i, b) && names.iter().any(|n| ci_eq(n, &b.name)))
    }

    fn in_range(&self, i: usize, iid: u64, target: usize) -> bool {
        let prox = self.interactions[&iid].base.proximity as f32;
        V2::dist_sq(self.ponies[i].location, self.ponies[target].location) <= prox * prox
    }

    fn get_interaction_trigger_if_conditions_met(&self, i: usize, iid: u64) -> (Option<PonyId>, Vec<PonyId>) {
        let inter = &self.interactions[&iid];
        let names = inter.base.behavior_names.clone();
        if !self.has_allowed_behavior(i, &names) {
            return (None, Vec::new());
        }
        match inter.base.activation {
            TargetActivation::All => {
                let mut trigger = None;
                for tid in &inter.targets {
                    let Some(ti) = self.idx(*tid) else { return (None, Vec::new()) };
                    if self.ponies[ti].is_busy() || !self.has_allowed_behavior(ti, &names) {
                        return (None, Vec::new());
                    }
                    if trigger.is_none() && self.in_range(i, iid, ti) {
                        trigger = Some(*tid);
                    }
                }
                (trigger, Vec::new())
            }
            TargetActivation::Any => {
                let mut trigger = None;
                let mut avail = Vec::new();
                for tid in &inter.targets {
                    let Some(ti) = self.idx(*tid) else { continue };
                    if self.ponies[ti].is_busy() || !self.has_allowed_behavior(ti, &names) {
                        continue;
                    }
                    if trigger.is_none() && self.in_range(i, iid, ti) {
                        trigger = Some(*tid);
                    }
                    avail.push(*tid);
                }
                if trigger.is_none() {
                    avail.clear();
                }
                (trigger, avail)
            }
            TargetActivation::One => {
                for tid in &inter.targets {
                    let Some(ti) = self.idx(*tid) else { continue };
                    if self.ponies[ti].is_busy() || !self.has_allowed_behavior(ti, &names) {
                        continue;
                    }
                    if self.in_range(i, iid, ti) {
                        return (Some(*tid), Vec::new());
                    }
                }
                (None, Vec::new())
            }
        }
    }

    fn random_allowed_behavior(&mut self, i: usize, names: &[String]) -> Option<usize> {
        let cands: Vec<usize> = self.ponies[i]
            .base
            .behaviors
            .iter()
            .enumerate()
            .filter(|(_, b)| self.behavior_allowed_by_group(i, b) && names.iter().any(|n| ci_eq(n, &b.name)))
            .map(|(k, _)| k)
            .collect();
        if cands.is_empty() {
            None
        } else {
            Some(cands[self.rng.usize(0..cands.len())])
        }
    }

    fn start_interaction(&mut self, i: usize, iid: u64, available_any: Vec<PonyId>) {
        let me = self.ponies[i].id;
        self.ponies[i].current_interaction = Some(iid);
        let (names, activation, targets, trigger) = {
            let x = self.interactions.get_mut(&iid).unwrap();
            x.initiator = Some(me);
            (x.base.behavior_names.clone(), x.base.activation, x.targets.clone(), x.trigger)
        };
        let b = self.random_allowed_behavior(i, &names);
        self.set_behavior_internal(i, b, true);
        let to_start: Vec<PonyId> = match activation {
            TargetActivation::All => targets,
            TargetActivation::Any => available_any,
            TargetActivation::One => trigger.into_iter().collect(),
        };
        for t in to_start {
            if let Some(ti) = self.idx(t) {
                self.start_interaction_as_target(ti, iid);
            }
        }
    }

    fn start_interaction_as_target(&mut self, i: usize, iid: u64) {
        let me = self.ponies[i].id;
        self.ponies[i].current_interaction = Some(iid);
        let names = {
            let x = self.interactions.get_mut(&iid).unwrap();
            x.involved_targets.push(me);
            x.base.behavior_names.clone()
        };
        let b = self.random_allowed_behavior(i, &names);
        self.set_behavior_internal(i, b, true);
    }

    fn end_interaction(&mut self, i: usize, forced_cancel: bool, reset_behavior_after_cancel: bool) {
        let Some(iid) = self.ponies[i].current_interaction else { return };
        let me = self.ponies[i].id;
        let (initiator, targets, delay) = match self.interactions.get(&iid) {
            Some(x) => (x.initiator, x.targets.clone(), x.base.reactivation_delay * 1000.0),
            None => {
                self.ponies[i].current_interaction = None;
                return;
            }
        };
        if forced_cancel {
            if let Some(init) = initiator {
                if init != me {
                    if let Some(ii) = self.idx(init) {
                        self.end_interaction(ii, forced_cancel, reset_behavior_after_cancel);
                        return;
                    }
                }
            }
        }
        if initiator == Some(me) {
            if let Some(x) = self.interactions.get_mut(&iid) {
                x.initiator = None;
            }
            for t in targets {
                if let Some(ti) = self.idx(t) {
                    if self.ponies[ti].current_interaction == Some(iid) {
                        self.end_interaction(ti, forced_cancel, reset_behavior_after_cancel);
                    }
                }
            }
        } else if let Some(x) = self.interactions.get_mut(&iid) {
            x.involved_targets.retain(|t| *t != me);
        }
        let mut d = delay;
        if forced_cancel {
            d = d.min(30_000.0);
        }
        self.ponies[i].interaction_cooldown_end = self.ponies[i].current_time + d;
        self.ponies[i].current_interaction = None;
        if reset_behavior_after_cancel {
            self.set_behavior_internal(i, None, false);
        }
    }

    // ------------------------------------------------------------ houses

    pub fn add_house(&mut self, base: Rc<HouseBase>) -> u64 {
        let id = self.next_id;
        self.next_id += 1;
        let region = self.ctx.region;
        let (w, h) = base.image.size;
        let (mut x, mut y) = (region.x as f64, region.y as f64);
        for attempt in 0..40 {
            x = region.x as f64 + self.rng.f64() * (region.w - w as i32).max(0) as f64;
            y = region.y as f64 + self.rng.f64() * (region.h - h as i32).max(0) as f64;
            let r = RectI::new(x as i32, y as i32, w as i32, h as i32).to_f();
            if attempt == 39 || !self.ctx.dead_zones.iter().any(|b| r.intersects(&b.to_f())) {
                break;
            }
        }
        let mut deployed = HashSet::new();
        for p in &self.ponies {
            if base.visitors.iter().any(|v| ci_eq(v, &p.base.directory)) {
                deployed.insert(p.id);
            }
        }
        self.houses.push(House {
            id,
            base,
            top_left: (x as i32, y as i32),
            expired: false,
            drag: false,
            deployed,
            recalling: HashSet::new(),
            recall_expiring: HashMap::new(),
            last_cycle_time: self.elapsed,
        });
        id
    }

    pub fn remove_house(&mut self, id: u64) {
        let mut tracked: Vec<PonyId> = Vec::new();
        if let Some(h) = self.houses.iter_mut().find(|h| h.id == id) {
            h.expired = true;
            tracked.extend(h.deployed.iter().copied());
            tracked.extend(h.recalling.iter().copied());
            tracked.extend(h.recall_expiring.keys().copied());
            h.deployed.clear();
            h.recalling.clear();
            h.recall_expiring.clear();
        }
        for t in tracked {
            if let Some(p) = self.pony_mut(t) {
                p.destination_override = None;
            }
        }
    }

    fn cycle_visitors(&mut self, h: usize, manual: &[PonyId]) {
        let now = self.elapsed;
        if self.houses[h].expired {
            return;
        }
        // Цикл
        if now - self.houses[h].last_cycle_time > self.houses[h].base.cycle_interval * 1000.0 {
            self.houses[h].last_cycle_time = now;
            if self.rng.f64() >= 0.5 {
                if self.rng.f64() < self.houses[h].base.bias {
                    let below_max = (self.houses[h].deployed.len() as i32) < self.houses[h].base.maximum_ponies;
                    if below_max && self.ponies.len() < self.max_pony_count {
                        self.deploy_pony(h);
                    }
                } else if (self.houses[h].deployed.len() as i32) > self.houses[h].base.minimum_ponies && self.ponies.len() > 1 {
                    self.recall_pony(h, manual);
                }
            }
        }
        // Отзываемые пони идут к двери и исчезают.
        for m in manual {
            self.houses[h].recalling.remove(m);
            self.houses[h].recall_expiring.remove(m);
        }
        let door = V2::new(
            (self.houses[h].top_left.0 + self.houses[h].base.door_position.0) as f32,
            (self.houses[h].top_left.1 + self.houses[h].base.door_position.1) as f32,
        );
        let recalling: Vec<PonyId> = self.houses[h].recalling.iter().copied().collect();
        for id in recalling {
            let mut arrived = false;
            if let Some(p) = self.pony_mut(id) {
                p.destination_override = Some(door);
                arrived = p.at_destination();
            } else {
                self.houses[h].recalling.remove(&id);
                continue;
            }
            if arrived {
                self.houses[h].recall_expiring.insert(id, now);
                self.houses[h].recalling.remove(&id);
            }
        }
        let expiring: Vec<(PonyId, f64)> = self.houses[h].recall_expiring.iter().map(|(k, v)| (*k, *v)).collect();
        for (id, t) in expiring {
            if t + RECALL_EXPIRE_DELAY_MS < now {
                self.remove_pony(id);
                self.houses[h].recall_expiring.remove(&id);
            }
        }
    }

    fn deploy_pony(&mut self, h: usize) {
        if self.all_bases.is_empty() {
            return;
        }
        let visitors = self.houses[h].base.visitors.clone();
        let base: Rc<PonyBase> = if visitors.iter().any(|v| v.eq_ignore_ascii_case("all")) {
            self.all_bases[self.rng.usize(0..self.all_bases.len())].clone()
        } else {
            let existing: Vec<String> = self.ponies.iter().map(|p| p.base.directory.to_lowercase()).collect();
            let cands: Vec<Rc<PonyBase>> = self
                .all_bases
                .iter()
                .filter(|b| visitors.iter().any(|v| ci_eq(v, &b.directory)) && !existing.contains(&b.directory.to_lowercase()))
                .cloned()
                .collect();
            if cands.is_empty() {
                return;
            }
            cands[self.rng.usize(0..cands.len())].clone()
        };
        let door = V2::new(
            (self.houses[h].top_left.0 + self.houses[h].base.door_position.0) as f32,
            (self.houses[h].top_left.1 + self.houses[h].base.door_position.1) as f32,
        );
        let id = self.add_pony_at(base, door);
        self.houses[h].deployed.insert(id);
    }

    fn recall_pony(&mut self, h: usize, manual: &[PonyId]) {
        let visitors = self.houses[h].base.visitors.clone();
        let all = visitors.iter().any(|v| v.eq_ignore_ascii_case("all"));
        let cands: Vec<PonyId> = self
            .ponies
            .iter()
            .filter(|p| !p.is_busy() && !manual.contains(&p.id))
            .filter(|p| all || visitors.iter().any(|v| ci_eq(v, &p.base.directory)))
            .map(|p| p.id)
            .collect();
        if cands.is_empty() {
            return;
        }
        let id = cands[self.rng.usize(0..cands.len())];
        self.houses[h].deployed.remove(&id);
        self.houses[h].recalling.insert(id);
    }

    // ------------------------------------------------------------ queries

    /// Ближайшая к точке пони под курсором (GetClosestUnderPoint).
    pub fn closest_pony_under_point(&self, x: i32, y: i32) -> Option<PonyId> {
        let mut best: Option<(f32, PonyId)> = None;
        for p in &self.ponies {
            if p.expired || !p.region.contains_point(x, y) {
                continue;
            }
            let c = RectF::new(p.region.x as f32, p.region.y as f32, p.region.w as f32, p.region.h as f32).center();
            let d = V2::dist_sq(c, V2::new(x as f32, y as f32));
            if best.map(|(bd, _)| d < bd).unwrap_or(true) {
                best = Some((d, p.id));
            }
        }
        best.map(|(_, id)| id)
    }

    pub fn closest_house_under_point(&self, x: i32, y: i32) -> Option<u64> {
        let scale = self.ctx.scale_factor;
        self.houses
            .iter()
            .find(|h| !h.expired && h.region(scale).contains_point(x, y))
            .map(|h| h.id)
    }
}

// ------------------------------------------------------------------ tests

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    /// Синтетическая пони без файлов: размеры картинок задаются вручную.
    fn make_base(dir: &str, behaviors: Vec<Behavior>) -> Rc<PonyBase> {
        let mut b = PonyBase::new(dir, PathBuf::new());
        b.behaviors = behaviors;
        Rc::new(b)
    }

    fn beh(name: &str, chance: f64, speed: f64, mv: u8, w: u32, h: u32) -> Behavior {
        let mut b = Behavior::new();
        b.name = name.to_string();
        b.chance = chance;
        b.speed = speed;
        b.allowed_movement = mv;
        b.min_duration = 1.0;
        b.max_duration = 2.0;
        b.right_image.size = (w, h);
        b.left_image.size = (w, h);
        b
    }

    fn world() -> World {
        let mut w = World::new(Context::new(RectI::new(0, 0, 800, 600)), Some(1234));
        w.ctx.random_speech_chance = 0.0;
        w
    }

    fn run(w: &mut World, seconds: f64) {
        let mut t = w.elapsed;
        let end = t + seconds * 1000.0;
        while t < end {
            t += STEP_SIZE;
            w.update(t);
        }
    }

    #[test]
    fn ponies_stay_on_real_monitors_of_different_height() {
        // 1920x1040 слева и 1366x728 справа: под правым монитором экрана нет
        let left = RectI::new(0, 0, 1920, 1040);
        let right = RectI::new(1920, 0, 1366, 728);
        let bound = left.union(&right);
        let mut w = World::new(Context::new(bound), Some(99));
        w.ctx.random_speech_chance = 0.0;
        w.ctx.areas = vec![left, right];
        w.ctx.dead_zones = crate::winapi::dead_zones(bound, &w.ctx.areas);
        assert_eq!(w.ctx.dead_zones, vec![RectI::new(1920, 728, 1366, 312)]);
        let base = make_base("Walker", vec![beh("walk", 1.0, 3.0, moves::ALL, 60, 60)]);
        let mut ids = Vec::new();
        for _ in 0..12 {
            ids.push(w.add_pony(base.clone()));
        }
        for p in &w.ponies {
            assert!(!p.region().to_f().intersects(&w.ctx.dead_zones[0].to_f()), "появилась вне экрана: {:?}", p.region());
        }
        let dz = w.ctx.dead_zones[0];
        let mut worst = 0;
        let mut t = w.elapsed;
        for _ in 0..(60.0 * STEP_RATE) as usize {
            t += STEP_SIZE;
            w.update(t);
            for p in &w.ponies {
                let r = p.region().intersect(&dz);
                worst = worst.max(r.w.min(r.h));
            }
        }
        // отскок происходит в момент касания: заходить глубже нескольких пикселей нельзя
        assert!(worst <= 8, "пони уходила вглубь места без экрана на {} px", worst);
    }

    #[test]
    fn walker_stays_inside_region_and_moves() {
        let mut w = world();
        let base = make_base("walker", vec![beh("walk", 1.0, 3.0, moves::ALL, 50, 40)]);
        let id = w.add_pony(base);
        let start = w.pony(id).unwrap().location();
        let mut moved = false;
        let mut min = (f32::MAX, f32::MAX);
        let mut max = (f32::MIN, f32::MIN);
        for _ in 0..60 * 25 {
            let t = w.elapsed + STEP_SIZE;
            w.update(t);
            let p = w.pony(id).unwrap();
            let l = p.location();
            moved |= V2::dist_sq(l, start) > 100.0;
            let r = p.region();
            min = (min.0.min(r.left() as f32), min.1.min(r.top() as f32));
            max = (max.0.max(r.right() as f32), max.1.max(r.bottom() as f32));
        }
        assert!(moved, "pony never moved");
        assert!(min.0 >= -2.0 && min.1 >= -2.0, "left the region: {:?}", min);
        assert!(max.0 <= 802.0 && max.1 <= 602.0, "left the region: {:?}", max);
    }

    #[test]
    fn speed_is_pixels_per_step() {
        // Speed 3 => 100 px/s => 4 px/step при 25 шагах/с.
        let mut w = world();
        let base = make_base("h", vec![beh("go", 1.0, 3.0, moves::HORIZONTAL_ONLY, 20, 20)]);
        let id = w.add_pony_at(base, V2::new(400.0, 300.0));
        let l0 = w.pony(id).unwrap().location();
        let t = w.elapsed + STEP_SIZE;
        w.update(t);
        let l1 = w.pony(id).unwrap().location();
        let d = ((l1.x - l0.x).powi(2) + (l1.y - l0.y).powi(2)).sqrt();
        assert!((d - 4.0).abs() < 0.01, "moved {} px in one step", d);
        assert_eq!(l1.y, l0.y, "horizontal only");
    }

    #[test]
    fn linked_behavior_follows_chain() {
        let mut w = world();
        let mut a = beh("a", 1.0, 0.0, moves::NONE, 20, 20);
        a.linked_behavior = "b".to_string();
        a.min_duration = 0.2;
        a.max_duration = 0.2;
        let mut b = beh("b", 0.0, 0.0, moves::NONE, 20, 20);
        b.min_duration = 100.0;
        b.max_duration = 100.0;
        let id = w.add_pony(make_base("chain", vec![a, b]));
        assert_eq!(w.pony(id).unwrap().current_behavior().name, "a");
        run(&mut w, 1.0);
        assert_eq!(w.pony(id).unwrap().current_behavior().name, "b", "linked behavior must follow, even with chance 0");
    }

    #[test]
    fn mouseover_and_sleep_states() {
        let mut w = world();
        let mut stand = beh("stand", 1.0, 0.0, moves::MOUSE_OVER, 40, 40);
        stand.min_duration = 50.0;
        stand.max_duration = 50.0;
        let walk = beh("walk", 0.0, 3.0, moves::ALL, 40, 40);
        let mut sleep = beh("zzz", 0.0, 0.0, moves::SLEEP, 40, 40);
        sleep.chance = 0.0;
        let id = w.add_pony_at(make_base("m", vec![stand, walk, sleep]), V2::new(300.0, 300.0));
        run(&mut w, 0.5);
        // сон
        w.pony_mut(id).unwrap().sleep = true;
        run(&mut w, 0.2);
        assert!(w.pony(id).unwrap().is_sleeping());
        assert_eq!(w.pony(id).unwrap().current_behavior().name, "zzz");
        let loc = w.pony(id).unwrap().location();
        run(&mut w, 1.0);
        assert_eq!(w.pony(id).unwrap().location(), loc, "sleeping pony does not move");
        w.pony_mut(id).unwrap().sleep = false;
        run(&mut w, 0.2);
        assert!(!w.pony(id).unwrap().is_sleeping());
        // наведение курсора
        let l = w.pony(id).unwrap().location();
        w.ctx.cursor = (l.x as i32, l.y as i32);
        run(&mut w, 0.2);
        assert!(w.pony(id).unwrap().is_busy(), "mouseover makes the pony busy");
        assert_eq!(w.pony(id).unwrap().current_behavior().name, "stand");
    }

    #[test]
    fn follow_target_moves_toward_other_pony() {
        let mut w = world();
        w.ctx.cursor_avoidance_enabled = false;
        let mut follow = beh("follow", 1.0, 3.0, moves::ALL, 20, 20);
        follow.follow_target = "leader".to_string();
        follow.min_duration = 60.0;
        follow.max_duration = 60.0;
        follow.target_vector = (0, 0);
        let leader = make_base("leader", vec![beh("stand", 1.0, 0.0, moves::NONE, 20, 20)]);
        let follower = make_base("follower", vec![follow]);
        let lid = w.add_pony_at(leader, V2::new(600.0, 300.0));
        let fid = w.add_pony_at(follower, V2::new(100.0, 300.0));
        let d0 = V2::dist_sq(w.pony(lid).unwrap().location(), w.pony(fid).unwrap().location());
        run(&mut w, 3.0);
        let d1 = V2::dist_sq(w.pony(lid).unwrap().location(), w.pony(fid).unwrap().location());
        assert!(d1 < d0 * 0.6, "follower must approach leader: {} -> {}", d0, d1);
    }

    #[test]
    fn interaction_starts_between_nearby_ponies() {
        let mut w = world();
        w.ctx.cursor_avoidance_enabled = false;
        let mut a = PonyBase::new("aa", PathBuf::new());
        let mut stand = beh("stand", 1.0, 0.0, moves::NONE, 20, 20);
        stand.min_duration = 60.0;
        stand.max_duration = 60.0;
        let hello = beh("hello", 0.0, 0.0, moves::NONE, 20, 20);
        a.behaviors = vec![stand.clone(), hello.clone()];
        a.interactions = vec![InteractionBase {
            name: "greet".into(),
            initiator_name: "aa".into(),
            chance: 1.0,
            proximity: 500.0,
            target_names: vec!["bb".into()],
            activation: TargetActivation::One,
            behavior_names: vec!["hello".into()],
            reactivation_delay: 60.0,
        }];
        let mut b = PonyBase::new("bb", PathBuf::new());
        b.behaviors = vec![stand, hello];
        let ia = w.add_pony_at(Rc::new(a), V2::new(300.0, 300.0));
        let ib = w.add_pony_at(Rc::new(b), V2::new(400.0, 300.0));
        run(&mut w, 1.0);
        assert_eq!(w.pony(ia).unwrap().current_behavior().name, "hello");
        assert_eq!(w.pony(ib).unwrap().current_behavior().name, "hello");
        // Взаимодействие завершается по окончании поведения и не перезапускается
        // мгновенно (reactivation delay).
        assert!(w.pony(ia).unwrap().is_busy());
    }

    #[test]
    fn effects_are_created_and_expire() {
        let mut w = world();
        w.ctx.cursor_avoidance_enabled = false;
        let mut b = PonyBase::new("fx", PathBuf::new());
        let mut go = beh("go", 1.0, 0.0, moves::NONE, 40, 40);
        go.min_duration = 60.0;
        go.max_duration = 60.0;
        b.behaviors = vec![go];
        let mut e = EffectBase::new();
        e.name = "spark".into();
        e.behavior_name = "go".into();
        e.right_image.size = (10, 10);
        e.left_image.size = (10, 10);
        e.duration = 1.0;
        e.repeat_delay = 0.4;
        e.placement_right = Direction::TopCenter;
        e.placement_left = Direction::TopCenter;
        e.centering_right = Direction::BottomCenter;
        e.centering_left = Direction::BottomCenter;
        b.effects = vec![e];
        w.add_pony_at(Rc::new(b), V2::new(400.0, 300.0));
        assert_eq!(w.effects.len(), 1, "effect starts with behavior");
        run(&mut w, 0.5);
        assert!(w.effects.len() >= 2, "repeat delay spawns more");
        run(&mut w, 3.0);
        assert!(w.effects.len() <= 4, "effects expire after duration: {}", w.effects.len());
        // Позиция: над пони (Top/Bottom)
        let eff = &w.effects[0];
        assert!(eff.top_left.1 < 300, "effect is above the pony");
    }

    #[test]
    fn speech_bubble_text_and_expiry() {
        let mut w = world();
        w.ctx.cursor_avoidance_enabled = false;
        let mut bb = PonyBase::new("talker", PathBuf::new());
        bb.display_name = "Talker".into();
        let mut b1 = beh("hi", 1.0, 0.0, moves::NONE, 20, 20);
        b1.start_line = "greeting".into();
        b1.min_duration = 60.0;
        b1.max_duration = 60.0;
        bb.behaviors = vec![b1];
        bb.speeches = vec![Speech { name: "greeting".into(), text: "Hello!".into(), sound_file: None, skip: true, group: 0 }];
        let id = w.add_pony_at(Rc::new(bb), V2::new(300.0, 300.0));
        assert_eq!(w.pony(id).unwrap().speech_text(), Some("Talker: \"Hello!\""));
        run(&mut w, 5.0);
        assert_eq!(w.pony(id).unwrap().speech_text(), None, "bubble disappears");
    }

    #[test]
    fn real_ponies_simulate_without_panics() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let coll = crate::loader::PonyCollection::load(&root, true);
        let mut w = world();
        w.ctx.random_speech_chance = 0.5;
        for name in ["Twilight Sparkle", "Applejack", "Rainbow Dash", "Pinkie Pie", "Rarity", "Fluttershy", "Princess Celestia", "Princess Luna"] {
            let base = coll.base_by_directory(name).unwrap_or_else(|| panic!("missing {}", name));
            w.add_pony(Rc::new(base.clone()));
        }
        w.ctx.cursor = (200, 200);
        run(&mut w, 120.0);
        assert_eq!(w.ponies.len(), 8);
        for p in &w.ponies {
            let r = p.region();
            assert!(r.right() > -400 && r.left() < 1200, "{} is far outside: {:?}", p.base.directory, r);
        }
    }
}
