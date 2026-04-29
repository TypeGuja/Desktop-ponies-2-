// src_rust/interaction.rs
use crate::pony::PonyEntity;
use crate::world::World;
use glam::Vec2;

pub struct InteractionSystem;

impl InteractionSystem {
    /// Проверяет, находятся ли два пони достаточно близко для взаимодействия
    pub fn are_ponies_close(a: &PonyEntity, b: &PonyEntity, threshold: f32) -> bool {
        a.position.distance(b.position) < threshold
    }

    /// Заставляет пони A подойти к пони B
    pub fn move_towards(a: &mut PonyEntity, b: &PonyEntity, speed: f32) {
        let direction = (b.position - a.position).normalize();
        a.velocity = direction * speed;
        if direction.x > 0.0 {
            a.facing_right = true;
        } else if direction.x < 0.0 {
            a.facing_right = false;
        }
    }

    /// Находит всех пони в радиусе
    pub fn find_nearby_ponies<'a>(
        pony: &PonyEntity,
        world: &'a World,
        radius: f32,
    ) -> Vec<&'a PonyEntity> {
        world.ponies.values()
            .filter(|other| {
                other.id != pony.id &&
                    pony.position.distance(other.position) < radius
            })
            .collect()
    }

    /// Запускает Conga-line (танец конга)
    pub fn start_conga(world: &mut World, leader_id: u64) {
        let leader_pos = world.ponies.get(&leader_id).map(|p| p.position);
        if leader_pos.is_none() { return; }
        let leader_pos = leader_pos.unwrap();

        let mut followers: Vec<u64> = world.ponies.keys()
            .filter(|&&id| id != leader_id)
            .copied()
            .collect();

        // Сортируем по расстоянию до лидера
        followers.sort_by(|&a, &b| {
            let dist_a = world.ponies.get(&a).map(|p| p.position.distance(leader_pos)).unwrap_or(f32::MAX);
            let dist_b = world.ponies.get(&b).map(|p| p.position.distance(leader_pos)).unwrap_or(f32::MAX);
            dist_a.partial_cmp(&dist_b).unwrap()
        });

        // Назначаем позиции в линии
        for (i, &follower_id) in followers.iter().enumerate() {
            if let Some(pony) = world.ponies.get_mut(&follower_id) {
                pony.current_animation = "conga".to_string();
                pony.animation_time = i as f32 * 0.3; // сдвиг фазы
                pony.speed_override = Some(0.5);
            }
        }
    }
}