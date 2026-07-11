(() => {
  'use strict';

  const GLYPH_VALUES = '0123456789ABCDEF'.split('');

  function normalize(value) {
    return String(value || '')
      .toUpperCase()
      .replace(/[^0-9A-F]/g, '')
      .slice(0, 12);
  }

  function isComplete(value) {
    return normalize(value).length === 12;
  }

  function imagePath(value) {
    const glyph = normalize(value).slice(0, 1);
    return glyph ? `assets/glyphs/${glyph}.png` : '';
  }

  function glyphHtml(value, options = {}) {
    const glyph = normalize(value).slice(0, 1);
    const sizeClass = options.compact ? ' compact' : '';
    if (!glyph) {
      return `<span class="portal-glyph empty${sizeClass}" aria-hidden="true"><span>?</span></span>`;
    }
    return `<span class="portal-glyph${sizeClass}" data-glyph="${glyph}" title="Portal glyph ${glyph}"><img src="${imagePath(glyph)}" alt="Portal glyph ${glyph}"><small>${glyph}</small></span>`;
  }

  function codeHtml(value, options = {}) {
    const code = normalize(value);
    const padded = code.padEnd(12, '?');
    return [...padded].map((glyph) => glyph === '?' ? glyphHtml('', options) : glyphHtml(glyph, options)).join('');
  }

  function render(target, value, options = {}) {
    const element = typeof target === 'string' ? document.querySelector(target) : target;
    if (!element) return;
    const code = normalize(value);
    element.classList.add('portal-glyph-row');
    if (options.compact) element.classList.add('compact');
    element.innerHTML = codeHtml(code, options);
    element.dataset.glyphCode = code;
    element.setAttribute('aria-label', code.length === 12 ? `Portal address ${code.split('').join(' ')}` : 'Incomplete portal address');
  }

  function bindInput(input, target, statusTarget) {
    const inputElement = typeof input === 'string' ? document.querySelector(input) : input;
    const targetElement = typeof target === 'string' ? document.querySelector(target) : target;
    const statusElement = typeof statusTarget === 'string' ? document.querySelector(statusTarget) : statusTarget;
    if (!inputElement || !targetElement) return;

    const update = () => {
      const caret = inputElement.selectionStart;
      const normalized = normalize(inputElement.value);
      inputElement.value = normalized;
      if (Number.isInteger(caret)) inputElement.setSelectionRange(Math.min(caret, normalized.length), Math.min(caret, normalized.length));
      render(targetElement, normalized);
      if (statusElement) {
        statusElement.textContent = normalized.length === 12
          ? 'Complete 12-glyph portal address.'
          : `${normalized.length} of 12 glyphs entered.`;
        statusElement.className = `glyph-input-status${normalized.length === 12 ? ' complete' : ''}`;
      }
    };

    inputElement.addEventListener('input', update);
    update();
  }

  async function copy(value) {
    const code = normalize(value);
    if (!code) return false;
    await navigator.clipboard.writeText(code);
    return true;
  }

  window.WCGlyphs = {
    values: GLYPH_VALUES,
    normalize,
    isComplete,
    imagePath,
    glyphHtml,
    codeHtml,
    render,
    bindInput,
    copy,
  };
})();
