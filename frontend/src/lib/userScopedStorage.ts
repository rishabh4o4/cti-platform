import type { StateStorage } from 'zustand/middleware';
import { getUserId } from './scopedStorage';

/**
 * A Zustand-compatible StateStorage adapter that scopes every key
 * to the currently logged-in user. On shared police workstations
 * this prevents one officer's preferences from leaking to another.
 *
 * Usage:
 *   persist(stateCreator, { name: 'theme', storage: createJSONStorage(() => userScopedStorage) })
 *
 * The actual localStorage key becomes `theme_<userId>`.
 */
export const userScopedStorage: StateStorage = {
  getItem(name: string): string | null {
    const key = `${name}_${getUserId()}`;
    return localStorage.getItem(key);
  },
  setItem(name: string, value: string): void {
    const key = `${name}_${getUserId()}`;
    localStorage.setItem(key, value);
  },
  removeItem(name: string): void {
    const key = `${name}_${getUserId()}`;
    localStorage.removeItem(key);
  },
};
