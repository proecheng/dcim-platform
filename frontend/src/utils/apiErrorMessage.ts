interface ValidationErrorDetail {
  loc?: unknown
  msg?: unknown
}

function formatValidationErrors(detail: unknown): string | undefined {
  if (!Array.isArray(detail)) return undefined

  const messages = detail.flatMap((item: ValidationErrorDetail) => {
    if (typeof item?.msg !== 'string' || item.msg.trim() === '') return []

    const location = Array.isArray(item.loc)
      ? item.loc.filter(part => part !== 'body').map(String).join('.')
      : ''
    return [location ? `${location}: ${item.msg}` : item.msg]
  })

  return messages.length > 0 ? messages.join('; ') : undefined
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  const data = (error as any)?.response?.data
  return (
    (typeof data?.detail === 'string' && data.detail) ||
    formatValidationErrors(data?.detail) ||
    (typeof data?.error?.message === 'string' && data.error.message) ||
    (typeof data?.error === 'string' && data.error) ||
    (typeof data?.message === 'string' && data.message) ||
    fallback
  )
}
