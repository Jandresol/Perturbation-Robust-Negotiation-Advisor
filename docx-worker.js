/* Extract plain text only: document HTML and embedded scripts are never rendered. */
importScripts('vendor/mammoth/mammoth.browser.js');
self.onmessage = async event => {
  try {
    const result = await mammoth.extractRawText({ arrayBuffer: event.data });
    const text = result.value.trim();
    if (!text) throw new Error('No readable text found. Image-only Word documents need OCR.');
    if (text.length > 2_000_000) throw new Error('Extracted text exceeds 2 million characters. Split this document.');
    // DOCX pagination depends on the Word renderer. Use explicit text sections instead.
    const sections = []; let chunk = '';
    for (const paragraph of text.split(/(?<=\n\n)(?=[^\n])/)) {
      if (chunk && chunk.length + paragraph.length > 4000) { sections.push({ number: sections.length + 1, text: chunk.trim() }); chunk = ''; }
      chunk += paragraph;
    }
    if (chunk) sections.push({ number: sections.length + 1, text: chunk.trim() });
    self.postMessage({ ok: true, result: { text, sections, pages: [], emptyPages: [], format: 'docx', warnings: result.messages.map(x => x.message) } });
  } catch (error) { self.postMessage({ ok: false, error: error.message }); }
};
