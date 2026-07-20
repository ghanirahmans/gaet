import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "gaet — Dashboard",
  description: "gaet: Database Backup & Sync Dashboard",
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='12' fill='%233b82f6'/><text x='50' y='68' font-size='48' font-family='Arial' font-weight='bold' fill='white' text-anchor='middle'>G</text></svg>",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                const theme = localStorage.getItem('gaet-theme');
                if (theme) document.documentElement.setAttribute('data-theme', theme);
                else if (window.matchMedia('(prefers-color-scheme: light)').matches) document.documentElement.setAttribute('data-theme', 'light');
              } catch(e) {}
            `,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
