import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import NodeToolbar from './NodeToolbar.vue'

describe('NodeToolbar', () => {
  it('adds nodes by click for mouse and keyboard users', async () => {
    const wrapper = mount(NodeToolbar, {
      global: {
        stubs: {
          ElButton: { template: '<button><slot /></button>' },
          ElIcon: { template: '<span><slot /></span>' },
          FullScreen: true
        }
      }
    })

    const buttons = wrapper.findAll('button.toolbar-item')
    expect(buttons).toHaveLength(3)

    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[2].trigger('click')

    expect(wrapper.emitted('add-node')).toEqual([['AND'], ['OR'], ['leaf']])
  })

  it('does not add a second node when a drag ends with a click', async () => {
    const wrapper = mount(NodeToolbar, {
      global: {
        stubs: {
          ElButton: { template: '<button><slot /></button>' },
          ElIcon: { template: '<span><slot /></span>' },
          FullScreen: true
        }
      }
    })
    const button = wrapper.find('button.toolbar-item')

    await button.trigger('dragstart')
    await button.trigger('dragend')
    await button.trigger('click')

    expect(wrapper.emitted('add-node')).toEqual([['AND']])
  })
})
