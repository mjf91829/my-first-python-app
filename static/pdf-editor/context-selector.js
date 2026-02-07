/* pdf-editor/context-selector.js - Linked context and markups loading */
(function () {
  'use strict';
  var state = window.PdfEditor.state;
  var config = window.PdfEditor.config;

  window.PdfEditor.contextSelector = {
    getMarkupsUrl: function () {
      var params = new URLSearchParams();
      if (state.currentLinkedType != null) params.set('linked_type', state.currentLinkedType);
      if (state.currentLinkedId != null) params.set('linked_id', state.currentLinkedId);
      var q = params.toString();
      return '/api/documents/' + config.docId + '/markups' + (q ? '?' + q : '');
    },
    getDownloadWithMarkupsUrl: function () {
      var params = new URLSearchParams();
      if (state.currentLinkedType != null) params.set('linked_type', state.currentLinkedType);
      if (state.currentLinkedId != null) params.set('linked_id', state.currentLinkedId);
      var q = params.toString();
      return '/api/documents/' + config.docId + '/file/with-markups' + (q ? '?' + q : '');
    },
    loadMarkups: function () {
      var self = this;
      return fetch(self.getMarkupsUrl()).then(function (res) { return res.json(); }).then(function (data) {
        state.markups = Array.isArray(data.markups) ? data.markups : [];
        window.PdfEditor.annotationLayer.renderMarkups();
      }).catch(function () {
        state.markups = [];
        window.PdfEditor.annotationLayer.renderMarkups();
      });
    },
    loadLinkedOptions: function () {
      var contextSelect = document.getElementById('context-select');
      var contextWrap = document.getElementById('context-wrap');
      return fetch('/api/documents/' + config.docId).then(function (res) { return res.json(); }).then(function (data) {
        state.linkedOptions = (data.linked || []).map(function (l) {
          return { linked_type: l.linked_type, linked_id: l.linked_id, title: l.title || l.linked_type + ' ' + l.linked_id };
        });
      }).catch(function () {
        state.linkedOptions = [];
      }).then(function () {
        contextSelect.innerHTML = '';
        contextSelect.appendChild(new Option('Document (no context)', '', true));
        state.linkedOptions.forEach(function (opt) {
          var o = new Option(opt.title, JSON.stringify({ t: opt.linked_type, i: opt.linked_id }));
          contextSelect.appendChild(o);
        });
        var hasContext = state.currentLinkedType != null && state.currentLinkedId != null;
        if (hasContext) {
          var val = JSON.stringify({ t: state.currentLinkedType, i: state.currentLinkedId });
          var found = Array.from(contextSelect.options).some(function (o) { return o.value === val; });
          if (found) {
            contextSelect.value = val;
          } else {
            state.currentLinkedType = null;
            state.currentLinkedId = null;
            contextSelect.value = '';
          }
        }
        contextSelect.onchange = function () {
          var v = contextSelect.value;
          if (!v) {
            state.currentLinkedType = null;
            state.currentLinkedId = null;
          } else {
            var parsed = JSON.parse(v);
            state.currentLinkedType = parsed.t;
            state.currentLinkedId = parsed.i;
          }
          state.undoStack.length = 0;
          state.redoStack.length = 0;
          window.PdfEditor.contextSelector.loadMarkups();
          document.getElementById('btn-download-with-markups').href = window.PdfEditor.contextSelector.getDownloadWithMarkupsUrl();
        };
        if (state.linkedOptions.length === 0) contextWrap.style.display = 'none';
      });
    }
  };
})();
