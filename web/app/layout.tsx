import "./globals.css";
import { Inter } from "next/font/google";
import type { Metadata } from "next";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
export const metadata: Metadata = { title: "DocQA – Ask your documents", description: "RAG document question answering with citations" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans`}>{children}</body>
    </html>
  );
}
