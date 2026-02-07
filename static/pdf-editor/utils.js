/* pdf-editor/utils.js - Utility functions */
(function () {
  'use strict';
  window.PdfEditor = window.PdfEditor || {};
  window.PdfEditor.utils = {
    escapeHtml: function (s) {
      var div = document.createElement('div');
      div.textContent = s == null ? '' : String(s);
      return div.innerHTML;
    },
    parseColor: function (hex) {
      if (!hex || typeof hex !== 'string') return { r: 1, g: 1, b: 0 };
      var m = hex.match(/^#?([a-f0-9]{6})$/i) || hex.match(/^#?([a-f0-9]{3})$/i);
      if (!m) return { r: 1, g: 1, b: 0 };
      var s = m[1];
      if (s.length === 3) s = s[0] + s[0] + s[1] + s[1] + s[2] + s[2];
      return {
        r: parseInt(s.slice(0, 2), 16) / 255,
        g: parseInt(s.slice(2, 4), 16) / 255,
        b: parseInt(s.slice(4, 6), 16) / 255
      };
    },
    showTextModal: function (placeholder, title) {
      return new Promise(function (resolve) {
        var overlay = document.getElementById('text-modal-overlay');
        var titleEl = document.getElementById('text-modal-title');
        var input = document.getElementById('text-modal-input');
        var saveBtn = document.getElementById('text-modal-save');
        var cancelBtn = document.getElementById('text-modal-cancel');
        var focusable = [input, saveBtn, cancelBtn];
        var focusIndex = 0;
        function trapFocus(e) {
          if (e.key !== 'Tab') return;
          e.preventDefault();
          focusIndex = (focusIndex + (e.shiftKey ? -1 : 1) + focusable.length) % focusable.length;
          focusable[focusIndex].focus();
        }
        function close(result) {
          overlay.classList.remove('visible');
          overlay.setAttribute('aria-hidden', 'true');
          document.removeEventListener('keydown', handleKeydown);
          document.removeEventListener('keydown', trapFocus);
          resolve(result);
        }
        function handleKeydown(e) {
          if (e.key === 'Escape') { e.preventDefault(); close(null); }
          else if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); saveBtn.click(); }
        }
        titleEl.textContent = title || 'Add text';
        input.placeholder = placeholder || '';
        input.value = '';
        overlay.classList.add('visible');
        overlay.setAttribute('aria-hidden', 'false');
        input.focus();
        focusIndex = 0;
        document.addEventListener('keydown', handleKeydown);
        document.addEventListener('keydown', trapFocus);
        saveBtn.onclick = function () { close(input.value.trim()); };
        cancelBtn.onclick = function () { close(null); };
        overlay.onclick = function (e) { if (e.target === overlay) close(null); };
      });
    }
  };
})();
