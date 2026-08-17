import { describe, expect, it } from 'vitest'

import { escapeHtml, renderSafeMarkdown } from './html'


describe('renderSafeMarkdown', () => {
  it('removes executable HTML and dangerous URLs', () => {
    const markdown = [
      '# 安全报告',
      '<script>window.__xss = true</script>',
      '<img src=x onerror="window.__xss = true">',
      '<svg><circle onload="window.__xss = true" /></svg>',
      '[危险链接](javascript:alert(1))',
      '[数据链接](data:text/html,<script>alert(1)</script>)'
    ].join('\n\n')

    const html = renderSafeMarkdown(markdown)

    expect(html).toContain('<h1>安全报告</h1>')
    expect(html).not.toMatch(/script|onerror|onload|<svg|javascript:|data:text\/html/i)
  })

  it('keeps supported report formatting and hardens external links', () => {
    const html = renderSafeMarkdown(
      '# 标题\n\n- 项目一\n- 项目二\n\n|列|值|\n|-|-|\n|A|1|\n\n[文档](https://example.com/docs)'
    )

    expect(html).toContain('<ul>')
    expect(html).toContain('<table>')
    expect(html).toContain('href="https://example.com/docs"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('normalizes link protocols and ignores persisted target attributes', () => {
    const html = renderSafeMarkdown([
      '[FTP](ftp://example.com/file)',
      '[外链](//example.com/docs)',
      '<a href="/internal" target="_blank" rel="opener">站内</a>'
    ].join('\n\n'))
    const container = document.createElement('div')
    container.innerHTML = html
    const links = Array.from(container.querySelectorAll('a'))

    expect(links[0].hasAttribute('href')).toBe(false)
    expect(links[1].getAttribute('target')).toBe('_blank')
    expect(links[1].getAttribute('rel')).toBe('noopener noreferrer')
    expect(links[2].getAttribute('href')).toBe('/internal')
    expect(links[2].hasAttribute('target')).toBe(false)
    expect(links[2].hasAttribute('rel')).toBe(false)
  })

  it('removes links containing ASCII control characters', () => {
    const html = renderSafeMarkdown('<a href="https://example.com/\u007fsecret">控制字符链接</a>')
    const container = document.createElement('div')
    container.innerHTML = html

    expect(container.querySelector('a')?.hasAttribute('href')).toBe(false)
  })

  it('escapes dynamic tooltip text', () => {
    expect(escapeHtml('<img src=x onerror=alert(1)>')).toBe('&lt;img src=x onerror=alert(1)&gt;')
  })
})
