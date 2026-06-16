// PATCH для исправления отображения Trace Reference
// В функции loadReference() добавить после redrawWithTrace() и updatePreview():

// Вместо прямого вызова redrawWithTrace(), используйте:
function ensureTraceRendered() {
    // Гарантирует, что DOM полностью обновлён перед перерисовкой
    requestAnimationFrame(() => {
        redrawWithTrace();
        // Если всё ещё не видно, добавьте ещё один вызов
        requestAnimationFrame(() => {
            redrawWithTrace();
        });
    });
}

// ИЛИ для более простого решения - просто добавьте:
// setTimeout(() => redrawWithTrace(), 0);
// Это гарантирует, что redrawWithTrace() вызовется ПОСЛЕ того, как браузер закончит обновление DOM
