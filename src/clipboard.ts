export async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // Some browsers block the async API but still allow copying a selection.
    }
  }

  const activeElement = document.activeElement
  const selection = document.getSelection()
  const ranges = selection
    ? Array.from({ length: selection.rangeCount }, (_, index) => selection.getRangeAt(index).cloneRange())
    : []
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.readOnly = true
  textarea.tabIndex = -1
  textarea.style.cssText = 'position:fixed;top:0;left:-9999px;font-size:16px;'
  document.body.appendChild(textarea)

  try {
    textarea.focus({ preventScroll: true })
    textarea.select()
    textarea.setSelectionRange(0, text.length)
    if (!document.execCommand('copy')) throw new Error('Clipboard copy failed')
  } finally {
    textarea.remove()
    if (activeElement instanceof HTMLElement) activeElement.focus({ preventScroll: true })
    if (selection) {
      selection.removeAllRanges()
      ranges.forEach((range) => selection.addRange(range))
    }
  }
}
