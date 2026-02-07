/* pdf-editor/main.js - Orchestrates init, toolbar, event handlers */
(function () {
  'use strict';
  var state = window.PdfEditor.state;
  var config = window.PdfEditor.config;

  function updateZoomDisplay() {
    var el = document.getElementById('zoom-value');
    if (el) el.textContent = Math.round(state.scale * 100) + '%';
  }

  function updateUndoRedoButtons() {
    var undoBtn = document.getElementById('btn-undo');
    var redoBtn = document.getElementById('btn-redo');
    if (undoBtn) undoBtn.disabled = state.undoStack.length === 0;
    if (redoBtn) redoBtn.disabled = state.redoStack.length === 0;
  }

  function updateToolbarForMode() {
    var editBtn = document.getElementById('btn-edit');
    var doneBtn = document.getElementById('btn-done');
    var editModeOnly = document.getElementById('edit-mode-only');
    if (state.isEditMode) {
      if (editBtn) editBtn.style.display = 'none';
      if (editModeOnly) editModeOnly.style.display = 'inline-flex';
      if (doneBtn) doneBtn.style.display = '';
    } else {
      if (editBtn) editBtn.style.display = '';
      if (editModeOnly) editModeOnly.style.display = 'none';
      if (doneBtn) doneBtn.style.display = 'none';
    }
    var downloadWithMarkups = document.getElementById('btn-download-with-markups');
    if (downloadWithMarkups) downloadWithMarkups.href = window.PdfEditor.contextSelector.getDownloadWithMarkupsUrl();
    document.querySelectorAll('.page-annotations').forEach(function (el) {
      el.classList.toggle('interactive', state.isEditMode && state.mode !== 'none');
    });
    window.PdfEditor.saveManager.updateSaveIndicator();
    updateUndoRedoButtons();
  }

  function setMode(m) {
    state.mode = m;
    var btnNone = document.getElementById('btn-mode-none');
    var btnHighlight = document.getElementById('btn-mode-highlight');
    var btnDraw = document.getElementById('btn-mode-draw');
    var btnText = document.getElementById('btn-mode-text');
    var btnComment = document.getElementById('btn-mode-comment');
    if (btnNone) btnNone.classList.toggle('active', state.mode === 'none');
    if (btnHighlight) btnHighlight.classList.toggle('active', state.mode === 'highlight');
    if (btnDraw) btnDraw.classList.toggle('active', state.mode === 'draw');
    if (btnText) btnText.classList.toggle('active', state.mode === 'text');
    if (btnComment) btnComment.classList.toggle('active', state.mode === 'comment');
    document.querySelectorAll('.page-annotations').forEach(function (el) {
      el.classList.toggle('interactive', state.isEditMode && state.mode !== 'none');
    });
    if (state.previewEl) { state.previewEl.remove(); state.previewEl = null; }
    if (state.inkStrokeEl) { state.inkStrokeEl.remove(); state.inkStrokeEl = null; }
    state.inkPoints = [];
  }

  async function handleSavePdfClick() {
    var btn = document.getElementById('btn-save-pdf');
    if (!btn || btn.disabled) return;
    var originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Saving...';
    try {
      if (state.dirty || state.saveStatus === 'error') {
        var saved = await window.PdfEditor.saveManager.performSave(true);
        if (!saved) throw new Error(state.lastSaveError || 'Markups could not be saved.');
      }
      await window.PdfEditor.saveManager.performSavePdf();
    } catch (e) { /* already updated */ }
    finally {
      btn.disabled = false;
      btn.textContent = originalText;
    }
  }

  function init() {
    if (typeof pdfjsLib !== 'undefined') {
      pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/pdf.worker.min.js';
    }
    updateToolbarForMode();
    updateZoomDisplay();

    document.getElementById('btn-zoom-in').addEventListener('click', function () { window.PdfEditor.pdfViewer.zoomIn(); });
    document.getElementById('btn-zoom-out').addEventListener('click', function () { window.PdfEditor.pdfViewer.zoomOut(); });
    document.getElementById('btn-print').addEventListener('click', function () { window.print(); });
    document.getElementById('btn-save-pdf').addEventListener('click', handleSavePdfClick);

    document.querySelector('.back-link').addEventListener('click', async function (e) {
      e.preventDefault();
      if (state.dirty || state.saveStatus === 'error') {
        try {
          await window.PdfEditor.saveManager.performSave(false);
          state.dirty = false;
          state.saveStatus = 'saved';
          window.PdfEditor.saveManager.updateSaveIndicator();
        } catch (err) {
          window.PdfEditor.saveManager.updateSaveIndicator();
          return;
        }
      }
      while (state.saveStatus === 'saving') {
        await new Promise(function (r) { setTimeout(r, 100); });
      }
      window.location.href = '/';
    });

    document.getElementById('btn-edit').addEventListener('click', function () {
      state.isEditMode = true;
      updateToolbarForMode();
      setMode('none');
    });
    document.getElementById('btn-done').addEventListener('click', function () {
      state.isEditMode = false;
      setMode('none');
      updateToolbarForMode();
    });
    document.getElementById('btn-mode-none').addEventListener('click', function () { setMode('none'); });
    document.getElementById('btn-mode-highlight').addEventListener('click', function () { setMode('highlight'); });
    document.getElementById('btn-mode-draw').addEventListener('click', function () { setMode('draw'); });
    document.getElementById('btn-mode-text').addEventListener('click', function () { setMode('text'); });
    document.getElementById('btn-mode-comment').addEventListener('click', function () { setMode('comment'); });
    var colorPicker = document.getElementById('highlight-color-picker');
    if (colorPicker) {
      colorPicker.querySelectorAll('.color-swatch').forEach(function (sw) {
        sw.style.background = sw.dataset.color;
        if (sw.dataset.color === (state.highlightColor || '#ffeb3b')) sw.classList.add('active');
        sw.addEventListener('click', function () {
          colorPicker.querySelectorAll('.color-swatch').forEach(function (s) { s.classList.remove('active'); });
          sw.classList.add('active');
          state.highlightColor = sw.dataset.color;
        });
      });
    }
    document.getElementById('btn-undo').addEventListener('click', function () { window.PdfEditor.undoManager.undo(); });
    document.getElementById('btn-redo').addEventListener('click', function () { window.PdfEditor.undoManager.redo(); });

    document.addEventListener('keydown', function (e) {
      if (!state.isEditMode) return;
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        if (e.shiftKey) window.PdfEditor.undoManager.redo();
        else window.PdfEditor.undoManager.undo();
      }
    });

    document.getElementById('save-indicator').addEventListener('click', function (e) {
      if (e.target && e.target.classList && e.target.classList.contains('save-retry')) {
        e.preventDefault();
        window.PdfEditor.saveManager.performSave(false);
      }
    });

    var historyBtn = document.getElementById('btn-history');
    var historyPopover = document.getElementById('history-popover');
    var historyList = document.getElementById('history-list');
    var historyEmpty = document.getElementById('history-empty');
    if (historyBtn && historyPopover) {
      historyBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var visible = historyPopover.getAttribute('aria-hidden') !== 'true';
        if (visible) {
          historyPopover.setAttribute('aria-hidden', 'true');
          historyPopover.classList.remove('open');
          return;
        }
        var params = new URLSearchParams();
        if (state.currentLinkedType != null) params.set('linked_type', state.currentLinkedType);
        if (state.currentLinkedId != null) params.set('linked_id', state.currentLinkedId);
        fetch('/api/documents/' + config.docId + '/markups/history' + (params.toString() ? '?' + params : '')).then(function (r) { return r.json(); }).then(function (data) {
          historyList.innerHTML = '';
          historyEmpty.style.display = 'none';
          var items = data.history || [];
          if (items.length === 0) {
            historyEmpty.style.display = 'block';
          } else {
            items.forEach(function (h) {
              var li = document.createElement('li');
              li.className = 'history-item';
              var label = document.createElement('span');
              label.textContent = 'v' + h.version + ' - ' + (h.created_at ? new Date(h.created_at).toLocaleString() : '');
              var restoreBtn = document.createElement('button');
              restoreBtn.type = 'button';
              restoreBtn.className = 'history-restore';
              restoreBtn.textContent = 'Restore';
              restoreBtn.dataset.version = h.version;
              restoreBtn.addEventListener('click', function () {
                var q = new URLSearchParams();
                q.set('version', this.dataset.version);
                if (state.currentLinkedType != null) q.set('linked_type', state.currentLinkedType);
                if (state.currentLinkedId != null) q.set('linked_id', state.currentLinkedId);
                fetch('/api/documents/' + config.docId + '/markups/restore?' + q, { method: 'POST' }).then(function (res) {
                  if (!res.ok) return;
                  historyPopover.setAttribute('aria-hidden', 'true');
                  historyPopover.classList.remove('open');
                  window.PdfEditor.contextSelector.loadMarkups();
                });
              });
              li.appendChild(label);
              li.appendChild(restoreBtn);
              historyList.appendChild(li);
            });
          }
        }).catch(function () {
          historyList.innerHTML = '';
          historyEmpty.style.display = 'block';
          historyEmpty.textContent = 'Could not load history.';
        });
        var rect = historyBtn.getBoundingClientRect();
        historyPopover.style.position = 'fixed';
        historyPopover.style.left = rect.left + 'px';
        historyPopover.style.top = (rect.bottom + 4) + 'px';
        historyPopover.setAttribute('aria-hidden', 'false');
        historyPopover.classList.add('open');
      });
      document.addEventListener('click', function (e) {
        if (!historyPopover.classList.contains('open')) return;
        if (historyPopover.contains(e.target) || historyBtn.contains(e.target)) return;
        historyPopover.setAttribute('aria-hidden', 'true');
        historyPopover.classList.remove('open');
      });
    }

    window.addEventListener('beforeunload', function (e) {
      if (state.dirty || state.saveStatus === 'saving' || state.saveStatus === 'error') {
        if (state.dirty) {
          try {
            fetch('/api/documents/' + config.docId + '/markups', {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                linked_type: state.currentLinkedType,
                linked_id: state.currentLinkedId,
                markups: state.markups
              }),
              keepalive: true
            });
          } catch (err) { /* ignore */ }
        }
        e.preventDefault();
      }
    });

    window.PdfEditor.pdfViewer.whenPdfJsReady().then(function () {
      if (typeof pdfjsLib !== 'undefined') window.PdfEditor.pdfViewer.loadPdf();
      else window.PdfEditor.pdfViewer.showIframeFallback();
    }).catch(function () { window.PdfEditor.pdfViewer.showIframeFallback(); });
  }

  window.PdfEditor.main = {
    init: init,
    updateZoomDisplay: updateZoomDisplay,
    updateUndoRedoButtons: updateUndoRedoButtons,
    updateToolbarForMode: updateToolbarForMode,
    setMode: setMode
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
