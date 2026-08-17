import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SafeRichText from './SafeRichText.vue'


describe('SafeRichText', () => {
  it.each([
    '<ScRiPt>window.__xss = true</ScRiPt>',
    '<img src=x oNeRrOr="window.__xss = true">',
    '<svg><a xlink:href="javascript:alert(1)">x</a></svg>',
    '<math><mtext><img src=x onerror=alert(1)></mtext></math>',
    '[entity](java&#x73;cript:alert(1))',
    '[control](java\u0000script:alert(1))',
    '[data](DaTa:text/html,%3Cscript%3Ealert(1)%3C/script%3E)',
    '&lt;img src=x onerror=alert(1)&gt;'
  ])('blocks persisted Markdown payload %s', markdown => {
    const wrapper = mount(SafeRichText, { props: { markdown } })

    expect(wrapper.find('script, img, svg, math').exists()).toBe(false)
    const root = wrapper.element as HTMLElement
    const attributes = Array.from(root.querySelectorAll('*')).flatMap(element =>
      Array.from(element.attributes).map(attribute => [attribute.name, attribute.value])
    )
    expect(attributes.some(([name]) => name.toLowerCase().startsWith('on'))).toBe(false)
    expect(attributes.some(([name, value]) =>
      ['href', 'src'].includes(name.toLowerCase()) && /^(?:javascript|data):/i.test(value)
    )).toBe(false)
    expect((globalThis as typeof globalThis & { __xss?: boolean }).__xss).not.toBe(true)
  })

  it('preserves readable report formatting and hardens external links', () => {
    const wrapper = mount(SafeRichText, {
      props: {
        markdown: '# 标题\n\n- 项目\n\n|列|值|\n|-|-|\n|A|1|\n\n[文档](https://example.com/docs)'
      }
    })

    expect(wrapper.find('h1').text()).toBe('标题')
    expect(wrapper.find('ul').exists()).toBe(true)
    expect(wrapper.find('table').exists()).toBe(true)
    expect(wrapper.find('a').attributes()).toMatchObject({
      href: 'https://example.com/docs',
      target: '_blank',
      rel: 'noopener noreferrer'
    })
  })
})
