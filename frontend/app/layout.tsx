import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LUMA — Funeral Home Form Automation",
  description: "Learning Universal Machine Architecture",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
