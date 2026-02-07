/* pdf-editor/markup-tools.js - Markup creation and manipulation */
(function () {
  'use strict';
  var state = window.PdfEditor.state;
  var utils = window.PdfEditor.utils;
  window.PdfEditor.markupTools = {
    id: function () {
      return 'm_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
    },
    normalizeBounds: function (x, y, w, h, pageWidth, pageHeight) {
      return {
        x: x / pageWidth,
        y: y / pageHeight,
        width: w / pageWidth,
        height: h / pageHeight
      };
    },
    decimatePoints: function (pts, maxPts) {
      if (pts.length <= maxPts) return pts;
      var step = (pts.length - 1) / (maxPts - 1);
      var out = [];
      for (var i = 0; i < maxPts; i++) {
        var idx = Math.min(Math.round(i * step), pts.length - 1);
        out.push(pts[idx]);
      }
      return out;
    },
    addMarkup: function (m) {
      window.PdfEditor.undoManager.pushUndo();
      state.markups.push(m);
      window.PdfEditor.saveManager.scheduleSave();
      window.PdfEditor.annotationLayer.renderMarkups();
    },
    deleteMarkup: function (markupId) {
      window.PdfEditor.undoManager.pushUndo();
      state.markups = state.markups.filter(function (x) { return x.id !== markupId; });
      window.PdfEditor.saveManager.scheduleSave();
      window.PdfEditor.annotationLayer.renderMarkups();
    }
  };
})();
