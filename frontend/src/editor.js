import { Editor, Extension } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { TextAlign } from '@tiptap/extension-text-align'
import { Image } from '@tiptap/extension-image'
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { Decoration, DecorationSet } from '@tiptap/pm/view'

const ghostSuggestionKey = new PluginKey('xanulaGhostSuggestion')
const promptSelectionKey = new PluginKey('xanulaPromptSelection')

function createGhostNode(suggestion) {
    const wrapper = document.createElement('div')
    wrapper.className = 'ai-ghost-suggestion'
    wrapper.setAttribute('contenteditable', 'false')

    const label = document.createElement('div')
    label.className = 'ai-ghost-label'
    label.textContent = 'Reepls suggestion'
    wrapper.appendChild(label)

    if (suggestion?.view === 'changes' && Array.isArray(suggestion.diff) && suggestion.diff.length) {
        const diff = document.createElement('div')
        diff.className = 'ai-ghost-diff'
        suggestion.diff.forEach(part => {
            const span = document.createElement('span')
            span.className = part.type || 'same'
            span.textContent = part.text || ''
            diff.appendChild(span)
        })
        wrapper.appendChild(diff)
        return wrapper
    }

    String(suggestion?.text || '')
        .split(/\n{2,}/)
        .map(block => block.trim())
        .filter(Boolean)
        .forEach(block => {
            const paragraph = document.createElement('p')
            paragraph.textContent = block.replace(/\n/g, ' ')
            wrapper.appendChild(paragraph)
        })

    return wrapper
}

const GhostSuggestion = Extension.create({
    name: 'ghostSuggestion',

    addProseMirrorPlugins() {
        return [
            new Plugin({
                key: ghostSuggestionKey,
                state: {
                    init: () => null,
                    apply(transaction, previous) {
                        const meta = transaction.getMeta(ghostSuggestionKey)
                        if (meta?.type === 'show') return meta.suggestion
                        if (meta?.type === 'clear') return null
                        if (!previous) return null

                        const from = transaction.mapping.map(previous.range.from)
                        const to = transaction.mapping.map(previous.range.to)
                        return { ...previous, range: { from, to } }
                    },
                },
                props: {
                    decorations(state) {
                        const suggestion = ghostSuggestionKey.getState(state)
                        if (!suggestion) return DecorationSet.empty

                        const decorations = []
                        const { from, to } = suggestion.range
                        const isReplacement = to > from
                        const widgetPosition = isReplacement ? from : to
                        if (to > from) {
                            decorations.push(Decoration.inline(from, to, { class: 'ai-ghost-original' }))
                        }
                        decorations.push(
                            Decoration.widget(widgetPosition || from, () => createGhostNode(suggestion), {
                                key: `ghost-${suggestion.id}-${suggestion.view || 'clean'}`,
                                side: isReplacement ? -1 : 1,
                            }),
                        )
                        return DecorationSet.create(state.doc, decorations)
                    },
                },
            }),
        ]
    },
})

const PromptSelectionMemory = Extension.create({
    name: 'promptSelectionMemory',

    addProseMirrorPlugins() {
        return [
            new Plugin({
                key: promptSelectionKey,
                state: {
                    init: () => null,
                    apply(transaction, previous) {
                        const meta = transaction.getMeta(promptSelectionKey)
                        if (meta?.type === 'show') return meta.selection
                        if (meta?.type === 'clear') return null
                        if (!previous) return null

                        const from = transaction.mapping.map(previous.from)
                        const to = transaction.mapping.map(previous.to)
                        if (to <= from) return null
                        return { from, to }
                    },
                },
                props: {
                    decorations(state) {
                        const selection = promptSelectionKey.getState(state)
                        if (!selection || selection.to <= selection.from) return DecorationSet.empty
                        return DecorationSet.create(state.doc, [
                            Decoration.inline(selection.from, selection.to, { class: 'ai-prompt-selection' }),
                        ])
                    },
                },
            }),
        ]
    },
})

window.xanulaGhostSuggestion = {
    get(editor) {
        return editor ? ghostSuggestionKey.getState(editor.state) : null
    },
    show(editor, suggestion) {
        if (!editor || !suggestion) return
        editor.view.dispatch(editor.state.tr.setMeta(ghostSuggestionKey, {
            type: 'show',
            suggestion,
        }))
        editor.setEditable(false, false)
    },
    clear(editor) {
        if (!editor) return
        editor.view.dispatch(editor.state.tr.setMeta(ghostSuggestionKey, { type: 'clear' }))
        editor.setEditable(true, false)
    },
    confirm(editor, content) {
        const suggestion = this.get(editor)
        if (!editor || !suggestion) return false
        editor.setEditable(true, false)
        editor.view.dispatch(editor.state.tr.setMeta(ghostSuggestionKey, { type: 'clear' }))
        editor.commands.insertContentAt(suggestion.range, content)
        return true
    },
}

window.xanulaPromptSelection = {
    show(editor, selection) {
        if (!editor || !selection || selection.to <= selection.from) return
        editor.view.dispatch(editor.state.tr.setMeta(promptSelectionKey, {
            type: 'show',
            selection,
        }))
    },
    clear(editor) {
        if (!editor) return
        editor.view.dispatch(editor.state.tr.setMeta(promptSelectionKey, { type: 'clear' }))
    },
}

window.initTiptapEditor = function(element, content) {
    let safeContent = ''
    if (content && typeof content === 'object' && content.type === 'doc') {
        safeContent = content
    } else if (typeof content === 'string' && content.length > 0) {
        safeContent = content
    }

    const editor = new Editor({
        element: element,
        extensions: [
            StarterKit.configure({
                heading: { levels: [1, 2, 3] },
            }),
            Placeholder.configure({
                placeholder: 'Start writing your book...',
                showOnlyCurrent: false,
                emptyEditorClass: 'is-editor-empty',
                emptyNodeClass: 'is-empty',
            }),
            TextAlign.configure({
                types: ['heading', 'paragraph'],
            }),
            Image.configure({
                inline: false,
                allowBase64: true,
            }),
            Table.configure({
                resizable: true,
            }),
            TableRow,
            TableCell,
            TableHeader,
            GhostSuggestion,
            PromptSelectionMemory,
        ],
        content: safeContent,
        autofocus: false,
    })

    return editor
}
