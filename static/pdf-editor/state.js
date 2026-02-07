/* pdf-editor/state.js - Shared state for PDF editor */
(function () {
  'use strict';
  var config = window.__PDF_CONFIG__ || { docId: 0, linkedType: null, linkedId: null };
  window.PdfEditor = window.PdfEditor || {};
  window.PdfEditor.config = config;
  window.PdfEditor.state = {
    pdfDoc: null,
    scale: 1,
    markups: [],
    linkedOptions: [],
    currentLinkedType: config.linkedType,
    currentLinkedId: config.linkedId,
    mode: 'none',
    highlightColor: '#ffeb3b',
    dragStart: null,
    previewEl: null,
    inkPoints: [],
    inkStrokeEl: null,
    isEditMode: false,
    undoStack: [],
    redoStack: [],
    saveStatus: 'idle',
    lastSaveError: '',
    dirty: false,
    saveTimeout: null,
    isUndoRedo: false
  };
})();
