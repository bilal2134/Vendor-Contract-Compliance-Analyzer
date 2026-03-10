import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vendor Contract Compliance Analyzer",
  description: "Audit-first procurement compliance review workspace.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <nav className="site-nav">
          <Link href="/" className="nav-brand">
            <span className="nav-dot" />
            Compliance Analyzer
          </Link>
          <div className="nav-links">
            <Link href="/" className="nav-link">Dashboard</Link>
            <Link href="/upload" className="nav-link">Upload</Link>
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="nav-link-primary"
            >
              API Docs ↗
            </a>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
