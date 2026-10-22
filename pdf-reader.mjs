import { getDocument, GlobalWorkerOptions } from './vendor/pdfjs/pdf.mjs';
GlobalWorkerOptions.workerSrc = new URL('./vendor/pdfjs/pdf.worker.mjs', import.meta.url).href;
export async function readPdf(file, { signal, onProgress = () => {} } = {}) {
  if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
  const data = new Uint8Array(await file.arrayBuffer());
  const task = getDocument({ data, isEvalSupported: false, cMapUrl: new URL('./vendor/pdfjs/cmaps/', import.meta.url).href, cMapPacked: true, standardFontDataUrl: new URL('./vendor/pdfjs/standard_fonts/', import.meta.url).href });
  const abort = () => { void task.destroy(); };
  signal?.addEventListener('abort', abort, { once: true });
  // Do not leave password-protected files waiting for interactive input.
  task.onPassword = () => { void task.destroy(); };
  try {
    const pdf = await task.promise;
    if (pdf.numPages > 500) throw new Error('More than 500 pages. Split this document into smaller PDFs.');
    const pages = []; let length = 0;
    for (let n = 1; n <= pdf.numPages; n++) {
      if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
      const page = await pdf.getPage(n);
      const content = await page.getTextContent();
      let text = '';
      for (const item of content.items) if ('str' in item) text += item.str + (item.hasEOL ? '\n' : ' ');
      text = text.replace(/[ \t]+\n/g, '\n').trim();
      length += text.length;
      if (length > 2_000_000) throw new Error('Extracted text exceeds 2 million characters. Split this PDF.');
      pages.push({ number: n, text }); page.cleanup(); onProgress(n, pdf.numPages);
    }
    const text = pages.map(p => p.text).filter(Boolean).join('\n\n');
    if (!text) throw new Error('No readable text found. This PDF may be scanned; run OCR and upload it again.');
    return { text, pages, emptyPages: pages.filter(p => !p.text).map(p => p.number) };
  } catch (error) {
    if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
    if (/password|loading aborted|worker was destroyed/i.test(error.message)) throw new Error('This PDF may require a password. Upload an unlocked copy.');
    throw error;
  } finally { signal?.removeEventListener('abort', abort); await task.destroy(); }
}
