/* pdf-editor/annotation-layer.js - Render markups and setup annotation handlers */
(function () {
  'use strict';
  var state = window.PdfEditor.state;
  var utils = window.PdfEditor.utils;
  var markupTools = window.PdfEditor.markupTools;

  function renderMarkups() {
    document.querySelectorAll('.page-annotations').forEach(function (annoLayer) {
      var wrap = annoLayer;
      var pageIndex = parseInt(annoLayer.dataset.page, 10);
      var pageMarkups = state.markups.filter(function (m) { return m.page === pageIndex; });
      wrap.querySelectorAll('.anno-highlight, .anno-comment, .anno-ink, .anno-text, .comment-popover').forEach(function (el) { el.remove(); });
      var pageWrap = wrap.closest('.page-wrap');
      if (!pageWrap) return;
      var canvas = pageWrap.querySelector('canvas');
      if (!canvas) return;
      var overlayW = parseFloat(wrap.style.width) || canvas.width;
      var overlayH = parseFloat(wrap.style.height) || canvas.height;
      pageMarkups.forEach(function (m) {
        if (m.type === 'highlight' && m.bounds) {
          var b = m.bounds;
          var div = document.createElement('div');
          div.className = 'anno-highlight';
          div.dataset.id = m.id;
          div.style.left = (b.x * 100) + '%';
          div.style.top = (b.y * 100) + '%';
          div.style.width = (b.width * 100) + '%';
          div.style.height = (b.height * 100) + '%';
          if (m.color) {
            var c = utils.parseColor(m.color);
            div.style.background = 'rgba(' + Math.round(c.r * 255) + ', ' + Math.round(c.g * 255) + ', ' + Math.round(c.b * 255) + ', 0.35)';
            div.style.borderColor = 'rgba(' + Math.round(c.r * 255) + ', ' + Math.round(c.g * 255) + ', ' + Math.round(c.b * 255) + ', 0.6)';
          }
          div.title = state.isEditMode ? 'Click to delete' : '';
          div.addEventListener('click', function (e) { e.stopPropagation(); if (!state.isEditMode) return; markupTools.deleteMarkup(m.id); });
          wrap.appendChild(div);
        } else if (m.type === 'ink' && m.points && m.points.length >= 2) {
          var pts = m.points;
          var strokeWidth = m.strokeWidth || 2;
          var color = m.color || '#000000';
          var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          svg.setAttribute('viewBox', '0 0 1 1');
          svg.setAttribute('preserveAspectRatio', 'none');
          var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.setAttribute('d', pts.map(function (p, i) { return (i === 0 ? 'M' : 'L') + p[0] + ',' + p[1]; }).join(' '));
          path.setAttribute('fill', 'none');
          path.setAttribute('stroke', color);
          path.setAttribute('stroke-width', (strokeWidth / overlayW).toString());
          path.setAttribute('stroke-linecap', 'round');
          path.setAttribute('stroke-linejoin', 'round');
          svg.appendChild(path);
          var inkWrap = document.createElement('div');
          inkWrap.className = 'anno-ink';
          inkWrap.dataset.id = m.id;
          inkWrap.appendChild(svg);
          inkWrap.title = state.isEditMode ? 'Click to delete' : '';
          inkWrap.addEventListener('click', function (e) { e.stopPropagation(); if (!state.isEditMode) return; markupTools.deleteMarkup(m.id); });
          wrap.appendChild(inkWrap);
        } else if (m.type === 'text' && m.bounds) {
          var b = m.bounds;
          var div = document.createElement('div');
          div.className = 'anno-text';
          div.dataset.id = m.id;
          div.style.left = (b.x * 100) + '%';
          div.style.top = (b.y * 100) + '%';
          div.style.width = ((b.width || 0.2) * 100) + '%';
          div.style.fontSize = (m.fontSize || 12) + 'px';
          div.style.color = m.color || '#000000';
          div.textContent = m.text || '';
          div.title = state.isEditMode ? 'Click to edit or delete' : '';
          div.addEventListener('click', function (e) {
            e.stopPropagation();
            if (!state.isEditMode) return;
            window.PdfEditor.annotationLayer.showTextEditPopover(m, div);
          });
          wrap.appendChild(div);
        } else if ((m.type === 'comment' || m.type === 'sticky_note') && m.bounds) {
          var b = m.bounds;
          var dot = document.createElement('div');
          dot.className = 'anno-comment' + (m.text ? ' has-text' : '');
          dot.dataset.id = m.id;
          dot.style.left = (b.x * 100) + '%';
          dot.style.top = (b.y * 100) + '%';
          dot.textContent = '\uD83D\uDCAC';
          dot.title = m.text || (state.isEditMode ? 'Add comment' : '');
          dot.addEventListener('click', function (e) {
            e.stopPropagation();
            if (!state.isEditMode) return;
            window.PdfEditor.annotationLayer.showCommentPopover(m, dot);
          });
          wrap.appendChild(dot);
        }
      });
    });
  }

  function showCommentPopover(markup, anchor) {
    var pop = document.querySelector('.comment-popover');
    if (pop) pop.remove();
    pop = document.createElement('div');
    pop.className = 'comment-popover';
    var textarea = document.createElement('textarea');
    textarea.rows = 3;
    textarea.value = markup.text || '';
    textarea.placeholder = 'Comment text...';
    textarea.style.width = '100%';
    var saveBtn = document.createElement('button');
    saveBtn.textContent = 'Save';
    saveBtn.type = 'button';
    var delBtn = document.createElement('button');
    delBtn.textContent = 'Delete';
    delBtn.type = 'button';
    var actions = document.createElement('div');
    actions.className = 'comment-actions';
    actions.append(saveBtn, delBtn);
    pop.append(textarea, actions);
    var rect = anchor.getBoundingClientRect();
    pop.style.position = 'fixed';
    pop.style.left = rect.left + 'px';
    pop.style.top = (rect.top - 120) + 'px';
    document.body.appendChild(pop);
    textarea.focus();
    saveBtn.addEventListener('click', function () {
      var idx = state.markups.findIndex(function (x) { return x.id === markup.id; });
      if (idx >= 0) {
        window.PdfEditor.undoManager.pushUndo();
        state.markups[idx].text = textarea.value.trim();
        window.PdfEditor.saveManager.scheduleSave();
      }
      renderMarkups();
      pop.remove();
    });
    delBtn.addEventListener('click', function () {
      markupTools.deleteMarkup(markup.id);
      pop.remove();
    });
  }

  var TEXT_COLORS = ['#000000', '#dc2626', '#2563eb', '#059669', '#7c3aed'];
  function showTextEditPopover(markup, anchor) {
    var pop = document.querySelector('.comment-popover');
    if (pop) pop.remove();
    pop = document.createElement('div');
    pop.className = 'comment-popover';
    var textarea = document.createElement('textarea');
    textarea.rows = 3;
    textarea.value = markup.text || '';
    textarea.placeholder = 'Text to display on page...';
    textarea.style.width = '100%';
    var formatRow = document.createElement('div');
    formatRow.className = 'text-format-row';
    var sizeLabel = document.createElement('label');
    sizeLabel.textContent = 'Size:';
    var sizeSelect = document.createElement('select');
    [10, 12, 14, 18, 24].forEach(function (n) {
      var o = document.createElement('option');
      o.value = n;
      o.textContent = n;
      if (n === (markup.fontSize || 12)) o.selected = true;
      sizeSelect.appendChild(o);
    });
    var colorLabel = document.createElement('label');
    colorLabel.textContent = 'Color:';
    var swatches = document.createElement('div');
    swatches.className = 'color-swatches';
    var currentColor = markup.color || '#000000';
    TEXT_COLORS.forEach(function (hex) {
      var sw = document.createElement('div');
      sw.className = 'color-swatch' + (hex === currentColor ? ' active' : '');
      sw.style.background = hex;
      sw.dataset.color = hex;
      sw.addEventListener('click', function () {
        swatches.querySelectorAll('.color-swatch').forEach(function (s) { s.classList.remove('active'); });
        sw.classList.add('active');
      });
      swatches.appendChild(sw);
    });
    formatRow.append(sizeLabel, sizeSelect, colorLabel, swatches);
    var saveBtn = document.createElement('button');
    saveBtn.textContent = 'Save';
    saveBtn.type = 'button';
    var delBtn = document.createElement('button');
    delBtn.textContent = 'Delete';
    delBtn.type = 'button';
    var actions = document.createElement('div');
    actions.className = 'comment-actions';
    actions.append(saveBtn, delBtn);
    pop.append(textarea, formatRow, actions);
    var rect = anchor.getBoundingClientRect();
    pop.style.position = 'fixed';
    pop.style.left = rect.left + 'px';
    pop.style.top = (rect.top - 160) + 'px';
    document.body.appendChild(pop);
    textarea.focus();
    saveBtn.addEventListener('click', function () {
      var idx = state.markups.findIndex(function (x) { return x.id === markup.id; });
      if (idx >= 0) {
        window.PdfEditor.undoManager.pushUndo();
        state.markups[idx].text = textarea.value;
        state.markups[idx].fontSize = parseInt(sizeSelect.value, 10);
        var activeSw = swatches.querySelector('.color-swatch.active') || swatches.firstElementChild;
        state.markups[idx].color = (activeSw && activeSw.dataset.color) || '#000000';
        window.PdfEditor.saveManager.scheduleSave();
      }
      renderMarkups();
      pop.remove();
    });
    delBtn.addEventListener('click', function () {
      markupTools.deleteMarkup(markup.id);
      pop.remove();
    });
  }

  function setupAnnotationLayer(pageWrap, pageIndex, pageWidth, pageHeight) {
    var overlay = pageWrap.querySelector('.page-annotations');
    if (!overlay) return;
    overlay.dataset.page = pageIndex;
    overlay.style.width = pageWidth + 'px';
    overlay.style.height = pageHeight + 'px';

    function getPointerCoords(ev) {
      if (ev.touches && ev.touches.length) return { x: ev.touches[0].clientX, y: ev.touches[0].clientY };
      if (ev.changedTouches && ev.changedTouches.length) return { x: ev.changedTouches[0].clientX, y: ev.changedTouches[0].clientY };
      return { x: ev.clientX, y: ev.clientY };
    }

    function finishInkStroke() {
      if (state.mode !== 'draw' || !state.inkStrokeEl || state.inkPoints.length < 2) return;
      var pts = state.inkPoints;
      var minX = pts[0][0], minY = pts[0][1], maxX = pts[0][0], maxY = pts[0][1];
      for (var i = 1; i < pts.length; i++) {
        minX = Math.min(minX, pts[i][0]);
        minY = Math.min(minY, pts[i][1]);
        maxX = Math.max(maxX, pts[i][0]);
        maxY = Math.max(maxY, pts[i][1]);
      }
      var margin = 0.005;
      var bounds = {
        x: Math.max(0, minX - margin),
        y: Math.max(0, minY - margin),
        width: Math.min(1, maxX - minX + 2 * margin),
        height: Math.min(1, maxY - minY + 2 * margin)
      };
      markupTools.addMarkup({
        id: markupTools.id(),
        page: state.inkStrokeEl._pageIndex,
        type: 'ink',
        bounds: bounds,
        points: pts.length > 500 ? markupTools.decimatePoints(pts, 500) : pts,
        color: '#000000',
        strokeWidth: 2
      });
      state.inkStrokeEl.remove();
      state.inkStrokeEl = null;
      state.inkPoints = [];
    }

    overlay.addEventListener('mousedown', function (e) {
      if (!state.isEditMode || (state.mode !== 'highlight' && state.mode !== 'comment' && state.mode !== 'draw' && state.mode !== 'text')) return;
      var rect = overlay.getBoundingClientRect();
      var x = e.clientX - rect.left;
      var y = e.clientY - rect.top;
      var nx = x / pageWidth;
      var ny = y / pageHeight;
      if (state.mode === 'highlight') {
        state.dragStart = { x: x, y: y };
        if (state.previewEl) state.previewEl.remove();
        state.previewEl = document.createElement('div');
        state.previewEl.className = 'highlight-preview';
        state.previewEl.style.left = x + 'px';
        state.previewEl.style.top = y + 'px';
        state.previewEl.style.width = '0';
        state.previewEl.style.height = '0';
        overlay.appendChild(state.previewEl);
      } else if (state.mode === 'comment') {
        utils.showTextModal('Comment text (optional)', 'Add comment').then(function (text) {
          if (text !== null) {
            markupTools.addMarkup({
              id: markupTools.id(),
              page: pageIndex,
              type: 'comment',
              bounds: { x: nx, y: ny, width: 0.03, height: 0.03 },
              text: text || ''
            });
          }
        });
      } else if (state.mode === 'draw') {
        state.inkPoints = [[nx, ny]];
        if (state.inkStrokeEl) state.inkStrokeEl.remove();
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 1 1');
        svg.setAttribute('preserveAspectRatio', 'none');
        svg.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;';
        var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', 'M' + nx + ',' + ny);
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke', '#000000');
        path.setAttribute('stroke-width', (2 / pageWidth).toString());
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');
        svg.appendChild(path);
        state.inkStrokeEl = document.createElement('div');
        state.inkStrokeEl.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;';
        state.inkStrokeEl.appendChild(svg);
        overlay.appendChild(state.inkStrokeEl);
        state.inkStrokeEl._path = path;
        state.inkStrokeEl._pageIndex = pageIndex;
        state.inkStrokeEl._pageW = pageWidth;
        state.inkStrokeEl._pageH = pageHeight;
      } else if (state.mode === 'text') {
        utils.showTextModal('Text to add on page', 'Add text').then(function (text) {
          if (text === null) return;
          var pad = 0.02;
          markupTools.addMarkup({
            id: markupTools.id(),
            page: pageIndex,
            type: 'text',
            bounds: { x: Math.max(0, nx - pad), y: Math.max(0, ny - pad), width: 0.2, height: 0.05 },
            text: String(text || '').trim(),
            fontSize: 12,
            color: '#000000'
          });
        });
      }
    });

    overlay.addEventListener('mousemove', function (e) {
      if (state.mode === 'highlight' && state.dragStart && state.previewEl) {
        var rect = overlay.getBoundingClientRect();
        var x = e.clientX - rect.left;
        var y = e.clientY - rect.top;
        var left = Math.min(state.dragStart.x, x);
        var top = Math.min(state.dragStart.y, y);
        var width = Math.abs(x - state.dragStart.x);
        var height = Math.abs(y - state.dragStart.y);
        state.previewEl.style.left = left + 'px';
        state.previewEl.style.top = top + 'px';
        state.previewEl.style.width = width + 'px';
        state.previewEl.style.height = height + 'px';
      } else if (state.mode === 'draw' && state.inkStrokeEl && state.inkPoints.length > 0) {
        var rect = overlay.getBoundingClientRect();
        var x = e.clientX - rect.left;
        var y = e.clientY - rect.top;
        var nx = x / state.inkStrokeEl._pageW;
        var ny = y / state.inkStrokeEl._pageH;
        state.inkPoints.push([nx, ny]);
        var d = state.inkPoints.map(function (p, i) { return (i === 0 ? 'M' : 'L') + p[0] + ',' + p[1]; }).join(' ');
        state.inkStrokeEl._path.setAttribute('d', d);
      }
    });

    overlay.addEventListener('mouseup', function (e) {
      if (state.mode === 'highlight' && state.dragStart && state.previewEl) {
        var rect = overlay.getBoundingClientRect();
        var x = e.clientX - rect.left;
        var y = e.clientY - rect.top;
        var left = Math.min(state.dragStart.x, x);
        var top = Math.min(state.dragStart.y, y);
        var width = Math.abs(x - state.dragStart.x);
        var height = Math.abs(y - state.dragStart.y);
        state.previewEl.remove();
        state.previewEl = null;
        state.dragStart = null;
        if (width < 5 || height < 5) return;
        var bounds = markupTools.normalizeBounds(left, top, width, height, pageWidth, pageHeight);
        markupTools.addMarkup({
          id: markupTools.id(),
          page: pageIndex,
          type: 'highlight',
          bounds: bounds,
          color: state.highlightColor || '#ffeb3b'
        });
      } else if (state.mode === 'draw') {
        finishInkStroke();
      }
    });

    overlay.addEventListener('mouseleave', finishInkStroke);

    overlay.addEventListener('touchstart', function (e) {
      if (!state.isEditMode || state.mode !== 'draw' || e.touches.length !== 1) return;
      e.preventDefault();
      var rect = overlay.getBoundingClientRect();
      var coords = getPointerCoords(e);
      var x = coords.x - rect.left;
      var y = coords.y - rect.top;
      var nx = x / pageWidth;
      var ny = y / pageHeight;
      state.inkPoints = [[nx, ny]];
      if (state.inkStrokeEl) state.inkStrokeEl.remove();
      var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 1 1');
      svg.setAttribute('preserveAspectRatio', 'none');
      svg.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;';
      var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', 'M' + nx + ',' + ny);
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', '#000000');
      path.setAttribute('stroke-width', (2 / pageWidth).toString());
      path.setAttribute('stroke-linecap', 'round');
      path.setAttribute('stroke-linejoin', 'round');
      svg.appendChild(path);
      state.inkStrokeEl = document.createElement('div');
      state.inkStrokeEl.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;';
      state.inkStrokeEl.appendChild(svg);
      overlay.appendChild(state.inkStrokeEl);
      state.inkStrokeEl._path = path;
      state.inkStrokeEl._pageIndex = pageIndex;
      state.inkStrokeEl._pageW = pageWidth;
      state.inkStrokeEl._pageH = pageHeight;
    }, { passive: false });

    overlay.addEventListener('touchmove', function (e) {
      if (state.mode === 'draw' && state.inkStrokeEl && state.inkPoints.length > 0 && e.touches.length === 1) {
        e.preventDefault();
        var rect = overlay.getBoundingClientRect();
        var coords = getPointerCoords(e);
        var x = coords.x - rect.left;
        var y = coords.y - rect.top;
        var nx = x / state.inkStrokeEl._pageW;
        var ny = y / state.inkStrokeEl._pageH;
        state.inkPoints.push([nx, ny]);
        var d = state.inkPoints.map(function (p, i) { return (i === 0 ? 'M' : 'L') + p[0] + ',' + p[1]; }).join(' ');
        state.inkStrokeEl._path.setAttribute('d', d);
      }
    }, { passive: false });

    overlay.addEventListener('touchend', function (e) {
      if (state.mode === 'draw' && e.changedTouches && e.changedTouches.length) {
        e.preventDefault();
        finishInkStroke();
      }
    }, { passive: false });

    overlay.addEventListener('touchcancel', function (e) {
      if (state.mode === 'draw') finishInkStroke();
    }, { passive: false });
  }

  window.PdfEditor.annotationLayer = {
    renderMarkups: renderMarkups,
    setupAnnotationLayer: setupAnnotationLayer,
    showCommentPopover: showCommentPopover,
    showTextEditPopover: showTextEditPopover
  };
})();
