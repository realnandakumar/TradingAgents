"use client";

import { useMemo } from "react";

export function MarkdownViewer({ text }: { text: string }) {
  const blocks = useMemo(() => {
    const lines = text.split("\n");
    const out: { type: "h1" | "h2" | "h3" | "p"; content: string }[] = [];
    let buf: string[] = [];

    const flush = () => {
      if (buf.length) {
        out.push({ type: "p", content: buf.join("\n") });
        buf = [];
      }
    };

    for (const line of lines) {
      if (line.startsWith("# ")) {
        flush();
        out.push({ type: "h1", content: line.slice(2) });
      } else if (line.startsWith("## ")) {
        flush();
        out.push({ type: "h2", content: line.slice(3) });
      } else if (line.startsWith("### ")) {
        flush();
        out.push({ type: "h3", content: line.slice(4) });
      } else {
        buf.push(line);
      }
    }
    flush();
    return out;
  }, [text]);

  return (
    <div className="space-y-3 text-sm leading-relaxed">
      {blocks.map((b, i) => {
        if (b.type === "h1")
          return (
            <h2 key={i} className="text-lg font-semibold text-foreground">
              {b.content}
            </h2>
          );
        if (b.type === "h2")
          return (
            <h3 key={i} className="text-base font-medium text-accent mt-4">
              {b.content}
            </h3>
          );
        if (b.type === "h3")
          return (
            <h4 key={i} className="text-sm font-medium text-foreground mt-3">
              {b.content}
            </h4>
          );
        return (
          <pre key={i} className="whitespace-pre-wrap font-sans text-muted text-sm">
            {b.content}
          </pre>
        );
      })}
    </div>
  );
}
