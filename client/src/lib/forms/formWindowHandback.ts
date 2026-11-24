/**
 * Runs inside the form window, injected as text, so it uses nothing from outside itself.
 * When the opening page goes away it replaces the dead form with "Loading…" and hands the window to the next page.
 */
export function formWindowHandback(win: Window): void {
    type Opener = Window & { adoptFormWindow?: (win: Window) => void };
    const root = win.document.documentElement;
    const show = (text: string) => {
        const line = win.document.createElement("p");
        line.style.padding = "1rem";
        line.textContent = text;
        win.document.body.replaceChildren(line);
    };
    const showClosed = () => {
        show(
            root.dataset.from === "browse"
                ? "The page that opened this form closed. Open the form again to continue."
                : "The viewer closed. Open a form from the viewer to continue.",
        );
        // This copy stops here; the next page to open a form injects a new one.
        delete root.dataset.eyenedForm;
    };

    function watch(): void {
        const opener = win.opener as Opener | null;
        if (!opener || opener.closed) return;
        opener.addEventListener("pagehide", () => {
            const gone = opener.document;
            delete root.dataset.mounted;
            show(root.dataset.loading || "Loading…");
            delete root.dataset.loading;
            let polls = 0;
            const timer = win.setInterval(() => {
                const next = win.opener as Opener | null;
                // A click on the new page filled the window first.
                if (root.dataset.mounted) {
                    win.clearInterval(timer);
                    watch();
                    return;
                }
                if (!next || next.closed) {
                    win.clearInterval(timer);
                    showClosed();
                    return;
                }
                try {
                    if (
                        next.document !== gone &&
                        typeof next.adoptFormWindow === "function"
                    ) {
                        win.clearInterval(timer);
                        next.adoptFormWindow(win);
                        watch();
                        return;
                    }
                } catch {
                    // Another site (a login page) is loading; keep waiting.
                }
                // 40 polls of 250 ms: 10 s.
                if (++polls >= 40) {
                    win.clearInterval(timer);
                    showClosed();
                }
            }, 250);
        });
    }
    watch();
}
