"use client";
/**
 * useSnippetHistory — تراجع/إعادة (undo/redo) لتحرير القصاصات.
 *
 * المصدر: محادثة DeepSeek (المرحلة 2) — مُكيَّف: الأنواع تُستورد من
 * "@/lib/snippet-ops" (لا من konva-helpers — المحرر في هذا المستودع
 * canvas-based وليس react-konva).
 *
 * reducer بثلاث خانات (past/present/future) مع حد 50 خطوة.
 */
import { useCallback, useReducer } from "react";
import type { SnippetLike } from "@/lib/snippet-ops";

type State<T> = {
  present: T[];
  past: T[][];
  future: T[][];
};

type Action<T> =
  | { type: "SET"; items: T[] }
  | { type: "MUTATE"; fn: (s: T[]) => T[] }
  | { type: "UNDO" }
  | { type: "REDO" }
  | { type: "CLEAR_HISTORY" };

const MAX_HISTORY = 50;

function reducer<T>(state: State<T>, action: Action<T>): State<T> {
  switch (action.type) {
    case "SET":
      return { present: action.items, past: [], future: [] };

    case "MUTATE": {
      const next = action.fn(state.present);
      if (next === state.present) return state; // لا تغيير
      return {
        past: [...state.past.slice(-MAX_HISTORY + 1), state.present],
        present: next,
        future: [],
      };
    }

    case "UNDO": {
      if (state.past.length === 0) return state;
      const previous = state.past[state.past.length - 1];
      return {
        past: state.past.slice(0, -1),
        present: previous,
        future: [state.present, ...state.future].slice(0, MAX_HISTORY),
      };
    }

    case "REDO": {
      if (state.future.length === 0) return state;
      const next = state.future[0];
      return {
        past: [...state.past, state.present].slice(-MAX_HISTORY),
        present: next,
        future: state.future.slice(1),
      };
    }

    case "CLEAR_HISTORY":
      return { ...state, past: [], future: [] };

    default:
      return state;
  }
}

export function useSnippetHistory<T extends SnippetLike>(initial: T[] = []) {
  const [state, dispatch] = useReducer(reducer<T>, {
    present: initial,
    past: [],
    future: [],
  });

  const setAll = useCallback(
    (items: T[]) => dispatch({ type: "SET", items }),
    [],
  );

  const mutate = useCallback(
    (fn: (s: T[]) => T[]) => dispatch({ type: "MUTATE", fn }),
    [],
  );

  const undo = useCallback(() => dispatch({ type: "UNDO" }), []);
  const redo = useCallback(() => dispatch({ type: "REDO" }), []);
  const clearHistory = useCallback(
    () => dispatch({ type: "CLEAR_HISTORY" }),
    [],
  );

  return {
    snippets: state.present,
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
    setAll,
    mutate,
    undo,
    redo,
    clearHistory,
  };
}
