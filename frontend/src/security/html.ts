import DOMPurify from 'dompurify'
import { marked } from 'marked'

const REPORT_TAGS = [
  'a', 'blockquote', 'br', 'code', 'del', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'hr', 'li', 'ol', 'p', 'pre', 'strong', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul'
]

const REPORT_ATTRIBUTES = ['class', 'href', 'title']

export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function hasAsciiControlCharacter(value: string): boolean {
  return Array.from(value).some(character => {
    const codePoint = character.codePointAt(0) ?? 0
    return codePoint <= 0x1f || codePoint === 0x7f
  })
}

export function renderSafeMarkdown(markdown: string): string {
  const parsed = marked.parse(markdown || '') as string
  const sanitized = DOMPurify.sanitize(parsed, {
    ALLOWED_TAGS: REPORT_TAGS,
    ALLOWED_ATTR: REPORT_ATTRIBUTES,
    ALLOW_DATA_ATTR: false,
    ALLOW_UNKNOWN_PROTOCOLS: false,
    FORBID_TAGS: ['math', 'svg'],
    FORBID_ATTR: ['style']
  })

  const container = document.createElement('div')
  container.innerHTML = sanitized
  container.querySelectorAll('a[href]').forEach(link => {
    const href = (link.getAttribute('href') || '').trim()
    const scheme = href.match(/^([a-z][a-z0-9+.-]*):/i)?.[1].toLowerCase()

    link.removeAttribute('target')
    link.removeAttribute('rel')
    if (!href || hasAsciiControlCharacter(href) || (scheme && !['http', 'https', 'mailto'].includes(scheme))) {
      link.removeAttribute('href')
      return
    }

    link.setAttribute('href', href)
    if (scheme === 'http' || scheme === 'https' || href.startsWith('//')) {
      link.setAttribute('target', '_blank')
      link.setAttribute('rel', 'noopener noreferrer')
    }
  })
  return container.innerHTML
}
