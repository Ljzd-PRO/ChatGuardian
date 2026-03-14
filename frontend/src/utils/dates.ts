/**
 * Parse backend timestamps that arrive as "YYYY-MM-DD HH:MM:SS" (UTC).
 * Replacing the space with "T" and appending "Z" gives a valid ISO-8601
 * string that all browsers (including Safari) parse correctly.
 *
 * Expected format: "2024-01-15 09:30:00" → new Date("2024-01-15T09:30:00Z")
 */
export function parseBackendDate(s: string): Date {
  return new Date(s.replace(' ', 'T') + 'Z');
}
