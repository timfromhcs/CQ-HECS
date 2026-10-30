// Code editor, loaded on demand (CodeMirror 6 only ships when the Code tab opens).

import { EditorView, basicSetup } from "codemirror";
import { keymap } from "@codemirror/view";
import { StreamLanguage } from "@codemirror/language";
import { javascript } from "@codemirror/lang-javascript";
import { oneDark } from "@codemirror/theme-one-dark";
import { Compartment, EditorState } from "@codemirror/state";

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

export interface CodeEditor {
  get(): string;
  set(text: string, lang: "qasm" | "js"): void;
}

export function createEditor(host: HTMLElement, text: string, lang: "qasm" | "js", onRun: () => void): CodeEditor {
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
        language.of(langExt(lang)),
        EditorView.lineWrapping,
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
