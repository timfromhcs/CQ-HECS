// Keyboard cursor movement for the circuit composer (W4-12). Pure so it can be tested in Node.

export interface Cursor { col: number; q: number }

/** Hard cap on columns reachable by keyboard so the grid cannot grow without bound. */
export const MAX_COLS = 64;

export type NavKey = "ArrowUp" | "ArrowDown" | "ArrowLeft" | "ArrowRight" | "Home" | "End" | "PageUp" | "PageDown";

export function isNavKey(key: string): key is NavKey {
  return ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"].includes(key);
}

/** Move the cursor; the result is always inside `0..numQubits-1` x `0..cols-1` (cols <= MAX_COLS). */
export function moveCursor(c: Cursor, key: NavKey, numQubits: number, cols: number): Cursor {
  const maxQ = Math.max(0, numQubits - 1);
  const maxC = Math.max(0, Math.min(cols, MAX_COLS) - 1);
  let { col, q } = c;
  switch (key) {
    case "ArrowUp": q -= 1; break;
    case "ArrowDown": q += 1; break;
    case "ArrowLeft": col -= 1; break;
    case "ArrowRight": col += 1; break;
    case "Home": col = 0; break;
    case "End": col = maxC; break;
    case "PageUp": q = 0; break;
    case "PageDown": q = maxQ; break;
  }
  return { col: Math.min(maxC, Math.max(0, col)), q: Math.min(maxQ, Math.max(0, q)) };
}
