/**
 * Device ID utility for Platziflix ratings system
 *
 * Generates and persists a unique device identifier in localStorage
 * to track user ratings without authentication.
 */

const STORAGE_KEY = "platziflix_device_id";

/**
 * Gets or creates a unique device ID for the current browser.
 *
 * @returns Device ID (UUID) or empty string during SSR
 *
 * @example
 * ```ts
 * const deviceId = getDeviceId();
 * // "550e8400-e29b-41d4-a716-446655440000"
 * ```
 */
export function getDeviceId(): string {
  // Guard against SSR execution
  if (typeof window === "undefined") return "";

  // Check if device ID already exists
  let deviceId = localStorage.getItem(STORAGE_KEY);

  // Generate new UUID if not found
  if (!deviceId) {
    deviceId = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, deviceId);
  }

  return deviceId;
}
