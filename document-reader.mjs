export async function readDocument(file, options = {}) {
  if (options.signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
  const extension = file.name.split('.').pop().toLowerCase();
  if (extension === 'pdf') {
    const { readPdf } = await import('./pdf-reader.mjs');
    return { ...await readPdf(file, options), format: 'pdf', sections: [] };
  }
  if (extension !== 'docx') throw new Error('Choose a PDF or DOCX file. Legacy .doc files must be saved as .docx.');
  const data = await file.arrayBuffer();
  if (options.signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
  const worker = new Worker(new URL('./docx-worker.js', import.meta.url));
  return new Promise((resolve, reject) => {
    let timer;
    const finish = (error, result) => { clearTimeout(timer); worker.terminate(); options.signal?.removeEventListener('abort', abort); error ? reject(error) : resolve(result); };
    const abort = () => finish(new DOMException('Cancelled', 'AbortError'));
    options.signal?.addEventListener('abort', abort, { once: true });
    timer = setTimeout(() => finish(new Error('Word extraction exceeded 30 seconds. Split or repair this document.')), 30000);
    worker.onmessage = e => e.data.ok ? finish(null, e.data.result) : finish(new Error(`Could not extract DOCX text: ${e.data.error}`));
    worker.onerror = () => finish(new Error('The Word reader could not load. Reload the app and try again.'));
    worker.postMessage(data, [data]);
  });
}
