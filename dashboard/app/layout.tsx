import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { THEME_SCRIPT } from "@/lib/theme-script";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const DESCRIPTION =
  "Daily-updated trends in remote developer jobs for Philippines-based developers: in-demand skills, stated pay in PHP, and roles open to PH applicants.";

export const metadata: Metadata = {
  metadataBase: new URL("https://ph-dev-job-market-radar.vercel.app"),
  title: { default: "PH Dev Job Market Radar", template: "%s · PH Dev Job Market Radar" },
  description: DESCRIPTION,
  openGraph: {
    type: "website",
    siteName: "PH Dev Job Market Radar",
    title: "PH Dev Job Market Radar",
    description: DESCRIPTION,
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: the inline script may add the "dark" class before React hydrates.
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
