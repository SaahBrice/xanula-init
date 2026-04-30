import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Underline from '@tiptap/extension-underline'

window.initTiptapEditor = function(element, content) {
    // Ensure content is valid: must be a TipTap JSON doc or HTML string or null
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
            Underline,
            Placeholder.configure({
                placeholder: 'Start writing your book...',
                showOnlyCurrent: false,
                emptyEditorClass: 'is-editor-empty',
                emptyNodeClass: 'is-empty',
            }),
        ],
        content: safeContent,
        autofocus: false,
    })

    return editor
}
