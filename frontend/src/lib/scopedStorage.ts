import { useAuthStore } from '@/store/useAuthStore';

/**
 * Extracts the user identifier from the stored JWT token.
 * Decodes the base64url payload without any library dependency.
 * Returns a fallback string if the token is absent or malformed,
 * which keeps the storage keys deterministic but isolated.
 */
export function getUserId(): string {
  const token = useAuthStore.getState().token;
  if (!token) return '__anonymous__';

  try {
    const payloadB64 = token.split('.')[1];
    if (!payloadB64) return '__anonymous__';

    // base64url → base64
    const base64 = payloadB64.replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(base64);
    const payload = JSON.parse(json);

    // Common JWT claims for user identity: sub, user_id, username
    return payload.sub || payload.user_id || payload.username || '__unknown__';
  } catch {
    return '__anonymous__';
  }
}

/**
 * Returns a localStorage key scoped to the current logged-in user.
 * Example: scopedKey('graph_positions') → 'graph_positions_officer_jones'
 *
 * IMPORTANT: On a shared police workstation, this prevents one officer's
 * session data (graph layouts, theme, sidebar state) from leaking to another.
 */
export function scopedKey(baseKey: string): string {
  return `${baseKey}_${getUserId()}`;
}

/**
 * Reads a value from user-scoped localStorage.
 */
export function getScopedItem(baseKey: string): string | null {
  return localStorage.getItem(scopedKey(baseKey));
}

/**
 * Writes a value to user-scoped localStorage.
 */
export function setScopedItem(baseKey: string, value: string): void {
  localStorage.setItem(scopedKey(baseKey), value);
}

/**
 * Removes a value from user-scoped localStorage.
 */
export function removeScopedItem(baseKey: string): void {
  localStorage.removeItem(scopedKey(baseKey));
}
