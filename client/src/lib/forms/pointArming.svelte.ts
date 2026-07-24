type Armed = { key: string; dispose: () => void };

class PointArming {
    armed: Armed | null = $state(null);

    arm(key: string, attach: () => () => void) {
        if (this.armed?.key === key) {
            this.disarm();
            return;
        }
        this.disarm();
        this.armed = { key, dispose: attach() };
    }

    disarm(key?: string) {
        if (key && this.armed?.key !== key) return;
        this.armed?.dispose();
        this.armed = null;
    }

    isArmed(key: string) {
        return this.armed?.key === key;
    }
}

export const pointArming = new PointArming();
