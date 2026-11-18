/* Keep startup failures recoverable without deleting the saved workspace. */
(() => {
  function recover(event) {
    if (window.workspaceStarted) return;
    const app = document.getElementById('app');
    app.replaceChildren();
    const panel = document.createElement('main');
    panel.style.cssText = 'padding:48px;max-width:640px;margin:40px auto';
    const title = document.createElement('h1');
    title.textContent = 'Your workspace could not open';
    const description = document.createElement('p');
    description.textContent = 'Your saved workspace has not been removed. Reload to get the latest app files, or download a backup before troubleshooting.';
    const detail = document.createElement('p');
    detail.textContent = event.message || 'An app file could not load.';
    const reload = document.createElement('button');
    reload.textContent = 'Reload app';
    reload.onclick = () => location.reload();
    const backup = document.createElement('button');
    backup.textContent = 'Download saved workspace';
    backup.style.margin = '12px';
    backup.onclick = () => {
      const saved = localStorage.getItem('negotiation-workspace-v1');
      if (!saved) { detail.textContent = 'No saved workspace was found in this browser.'; return; }
      const url = URL.createObjectURL(new Blob([saved], {type:'application/json'}));
      const link = document.createElement('a');
      link.href = url; link.download = 'negotiation-workspace-backup.json'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    panel.append(title, description, detail, reload, backup);
    app.append(panel);
  }
  window.addEventListener('error', recover, true);
})();
