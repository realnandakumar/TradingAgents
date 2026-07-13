import Link from "next/link";

import { shortSymbol } from "@/lib/format";

export function ChartTickerLink({
  ticker,
  desk,
  intraday,
  className = "hover:text-accent",
  children,
}: {
  ticker: string;
  desk?: string;
  intraday?: boolean;
  className?: string;
  children?: React.ReactNode;
}) {
  const params = new URLSearchParams({ ticker });
  if (desk) params.set("desk", desk);
  if (intraday) params.set("intraday", "1");
  return (
    <Link href={`/charts?${params.toString()}`} className={className}>
      {children ?? shortSymbol(ticker)}
    </Link>
  );
}
