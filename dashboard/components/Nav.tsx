"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const NAV_GROUPS = [
  {
    label: "Home",
    links: [
      { href: "/", label: "Overview" },
      { href: "/command-center", label: "Command center" },
      { href: "/overlaps", label: "Overlaps" },
      { href: "/data-health", label: "Data health" },
      { href: "/positions", label: "RS desk" },
      { href: "/screens", label: "Screens" },
    ],
  },
  {
    label: "Research",
    links: [
      { href: "/charts", label: "Charts" },
      { href: "/analyze", label: "AI Analyze" },
      { href: "/tech-desk", label: "Tech desk" },
    ],
  },
  {
    label: "Desks",
    links: [
      { href: "/swing", label: "Swing" },
      { href: "/momentum", label: "Momentum" },
      { href: "/nss", label: "NSS" },
      { href: "/supertrend-rsi", label: "ST+RSI" },
      { href: "/trama", label: "TRAMA" },
      { href: "/gap-fill", label: "Gap fill" },
      { href: "/nw-envelope", label: "NW Envelope" },
      { href: "/pattern-forecast", label: "Pattern" },
    ],
  },
  {
    label: "Screeners",
    links: [{ href: "/chart-patterns", label: "Chart patterns" }],
  },
] as const;

function isActive(path: string, href: string) {
  return href === "/" ? path === "/" : path.startsWith(href);
}

export function Nav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="border-b border-border bg-surface/60 backdrop-blur sticky top-0 z-30">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-4">
        <Link href="/" className="font-semibold tracking-tight shrink-0">
          <span className="text-accent">RS</span>Screener
          <span className="text-muted font-normal"> · India</span>
        </Link>

        <nav className="hidden lg:flex items-center gap-1 text-sm flex-1 min-w-0 overflow-x-auto">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="flex items-center gap-0.5 shrink-0">
              <span className="text-[10px] uppercase text-muted px-2 hidden xl:inline">
                {group.label}
              </span>
              {group.links.map((l) => (
                <Link
                  key={l.href}
                  href={l.href}
                  className={`px-2.5 py-1.5 rounded-lg whitespace-nowrap transition-colors ${
                    isActive(path, l.href)
                      ? "bg-surface-2 text-foreground"
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  {l.label}
                </Link>
              ))}
              <span className="text-border mx-1 hidden xl:inline">|</span>
            </div>
          ))}
        </nav>

        <button
          type="button"
          className="lg:hidden ml-auto px-3 py-1.5 rounded-lg border border-border text-sm"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          Menu
        </button>
      </div>

      {open ? (
        <div className="lg:hidden border-t border-border bg-surface max-h-[70vh] overflow-y-auto">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="px-4 py-3 border-b border-border/60">
              <div className="text-[10px] uppercase tracking-wide text-muted mb-2">
                {group.label}
              </div>
              <div className="flex flex-wrap gap-2">
                {group.links.map((l) => (
                  <Link
                    key={l.href}
                    href={l.href}
                    onClick={() => setOpen(false)}
                    className={`px-3 py-1.5 rounded-lg text-sm ${
                      isActive(path, l.href)
                        ? "bg-surface-2 text-foreground"
                        : "text-muted border border-border"
                    }`}
                  >
                    {l.label}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </header>
  );
}
