const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE_PATTERN = /^\+?[0-9][0-9 ()-]{5,19}$/
const RESERVED_EMAIL_TLDS = new Set(['example', 'invalid', 'local', 'localhost', 'test'])

export function isValidOptionalEmail(value: string): boolean {
  const normalized = value.trim()
  if (normalized === '') return true
  if (!EMAIL_PATTERN.test(normalized)) return false

  const domain = normalized.slice(normalized.lastIndexOf('@') + 1).toLowerCase()
  const topLevelDomain = domain.slice(domain.lastIndexOf('.') + 1)
  return !RESERVED_EMAIL_TLDS.has(topLevelDomain)
}

export function isValidOptionalPhone(value: string): boolean {
  const normalized = value.trim()
  return normalized === '' || PHONE_PATTERN.test(normalized)
}
