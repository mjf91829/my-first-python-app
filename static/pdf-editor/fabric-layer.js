/* pdf-editor/fabric-layer.js - Fabric.js canvas per page, object layer over PDF
 * Coordinate normalization: All stored coordinates are 0-1 (fraction of page width/height).
 * - When saving: canvas pixel coords are divided by canvas width/height.
 * - When loading: normalized values are multiplied by current canvas width/height.
 * This keeps export consistent across zoom levels and device pixel ratios.
 */
(function () {
  'use strict';
  var state = window.PdfEditor.state;
  var markupTools = window.PdfEditor.markupTools;
  var utils = window.PdfEditor.utils;
  var fabricCanvases = {}; // pageIndex -> { canvas, width, height }

  function whenFabricReady() {
    if (typeof fabric !== 'undefined') return Promise.resolve();
    return new Promise(function (resolve) {
      function check() {
        if (typeof fabric !== 'undefined') { resolve(); return; }
        requestAnimationFrame(check);
      }
      requestAnimationFrame(check);
    });
  }

  function syncPageToState(pageIndex) {
    var pageMarkups = serializePageToMarkups(pageIndex);
    if (pageMarkups === null) return;
    state.markups = state.markups.filter(function (m) { return m.page !== pageIndex; }).concat(pageMarkups);
    window.PdfEditor.saveManager.scheduleSave();
  }

  function objectToMarkup(obj, pageIndex, w, h) {
    var data = obj.get && obj.get('data') ? obj.get('data') : {};
    var id = data.id || markupTools.id();
    var type = data.markupType || 'highlight';
    var left = obj.left || 0;
    var top = obj.top || 0;
    var width = (obj.width * (obj.scaleX || 1)) || 0.01;
    var height = (obj.height * (obj.scaleY || 1)) || 0.01;
    var nx = left / w;
    var ny = top / h;
    var nw = width / w;
    var nh = height / h;
    var bounds = { x: nx, y: ny, width: nw, height: nh };

    if (type === 'highlight') {
      var fill = (obj.fill && obj.fill !== 'transparent') ? obj.fill : '#ffeb3b';
      var hex = typeof fill === 'string' && fill.indexOf('rgba') === 0
        ? '#ffeb3b'
        : (typeof fill === 'string' ? fill : '#ffeb3b');
      return { id: id, page: pageIndex, type: 'highlight', bounds: bounds, color: hex };
    }
    if (type === 'ink') {
      var pathData = obj.path;
      if (pathData && pathData.path) pathData = pathData.path;
      var pts = [];
      if (pathData && pathData.length) {
        for (var pi = 0; pi < pathData.length; pi++) {
          var cmd = pathData[pi];
          if (Array.isArray(cmd) && (cmd[0] === 'M' || cmd[0] === 'L') && cmd.length >= 3) {
            pts.push([cmd[1] / w, cmd[2] / h]);
          }
        }
      }
      if (pts.length < 2 && data.points && data.points.length >= 2) {
        pts = data.points;
      }
      if (pts.length < 2) pts = [[nx, ny], [nx + nw, ny + nh]];
      var stroke = (obj.stroke && obj.stroke !== 'transparent') ? obj.stroke : '#000000';
      return {
        id: id,
        page: pageIndex,
        type: 'ink',
        bounds: bounds,
        points: pts,
        color: typeof stroke === 'string' ? stroke : '#000000',
        strokeWidth: obj.strokeWidth || 2
      };
    }
    if (type === 'text') {
      var text = (obj.get && obj.get('text')) ? obj.get('text') : (obj.text || '');
      var fontSize = (obj.get && obj.get('fontSize')) ? obj.get('fontSize') : (obj.fontSize || 12);
      var color = (obj.fill && obj.fill !== 'transparent') ? obj.fill : '#000000';
      return {
        id: id,
        page: pageIndex,
        type: 'text',
        bounds: bounds,
        text: text,
        fontSize: fontSize,
        color: typeof color === 'string' ? color : '#000000'
      };
    }
    if (type === 'comment') {
      var commentText = (obj.get && obj.get('commentText')) ? obj.get('commentText') : (obj.commentText || '');
      return {
        id: id,
        page: pageIndex,
        type: 'comment',
        bounds: bounds,
        text: commentText
      };
    }
    return null;
  }

  function serializePageToMarkups(pageIndex) {
    var entry = fabricCanvases[pageIndex];
    if (!entry || !entry.canvas) return null;
    var canvas = entry.canvas;
    var w = entry.width;
    var h = entry.height;
    var objects = canvas.getObjects();
    var list = [];
    for (var i = 0; i < objects.length; i++) {
      var m = objectToMarkup(objects[i], pageIndex, w, h);
      if (m) list.push(m);
    }
    return list;
  }

  function serializeAllFabricToMarkups() {
    var pageIndices = Object.keys(fabricCanvases).map(Number);
    var result = state.markups.filter(function (m) {
      return pageIndices.indexOf(m.page) === -1;
    });
    for (var i = 0; i < pageIndices.length; i++) {
      var pageMarkups = serializePageToMarkups(pageIndices[i]);
      if (pageMarkups) result = result.concat(pageMarkups);
    }
    return result;
  }

  function markupToFabricObject(m, w, h) {
    var id = m.id || markupTools.id();
    var page = m.page;
    var b = m.bounds || { x: 0, y: 0, width: 0.1, height: 0.1 };
    var left = b.x * w;
    var top = b.y * h;
    var width = (b.width || 0.1) * w;
    var height = (b.height || 0.1) * h;
    var data = { id: id, page: page, markupType: m.type };

    if (m.type === 'highlight') {
      var color = m.color || '#ffeb3b';
      var c = utils.parseColor(color);
      var fillRgba = 'rgba(' + Math.round(c.r * 255) + ',' + Math.round(c.g * 255) + ',' + Math.round(c.b * 255) + ',0.35)';
      var rect = new fabric.Rect({
        left: left,
        top: top,
        width: width,
        height: height,
        fill: fillRgba,
        stroke: color,
        strokeWidth: 1,
        selectable: true,
        evented: true,
        data: data
      });
      return rect;
    }
    if (m.type === 'ink' && m.points && m.points.length >= 2) {
      var pts = m.points;
      var pathStr = 'M ' + (pts[0][0] * w) + ' ' + (pts[0][1] * h);
      for (var pi = 1; pi < pts.length; pi++) {
        pathStr += ' L ' + (pts[pi][0] * w) + ' ' + (pts[pi][1] * h);
      }
      var pathObj = new fabric.Path(pathStr, {
        stroke: m.color || '#000000',
        strokeWidth: m.strokeWidth || 2,
        fill: null,
        selectable: true,
        evented: true,
        data: Object.assign({}, data, { points: pts })
      });
      return pathObj;
    }
    if (m.type === 'text') {
      var text = (m.text || '').toString();
      var fontSize = m.fontSize || 12;
      var color = m.color || '#000000';
      var itext = new fabric.IText(text || 'Text', {
        left: left,
        top: top,
        fontSize: fontSize,
        fill: color,
        selectable: true,
        evented: true,
        data: data
      });
      if (width > 0 && height > 0) itext.set({ width: width, height: height });
      return itext;
    }
    if (m.type === 'comment' || m.type === 'sticky_note') {
      var commentText = (m.text || '').toString();
      var r = Math.max(4, Math.min(width, height) * 0.5);
      var circle = new fabric.Circle({
        left: left,
        top: top,
        radius: r,
        fill: '#8b5cf6',
        selectable: true,
        evented: true,
        data: Object.assign({}, data, { commentText: commentText })
      });
      return circle;
    }
    return null;
  }

  function loadMarkupsIntoFabric(markups) {
    state.markups = Array.isArray(markups) ? markups : [];
    var byPage = {};
    state.markups.forEach(function (m) {
      var p = m.page;
      if (!byPage[p]) byPage[p] = [];
      byPage[p].push(m);
    });
    Object.keys(fabricCanvases).forEach(function (pageKey) {
      var pageIndex = parseInt(pageKey, 10);
      var entry = fabricCanvases[pageIndex];
      if (!entry || !entry.canvas) return;
      var canvas = entry.canvas;
      canvas.remove.apply(canvas, canvas.getObjects());
      var list = byPage[pageIndex] || [];
      for (var i = 0; i < list.length; i++) {
        var obj = markupToFabricObject(list[i], entry.width, entry.height);
        if (obj) canvas.add(obj);
      }
      canvas.requestRenderAll();
    });
  }

  function loadMarkupsForPage(pageIndex) {
    var entry = fabricCanvases[pageIndex];
    if (!entry) return;
    var list = state.markups.filter(function (m) { return m.page === pageIndex; });
    var canvas = entry.canvas;
    canvas.remove.apply(canvas, canvas.getObjects());
    for (var i = 0; i < list.length; i++) {
      var obj = markupToFabricObject(list[i], entry.width, entry.height);
      if (obj) canvas.add(obj);
    }
    canvas.requestRenderAll();
  }

  function setSelectionEnabled(enabled) {
    Object.keys(fabricCanvases).forEach(function (pageKey) {
      var entry = fabricCanvases[pageKey];
      if (entry && entry.canvas) entry.canvas.selection = enabled;
    });
  }

  var drawingRect = null;
  var drawingPathPoints = null;
  var drawingPathPage = null;
  var drawingPathW = 0;
  var drawingPathH = 0;

  function initFabricForPage(pageWrap, pageIndex, w, h) {
    whenFabricReady().then(function () {
      if (fabricCanvases[pageIndex]) return;
      var fabricContainer = document.createElement('div');
      fabricContainer.className = 'fabric-canvas-container';
      fabricContainer.style.cssText = 'position:absolute;left:0;top:0;width:' + w + 'px;height:' + h + 'px;pointer-events:auto;';
      fabricContainer.dataset.page = String(pageIndex);
      pageWrap.appendChild(fabricContainer);

      var canvas = new fabric.Canvas(fabricContainer, {
        width: w,
        height: h,
        selection: state.mode === 'none',
        preserveObjectStacking: true
      });
      canvas.allowTouchScrolling = false;
      canvas.backgroundColor = 'transparent';

      fabricCanvases[pageIndex] = { canvas: canvas, width: w, height: h };

      loadMarkupsForPage(pageIndex);

      function getPointer(ev) {
        var pointer = canvas.getPointer(ev.e);
        return { x: pointer.x, y: pointer.y };
      }

      canvas.on('object:added', function (opt) {
        if (state.isUndoRedo) return;
        syncPageToState(pageIndex);
      });
      canvas.on('object:modified', function (opt) {
        if (state.isUndoRedo) return;
        syncPageToState(pageIndex);
      });
      canvas.on('object:removed', function (opt) {
        if (state.isUndoRedo) return;
        syncPageToState(pageIndex);
      });

      canvas.on('selection:created', function (opt) {
        showContextMenu(canvas, pageIndex, fabricContainer);
      });
      canvas.on('selection:updated', function (opt) {
        showContextMenu(canvas, pageIndex, fabricContainer);
      });
      canvas.on('selection:cleared', function (opt) {
        hideContextMenu();
      });

      canvas.on('mouse:down', function (opt) {
        if (!state.isEditMode || !opt.pointer) return;
        var ptr = getPointer(opt);
        var nx = ptr.x / w;
        var ny = ptr.y / h;

        if (state.mode === 'highlight') {
          window.PdfEditor.undoManager.pushUndo();
          drawingRect = new fabric.Rect({
            left: ptr.x,
            top: ptr.y,
            width: 0,
            height: 0,
            fill: 'rgba(255,235,59,0.35)',
            stroke: state.highlightColor || '#ffeb3b',
            strokeWidth: 1,
            selectable: false,
            evented: false,
            data: { id: markupTools.id(), page: pageIndex, markupType: 'highlight' }
          });
          canvas.add(drawingRect);
          return;
        }
        if (state.mode === 'draw') {
          window.PdfEditor.undoManager.pushUndo();
          drawingPathPoints = [[ptr.x, ptr.y]];
          drawingPathPage = pageIndex;
          drawingPathW = w;
          drawingPathH = h;
          return;
        }
        if (state.mode === 'text') {
          window.PdfEditor.undoManager.pushUndo();
          utils.showTextModal('Text to add on page', 'Add text').then(function (text) {
            if (text === null) return;
            var pad = 0.02 * w;
            var itext = new fabric.IText(String(text || '').trim() || 'Text', {
              left: Math.max(0, ptr.x - pad),
              top: Math.max(0, ptr.y - pad),
              fontSize: 12,
              fill: '#000000',
              selectable: true,
              evented: true,
              data: { id: markupTools.id(), page: pageIndex, markupType: 'text' }
            });
            canvas.add(itext);
            syncPageToState(pageIndex);
          });
          return;
        }
        if (state.mode === 'comment') {
          window.PdfEditor.undoManager.pushUndo();
          utils.showTextModal('Comment text (optional)', 'Add comment').then(function (text) {
            if (text !== null) {
              var radius = Math.min(0.03 * w, 0.03 * h);
              var circle = new fabric.Circle({
                left: ptr.x - radius,
                top: ptr.y - radius,
                radius: radius,
                fill: '#8b5cf6',
                selectable: true,
                evented: true,
                data: { id: markupTools.id(), page: pageIndex, markupType: 'comment', commentText: text || '' }
              });
              canvas.add(circle);
              syncPageToState(pageIndex);
            }
          });
        }
      });

      canvas.on('mouse:move', function (opt) {
        if (state.mode === 'highlight' && drawingRect) {
          var ptr = getPointer(opt);
          var left = Math.min(drawingRect.left, ptr.x);
          var top = Math.min(drawingRect.top, ptr.y);
          var width = Math.abs(ptr.x - drawingRect.left);
          var height = Math.abs(ptr.y - drawingRect.top);
          drawingRect.set({ left: left, top: top, width: width, height: height });
          canvas.requestRenderAll();
        } else if (state.mode === 'draw' && drawingPathPoints && drawingPathPage === pageIndex) {
          var ptr = getPointer(opt);
          drawingPathPoints.push([ptr.x, ptr.y]);
        }
      });

      canvas.on('mouse:up', function (opt) {
        if (state.mode === 'highlight' && drawingRect) {
          var width = drawingRect.get('width') * (drawingRect.get('scaleX') || 1);
          var height = drawingRect.get('height') * (drawingRect.get('scaleY') || 1);
          if (width < 5 || height < 5) {
            canvas.remove(drawingRect);
          } else {
            var c = state.highlightColor || '#ffeb3b';
            drawingRect.set({ fill: 'rgba(255,235,59,0.35)', stroke: c });
            drawingRect.set('selectable', true);
            drawingRect.set('evented', true);
            syncPageToState(pageIndex);
          }
          drawingRect = null;
          canvas.requestRenderAll();
          return;
        }
        if (state.mode === 'draw' && drawingPathPoints && drawingPathPage === pageIndex) {
          if (drawingPathPoints.length >= 2) {
            var pts = drawingPathPoints;
            var pathStr = 'M ' + pts[0][0] + ' ' + pts[0][1];
            for (var i = 1; i < pts.length; i++) {
              pathStr += ' L ' + pts[i][0] + ' ' + pts[i][1];
            }
            var normalizedPts = pts.map(function (p) { return [p[0] / w, p[1] / h]; });
            var decimated = normalizedPts.length > 500 ? markupTools.decimatePoints(normalizedPts, 500) : normalizedPts;
            var minX = decimated[0][0], minY = decimated[0][1], maxX = decimated[0][0], maxY = decimated[0][1];
            for (var j = 1; j < decimated.length; j++) {
              minX = Math.min(minX, decimated[j][0]);
              minY = Math.min(minY, decimated[j][1]);
              maxX = Math.max(maxX, decimated[j][0]);
              maxY = Math.max(maxY, decimated[j][1]);
            }
            var margin = 0.005;
            var pathObj = new fabric.Path(pathStr, {
              stroke: '#000000',
              strokeWidth: 2,
              fill: null,
              selectable: true,
              evented: true,
              data: {
                id: markupTools.id(),
                page: pageIndex,
                markupType: 'ink',
                bounds: {
                  x: Math.max(0, minX - margin),
                  y: Math.max(0, minY - margin),
                  width: Math.min(1, maxX - minX + 2 * margin),
                  height: Math.min(1, maxY - minY + 2 * margin)
                },
                points: decimated
              }
            });
            canvas.add(pathObj);
            syncPageToState(pageIndex);
          }
          drawingPathPoints = null;
          drawingPathPage = null;
        }
      });

      canvas.on('mouse:out', function () {
        if (state.mode === 'highlight' && drawingRect) {
          canvas.remove(drawingRect);
          drawingRect = null;
        }
        if (state.mode === 'draw' && drawingPathPoints && drawingPathPage === pageIndex) {
          drawingPathPoints = null;
          drawingPathPage = null;
        }
      });
    });
  }

  function disposeFabricForPage(pageIndex) {
    var entry = fabricCanvases[pageIndex];
    if (!entry) return;
    if (entry.canvas) {
      entry.canvas.dispose();
    }
    delete fabricCanvases[pageIndex];
  }

  var activeContextCanvas = null;
  var activeContextPageIndex = null;

  function getContextMenuEl() {
    return document.getElementById('context-menu');
  }

  function hideContextMenu() {
    var el = getContextMenuEl();
    if (el) {
      el.setAttribute('aria-hidden', 'true');
      el.style.display = 'none';
    }
    activeContextCanvas = null;
    activeContextPageIndex = null;
  }

  function showContextMenu(canvas, pageIndex, containerEl) {
    var obj = canvas.getActiveObject();
    if (!obj) { hideContextMenu(); return; }
    activeContextCanvas = canvas;
    activeContextPageIndex = pageIndex;
    var menuEl = getContextMenuEl();
    if (!menuEl) return;
    var textOpts = document.getElementById('context-menu-text-options');
    var data = obj.get && obj.get('data') ? obj.get('data') : {};
    var isText = data.markupType === 'text' || (obj.type === 'i-text' || obj.type === 'textbox');
    if (textOpts) {
      textOpts.style.display = isText ? 'block' : 'none';
      if (isText) {
        var fontSizeSelect = document.getElementById('context-menu-font-size');
        if (fontSizeSelect) {
          var fs = (obj.get && obj.get('fontSize')) ? obj.get('fontSize') : (obj.fontSize || 12);
          fontSizeSelect.value = String(Math.round(fs));
        }
        var colorsEl = document.getElementById('context-menu-colors');
        if (colorsEl) {
          var colors = ['#000000', '#dc2626', '#2563eb', '#059669', '#7c3aed'];
          var current = (obj.get && obj.get('fill')) ? obj.get('fill') : (obj.fill || '#000000');
          colorsEl.innerHTML = '';
          colors.forEach(function (hex) {
            var dot = document.createElement('div');
            dot.className = 'color-dot' + (hex === current ? ' active' : '');
            dot.style.background = hex;
            dot.dataset.color = hex;
            dot.addEventListener('click', function () {
              if (activeContextCanvas && activeContextCanvas.getActiveObject()) {
                activeContextCanvas.getActiveObject().set('fill', hex);
                activeContextCanvas.requestRenderAll();
                syncPageToState(activeContextPageIndex);
              }
              colorsEl.querySelectorAll('.color-dot').forEach(function (d) { d.classList.remove('active'); });
              dot.classList.add('active');
            });
            colorsEl.appendChild(dot);
          });
        }
      }
    }
    var containerRect = containerEl.getBoundingClientRect();
    var objRect = obj.getBoundingRect();
    var virtualRef = {
      getBoundingClientRect: function () {
        return {
          left: containerRect.left + objRect.left,
          top: containerRect.top + objRect.top,
          width: objRect.width,
          height: objRect.height,
          right: containerRect.left + objRect.left + objRect.width,
          bottom: containerRect.top + objRect.top + objRect.height,
          x: containerRect.left + objRect.left,
          y: containerRect.top + objRect.top
        };
      }
    };
    menuEl.style.display = 'flex';
    menuEl.setAttribute('aria-hidden', 'false');
    menuEl.style.left = '0';
    menuEl.style.top = '0';
    var fl = window.FloatingUIDOM || (typeof FloatingUIDOM !== 'undefined' ? FloatingUIDOM : null);
    var computePosition = fl && fl.computePosition;
    if (computePosition) {
      try {
        computePosition(virtualRef, menuEl, { placement: 'bottom' }).then(function (pos) {
          Object.assign(menuEl.style, { left: pos.x + 'px', top: pos.y + 'px' });
        }).catch(function () {
          var r = virtualRef.getBoundingClientRect();
          menuEl.style.left = r.left + 'px';
          menuEl.style.top = (r.bottom + 4) + 'px';
        });
      } catch (err) {
        var r = virtualRef.getBoundingClientRect();
        menuEl.style.left = r.left + 'px';
        menuEl.style.top = (r.bottom + 4) + 'px';
      }
    } else {
      var r = virtualRef.getBoundingClientRect();
      menuEl.style.left = r.left + 'px';
      menuEl.style.top = (r.bottom + 4) + 'px';
    }
  }

  function setupContextMenuHandlers() {
    var menuEl = getContextMenuEl();
    if (!menuEl) return;
    var deleteBtn = document.getElementById('context-menu-delete');
    var fontSizeSelect = document.getElementById('context-menu-font-size');
    if (deleteBtn) {
      deleteBtn.addEventListener('click', function () {
        removeSelectedFromAllCanvases();
        hideContextMenu();
      });
    }
    if (fontSizeSelect) {
      fontSizeSelect.addEventListener('change', function () {
        if (activeContextCanvas && activeContextCanvas.getActiveObject()) {
          var fs = parseInt(fontSizeSelect.value, 10);
          activeContextCanvas.getActiveObject().set('fontSize', fs);
          activeContextCanvas.requestRenderAll();
          syncPageToState(activeContextPageIndex);
        }
      });
    }
    document.addEventListener('click', function (e) {
      if (!menuEl || menuEl.getAttribute('aria-hidden') === 'true') return;
      if (menuEl.contains(e.target)) return;
      var inCanvas = false;
      Object.keys(fabricCanvases).forEach(function (key) {
        var entry = fabricCanvases[key];
        if (entry && entry.canvas && entry.canvas.getElement().parentNode && entry.canvas.getElement().parentNode.contains(e.target)) inCanvas = true;
      });
      if (!inCanvas) hideContextMenu();
    });
  }

  function removeSelectedFromAllCanvases() {
    Object.keys(fabricCanvases).forEach(function (pageKey) {
      var pageIndex = parseInt(pageKey, 10);
      var entry = fabricCanvases[pageIndex];
      if (!entry || !entry.canvas) return;
      var canvas = entry.canvas;
      var active = canvas.getActiveObjects && canvas.getActiveObjects();
      if (active && active.length > 0) {
        active.forEach(function (obj) { canvas.remove(obj); });
        syncPageToState(pageIndex);
        canvas.discardActiveObject();
        canvas.requestRenderAll();
      } else if (canvas.getActiveObject()) {
        canvas.remove(canvas.getActiveObject());
        syncPageToState(pageIndex);
        canvas.discardActiveObject();
        canvas.requestRenderAll();
      }
    });
  }

  window.PdfEditor.fabricLayer = {
    whenFabricReady: whenFabricReady,
    initFabricForPage: initFabricForPage,
    disposeFabricForPage: disposeFabricForPage,
    serializePageToMarkups: serializePageToMarkups,
    serializeAllFabricToMarkups: serializeAllFabricToMarkups,
    loadMarkupsIntoFabric: loadMarkupsIntoFabric,
    loadMarkupsForPage: loadMarkupsForPage,
    setSelectionEnabled: setSelectionEnabled,
    removeSelectedFromAllCanvases: removeSelectedFromAllCanvases
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupContextMenuHandlers);
  } else {
    setupContextMenuHandlers();
  }
})();
