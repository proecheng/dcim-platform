import { describe, expect, it } from 'vitest'
import { isValidOptionalEmail, isValidOptionalPhone } from '@/utils/userValidation'

describe('user form validation', () => {
  it('accepts empty or valid email values', () => {
    expect(isValidOptionalEmail('')).toBe(true)
    expect(isValidOptionalEmail('  admin@example.com  ')).toBe(true)
    expect(isValidOptionalEmail('invalid-email')).toBe(false)
    expect(isValidOptionalEmail('admin@example')).toBe(false)
    expect(isValidOptionalEmail('admin@example.invalid')).toBe(false)
    expect(isValidOptionalEmail('admin@example.test')).toBe(false)
  })

  it('accepts common phone formats and rejects incomplete values', () => {
    expect(isValidOptionalPhone('')).toBe(true)
    expect(isValidOptionalPhone('13800138000')).toBe(true)
    expect(isValidOptionalPhone('+86 138-0013-8000')).toBe(true)
    expect(isValidOptionalPhone('123')).toBe(false)
    expect(isValidOptionalPhone('phone-number')).toBe(false)
  })
})
