// src_rust/editor/pony_preview.rs
use std::sync::{Arc, Mutex};
use std::path::PathBuf;
use wry::{WebView, WebViewBuilder};
use winit::window::Window;
use crate::loader::DesktopPoniesLoader;
use crate::pony::PonyEntity;
use glam::Vec2;

pub struct PonyPreview {
    webview: WebView,
    pony: Option<PonyEntity>,
    loader: Arc<Mutex<DesktopPoniesLoader>>,
}

impl PonyPreview {
    pub fn new(
        window: Arc<Window>,
        loader: Arc<Mutex<DesktopPoniesLoader>>,
    ) -> Result<Self, String> {
        let html = build_preview_html();

        let webview = WebViewBuilder::new()
            .with_html(&html)
            .build(&*window)
            .map_err(|e| format!("Failed to build preview webview: {}", e))?;

        Ok(Self {
            webview,
            pony: None,
            loader,
        })
    }

    pub fn load_pony(&mut self, pony_name: &str, behavior_name: Option<&str>) {
        let loader = self.loader.lock().unwrap();
        if let Some(config) = loader.get_config(pony_name) {
            // Загружаем спрайты для предпросмотра
            let behavior = if let Some(name) = behavior_name {
                config.behaviors.iter().find(|b| b.name == name)
            } else {
                config.behaviors.first()
            };

            if let Some(behavior) = behavior {
                let sprite_name = if !behavior.sprite_right.is_empty() {
                    &behavior.sprite_right
                } else {
                    &behavior.sprite_left
                };

                let (frames, fc, w, h, delay) = loader.load_pony_frames(pony_name, sprite_name);

                // Отправляем данные в WebView для отображения
                let js = format!(
                    "window.showPreview({}, {}, {}, {}, {}, {});",
                    serde_json::to_string(&frames).unwrap_or_default(),
                    fc, w, h, delay,
                    serde_json::to_string(&behavior.name).unwrap_or_default()
                );
                let _ = self.webview.evaluate_script(&js);
            }
        }
    }
}

fn build_preview_html() -> String {
    r#"
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                margin: 0;
                padding: 0;
                background: #1e1e2e;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                overflow: hidden;
            }
            canvas {
                image-rendering: crisp-edges;
                image-rendering: pixelated;
                image-rendering: pixelated;
            }
        </style>
    </head>
    <body>
        <canvas id="preview-canvas" width="400" height="400"></canvas>
        <script>
            const canvas = document.getElementById('preview-canvas');
            const ctx = canvas.getContext('2d');
            let frames = [];
            let currentFrame = 0;
            let frameCount = 1;
            let width = 100;
            let height = 100;
            let frameDuration = 0.1;
            let lastTime = 0;
            let behaviorName = '';

            window.showPreview = function(framesData, fc, w, h, duration, name) {
                frames = framesData;
                frameCount = fc;
                width = w;
                height = h;
                frameDuration = duration;
                behaviorName = name;
                currentFrame = 0;
                lastTime = performance.now() / 1000;
                document.title = 'Preview: ' + name;
                draw();
            };

            function draw() {
                if (frames.length === 0 || currentFrame >= frames.length) return;

                const frame = frames[currentFrame];
                const imageData = new ImageData(width, height);

                for (let i = 0; i < frame.length; i++) {
                    const pixel = frame[i];
                    const a = (pixel >> 24) & 0xFF;
                    const r = (pixel >> 16) & 0xFF;
                    const g = (pixel >> 8) & 0xFF;
                    const b = pixel & 0xFF;

                    imageData.data[i * 4] = r;
                    imageData.data[i * 4 + 1] = g;
                    imageData.data[i * 4 + 2] = b;
                    imageData.data[i * 4 + 3] = a;
                }

                ctx.clearRect(0, 0, canvas.width, canvas.height);

                const scale = Math.min(canvas.width / width, canvas.height / height);
                const x = (canvas.width - width * scale) / 2;
                const y = (canvas.height - height * scale) / 2;

                canvas.width = width * scale;
                canvas.height = height * scale;
                canvas.style.width = (width * scale) + 'px';
                canvas.style.height = (height * scale) + 'px';

                const tempCanvas = new OffscreenCanvas(width, height);
                tempCanvas.getContext('2d').putImageData(imageData, 0, 0);
                ctx.drawImage(tempCanvas, 0, 0, width, height, 0, 0, width * scale, height * scale);

                requestAnimationFrame(animate);
            }

            function animate(now) {
                const current = now / 1000;
                if (current - lastTime >= frameDuration) {
                    lastTime = current;
                    currentFrame = (currentFrame + 1) % frameCount;
                    draw();
                } else {
                    requestAnimationFrame(animate);
                }
            }

            console.log('Preview ready');
        </script>
    </body>
    </html>
    "#.to_string()
}