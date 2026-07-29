import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pocket.ai Studio",
  description: "Meeting intelligence and executive coaching for Pocket.ai recordings",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="masthead">
            <h1>Pocket.ai Studio</h1>
            <nav>
              <Link href="/">Meetings</Link>
              <Link href="/chat">Chat</Link>
              <Link href="/coach">Coach</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
