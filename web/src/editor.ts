// Code editor, loaded on demand (CodeMirror 6 only ships when the Code tab opens).

import { EditorView, basicSetup } from "codemirror";
import { keymap } from "@codemirror/view";
import { HighlightStyle, StreamLanguage, syntaxHighlighting } from "@codemirror/language";
import { tags } from "@lezer/highlight";
import { javascript } from "@codemirror/lang-javascript";
import { oneDark } from "@codemirror/theme-one-dark";
import { Compartment, EditorState, Prec } from "@codemirror/state";

const qasm = StreamLanguage.define<null>({
  token(stream) {
    if (stream.match("//")) { stream.skipToEnd(); return "comment"; }
    if (stream.match(/^"[^"]*"/)) return "string";
    if (stream.match(/^(OPENQASM|include|qreg|creg|measure|reset|barrier|gate|if)\b/)) return "keyword";
    if (stream.match(/^(pi|PI)\b/)) return "atom";
    if (stream.match(/^\d+(\.\d+)?(e[+-]?\d+)?/i)) return "number";
    if (stream.match(/^[a-z][\w]*/)) return "variableName";
    if (stream.match(/^->/)) return "operator";
    stream.next();
    return null;
  },
});

// oneDark's comment/gutter grey (#7d8799, 3.9:1) and keyword violet on the active
// line (4.4:1) miss WCAG AA 4.5:1; these colours keep the palette and reach it.
const contrast = [
  Prec.highest(syntaxHighlighting(HighlightStyle.define([
    { tag: tags.comment, color: "#a3acbf" },
    { tag: tags.keyword, color: "#d7a1ee" },
    { tag: [tags.variableName, tags.propertyName], color: "#ef8a92" },
  ]))),
  // Prec.highest: extensions listed earlier win, so oneDark's own gutter colour
  // would otherwise take precedence over this override.
  Prec.highest(EditorView.theme({
    ".cm-gutters": { color: "#a3acbf" },
    ".cm-activeLineGutter": { color: "#e6e9ef" },
  }, { dark: true })),
];

export interface CodeEditor {
  get(): string;
  set(text: string, lang: "qasm" | "js"): void;
}

export function createEditor(host: HTMLElement, text: string, lang: "qasm" | "js", onRun: () => void, onChange: () => void = () => {}): CodeEditor {
  const language = new Compartment();
  const langExt = (l: "qasm" | "js") => (l === "js" ? javascript() : qasm);
  const view = new EditorView({
    parent: host,
    state: EditorState.create({
      doc: text,
      extensions: [
        keymap.of([{ key: "Mod-Enter", run: () => { onRun(); return true; } }]),
        basicSetup,
        oneDark,
        contrast,
        EditorView.contentAttributes.of({ "aria-label": "Circuit source code (OpenQASM or JavaScript)" }),
        language.of(langExt(lang)),
        EditorView.lineWrapping,
        EditorView.updateListener.of((u) => { if (u.docChanged) onChange(); }),
      ],
    }),
  });
  return {
    get: () => view.state.doc.toString(),
    set: (t, l) => {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: t }, effects: language.reconfigure(langExt(l)) });
    },
  };
}
