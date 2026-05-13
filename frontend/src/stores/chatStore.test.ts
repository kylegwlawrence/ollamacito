import { describe, expect, it, beforeEach } from 'vitest'
import { useChatStore } from './chatStore'

describe('chatStore', () => {
  beforeEach(() => {
    useChatStore.setState({
      currentChat: null,
      messages: [],
      selectedFileIds: [],
    })
  })

  it('setSelectedFileIds replaces the list', () => {
    useChatStore.getState().setSelectedFileIds(['a', 'b'])
    expect(useChatStore.getState().selectedFileIds).toEqual(['a', 'b'])
    useChatStore.getState().setSelectedFileIds([])
    expect(useChatStore.getState().selectedFileIds).toEqual([])
  })

  it('toggleFileId adds, then removes', () => {
    useChatStore.getState().toggleFileId('a')
    expect(useChatStore.getState().selectedFileIds).toEqual(['a'])
    useChatStore.getState().toggleFileId('b')
    expect(useChatStore.getState().selectedFileIds).toEqual(['a', 'b'])
    useChatStore.getState().toggleFileId('a')
    expect(useChatStore.getState().selectedFileIds).toEqual(['b'])
  })

  it('toggleFileId does not duplicate an existing id', () => {
    useChatStore.getState().setSelectedFileIds(['x'])
    useChatStore.getState().toggleFileId('x')
    expect(useChatStore.getState().selectedFileIds).toEqual([])
  })
})
