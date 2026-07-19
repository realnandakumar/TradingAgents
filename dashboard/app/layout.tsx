import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { DeskJobStatusBar } from "@/components/DeskJobStatusBar";
import { Nav } from "@/components/Nav";
import { DeskJobProvider } from "@/lib/desk-job-context";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: "Trading Bulls",
    template: "%s · Trading Bulls",
  },
  description:
    "Trading Bulls — India equity desks: screeners, paper books, charts, and AI research.",
  applicationName: "Trading Bulls",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <DeskJobProvider>
          <Nav />
          <DeskJobStatusBar />
          <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 py-8">{children}</main>
        </DeskJobProvider>
        <footer className="text-muted text-xs text-center py-6 border-t border-border">
          Trading Bulls · paper-trading simulation · research only, not financial advice
        </footer>
      </body>
    </html>
  );
}
