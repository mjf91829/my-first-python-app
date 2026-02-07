/* pdf-editor/undo-manager.js - Undo/redo stack */
(function () {
  'use strict';
  var state = window.PdfEditor.state;
  window.PdfEditor.undoManager = {
    pushUndo: function () {
      if (state.isUndoRedo) return;
      state.undoStack.push(JSON.parse(JSON.stringify(state.markups)));
      state.redoStack.length = 0;
      window.PdfEditor.main.updateUndoRedoButtons();
    },
    undo: function () {
      if (state.undoStack.length === 0) return;
      state.isUndoRedo = true;
      state.redoStack.push(JSON.parse(JSON.stringify(state.markups)));
      state.markups = state.undoStack.pop();
      state.isUndoRedo = false;
      window.PdfEditor.annotationLayer.renderMarkups();
      window.PdfEditor.saveManager.scheduleSave();
      window.PdfEditor.main.updateUndoRedoButtons();
    },
    redo: function () {
      if (state.redoStack.length === 0) return;
      state.isUndoRedo = true;
      state.undoStack.push(JSON.parse(JSON.stringify(state.markups)));
      state.markups = state.redoStack.pop();
      state.isUndoRedo = false;
      window.PdfEditor.annotationLayer.renderMarkups();
      window.PdfEditor.saveManager.scheduleSave();
      window.PdfEditor.main.updateUndoRedoButtons();
    }
  };
})();
