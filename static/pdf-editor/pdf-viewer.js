/* pdf-editor/pdf-viewer.js - PDF loading, rendering, zoom, page virtualization */
(function () {
  'use strict';
  var state = window.PdfEditor.state;
  var config = window.PdfEditor.config;
  var container = document.getElementById('pdf-container');

  var PAGE_CACHE_SIZE = 15;
  var ROOT_MARGIN = '200px';
  var pageInfos = [];
  var pageDimensions = [];
  var intersectionObserver = null;
  var scrollWrapper = null;

  function whenPdfJsReady() {
    if (typeof pdfjsLib !== 'undefined') return Promise.resolve();
    return new Promise(function (resolve) {
      function check() {
        if (typeof pdfjsLib !== 'undefined') { resolve(); return; }
        requestAnimationFrame(check);
      }
      requestAnimationFrame(check);
    });
  }

  function showIframeFallback() {
    container.innerHTML = '';
    var wrap = document.createElement('div');
    wrap.style.cssText = 'flex:1;display:flex;overflow:auto;';
    var iframe = document.createElement('iframe');
    iframe.id = 'pdf-iframe';
    iframe.src = '/api/documents/' + config.docId + '/file';
    iframe.style.cssText = 'width:100%;height:100%;min-height:80vh;border:none;transform-origin:0 0;';
    wrap.appendChild(iframe);
    container.appendChild(wrap);
  }

  function createPlaceholder(w, h) {
    var placeholder = document.createElement('div');
    placeholder.className = 'page-placeholder';
    placeholder.style.cssText = 'width:' + w + 'px;height:' + h + 'px;display:flex;align-items:center;justify-content:center;background:#3d4043;color:#9ca3af;font-size:0.875rem;';
    placeholder.textContent = 'Loading...';
    return placeholder;
  }

  function getRenderedPageIndices() {
    return pageInfos.filter(function (p) { return p.rendered; }).map(function (p) { return p.pageIndex; });
  }

  function evictFurthestFromVisible(visibleSet) {
    var rendered = getRenderedPageIndices();
    if (rendered.length < PAGE_CACHE_SIZE) return null;
    var minVisible = Math.min.apply(null, visibleSet);
    var maxVisible = Math.max.apply(null, visibleSet);
    var furthest = null;
    var maxDist = -1;
    rendered.forEach(function (idx) {
      if (visibleSet.indexOf(idx) >= 0) return;
      var dist = Math.min(
        idx < minVisible ? minVisible - idx : 9999,
        idx > maxVisible ? idx - maxVisible : 9999
      );
      if (dist > maxDist) { maxDist = dist; furthest = idx; }
    });
    return furthest;
  }

  function evictPage(pageIndex) {
    var info = pageInfos[pageIndex];
    if (!info || !info.rendered) return;
    var placeholder = createPlaceholder(info.width, info.height);
    while (info.el.firstChild) info.el.removeChild(info.el.firstChild);
    info.el.appendChild(placeholder);
    info.placeholderEl = placeholder;
    info.rendered = false;
    info.canvas = null;
    info.overlay = null;
  }

  async function renderPage(pageIndex) {
    var info = pageInfos[pageIndex];
    if (!info || !state.pdfDoc || info.rendered) return;
    var visibleSet = getRenderedPageIndices().concat([pageIndex]);
    var toEvict = evictFurthestFromVisible(visibleSet);
    if (toEvict != null) evictPage(toEvict);

    var page = await state.pdfDoc.getPage(pageIndex + 1);
    var viewport = page.getViewport({ scale: state.scale });
    var w = viewport.width;
    var h = viewport.height;

    var canvas = document.createElement('canvas');
    canvas.height = h;
    canvas.width = w;
    var ctx = canvas.getContext('2d');
    await page.render({ canvasContext: ctx, viewport: viewport }).promise;

    var overlay = document.createElement('div');
    overlay.className = 'page-annotations';
    overlay.style.width = w + 'px';
    overlay.style.height = h + 'px';
    overlay.dataset.page = pageIndex;

    if (info.placeholderEl) info.placeholderEl.remove();
    while (info.el.firstChild) info.el.removeChild(info.el.firstChild);
    info.el.appendChild(canvas);
    info.el.appendChild(overlay);
    info.canvas = canvas;
    info.overlay = overlay;
    info.rendered = true;
    info.placeholderEl = null;

    window.PdfEditor.annotationLayer.setupAnnotationLayer(info.el, pageIndex, w, h);
    window.PdfEditor.annotationLayer.renderMarkups();
  }

  function onIntersection(entries) {
    var visible = [];
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      var pageIndex = parseInt(entry.target.dataset.pageIndex, 10);
      if (isNaN(pageIndex)) return;
      visible.push(pageIndex);
    });
    visible.forEach(function (idx) {
      if (pageInfos[idx] && !pageInfos[idx].rendered) {
        renderPage(idx);
      }
    });
  }

  async function buildPageStructure() {
    if (!state.pdfDoc) return;
    var numPages = state.pdfDoc.numPages;
    pageDimensions = [];
    for (var i = 1; i <= numPages; i++) {
      var page = await state.pdfDoc.getPage(i);
      var viewport = page.getViewport({ scale: state.scale });
      pageDimensions.push({ w: viewport.width, h: viewport.height });
    }

    container.innerHTML = '';
    container.classList.add('pdf-pages-mode');
    scrollWrapper = document.createElement('div');
    scrollWrapper.className = 'pdf-scroll-wrapper';
    scrollWrapper.style.cssText = 'flex:1;overflow-y:auto;display:flex;flex-direction:column;align-items:center;padding:1rem 0;';

    pageInfos = [];
    for (var j = 0; j < numPages; j++) {
      var dim = pageDimensions[j];
      var pageWrap = document.createElement('div');
      pageWrap.className = 'page-wrap';
      pageWrap.dataset.pageIndex = j;
      pageWrap.style.width = dim.w + 'px';

      var placeholder = createPlaceholder(dim.w, dim.h);
      pageWrap.appendChild(placeholder);

      scrollWrapper.appendChild(pageWrap);
      pageInfos.push({
        el: pageWrap,
        pageIndex: j,
        width: dim.w,
        height: dim.h,
        placeholderEl: placeholder,
        rendered: false,
        canvas: null,
        overlay: null
      });
    }
    container.appendChild(scrollWrapper);

    if (intersectionObserver) intersectionObserver.disconnect();
    intersectionObserver = new IntersectionObserver(onIntersection, {
      root: scrollWrapper,
      rootMargin: ROOT_MARGIN,
      threshold: 0
    });
    pageInfos.forEach(function (p) {
      intersectionObserver.observe(p.el);
    });

    window.PdfEditor.annotationLayer.renderMarkups();
  }

  async function renderPdf() {
    if (!state.pdfDoc) return;
    await buildPageStructure();
  }

  async function loadPdf() {
    try {
      var res = await fetch('/api/documents/' + config.docId + '/file');
      var blob = await res.blob();
      var data = await blob.arrayBuffer();
      state.pdfDoc = await pdfjsLib.getDocument({ data: data }).promise;
      try {
        var saved = sessionStorage.getItem('pdf-zoom-' + config.docId);
        if (saved) { var s = parseFloat(saved); if (s >= 0.5 && s <= 3) state.scale = s; }
      } catch (e) { /* ignore */ }
      window.PdfEditor.main.updateZoomDisplay();
      await window.PdfEditor.contextSelector.loadLinkedOptions();
      if (state.currentLinkedType == null && state.currentLinkedId == null && state.linkedOptions.length > 0) {
        var first = state.linkedOptions[0];
        state.currentLinkedType = first.linked_type;
        state.currentLinkedId = first.linked_id;
        document.getElementById('context-select').value = JSON.stringify({ t: first.linked_type, i: first.linked_id });
      }
      await window.PdfEditor.contextSelector.loadMarkups();
      await renderPdf();
    } catch (e) {
      showIframeFallback();
    }
  }

  function zoomIn() {
    state.scale = Math.min(3, state.scale + 0.25);
    window.PdfEditor.main.updateZoomDisplay();
    try { sessionStorage.setItem('pdf-zoom-' + config.docId, String(state.scale)); } catch (e) { /* ignore */ }
    if (state.pdfDoc) {
      renderPdf();
    } else {
      var wrap = document.getElementById('pdf-display-wrap');
      if (wrap) {
        wrap.style.transform = 'scale(' + state.scale + ')';
        wrap.style.width = (100 / state.scale) + '%';
        wrap.style.height = (100 / state.scale) + '%';
      }
    }
  }

  function zoomOut() {
    state.scale = Math.max(0.5, state.scale - 0.25);
    window.PdfEditor.main.updateZoomDisplay();
    try { sessionStorage.setItem('pdf-zoom-' + config.docId, String(state.scale)); } catch (e) { /* ignore */ }
    if (state.pdfDoc) {
      renderPdf();
    } else {
      var wrap = document.getElementById('pdf-display-wrap');
      if (wrap) {
        wrap.style.transform = 'scale(' + state.scale + ')';
        wrap.style.width = (100 / state.scale) + '%';
        wrap.style.height = (100 / state.scale) + '%';
      }
    }
  }

  window.PdfEditor.pdfViewer = {
    whenPdfJsReady: whenPdfJsReady,
    loadPdf: loadPdf,
    renderPdf: renderPdf,
    showIframeFallback: showIframeFallback,
    zoomIn: zoomIn,
    zoomOut: zoomOut,
    getPageInfos: function () { return pageInfos; }
  };
})();
