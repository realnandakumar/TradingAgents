"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/analyze", label: "AI Analyze" },
  { href: "/swing", label: "Swing desk" },
  { href: "/momentum", label: "Momentum desk" },
  { href: "/nss", label: "NSS desk" },
  { href: "/supertrend-rsi", label: "ST+RSI desk" },
  { href: "/trama", label: "TRAMA desk" },
  { href: "/nw-envelope", label: "NW Envelope" },
  { href: "/pattern-forecast", label: "Pattern desk" },
  { href: "/screens", label: "Screens" },
  { href: "/positions", label: "Positions" },
];

export function Nav() {
  const path = usePathname();
  return (
    <header className="border-b border-border bg-surface/60 backdrop-blur sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-6">
        <Link href="/" className="font-semibold tracking-tight">
          <span className="text-accent">RS</span>Screener
          <span className="text-muted font-normal"> · India</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {LINKS.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`px-3 py-1.5 rounded-lg transition-colors ${
                  active ? "bg-surface-2 text-foreground" : "text-muted hover:text-foreground"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
