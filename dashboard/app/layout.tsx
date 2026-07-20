import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "gaet — Dashboard",
  description: "gaet: Database Backup & Sync",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
