/* pdf-editor/undo-manager.js - Undo/redo stack */
(function () {
  'use strict';
  var state = window.PdfEditor.state;
  window.PdfEditor.undoManager = {
    pushUndo: function () {
      if (state.isUndoRedo) return;
      var snapshot = window.PdfEditor.fabricLayer
        ? window.PdfEditor.fabricLayer.serializeAllFabricToMarkups()
        : state.markups;
      state.undoStack.push(JSON.parse(JSON.stringify(snapshot)));
      state.redoStack.length = 0;
      window.PdfEditor.main.updateUndoRedoButtons();
    },
    undo: function () {
      if (state.undoStack.length === 0) return;
      state.isUndoRedo = true;
      var current = window.PdfEditor.fabricLayer
        ? window.PdfEditor.fabricLayer.serializeAllFabricToMarkups()
        : state.markups;
      state.redoStack.push(JSON.parse(JSON.stringify(current)));
      state.markups = state.undoStack.pop();
      state.isUndoRedo = false;
      if (window.PdfEditor.fabricLayer) {
        window.PdfEditor.fabricLayer.loadMarkupsIntoFabric(state.markups);
      } else {
        window.PdfEditor.annotationLayer.renderMarkups();
      }
      window.PdfEditor.saveManager.scheduleSave();
      window.PdfEditor.main.updateUndoRedoButtons();
    },
    redo: function () {
      if (state.redoStack.length === 0) return;
      state.isUndoRedo = true;
      var current = window.PdfEditor.fabricLayer
        ? window.PdfEditor.fabricLayer.serializeAllFabricToMarkups()
        : state.markups;
      state.undoStack.push(JSON.parse(JSON.stringify(current)));
      state.markups = state.redoStack.pop();
      state.isUndoRedo = false;
      if (window.PdfEditor.fabricLayer) {
        window.PdfEditor.fabricLayer.loadMarkupsIntoFabric(state.markups);
      } else {
        window.PdfEditor.annotationLayer.renderMarkups();
      }
      window.PdfEditor.saveManager.scheduleSave();
      window.PdfEditor.main.updateUndoRedoButtons();
    }
  };
})();
