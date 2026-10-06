import type { Metadata } from "next";
import { JetBrains_Mono, Sora } from "next/font/google";
import "./globals.css";

const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "OpsPilot — AI SRE Incident Commander",
  description:
    "Evidence-backed incident diagnosis with human-in-the-loop remediation approval.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${sora.variable} ${jetbrains.variable} font-display antialiased`}>
        <div className="relative min-h-screen">
          <div className="pointer-events-none absolute inset-0 grid-fade" />
          <div className="relative z-10">{children}</div>
        </div>
      </body>
    </html>
  );
}
