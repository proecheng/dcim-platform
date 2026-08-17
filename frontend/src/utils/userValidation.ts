const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE_PATTERN = /^\+?[0-9][0-9 ()-]{5,19}$/

export function isValidOptionalEmail(value: string): boolean {
  const normalized = value.trim()
  return normalized === '' || EMAIL_PATTERN.test(normalized)
}

export function isValidOptionalPhone(value: string): boolean {
  const normalized = value.trim()
  return normalized === '' || PHONE_PATTERN.test(normalized)
}
