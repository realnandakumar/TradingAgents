/** Trading Bulls wordmark glyph — bull head + rising bar. */
export function TradingBullsMark({
  className = "h-7 w-7",
  title = "Trading Bulls",
}: {
  className?: string;
  title?: string;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label={title}
    >
      <title>{title}</title>
      {/* Horns */}
      <path
        d="M6 11c0-4 2.5-7 5-7 1.2 0 2.2.6 3 1.6C12.8 4.4 14.2 3.5 16 3.5c1.8 0 3.2.9 4 2.1.8-1 1.8-1.6 3-1.6 2.5 0 5 3 5 7"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-bull"
      />
      {/* Head */}
      <path
        d="M10.5 13.5c0 5.2 2.4 9.5 5.5 9.5s5.5-4.3 5.5-9.5c0-1.8-1.1-3.2-2.6-3.8-.9-.3-1.9-.5-2.9-.5s-2 .2-2.9.5c-1.5.6-2.6 2-2.6 3.8Z"
        fill="currentColor"
        className="text-bull"
      />
      {/* Snout */}
      <path
        d="M13.2 20.5c.8 1.6 1.8 2.5 2.8 2.5s2-.9 2.8-2.5"
        stroke="var(--background)"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      {/* Eyes */}
      <circle cx="13.6" cy="14.2" r="1.1" fill="var(--background)" />
      <circle cx="18.4" cy="14.2" r="1.1" fill="var(--background)" />
      {/* Rising candle mark */}
      <path
        d="M24.5 22.5V17M24.5 17l2.2 2.2M24.5 17l-2.2 2.2"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-accent"
      />
    </svg>
  );
}
