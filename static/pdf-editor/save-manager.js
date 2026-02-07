/* pdf-editor/save-manager.js - Save markups and PDF flatten */
(function () {
  'use strict';
  var state = window.PdfEditor.state;
  var config = window.PdfEditor.config;
  var utils = window.PdfEditor.utils;

  function getMarkupsUrl() {
    var params = new URLSearchParams();
    if (state.currentLinkedType != null) params.set('linked_type', state.currentLinkedType);
    if (state.currentLinkedId != null) params.set('linked_id', state.currentLinkedId);
    var q = params.toString();
    return '/api/documents/' + config.docId + '/markups' + (q ? '?' + q : '');
  }

  function updateSaveIndicator() {
    var el = document.getElementById('save-indicator');
    if (!el) return;
    var s = state.saveStatus;
    el.className = 'save-indicator save-indicator--' + s;
    if (s === 'saving') {
      el.innerHTML = '<span class="save-indicator-dot"></span> Saving...';
    } else if (s === 'saved') {
      el.innerHTML = '<span class="save-indicator-check">✓</span> All changes saved';
    } else if (s === 'error') {
      var errTip = state.lastSaveError ? ' <span title="' + utils.escapeHtml(state.lastSaveError) + '">(' + utils.escapeHtml(state.lastSaveError.slice(0, 40)) + (state.lastSaveError.length > 40 ? '…' : '') + ')</span>' : '';
      el.innerHTML = 'Failed to save' + errTip + ' · <button type="button" class="save-retry">Retry</button>';
    } else {
      el.textContent = '';
    }
  }

  window.PdfEditor.saveManager = {
    getMarkupsUrl: getMarkupsUrl,
    updateSaveIndicator: updateSaveIndicator,
    scheduleSave: function () {
      state.dirty = true;
      if (state.saveTimeout) clearTimeout(state.saveTimeout);
      state.saveTimeout = setTimeout(function () { window.PdfEditor.saveManager.performSave(false); }, 500);
    },
    performSave: function (skipSavePdf) {
      if (!state.dirty && state.saveStatus !== 'error') return Promise.resolve(true);
      state.saveStatus = 'saving';
      updateSaveIndicator();
      return fetch('/api/documents/' + config.docId + '/markups', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          linked_type: state.currentLinkedType,
          linked_id: state.currentLinkedId,
          markups: state.markups
        })
      }).then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () { return {}; }).then(function (errBody) {
            var msg = errBody.detail || res.statusText;
            throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
          });
        }
        state.dirty = false;
        state.saveStatus = 'saved';
        updateSaveIndicator();
        if (!skipSavePdf) {
          window.PdfEditor.saveManager.performSavePdf().catch(function (e) { console.error('PDF could not be saved', e); });
        }
        return true;
      }).catch(function (e) {
        console.error('Failed to save markups', e);
        state.lastSaveError = e && e.message ? e.message : String(e);
        state.saveStatus = 'error';
        updateSaveIndicator();
        return false;
      });
    },
    performSavePdf: function () {
      var btn = document.getElementById('btn-save-pdf');
      if (btn) btn.disabled = true;
      var self = this;
      var saveIndicatorEl = document.getElementById('save-indicator');
      return (state.dirty || state.saveStatus === 'error' ? self.performSave(true) : Promise.resolve(true)).then(function (saved) {
        if (!saved) throw new Error(state.lastSaveError || 'Markups could not be saved.');
        return fetch('/api/documents/' + config.docId + '/save-pdf', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            linked_type: state.currentLinkedType,
            linked_id: state.currentLinkedId
          })
        });
      }).then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () { return {}; }).then(function (errBody) {
            var msg = errBody.detail || res.statusText || 'Save failed';
            throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
          });
        }
        if (saveIndicatorEl && btn) {
          saveIndicatorEl.className = 'save-indicator save-indicator--saved';
          saveIndicatorEl.innerHTML = '<span class="save-indicator-check">✓</span> PDF saved';
          setTimeout(updateSaveIndicator, 2500);
        }
        return res.json();
      }).catch(function (e) {
        console.error('Failed to save PDF', e);
        state.lastSaveError = e && e.message ? e.message : String(e);
        if (saveIndicatorEl && btn) {
          saveIndicatorEl.className = 'save-indicator save-indicator--error';
          saveIndicatorEl.textContent = 'Failed to save PDF';
          setTimeout(updateSaveIndicator, 3000);
        }
        throw e;
      }).finally(function () {
        if (btn) btn.disabled = false;
      });
    }
  };
})();
