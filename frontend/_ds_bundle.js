/* @ds-bundle: {"format":3,"namespace":"QMSDesignSystem","components":[{"name":"ChatComposer","sourcePath":"components/chat/ChatComposer.jsx"},{"name":"MessageBubble","sourcePath":"components/chat/MessageBubble.jsx"},{"name":"ScorePill","sourcePath":"components/chat/ScorePill.jsx"},{"name":"SourceCard","sourcePath":"components/chat/SourceCard.jsx"},{"name":"SourceDrawer","sourcePath":"components/chat/SourceDrawer.jsx"},{"name":"TypingIndicator","sourcePath":"components/chat/TypingIndicator.jsx"},{"name":"Avatar","sourcePath":"components/core/Avatar.jsx"},{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"}],"sourceHashes":{"components/chat/ChatComposer.jsx":"f4ab5f98bbb8","components/chat/MessageBubble.jsx":"1eae0b3570af","components/chat/ScorePill.jsx":"9fd7f2ff84dc","components/chat/SourceCard.jsx":"41efb0ddd829","components/chat/SourceDrawer.jsx":"0058bb19751c","components/chat/TypingIndicator.jsx":"d172cc26bae5","components/core/Avatar.jsx":"74501dbf96d6","components/core/Badge.jsx":"86fe9929f9a4","components/core/Button.jsx":"cd20195a6ac4","components/core/Card.jsx":"07aaa2b5fae4","components/core/IconButton.jsx":"0a776669486f","components/forms/Input.jsx":"83bb52169fe3"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.QMSDesignSystem = window.QMSDesignSystem || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/chat/ChatComposer.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function SendIcon() {
  return /*#__PURE__*/React.createElement("svg", {
    width: "18",
    height: "18",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M22 2 11 13"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M22 2 15 22l-4-9-9-4 20-7z"
  }));
}

/**
 * Message composer — auto-growing textarea + blue send button.
 * Enter sends; Shift+Enter inserts a newline.
 */
function ChatComposer({
  value,
  onChange,
  onSend,
  placeholder = 'Ask about a procedure, policy, or test plan…',
  disabled = false,
  hint = 'Answers cite retrieved documents. Verify against the controlled copy.',
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const taRef = React.useRef(null);
  React.useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }, [value]);
  const send = () => {
    if (!disabled && value && value.trim()) onSend && onSend(value.trim());
  };
  const canSend = !disabled && value && value.trim().length > 0;
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      width: '100%',
      ...rest.style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      gap: 10,
      background: 'var(--gray-0)',
      border: `1px solid ${focus ? 'var(--blue-400)' : 'var(--border-default)'}`,
      borderRadius: 'var(--radius-lg)',
      boxShadow: focus ? 'var(--focus-ring)' : 'var(--shadow-sm)',
      padding: '8px 8px 8px 16px',
      transition: 'border-color var(--dur-fast) var(--ease-out), box-shadow var(--dur-fast) var(--ease-out)'
    }
  }, /*#__PURE__*/React.createElement("textarea", {
    ref: taRef,
    rows: 1,
    value: value,
    onChange: onChange,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    onKeyDown: e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    },
    placeholder: placeholder,
    disabled: disabled,
    style: {
      flex: 1,
      resize: 'none',
      border: 'none',
      outline: 'none',
      background: 'transparent',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--fs-base)',
      lineHeight: 'var(--lh-normal)',
      color: 'var(--text-strong)',
      padding: '8px 0',
      maxHeight: 160
    }
  }), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: send,
    disabled: !canSend,
    "aria-label": "Send",
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: 40,
      height: 40,
      flex: 'none',
      borderRadius: 'var(--radius-md)',
      border: 'none',
      background: canSend ? 'var(--blue-500)' : 'var(--gray-200)',
      color: canSend ? '#fff' : 'var(--gray-400)',
      cursor: canSend ? 'pointer' : 'not-allowed',
      transition: 'background var(--dur-fast) var(--ease-out)'
    }
  }, /*#__PURE__*/React.createElement(SendIcon, null))), hint && /*#__PURE__*/React.createElement("p", {
    style: {
      margin: '8px 2px 0',
      fontSize: '11.5px',
      color: 'var(--text-faint)',
      textAlign: 'center'
    }
  }, hint));
}
Object.assign(__ds_scope, { ChatComposer });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/ChatComposer.jsx", error: String((e && e.message) || e) }); }

// components/chat/ScorePill.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Relevance score indicator for a retrieved source (0–1).
 * Colour shifts green→amber→gray by confidence.
 */
function ScorePill({
  score = 0,
  showLabel = true,
  ...rest
}) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? 'var(--score-high)' : score >= 0.5 ? 'var(--score-mid)' : 'var(--score-low)';
  const bg = score >= 0.8 ? 'var(--green-50)' : score >= 0.5 ? 'var(--amber-50)' : 'var(--gray-100)';
  return /*#__PURE__*/React.createElement("span", _extends({
    title: `Relevance ${pct}%`,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '2px 8px',
      borderRadius: 'var(--radius-pill)',
      background: bg,
      color,
      fontFamily: 'var(--font-mono)',
      fontSize: '11.5px',
      fontWeight: 600,
      lineHeight: 1.4,
      ...rest.style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: color,
      flex: 'none'
    }
  }), score.toFixed(2), showLabel && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-faint)',
      fontWeight: 500
    }
  }, "match"));
}
Object.assign(__ds_scope, { ScorePill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/ScorePill.jsx", error: String((e && e.message) || e) }); }

// components/chat/TypingIndicator.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Assistant "thinking" indicator — three pulsing dots in a bot bubble.
 */
function TypingIndicator({
  label = 'Searching documents',
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      ...rest.style
    }
  }, rest), /*#__PURE__*/React.createElement("style", null, `@keyframes qms-blink{0%,80%,100%{opacity:.25;transform:translateY(0)}40%{opacity:1;transform:translateY(-2px)}}`), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'inline-flex',
      gap: 5,
      padding: '12px 15px',
      background: 'var(--bubble-bot-bg)',
      border: '1px solid var(--bubble-bot-border)',
      borderRadius: '14px 14px 14px 4px',
      boxShadow: 'var(--shadow-xs)'
    }
  }, [0, 1, 2].map(i => /*#__PURE__*/React.createElement("span", {
    key: i,
    style: {
      width: 7,
      height: 7,
      borderRadius: '50%',
      background: 'var(--blue-400)',
      animation: `qms-blink 1.3s ${i * 0.18}s infinite ease-in-out`
    }
  }))), label && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: '12.5px',
      color: 'var(--text-muted)'
    }
  }, label, "\u2026"));
}
Object.assign(__ds_scope, { TypingIndicator });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/TypingIndicator.jsx", error: String((e && e.message) || e) }); }

// components/core/Avatar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: 28,
  md: 36,
  lg: 44
};
function initials(name = '') {
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0] || '').join('').toUpperCase();
}

/**
 * User / assistant avatar. Renders initials, an image, or a brand mark.
 */
function Avatar({
  name = '',
  src = null,
  size = 'md',
  variant = 'user',
  ...rest
}) {
  const dim = SIZES[size] || SIZES.md;
  const isBot = variant === 'assistant';
  const bg = isBot ? 'var(--blue-500)' : 'var(--gray-200)';
  const color = isBot ? '#fff' : 'var(--gray-700)';
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: dim,
      height: dim,
      flex: 'none',
      borderRadius: 'var(--radius-sm)',
      background: src ? 'transparent' : bg,
      color,
      fontFamily: 'var(--font-sans)',
      fontSize: dim * 0.38,
      fontWeight: 600,
      overflow: 'hidden',
      ...rest.style
    }
  }, rest), src ? /*#__PURE__*/React.createElement("img", {
    src: src,
    alt: name,
    style: {
      width: '100%',
      height: '100%',
      objectFit: 'cover'
    }
  }) : isBot ? /*#__PURE__*/React.createElement("svg", {
    width: dim * 0.56,
    height: dim * 0.56,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("rect", {
    x: "3",
    y: "8",
    width: "18",
    height: "12",
    rx: "3"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M12 8V4"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "3",
    r: "1"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M8 13v2M16 13v2"
  })) : initials(name) || '?');
}
Object.assign(__ds_scope, { Avatar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Avatar.jsx", error: String((e && e.message) || e) }); }

// components/chat/MessageBubble.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * A single chat turn. `role="user"` renders a right-aligned blue bubble;
 * `role="assistant"` renders a left-aligned white bubble. Children below
 * the bubble (e.g. SourceCards) render within the assistant column.
 */
function MessageBubble({
  role = 'assistant',
  children,
  authorName = 'You',
  timestamp,
  footer = null,
  showAvatar = true,
  ...rest
}) {
  const isUser = role === 'user';
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: 'flex',
      flexDirection: isUser ? 'row-reverse' : 'row',
      gap: 12,
      alignItems: 'flex-start',
      ...rest.style
    }
  }, rest), showAvatar && /*#__PURE__*/React.createElement("div", {
    style: {
      paddingTop: 2
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Avatar, {
    variant: isUser ? 'user' : 'assistant',
    name: authorName,
    size: "md"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
      maxWidth: '76%',
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: isUser ? 'var(--bubble-user-bg)' : 'var(--bubble-bot-bg)',
      color: isUser ? 'var(--bubble-user-text)' : 'var(--bubble-bot-text)',
      border: isUser ? 'none' : '1px solid var(--bubble-bot-border)',
      boxShadow: isUser ? 'none' : 'var(--shadow-xs)',
      borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
      padding: '11px 15px',
      fontSize: 'var(--fs-base)',
      lineHeight: 'var(--lh-relaxed)',
      wordBreak: 'break-word'
    }
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      width: '100%',
      marginTop: 8
    }
  }, footer), timestamp && /*#__PURE__*/React.createElement("span", {
    style: {
      marginTop: 4,
      fontSize: '11px',
      color: 'var(--text-faint)'
    }
  }, timestamp)));
}
Object.assign(__ds_scope, { MessageBubble });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/MessageBubble.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const TONES = {
  neutral: {
    bg: 'var(--gray-100)',
    color: 'var(--gray-700)',
    border: 'var(--gray-200)'
  },
  brand: {
    bg: 'var(--blue-50)',
    color: 'var(--blue-600)',
    border: 'var(--blue-100)'
  },
  success: {
    bg: 'var(--green-50)',
    color: 'var(--green-600)',
    border: 'var(--green-50)'
  },
  warning: {
    bg: 'var(--amber-50)',
    color: 'var(--amber-600)',
    border: 'var(--amber-50)'
  },
  danger: {
    bg: 'var(--red-50)',
    color: 'var(--red-600)',
    border: 'var(--red-50)'
  }
};

/**
 * Compact status / category label.
 */
function Badge({
  children,
  tone = 'neutral',
  dot = false,
  mono = false,
  ...rest
}) {
  const t = TONES[tone] || TONES.neutral;
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      height: 22,
      padding: '0 9px',
      borderRadius: 'var(--radius-pill)',
      background: t.bg,
      color: t.color,
      border: `1px solid ${t.border}`,
      fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)',
      fontSize: '11.5px',
      fontWeight: 600,
      lineHeight: 1,
      letterSpacing: mono ? 0 : '0.01em',
      whiteSpace: 'nowrap',
      ...rest.style
    }
  }, rest), dot && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: t.color,
      flex: 'none'
    }
  }), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/chat/SourceCard.jsx
try { (() => {
function FileIcon() {
  return /*#__PURE__*/React.createElement("svg", {
    width: "16",
    height: "16",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M14 3v5h5"
  }));
}
function Chevron({
  open
}) {
  return /*#__PURE__*/React.createElement("svg", {
    width: "16",
    height: "16",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      transform: open ? 'rotate(180deg)' : 'none',
      transition: 'transform var(--dur-base) var(--ease-out)',
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "M6 9l6 6 6-6"
  }));
}

/**
 * Collapsible retrieved-source card shown beneath an assistant answer.
 * Header always visible (doc id, title, score); body (snippet + meta)
 * expands on click. "Open" button surfaces the full preview drawer.
 */
function SourceCard({
  docId,
  title,
  score = 0,
  snippet = '',
  docType = 'Procedure',
  page,
  defaultOpen = false,
  onOpenPreview,
  ...rest
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", {
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-md)',
      boxShadow: hover ? 'var(--shadow-sm)' : 'var(--shadow-xs)',
      overflow: 'hidden',
      transition: 'box-shadow var(--dur-fast) var(--ease-out)',
      ...rest.style
    }
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setOpen(o => !o),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      width: '100%',
      padding: '10px 12px',
      background: 'transparent',
      border: 'none',
      cursor: 'pointer',
      textAlign: 'left'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--blue-500)',
      display: 'inline-flex',
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement(FileIcon, null)), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: '11px',
      fontWeight: 600,
      color: 'var(--text-muted)'
    }
  }, docId), /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    tone: "neutral",
    style: {
      height: 18,
      fontSize: '10.5px',
      padding: '0 7px'
    }
  }, docType)), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: '13.5px',
      fontWeight: 600,
      color: 'var(--text-strong)',
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    }
  }, title)), /*#__PURE__*/React.createElement(__ds_scope.ScorePill, {
    score: score,
    showLabel: false
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-faint)'
    }
  }, /*#__PURE__*/React.createElement(Chevron, {
    open: open
  }))), open && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '0 12px 12px 38px'
    }
  }, /*#__PURE__*/React.createElement("p", {
    style: {
      margin: '0 0 10px',
      fontSize: '13px',
      lineHeight: 'var(--lh-relaxed)',
      color: 'var(--text-body)',
      borderLeft: '2px solid var(--blue-200)',
      paddingLeft: 12
    }
  }, snippet), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 14,
      fontSize: '11.5px',
      color: 'var(--text-muted)'
    }
  }, page != null && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)'
    }
  }, "Page ", page), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: e => {
      e.stopPropagation();
      onOpenPreview && onOpenPreview();
    },
    style: {
      marginLeft: 'auto',
      background: 'transparent',
      border: 'none',
      color: 'var(--text-link)',
      fontFamily: 'var(--font-sans)',
      fontSize: '12px',
      fontWeight: 600,
      cursor: 'pointer',
      padding: 0
    }
  }, "Open document \u2192"))));
}
Object.assign(__ds_scope, { SourceCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/SourceCard.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: {
    height: 32,
    padding: '0 12px',
    font: '13px',
    radius: 'var(--radius-sm)',
    gap: 6
  },
  md: {
    height: 40,
    padding: '0 16px',
    font: '14px',
    radius: 'var(--radius-md)',
    gap: 8
  },
  lg: {
    height: 48,
    padding: '0 22px',
    font: '15px',
    radius: 'var(--radius-md)',
    gap: 8
  }
};
const VARIANTS = {
  primary: {
    base: {
      background: 'var(--blue-500)',
      color: '#fff',
      border: '1px solid var(--blue-500)'
    },
    hover: {
      background: 'var(--blue-600)',
      borderColor: 'var(--blue-600)'
    }
  },
  secondary: {
    base: {
      background: 'var(--gray-0)',
      color: 'var(--text-strong)',
      border: '1px solid var(--border-default)'
    },
    hover: {
      background: 'var(--gray-50)',
      borderColor: 'var(--border-strong)'
    }
  },
  ghost: {
    base: {
      background: 'transparent',
      color: 'var(--text-body)',
      border: '1px solid transparent'
    },
    hover: {
      background: 'var(--gray-100)'
    }
  },
  danger: {
    base: {
      background: 'var(--red-500)',
      color: '#fff',
      border: '1px solid var(--red-500)'
    },
    hover: {
      background: 'var(--red-600)',
      borderColor: 'var(--red-600)'
    }
  }
};

/**
 * Primary action button.
 */
function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  fullWidth = false,
  iconLeft = null,
  iconRight = null,
  onClick,
  type = 'button',
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const s = SIZES[size] || SIZES.md;
  const v = VARIANTS[variant] || VARIANTS.primary;
  const style = {
    display: fullWidth ? 'flex' : 'inline-flex',
    width: fullWidth ? '100%' : undefined,
    alignItems: 'center',
    justifyContent: 'center',
    gap: s.gap,
    height: s.height,
    padding: s.padding,
    borderRadius: s.radius,
    fontFamily: 'var(--font-sans)',
    fontSize: s.font,
    fontWeight: 600,
    lineHeight: 1,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    transition: 'background var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out)',
    whiteSpace: 'nowrap',
    userSelect: 'none',
    ...v.base,
    ...(hover && !disabled ? v.hover : null)
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    style: style,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    onMouseDown: e => {
      if (!disabled) e.currentTarget.style.transform = 'translateY(1px)';
    },
    onMouseUp: e => {
      e.currentTarget.style.transform = 'none';
    }
  }, rest), iconLeft, children, iconRight);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Generic surface container with the elevation system.
 */
function Card({
  children,
  elevation = 'sm',
  padding = 16,
  interactive = false,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const shadows = {
    none: 'none',
    sm: 'var(--shadow-sm)',
    md: 'var(--shadow-md)',
    lg: 'var(--shadow-lg)'
  };
  return /*#__PURE__*/React.createElement("div", _extends({
    onMouseEnter: () => interactive && setHover(true),
    onMouseLeave: () => interactive && setHover(false),
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: hover ? 'var(--shadow-md)' : shadows[elevation],
      padding,
      transition: 'box-shadow var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out)',
      transform: hover ? 'translateY(-1px)' : 'none',
      cursor: interactive ? 'pointer' : 'default',
      ...rest.style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: 30,
  md: 36,
  lg: 42
};

/**
 * Square icon-only button. Pass an SVG/icon node as children.
 */
function IconButton({
  children,
  size = 'md',
  variant = 'ghost',
  active = false,
  disabled = false,
  label,
  onClick,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const dim = SIZES[size] || SIZES.md;
  const variants = {
    ghost: {
      bg: 'transparent',
      color: 'var(--text-muted)',
      hoverBg: 'var(--gray-100)'
    },
    solid: {
      bg: 'var(--blue-500)',
      color: '#fff',
      hoverBg: 'var(--blue-600)'
    },
    outline: {
      bg: 'var(--gray-0)',
      color: 'var(--text-body)',
      hoverBg: 'var(--gray-50)',
      border: '1px solid var(--border-default)'
    }
  };
  const v = variants[variant] || variants.ghost;
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    "aria-label": label,
    title: label,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: dim,
      height: dim,
      borderRadius: 'var(--radius-sm)',
      border: v.border || '1px solid transparent',
      background: active ? 'var(--blue-50)' : hover && !disabled ? v.hoverBg : v.bg,
      color: active ? 'var(--blue-500)' : v.color,
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.5 : 1,
      transition: 'background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out)',
      padding: 0,
      ...rest.style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/chat/SourceDrawer.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function CloseIcon() {
  return /*#__PURE__*/React.createElement("svg", {
    width: "18",
    height: "18",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M18 6 6 18M6 6l12 12"
  }));
}

/**
 * Right-hand detail drawer previewing a source document: header (id, title,
 * score, metadata), the matched excerpt highlighted, then surrounding body.
 */
function SourceDrawer({
  open = false,
  document: doc = null,
  onClose,
  width = 'var(--drawer-w)',
  ...rest
}) {
  if (!doc) return null;
  return /*#__PURE__*/React.createElement("aside", _extends({
    style: {
      position: 'absolute',
      top: 0,
      right: 0,
      height: '100%',
      width,
      maxWidth: '92vw',
      background: 'var(--surface-card)',
      borderLeft: '1px solid var(--border-subtle)',
      boxShadow: 'var(--shadow-drawer)',
      display: 'flex',
      flexDirection: 'column',
      transform: open ? 'translateX(0)' : 'translateX(105%)',
      transition: 'transform var(--dur-slow) var(--ease-out)',
      zIndex: 20,
      ...rest.style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 12,
      padding: '16px 16px 14px',
      borderBottom: '1px solid var(--border-subtle)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: '12px',
      fontWeight: 600,
      color: 'var(--blue-600)'
    }
  }, doc.docId), /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    tone: "brand",
    style: {
      height: 18,
      fontSize: '10.5px',
      padding: '0 7px'
    }
  }, doc.docType || 'Procedure'), doc.score != null && /*#__PURE__*/React.createElement(__ds_scope.ScorePill, {
    score: doc.score,
    showLabel: false
  })), /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      font: 'var(--text-h3)',
      color: 'var(--text-strong)',
      fontSize: '17px'
    }
  }, doc.title)), /*#__PURE__*/React.createElement(__ds_scope.IconButton, {
    label: "Close",
    onClick: onClose
  }, /*#__PURE__*/React.createElement(CloseIcon, null))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: '6px 20px',
      padding: '12px 16px',
      borderBottom: '1px solid var(--border-subtle)',
      background: 'var(--gray-50)'
    }
  }, [['Revision', doc.revision], ['Effective', doc.effective], ['Owner', doc.owner], ['Status', doc.status]].filter(([, v]) => v).map(([k, v]) => /*#__PURE__*/React.createElement("div", {
    key: k,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: '10.5px',
      textTransform: 'uppercase',
      letterSpacing: 'var(--ls-caps)',
      color: 'var(--text-faint)'
    }
  }, k), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: '13px',
      fontWeight: 500,
      color: 'var(--text-body)'
    }
  }, v)))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: 'auto',
      padding: '18px 16px'
    }
  }, doc.excerpt && /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: '11px',
      textTransform: 'uppercase',
      letterSpacing: 'var(--ls-caps)',
      color: 'var(--text-muted)',
      marginBottom: 8
    }
  }, "Matched excerpt ", doc.page != null && `· p.${doc.page}`), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      padding: '12px 14px',
      background: 'var(--blue-50)',
      borderLeft: '3px solid var(--blue-500)',
      borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
      fontSize: '14px',
      lineHeight: 'var(--lh-relaxed)',
      color: 'var(--text-strong)'
    }
  }, doc.excerpt)), (doc.body || []).map((para, i) => /*#__PURE__*/React.createElement("p", {
    key: i,
    style: {
      margin: '0 0 14px',
      fontSize: '14px',
      lineHeight: 'var(--lh-relaxed)',
      color: 'var(--text-body)'
    }
  }, para))));
}
Object.assign(__ds_scope, { SourceDrawer });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/SourceDrawer.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: {
    height: 34,
    font: '13px',
    pad: 10
  },
  md: {
    height: 40,
    font: '14px',
    pad: 12
  },
  lg: {
    height: 46,
    font: '15px',
    pad: 14
  }
};

/**
 * Single-line text input with focus ring and optional adornments.
 */
function Input({
  value,
  onChange,
  placeholder = '',
  size = 'md',
  type = 'text',
  disabled = false,
  invalid = false,
  iconLeft = null,
  iconRight = null,
  fullWidth = true,
  onKeyDown,
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const s = SIZES[size] || SIZES.md;
  const borderColor = invalid ? 'var(--red-500)' : focus ? 'var(--blue-400)' : 'var(--border-default)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      width: fullWidth ? '100%' : undefined,
      height: s.height,
      padding: `0 ${s.pad}px`,
      background: disabled ? 'var(--gray-100)' : 'var(--gray-0)',
      border: `1px solid ${borderColor}`,
      borderRadius: 'var(--radius-md)',
      boxShadow: focus ? 'var(--focus-ring)' : 'none',
      transition: 'border-color var(--dur-fast) var(--ease-out), box-shadow var(--dur-fast) var(--ease-out)',
      boxSizing: 'border-box',
      ...rest.style
    }
  }, iconLeft && /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      color: 'var(--text-muted)',
      flex: 'none'
    }
  }, iconLeft), /*#__PURE__*/React.createElement("input", _extends({
    value: value,
    onChange: onChange,
    onKeyDown: onKeyDown,
    placeholder: placeholder,
    type: type,
    disabled: disabled,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      flex: 1,
      minWidth: 0,
      border: 'none',
      outline: 'none',
      background: 'transparent',
      fontFamily: 'var(--font-sans)',
      fontSize: s.font,
      color: 'var(--text-strong)'
    }
  }, rest)), iconRight && /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      color: 'var(--text-muted)',
      flex: 'none'
    }
  }, iconRight));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

__ds_ns.ChatComposer = __ds_scope.ChatComposer;

__ds_ns.MessageBubble = __ds_scope.MessageBubble;

__ds_ns.ScorePill = __ds_scope.ScorePill;

__ds_ns.SourceCard = __ds_scope.SourceCard;

__ds_ns.SourceDrawer = __ds_scope.SourceDrawer;

__ds_ns.TypingIndicator = __ds_scope.TypingIndicator;

__ds_ns.Avatar = __ds_scope.Avatar;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Input = __ds_scope.Input;

})();
