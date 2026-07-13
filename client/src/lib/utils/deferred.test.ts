import { describe, it, expect, vi } from 'vitest';
import { DeferredMap } from './deferred';

describe('DeferredMap', () => {
    it('resolves get() immediately when the value is already set', async () => {
        const m = new DeferredMap<string, number>();
        m.set('a', 1);
        await expect(m.get('a')).resolves.toBe(1);
    });

    it('resolves a pending get() once the value arrives later', async () => {
        const m = new DeferredMap<string, number>();
        const pending = m.get('b');
        m.set('b', 42);
        await expect(pending).resolves.toBe(42);
    });

    it('resolves all waiters registered for the same key', async () => {
        const m = new DeferredMap<string, number>();
        const w1 = m.get('c');
        const w2 = m.get('c');
        m.set('c', 7);
        await expect(Promise.all([w1, w2])).resolves.toEqual([7, 7]);
    });

    it('getSync returns the value or undefined, and has() tracks membership', () => {
        const m = new DeferredMap<string, number>();
        expect(m.getSync('x')).toBeUndefined();
        expect(m.has('x')).toBe(false);
        m.set('x', 5);
        expect(m.getSync('x')).toBe(5);
        expect(m.has('x')).toBe(true);
    });

    it('ignores a duplicate set and warns', () => {
        const m = new DeferredMap<string, number>();
        const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
        m.set('d', 1);
        m.set('d', 2);
        expect(m.getSync('d')).toBe(1);
        expect(warn).toHaveBeenCalledOnce();
        warn.mockRestore();
    });

    it('clear() empties values and waiters', () => {
        const m = new DeferredMap<string, number>();
        m.set('e', 1);
        m.clear();
        expect(m.has('e')).toBe(false);
        expect(m.getSync('e')).toBeUndefined();
    });
});
