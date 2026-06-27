import { describe, expect, it } from 'vitest'
import { normalizeSpatialTreeResponse } from '@/api/modules/spatial'

const tree = [
  {
    id: 1,
    site_code: 'SZ-DC-01',
    site_name: '深圳算力中心',
    floors: [],
  },
]

describe('spatial api helpers', () => {
  it('accepts direct array responses from spatial tree endpoint', () => {
    expect(normalizeSpatialTreeResponse(tree)).toEqual(tree)
  })

  it('accepts wrapped ResponseModel-style spatial tree responses', () => {
    expect(normalizeSpatialTreeResponse({ code: 0, message: 'ok', data: tree })).toEqual(tree)
  })

  it('falls back to an empty tree for unexpected responses', () => {
    expect(normalizeSpatialTreeResponse({ data: null })).toEqual([])
  })
})
