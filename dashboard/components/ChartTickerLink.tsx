import Link from "next/link";

import { shortSymbol } from "@/lib/format";

export function ChartTickerLink({
  ticker,
  desk,
  intraday,
  patternId,
  className = "hover:text-accent",
  children,
}: {
  ticker: string;
  desk?: string;
  intraday?: boolean;
  patternId?: string;
  className?: string;
  children?: React.ReactNode;
}) {
  const params = new URLSearchParams({ ticker });
  if (desk) params.set("desk", desk);
  if (intraday) params.set("intraday", "1");
  if (patternId) params.set("pattern_id", patternId);
  return (
    <Link href={`/charts?${params.toString()}`} className={className}>
      {children ?? shortSymbol(ticker)}
    </Link>
  );
}
