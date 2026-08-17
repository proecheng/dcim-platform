import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const sourceRoot = path.resolve(__dirname, '..')
const allowedDynamicHtmlFiles = new Set([
  path.normalize('components/common/SafeRichText.vue'),
  path.normalize('security/html.ts')
])

function sourceFiles(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const absolutePath = path.join(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(absolutePath)
    return /\.(vue|ts)$/.test(entry.name) && !entry.name.endsWith('.test.ts') ? [absolutePath] : []
  })
}

describe('dynamic HTML sink policy', () => {
  it('keeps dynamic HTML APIs inside the reviewed security boundary', { timeout: 30_000 }, () => {
    const violations = sourceFiles(sourceRoot).flatMap(file => {
      const relative = path.normalize(path.relative(sourceRoot, file))
      if (allowedDynamicHtmlFiles.has(relative)) return []
      const source = fs.readFileSync(file, 'utf8')
      return /v-html|\.innerHTML\s*=|dangerouslyUseHTMLString\s*:\s*true/.test(source) ? [relative] : []
    })

    expect(violations).toEqual([])
  })

  it('routes persisted diagnosis Markdown through SafeRichText', () => {
    const reportsView = fs.readFileSync(path.join(sourceRoot, 'views/diagnosis/Reports.vue'), 'utf8')

    expect(reportsView).toContain('<SafeRichText :markdown="currentReport.content" />')
    expect(reportsView).not.toContain('marked(')
  })

  it('keeps ECharts tooltip formatters out of HTML mode', () => {
    const violations = sourceFiles(sourceRoot).flatMap(file => {
      const relative = path.normalize(path.relative(sourceRoot, file))
      return fs.readFileSync(file, 'utf8').split(/\r?\n/).flatMap((line, index) =>
        line.includes('<br') ? [`${relative}:${index + 1}`] : []
      )
    })

    expect(violations).toEqual([])
  })

  it('does not expose development credentials unconditionally in production UI', () => {
    const loginView = fs.readFileSync(path.join(sourceRoot, 'views/login/index.vue'), 'utf8')

    expect(loginView).toContain('v-if="showDevelopmentCredentials"')
    expect(loginView).toContain('const showDevelopmentCredentials = import.meta.env.DEV')
  })

  it('keeps diagnosis WebSockets on the shared first-frame authentication path', () => {
    for (const relative of [
      'views/diagnosis/ProbabilityTuning.vue',
      'views/diagnosis/TimeWindowTuning.vue',
    ]) {
      const source = fs.readFileSync(path.join(sourceRoot, relative), 'utf8')

      expect(source).toContain("new WebSocketClient({")
      expect(source).toContain("url: '/ws/system'")
      expect(source).not.toMatch(/new WebSocket\(|[?&]token=/)
      expect(source).not.toContain('ws://localhost')
    }
  })
})
