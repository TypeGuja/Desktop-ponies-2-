// src_rust/audio.rs
//
// Воспроизведение звуков речи пони (mp3/ogg/wav) через rodio. Если звукового
// устройства нет — все вызовы тихо ничего не делают. Ограничения как в
// оригинале: громкость из настроек, «не больше одного звука одновременно»
// (SoundSingleChannelOnly) либо «не больше одного звука на пони».

use rodio::{Decoder, OutputStream, OutputStreamHandle, Sink};
use std::collections::HashMap;
use std::fs::File;
use std::io::BufReader;

pub struct Audio {
    // stream должен жить, пока играет звук.
    _stream: Option<OutputStream>,
    handle: Option<OutputStreamHandle>,
    sinks: Vec<(u64, Sink)>,
    per_owner: HashMap<u64, ()>,
}

impl Audio {
    pub fn new() -> Audio {
        match OutputStream::try_default() {
            Ok((stream, handle)) => Audio { _stream: Some(stream), handle: Some(handle), sinks: Vec::new(), per_owner: HashMap::new() },
            Err(e) => {
                eprintln!("[Audio] No output device: {}", e);
                Audio { _stream: None, handle: None, sinks: Vec::new(), per_owner: HashMap::new() }
            }
        }
    }

    pub fn available(&self) -> bool {
        self.handle.is_some()
    }

    /// Убирает закончившиеся звуки.
    pub fn cleanup(&mut self) {
        self.sinks.retain(|(_, s)| !s.empty());
        self.per_owner.retain(|o, _| self.sinks.iter().any(|(id, _)| id == o));
    }

    pub fn is_playing(&self) -> bool {
        !self.sinks.is_empty()
    }

    pub fn play(&mut self, owner: u64, path: &str, volume: f32, single_channel_only: bool) {
        let Some(handle) = self.handle.clone() else { return };
        self.cleanup();
        if single_channel_only {
            if !self.sinks.is_empty() {
                return;
            }
        } else if self.per_owner.contains_key(&owner) {
            return;
        }
        let Ok(file) = File::open(path) else { return };
        let Ok(source) = Decoder::new(BufReader::new(file)) else { return };
        let Ok(sink) = Sink::try_new(&handle) else { return };
        sink.set_volume(volume.clamp(0.0, 1.0));
        sink.append(source);
        self.sinks.push((owner, sink));
        self.per_owner.insert(owner, ());
    }

    pub fn stop_all(&mut self) {
        self.sinks.clear();
        self.per_owner.clear();
    }
}
