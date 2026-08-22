import { describe, expect, it } from 'vitest'
import { getApiErrorMessage } from '@/utils/apiErrorMessage'

describe('getApiErrorMessage', () => {
  it('formats FastAPI validation errors with their field path', () => {
    const error = {
      response: {
        data: {
          detail: [
            {
              loc: ['body', 'email'],
              msg: 'value is not a valid email address',
              type: 'value_error',
            },
          ],
        },
      },
    }

    expect(getApiErrorMessage(error, '操作失败')).toBe(
      'email: value is not a valid email address',
    )
  })

  it('preserves string API errors and falls back when the payload is empty', () => {
    expect(
      getApiErrorMessage({ response: { data: { detail: '用户名已存在' } } }, '操作失败'),
    ).toBe('用户名已存在')
    expect(getApiErrorMessage({ response: { data: {} } }, '操作失败')).toBe('操作失败')
  })
})
